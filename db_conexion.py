import json
import os
import urllib.parse

CONFIG_FILE = "db_config.json"


def generar_configuracion():
    """Pregunta los datos por consola y los guarda en un archivo JSON local."""
    print("==========================================")
    print(" ⚙️ CONFIGURACIÓN GLOBAL DE BASE DE DATOS (pymssql)")
    print("==========================================")

    # Forzar 127.0.0.1 en lugar de localhost para evitar problemas de IPv6 en Linux
    server = (
        input("Servidor SQL (Ej: 127.0.0.1) [Enter para '127.0.0.1']: ").strip()
        or "127.0.0.1"
    )

    print("\nTipo de autenticación:")
    print("1. Autenticación de Windows (No recomendada en Linux/Docker)")
    print("2. Autenticación de SQL Server (Usuario y Contraseña)")

    # Dejar la opción 2 como predeterminada
    auth_type = input("Elige (1 o 2) [Enter para 2]: ").strip() or "2"

    user, password = "", ""
    if auth_type == "2":
        user = input("Usuario [Enter para 'sa']: ").strip() or "sa"
        password = input("Contraseña: ").strip()

    config = {
        "server": server,
        "auth_type": auth_type,
        "user": user,
        "password": password,
        "csv_path": "",
    }

    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f)

    print(
        "[OK] Configuración guardada en 'db_config.json'. No se te volverá a preguntar.\n"
    )
    return config


def leer_configuracion():
    """Lee y devuelve el diccionario de configuración. Si no existe, lo genera."""
    if not os.path.exists(CONFIG_FILE):
        return generar_configuracion()
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)


def actualizar_configuracion(config):
    """Sobrescribe el archivo de configuración con nuevos datos."""
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f)


def obtener_uris():
    """Lee la configuración y devuelve las URIs de conexión usando pymssql."""
    config = leer_configuracion()

    server = config["server"]

    # Seguridad adicional: si el JSON todavía contiene 'localhost', se fuerza a 127.0.0.1
    if server.lower() == "localhost":
        server = "127.0.0.1"

    if config.get("auth_type", "2") == "1":
        base_uri = f"mssql+pymssql://@{server}/{{db}}"
    else:
        user = config.get("user", "sa")
        pwd = config.get("password", "")
        encoded_pwd = urllib.parse.quote_plus(pwd)

        # Añadir charset=utf8 por seguridad para pymssql
        base_uri = (
            f"mssql+pymssql://{user}:{encoded_pwd}@{server}:1433/{{db}}?charset=utf8"
        )

    master_uri = base_uri.format(db="master")
    staging_uri = base_uri.format(db="CentroMas_Staging")
    dw_uri = base_uri.format(db="CentroMas_DW")

    return master_uri, staging_uri, dw_uri
