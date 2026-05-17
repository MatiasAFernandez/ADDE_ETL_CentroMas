# TPI Supermercado — Data Warehouse "CentroMás"

## Resumen del Proyecto

Este proyecto implementa un proceso **ETL (Extract, Transform, Load)** completo para construir un **Data Warehouse (DW)** en esquema estrella (*star schema*) a partir de archivos CSV fuente de un supermercado denominado **CentroMás**.

### Objetivo

Poner en práctica conceptos fundamentales de integración de datos, modelado multidimensional y carga de un Data Warehouse, incluyendo consideraciones de integridad, historización (SCD Tipo 2) y calidad de datos.

### Tecnologías Utilizadas

- **Python 3** como lenguaje de automatización del proceso ETL
- **Microsoft SQL Server** como motor de base de datos
- **pandas** para transformación y manipulación de datos
- **SQLAlchemy** como ORM / motor de conexión
- **pymssql** (FreeTDS) o **pyodbc + ODBC Driver 18** como drivers de conexión a SQL Server (a elección del usuario)

**Se recomienda crear un entorno virtual para instalar las librerías necesarias:**

1. Crear el entorno virtual:
   ```bash
   python -m venv venv
   ```

2. Activar el entorno virtual:
   - En Windows:
     ```bash
     venv\Scripts\activate
     ```
   - En Linux/Mac:
     ```bash
     source venv/bin/activate
     ```

3. Instalar las librerías requeridas:
   ```bash
   pip install -r requirements.txt
   ```

---

## Orquestador Automático (Recomendado)

En lugar de ejecutar cada script manualmente, puede utilizar el **orquestador** `run_etl.py` que guía al usuario mediante un menú interactivo y ejecuta los scripts en el orden correcto para cada flujo:

```bash
python run_etl.py
```

El orquestador muestra un menú con las siguientes opciones:

```
   1. CARGA INICIAL (primera vez)
   2. CARGA INCREMENTAL (ejecución periódica)
   3. SALIR
```

Cada flujo se compone de varios pasos que pueden confirmarse, saltarse o cancelarse individualmente. Si algún script falla, el flujo se aborta automáticamente para evitar errores en cascada.

> **Nota:** Si es la primera ejecución y no existe `db_config.json`, el orquestador ejecutará los scripts que a su vez iniciarán el asistente de configuración de base de datos automáticamente.

---

## Flujos de Trabajo

El proyecto contempla **dos flujos de ejecución** bien diferenciados:

### Flujo 1: Carga Inicial (primera vez)

```
┌──────────────┐       ┌──────────────────┐       ┌───────────────────┐       ┌──────────────────────┐
│              │       │                  │       │                   │       │                      │
│  Archivos    │──────▶│  01_staging_    │──────▶│  02_staging_     │──────▶│  03_carga_Inicial_   │
│  CSV Fuente  │       │  area.py        │       │  clean.py         │       │  dw.py                │
│              │       │                  │       │                   │       │                      │
└──────────────┘       └──────────────────┘       └───────────────────┘       └──────────────────────┘
                              │                           │                           │
                              ▼                           ▼                           ▼
                     ┌──────────────────┐       ┌───────────────────┐       ┌──────────────────┐
                     │ CentroMas_       │       │ CentroMas_        │       │ CentroMas_       │
                     │ Staging          │       │ Staging_Clean     │       │ DW               │
                     │ (tablas crudas)  │       │ (datos limpios)   │       │ (Dim + Fact)     │
                     └──────────────────┘       └───────────────────┘       └──────────────────┘

  00_crear_dw.py ─────────────────────────────────────────────────────────────────────────────────┘
                     (crea la base de datos y el esquema del DW - ejecutar antes del Flujo 1)
```

### Flujo 2: Carga Incremental (ejecución periódica)

```
┌──────────────────────┐       ┌──────────────────┐       ┌───────────────────┐       ┌──────────────────────┐
│                      │       │                  │       │                   │       │                      │
│  Nuevos archivos     │──────▶│  01_staging_    │──────▶│  02_staging_     │──────▶│  04_carga_           │
│  CSV (no procesados) │       │  area.py        │       │  clean.py         │       │  incremental.py      │
│                      │       │                  │       │                   │       │                      │
└──────────────────────┘       └──────────────────┘       └───────────────────┘       └──────────────────────┘
                                       │                           │                           │
                                       ▼                           ▼                           ▼
                              ┌──────────────────┐       ┌───────────────────┐       ┌──────────────────────┐
                              │ CentroMas_       │       │ CentroMas_        │       │ CentroMas_DW         │
                              │ Staging          │       │ Staging_Clean     │       │ (actualizaciones     │
                              │ (tablas crudas)  │       │ (datos limpios)   │       │  incrementales)      │
                              └──────────────────┘       └───────────────────┘       └──────────────────────┘
```

