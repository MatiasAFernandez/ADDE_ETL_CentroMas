"""Construcción del delta de hechos para Fact_Venta."""
import pandas as pd
from sqlalchemy import types
from .hash_utils import calcular_hash


def _aplicar_join_temporal(df_ventas, dim_df, bk_col, sk_col):
    """
    Realiza un as-was join entre las ventas delta y una dimensión,
    filtrando por la fecha de la venta dentro del rango de vigencia del registro de dimensión.
    """
    df_ventas['temp_row_id'] = range(len(df_ventas))
    merged = df_ventas.merge(dim_df, on=bk_col, how='left')
    mask_fecha = (merged['order_date'] >= merged['fecha_inicio']) & (merged['order_date'] <= merged['fecha_fin'])
    validos = merged[mask_fecha].copy()
    id_validos = validos['temp_row_id'].unique()
    huerfanas = df_ventas[~df_ventas['temp_row_id'].isin(id_validos)].copy()
    huerfanas[sk_col] = -1
    resultado = pd.concat([validos.drop(columns=['fecha_inicio', 'fecha_fin']), huerfanas], ignore_index=True)
    return resultado.drop(columns=['temp_row_id'])


def construir_fact_delta(engine_dw, df_orders, df_details, dict_cli, dict_prod, fecha_ejecucion):
    """
    Construye el DataFrame delta de Fact_Venta a partir de los datos de staging.
    Incluye:
      - Merge de orders y order_details
      - Cálculo de sk_tiempo
      - Cruce con diccionarios y dimensiones (as-was join)
      - Renombrado de columnas y cálculo de métricas
      - Generación de hash por fila

    Retorna el DataFrame delta listo para UPSERT.
    """
    print("-> [FACT] Construyendo tabla de hechos delta...")

    df_fact = df_details.merge(df_orders, on='order_id', suffixes=('_det', '_ord'))
    df_fact['order_date'] = pd.to_datetime(df_fact['order_date'])
    df_fact['sk_tiempo'] = df_fact['order_date'].dt.strftime('%Y%m%d').astype(int)

    # Cruce con diccionarios
    df_fact = df_fact.merge(dict_cli, on='customer_id', how='left')
    df_fact = df_fact.merge(dict_prod, on='product_id', how='left')
    df_fact['id_sucursal_bk'] = df_fact['store_id']

    # Cruce temporal con dimensiones (as-was join)
    dim_cli = pd.read_sql(
        "SELECT sk_cliente, id_cliente_bk as customer_code, fecha_inicio, ISNULL(fecha_fin, '9999-12-31') as fecha_fin FROM Dim_Cliente",
        engine_dw
    )
    dim_prod = pd.read_sql(
        "SELECT sk_producto, id_producto_bk as sku, fecha_inicio, ISNULL(fecha_fin, '9999-12-31') as fecha_fin FROM Dim_Producto",
        engine_dw
    )
    dim_suc = pd.read_sql(
        "SELECT sk_sucursal, CAST(id_sucursal_bk AS VARCHAR) as id_sucursal_bk, fecha_inicio, ISNULL(fecha_fin, '9999-12-31') as fecha_fin FROM Dim_Sucursal",
        engine_dw
    )

    df_fact['id_sucursal_bk'] = df_fact['id_sucursal_bk'].astype(str)
    for d in [dim_cli, dim_prod, dim_suc]:
        d['fecha_inicio'] = pd.to_datetime(d['fecha_inicio'])
        d['fecha_fin'] = pd.to_datetime(d['fecha_fin'])

    df_fact = _aplicar_join_temporal(df_fact, dim_cli, 'customer_code', 'sk_cliente')
    df_fact = _aplicar_join_temporal(df_fact, dim_prod, 'sku', 'sk_producto')
    df_fact = _aplicar_join_temporal(df_fact, dim_suc, 'id_sucursal_bk', 'sk_sucursal')

    # Renombrar y calcular métricas
    df_fact = df_fact.rename(columns={
        'order_id': 'nro_ticket',
        'unit_price': 'precio_unitario',
        'net_amount_det': 'monto_neto',
        'quantity': 'cantidad_vendida',
        'discount_amount': 'descuento_aplicado'
    })
    df_fact['monto_bruto'] = df_fact['cantidad_vendida'] * df_fact['precio_unitario']

    # Generar hash por fila
    df_fact['row_hash'] = df_fact.apply(calcular_hash, axis=1)
    df_fact['last_updated'] = fecha_ejecucion

    return df_fact