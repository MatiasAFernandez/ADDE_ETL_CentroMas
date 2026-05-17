"""Orquestador principal del proceso de carga incremental."""
from datetime import datetime

from sqlalchemy import create_engine

from db_conexion import obtener_uris
from .config import DW_DB_NAME, CLEAN_DB_NAME, SCRIPT_NAME
from .audit_logger import inicializar_auditoria, escribir_log
from .staging_loader import cargar_staging_clean
from .dimension_scd import procesar_clientes, procesar_productos, procesar_sucursales
from .diccionarios import sincronizar_diccionarios
from .dim_tiempo import mantener_dim_tiempo
from .fact_builder import construir_fact_delta
from .cdc_upsert import ejecutar_upsert


def ejecutar_carga_incremental():
    """
    Orquesta todo el proceso de carga incremental:
      1. Inicializa auditoría y conexiones a bases de datos.
      2. Carga datos desde Staging Clean.
      3. Crea tabla de rechazados y detecta huérfanos.
      4. Procesa SCD Tipo 2 para dimensiones (clientes, productos, sucursales).
      5. Sincroniza diccionarios de traducción.
      6. Construye el delta de hechos (Fact_Venta).
      7. Mantiene Dim_Tiempo con nuevas fechas si es necesario.
      8. Ejecuta UPSERT por hash (CDC) sobre Fact_Venta.
      9. Registra auditoría en ETL_Logs.
    """
    auditoria = inicializar_auditoria()
    engine_dw = None

    try:
        master_uri, _, _ = obtener_uris()
        engine_dw = create_engine(master_uri.replace('master', DW_DB_NAME))
        engine_clean = create_engine(master_uri.replace('master', CLEAN_DB_NAME))

        fecha_ejecucion = datetime.now()
        print(f"[*] Iniciando Carga Incremental (CDC por hash): {fecha_ejecucion.strftime('%Y-%m-%d %H:%M:%S')}")

        # ==========================================
        # PASO 1: CARGAR DATOS DESDE STAGING CLEAN
        # ==========================================
        datos = cargar_staging_clean(engine_clean)

        # ==========================================
        # PASO 2: PROCESAR DIMENSIONES (SCD TIPO 2)
        # ==========================================
        procesar_clientes(engine_dw, datos['customers'], fecha_ejecucion)
        procesar_productos(engine_dw, datos['products'], fecha_ejecucion)
        procesar_sucursales(engine_dw, datos['stores'], fecha_ejecucion)

        # ==========================================
        # PASO 4: SINCRONIZAR DICCIONARIOS
        # ==========================================
        dict_cli, dict_prod = sincronizar_diccionarios(engine_clean, datos['customers'], datos['products'])

        # ==========================================
        # PASO 5: CONSTRUIR DELTA DE HECHOS Y EJECUTAR CDC
        # ==========================================
        if datos['hay_ventas']:
            df_fact = construir_fact_delta(engine_dw, datos['orders'], datos['details'],
                                           dict_cli, dict_prod, fecha_ejecucion)

            # Mantener Dim_Tiempo
            sk_tiempos = df_fact['sk_tiempo'].unique().tolist()
            mantener_dim_tiempo(engine_dw, sk_tiempos)

            # Ejecutar UPSERT por hash
            resultado = ejecutar_upsert(engine_dw, df_fact, fecha_ejecucion, SCRIPT_NAME)

            total_filas = resultado['insert_count'] + resultado['update_count']
            auditoria['filas_totales'] = total_filas
            auditoria['estado'] = 'EXITO'
            auditoria['mensaje'] = (
                f"Carga incremental finalizada. "
                f"{resultado['insert_count']} insertadas, "
                f"{resultado['update_count']} actualizadas"
            )

            print(f"\n[CDC] Resumen de la ejecución:")
            print(f"    -> Filas INSERTADAS: {resultado['insert_count']}")
            print(f"    -> Filas ACTUALIZADAS (hash cambiado): {resultado['update_count']}")
            if resultado['delete_count'] > 0:
                print(f"    -> Tickets ausentes en staging (registrados en ChangeLog): {resultado['delete_count']}")
            print(f"    -> Total de líneas procesadas: {total_filas}")

        else:
            auditoria['estado'] = 'EXITO'
            auditoria['mensaje'] = "Carga finalizada. No se detectaron ventas nuevas en el staging."

        print(f"\n[{auditoria['estado']}] {auditoria['mensaje']}")

    except Exception as e:
        auditoria['estado'] = 'ERROR'
        auditoria['mensaje'] = f"Fallo en la ejecución: {str(e)[:4000]}"
        print(f"\n[ERROR EN INCREMENTAL] {e}")
        raise e

    finally:
        escribir_log(engine_dw, auditoria)


if __name__ == "__main__":
    ejecutar_carga_incremental()