import os
import json
# import pyodbc # Eliminado para no depender de ODBC

CONFIG_FILE = 'db_config.json'

def generar_configuracion():
    """Pregunta los datos por consola y los guarda en un archivo JSON local."""
    print("==========================================")
    print(" ⚙️ CONFIGURACIÓN GLOBAL DE BASE DE DATOS (pymssql)")
    print("==========================================")
    
    server = input("Servidor SQL (Ej: localhost) [Enter para 'localhost']: ").strip() or 'localhost'
    
    print("\nTipo de autenticación:")
    print("1. Autenticación de Windows (Trusted Connection - Puede requerir configuración en pymssql dependiendo del SO)")
    print("2. Autenticación de SQL Server (Usuario y Contraseña)")
    auth_type = input("Elige (1 o 2) [Enter para 1]: ").strip() or '1'
    
    user, password = '', ''
    if auth_type == '2':
        user = input("Usuario [Enter para 'sa']: ").strip() or 'sa'
        password = input("Contraseña: ").strip()
        
    config = {
        "server": server,
        "auth_type": auth_type,
        "user": user,
        "password": password,
        "csv_path": ""
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
    """Lee la configuración y devuelve las URIs de conexión usando pymssql."""
    config = leer_configuracion()
            
    server = config['server']
    
    if config.get('auth_type', '1') == '1':
        # Autenticación de Windows sin driver ODBC
        base_uri = f"mssql+pymssql://@{server}/{{db}}"
    else:
        user = config.get('user', '')
        pwd = config.get('password', '')
        # Autenticación SQL sin driver ODBC
        base_uri = f"mssql+pymssql://{user}:{pwd}@{server}/{{db}}"
        
    master_uri = base_uri.format(db='master')
    staging_uri = base_uri.format(db='CentroMas_Staging')
    dw_uri = base_uri.format(db='CentroMas_DW')
    
    return master_uri, staging_uri, dw_uri