import pandas as pd
from sqlalchemy import create_engine, text
from db_conexion import obtener_uris
from datetime import datetime

def calcular_edad(fecha_nacimiento):
    if pd.isnull(fecha_nacimiento): return None
    hoy = datetime.now()
    return hoy.year - fecha_nacimiento.year - ((hoy.month, hoy.day) < (fecha_nacimiento.month, fecha_nacimiento.day))

def actualizar_dimension(engine_dw, nombre_tabla, sk_columna, bk_columna, df_nuevos, df_cambios, fecha_ejecucion):
    """Función genérica para aplicar SCD Tipo 2 en la base de datos."""
    with engine_dw.begin() as conn:
        # 1. CERRAR HISTORIAL VIEJO (UPDATE)
        if not df_cambios.empty:
            sks_a_cerrar = df_cambios[f'{sk_columna}_dw'].astype(int).tolist()
            # Formatear la lista para la query SQL
            sks_str = ','.join(map(str, sks_a_cerrar))
            query_update = text(f"""
                UPDATE {nombre_tabla} 
                SET es_actual = 0, fecha_fin = :fecha_fin 
                WHERE {sk_columna} IN ({sks_str})
            """)
            conn.execute(query_update, {"fecha_fin": fecha_ejecucion})
            print(f"      -> {len(sks_a_cerrar)} registros históricos cerrados en {nombre_tabla}.")

    # 2. ABRIR HISTORIAL NUEVO Y AGREGAR INÉDITOS (INSERT)
    df_a_insertar = pd.concat([df_nuevos, df_cambios], ignore_index=True)
    if not df_a_insertar.empty:
        # Limpiar columnas de control del cruce (_dw)
        columnas_validas = [col for col in df_a_insertar.columns if not col.endswith('_dw') and col != sk_columna]
        df_final = df_a_insertar[columnas_validas].copy()
        
        # Setear banderas SCD2
        df_final['fecha_inicio'] = fecha_ejecucion
        df_final['fecha_fin'] = None
        df_final['es_actual'] = 1
        
        df_final.to_sql(nombre_tabla, engine_dw, if_exists='append', index=False)
        print(f"      -> {len(df_final)} registros insertados en {nombre_tabla} (Nuevos + Versiones actualizadas).")
    else:
        print(f"      -> Sin cambios ni registros nuevos para {nombre_tabla}.")

