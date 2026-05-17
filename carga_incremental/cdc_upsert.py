"""Lógica de UPSERT por hash (CDC) para la tabla Fact_Venta."""
import pandas as pd
from sqlalchemy import text, types


def _registrar_changelog(conn, nro_ticket, tipo_cambio, fecha, hash_anterior, hash_nuevo, script_name, detalle):
    """Inserta un registro en Fact_Venta_ChangeLog."""
    conn.execute(text("""
        INSERT INTO Fact_Venta_ChangeLog (nro_ticket, tipo_cambio, fecha_cambio, hash_anterior, hash_nuevo, ejecucion_etl, detalle)
        VALUES (:ticket, :tipo, :fecha, :hash_old, :hash_new, :ejecucion, :detalle)
    """), {
        "ticket": int(nro_ticket),
        "tipo": tipo_cambio,
        "fecha": fecha,
        "hash_old": hash_anterior,
        "hash_new": hash_nuevo,
        "ejecucion": script_name,
        "detalle": detalle
    })


def ejecutar_upsert(engine_dw, df_fact, fecha_ejecucion, script_name):
    """
    Ejecuta la lógica de UPSERT (INSERT / UPDATE) basada en hash de integridad.
    
    Pasos:
      1. Identifica tickets nuevos vs existentes en el DW.
      2. Para tickets nuevos: INSERT directo.
      3. Para tickets existentes: compara hash línea a línea.
         - Coinciden: se omiten (sin cambios).
         - No coinciden: UPDATE.
         - No existen en DW: INSERT como nueva línea.
      4. Registra todos los cambios en Fact_Venta_ChangeLog.
      5. Detecta tickets presentes en DW pero ausentes en staging (log informativo).

    Retorna un dict con: insert_count, update_count, delete_count.
    """
    print("-> [CDC] Ejecutando lógica de UPSERT por hash de integridad...")

    # --- Validación: si no hay datos delta, salir temprano ---
    if df_fact.empty:
        print("    -> [!] df_fact está vacío. No hay datos delta para procesar.")
        return {'insert_count': 0, 'update_count': 0, 'delete_count': 0}

    tickets_delta = sorted(int(x) for x in df_fact['nro_ticket'].unique())
    tickets_tuple = tuple(tickets_delta)

    # --- Validación: si no hay tickets, salir temprano ---
    if not tickets_tuple:
        print("    -> [!] No se encontraron tickets en df_fact. Saliendo de CDC.")
        return {'insert_count': 0, 'update_count': 0, 'delete_count': 0}
    
    # Obtener hashes actuales del DW para estos tickets
    query_dw_hashes = f"""
        SELECT sk_venta, nro_ticket, cantidad_vendida, precio_unitario, monto_bruto,
               descuento_aplicado, monto_neto, row_hash
        FROM Fact_Venta WHERE nro_ticket IN {tickets_tuple}
    """
    dw_hashes = pd.read_sql(query_dw_hashes, engine_dw)

    tickets_existentes = set(dw_hashes['nro_ticket'].unique())
    tickets_nuevos = [t for t in tickets_delta if t not in tickets_existentes]

    df_insert = df_fact[df_fact['nro_ticket'].isin(tickets_nuevos)].copy()
    df_potencial_update = df_fact[df_fact['nro_ticket'].isin(tickets_existentes)].copy()

    insert_count = 0
    update_count = 0
    delete_count = 0

    cols_fact_insert = [
        'sk_tiempo', 'sk_cliente', 'sk_producto', 'sk_sucursal', 'nro_ticket',
        'cantidad_vendida', 'precio_unitario', 'monto_bruto', 'descuento_aplicado',
        'monto_neto', 'last_updated', 'row_hash'
    ]

    # ========== INSERTS (tickets completamente nuevos) ==========
    if not df_insert.empty:
        print(f"    -> {len(df_insert)} filas nuevas para INSERT (tickets: {df_insert['nro_ticket'].nunique()})")

        df_insert[cols_fact_insert].to_sql(
            'Fact_Venta', engine_dw, if_exists='append', index=False, method='multi',
            dtype={
                'precio_unitario': types.Numeric(12, 2),
                'monto_bruto': types.Numeric(12, 2),
                'monto_neto': types.Numeric(12, 2),
                'cantidad_vendida': types.Numeric(10, 2),
                'descuento_aplicado': types.Numeric(12, 2),
                'last_updated': types.DateTime,
                'row_hash': types.String(32)
            }
        )
        insert_count = len(df_insert)

        with engine_dw.connect() as conn:
            for ticket in df_insert['nro_ticket'].unique():
                _registrar_changelog(
                    conn, ticket, 'INSERT', fecha_ejecucion, None,
                    df_insert[df_insert['nro_ticket'] == ticket]['row_hash'].iloc[0],
                    script_name,
                    f"Insertadas {len(df_insert[df_insert['nro_ticket'] == ticket])} líneas"
                )
            conn.commit()

    # ========== UPDATES (tickets existentes que cambiaron) ==========
    if not df_potencial_update.empty and not dw_hashes.empty:
        tickets_existentes_tuple = tuple(sorted(int(x) for x in tickets_existentes))

        # --- Validación: si no hay tickets existentes, evitar consulta IN () ---
        if not tickets_existentes_tuple:
            print("    -> [!] No hay tickets existentes en el DW para comparar.")
        else:
            query_dw_existing = f"""
                SELECT sk_venta, nro_ticket, sk_cliente, sk_producto, sk_sucursal,
                       cantidad_vendida, precio_unitario, monto_bruto, descuento_aplicado,
                       monto_neto, row_hash
                FROM Fact_Venta WHERE nro_ticket IN {tickets_existentes_tuple}
            """
            dw_existing = pd.read_sql(query_dw_existing, engine_dw)

            # Clave natural de línea: (nro_ticket, sk_cliente, sk_producto, sk_sucursal)
            df_potencial_update['merge_key'] = (
                df_potencial_update['nro_ticket'].astype(str) + '_' +
                df_potencial_update['sk_cliente'].astype(str) + '_' +
                df_potencial_update['sk_producto'].astype(str) + '_' +
                df_potencial_update['sk_sucursal'].astype(str)
            )
            dw_existing['merge_key'] = (
                dw_existing['nro_ticket'].astype(str) + '_' +
                dw_existing['sk_cliente'].astype(str) + '_' +
                dw_existing['sk_producto'].astype(str) + '_' +
                dw_existing['sk_sucursal'].astype(str)
            )

            merged_updates = df_potencial_update.merge(
                dw_existing[['merge_key', 'sk_venta', 'row_hash']],
                on='merge_key', how='left', suffixes=('_new', '_dw')
            )

            # Filas donde el hash cambió (UPDATE)
            df_changed = merged_updates[
                (merged_updates['sk_venta'].notna()) &
                (merged_updates['row_hash_new'] != merged_updates['row_hash_dw'])
            ].copy()

            # Filas del delta que no encontraron matching en DW (nuevas líneas para tickets existentes)
            df_new_lines = merged_updates[merged_updates['sk_venta'].isna()].copy()

            # --- APLICAR UPDATES ---
            if not df_changed.empty:
                print(f"    -> {len(df_changed)} líneas modificadas detectadas. Ejecutando UPDATE...")
                update_count = len(df_changed)
                with engine_dw.connect() as conn:
                    for _, row in df_changed.iterrows():
                        conn.execute(text("""
                            UPDATE Fact_Venta SET
                                cantidad_vendida = :cantidad,
                                precio_unitario = :precio,
                                monto_bruto = :bruto,
                                descuento_aplicado = :descuento,
                                monto_neto = :neto,
                                last_updated = :fecha,
                                row_hash = :hash
                            WHERE sk_venta = :sk
                        """), {
                            "cantidad": row['cantidad_vendida'],
                            "precio": row['precio_unitario'],
                            "bruto": row['monto_bruto'],
                            "descuento": row['descuento_aplicado'],
                            "neto": row['monto_neto'],
                            "fecha": fecha_ejecucion,
                            "hash": row['row_hash_new'],
                            "sk": int(row['sk_venta'])
                        })

                        _registrar_changelog(
                            conn, row['nro_ticket'], 'UPDATE', fecha_ejecucion,
                            row['row_hash_dw'], row['row_hash_new'], script_name,
                            f"Línea sk_venta={int(row['sk_venta'])} modificada"
                        )
                    conn.commit()

            # --- INSERTAR NUEVAS LÍNEAS PARA TICKETS EXISTENTES ---
            if not df_new_lines.empty:
                print(f"    -> {len(df_new_lines)} nuevas líneas para tickets existentes. Insertando...")
                df_new_lines[cols_fact_insert].to_sql(
                    'Fact_Venta', engine_dw, if_exists='append', index=False, method='multi',
                    dtype={
                        'precio_unitario': types.Numeric(12, 2),
                        'monto_bruto': types.Numeric(12, 2),
                        'monto_neto': types.Numeric(12, 2),
                        'cantidad_vendida': types.Numeric(10, 2),
                        'descuento_aplicado': types.Numeric(12, 2),
                        'last_updated': types.DateTime,
                        'row_hash': types.String(32)
                    }
                )
                insert_count += len(df_new_lines)

                with engine_dw.connect() as conn:
                    for _, row in df_new_lines.iterrows():
                        _registrar_changelog(
                            conn, row['nro_ticket'], 'INSERT', fecha_ejecucion,
                            None, row['row_hash'], script_name,
                            "Nueva línea agregada a ticket existente"
                        )
                    conn.commit()

        # --- TICKETS AUSENTES EN STAGING (solo log informativo) ---
        tickets_en_staging = set(df_fact['nro_ticket'].unique())
        tickets_ausentes = tickets_existentes - tickets_en_staging

        if tickets_ausentes:
            print(f"    -> [!] Detectados {len(tickets_ausentes)} tickets en DW que no están en el staging actual.")
            print(f"         (No implica eliminación - pueden estar en otro archivo incremental)")
            delete_count = len(tickets_ausentes)
            with engine_dw.connect() as conn:
                for t in list(tickets_ausentes)[:10]:
                    _registrar_changelog(
                        conn, t, 'DELETE', fecha_ejecucion,
                        None, None, script_name,
                        "Ticket presente en DW pero ausente en staging actual (posible baja)"
                    )
                conn.commit()

    return {
        'insert_count': insert_count,
        'update_count': update_count,
        'delete_count': delete_count
    }