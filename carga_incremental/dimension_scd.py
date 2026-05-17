"""Gestión de dimensiones con SCD Tipo 2: Clientes, Productos y Sucursales."""
import pandas as pd
from sqlalchemy import text


def procesar_clientes(engine_dw, stg_cust, fecha_ejecucion):
    """
    SCD Tipo 2 para Dim_Cliente.
    Actualiza registros cambiados (fecha_fin, es_actual=0) e inserta nuevos.
    """
    if stg_cust.empty:
        return

    print("    -> [SCD2] Verificando Clientes...")
    for _, row in stg_cust.iterrows():
        query_check = text("""
            SELECT sk_cliente, ciudad_cliente, provincia_cliente FROM Dim_Cliente
            WHERE id_cliente_bk = :bk AND es_actual = 1
        """)
        with engine_dw.connect() as conn:
            current_dw = conn.execute(query_check, {"bk": row['customer_code']}).fetchone()

            if current_dw:
                if (current_dw.ciudad_cliente != row['city'] or current_dw.provincia_cliente != row['province']):
                    conn.execute(
                        text("UPDATE Dim_Cliente SET fecha_fin = :fecha, es_actual = 0 WHERE sk_cliente = :sk"),
                        {"fecha": fecha_ejecucion.date(), "sk": current_dw.sk_cliente}
                    )

                    edad = int((fecha_ejecucion - pd.to_datetime(row['birth_date'])).days / 365.25) if pd.notnull(row['birth_date']) else None
                    conn.execute(text("""
                        INSERT INTO Dim_Cliente (id_cliente_bk, genero, edad, tipo_cliente, ciudad_cliente, provincia_cliente, fecha_inicio, es_actual)
                        VALUES (:bk, :gen, :edad, :tipo, :ciu, :prov, :fi, 1)
                    """), {
                        "bk": row['customer_code'], "gen": row['gender'], "edad": edad, "tipo": row['customer_type'],
                        "ciu": row['city'], "prov": row['province'], "fi": fecha_ejecucion.date()
                    })
            else:
                edad = int((fecha_ejecucion - pd.to_datetime(row['birth_date'])).days / 365.25) if pd.notnull(row['birth_date']) else None
                conn.execute(text("""
                    INSERT INTO Dim_Cliente (id_cliente_bk, genero, edad, tipo_cliente, ciudad_cliente, provincia_cliente, fecha_inicio, es_actual)
                    VALUES (:bk, :gen, :edad, :tipo, :ciu, :prov, :fi, 1)
                """), {
                    "bk": row['customer_code'], "gen": row['gender'], "edad": edad, "tipo": row['customer_type'],
                    "ciu": row['city'], "prov": row['province'], "fi": row['registration_date']
                })
            conn.commit()


