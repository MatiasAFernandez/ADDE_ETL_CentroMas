import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text, types
from db_conexion import obtener_uris
from datetime import datetime

CLEAN_DB_NAME = 'CentroMas_Staging_Clean'

def asegurar_idempotencia(master_uri):
    """Elimina y recrea la base de datos Clean para asegurar un inicio limpio."""
    print(f"\n[*] [IDEMPOTENCIA] Reiniciando '{CLEAN_DB_NAME}'...")
    engine_master = create_engine(master_uri, isolation_level="AUTOCOMMIT")
    with engine_master.connect() as conn:
        check_db = conn.execute(text(f"SELECT name FROM sys.databases WHERE name = '{CLEAN_DB_NAME}'")).fetchone()
        if check_db:
            conn.execute(text(f"ALTER DATABASE {CLEAN_DB_NAME} SET SINGLE_USER WITH ROLLBACK IMMEDIATE"))
            conn.execute(text(f"DROP DATABASE {CLEAN_DB_NAME}"))
        conn.execute(text(f"CREATE DATABASE {CLEAN_DB_NAME}"))
    print("    -> Base de datos recreada.")

def inicializar_lookups(engine_clean):
    """Crea y puebla las tablas de referencia (Lookups) para evitar el hard-coding."""
    print("[*] Configurando tablas Lookup de referencia...")
    
    # 1. Tabla para normalización de códigos de género
    df_map_codigos = pd.DataFrame([
        {'codigo_original': 'F', 'genero_estandar': 'Femenino'},
        {'codigo_original': 'M', 'genero_estandar': 'Masculino'}
    ])
    df_map_codigos.to_sql('lkp_genero_codigos', engine_clean, if_exists='replace', index=False)

    # 2. Diccionario de nombres para corrección de inconsistencias
    nombres_data = [
    {'nombre_clave': 'pedro',        'genero_inferido': 'Masculino'},
    {'nombre_clave': 'luis',         'genero_inferido': 'Masculino'},
    {'nombre_clave': 'jorge',        'genero_inferido': 'Masculino'},
    {'nombre_clave': 'carlos',       'genero_inferido': 'Masculino'},
    {'nombre_clave': 'pablo',        'genero_inferido': 'Masculino'},
    {'nombre_clave': 'juan',         'genero_inferido': 'Masculino'},
    {'nombre_clave': 'diego',        'genero_inferido': 'Masculino'},
    {'nombre_clave': 'andres',       'genero_inferido': 'Masculino'},
    {'nombre_clave': 'matias',       'genero_inferido': 'Masculino'},
    {'nombre_clave': 'franco',       'genero_inferido': 'Masculino'},
    {'nombre_clave': 'nicolas',      'genero_inferido': 'Masculino'},
    {'nombre_clave': 'sebastian',    'genero_inferido': 'Masculino'},
    {'nombre_clave': 'alejandro',    'genero_inferido': 'Masculino'},
    {'nombre_clave': 'gabriel',      'genero_inferido': 'Masculino'},
    {'nombre_clave': 'daniel',       'genero_inferido': 'Masculino'},
    {'nombre_clave': 'martin',       'genero_inferido': 'Masculino'},
    {'nombre_clave': 'lucas',        'genero_inferido': 'Masculino'},
    {'nombre_clave': 'santiago',     'genero_inferido': 'Masculino'},
    {'nombre_clave': 'miguel',       'genero_inferido': 'Masculino'},
    {'nombre_clave': 'jose',         'genero_inferido': 'Masculino'},
    {'nombre_clave': 'fernando',     'genero_inferido': 'Masculino'},
    {'nombre_clave': 'roberto',      'genero_inferido': 'Masculino'},
    {'nombre_clave': 'eduardo',      'genero_inferido': 'Masculino'},
    {'nombre_clave': 'alberto',      'genero_inferido': 'Masculino'},
    {'nombre_clave': 'gustavo',      'genero_inferido': 'Masculino'},
    {'nombre_clave': 'ricardo',      'genero_inferido': 'Masculino'},
    {'nombre_clave': 'mario',        'genero_inferido': 'Masculino'},
    {'nombre_clave': 'cristian',     'genero_inferido': 'Masculino'},
    {'nombre_clave': 'facundo',      'genero_inferido': 'Masculino'},
    {'nombre_clave': 'ezequiel',     'genero_inferido': 'Masculino'},
    {'nombre_clave': 'leandro',      'genero_inferido': 'Masculino'},
    {'nombre_clave': 'maximiliano',  'genero_inferido': 'Masculino'},
    {'nombre_clave': 'ignacio',      'genero_inferido': 'Masculino'},
    {'nombre_clave': 'federico',     'genero_inferido': 'Masculino'},
    {'nombre_clave': 'mariano',      'genero_inferido': 'Masculino'},
    {'nombre_clave': 'hernan',       'genero_inferido': 'Masculino'},
    {'nombre_clave': 'leonardo',     'genero_inferido': 'Masculino'},
    {'nombre_clave': 'victor',       'genero_inferido': 'Masculino'},
    {'nombre_clave': 'hugo',         'genero_inferido': 'Masculino'},
    {'nombre_clave': 'emilio',       'genero_inferido': 'Masculino'},
    {'nombre_clave': 'raul',         'genero_inferido': 'Masculino'},
    {'nombre_clave': 'oscar',        'genero_inferido': 'Masculino'},
    {'nombre_clave': 'sergio',       'genero_inferido': 'Masculino'},
    {'nombre_clave': 'julian',       'genero_inferido': 'Masculino'},
    {'nombre_clave': 'gonzalo',      'genero_inferido': 'Masculino'},
    {'nombre_clave': 'rodrigo',      'genero_inferido': 'Masculino'},
    {'nombre_clave': 'agustin',      'genero_inferido': 'Masculino'},
    {'nombre_clave': 'tomas',        'genero_inferido': 'Masculino'},
    {'nombre_clave': 'marcos',       'genero_inferido': 'Masculino'},
    {'nombre_clave': 'philippe',     'genero_inferido': 'Masculino'},
    {'nombre_clave': 'hector',       'genero_inferido': 'Masculino'},
    {'nombre_clave': 'walter',       'genero_inferido': 'Masculino'},
    {'nombre_clave': 'claudio',      'genero_inferido': 'Masculino'},
    {'nombre_clave': 'marcelo',      'genero_inferido': 'Masculino'},
    {'nombre_clave': 'ernesto',      'genero_inferido': 'Masculino'},
    {'nombre_clave': 'ivan',         'genero_inferido': 'Masculino'},
    {'nombre_clave': 'ariel',        'genero_inferido': 'Masculino'},
    {'nombre_clave': 'damian',       'genero_inferido': 'Masculino'},
    {'nombre_clave': 'patricio',     'genero_inferido': 'Masculino'},
    {'nombre_clave': 'esteban',      'genero_inferido': 'Masculino'},
    {'nombre_clave': 'german',       'genero_inferido': 'Masculino'},
    {'nombre_clave': 'christian',    'genero_inferido': 'Masculino'},
    {'nombre_clave': 'javier',       'genero_inferido': 'Masculino'},
    {'nombre_clave': 'ruben',        'genero_inferido': 'Masculino'},
    {'nombre_clave': 'horacio',      'genero_inferido': 'Masculino'},
    {'nombre_clave': 'nestor',       'genero_inferido': 'Masculino'},
    {'nombre_clave': 'alfredo',      'genero_inferido': 'Masculino'},
    {'nombre_clave': 'cesar',        'genero_inferido': 'Masculino'},
    {'nombre_clave': 'omar',         'genero_inferido': 'Masculino'},
    {'nombre_clave': 'rafael',       'genero_inferido': 'Masculino'},
    {'nombre_clave': 'manuel',       'genero_inferido': 'Masculino'},
    {'nombre_clave': 'alan',         'genero_inferido': 'Masculino'},
    {'nombre_clave': 'brian',        'genero_inferido': 'Masculino'},
    {'nombre_clave': 'kevin',        'genero_inferido': 'Masculino'},
    {'nombre_clave': 'lautaro',      'genero_inferido': 'Masculino'},
    {'nombre_clave': 'thiago',       'genero_inferido': 'Masculino'},
    {'nombre_clave': 'mateo',        'genero_inferido': 'Masculino'},
    {'nombre_clave': 'joaquin',      'genero_inferido': 'Masculino'},
    {'nombre_clave': 'alexis',       'genero_inferido': 'Masculino'},
    {'nombre_clave': 'maria',        'genero_inferido': 'Femenino'},
    {'nombre_clave': 'laura',        'genero_inferido': 'Femenino'},
    {'nombre_clave': 'ana',          'genero_inferido': 'Femenino'},
    {'nombre_clave': 'sofia',        'genero_inferido': 'Femenino'},
    {'nombre_clave': 'carla',        'genero_inferido': 'Femenino'},
    {'nombre_clave': 'lucia',        'genero_inferido': 'Femenino'},
    {'nombre_clave': 'valeria',      'genero_inferido': 'Femenino'},
    {'nombre_clave': 'fatima',       'genero_inferido': 'Femenino'},
    {'nombre_clave': 'andrea',       'genero_inferido': 'Femenino'},
    {'nombre_clave': 'paula',        'genero_inferido': 'Femenino'},
    {'nombre_clave': 'gabriela',     'genero_inferido': 'Femenino'},
    {'nombre_clave': 'marina',       'genero_inferido': 'Femenino'},
    {'nombre_clave': 'florencia',    'genero_inferido': 'Femenino'},
    {'nombre_clave': 'natalia',      'genero_inferido': 'Femenino'},
    {'nombre_clave': 'carolina',     'genero_inferido': 'Femenino'},
    {'nombre_clave': 'claudia',      'genero_inferido': 'Femenino'},
    {'nombre_clave': 'patricia',     'genero_inferido': 'Femenino'},
    {'nombre_clave': 'silvia',       'genero_inferido': 'Femenino'},
    {'nombre_clave': 'beatriz',      'genero_inferido': 'Femenino'},
    {'nombre_clave': 'monica',       'genero_inferido': 'Femenino'},
    {'nombre_clave': 'susana',       'genero_inferido': 'Femenino'},
    {'nombre_clave': 'veronica',     'genero_inferido': 'Femenino'},
    {'nombre_clave': 'alejandra',    'genero_inferido': 'Femenino'},
    {'nombre_clave': 'marcela',      'genero_inferido': 'Femenino'},
    {'nombre_clave': 'fernanda',     'genero_inferido': 'Femenino'},
    {'nombre_clave': 'romina',       'genero_inferido': 'Femenino'},
    {'nombre_clave': 'paola',        'genero_inferido': 'Femenino'},
    {'nombre_clave': 'vanesa',       'genero_inferido': 'Femenino'},
    {'nombre_clave': 'sabrina',      'genero_inferido': 'Femenino'},
    {'nombre_clave': 'lorena',       'genero_inferido': 'Femenino'},
    {'nombre_clave': 'cecilia',      'genero_inferido': 'Femenino'},
    {'nombre_clave': 'roxana',       'genero_inferido': 'Femenino'},
    {'nombre_clave': 'miriam',       'genero_inferido': 'Femenino'},
    {'nombre_clave': 'graciela',     'genero_inferido': 'Femenino'},
    {'nombre_clave': 'daniela',      'genero_inferido': 'Femenino'},
    {'nombre_clave': 'camila',       'genero_inferido': 'Femenino'},
    {'nombre_clave': 'martina',      'genero_inferido': 'Femenino'},
    {'nombre_clave': 'julieta',      'genero_inferido': 'Femenino'},
    {'nombre_clave': 'valentina',    'genero_inferido': 'Femenino'},
    {'nombre_clave': 'micaela',      'genero_inferido': 'Femenino'},
    {'nombre_clave': 'belen',        'genero_inferido': 'Femenino'},
    {'nombre_clave': 'celeste',      'genero_inferido': 'Femenino'},
    {'nombre_clave': 'noelia',       'genero_inferido': 'Femenino'},
    {'nombre_clave': 'aldana',       'genero_inferido': 'Femenino'},
    {'nombre_clave': 'magali',       'genero_inferido': 'Femenino'},
    {'nombre_clave': 'nadia',        'genero_inferido': 'Femenino'},
    {'nombre_clave': 'brenda',       'genero_inferido': 'Femenino'},
    {'nombre_clave': 'melina',       'genero_inferido': 'Femenino'},
    {'nombre_clave': 'gisela',       'genero_inferido': 'Femenino'},
    {'nombre_clave': 'ivana',        'genero_inferido': 'Femenino'},
    {'nombre_clave': 'norma',        'genero_inferido': 'Femenino'},
    {'nombre_clave': 'rosa',         'genero_inferido': 'Femenino'},
    {'nombre_clave': 'elena',        'genero_inferido': 'Femenino'},
    {'nombre_clave': 'teresa',       'genero_inferido': 'Femenino'},
    {'nombre_clave': 'alicia',       'genero_inferido': 'Femenino'},
    {'nombre_clave': 'viviana',      'genero_inferido': 'Femenino'},
    {'nombre_clave': 'karina',       'genero_inferido': 'Femenino'},
    {'nombre_clave': 'soledad',      'genero_inferido': 'Femenino'},
    {'nombre_clave': 'estela',       'genero_inferido': 'Femenino'},
    {'nombre_clave': 'liliana',      'genero_inferido': 'Femenino'},
    {'nombre_clave': 'adriana',      'genero_inferido': 'Femenino'},
    {'nombre_clave': 'mariela',      'genero_inferido': 'Femenino'},
    {'nombre_clave': 'silvina',      'genero_inferido': 'Femenino'},
    {'nombre_clave': 'analia',       'genero_inferido': 'Femenino'},
    {'nombre_clave': 'barbara',      'genero_inferido': 'Femenino'},
    {'nombre_clave': 'virginia',     'genero_inferido': 'Femenino'},
    {'nombre_clave': 'jessica',      'genero_inferido': 'Femenino'},
    {'nombre_clave': 'cynthia',      'genero_inferido': 'Femenino'},
    {'nombre_clave': 'elizabeth',    'genero_inferido': 'Femenino'},
    {'nombre_clave': 'erica',        'genero_inferido': 'Femenino'},
    {'nombre_clave': 'mia',          'genero_inferido': 'Femenino'},
    {'nombre_clave': 'emma',         'genero_inferido': 'Femenino'},
    {'nombre_clave': 'agustina',     'genero_inferido': 'Femenino'},
    {'nombre_clave': 'milagros',     'genero_inferido': 'Femenino'},
    {'nombre_clave': 'ailén',        'genero_inferido': 'Femenino'},
    {'nombre_clave': 'ailen',        'genero_inferido': 'Femenino'},
    {'nombre_clave': 'morena',       'genero_inferido': 'Femenino'},
    {'nombre_clave': 'paz',          'genero_inferido': 'Femenino'},
    ]

    pd.DataFrame(nombres_data).to_sql('lkp_diccionario_nombres', engine_clean, if_exists='replace', index=False)
    print("    -> Lookups inicializados.")

