"""
Script principal de Carga Incremental - Data Warehouse Centro Más.

Este script ahora delega toda la lógica al módulo `carga_incremental`,
que está organizado en submódulos enfocados en tareas específicas.

Para ver la implementación detallada, explorar la carpeta `carga_incremental/`.
"""
from carga_incremental import ejecutar_carga_incremental

if __name__ == "__main__":
    ejecutar_carga_incremental()