---

## Orden de Ejecución

### Flujo de Carga Inicial (primera ejecución)

| Orden | Script                          | Descripción breve                                          |
|-------|---------------------------------|-----------------------------------------------------------|
| 1     | `00_crear_dw.py`                | Crea la base de datos `CentroMas_DW` y sus tablas         |
| 2     | `01_staging_area.py`            | Carga los archivos CSV originales en `CentroMas_Staging`  |
| 3     | `02_staging_clean.py`           | Limpia y transforma los datos en `CentroMas_Staging_Clean`|
| 4     | `03_carga_Inicial_dw.py`       | Puebla el DW con todos los datos limpios (carga inicial)  |

### Flujo de Carga Incremental (ejecución periódica)

| Orden | Script                          | Descripción breve                                          |
|-------|---------------------------------|-----------------------------------------------------------|
| 1     | `01_staging_area.py`            | Carga los nuevos archivos CSV (no procesados) en `CentroMas_Staging` |
| 2     | `02_staging_clean.py`           | Limpia y transforma los nuevos datos en `CentroMas_Staging_Clean` |
| 3     | `04_carga_incremental.py`       | Actualiza el DW con los nuevos datos (CDC por hash + SCD Tipo 2)   |

> **Nota:** Todos los scripts dependen de `db_conexion.py`. Al ejecutar cualquiera de ellos por primera vez, si no existe el archivo `db_config.json`, se iniciará automáticamente un asistente de configuración para establecer la conexión con SQL Server.

---

## Descripción Detallada de Cada Script

### 00_crear_dw.py — Creación del Data Warehouse

**Función principal:** Crea la base de datos `CentroMas_DW` y todo su esquema físico (tablas de dimensiones, tabla de hechos y tablas de soporte).

**Bases de datos que utiliza:**
- `master` (conexión administrativa para crear la base de datos)
- `CentroMas_DW` (base de datos destino que crea)

**Pasos internos:**

1. **Creación de la base de datos** — Verifica si `CentroMas_DW` existe; si no, la crea.
2. **Limpieza previa (idempotencia)** — Elimina las restricciones de clave foránea (`FK`) de `Fact_Venta` si existen, y luego elimina todas las tablas (`DROP TABLE IF EXISTS`).
3. **Creación de dimensiones (en orden):**
   - `Dim_Tiempo` — Dimensión temporal con `sk_tiempo` como clave sustituta en formato `YYYYMMDD`.
   - `Dim_Sucursal` — Sucursales con soporte para **SCD Tipo 2** (columnas `fecha_inicio`, `fecha_fin`, `es_actual`).
   - `Dim_Producto` — Productos con atributos de negocio y soporte SCD Tipo 2.
   - `Dim_Cliente` — Clientes con valores por defecto (`'No Informado'`) para campos opcionales y soporte SCD Tipo 2.
4. **Creación de la tabla de hechos:**
   - `Fact_Venta` — Tabla de hechos con claves foráneas a las 4 dimensiones, métricas aditivas (`cantidad_vendida`, `precio_unitario`, `monto_bruto`, `descuento_aplicado`, `monto_neto`), una dimensión degenerada (`nro_ticket`), columna `last_updated` y `row_hash` (hash MD5 para CDC incremental).
5. **Creación de tablas de soporte:**
   - `Fact_Venta_ChangeLog` — Tabla de auditoría que registra cada INSERT, UPDATE o DELETE sobre la tabla de hechos durante la carga incremental.
   - `ETL_Logs` — Tabla de registro de ejecuciones ETL con estado, filas procesadas y mensajes (gestionada vía `audit_logger.py`).
   - `Staging_Clean_Rechazados` — Tabla de cuarentena para registros huérfanos detectados durante la carga incremental (órdenes sin detalle o viceversa).

