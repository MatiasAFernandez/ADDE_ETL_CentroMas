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

**Se recomienda crear un entorno virtual para instalar las librerias necesarias**
**pip install pandas sqlalchemy pyodbc**

---

## Arquitectura del Flujo ETL

```
┌──────────────┐       ┌──────────────────┐       ┌───────────────────┐       ┌──────────────┐
│              │       │                  │       │                   │       │              │
│  Archivos    │──────▶│  01_staging_    │──────▶│  02_staging_     │──────▶│  03_carga_   │
│  CSV Fuente  │       │  area.py        │       │  clean.py         │       │  dw.py        │
│              │       │                  │       │                   │       │              │
└──────────────┘       └──────────────────┘       └───────────────────┘       └──────────────┘
                              │                           │                          │
                              ▼                           ▼                          ▼
                     ┌──────────────────┐       ┌───────────────────┐       ┌──────────────────┐
                     │ CentroMas_       │       │ CentroMas_        │       │ CentroMas_       │
                     │ Staging          │       │ Staging_Clean     │       │ DW               │
                     │ (tablas crudas)  │       │ (datos limpios)   │       │ (Dim + Fact)     │
                     └──────────────────┘       └───────────────────┘       └──────────────────┘

  00_crear_dw.py ─────────────────────────────────────────────────────────────────────────────────┘
                    (crea la base de datos y el esquema del DW)
```

---

## Orden de Ejecución de los Scripts

Los scripts deben ejecutarse en el siguiente orden **obligatorio** debido a las dependencias entre ellos:

| Orden | Script               | Descripción breve                              |
|-------|----------------------|-----------------------------------------------|
| 1     | `00_crear_dw.py`     | Crea la base de datos `CentroMas_DW` y sus tablas |
| 2     | `01_staging_area.py` | Carga los archivos CSV en `CentroMas_Staging` |
| 3     | `02_staging_clean.py`| Limpia y transforma los datos en `CentroMas_Staging_Clean` |
| 4     | `03_carga_dw.py`     | Puebla el DW con los datos limpios            |

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

---

### 01_staging_area.py — Carga de Datos a Staging

**Función principal:** Lee los archivos CSV fuente y los carga en tablas de staging dentro de la base de datos `CentroMas_Staging`.

**Bases de datos que utiliza:**
- `master` (para crear/eliminar la base de staging)
- `CentroMas_Staging` (base de datos destino)

**Archivos CSV que carga:**
- `categories.csv`, `customers.csv`, `employees.csv`, `order_details.csv`, `orders.csv`, `payment_methods.csv`, `products.csv`, `promotions.csv`, `stores.csv`, `suppliers.csv`

**Pasos internos:**

1. **Configuración de ruta** — Solicita al usuario la ruta de la carpeta que contiene los archivos CSV. Si ya se configuró antes, permite reutilizar la ruta guardada en `db_config.json`.
2. **Recreación de la base de datos** — Si `CentroMas_Staging` ya existe, la elimina y la recrea desde cero para garantizar una carga limpia (**idempotencia**).
3. **Carga masiva** — Itera sobre cada archivo CSV, lo lee con `pandas.read_csv()` y lo inserta en una tabla con prefijo `stg_` (ej: `stg_products`, `stg_customers`) usando `to_sql()` con chunks de 5000 registros.

**Particularidades:**
- No realiza transformaciones de datos (carga cruda).
- Maneja errores por archivo (si un archivo falla, continúa con el siguiente).
- Reporta cantidad de tablas creadas y registros insertados.

---

### 02_staging_clean.py — Limpieza y Transformación de Datos

**Función principal:** Toma los datos crudos de `CentroMas_Staging`, aplica reglas de limpieza y calidad de datos, y los guarda en una base de staging intermedia `CentroMas_Staging_Clean`.

**Bases de datos que utiliza:**
- `master` (para crear/eliminar la base clean)
- `CentroMas_Staging` (origen de datos crudos)
- `CentroMas_Staging_Clean` (destino de datos limpios)

**Reglas de calidad de datos aplicadas:**

| Archivo      | Problema                        | Acción                                           |
|-------------|---------------------------------|--------------------------------------------------|
| `customers` | Género en código (`F`/`M`)     | Normaliza a `'Femenino'`/`'Masculino'`           |
| `customers` | Género inconsistente            | Infiere el género a partir del nombre del cliente |
| `customers` | Clientes duplicados             | Deduplicación por nombre + ciudad + provincia, conservando el de mayor edad |
| `customers` | Fecha de registro posterior a la primera compra | Corrige `registration_date` usando la fecha de la orden más antigua |
| `products`  | Unidades incorrectas            | Redondea `quantity` al entero superior si la unidad no es `kg` |