def ejecutar_staging_clean():
    try:
        master_uri, staging_uri, _ = obtener_uris()
        asegurar_idempotencia(master_uri)
        
        engine_stg = create_engine(staging_uri)
        engine_clean = create_engine(master_uri.replace('master', CLEAN_DB_NAME))
        
        inicializar_lookups(engine_clean)
        fecha_ejecucion = datetime.now()

        # --- 1. PRODUCTOS ---
        print("-> [1/5] Procesando Productos...")
        query_prod = """
            SELECT p.product_id, p.sku, p.product_name, p.brand, p.unit, p.unit_cost, p.list_price, p.active_flag, c.category_name 
            FROM stg_products p 
            JOIN stg_categories c ON p.category_id = c.category_id
        """
        df_prod = pd.read_sql(query_prod, engine_stg)
        df_prod['active_flag'] = df_prod['active_flag'].map({'Y': 1, 'N': 0}).fillna(0)
        df_prod['fecha_carga'] = fecha_ejecucion
        df_prod.to_sql('clean_products', engine_clean, if_exists='replace', index=False, 
                       dtype={'list_price': types.Numeric(12,2), 'fecha_carga': types.DateTime})

        # --- 2. SUCURSALES ---
        print("-> [2/5] Procesando Sucursales...")
        df_stores = pd.read_sql("SELECT store_id, surface_m2, city, province, opening_date FROM stg_stores", engine_stg)
        df_stores['opening_date'] = pd.to_datetime(df_stores['opening_date'])
        df_stores['fecha_carga'] = fecha_ejecucion
        df_stores.to_sql('clean_stores', engine_clean, if_exists='replace', index=False,
                        dtype={'opening_date': types.Date, 'surface_m2': types.Numeric(10,2), 'fecha_carga': types.DateTime})

        # --- 3. CLIENTES (PARTE A: GÉNERO Y DEDUPLICACIÓN) ---
        print("-> [3/5] Procesando Clientes (Limpieza y Deduplicación)...")
        df_cust = pd.read_sql("SELECT * FROM stg_customers", engine_stg)
        df_lkp_cods = pd.read_sql("SELECT * FROM lkp_genero_codigos", engine_clean)
        df_lkp_nombres = pd.read_sql("SELECT * FROM lkp_diccionario_nombres", engine_clean)

        # Normalización de género vía Lookups
        df_cust = df_cust.merge(df_lkp_cods, left_on='gender', right_on='codigo_original', how='left')
        df_cust['nombre_busqueda'] = df_cust['customer_name'].str.lower()
        for _, row in df_lkp_nombres.iterrows():
            mask = df_cust['nombre_busqueda'].str.contains(row['nombre_clave'])
            df_cust.loc[mask, 'genero_estandar'] = row['genero_inferido']
        
        df_cust['gender'] = df_cust['genero_estandar'].fillna('No Informado')
        df_cust = df_cust.drop(columns=['codigo_original', 'genero_estandar', 'nombre_busqueda'])

        # Manejo de Duplicados (Deduplicación)
        df_cust['birth_date'] = pd.to_datetime(df_cust['birth_date'])
        df_cust['registration_date'] = pd.to_datetime(df_cust['registration_date'])
        df_cust = df_cust.sort_values(by=['customer_name', 'city', 'province', 'birth_date'])
        
        # Identificar ID sobreviviente (el más antiguo)
        df_cust['id_sobreviviente'] = df_cust.groupby(['customer_name', 'city', 'province'])['customer_id'].transform('first')
        df_lookup_map_clientes = df_cust[['customer_id', 'id_sobreviviente']].copy()
        
        # Crear tabla maestra de clientes deduplicada
        df_cust_clean = df_cust.drop_duplicates(subset=['customer_name', 'city', 'province'], keep='first').copy()
        df_cust_clean = df_cust_clean.drop(columns=['id_sobreviviente'])

        # --- 4. VENTAS (REASIGNACIÓN DE CLIENTES) ---
        print("-> [4/5] Procesando Ventas (Corrección de Clientes y Fechas)...")
        df_orders = pd.read_sql("SELECT order_id, order_date, customer_id, store_id, net_amount FROM stg_orders", engine_stg)
        df_orders['order_date'] = pd.to_datetime(df_orders['order_date'])
        
        # Mapear IDs de órdenes al cliente sobreviviente usando la tabla Lookup
        df_orders = df_orders.merge(df_lookup_map_clientes, on='customer_id', how='left')
        df_orders['customer_id'] = df_orders['id_sobreviviente']
        df_orders = df_orders.drop(columns=['id_sobreviviente'])

        # --- INTEGRIDAD TEMPORAL ---
        # 1. Obtenemos la fecha de la compra más antigua para cada cliente consolidado
        df_primera_compra = df_orders.groupby('customer_id')['order_date'].min().reset_index()
        df_primera_compra.rename(columns={'order_date': 'fecha_min_compra'}, inplace=True)

        # 2. Cruzamos con nuestra tabla maestra de clientes
        df_cust_clean = df_cust_clean.merge(df_primera_compra, on='customer_id', how='left')

        # 3. Regla: Si (fecha_registro > fecha_min_compra), actualizar registro a la fecha de compra
        mask_fecha_invalida = df_cust_clean['registration_date'] > df_cust_clean['fecha_min_compra']
        df_cust_clean.loc[mask_fecha_invalida, 'registration_date'] = df_cust_clean['fecha_min_compra']
        
        # Limpiamos columna temporal
        df_cust_clean = df_cust_clean.drop(columns=['fecha_min_compra'])

        # --- 5. DETALLES Y REGLA DE UNIDADES ---
        print("-> [5/5] Procesando Detalles (Regla de Unidades)...")
        df_det = pd.read_sql("SELECT od.*, p.unit FROM stg_order_details od JOIN stg_products p ON od.product_id = p.product_id", engine_stg)
        mask_no_peso = ~df_det['unit'].str.lower().str.contains('kg', na=False)
        df_det.loc[mask_no_peso, 'quantity'] = np.ceil(pd.to_numeric(df_det.loc[mask_no_peso, 'quantity'])).clip(lower=1)
        df_det = df_det.drop(columns=['unit'])

        # --- CARGA FINAL A STAGING_CLEAN CON FECHA_CARGA ---
        print("\n[*] Insertando datos finales en 'CentroMas_Staging_Clean'...")
        
        df_cust_clean['fecha_carga'] = fecha_ejecucion
        df_cust_clean.to_sql('clean_customers', engine_clean, if_exists='replace', index=False, 
                             dtype={'birth_date': types.Date, 'registration_date': types.Date, 'fecha_carga': types.DateTime})
                             
        df_lookup_map_clientes.to_sql('lookup_map_clientes', engine_clean, if_exists='replace', index=False)

        df_orders['fecha_carga'] = fecha_ejecucion
        df_orders.to_sql('clean_orders', engine_clean, if_exists='replace', index=False, 
                         dtype={'order_date': types.Date, 'net_amount': types.Numeric(12,2), 'fecha_carga': types.DateTime})
        
        df_det['fecha_carga'] = fecha_ejecucion
        df_det.to_sql('clean_order_details', engine_clean, if_exists='replace', index=False, 
                      dtype={'quantity': types.Numeric(10,2), 'unit_price': types.Numeric(12,2), 
                             'discount_amount': types.Numeric(12,2), 'net_amount': types.Numeric(12,2), 'fecha_carga': types.DateTime})

        print(f"\n[ÉXITO] Limpieza de Datos Finalizada.")
        print(f"-> Los clientes duplicados han sido unificados.")
        print(f"-> Las fechas de registro incoherentes han sido corregidas.")
        print(f"-> Todas las tablas cuentan con marca temporal: {fecha_ejecucion.strftime('%Y-%m-%d %H:%M:%S')}")

    except Exception as e:
        print(f"\n[ERROR FATAL] {e}")

if __name__ == "__main__":
    ejecutar_staging_clean()