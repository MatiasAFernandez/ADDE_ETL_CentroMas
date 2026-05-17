# Módulos para carga incremental del Data Warehouse
# Cada submódulo se enfoca en una tarea específica del proceso ETL

from .main import ejecutar_carga_incremental

__all__ = ['ejecutar_carga_incremental']