**Particularidades:**
- Es **idempotente**: puede ejecutarse múltiples veces sin generar errores (limpia y recrea el esquema).
- No carga datos, solo define la estructura.
- **Debe ejecutarse antes del primer uso del Flujo 1 (carga inicial).**

---

### 01_staging_area.py — Carga de Datos a Staging

**Función principal:** Lee los archivos CSV fuente y los carga en tablas de staging dentro de la base de datos `CentroMas_Staging`. Los archivos procesados se mueven a una subcarpeta `procesados/` para no volver a cargarlos.

**Bases de datos que utiliza:**
- `master` (para crear/eliminar la base de staging)
- `CentroMas_Staging` (base de datos destino)

**Archivos CSV que carga:**
- `categories.csv`, `customers.csv`, `employees.csv`, `order_details.csv`, `orders.csv`, `payment_methods.csv`, `products.csv`, `promotions.csv`, `stores.csv`, `suppliers.csv`

> **Nota sobre el Flujo Incremental:** Si un archivo CSV no está presente en el lote del día (por ejemplo, no hay clientes nuevos), simplemente se omite sin generar errores. Esto permite cargar únicamente los datos nuevos.

**Pasos internos:**

1. **Configuración de ruta** — Solicita al usuario la ruta de la carpeta que contiene los archivos CSV. Si ya se configuró antes, permite reutilizar la ruta guardada en `db_config.json`.
2. **Recreación de la base de datos** — Si `CentroMas_Staging` ya existe, la elimina y la recrea desde cero para garantizar una carga limpia (**idempotencia**).
3. **Carga masiva** — Itera sobre cada archivo CSV, lo lee con `pandas.read_csv()` y lo inserta en una tabla con prefijo `stg_` (ej: `stg_products`, `stg_customers`) usando `to_sql()` con chunks de 5000 registros.
4. **Archivado** — Los archivos procesados se mueven a la carpeta `procesados/` para evitar reprocesamiento.

**Particularidades:**
- No realiza transformaciones de datos (carga cruda).
- Maneja errores por archivo (si un archivo falla, continúa con el siguiente).
- Reporta cantidad de tablas creadas y registros insertados.
- **Se utiliza tanto en el Flujo 1 (carga inicial) como en el Flujo 2 (carga incremental).**

---

### 02_staging_clean.py — Limpieza y Transformación de Datos

**Función principal:** Toma los datos crudos de `CentroMas_Staging`, aplica reglas de limpieza y calidad de datos, y los guarda en una base de staging intermedia `CentroMas_Staging_Clean`.

**Bases de datos que utiliza:**
- `master` (para crear/eliminar la base clean)
- `CentroMas_Staging` (origen de datos crudos)
- `CentroMas_Staging_Clean` (destino de datos limpios)

**Reglas de auditoría y calidad de datos aplicadas (Data Quality & Cuarentena):**

| Archivo            | Regla de Validación Estricta                                  | Acción ante Dato Inválido / Anomalía                                 |
|--------------------|---------------------------------------------------------------|----------------------------------------------------------------------|
| `products`         | `unit_cost` y `list_price` deben ser reales >= 0              | Se rechaza e inserta en `rejected_records` con motivo detallado      |
| `stores`           | `surface_m2` debe ser numérico > 0                            | Se rechaza e inserta en `rejected_records`                           |
| `order_details`    | `quantity` > 0, `unit_price` >= 0, `discount_pct` >= 0        | Se rechaza e inserta en `rejected_records`                           |
| `orders`           | `net_amount` debe ser numérico >= 0                           | Se rechaza e inserta en `rejected_records`                           |
| `customers` / varios| Datos mal formados (ej. strings en columnas numéricas)        | Se convierten a Null (coerce) y son enviados a cuarentena (rechazados)|

**Reglas de transformación aplicadas:**

| Archivo      | Problema                        | Acción                                           |
|-------------|---------------------------------|--------------------------------------------------|
| `customers` | Género en código (`F`/`M`)     | Normaliza a `'Femenino'`/`'Masculino'`           |
| `customers` | Género inconsistente            | Infiere el género a partir del nombre del cliente |
| `customers` | Clientes duplicados             | Deduplicación por nombre + ciudad + provincia, conservando el de mayor edad |
| `customers` | Fecha de registro posterior a la primera compra | Corrige `registration_date` usando la fecha de la orden más antigua |
| `products`  | Categoría faltante              | Asigna el valor `'Sin Categoría'` de forma segura|
| `products`  | Unidades en crudo            | Redondea `quantity` al entero superior si la unidad no es `kg` |

