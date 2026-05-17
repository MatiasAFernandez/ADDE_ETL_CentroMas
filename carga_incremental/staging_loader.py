"""Carga de datos desde las tablas de Staging Clean."""
import pandas as pd


def cargar_staging_clean(engine_clean):
    """
    Carga todos los dataframes desde las tablas de Staging Clean.
    Retorna un diccionario con:
      - orders: DataFrame de clean_orders
      - details: DataFrame de clean_order_details
      - customers: DataFrame de clean_customers
      - products: DataFrame de clean_products
      - stores: DataFrame de clean_stores
      - hay_ventas: bool indicando si hay datos de ventas
    """
    print("[*] Cargando datos desde Staging Clean...")

    df_orders = pd.read_sql("SELECT * FROM clean_orders", engine_clean)
    df_details = pd.read_sql("SELECT * FROM clean_order_details", engine_clean)
    df_customers = pd.read_sql("SELECT * FROM clean_customers", engine_clean)
    df_products = pd.read_sql("SELECT * FROM clean_products", engine_clean)
    df_stores = pd.read_sql("SELECT * FROM clean_stores", engine_clean)

    hay_ventas = (not df_orders.empty) and (not df_details.empty)

    if not hay_ventas:
        print("[*] No se detectaron datos nuevos en Staging Clean. Omitiendo carga de hechos.")
    else:
        print(f"[*] Datos cargados desde Staging Clean: {len(df_orders)} órdenes, {len(df_details)} detalles.")

    return {
        'orders': df_orders,
        'details': df_details,
        'customers': df_customers,
        'products': df_products,
        'stores': df_stores,
        'hay_ventas': hay_ventas
    }