def procesar_productos(engine_dw, stg_prod, fecha_ejecucion):
    """
    SCD Tipo 2 para Dim_Producto.
    Compara costo_unidad, precio_lista y categoria_nombre para detectar cambios.
    """
    if stg_prod.empty:
        return

    print("    -> [SCD2] Verificando Productos...")
    for _, row in stg_prod.iterrows():
        query_check_prod = text("""
            SELECT sk_producto, costo_unidad, precio_lista, categoria_nombre
            FROM Dim_Producto
            WHERE id_producto_bk = :bk AND es_actual = 1
        """)
        with engine_dw.connect() as conn:
            current_dw_prod = conn.execute(query_check_prod, {"bk": row['sku']}).fetchone()

            if current_dw_prod:
                costo_dw = float(current_dw_prod.costo_unidad or 0)
                costo_stg = float(row['unit_cost'] or 0)
                precio_dw = float(current_dw_prod.precio_lista or 0)
                precio_stg = float(row['list_price'] or 0)
                cat_dw = str(current_dw_prod.categoria_nombre or "").strip()
                cat_stg = str(row['category_name'] or "").strip()

                hubo_cambio = (
                    abs(costo_dw - costo_stg) > 0.01 or
                    abs(precio_dw - precio_stg) > 0.01 or
                    cat_dw != cat_stg
                )

                if hubo_cambio:
                    conn.execute(
                        text("UPDATE Dim_Producto SET fecha_fin = :fecha, es_actual = 0 WHERE sk_producto = :sk"),
                        {"fecha": fecha_ejecucion.date(), "sk": current_dw_prod.sk_producto}
                    )

                    conn.execute(text("""
                        INSERT INTO Dim_Producto (id_producto_bk, producto_nombre, marca_nombre, categoria_nombre, costo_unidad, precio_lista, fecha_inicio, es_actual)
                        VALUES (:bk, :nom, :marca, :cat, :costo, :precio, :fi, 1)
                    """), {
                        "bk": row['sku'], "nom": row['product_name'], "marca": row['brand'], "cat": cat_stg,
                        "costo": row['unit_cost'], "precio": row['list_price'], "fi": fecha_ejecucion.date()
                    })
                    conn.commit()
            else:
                conn.execute(text("""
                    INSERT INTO Dim_Producto (id_producto_bk, producto_nombre, marca_nombre, categoria_nombre, costo_unidad, precio_lista, fecha_inicio, es_actual)
                    VALUES (:bk, :nom, :marca, :cat, :costo, :precio, :fi, 1)
                """), {
                    "bk": row['sku'], "nom": row['product_name'], "marca": row['brand'],
                    "cat": str(row['category_name']).strip(),
                    "costo": row['unit_cost'], "precio": row['list_price'], "fi": fecha_ejecucion.date()
                })
                conn.commit()


def procesar_sucursales(engine_dw, stg_stores, fecha_ejecucion):
    """
    SCD Tipo 2 para Dim_Sucursal.
    Compara superficie_m2, ciudad_sucursal y provincia_sucursal.
    """
    if stg_stores.empty:
        return

    print("    -> [SCD2] Verificando Sucursales...")
    for _, row in stg_stores.iterrows():
        query_check_suc = text("""
            SELECT sk_sucursal, superficie_m2, ciudad_sucursal, provincia_sucursal
            FROM Dim_Sucursal
            WHERE id_sucursal_bk = :bk AND es_actual = 1
        """)
        with engine_dw.connect() as conn:
            current_dw_suc = conn.execute(query_check_suc, {"bk": int(row['store_id'])}).fetchone()

            if current_dw_suc:
                if (current_dw_suc.superficie_m2 != row['surface_m2'] or
                    current_dw_suc.ciudad_sucursal != row['city'] or
                    current_dw_suc.provincia_sucursal != row['province']):

                    conn.execute(
                        text("UPDATE Dim_Sucursal SET fecha_fin = :fecha, es_actual = 0 WHERE sk_sucursal = :sk"),
                        {"fecha": fecha_ejecucion.date(), "sk": current_dw_suc.sk_sucursal}
                    )

                    conn.execute(text("""
                        INSERT INTO Dim_Sucursal (id_sucursal_bk, superficie_m2, ciudad_sucursal, provincia_sucursal, fecha_inicio, es_actual)
                        VALUES (:bk, :sup, :ciu, :prov, :fi, 1)
                    """), {
                        "bk": int(row['store_id']), "sup": row['surface_m2'], "ciu": row['city'],
                        "prov": row['province'], "fi": fecha_ejecucion.date()
                    })
            else:
                conn.execute(text("""
                    INSERT INTO Dim_Sucursal (id_sucursal_bk, superficie_m2, ciudad_sucursal, provincia_sucursal, fecha_inicio, es_actual)
                    VALUES (:bk, :sup, :ciu, :prov, :fi, 1)
                """), {
                    "bk": int(row['store_id']), "sup": row['surface_m2'], "ciu": row['city'],
                    "prov": row['province'], "fi": row['opening_date']
                })
            conn.commit()