**Pasos internos:**

1. **Idempotencia** — Verifica la existencia de `CentroMas_Staging_Clean` y limpia las tablas para el reproceso.
2. **Inicialización de Lookups** — Crea tablas auxiliares (`lkp_genero_codigos`, `lkp_diccionario_nombres`) para normalización de género.
3. **Validación Exhaustiva** — Revisa los tipos de datos y valores negativos utilizando casteo estricto (`errors='coerce'`).
4. **Productos** — Cruza con categorías de manera dinámica (evitando colisión de columnas), mapea `active_flag` a booleano.
5. **Sucursales** — Convierte tipos de fecha y alerta sobre superficies inválidas.
6. **Clientes (bloque principal):**
   - Normaliza género mediante lookups y diccionario de nombres.
   - Detecta y unifica duplicados, creando un `lkp_duplicados` para reasignar órdenes.
7. **Órdenes/Ventas** — Reasigna `customer_id` al cliente sobreviviente. Corrige fechas de registro inválidas.
8. **Detalles de órdenes** — Aplica regla de unidades (redondeo para productos no pesables).
9. **Carga final y Cuarentena** — Inserta todas las tablas limpias y genera la tabla transversal `rejected_records` (solo si hay datos defectuosos detectados) guardando el payload en JSON.

**Particularidades:**
- Es el script más complejo del proceso.
- Es totalmente **idempotente** (recrea la base de datos limpia cada vez).
- Maneja la integridad referencial entre órdenes y clientes después de la deduplicación.
- **Se utiliza tanto en el Flujo 1 como en el Flujo 2.**

---

### 03_carga_Inicial_dw.py — Carga Inicial del Data Warehouse

**Función principal:** Puebla las tablas del Data Warehouse (`CentroMas_DW`) con **todos** los datos limpios provenientes de `CentroMas_Staging_Clean` por primera vez.

**Bases de datos que utiliza:**
- `CentroMas_Staging_Clean` (origen de datos limpios)
- `CentroMas_DW` (destino final)

**Pasos internos:**

1. **Limpieza de tablas del DW (idempotencia)** — Vacía todas las tablas del DW y resetea los contadores `IDENTITY` de las dimensiones.
2. **Carga de Dim_Tiempo** — Genera un calendario continuo desde la fecha de la orden más antigua hasta la más reciente. Calcula `sk_tiempo` como `YYYYMMDD`, `dia_nro`, `mes_nro`, `anio_nro` y `temporada` (Verano/Otoño/Invierno/Primavera).
3. **Carga de Dim_Sucursal** — Inserta sucursales desde `clean_stores` con `es_actual = 1`, usando `opening_date` como `fecha_inicio`.
4. **Carga de Dim_Producto** — Inserta productos desde `clean_products` con `es_actual = 1`, usando `fecha_carga` como `fecha_inicio`.
5. **Carga de Dim_Cliente** — Calcula la edad a partir de la fecha de nacimiento y carga los clientes deduplicados, usando `registration_date` como `fecha_inicio`.
6. **Carga de Fact_Venta (mapeo seguro de claves)** — Para cada detalle de orden, resuelve las claves sustitutas (*surrogate keys*) reales del DW mediante joins con las dimensiones:
   - `sk_sucursal` → lookup por `id_sucursal_bk`
   - `sk_producto` → lookup vía `sku` en `clean_products`
   - `sk_cliente` → lookup vía `customer_code` en `clean_customers`
   - `sk_tiempo` → calculado desde la fecha de la orden

**Particularidades:**
- **Totalmente idempotente**: puede ejecutarse múltiples veces (limpia y recarga todo).
- Utiliza **mapeo seguro** de claves sustitutas leyendo los IDs reales desde el DW (no asume valores).
- Las dimensiones incluyen `fecha_inicio`, `fecha_fin`, `es_actual` para soportar **SCD Tipo 2** en cargas incrementales posteriores.
- **Solo debe ejecutarse en el Flujo 1 (carga inicial). No debe ejecutarse en el Flujo 2.**

---

### 04_carga_incremental.py — Carga Incremental (CDC por Hash & SCD Tipo 2)

