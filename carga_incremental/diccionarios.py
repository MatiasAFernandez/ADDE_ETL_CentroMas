"""Sincronización de tablas diccionario para traducción de IDs a Business Keys."""
import pandas as pd


def sincronizar_diccionarios(engine_clean, stg_cust, stg_prod):
    """
    Actualiza las tablas dict_clientes y dict_productos en Staging Clean.
    Estas tablas permiten traducir IDs transaccionales a business keys (customer_code, sku).
    """
    print("-> [DICCIONARIOS] Sincronizando IDs transaccionales con Business Keys...")

    # Diccionario de clientes
    try:
        dict_cli = pd.read_sql("SELECT * FROM dict_clientes", engine_clean)
    except Exception:
        dict_cli = pd.DataFrame(columns=['customer_id', 'customer_code'])

    if not stg_cust.empty:
        dict_cli = pd.concat([dict_cli, stg_cust[['customer_id', 'customer_code']]]) \
                      .drop_duplicates(subset=['customer_id'], keep='last')
        dict_cli.to_sql('dict_clientes', engine_clean, if_exists='replace', index=False)

    # Diccionario de productos
    try:
        dict_prod = pd.read_sql("SELECT * FROM dict_productos", engine_clean)
    except Exception:
        dict_prod = pd.DataFrame(columns=['product_id', 'sku'])

    if not stg_prod.empty:
        dict_prod = pd.concat([dict_prod, stg_prod[['product_id', 'sku']]]) \
                      .drop_duplicates(subset=['product_id'], keep='last')
        dict_prod.to_sql('dict_productos', engine_clean, if_exists='replace', index=False)

    return dict_cli, dict_prod