"""
run_etl.py — Orquestador de flujos ETL

Guía al usuario en la ejecución de los flujos de carga inicial y carga incremental,
ejecutando automáticamente los scripts en el orden correcto.

Modo de uso:
    python run_etl.py

Flujos disponibles:
    1. Carga Inicial  → 00_crear_dw.py → 01_staging_area.py (f) → 02_staging_clean.py → 03_carga_Inicial_dw.py
    2. Carga Incremental → 01_staging_area.py (i) → 02_staging_clean.py → 04_carga_incremental.py
"""

import subprocess
import sys
import os

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))

SCRIPTS = {
    "crear_dw": "00_crear_dw.py",
    "staging_area": "01_staging_area.py",
    "staging_clean": "02_staging_clean.py",
    "carga_inicial_dw": "03_carga_Inicial_dw.py",
    "carga_incremental": "04_carga_incremental.py",
}

FLUJO_INICIAL = [
    ("Crear Data Warehouse (esquema físico)", "crear_dw", None),
    ("Cargar archivos CSV a Staging (carga inicial)", "staging_area", "f"),
    ("Limpiar y transformar datos en Staging Clean", "staging_clean", None),
    ("Cargar datos limpios al Data Warehouse (carga inicial)", "carga_inicial_dw", None),
]

FLUJO_INCREMENTAL = [
    ("Cargar nuevos archivos CSV a Staging (carga incremental)", "staging_area", "i"),
    ("Limpiar y transformar nuevos datos en Staging Clean", "staging_clean", None),
    ("Actualizar Data Warehouse con datos incrementales (CDC + SCD2)", "carga_incremental", None),
]


def ejecutar_script(script_name, argumento=None):
    """Ejecuta un script Python y retorna True si fue exitoso."""
    script_path = os.path.join(SCRIPTS_DIR, script_name)
    
    if not os.path.exists(script_path):
        print(f"  [ERROR] No se encontró el archivo: {script_path}")
        return False

    cmd = [sys.executable, script_path]
    if argumento:
        cmd.append(argumento)

    print(f"\n{'='*70}")
    print(f" ▶ EJECUTANDO: python {script_name}" + (f" {argumento}" if argumento else ""))
    print(f"{'='*70}\n")

    result = subprocess.run(cmd, cwd=SCRIPTS_DIR)

    if result.returncode == 0:
        print(f"\n{'='*70}")
        print(f" ✅ FINALIZADO: {script_name}")
        print(f"{'='*70}")
        return True
    else:
        print(f"\n{'='*70}")
        print(f" ❌ ERROR: {script_name} terminó con código {result.returncode}")
        print(f"{'='*70}")
        return False


def ejecutar_flujo(flujo, nombre_flujo):
    """Ejecuta una secuencia de pasos (flujo) y aborta si alguno falla."""
    print(f"\n{'#'*70}")
    print(f" # INICIANDO FLUJO: {nombre_flujo}")
    print(f"{'#'*70}\n")

    for descripcion, script_key, argumento in flujo:
        script_name = SCRIPTS[script_key]

        print(f"\n[PASO] {descripcion}")
        print(f"       Script: {script_name}")
        confirmar = input("¿Ejecutar este paso? (Enter para continuar, 's' para saltar, 'x' para cancelar): ").strip().lower()

        if confirmar == 'x':
            print("\n[FLUJO CANCELADO POR EL USUARIO]")
            return False
        elif confirmar == 's':
            print("  -> Paso saltado.")
            continue

        ok = ejecutar_script(script_name, argumento)
        if not ok:
            print(f"\n[FLUJO ABORTADO] Falló en: {descripcion}")
            return False

    print(f"\n{'#'*70}")
    print(f" ✅ FLUJO COMPLETADO EXITOSAMENTE: {nombre_flujo}")
    print(f"{'#'*70}")
    return True


def mostrar_menu():
    """Muestra el menú principal y retorna la opción elegida."""
    print("\n" + "="*60)
    print("   🏪 ETL CENTROMÁS — ORQUESTADOR DE FLUJOS")
    print("="*60)
    print("   ¿Qué flujo deseas ejecutar?")
    print()
    print("   1. CARGA INICIAL (primera vez)")
    print("      - Crea el DW, carga todos los CSV, limpia datos y puebla el DW")
    print()
    print("   2. CARGA INCREMENTAL (ejecución periódica)")
    print("      - Carga solo archivos nuevos, limpia y actualiza el DW (SCD2)")
    print()
    print("   3. SALIR")
    print("="*60)

    opcion = input("Selecciona una opción (1, 2 o 3): ").strip()
    return opcion


def main():
    while True:
        opcion = mostrar_menu()

        if opcion == "1":
            print("\n[INFO] Se ejecutarán los siguientes scripts en orden:")
            for desc, script_key, arg in FLUJO_INICIAL:
                script = SCRIPTS[script_key]
                print(f"   - {script}" + (f" {arg}" if arg else "") + f"  → {desc}")
            print()
            confirmar = input("¿Estás seguro de iniciar el Flujo de CARGA INICIAL? (s/n): ").strip().lower()
            if confirmar == 's':
                ejecutar_flujo(FLUJO_INICIAL, "CARGA INICIAL")
            else:
                print("\n[FLUJO CANCELADO]")

        elif opcion == "2":
            print("\n[INFO] Se ejecutarán los siguientes scripts en orden:")
            for desc, script_key, arg in FLUJO_INCREMENTAL:
                script = SCRIPTS[script_key]
                print(f"   - {script}" + (f" {arg}" if arg else "") + f"  → {desc}")
            print()
            confirmar = input("¿Estás seguro de iniciar el Flujo de CARGA INCREMENTAL? (s/n): ").strip().lower()
            if confirmar == 's':
                ejecutar_flujo(FLUJO_INCREMENTAL, "CARGA INCREMENTAL")
            else:
                print("\n[FLUJO CANCELADO]")

        elif opcion == "3":
            print("\n👋 Saliendo del orquestador. ¡Hasta luego!\n")
            break

        else:
            print("\n[!] Opción no válida. Ingresa 1, 2 o 3.")

        input("\nPresiona Enter para volver al menú principal...")


if __name__ == "__main__":
    main()