**Función principal:** Actualiza el Data Warehouse `CentroMas_DW` con nuevos datos provenientes de `CentroMas_Staging_Clean`, aplicando técnicas de **Change Data Capture (CDC) mediante hash MD5** y **SCD Tipo 2** para mantener el historial de cambios en las dimensiones.

**Nota de Arquitectura:** El script `04_carga_incremental.py` actúa como un **punto de entrada mínimo** que delega toda la lógica al paquete modular `carga_incremental/`. Este paquete está organizado en submódulos especializados que se describen en la siguiente sección.

**Bases de datos que utiliza:**
- `CentroMas_Staging_Clean` (origen de datos limpios con nuevas transacciones)
- `CentroMas_DW` (destino final, actualizado incrementalmente)

**Pasos internos del orquestador (`carga_incremental/main.py`):**

1. **Inicialización de auditoría** — Prepara las variables de auditoría y establece las conexiones a las bases de datos.

2. **Carga desde Staging Clean** — Lee todas las tablas limpias (`clean_orders`, `clean_order_details`, `clean_customers`, `clean_products`, `clean_stores`) mediante `staging_loader.py`.

3. **Detección de registros huérfanos** — Crea la tabla `Staging_Clean_Rechazados` (si no existe) y detecta:
   - Órdenes sin detalle asociado (order_id presente en `clean_orders` pero ausente en `clean_order_details`).
   - Detalles sin orden padre (order_id en `clean_order_details` que no existe en `clean_orders`).
   
4. **Procesamiento SCD Tipo 2 en dimensiones** — Por cada dimensión:
   - **Dim_Cliente** — Compara `ciudad_cliente` y `provincia_cliente`. Si hay cambios, cierra el registro activo (`es_actual = 0`, `fecha_fin` = fecha de ejecución) e inserta uno nuevo con los datos actualizados.
   - **Dim_Producto** — Compara `costo_unidad`, `precio_lista` y `categoria_nombre`. Ante cualquier variación (tolerancia de 0.01 en valores numéricos), cierra el historial anterior y abre uno nuevo.
   - **Dim_Sucursal** — Compara `superficie_m2`, `ciudad_sucursal` y `provincia_sucursal`. Aplica cierre/apertura de historial ante cualquier cambio.

5. **Sincronización de diccionarios de traducción** — Actualiza las tablas `dict_clientes` y `dict_productos` en `CentroMas_Staging_Clean`. Estas tablas permiten traducir IDs transaccionales (ej: `customer_id`) a *business keys* (ej: `customer_code`) para el mapeo de claves sustitutas.

6. **Construcción del delta de hechos** — Prepara el DataFrame de `Fact_Venta` con los nuevos registros:
   - Merge de `clean_orders` y `clean_order_details`.
   - Cálculo de `sk_tiempo` en formato `YYYYMMDD`.
   - Cruce con los diccionarios de traducción y las dimensiones del DW mediante **joins temporales as-was** (resuelve qué versión de la dimensión estaba vigente en la fecha de la transacción).
   - Cálculo de métricas (`monto_bruto`) y generación de `row_hash` (hash MD5 de las columnas de negocio) para la detección de cambios.

7. **Mantenimiento de Dim_Tiempo** — Si existen nuevas fechas en el delta que no están en `Dim_Tiempo`, se insertan los registros de calendario faltantes con su temporada correspondiente.

8. **Ejecución de UPSERT por hash (CDC)** — Ejecuta el proceso detallado en `cdc_upsert.py`:
   - **Tickets nuevos**: Se insertan directamente con todas sus líneas.
   - **Tickets existentes**: Se compara el hash línea a línea; las líneas con hash coincidente se omiten, las que cambiaron se actualizan, y las nuevas líneas se insertan.
   - **Registro en ChangeLog**: Cada operación (INSERT, UPDATE) se registra en `Fact_Venta_ChangeLog` con el hash anterior y nuevo, la fecha y el script ejecutor.
   - **Tickets ausentes en staging**: Se detectan tickets presentes en el DW pero no en el staging actual (log informativo en ChangeLog como tipo `DELETE`).

9. **Registro de auditoría** — Al finalizar (o fallar) la ejecución, se escribe un registro en `ETL_Logs` con el script, estado, filas procesadas y mensaje.