**Pasos internos:**

1. **Idempotencia** — Elimina y recrea `CentroMas_Staging_Clean`.
2. **Inicialización de Lookups** — Crea tablas auxiliares (`lkp_genero_codigos`, `lkp_diccionario_nombres`) para normalización de género.
3. **Productos** — Cruza con categorías, mapea `active_flag` a booleano.
4. **Sucursales** — Convierte tipos de fecha y superficie.
5. **Clientes (bloque principal):**
   - Normaliza género mediante lookups y diccionario de nombres.
   - Detecta y unifica duplicados, creando un `lookup_map_clientes` para reasignar órdenes.
6. **Órdenes/Ventas** — Reasigna `customer_id` al cliente sobreviviente. Corrige fechas de registro inválidas.
7. **Detalles de órdenes** — Aplica regla de unidades (redondeo para productos no pesables).
8. **Carga final** — Inserta todas las tablas limpias (`clean_products`, `clean_stores`, `clean_customers`, `clean_orders`, `clean_order_details`) con una marca temporal de ejecución.

**Particularidades:**
- Es el script más complejo del proceso.
- Es totalmente **idempotente** (recrea la base de datos limpia cada vez).
- Maneja la integridad referencial entre órdenes y clientes después de la deduplicación.

---

### 03_carga_dw.py — Carga Final del Data Warehouse

**Función principal:** Puebla las tablas del Data Warehouse (`CentroMas_DW`) con los datos limpios provenientes de `CentroMas_Staging_Clean`.

**Bases de datos que utiliza:**
- `CentroMas_Staging_Clean` (origen de datos limpios)
- `CentroMas_DW` (destino final)

**Pasos internos:**

1. **Limpieza de tablas del DW (idempotencia)** — Vacía todas las tablas del DW y resetea los contadores `IDENTITY` de las dimensiones.
2. **Carga de Dim_Tiempo** — Genera un calendario continuo desde la fecha de la orden más antigua hasta la más reciente. Calcula `sk_tiempo` como `YYYYMMDD`, `dia_nro`, `mes_nro`, `anio_nro` y `temporada` (Verano/Otoño/Invierno/Primavera).
3. **Carga de Dim_Sucursal** — Inserta sucursales desde `clean_stores` con `es_actual = 1`.
4. **Carga de Dim_Producto** — Inserta productos desde `clean_products` con `es_actual = 1`.
5. **Carga de Dim_Cliente** — Calcula la edad a partir de la fecha de nacimiento y carga los clientes deduplicados.
6. **Carga de Fact_Venta (mapeo seguro de claves)** — Para cada detalle de orden, resuelve las claves sustitutas (*surrogate keys*) reales del DW mediante joins con las dimensiones:
   - `sk_sucursal` → lookup por `id_sucursal_bk`
   - `sk_producto` → lookup vía `sku` en `clean_products`
   - `sk_cliente` → lookup vía `customer_code` en `clean_customers`
   - `sk_tiempo` → calculado desde la fecha de la orden

**Particularidades:**
- **Totalmente idempotente**: puede ejecutarse múltiples veces.
- Utiliza **mapeo seguro** de claves sustitutas leyendo los IDs reales desde el DW (no asume valores).
- Es compatible con **SCD Tipo 2** (dimensiones incluyen `fecha_inicio`, `fecha_fin`, `es_actual`) para futuras cargas incrementales.

---

## Ejecución Completa (Paso a Paso)

```bash
# 1. Configurar la conexión (se ejecuta automáticamente si no existe db_config.json)
#    O manualmente: python db_conexion.py

# 2. Crear el Data Warehouse
python 00_crear_dw.py

# 3. Cargar datos crudos al staging (solicitará la ruta de los CSV)
python 01_staging_area.py

# 4. Limpiar y transformar datos
python 02_staging_clean.py

# 5. Cargar el DW con datos limpios
python 03_carga_dw.py
```

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

**Volumen de datos resultante:**
- Aproximadamente **23.410 registros** en la tabla de hechos `Fact_Venta`
- **4 dimensiones** pobladas con datos limpios y deduplicados