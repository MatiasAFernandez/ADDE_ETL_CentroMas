"""Funciones hash para detección de cambios (CDC) en la tabla de hechos."""
import hashlib


def calcular_hash(row):
    """
    Genera un hash MD5 consistente para una fila de Fact_Venta.
    Incluye todas las columnas de negocio que definen el contenido real del registro.
    """
    raw = (
        str(row['cantidad_vendida']) + '|' +
        str(row['precio_unitario']) + '|' +
        str(row['monto_bruto']) + '|' +
        str(row['descuento_aplicado']) + '|' +
        str(row['monto_neto'])
    )
    return hashlib.md5(raw.encode('utf-8')).hexdigest()