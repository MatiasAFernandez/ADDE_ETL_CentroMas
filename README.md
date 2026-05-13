# TPI Supermercado — Data Warehouse "CentroMás"

## Resumen del Proyecto

Este proyecto implementa un proceso **ETL (Extract, Transform, Load)** completo para construir un **Data Warehouse (DW)** en esquema estrella (*star schema*) a partir de archivos CSV fuente de un supermercado denominado **CentroMás**.

### Objetivo

Poner en práctica conceptos fundamentales de integración de datos, modelado multidimensional y carga de un Data Warehouse, incluyendo consideraciones de integridad, historización (SCD Tipo 2) y calidad de datos.

### Tecnologías Utilizadas

- **Python 3** como lenguaje de automatización del proceso ETL
- **Microsoft SQL Server** como motor de base de datos
- **pandas** para transformación y manipulación de datos
- **SQLAlchemy + pyodbc** como puente de conexión entre Python y SQL Server
- **Driver ODBC 18 para SQL Server**

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
   pip install pandas sqlalchemy pyodbc
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
| 3     | `04_carga_incremental.py`       | Actualiza el DW con los nuevos datos (CDC y SCD Tipo 2)   |

> **Nota:** Todos los scripts dependen de `db_conexion.py`. Al ejecutar cualquiera de ellos por primera vez, si no existe el archivo `db_config.json`, se iniciará automáticamente un asistente de configuración para establecer la conexión con SQL Server.

---

## Descripción Detallada de Cada Script

### 00_crear_dw.py — Creación del Data Warehouse

**Función principal:** Crea la base de datos `CentroMas_DW` y todo su esquema físico (tablas de dimensiones y tabla de hechos).

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
   - `Fact_Venta` — Tabla de hechos con claves foráneas a las 4 dimensiones, métricas aditivas (`cantidad_vendida`, `precio_unitario`, `monto_bruto`, `descuento_aplicado`, `monto_neto`) y una dimensión degenerada (`nro_ticket`).

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

### 04_carga_incremental.py — Carga Incremental (CDC & SCD Tipo 2)

**Función principal:** Actualiza el Data Warehouse `CentroMas_DW` con nuevos datos provenientes de `CentroMas_Staging_Clean`, aplicando técnicas de **Change Data Capture (CDC)** y **SCD Tipo 2** para mantener el historial de cambios en las dimensiones.

**Bases de datos que utiliza:**
- `CentroMas_Staging_Clean` (origen de datos limpios con nuevas transacciones)
- `CentroMas_DW` (destino final, actualizado incrementalmente)

**Pasos internos:**

1. **Actualización de Dim_Tiempo** — Consulta la fecha máxima de `clean_orders` y la compara con el `sk_tiempo` máximo del DW. Si existen nuevos días, genera los registros de calendario faltantes y los inserta en `Dim_Tiempo`.

2. **SCD2 en Dim_Sucursal** — Compara los datos actuales de sucursales en staging contra los registros activos (`es_actual = 1`) del DW. Si detecta cambios en atributos (`superficie_m2`, `ciudad_sucursal`, `provincia_sucursal`):
   - **Cierra el historial anterior**: actualiza `es_actual = 0` y `fecha_fin` con la fecha de ejecución.
   - **Abre nuevo historial**: inserta una nueva versión del registro con `fecha_inicio` = fecha de ejecución y `es_actual = 1`.
   - **Registros inéditos**: las sucursales nuevas se insertan directamente con `es_actual = 1`.

3. **SCD2 en Dim_Producto** — Similar a sucursales, compara atributos (`producto_nombre`, `marca_nombre`, `categoria_nombre`, `costo_unidad`, `precio_lista`) y aplica SCD Tipo 2 ante cualquier cambio.

4. **SCD2 en Dim_Cliente** — Calcula la edad actual a partir de `birth_date` y compara atributos (`genero`, `edad`, `tipo_cliente`, `ciudad_cliente`, `provincia_cliente`). Aplica cierre/apertura de historial según corresponda.

5. **Carga de hechos (High-Water Mark)** — Utiliza **High-Water Mark** basado en `nro_ticket` para identificar nuevos tickets de venta:
   - Obtiene el último `nro_ticket` insertado en `Fact_Venta`.
   - Extrae de `clean_orders` y `clean_order_details` solo los registros con `order_id > hwm_ticket`.
   - Mapea cada registro a las claves sustitutas activas (`sk_sucursal`, `sk_producto`, `sk_cliente`, `sk_tiempo`) mediante joins con las dimensiones actualizadas.
   - Inserta los nuevos registros en `Fact_Venta`.

**Particularidades:**
- **No es idempotente**: está diseñado para ejecutarse periódicamente y solo procesa datos nuevos.
- Utiliza **SCD Tipo 2** para preservar el historial de cambios en las dimensiones.
- Implementa **High-Water Mark** sobre `nro_ticket` para la tabla de hechos, evitando duplicados.
- La función `actualizar_dimension()` centraliza la lógica de SCD2 (cierre + apertura) para las tres dimensiones.
- Depende de que `03_carga_Inicial_dw.py` se haya ejecutado al menos una vez para establecer los datos base en el DW.
- **Solo debe ejecutarse en el Flujo 2 (carga incremental).**

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

# 3. Actualizar el DW con los nuevos datos (CDC + SCD Tipo 2)
python 04_carga_incremental.py
```

> **Nota importante:** El Flujo 2 (incremental) sustituye al paso 5 del Flujo 1. Una vez realizada la carga inicial, **no debe volver a ejecutarse `03_carga_Inicial_dw.py`**, ya que este reiniciaría por completo el DW. Para incorporar datos nuevos periódicamente, utilice siempre el Flujo 2.

---

## Configuración Inicial

Al ejecutar cualquier script por primera vez, se solicitará:

1. **Servidor SQL Server** (por defecto: `localhost`)
2. **Tipo de autenticación**: Windows (`Trusted Connection`) o SQL Server
3. **Usuario y contraseña** (solo para autenticación SQL Server)
4. **Driver ODBC** para SQL Server (lista los disponibles en el equipo)

Esta configuración se guarda en `db_config.json` y se reutiliza automáticamente.

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

## Estructura Final del Data Warehouse (Esquema en Estrella)

```
Dim_Tiempo (sk_tiempo, fecha_completa, dia_nro, mes_nro, temporada, anio_nro)
Dim_Sucursal (sk_sucursal, id_sucursal_bk, superficie_m2, ciudad_sucursal, provincia_sucursal, fecha_inicio, fecha_fin, es_actual)
Dim_Producto (sk_producto, id_producto_bk, producto_nombre, marca_nombre, categoria_nombre, costo_unidad, precio_lista, fecha_inicio, fecha_fin, es_actual)
Dim_Cliente (sk_cliente, id_cliente_bk, genero, edad, tipo_cliente, ciudad_cliente, provincia_cliente, fecha_inicio, fecha_fin, es_actual)

Fact_Venta (sk_venta, sk_tiempo, sk_cliente, sk_producto, sk_sucursal, nro_ticket, cantidad_vendida, precio_unitario, monto_bruto, descuento_aplicado, monto_neto)
```