**Particularidades:**
- **No es idempotente**: está diseñado para ejecutarse periódicamente y solo procesa datos nuevos.
- Utiliza **SCD Tipo 2** para preservar el historial de cambios en las dimensiones.
- Implementa **CDC por hash MD5** en la tabla de hechos, comparando hashes línea a línea para detectar cambios, en lugar de usar un simple *High-Water Mark* o *timestamp*.
- Utiliza **joins temporales as-was** para asociar cada venta a la versión correcta de la dimensión vigente en la fecha de la transacción.
- Detecta automáticamente registros huérfanos y los almacena en una tabla de cuarentena.
- Mantiene un **ChangeLog** detallado de todos los cambios sobre `Fact_Venta`.
- Depende de que `03_carga_Inicial_dw.py` se haya ejecutado al menos una vez para establecer los datos base en el DW.
- **Solo debe ejecutarse en el Flujo 2 (carga incremental).**

---

## Paquete `carga_incremental/` — Arquitectura Modular

La lógica de la carga incremental está organizada en un paquete Python modular dentro de la carpeta `carga_incremental/`, lo que mejora la mantenibilidad, separación de responsabilidades y facilita las pruebas unitarias.

### Estructura del Paquete

```
carga_incremental/
├── __init__.py        # Exporta ejecutar_carga_incremental
├── main.py            # Orquestador principal
├── config.py          # Constantes y configuración
├── staging_loader.py  # Carga de datos desde Staging Clean
├── rechazados.py      # Detección de registros huérfanos
├── dimension_scd.py   # SCD Tipo 2 para Clientes, Productos, Sucursales
├── diccionarios.py    # Sincronización de tablas diccionario (ID → BK)
├── dim_tiempo.py      # Mantenimiento dinámico de Dim_Tiempo
├── fact_builder.py    # Construcción del delta de hechos
├── hash_utils.py      # Funciones hash (MD5) para CDC
├── cdc_upsert.py      # Lógica UPSERT por hash (Change Data Capture)
└── audit_logger.py    # Inicialización y escritura de logs ETL
```

### Descripción de cada submódulo

| Módulo                      | Responsabilidad                                                                 |
|-----------------------------|---------------------------------------------------------------------------------|
| `config.py`                 | Define constantes: nombres de bases de datos (`CentroMas_DW`, `CentroMas_Staging_Clean`) y nombre del script. |
| `staging_loader.py`         | Carga los DataFrames desde las tablas limpias (`clean_orders`, `clean_customers`, etc.) usando `pd.read_sql()`. |
| `rechazados.py`             | Crea la tabla `Staging_Clean_Rechazados` y detecta registros huérfanos (órdenes sin detalle y viceversa). |
| `dimension_scd.py`          | Implementa SCD Tipo 2 para las tres dimensiones: compara atributos entre staging y DW, cierra historial anterior y abre nuevo. |
| `diccionarios.py`           | Sincroniza las tablas `dict_clientes` y `dict_productos` que traducen IDs transaccionales a *business keys*. |
| `dim_tiempo.py`             | Verifica qué fechas (`sk_tiempo`) faltan en `Dim_Tiempo` y las inserta con su temporada correspondiente. |
| `fact_builder.py`           | Construye el DataFrame delta de `Fact_Venta`: merge de órdenes y detalles, cruce con dimensiones (joins as-was), cálculo de métricas y hash. |
| `hash_utils.py`             | Calcula el hash MD5 de una fila de `Fact_Venta` combinando todas las columnas de negocio (`cantidad_vendida`, `precio_unitario`, etc.). |
| `cdc_upsert.py`             | Ejecuta la lógica de UPSERT: separa tickets nuevos (INSERT) de existentes (compara hash → UPDATE/omite), registra cambios en `Fact_Venta_ChangeLog`. |
| `audit_logger.py`           | Inicializa variables de auditoría y escribe el registro final en `ETL_Logs` (se ejecuta incluso en caso de error, gracias al bloque `finally`). |

---

## Ejecución Completa (Paso a Paso)

### Método recomendado: Usando el Orquestador

```bash
python run_etl.py
```

Luego seleccionar:
- **Opción 1** para la **carga inicial** (primera vez)
- **Opción 2** para la **carga incremental** (ejecución periódica)

El orquestador se encargará de ejecutar cada script en el orden correcto y abortará ante cualquier error.

