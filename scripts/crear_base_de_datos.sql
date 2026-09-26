/*
  CoffeeStock - preparación de SQL Server

  Cómo usarlo:
    - SQL Server Management Studio (SSMS) o Azure Data Studio: abre este
      archivo (o pega su contenido en "New Query") y presiona Execute (F5).
    - Terminal: sqlcmd -S localhost\SQLEXPRESS -E -C -i scripts\crear_base_de_datos.sql
      (-E = Windows Authentication; con usuario SQL usa -U sa -P "tu_clave")

  Se puede ejecutar varias veces sin problema: si algo ya existe, lo salta.
  Las TABLAS no se crean aquí: las crea Django con "python manage.py migrate".
*/

-- 1) Base de datos (OBLIGATORIO)
IF DB_ID(N'CoffeeStockDB') IS NULL
    CREATE DATABASE CoffeeStockDB;
GO

/*
  2) Usuario SQL para la aplicación (OPCIONAL)

  Solo si vas a conectarte con SQL Authentication (DB_USER / DB_PASSWORD en
  el .env). Si usas Windows Authentication puedes ignorar esta parte.
  Si cambias la contraseña aquí, pon la misma en DB_PASSWORD.
*/
IF NOT EXISTS (SELECT 1 FROM sys.server_principals WHERE name = N'coffeestock_app')
    CREATE LOGIN coffeestock_app WITH PASSWORD = N'CoffeeStock_2026!', CHECK_POLICY = OFF;
GO

-- Permite que "python manage.py test" cree su base temporal de pruebas.
ALTER SERVER ROLE dbcreator ADD MEMBER coffeestock_app;
GO

USE CoffeeStockDB;
GO

IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = N'coffeestock_app')
    CREATE USER coffeestock_app FOR LOGIN coffeestock_app;
GO

ALTER ROLE db_owner ADD MEMBER coffeestock_app;
GO

PRINT 'Listo: base de datos CoffeeStockDB preparada.';
GO
