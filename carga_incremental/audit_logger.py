"""Inicialización de auditoría y escritura de logs ETL."""
from sqlalchemy import text


def inicializar_auditoria():
    """
    Inicializa las variables de auditoría para el proceso ETL.
    Retorna un diccionario con: script_name, estado, filas_totales, mensaje.
    """
    return {
        'script_name': '04_carga_incremental.py',
        'estado': 'EN EJECUCION',
        'filas_totales': 0,
        'mensaje': ''
    }


def escribir_log(engine_dw, auditoria):
    """
    Escribe el registro de auditoría en la tabla ETL_Logs.
    Se ejecuta en el bloque finally para garantizar que se registre incluso en caso de error.
    """
    if engine_dw is None:
        print("[!] No se pudo registrar el log porque no se estableció conexión con el DW.")
        return

    try:
        print("\n-> Escribiendo registro en la tabla de Logs...")
        query_log = text("""
            INSERT INTO ETL_Logs (script_nombre, estado, filas_procesadas, mensaje)
            VALUES (:script, :estado, :filas, :msg)
        """)
        with engine_dw.begin() as conn:
            conn.execute(query_log, {
                "script": auditoria['script_name'],
                "estado": auditoria['estado'],
                "filas": auditoria['filas_totales'],
                "msg": auditoria['mensaje']
            })
        print("[OK] Log guardado exitosamente en la base de datos.")
    except Exception as log_e:
        print(f"[!] Error crítico al escribir en la tabla ETL_Logs: {log_e}")