---

### Método manual: Ejecución script por script

#### Flujo 1: Carga Inicial (primera vez)

```bash
# 1. Configurar la conexión (se ejecuta automáticamente si no existe db_config.json)
#    O manualmente: python db_conexion.py

# 2. Crear el Data Warehouse (esquema físico)
python 00_crear_dw.py

# 3. Cargar datos crudos al staging (solicitará la ruta de los CSV originales)
python 01_staging_area.py

# 4. Limpiar y transformar datos
python 02_staging_clean.py

# 5. Cargar el DW con todos los datos limpios
python 03_carga_Inicial_dw.py
```

#### Flujo 2: Carga Incremental (ejecución periódica)

```bash
# 1. Cargar solo los nuevos archivos CSV (los que no se hayan procesado antes)
python 01_staging_area.py

# 2. Limpiar y transformar los nuevos datos
python 02_staging_clean.py

# 3. Actualizar el DW con los nuevos datos (CDC por hash + SCD Tipo 2)
python 04_carga_incremental.py
```

> **Nota importante:** El Flujo 2 (incremental) sustituye al paso 5 del Flujo 1. Una vez realizada la carga inicial, **no debe volver a ejecutarse `03_carga_Inicial_dw.py`**, ya que este reiniciaría por completo el DW. Para incorporar datos nuevos periódicamente, utilice siempre el Flujo 2.

---

## Configuración Inicial

Al ejecutar cualquier script por primera vez, se solicitará:

1. **Servidor SQL Server** (por defecto: `127.0.0.1`)
2. **Tipo de autenticación**: Windows (`Trusted Connection`) o SQL Server
3. **Usuario y contraseña** (solo para autenticación SQL Server)
4. **Método de conexión**: pymssql (FreeTDS) o pyodbc (ODBC Driver 18)

Esta configuración se guarda en `db_config.json` y se reutiliza automáticamente.

---

### Opciones de Conexión a SQL Server

El programa permite elegir entre **dos métodos de conexión** a SQL Server durante la configuración inicial. Ambos son compatibles con SQLAlchemy y el resto del ETL funciona de forma transparente.

#### Opción 1: pymssql (FreeTDS) — *Por defecto*

- **Ventaja:** No requiere instalar ningún driver ODBC adicional. Funciona con FreeTDS incluido en la librería.
- **URI generada:** `mssql+pymssql://usuario:contraseña@servidor:1433/base_datos?charset=utf8`
- **Recomendado para:** Entornos Linux/Docker donde la instalación del driver ODBC puede ser más compleja.

#### Opción 2: pyodbc + ODBC Driver 18 for SQL Server

- **Ventaja:** Conexión nativa de Microsoft, mejor rendimiento y compatibilidad con características específicas de SQL Server.
- **URI generada:** `mssql+pyodbc://usuario:contraseña@servidor:1433/base_datos?driver=ODBC+Driver+18+for+SQL+Server`
- **Requerimientos:**
  1. El módulo `pyodbc` debe estar instalado (incluido en `requirements.txt`).
  2. El **'ODBC Driver 18 for SQL Server'** debe estar instalado en el sistema. Puedes descargarlo desde:
     - [Microsoft ODBC Driver 18 for SQL Server](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server)
- **Nota:** Si eliges esta opción pero el driver ODBC 18 no está instalado, el programa te mostrará una advertencia con las instrucciones para instalarlo, pero guardará la configuración igualmente. La conexión fallará hasta que instales el driver.
- **Nota sobre seguridad en Windows:** Se agrega automáticamente `TrustServerCertificate=yes` a la URI de conexión con pyodbc para evitar errores de certificado SSL.
- **Recomendado para:** Entornos Windows donde el driver ODBC suele estar preinstalado o es fácil de instalar.

#### Soporte para autenticación de Windows

Si se selecciona autenticación de Windows (`Trusted Connection`), la URI se genera sin credenciales y con el parámetro `trusted_connection=yes`:
- **pymssql:** `mssql+pymssql://@servidor/base_datos`
- **pyodbc:** `mssql+pyodbc://@servidor/base_datos?driver=ODBC+Driver+18+for+SQL+Server&trusted_connection=yes&TrustServerCertificate=yes`

#### Medidas de seguridad en la conexión

