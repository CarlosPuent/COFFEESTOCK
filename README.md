# ☕ CoffeeStock

Sistema de gestión para cafeterías construido con Django: control de inventario de
insumos, catálogo de productos con receta (consumo de insumos por unidad vendida),
punto de venta (POS) con descuento automático de stock, registro de mermas,
alertas de stock bajo por correo (SendGrid) y un dashboard con indicadores clave
(ventas de los últimos 7 días, productos más vendidos, mermas por causa).

El sistema maneja dos roles con permisos diferenciados mediante grupos de Django:

- **Administrador**: gestiona insumos, productos, mermas, y accede al dashboard.
- **Cajero**: opera el punto de venta (POS) y registra mermas durante su turno.

## Requisitos previos

- Python 3.11+
- SQL Server (local o remoto) accesible, con el [ODBC Driver 17 for SQL Server](https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server) instalado
- Una cuenta de [SendGrid](https://sendgrid.com/) (opcional, solo si quieres probar las alertas de stock por correo)

## Instalación paso a paso

### 1. Clonar el repositorio y crear el entorno virtual

```bash
git clone <url-del-repositorio>
cd coffeeStock
python -m venv venv
```

Activar el entorno virtual:

```bash
# Windows (PowerShell)
venv\Scripts\Activate.ps1

# Windows (Git Bash / cmd)
source venv/Scripts/activate

# Linux / macOS
source venv/bin/activate
```

### 2. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 3. Configurar variables de entorno

Copia el archivo de ejemplo y complétalo con tus propios valores:

```bash
cp .env.example .env
```

Variables disponibles en `.env`:

| Variable | Descripción |
|---|---|
| `DB_NAME` | Nombre de la base de datos en SQL Server (ej. `CoffeeStockDB`). |
| `DB_HOST` | Servidor SQL Server. Puede incluir el nombre de instancia, ej. `SERVIDOR\SQLEXPRESS`. |
| `DB_PORT` | Puerto de SQL Server. Opcional: déjalo vacío para usar el puerto por defecto. |
| `DB_USER` | Usuario de SQL Authentication. **Déjalo vacío junto con `DB_PASSWORD` para usar Windows Authentication** (`Trusted_Connection`). |
| `DB_PASSWORD` | Contraseña de SQL Authentication. Debe ir junto con `DB_USER`; si cualquiera de los dos queda vacío, se usa Windows Authentication. |
| `SENDGRID_API_KEY` | API key de SendGrid, usada para enviar las alertas de stock bajo. Si se deja vacía, los envíos fallarán silenciosamente y solo quedará el registro `WARNING` en la consola (no rompe la aplicación). |
| `SENDGRID_FROM_EMAIL` | Correo remitente verificado en SendGrid para las alertas de stock. |
| `SENDGRID_ADMIN_EMAIL` | Correo del administrador que recibe las alertas de stock bajo. |

> El archivo `.env` nunca debe subirse al repositorio (ya está en `.gitignore`).

### 4. Aplicar las migraciones

```bash
python manage.py migrate
```

### 5. Crear los grupos de permisos (Administrador / Cajero)

```bash
python manage.py create_groups
```

Crea (o actualiza) los grupos `Administrador` (permisos completos sobre Insumo,
Producto, RecetaInsumo y Merma) y `Cajero` (permisos de alta/consulta sobre
Venta, DetalleVenta y Merma).

### 6. Crear los usuarios de prueba

```bash
python manage.py create_test_users
```

Crea (o actualiza) dos usuarios y los asigna a su grupo correspondiente:

| Usuario | Contraseña | Grupo | Acceso |
|---|---|---|---|
| `cajero1` | `Cajero123!` | Cajero | Punto de venta (POS) y registro de mermas |
| `admin_coffeestock` | `Admin123!` | Administrador | Dashboard, Insumos, Productos, Mermas |

### 7. (Opcional) Sembrar datos de ejemplo

Para tener insumos, productos con receta, ventas de los últimos 7 días y mermas
de ejemplo listos para explorar el POS y el dashboard sin partir de cero:

```bash
python manage.py seed_demo_data
```

- Si ya existen datos, el comando pedirá confirmación antes de continuar (para
  no duplicar información sin querer).
- Para limpiar los datos existentes (insumos, productos, recetas, ventas y
  mermas) y volver a sembrar desde cero, sin que se pida confirmación:

  ```bash
  python manage.py seed_demo_data --reset
  ```

### 8. Ejecutar el servidor de desarrollo

```bash
python manage.py runserver
```

La aplicación queda disponible en `http://127.0.0.1:8000/`:

- `/login/` — inicio de sesión (redirige automáticamente al POS o al dashboard según el rol del usuario).
- `/pos/` — punto de venta (rol Cajero o Administrador).
- `/dashboard/` — panel de administración (rol Administrador).
- `/admin/` — administración nativa de Django (requiere `createsuperuser` aparte si se desea usar).

## Estructura del proyecto

- `core` — modelos de dominio (Insumo, Producto, RecetaInsumo, Merma, Venta,
  DetalleVenta), autenticación, mixins compartidos, comandos de management y el
  servicio de alertas de stock por correo.
- `pos` — punto de venta: selección de productos, carrito en el frontend y
  confirmación de venta con descuento de stock transaccional.
- `dashboard` — panel de administración: CRUD de Insumos y Productos,
  registro/listado de Mermas, y el dashboard con gráficos (Chart.js).
