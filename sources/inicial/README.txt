Dataset CSV para ETL – Cadena de Supermercados
=====================================================

Descripción
-----------
Conjunto de archivos CSV relacionales, inspirado en un esquema OLTP tipo retail/supermercado.
Sirve para practicar procesos ETL, staging, integración y carga a un DW sin depender de un motor específico.

Importante
----------
- Es un dataset de ejemplo con estructura transaccional realista.
- Está inspirado en modelos tipo Northwind / retail.
- No proviene de una cadena real de supermercados.
- Cantidad de registros:
  * stores: 8
  * categories: 8
  * suppliers: 10
  * products: 31
  * customers: 120
  * employees: 40
  * payment_methods: 4
  * promotions: 5
  * orders: 4716
  * order_details: 23410

Relaciones principales
----------------------
- products.category_id -> categories.category_id
- products.supplier_id -> suppliers.supplier_id
- employees.store_id -> stores.store_id
- orders.store_id -> stores.store_id
- orders.customer_id -> customers.customer_id
- orders.employee_id -> employees.employee_id
- orders.payment_method_id -> payment_methods.payment_method_id
- orders.promotion_id -> promotions.promotion_id
- order_details.order_id -> orders.order_id
- order_details.product_id -> products.product_id

Sugerencia de flujo ETL
-----------------------
1. Cargar maestros: stores, categories, suppliers, products, customers, employees, payment_methods, promotions
2. Cargar transacciones: orders
3. Cargar detalle: order_details
4. Crear dimensiones:
   - dim_fecha
   - dim_producto
   - dim_cliente
   - dim_sucursal
   - dim_empleado
   - dim_medio_pago
   - dim_promocion
5. Crear fact_ventas a nivel línea de venta

Granularidad recomendada del hecho
----------------------------------
Una fila por línea de venta (order_details), enriquecida con los datos del encabezado (orders).

Posibles métricas
-----------------
- quantity
- gross_amount
- discount_amount
- net_amount
- ticket_count
- unit_price

Posibles análisis
-----------------
- Ventas por mes, sucursal y categoría
- Ranking de productos por región
- Ticket promedio por cliente
- Impacto de descuentos en volumen y facturación
