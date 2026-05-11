import pandas as pd
from sqlalchemy import create_engine, text, types
from db_conexion import obtener_uris
from datetime import datetime

DW_DB_NAME = 'CentroMas_DW'
CLEAN_DB_NAME = 'CentroMas_Staging_Clean'

def ejecutar_carga_incremental():
    try:
        master_uri, _, _ = obtener_uris()
        engine_dw = create_engine(master_uri.replace('master', DW_DB_NAME))
        engine_clean = create_engine(master_uri.replace('master', CLEAN_DB_NAME))
        
        fecha_ejecucion = datetime.now()
        print(f"[*] Iniciando Carga Incremental: {fecha_ejecucion.strftime('%Y-%m-%d %H:%M:%S')}")

        # ==========================================
        # PASO 1: DETERMINAR EL HIGH-WATER MARK (HWM)
        # ==========================================
        with engine_dw.connect() as conn:
            max_ticket = conn.execute(text("SELECT ISNULL(MAX(nro_ticket), 0) FROM Fact_Venta")).fetchone()[0]
        
        print(f"-> [HWM] Último ticket en DW: {max_ticket}")

        # ==========================================
        # PASO 2: CARGA DE DELTAS
        # ==========================================
        df_orders_delta = pd.read_sql(f"SELECT * FROM clean_orders WHERE order_id > {max_ticket}", engine_clean)
        hay_ventas = not df_orders_delta.empty
        
        if hay_ventas:
            print(f"-> Procesando {len(df_orders_delta)} nuevas órdenes.")
            order_ids = tuple(df_orders_delta['order_id'].tolist())
            query_details = f"SELECT * FROM clean_order_details WHERE order_id IN {order_ids}" if len(order_ids) > 1 else f"SELECT * FROM clean_order_details WHERE order_id = {order_ids[0]}"
            df_details_delta = pd.read_sql(query_details, engine_clean)

        # ==========================================
        # PASO 3: GESTIÓN DE DIMENSIONES (SCD TIPO 2)
        # ==========================================
        print("-> [SCD2] Verificando cambios en dimensiones...")
        stg_cust = pd.read_sql("SELECT * FROM clean_customers", engine_clean)
        if not stg_cust.empty:
            for _, row in stg_cust.iterrows():
                query_check = text("""
                    SELECT sk_cliente, ciudad_cliente, provincia_cliente FROM Dim_Cliente 
                    WHERE id_cliente_bk = :bk AND es_actual = 1
                """)
                with engine_dw.connect() as conn:
                    current_dw = conn.execute(query_check, {"bk": row['customer_code']}).fetchone()
                    if current_dw and (current_dw.ciudad_cliente != row['city'] or current_dw.provincia_cliente != row['province']):
                        conn.execute(text("UPDATE Dim_Cliente SET fecha_fin = :fecha, es_actual = 0 WHERE sk_cliente = :sk"), 
                                     {"fecha": fecha_ejecucion, "sk": current_dw.sk_cliente})
                        edad = int((fecha_ejecucion - pd.to_datetime(row['birth_date'])).days / 365.25) if pd.notnull(row['birth_date']) else None
                        conn.execute(text("""
                            INSERT INTO Dim_Cliente (id_cliente_bk, genero, edad, tipo_cliente, ciudad_cliente, provincia_cliente, fecha_inicio, es_actual)
                            VALUES (:bk, :gen, :edad, 'Regular', :ciu, :prov, :fi, 1)
                        """), {"bk": row['customer_code'], "gen": row['gender'], "edad": edad, "ciu": row['city'], "prov": row['province'], "fi": fecha_ejecucion.date()})
                        conn.commit()

        # ==========================================
        # PASO 4: DICCIONARIOS DE TRADUCCIÓN (ID a CÓDIGO)
        # Guardamos la relación inmutable de IDs origen hacia Business Keys (BK).
        # ==========================================
        print("-> [DICCIONARIOS] Sincronizando IDs transaccionales con Business Keys...")

        # 4.1 Clientes
        try: dict_cli = pd.read_sql("SELECT * FROM dict_clientes", engine_clean)
        except: dict_cli = pd.DataFrame(columns=['customer_id', 'customer_code'])
        if not stg_cust.empty:
            dict_cli = pd.concat([dict_cli, stg_cust[['customer_id', 'customer_code']]]).drop_duplicates(subset=['customer_id'], keep='last')
            dict_cli.to_sql('dict_clientes', engine_clean, if_exists='replace', index=False)

        # 4.2 Productos
        stg_prod = pd.read_sql("SELECT * FROM clean_products", engine_clean)
        try: dict_prod = pd.read_sql("SELECT * FROM dict_productos", engine_clean)
        except: dict_prod = pd.DataFrame(columns=['product_id', 'sku'])
        if not stg_prod.empty:
            dict_prod = pd.concat([dict_prod, stg_prod[['product_id', 'sku']]]).drop_duplicates(subset=['product_id'], keep='last')
            dict_prod.to_sql('dict_productos', engine_clean, if_exists='replace', index=False)

        # ==========================================
        # PASO 5: BÚSQUEDA DIRECTA EN DATA WAREHOUSE Y CARGA
        # ==========================================
        if hay_ventas:
            print("-> [FACT] Cruzando ventas con dimensiones activas del DW...")
            
            df_fact = df_details_delta.merge(df_orders_delta, on='order_id', suffixes=('_det', '_ord'))
            df_fact['sk_tiempo'] = pd.to_datetime(df_fact['order_date']).dt.strftime('%Y%m%d').astype(int)
            
            # --- NUEVO: MANTENIMIENTO DINÁMICO DE DIM_TIEMPO ---
            fechas_unicas = df_fact['sk_tiempo'].unique()
            fechas_str = ",".join(map(str, fechas_unicas))
            
            # Consultamos qué fechas ya existen en el DW
            existentes = pd.read_sql(f"SELECT sk_tiempo FROM Dim_Tiempo WHERE sk_tiempo IN ({fechas_str})", engine_dw)
            fechas_existentes = existentes['sk_tiempo'].tolist()
            
            # Filtramos las que faltan
            fechas_faltantes = [sk for sk in fechas_unicas if sk not in fechas_existentes]
            
            if fechas_faltantes:
                print(f"    -> Detectadas {len(fechas_faltantes)} nuevas fechas. Agregando a Dim_Tiempo...")
                def obtener_temporada(mes):
                    if mes in [12, 1, 2]: return 'Verano'
                    if mes in [3, 4, 5]: return 'Otoño'
                    if mes in [6, 7, 8]: return 'Invierno'
                    return 'Primavera'

                nuevas_fechas_dt = [datetime.strptime(str(sk), '%Y%m%d') for sk in fechas_faltantes]
                df_tiempo_nuevo = pd.DataFrame({'fecha_completa': nuevas_fechas_dt, 'sk_tiempo': fechas_faltantes})
                df_tiempo_nuevo['dia_nro'] = df_tiempo_nuevo['fecha_completa'].dt.day
                df_tiempo_nuevo['mes_nro'] = df_tiempo_nuevo['fecha_completa'].dt.month
                df_tiempo_nuevo['anio_nro'] = df_tiempo_nuevo['fecha_completa'].dt.year
                df_tiempo_nuevo['temporada'] = df_tiempo_nuevo['mes_nro'].apply(obtener_temporada)
                
                df_tiempo_nuevo.to_sql('Dim_Tiempo', engine_dw, if_exists='append', index=False)
            # ---------------------------------------------------

            # A) Traducir el idioma del Origen al idioma del DW usando nuestros diccionarios
            df_fact = df_fact.merge(dict_cli, on='customer_id', how='inner')
            df_fact = df_fact.merge(dict_prod, on='product_id', how='inner')
            df_fact['id_sucursal_bk'] = df_fact['store_id'] # Sucursal usa ID directo como BK
            
            # B) Buscar los Surrogate Keys DIRECTO en el DW (Solo las versiones actuales)
            dim_cli = pd.read_sql("SELECT sk_cliente, id_cliente_bk as customer_code FROM Dim_Cliente WHERE es_actual = 1", engine_dw)
            dim_prod = pd.read_sql("SELECT sk_producto, id_producto_bk as sku FROM Dim_Producto WHERE es_actual = 1", engine_dw)
            dim_suc = pd.read_sql("SELECT sk_sucursal, id_sucursal_bk FROM Dim_Sucursal WHERE es_actual = 1", engine_dw)
            
            # C) Asignar los SK a las ventas
            df_fact = df_fact.merge(dim_cli, on='customer_code', how='inner')
            df_fact = df_fact.merge(dim_prod, on='sku', how='inner')
            df_fact = df_fact.merge(dim_suc, on='id_sucursal_bk', how='inner')

            # Renombrar y calcular métricas
            df_fact = df_fact.rename(columns={'order_id': 'nro_ticket', 'unit_price': 'precio_unitario', 'net_amount_det': 'monto_neto', 'quantity': 'cantidad_vendida', 'discount_amount': 'descuento_aplicado'})
            df_fact['monto_bruto'] = df_fact['cantidad_vendida'] * df_fact['precio_unitario']
            cols_fact = ['sk_tiempo', 'sk_cliente', 'sk_producto', 'sk_sucursal', 'nro_ticket', 'cantidad_vendida', 'precio_unitario', 'monto_bruto', 'descuento_aplicado', 'monto_neto']
            
            df_fact_final = df_fact[cols_fact]

            print(f"[*] Insertando {len(df_fact_final)} filas en Fact_Venta...")
            df_fact_final.to_sql('Fact_Venta', engine_dw, if_exists='append', index=False, method='multi', dtype={'precio_unitario': types.Numeric(12,2), 'monto_bruto': types.Numeric(12,2), 'monto_neto': types.Numeric(12,2), 'cantidad_vendida': types.Numeric(10,2), 'descuento_aplicado': types.Numeric(12,2)})
            print(f"-> Se procesaron ventas hasta el ticket: {df_orders_delta['order_id'].max()}")

        print("\n[ÉXITO] Carga Incremental Finalizada Correctamente.")

    except Exception as e:
        print(f"\n[ERROR EN INCREMENTAL] {e}")

if __name__ == "__main__":
    ejecutar_carga_incremental()