def ejecutar_carga_incremental():
    try:
        master_uri, _, dw_uri = obtener_uris()
        clean_uri = master_uri.replace('master', 'CentroMas_Staging_Clean')
        
        engine_clean = create_engine(clean_uri)
        engine_dw = create_engine(dw_uri)
        fecha_ejecucion = datetime.now()
        fecha_ejecucion_date = fecha_ejecucion.date()

        print("\n==========================================")
        print(" 🔄 INICIANDO CARGA INCREMENTAL (CDC & SCD2)")
        print("==========================================\n")

        # --- 1. ACTUALIZAR DIMENSIÓN TIEMPO ---
        print("-> [1/5] Verificando Dim_Tiempo...")
        # Traemos la fecha máxima que ingresó hoy
        max_date_stg = pd.read_sql("SELECT MAX(order_date) as max_d FROM clean_orders", engine_clean).iloc[0,0]
        # Traemos la fecha máxima que ya existe en el DW
        max_date_dw_str = pd.read_sql("SELECT MAX(sk_tiempo) as max_sk FROM Dim_Tiempo", engine_dw).iloc[0,0]
        max_date_dw = datetime.strptime(str(max_date_dw_str), '%Y%m%d').date() if max_date_dw_str else None

        if max_date_stg and max_date_dw and max_date_stg.date() > max_date_dw:
            fechas_nuevas = pd.date_range(start=max_date_dw + pd.Timedelta(days=1), end=max_date_stg.date())
            if not fechas_nuevas.empty:
                df_tiempo = pd.DataFrame({'fecha_completa': fechas_nuevas})
                df_tiempo['sk_tiempo'] = df_tiempo['fecha_completa'].dt.strftime('%Y%m%d').astype(int)
                df_tiempo['dia_nro'] = df_tiempo['fecha_completa'].dt.day
                df_tiempo['mes_nro'] = df_tiempo['fecha_completa'].dt.month
                df_tiempo['anio_nro'] = df_tiempo['fecha_completa'].dt.year
                df_tiempo['temporada'] = df_tiempo['mes_nro'].apply(lambda m: 'Verano' if m in [12,1,2] else ('Otoño' if m in [3,4,5] else ('Invierno' if m in [6,7,8] else 'Primavera')))
                df_tiempo.to_sql('Dim_Tiempo', engine_dw, if_exists='append', index=False)
                print(f"   [+] {len(df_tiempo)} nuevos días agregados al calendario.")
        else:
            print("   [=] El calendario está al día.")

        # --- 2. SCD2: DIMENSIÓN SUCURSAL ---
        print("\n-> [2/5] Procesando SCD2 en Dim_Sucursal...")
        df_stg_suc = pd.read_sql("SELECT store_id as id_sucursal_bk, surface_m2 as superficie_m2, city as ciudad_sucursal, province as provincia_sucursal FROM clean_stores", engine_clean)
        df_dw_suc = pd.read_sql("SELECT sk_sucursal, id_sucursal_bk, superficie_m2, ciudad_sucursal, provincia_sucursal FROM Dim_Sucursal WHERE es_actual = 1", engine_dw)
        
        # Convertir BKs al mismo tipo para asegurar el cruce
        df_stg_suc['id_sucursal_bk'] = df_stg_suc['id_sucursal_bk'].astype(str)
        df_dw_suc['id_sucursal_bk'] = df_dw_suc['id_sucursal_bk'].astype(str)

        # Merge de comparación (Left Join)
        merged_suc = df_stg_suc.merge(df_dw_suc, on='id_sucursal_bk', how='left', suffixes=('', '_dw'))
        
        nuevas_suc = merged_suc[merged_suc['sk_sucursal_dw'].isna()].copy()
        existentes_suc = merged_suc[merged_suc['sk_sucursal_dw'].notna()].copy()
        
        # Detectar cambios exactos en atributos
        cond_suc = (
            (existentes_suc['superficie_m2'].astype(float) != existentes_suc['superficie_m2_dw'].astype(float)) |
            (existentes_suc['ciudad_sucursal'] != existentes_suc['ciudad_sucursal_dw']) |
            (existentes_suc['provincia_sucursal'] != existentes_suc['provincia_sucursal_dw'])
        )
        cambios_suc = existentes_suc[cond_suc].copy()
        
        actualizar_dimension(engine_dw, 'Dim_Sucursal', 'sk_sucursal', 'id_sucursal_bk', nuevas_suc, cambios_suc, fecha_ejecucion_date)

        # --- 3. SCD2: DIMENSIÓN PRODUCTO ---
        print("\n-> [3/5] Procesando SCD2 en Dim_Producto...")
        df_stg_prod = pd.read_sql("SELECT sku as id_producto_bk, product_name as producto_nombre, brand as marca_nombre, category_name as categoria_nombre, unit_cost as costo_unidad, list_price as precio_lista FROM clean_products", engine_clean)
        df_dw_prod = pd.read_sql("SELECT sk_producto, id_producto_bk, producto_nombre, marca_nombre, categoria_nombre, costo_unidad, precio_lista FROM Dim_Producto WHERE es_actual = 1", engine_dw)
        
        df_stg_prod['id_producto_bk'] = df_stg_prod['id_producto_bk'].astype(str)
        df_dw_prod['id_producto_bk'] = df_dw_prod['id_producto_bk'].astype(str)

        merged_prod = df_stg_prod.merge(df_dw_prod, on='id_producto_bk', how='left', suffixes=('', '_dw'))
        
        nuevas_prod = merged_prod[merged_prod['sk_producto_dw'].isna()].copy()
        existentes_prod = merged_prod[merged_prod['sk_producto_dw'].notna()].copy()
        
        cond_prod = (
            (existentes_prod['producto_nombre'] != existentes_prod['producto_nombre_dw']) |
            (existentes_prod['marca_nombre'] != existentes_prod['marca_nombre_dw']) |
            (existentes_prod['categoria_nombre'] != existentes_prod['categoria_nombre_dw']) |
            (existentes_prod['costo_unidad'].astype(float).round(2) != existentes_prod['costo_unidad_dw'].astype(float).round(2)) |
            (existentes_prod['precio_lista'].astype(float).round(2) != existentes_prod['precio_lista_dw'].astype(float).round(2))
        )
        cambios_prod = existentes_prod[cond_prod].copy()
        
        actualizar_dimension(engine_dw, 'Dim_Producto', 'sk_producto', 'id_producto_bk', nuevas_prod, cambios_prod, fecha_ejecucion_date)

        # --- 4. SCD2: DIMENSIÓN CLIENTE ---
        print("\n-> [4/5] Procesando SCD2 en Dim_Cliente...")
        df_stg_cust = pd.read_sql("SELECT customer_code as id_cliente_bk, gender as genero, birth_date, customer_type as tipo_cliente, city as ciudad_cliente, province as provincia_cliente FROM clean_customers", engine_clean)
        df_stg_cust['birth_date'] = pd.to_datetime(df_stg_cust['birth_date'])
        df_stg_cust['edad'] = df_stg_cust['birth_date'].apply(calcular_edad)
        # Descartamos birth_date ya que calculamos la edad
        df_stg_cust.drop(columns=['birth_date'], inplace=True)

        df_dw_cust = pd.read_sql("SELECT sk_cliente, id_cliente_bk, genero, edad, tipo_cliente, ciudad_cliente, provincia_cliente FROM Dim_Cliente WHERE es_actual = 1", engine_dw)
        
        df_stg_cust['id_cliente_bk'] = df_stg_cust['id_cliente_bk'].astype(str)
        df_dw_cust['id_cliente_bk'] = df_dw_cust['id_cliente_bk'].astype(str)

        merged_cust = df_stg_cust.merge(df_dw_cust, on='id_cliente_bk', how='left', suffixes=('', '_dw'))
        
        nuevos_cust = merged_cust[merged_cust['sk_cliente_dw'].isna()].copy()
        existentes_cust = merged_cust[merged_cust['sk_cliente_dw'].notna()].copy()
        
        cond_cust = (
            (existentes_cust['genero'] != existentes_cust['genero_dw']) |
            (existentes_cust['tipo_cliente'] != existentes_cust['tipo_cliente_dw']) |
            (existentes_cust['ciudad_cliente'] != existentes_cust['ciudad_cliente_dw']) |
            (existentes_cust['provincia_cliente'] != existentes_cust['provincia_cliente_dw']) |
            (existentes_cust['edad'].astype(float) != existentes_cust['edad_dw'].astype(float))
        )
        cambios_cust = existentes_cust[cond_cust].copy()
        
        actualizar_dimension(engine_dw, 'Dim_Cliente', 'sk_cliente', 'id_cliente_bk', nuevos_cust, cambios_cust, fecha_ejecucion_date)

        # --- 5. CARGA DE HECHOS (HIGH-WATER MARK CON NRO_TICKET) ---
        print("\n-> [5/5] Analizando y Cargando nuevos tickets en Fact_Venta...")
        # Obtener el High-Water Mark (último ticket insertado)
        hwm_query = "SELECT ISNULL(MAX(nro_ticket), 0) FROM Fact_Venta"
        hwm_ticket = pd.read_sql(hwm_query, engine_dw).iloc[0,0]
        print(f"   [*] High-Water Mark actual: Ticket #{hwm_ticket}")

        query_hechos_delta = f"""
            SELECT o.order_date, o.customer_id, o.store_id, d.product_id, o.order_id as nro_ticket, 
                   d.quantity as cantidad_vendida, d.unit_price as precio_unitario, 
                   (d.quantity * d.unit_price) as monto_bruto, d.discount_amount as descuento_aplicado, d.net_amount as monto_neto
            FROM clean_orders o
            JOIN clean_order_details d ON o.order_id = d.order_id
            WHERE o.order_id > {hwm_ticket}
        """
        df_fact_delta = pd.read_sql(query_hechos_delta, engine_clean)

        if df_fact_delta.empty:
            print("   [=] No se detectaron ventas nuevas. El DW de hechos está al día.")
        else:
            df_fact_delta['order_date'] = pd.to_datetime(df_fact_delta['order_date'])
            df_fact_delta['sk_tiempo'] = df_fact_delta['order_date'].dt.strftime('%Y%m%d').astype(int)

            # MAPEO CON LOS SK ACTIVOS ACTUALIZADOS EN ESTA EJECUCIÓN (es_actual = 1)
            # Mapeo Sucursales
            map_suc = pd.read_sql("SELECT sk_sucursal, id_sucursal_bk FROM Dim_Sucursal WHERE es_actual = 1", engine_dw)
            df_fact_delta['store_id'] = df_fact_delta['store_id'].astype(str)
            df_fact_delta = df_fact_delta.merge(map_suc, left_on='store_id', right_on='id_sucursal_bk', how='inner')

            # Mapeo Productos (A través de la llave natural de clean_products)
            map_prod = pd.read_sql("SELECT sk_producto, id_producto_bk FROM Dim_Producto WHERE es_actual = 1", engine_dw)
            link_prod = pd.read_sql("SELECT product_id, sku FROM clean_products", engine_clean)
            map_prod_final = link_prod.merge(map_prod, left_on='sku', right_on='id_producto_bk')[['product_id', 'sk_producto']]
            df_fact_delta = df_fact_delta.merge(map_prod_final, on='product_id', how='inner')

            # Mapeo Clientes
            map_cli = pd.read_sql("SELECT sk_cliente, id_cliente_bk FROM Dim_Cliente WHERE es_actual = 1", engine_dw)
            link_cli = pd.read_sql("SELECT customer_id, customer_code FROM clean_customers", engine_clean)
            map_cli_final = link_cli.merge(map_cli, left_on='customer_code', right_on='id_cliente_bk')[['customer_id', 'sk_cliente']]
            df_fact_delta = df_fact_delta.merge(map_cli_final, on='customer_id', how='inner')

            # Inserción final
            cols_fact = ['sk_tiempo', 'sk_cliente', 'sk_producto', 'sk_sucursal', 'nro_ticket', 
                         'cantidad_vendida', 'precio_unitario', 'monto_bruto', 'descuento_aplicado', 'monto_neto']
            
            df_fact_delta[cols_fact].to_sql('Fact_Venta', engine_dw, if_exists='append', index=False, chunksize=5000)
            
            print(f"   [+] {len(df_fact_delta)} nuevas líneas de ticket insertadas exitosamente.")

        print("\n[ÉXITO] Ejecución de Carga Incremental finalizada.")
        print("==========================================\n")

    except Exception as e:
        print(f"\n[ERROR FATAL] {e}")

if __name__ == "__main__":
    ejecutar_carga_incremental()