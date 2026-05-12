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
        # --- 3.1 SCD TIPO 2 Y NUEVOS: CLIENTES ---
        stg_cust = pd.read_sql("SELECT * FROM clean_customers", engine_clean)
        if not stg_cust.empty:
            print("    -> Verificando Clientes (SCD2 y Nuevos)...")
            for _, row in stg_cust.iterrows():
                query_check = text("""
                    SELECT sk_cliente, ciudad_cliente, provincia_cliente FROM Dim_Cliente 
                    WHERE id_cliente_bk = :bk AND es_actual = 1
                """)
                with engine_dw.connect() as conn:
                    current_dw = conn.execute(query_check, {"bk": row['customer_code']}).fetchone()
                    
                    # CASO A: El cliente ya existe
                    if current_dw:
                        # Verificamos si hubo cambios en ubicación para aplicar SCD2
                        if (current_dw.ciudad_cliente != row['city'] or current_dw.provincia_cliente != row['province']):
                            # Cerramos registro actual
                            conn.execute(text("UPDATE Dim_Cliente SET fecha_fin = :fecha, es_actual = 0 WHERE sk_cliente = :sk"), 
                                         {"fecha": fecha_ejecucion.date(), "sk": current_dw.sk_cliente})
                            
                            # Insertamos nueva versión
                            edad = int((fecha_ejecucion - pd.to_datetime(row['birth_date'])).days / 365.25) if pd.notnull(row['birth_date']) else None
                            conn.execute(text("""
                                INSERT INTO Dim_Cliente (id_cliente_bk, genero, edad, tipo_cliente, ciudad_cliente, provincia_cliente, fecha_inicio, es_actual)
                                VALUES (:bk, :gen, :edad, :tipo, :ciu, :prov, :fi, 1)
                            """), {"bk": row['customer_code'], "gen": row['gender'], "edad": edad, "tipo": row['customer_type'], 
                                   "ciu": row['city'], "prov": row['province'], "fi": fecha_ejecucion.date()})
                    
                    # CASO B: El cliente es totalmente nuevo (Lo que faltaba)
                    else:
                        edad = int((fecha_ejecucion - pd.to_datetime(row['birth_date'])).days / 365.25) if pd.notnull(row['birth_date']) else None
                        conn.execute(text("""
                            INSERT INTO Dim_Cliente (id_cliente_bk, genero, edad, tipo_cliente, ciudad_cliente, provincia_cliente, fecha_inicio, es_actual)
                            VALUES (:bk, :gen, :edad, :tipo, :ciu, :prov, :fi, 1)
                        """), {"bk": row['customer_code'], "gen": row['gender'], "edad": edad, "tipo": row['customer_type'], 
                               "ciu": row['city'], "prov": row['province'], "fi": row['registration_date']})
                    conn.commit()
        # --- 3.2 SCD TIPO 2: PRODUCTOS ---
        stg_prod = pd.read_sql("SELECT * FROM clean_products", engine_clean)
        
        if not stg_prod.empty:
            print("    -> Verificando Productos (SCD2 y Nuevos)...")
            for _, row in stg_prod.iterrows():
                query_check_prod = text("""
                    SELECT sk_producto, costo_unidad, precio_lista, categoria_nombre 
                    FROM Dim_Producto 
                    WHERE id_producto_bk = :bk AND es_actual = 1
                """)
                with engine_dw.connect() as conn:
                    current_dw_prod = conn.execute(query_check_prod, {"bk": row['sku']}).fetchone()
                    
                    if current_dw_prod:
                        # 1. Normalización: Convertimos todo a float para comparar manzanas con manzanas
                        # Usamos 'or 0' por si algún campo viene NULL de la base
                        costo_dw = float(current_dw_prod.costo_unidad or 0)
                        costo_stg = float(row['unit_cost'] or 0)
                        precio_dw = float(current_dw_prod.precio_lista or 0)
                        precio_stg = float(row['list_price'] or 0)
                        
                        # 2. Limpieza de strings para evitar fallos por espacios invisibles
                        cat_dw = str(current_dw_prod.categoria_nombre or "").strip()
                        cat_stg = str(row['category_name_y'] or "").strip()

                        # 3. Comparación robusta: ¿La diferencia es mayor a 1 centavo?
                        hubo_cambio = (
                            abs(costo_dw - costo_stg) > 0.01 or 
                            abs(precio_dw - precio_stg) > 0.01 or 
                            cat_dw != cat_stg
                        )

                        if hubo_cambio:
                            # Cerramos versión vieja
                            conn.execute(text("UPDATE Dim_Producto SET fecha_fin = :fecha, es_actual = 0 WHERE sk_producto = :sk"), 
                                         {"fecha": fecha_ejecucion.date(), "sk": current_dw_prod.sk_producto})
                            
                            # Insertamos versión nueva
                            conn.execute(text("""
                                INSERT INTO Dim_Producto (id_producto_bk, producto_nombre, marca_nombre, categoria_nombre, costo_unidad, precio_lista, fecha_inicio, es_actual)
                                VALUES (:bk, :nom, :marca, :cat, :costo, :precio, :fi, 1)
                            """), {"bk": row['sku'], "nom": row['product_name'], "marca": row['brand'], "cat": cat_stg, 
                                   "costo": row['unit_cost'], "precio": row['list_price'], "fi": fecha_ejecucion.date()})
                            conn.commit()
                    
                    else:
                        # CASO B: Producto totalmente nuevo (Insert puro)
                        conn.execute(text("""
                            INSERT INTO Dim_Producto (id_producto_bk, producto_nombre, marca_nombre, categoria_nombre, costo_unidad, precio_lista, fecha_inicio, es_actual)
                            VALUES (:bk, :nom, :marca, :cat, :costo, :precio, :fi, 1)
                        """), {"bk": row['sku'], "nom": row['product_name'], "marca": row['brand'], "cat": str(row['category_name_y']).strip(), 
                               "costo": row['unit_cost'], "precio": row['list_price'], "fi": fecha_ejecucion.date()})
                        conn.commit()
                    
        # --- 3.3 SCD TIPO 2 Y NUEVOS: SUCURSALES ---
        stg_stores = pd.read_sql("SELECT * FROM clean_stores", engine_clean)
        if not stg_stores.empty:
            print("    -> Verificando Sucursales (SCD2 y Nuevas)...")
            for _, row in stg_stores.iterrows():
                query_check_suc = text("""
                    SELECT sk_sucursal, superficie_m2, ciudad_sucursal, provincia_sucursal 
                    FROM Dim_Sucursal 
                    WHERE id_sucursal_bk = :bk AND es_actual = 1
                """)
                with engine_dw.connect() as conn:
                    # SQL Server usa store_id como entero, aseguramos el tipo
                    current_dw_suc = conn.execute(query_check_suc, {"bk": int(row['store_id'])}).fetchone()
                    
                    # CASO A: La sucursal ya existe
                    if current_dw_suc:
                        # Si cambió la superficie o ubicación, historizamos (SCD2)
                        if (current_dw_suc.superficie_m2 != row['surface_m2'] or 
                            current_dw_suc.ciudad_sucursal != row['city'] or 
                            current_dw_suc.provincia_sucursal != row['province']):
                            
                            conn.execute(text("UPDATE Dim_Sucursal SET fecha_fin = :fecha, es_actual = 0 WHERE sk_sucursal = :sk"), 
                                         {"fecha": fecha_ejecucion.date(), "sk": current_dw_suc.sk_sucursal})
                            
                            conn.execute(text("""
                                INSERT INTO Dim_Sucursal (id_sucursal_bk, superficie_m2, ciudad_sucursal, provincia_sucursal, fecha_inicio, es_actual)
                                VALUES (:bk, :sup, :ciu, :prov, :fi, 1)
                            """), {"bk": int(row['store_id']), "sup": row['surface_m2'], "ciu": row['city'], "prov": row['province'], "fi": fecha_ejecucion.date()})
                    
                    # CASO B: Sucursal nueva
                    else:
                        conn.execute(text("""
                            INSERT INTO Dim_Sucursal (id_sucursal_bk, superficie_m2, ciudad_sucursal, provincia_sucursal, fecha_inicio, es_actual)
                            VALUES (:bk, :sup, :ciu, :prov, :fi, 1)
                        """), {"bk": int(row['store_id']), "sup": row['surface_m2'], "ciu": row['city'], "prov": row['province'], "fi": row['opening_date']})
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
        # PASO 5: BÚSQUEDA DIRECTA EN DATA WAREHOUSE Y CARGA (AS-WAS JOIN)
        # ==========================================
        if hay_ventas:
            print("-> [FACT] Cruzando ventas con el historial del DW (Cruce Temporal)...")
            
            df_fact = df_details_delta.merge(df_orders_delta, on='order_id', suffixes=('_det', '_ord'))
            df_fact['order_date'] = pd.to_datetime(df_fact['order_date'])
            df_fact['sk_tiempo'] = df_fact['order_date'].dt.strftime('%Y%m%d').astype(int)
            
            # --- MANTENIMIENTO DINÁMICO DE DIM_TIEMPO ---
            fechas_unicas = df_fact['sk_tiempo'].unique()
            fechas_str = ",".join(map(str, fechas_unicas))
            
            existentes = pd.read_sql(f"SELECT sk_tiempo FROM Dim_Tiempo WHERE sk_tiempo IN ({fechas_str})", engine_dw)
            fechas_existentes = existentes['sk_tiempo'].tolist()
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

            # A) Traducir el idioma del Origen al idioma del DW usando nuestros diccionarios (con LEFT JOIN por seguridad)
            df_fact = df_fact.merge(dict_cli, on='customer_id', how='left')
            df_fact = df_fact.merge(dict_prod, on='product_id', how='left')
            df_fact['id_sucursal_bk'] = df_fact['store_id'] 

            # B) Traer TODO el historial de las dimensiones (Reemplazando NULL por Fecha Infinita)
            dim_cli = pd.read_sql("SELECT sk_cliente, id_cliente_bk as customer_code, fecha_inicio, ISNULL(fecha_fin, '9999-12-31') as fecha_fin FROM Dim_Cliente", engine_dw)
            dim_prod = pd.read_sql("SELECT sk_producto, id_producto_bk as sku, fecha_inicio, ISNULL(fecha_fin, '9999-12-31') as fecha_fin FROM Dim_Producto", engine_dw)
            dim_suc = pd.read_sql("SELECT sk_sucursal, CAST(id_sucursal_bk AS VARCHAR) as id_sucursal_bk, fecha_inicio, ISNULL(fecha_fin, '9999-12-31') as fecha_fin FROM Dim_Sucursal", engine_dw)
            
            # Asegurar compatibilidad de tipos
            df_fact['id_sucursal_bk'] = df_fact['id_sucursal_bk'].astype(str)
            for d in [dim_cli, dim_prod, dim_suc]:
                d['fecha_inicio'] = pd.to_datetime(d['fecha_inicio'])
                d['fecha_fin'] = pd.to_datetime(d['fecha_fin'])

            # C) Función robusta para Cruce Temporal
            def aplicar_join_temporal(df_ventas, dim_df, bk_col, sk_col):
                # 1. Asignar ID único a cada fila de venta para no perder el rastro
                df_ventas['temp_row_id'] = range(len(df_ventas))

                # 2. Cruce inicial por Business Key (generará duplicados si la dimensión tiene historia)
                merged = df_ventas.merge(dim_df, on=bk_col, how='left')

                # 3. Filtrar para quedarse SOLO con la versión vigente en el momento de la venta
                mask_fecha = (merged['order_date'] >= merged['fecha_inicio']) & (merged['order_date'] <= merged['fecha_fin'])
                validos = merged[mask_fecha].copy()

                # 4. Atrapar ventas que NO encontraron coincidencia (fuera de fecha o ID inexistente)
                id_validos = validos['temp_row_id'].unique()
                huerfanas = df_ventas[~df_ventas['temp_row_id'].isin(id_validos)].copy()
                huerfanas[sk_col] = -1 # Clave del registro "Unknown"

                # 5. Unir los resultados y limpiar columnas auxiliares
                resultado = pd.concat([validos.drop(columns=['fecha_inicio', 'fecha_fin']), huerfanas], ignore_index=True)
                return resultado.drop(columns=['temp_row_id'])

            # D) Aplicar la función a las 3 dimensiones
            df_fact = aplicar_join_temporal(df_fact, dim_cli, 'customer_code', 'sk_cliente')
            df_fact = aplicar_join_temporal(df_fact, dim_prod, 'sku', 'sk_producto')
            df_fact = aplicar_join_temporal(df_fact, dim_suc, 'id_sucursal_bk', 'sk_sucursal')

            # E) Renombrar, calcular métricas y Guardar
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