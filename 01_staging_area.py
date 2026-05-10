import pandas as pd
from sqlalchemy import create_engine, text
import os
import shutil
from db_conexion import obtener_uris

CSV_FILES = [
    'categories.csv', 'customers.csv', 'employees.csv',
    'order_details.csv', 'orders.csv', 'payment_methods.csv',
    'products.csv', 'promotions.csv', 'stores.csv', 'suppliers.csv'
]

def recreate_database(master_uri, db_name):
    print(f"\n[*] Preparando el entorno efímero L1...")
    engine_master = create_engine(master_uri, isolation_level="AUTOCOMMIT")
    
    with engine_master.connect() as conn:
        check_db = conn.execute(text(f"SELECT name FROM sys.databases WHERE name = '{db_name}'")).fetchone()
        if check_db:
            conn.execute(text(f"ALTER DATABASE {db_name} SET SINGLE_USER WITH ROLLBACK IMMEDIATE"))
            conn.execute(text(f"DROP DATABASE {db_name}"))
        
        conn.execute(text(f"CREATE DATABASE {db_name}"))
        print(f"[*] Base de datos '{db_name}' lista y vacía para recibir el Delta del día.\n")

def load_staging_area():
    try:
        master_uri, staging_uri, _ = obtener_uris()
    except Exception as e:
        print(f"\n[ERROR FATAL] {e}")
        return

    folder_path = input("\nIngresa la ruta de la carpeta con los archivos CSV del día:\n> ").strip().strip('"').strip("'")
    
    if not os.path.exists(folder_path):
        print(f"\n[ERROR] No se pudo encontrar la ruta: '{folder_path}'")
        return

    # Crear carpeta para archivar los archivos ya procesados
    carpeta_procesados = os.path.join(folder_path, "procesados")
    if not os.path.exists(carpeta_procesados):
        os.makedirs(carpeta_procesados)

    print("\n==========================================")
    print(" 🚀 INICIANDO EXTRACCIÓN DELTA A SQL SERVER")
    print("==========================================\n")

    recreate_database(master_uri, 'CentroMas_Staging')

    engine = create_engine(staging_uri)
    total_records = 0
    tables_created = 0

    for file_name in CSV_FILES:
        file_path = os.path.join(folder_path, file_name)
        
        # Si el archivo no vino hoy (ej. no hay clientes nuevos), lo salta
        if not os.path.exists(file_path):
            print(f"-> [OMITIDO] '{file_name}' no se encontró en el lote de hoy.")
            continue
            
        table_name = f"stg_{file_name.split('.')[0]}"
        try:
            print(f"-> Cargando '{file_name}' en [{table_name}]...")
            df = pd.read_csv(file_path)
            df.to_sql(table_name, con=engine, if_exists='replace', index=False, chunksize=5000)
            
            total_records += len(df)
            tables_created += 1
            
            # Mover el archivo a la carpeta de procesados
            ruta_destino = os.path.join(carpeta_procesados, file_name)
            # Si ya existía un archivo con el mismo nombre en 'procesados', lo sobrescribe
            if os.path.exists(ruta_destino):
                os.remove(ruta_destino)
            shutil.move(file_path, ruta_destino)
            
        except Exception as e:
            print(f"  [ERROR] Detalle: {e}")

    print(f"\n[OK] {tables_created} tablas creadas. {total_records} registros delta insertados.")
    print(f"[*] Los archivos originales fueron movidos a la carpeta 'procesados'.")

if __name__ == "__main__":
    load_staging_area()