- **Forzado de 127.0.0.1:** Si el usuario ingresa `localhost` (o se guardó previamente en el JSON), el sistema lo reemplaza automáticamente por `127.0.0.1` para evitar problemas de resolución IPv6 en Linux.
- **Contraseñas codificadas:** La contraseña se codifica con `urllib.parse.quote_plus()` para manejar caracteres especiales dentro de la URI.
- **Charset UTF-8:** Se agrega `charset=utf8` en la conexión con pymssql para garantizar la correcta codificación de caracteres.

---

## Consideraciones de Calidad de Datos

| Archivo       | Problema Identificado                     | Transformación Aplicada                          |
|---------------|-------------------------------------------|--------------------------------------------------|
| `customers`   | Género en formato código (`F`/`M`)        | Normalización a texto completo                   |
| `customers`   | Género inconsistente con el nombre        | Inferencia mediante diccionario de nombres       |
| `customers`   | Clientes duplicados (~19 casos)           | Deduplicación y unificación de referencias       |
| `customers`   | Fecha de registro posterior a la compra   | Corrección temporal                              |
| `products`    | Unidades no estándar                      | Redondeo de cantidades para productos no pesables |

---

## Auditoría y Trazabilidad

El sistema implementa múltiples mecanismos de auditoría para garantizar la trazabilidad de cada ejecución ETL:

### ETL_Logs — Registro de ejecuciones

Cada vez que se ejecuta `04_carga_incremental.py`, se inserta un registro en la tabla `ETL_Logs` con:
- `script_nombre`: Nombre del script ejecutado.
- `estado`: `EN EJECUCION`, `EXITO` o `ERROR`.
- `filas_procesadas`: Cantidad total de filas procesadas (insertadas + actualizadas).
- `mensaje`: Descripción del resultado o detalle del error.

El registro se escribe en un bloque `finally`, garantizando que incluso si ocurre una excepción, quede constancia en la base de datos.

### Fact_Venta_ChangeLog — Historial de cambios en hechos

Cada operación sobre `Fact_Venta` durante la carga incremental queda registrada en `Fact_Venta_ChangeLog`:
- **INSERT**: Nuevas líneas insertadas (con su hash).
- **UPDATE**: Líneas modificadas (hash anterior y nuevo).
- **DELETE** (informativo): Tickets presentes en el DW pero ausentes en el staging actual.

### Staging_Clean_Rechazados — Cuarentena de huérfanos

Los registros huérfanos detectados durante la carga incremental (órdenes sin detalle o detalles sin orden) se almacenan en la tabla `Staging_Clean_Rechazados` con:
- `tabla_origen`: Tabla donde se originó el rechazo (`clean_orders` o `clean_order_details`).
- `identificador`: ID del registro problemático.
- `razon_rechazo`: Descripción del problema.
- `fecha_rechazo`: Momento en que se detectó.

---

## Estructura Final del Data Warehouse (Esquema en Estrella)

```
Dim_Tiempo (sk_tiempo, fecha_completa, dia_nro, mes_nro, temporada, anio_nro)
Dim_Sucursal (sk_sucursal, id_sucursal_bk, superficie_m2, ciudad_sucursal, provincia_sucursal, fecha_inicio, fecha_fin, es_actual)
Dim_Producto (sk_producto, id_producto_bk, producto_nombre, marca_nombre, categoria_nombre, costo_unidad, precio_lista, fecha_inicio, fecha_fin, es_actual)
Dim_Cliente (sk_cliente, id_cliente_bk, genero, edad, tipo_cliente, ciudad_cliente, provincia_cliente, fecha_inicio, fecha_fin, es_actual)

Fact_Venta (sk_venta, sk_tiempo, sk_cliente, sk_producto, sk_sucursal, nro_ticket, cantidad_vendida, precio_unitario, monto_bruto, descuento_aplicado, monto_neto, last_updated, row_hash)
```

### Tablas de Soporte (Auditoría y Cuarentena)

```
Fact_Venta_ChangeLog (id_changelog, nro_ticket, tipo_cambio, fecha_cambio, hash_anterior, hash_nuevo, ejecucion_etl, detalle)
ETL_Logs (id_log, script_nombre, estado, filas_procesadas, mensaje, fecha_ejecucion)
Staging_Clean_Rechazados (id, tabla_origen, identificador, razon_rechazo, fecha_rechazo)
```

---