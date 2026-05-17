from sqlalchemy import create_engine, text
from db_conexion import obtener_uris  # Importamos tu nuevo módulo central

def create_database(master_uri, db_name):
    print(f"\n[*] Conectando a master para inicializar la base de datos...")
    engine_master = create_engine(master_uri, isolation_level="AUTOCOMMIT")
    
    with engine_master.connect() as conn:
        check_db = conn.execute(text(f"SELECT name FROM sys.databases WHERE name = '{db_name}'")).fetchone()
        if not check_db:
            print(f"[*] Creando la base de datos '{db_name}'...")
            conn.execute(text(f"CREATE DATABASE {db_name}"))
        else:
            print(f"[*] La base de datos '{db_name}' ya existe.")

def build_data_warehouse(dw_uri):
    print(f"\n[*] Conectando a CentroMas_DW para crear el esquema...")
    engine_dw = create_engine(dw_uri, isolation_level="AUTOCOMMIT")
    
    queries = {
        "1. Limpieza previa (Drop Constraints)": """
            IF OBJECT_ID('dbo.Fact_Venta', 'U') IS NOT NULL
            BEGIN
               IF EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name = 'FK_Fact_Venta_Tiempo')
                   ALTER TABLE dbo.Fact_Venta DROP CONSTRAINT FK_Fact_Venta_Tiempo;
               IF EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name = 'FK_Fact_Venta_Cliente')
                   ALTER TABLE dbo.Fact_Venta DROP CONSTRAINT FK_Fact_Venta_Cliente;
               IF EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name = 'FK_Fact_Venta_Producto')
                   ALTER TABLE dbo.Fact_Venta DROP CONSTRAINT FK_Fact_Venta_Producto;
               IF EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name = 'FK_Fact_Venta_Sucursal')
                   ALTER TABLE dbo.Fact_Venta DROP CONSTRAINT FK_Fact_Venta_Sucursal;
            END
        """,
        "2. Limpieza previa (Drop Tables)": """
            DROP TABLE IF EXISTS dbo.Fact_Venta;
            DROP TABLE IF EXISTS dbo.Dim_Cliente;
            DROP TABLE IF EXISTS dbo.Dim_Producto;
            DROP TABLE IF EXISTS dbo.Dim_Sucursal;
            DROP TABLE IF EXISTS dbo.Dim_Tiempo;
        """,
        "3. Creación Dim_Tiempo": """
            CREATE TABLE dbo.Dim_Tiempo (
               sk_tiempo       INT          PRIMARY KEY,
               fecha_completa  DATE         NOT NULL,
               dia_nro         INT          NOT NULL,
               mes_nro         INT          NOT NULL,
               temporada       VARCHAR(20)  NOT NULL,
               anio_nro        INT          NOT NULL
            );
        """,
        "4. Creación Dim_Sucursal": """
            CREATE TABLE dbo.Dim_Sucursal (
               sk_sucursal         INT IDENTITY(1,1) PRIMARY KEY,
               id_sucursal_bk      INT             NOT NULL,
               superficie_m2       DECIMAL(10,2)   NOT NULL,
               ciudad_sucursal     VARCHAR(100)    NOT NULL,
               provincia_sucursal  VARCHAR(50)     NOT NULL,
               fecha_inicio        DATE            NOT NULL,
               fecha_fin           DATE            NULL,
               es_actual           BIT             NOT NULL DEFAULT 1
            );
        """,
        "5. Creación Dim_Producto": """
            CREATE TABLE dbo.Dim_Producto (
               sk_producto         INT IDENTITY(1,1) PRIMARY KEY,
               id_producto_bk      VARCHAR(8)      NOT NULL,
               producto_nombre     VARCHAR(150)    NOT NULL,
               marca_nombre        VARCHAR(100)    NOT NULL,
               categoria_nombre    VARCHAR(100)    NOT NULL,
               costo_unidad        DECIMAL(12,2)   NOT NULL,
               precio_lista        DECIMAL(12,2)   NOT NULL,
               fecha_inicio        DATE            NOT NULL,
               fecha_fin           DATE            NULL,
               es_actual           BIT             NOT NULL DEFAULT 1
            );
        """,
        "6. Creación Dim_Cliente": """
            CREATE TABLE dbo.Dim_Cliente (
               sk_cliente      INT IDENTITY(1,1) PRIMARY KEY,
               id_cliente_bk   VARCHAR(10)     NOT NULL,
               genero          VARCHAR(20)     NOT NULL DEFAULT 'No Informado',
               edad            INT             NULL,
               tipo_cliente    VARCHAR(50)     NOT NULL,
               ciudad_cliente  VARCHAR(100)    NOT NULL DEFAULT 'No Informado',
               provincia_cliente VARCHAR(100)   NOT NULL DEFAULT 'No Informado',
               fecha_inicio    DATE            NOT NULL,
               fecha_fin       DATE            NULL,
               es_actual       BIT             NOT NULL DEFAULT 1
            );
        """,
        "7. Creación Fact_Venta": """
            CREATE TABLE dbo.Fact_Venta (
               sk_venta            INT IDENTITY(1,1) PRIMARY KEY,
               sk_tiempo           INT             NOT NULL,
               sk_cliente          INT             NOT NULL,
               sk_producto         INT             NOT NULL,
               sk_sucursal         INT             NOT NULL,
               nro_ticket          INT             NOT NULL,
               cantidad_vendida    DECIMAL(10,2)   NOT NULL CHECK (cantidad_vendida > 0),
               precio_unitario     DECIMAL(12,2)   NOT NULL,
               monto_bruto         DECIMAL(12,2)   NOT NULL,
               descuento_aplicado  DECIMAL(12,2)   NOT NULL DEFAULT 0,
               monto_neto          DECIMAL(12,2)   NOT NULL,
               last_updated        DATETIME        NOT NULL DEFAULT GETDATE(),
               row_hash            VARCHAR(32)     NOT NULL,
               CONSTRAINT FK_Fact_Venta_Tiempo    FOREIGN KEY (sk_tiempo)    REFERENCES dbo.Dim_Tiempo(sk_tiempo),
               CONSTRAINT FK_Fact_Venta_Cliente   FOREIGN KEY (sk_cliente)   REFERENCES dbo.Dim_Cliente(sk_cliente),
               CONSTRAINT FK_Fact_Venta_Producto  FOREIGN KEY (sk_producto)  REFERENCES dbo.Dim_Producto(sk_producto),
               CONSTRAINT FK_Fact_Venta_Sucursal  FOREIGN KEY (sk_sucursal)  REFERENCES dbo.Dim_Sucursal(sk_sucursal)
            );
        """,
        "8. Creación Fact_Venta_ChangeLog": """
            IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[Fact_Venta_ChangeLog]') AND type in (N'U'))
            BEGIN
                CREATE TABLE dbo.Fact_Venta_ChangeLog (
                    id_cambio       INT IDENTITY(1,1) PRIMARY KEY,
                    nro_ticket      INT             NOT NULL,
                    tipo_cambio     VARCHAR(10)     NOT NULL CHECK (tipo_cambio IN ('INSERT', 'UPDATE', 'DELETE')),
                    fecha_cambio    DATETIME        NOT NULL DEFAULT GETDATE(),
                    hash_anterior   VARCHAR(32)     NULL,
                    hash_nuevo      VARCHAR(32)     NULL,
                    ejecucion_etl   VARCHAR(100)    NOT NULL,
                    detalle         VARCHAR(MAX)    NULL
                );
            END
        """,
        "9. Creación ETL_Logs (Auditoría)": """
            IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[ETL_Logs]') AND type in (N'U'))
            BEGIN
                CREATE TABLE dbo.ETL_Logs (
                    id_log              INT IDENTITY(1,1) PRIMARY KEY,
                    fecha_carga         DATETIME        DEFAULT GETDATE(),
                    script_nombre       VARCHAR(100)    NOT NULL,
                    estado              VARCHAR(20)     NOT NULL,
                    filas_procesadas    INT             NOT NULL,
                    mensaje             VARCHAR(MAX)    NULL
                );
            END
        """
    }

    with engine_dw.connect() as conn:
        for step_name, query in queries.items():
            print(f"   -> Ejecutando: {step_name}...")
            conn.execute(text(query))
            
    print("\n[ÉXITO] Esquema físico creado correctamente. ¡El DW está listo para recibir datos!")

def main():
    try:
        master_uri, _, dw_uri = obtener_uris()
        create_database(master_uri, 'CentroMas_DW')
        build_data_warehouse(dw_uri)
    except Exception as e:
        print(f"\n[ERROR FATAL] Ocurrió un problema: {e}")

if __name__ == "__main__":
    main()