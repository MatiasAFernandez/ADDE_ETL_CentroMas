import pandas as pd
from sqlalchemy import create_engine, text
from db_conexion import obtener_uris
from datetime import datetime

def obtener_temporada(mes):
    if mes in [12, 1, 2]: return 'Verano'
    if mes in [3, 4, 5]: return 'Otoño'
    if mes in [6, 7, 8]: return 'Invierno'
    return 'Primavera'

def calcular_edad(fecha_nacimiento):
    if pd.isnull(fecha_nacimiento): return None
    hoy = datetime.now()
    return hoy.year - fecha_nacimiento.year - ((hoy.month, hoy.day) < (fecha_nacimiento.month, fecha_nacimiento.day))

def ejecutar_carga_dw():
    try:
        master_uri, _, dw_uri = obtener_uris()
        clean_uri = master_uri.replace('master', 'CentroMas_Staging_Clean')
        
        engine_clean = create_engine(clean_uri)
        engine_dw = create_engine(dw_uri)
        
        print("\n==========================================")
        print(" 🏗️ INICIANDO CARGA FINAL AL DW")
        print("==========================================\n")

        # --- 0. IDEMPOTENCIA ---
        print("[*] [IDEMPOTENCIA] Limpiando tablas del DW para carga inicial...")
        with engine_dw.connect() as conn:
            conn.execute(text("DELETE FROM Fact_Venta"))
            conn.execute(text("DELETE FROM Dim_Cliente; DBCC CHECKIDENT ('Dim_Cliente', RESEED, 0)"))
            conn.execute(text("DELETE FROM Dim_Producto; DBCC CHECKIDENT ('Dim_Producto', RESEED, 0)"))
            conn.execute(text("DELETE FROM Dim_Sucursal; DBCC CHECKIDENT ('Dim_Sucursal', RESEED, 0)"))
            conn.execute(text("DELETE FROM Dim_Tiempo"))
            conn.commit()

        # --- 1. DIMENSIÓN TIEMPO ---
        print("-> [1/5] Generando Dim_Tiempo...")
        df_orders_dates = pd.read_sql("SELECT MIN(order_date) as min_d, MAX(order_date) as max_d FROM clean_orders", engine_clean)
        fechas = pd.date_range(start=df_orders_dates['min_d'][0], end=df_orders_dates['max_d'][0])
        
        df_tiempo = pd.DataFrame({'fecha_completa': fechas})
        df_tiempo['sk_tiempo'] = df_tiempo['fecha_completa'].dt.strftime('%Y%m%d').astype(int)
        df_tiempo['dia_nro'] = df_tiempo['fecha_completa'].dt.day
        df_tiempo['mes_nro'] = df_tiempo['fecha_completa'].dt.month
        df_tiempo['anio_nro'] = df_tiempo['fecha_completa'].dt.year
        df_tiempo['temporada'] = df_tiempo['mes_nro'].apply(obtener_temporada)
        
        df_tiempo.to_sql('Dim_Tiempo', engine_dw, if_exists='append', index=False)

        # --- 2. DIMENSIÓN SUCURSAL ---
        print("-> [2/5] Cargando Dim_Sucursal...")
        df_stg_stores = pd.read_sql("SELECT store_id as id_sucursal_bk, surface_m2 as superficie_m2, city as ciudad_sucursal, province as provincia_sucursal, opening_date FROM clean_stores", engine_clean)
        df_stg_stores['fecha_inicio'] = df_stg_stores['opening_date']
        df_stg_stores['fecha_fin'] = None
        df_stg_stores['es_actual'] = 1
        # Insertamos en DB (sin adivinar IDs)
        df_stg_stores.drop(columns=['opening_date']).to_sql('Dim_Sucursal', engine_dw, if_exists='append', index=False)

        # --- 3. DIMENSIÓN PRODUCTO ---
        print("-> [3/5] Cargando Dim_Producto...")
        df_stg_prod = pd.read_sql("SELECT sku as id_producto_bk, product_name as producto_nombre, brand as marca_nombre, category_name as categoria_nombre, unit_cost as costo_unidad, list_price as precio_lista, fecha_carga FROM clean_products", engine_clean)
        df_stg_prod['fecha_inicio'] = df_stg_prod['fecha_carga']
        df_stg_prod['fecha_fin'] = None
        df_stg_prod['es_actual'] = 1
        df_stg_prod.drop(columns=['fecha_carga']).to_sql('Dim_Producto', engine_dw, if_exists='append', index=False)

        # --- 4. DIMENSIÓN CLIENTE ---
        print("-> [4/5] Cargando Dim_Cliente...")
        df_stg_cust = pd.read_sql("SELECT customer_code as id_cliente_bk, gender as genero, birth_date, customer_type as tipo_cliente, city as ciudad_cliente, province as provincia_cliente, registration_date FROM clean_customers", engine_clean)
        df_stg_cust['birth_date'] = pd.to_datetime(df_stg_cust['birth_date'])
        df_stg_cust['edad'] = df_stg_cust['birth_date'].apply(calcular_edad)
        df_stg_cust['fecha_inicio'] = df_stg_cust['registration_date']
        df_stg_cust['fecha_fin'] = None
        df_stg_cust['es_actual'] = 1
        df_stg_cust.drop(columns=['birth_date', 'registration_date']).to_sql('Dim_Cliente', engine_dw, if_exists='append', index=False)

        # --- 5. TABLA DE HECHOS (MAPEO 100% SEGURO) ---
        print("-> [5/5] Cargando Fact_Venta (Leyendo SKs reales del DW)...")
        query_hechos = """
            SELECT o.order_date, o.customer_id, o.store_id, d.product_id, o.order_id as nro_ticket, 
                   d.quantity as cantidad_vendida, d.unit_price as precio_unitario, 
                   (d.quantity * d.unit_price) as monto_bruto, d.discount_amount as descuento_aplicado, d.net_amount as monto_neto
            FROM clean_orders o
            JOIN clean_order_details d ON o.order_id = d.order_id
        """
        df_fact = pd.read_sql(query_hechos, engine_clean)
        df_fact['order_date'] = pd.to_datetime(df_fact['order_date'])
        df_fact['sk_tiempo'] = df_fact['order_date'].dt.strftime('%Y%m%d').astype(int)

        # 5.1 MAPEO SUCURSALES
        # Traemos las claves reales de la base de datos
        map_suc = pd.read_sql("SELECT sk_sucursal, id_sucursal_bk FROM Dim_Sucursal WHERE es_actual = 1", engine_dw)
        map_suc['id_sucursal_bk'] = map_suc['id_sucursal_bk'].astype(str) # Evitar errores de tipo
        df_fact['store_id_str'] = df_fact['store_id'].astype(str)
        df_fact = df_fact.merge(map_suc, left_on='store_id_str', right_on='id_sucursal_bk', how='inner').drop(columns=['id_sucursal_bk', 'store_id_str'])

        # 5.2 MAPEO PRODUCTOS
        # Como los hechos usan 'product_id', necesitamos cruzarlo usando el SKU
        map_prod = pd.read_sql("SELECT sk_producto, id_producto_bk FROM Dim_Producto WHERE es_actual = 1", engine_dw)
        link_prod = pd.read_sql("SELECT product_id, sku FROM clean_products", engine_clean)
        # Cruzamos el ID natural con el SKU, y el SKU con el SK
        map_prod_final = link_prod.merge(map_prod, left_on='sku', right_on='id_producto_bk')[['product_id', 'sk_producto']]
        df_fact = df_fact.merge(map_prod_final, on='product_id', how='inner')

        # 5.3 MAPEO CLIENTES
        map_cli = pd.read_sql("SELECT sk_cliente, id_cliente_bk FROM Dim_Cliente WHERE es_actual = 1", engine_dw)
        link_cli = pd.read_sql("SELECT customer_id, customer_code FROM clean_customers", engine_clean)
        map_cli_final = link_cli.merge(map_cli, left_on='customer_code', right_on='id_cliente_bk')[['customer_id', 'sk_cliente']]
        df_fact = df_fact.merge(map_cli_final, on='customer_id', how='inner')

        # 5.4 CARGA FINAL
        cols_fact = ['sk_tiempo', 'sk_cliente', 'sk_producto', 'sk_sucursal', 'nro_ticket', 
                     'cantidad_vendida', 'precio_unitario', 'monto_bruto', 'descuento_aplicado', 'monto_neto']
        
        df_fact[cols_fact].to_sql('Fact_Venta', engine_dw, if_exists='append', index=False, chunksize=5000)

        print("\n[ÉXITO] El Data Warehouse ha sido cargado completamente.")
        print("------------------------------------------")
        print(f"Líneas de tickets procesadas y guardadas: {len(df_fact)}")
        print("==========================================\n")

    except Exception as e:
        print(f"\n[ERROR FATAL] {e}")

if __name__ == "__main__":
    ejecutar_carga_dw()