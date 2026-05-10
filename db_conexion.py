import os
import json
import pyodbc

CONFIG_FILE = 'db_config.json'

def generar_configuracion():
    """Pregunta los datos por consola y los guarda en un archivo JSON local."""
    print("==========================================")
    print(" ⚙️ CONFIGURACIÓN GLOBAL DE BASE DE DATOS")
    print("==========================================")
    
    server = input("Servidor SQL (Ej: localhost) [Enter para 'localhost']: ").strip() or 'localhost'
    
    print("\nTipo de autenticación:")
    print("1. Autenticación de Windows (Trusted Connection)")
    print("2. Autenticación de SQL Server (Usuario y Contraseña)")
    auth_type = input("Elige (1 o 2) [Enter para 1]: ").strip() or '1'
    
    user, password = '', ''
    if auth_type == '2':
        user = input("Usuario [Enter para 'sa']: ").strip() or 'sa'
        password = input("Contraseña: ").strip()
        
    drivers = [d for d in pyodbc.drivers() if 'SQL Server' in d]
    if not drivers:
        raise Exception("No se encontraron drivers ODBC instalados.")
        
    print("\nDrivers ODBC detectados en tu equipo:")
    for i, d in enumerate(drivers):
        print(f"{i+1}. {d}")
        
    opcion = input(f"\nElige el número de tu driver (1-{len(drivers)}): ").strip()
    try:
        driver_elegido = drivers[int(opcion)-1]
    except:
        driver_elegido = drivers[-1]
        
    driver_str = driver_elegido.replace(' ', '+')
    print(f"\n[!] Driver seleccionado: {driver_elegido}")
    
    config = {
        "server": server,
        "auth_type": auth_type,
        "user": user,
        "password": password,
        "driver": driver_str,
        "csv_path": ""  # Agregamos esta clave vacía por defecto
    }
    
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f)
        
    print("[OK] Configuración guardada en 'db_config.json'. No se te volverá a preguntar.\n")
    return config

def leer_configuracion():
    """Lee y devuelve el diccionario de configuración. Si no existe, lo genera."""
    if not os.path.exists(CONFIG_FILE):
        return generar_configuracion()
    with open(CONFIG_FILE, 'r') as f:
        return json.load(f)

def actualizar_configuracion(config):
    """Sobrescribe el archivo de configuración con nuevos datos."""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f)

def obtener_uris():
    """Lee la configuración y devuelve las URIs de conexión."""
    config = leer_configuracion()
            
    server = config['server']
    driver = config['driver']
    
    if config['auth_type'] == '1':
        base_uri = f"mssql+pyodbc://@{server}/{{db}}?driver={driver}&Trusted_Connection=yes&TrustServerCertificate=yes"
    else:
        user = config['user']
        pwd = config['password']
        base_uri = f"mssql+pyodbc://{user}:{pwd}@{server}/{{db}}?driver={driver}&TrustServerCertificate=yes"
        
    master_uri = base_uri.format(db='master')
    staging_uri = base_uri.format(db='CentroMas_Staging')
    dw_uri = base_uri.format(db='CentroMas_DW')
    
    return master_uri, staging_uri, dw_uri