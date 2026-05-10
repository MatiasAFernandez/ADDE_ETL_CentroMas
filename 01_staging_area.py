import pandas as pd
from sqlalchemy import create_engine, text
import os
from db_conexion import obtener_uris, leer_configuracion, actualizar_configuracion

CSV_FILES = [
    'categories.csv', 'customers.csv', 'employees.csv',
    'order_details.csv', 'orders.csv', 'payment_methods.csv',
    'products.csv', 'promotions.csv', 'stores.csv', 'suppliers.csv'
]

def recreate_database(master_uri, db_name):
    print(f"\n[*] Conectando a SQL Server para preparar el entorno...")
    engine_master = create_engine(master_uri, isolation_level="AUTOCOMMIT")
    
    with engine_master.connect() as conn:
        check_db = conn.execute(text(f"SELECT name FROM sys.databases WHERE name = '{db_name}'")).fetchone()
        if check_db:
            print(f"[*] La base de datos '{db_name}' ya existe. Eliminando para una carga limpia...")
            conn.execute(text(f"ALTER DATABASE {db_name} SET SINGLE_USER WITH ROLLBACK IMMEDIATE"))
            conn.execute(text(f"DROP DATABASE {db_name}"))
        
        print(f"[*] Creando la base de datos '{db_name}'...")
        conn.execute(text(f"CREATE DATABASE {db_name}"))
        print("[*] Base de datos de Staging lista.\n")

def load_staging_area():
    try:
        master_uri, staging_uri, _ = obtener_uris()
        config = leer_configuracion() # Obtenemos la configuración completa
    except Exception as e:
        print(f"\n[ERROR FATAL] {e}")
        return

    # Lógica para la ruta de los CSV
    ruta_guardada = config.get("csv_path", "")
    
    if ruta_guardada:
        print(f"\nRuta guardada anteriormente: {ruta_guardada}")
        folder_path_input = input("Ingresa una nueva ruta o presiona [Enter] para usar la guardada:\n> ").strip().strip('"').strip("'")
    else:
        folder_path_input = input("\nIngresa la ruta completa de la carpeta de los archivos CSV:\n> ").strip().strip('"').strip("'")
    
    # Determinar qué ruta usar y actualizar si es necesario
    if folder_path_input:
        folder_path = folder_path_input
        config["csv_path"] = folder_path
        actualizar_configuracion(config) # Se actualiza el JSON
        print("[OK] Ruta actualizada y guardada en 'db_config.json'.")
    else:
        folder_path = ruta_guardada

    if not folder_path or not os.path.exists(folder_path):
        print(f"\n[ERROR] No se pudo encontrar la ruta: '{folder_path}'")
        return

    print("\n==========================================")
    print(" 🚀 INICIANDO EXTRACCIÓN A SQL SERVER")
    print("==========================================\n")

    recreate_database(master_uri, 'CentroMas_Staging')

    engine = create_engine(staging_uri)
    total_records = 0
    tables_created = 0

    for file_name in CSV_FILES:
        file_path = os.path.join(folder_path, file_name)
        if not os.path.exists(file_path):
            continue
            
        table_name = f"stg_{file_name.split('.')[0]}"
        try:
            print(f"-> Cargando '{file_name}' en [{table_name}]...")
            df = pd.read_csv(file_path)
            df.to_sql(table_name, con=engine, if_exists='replace', index=False, chunksize=5000)
            total_records += len(df)
            tables_created += 1
        except Exception as e:
            print(f"  [ERROR] Detalle: {e}")

    print(f"\n[OK] {tables_created} tablas creadas. {total_records} registros insertados.")

if __name__ == "__main__":
    load_staging_area()