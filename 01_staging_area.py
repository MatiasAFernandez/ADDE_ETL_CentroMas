import pandas as pd
from sqlalchemy import create_engine, text
import os
import sys
from db_conexion import obtener_uris

CSV_FILES = [
    'categories.csv', 'customers.csv', 'employees.csv',
    'order_details.csv', 'orders.csv', 'payment_methods.csv',
    'products.csv', 'promotions.csv', 'stores.csv', 'suppliers.csv'
]

SOURCE_BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sources")
INICIAL_DIR = os.path.join(SOURCE_BASE, "inicial")
INCREMENTAL_DIR = os.path.join(SOURCE_BASE, "incremental")

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

    # Solicitar tipo de carga (solo si no se especificó como argumento CLI)
    if len(sys.argv) > 1 and sys.argv[1] in ('f', 'i'):
        tipo_carga = sys.argv[1]
    else:
        tipo_carga = input("\n¿Tipo de carga? (f = inicial | i = incremental):\n> ").strip().lower()

    if tipo_carga == 'f':
        folder_path = INICIAL_DIR
        tipo_label = "INICIAL"
    elif tipo_carga == 'i':
        folder_path = INCREMENTAL_DIR
        tipo_label = "INCREMENTAL"
    else:
        print(f"\n[ERROR] Opción inválida. Debe ingresar 'f' para inicial o 'i' para incremental.")
        return

    if not os.path.exists(folder_path):
        print(f"\n[ERROR] No se encontró la carpeta '{folder_path}'. Verificá que exista la estructura 'sources/{tipo_label.lower()}/'.")
        return

    print("\n==========================================")
    print(f" 🚀 INICIANDO EXTRACCIÓN {tipo_label} A SQL SERVER")
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
            
        except Exception as e:
            print(f"  [ERROR] Detalle: {e}")

    print(f"\n[OK] {tables_created} tablas creadas. {total_records} registros delta insertados.")
    print(f"[*] Los archivos permanecen en su ubicación original.")

if __name__ == "__main__":
    load_staging_area()