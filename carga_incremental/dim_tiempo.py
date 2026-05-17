"""Mantenimiento dinámico de la dimensión temporal Dim_Tiempo."""
import pandas as pd
from datetime import datetime


def _obtener_temporada(mes):
    """Determina la temporada según el mes."""
    if mes in [12, 1, 2]:
        return 'Verano'
    if mes in [3, 4, 5]:
        return 'Otoño'
    if mes in [6, 7, 8]:
        return 'Invierno'
    return 'Primavera'


def mantener_dim_tiempo(engine_dw, sk_tiempos_requeridos):
    """
    Verifica qué fechas de sk_tiempo existen en Dim_Tiempo e inserta las faltantes.
    Recibe una lista de valores sk_tiempo (formato YYYYMMDD).
    """
    if not sk_tiempos_requeridos:
        return

    fechas_str = ",".join(map(str, sk_tiempos_requeridos))

    existentes = pd.read_sql(f"SELECT sk_tiempo FROM Dim_Tiempo WHERE sk_tiempo IN ({fechas_str})", engine_dw)
    fechas_existentes = existentes['sk_tiempo'].tolist()
    fechas_faltantes = [sk for sk in sk_tiempos_requeridos if sk not in fechas_existentes]

    if fechas_faltantes:
        print(f"    -> Detectadas {len(fechas_faltantes)} nuevas fechas. Agregando a Dim_Tiempo...")

        nuevas_fechas_dt = [datetime.strptime(str(sk), '%Y%m%d') for sk in fechas_faltantes]
        df_tiempo_nuevo = pd.DataFrame({'fecha_completa': nuevas_fechas_dt, 'sk_tiempo': fechas_faltantes})
        df_tiempo_nuevo['dia_nro'] = df_tiempo_nuevo['fecha_completa'].dt.day
        df_tiempo_nuevo['mes_nro'] = df_tiempo_nuevo['fecha_completa'].dt.month
        df_tiempo_nuevo['anio_nro'] = df_tiempo_nuevo['fecha_completa'].dt.year
        df_tiempo_nuevo['temporada'] = df_tiempo_nuevo['mes_nro'].apply(_obtener_temporada)
        df_tiempo_nuevo.to_sql('Dim_Tiempo', engine_dw, if_exists='append', index=False)