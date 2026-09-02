# ☕ CoffeeStock

Sistema de gestión para cafeterías construido con Django. Cubre el ciclo completo
de operación de una cafetería: inventario de insumos, catálogo de productos con
receta, punto de venta, control de mermas, alertas de stock bajo y reportes.

## Módulos

- **Punto de venta (POS)**: selección de productos por categoría, carrito en el
  frontend y confirmación de venta. Al confirmar, cada `Producto` vendido
  descuenta automáticamente el stock de sus insumos según su receta
  (`RecetaInsumo`), dentro de una transacción atómica con bloqueo de fila
  (`select_for_update`) para evitar condiciones de carrera.
- **Gestión de insumos, productos y recetas**: CRUD completo de `Insumo` y
  `Producto`, con un formset inline para asociar los insumos y cantidades que
  componen la receta de cada producto.
- **Registro de mermas**: da de baja stock por caducidad, mala preparación u
  otra causa, descontándolo del insumo correspondiente de la misma forma que
  una venta (atómico, con bloqueo de fila).
- **Alertas automáticas de stock bajo**: cuando el stock de un insumo cae por
  debajo de su mínimo (por una venta o una merma), el sistema envía un correo
  por SendGrid al administrador, con un cooldown de 24 horas para no reenviar
  la misma alerta repetidamente. Si el envío falla o SendGrid no está
  configurado, el insumo queda marcado con `alerta_pendiente=True` como
  respaldo visual en el dashboard (ver variables de entorno más abajo).
- **Dashboard**: gráficos (Chart.js) de ventas de los últimos 7 días, top 5
  productos más vendidos (últimos 30 días) y mermas del mes por causa, además
  de las tarjetas de alerta de insumos con stock bajo.
- **Historial de ventas**: listado de todas las ventas con filtros por cajero y
  rango de fecha, y vista de detalle con los productos vendidos en cada una.

### Roles

El sistema usa dos grupos de Django con permisos y accesos diferenciados:

- **Cajero**: opera el punto de venta (`/pos/`) y puede registrar mermas
  durante su turno.
- **Administrador**: gestiona insumos, productos, mermas, ventas y accede al
  dashboard (todo bajo `/dashboard/`), además de poder registrar mermas y usar
  el POS.

Al iniciar sesión, cada usuario es redirigido automáticamente según su grupo.

## Requisitos previos

- Python 3.11+
- SQL Server (local o remoto) accesible, con el [ODBC Driver 17 for SQL Server](https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server) instalado
- Una cuenta de [SendGrid](https://sendgrid.com/) (opcional, solo si quieres probar el envío real de alertas de stock por correo)

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

Variables disponibles en `.env` (ver `.env.example`):

| Variable | Descripción |
|---|---|
| `DB_NAME` | Nombre de la base de datos en SQL Server (ej. `CoffeeStockDB`). |
| `DB_HOST` | Servidor SQL Server. Puede incluir el nombre de instancia, ej. `SERVIDOR\SQLEXPRESS`. |
| `DB_PORT` | Puerto de SQL Server. Opcional: déjalo vacío para usar el puerto por defecto. |
| `DB_USER` | Usuario de SQL Authentication. |
| `DB_PASSWORD` | Contraseña de SQL Authentication. |
| `SENDGRID_API_KEY` | API key de SendGrid, usada para enviar las alertas de stock bajo. |
| `SENDGRID_FROM_EMAIL` | Correo remitente verificado en SendGrid para las alertas de stock. |
| `SENDGRID_ADMIN_EMAIL` | Correo del administrador que recibe las alertas de stock bajo. |

**Windows Authentication vs. SQL Authentication**: si `DB_USER` y `DB_PASSWORD`
están **ambos** completos, la conexión usa SQL Authentication con esas
credenciales. Si **cualquiera de los dos** queda vacío, el sistema usa
automáticamente Windows Authentication (`Trusted_Connection=yes`) contra el
`DB_HOST` indicado, sin enviar usuario ni contraseña.

**Si no configuras SendGrid** (dejas `SENDGRID_API_KEY` vacío): el sistema
sigue funcionando con normalidad. El intento de envío falla silenciosamente
(se registra un `WARNING` en la consola del servidor, sin romper la venta ni
la merma que lo disparó) y el insumo simplemente queda con
`alerta_pendiente=True`, visible como tarjeta de alerta en el dashboard. El
correo es un canal adicional, no un requisito para que el control de stock
funcione.

> El archivo `.env` nunca debe subirse al repositorio (ya está en `.gitignore`).

### 4. Aplicar las migraciones

```bash
python manage.py migrate
```

### 5. Crear un superusuario

```bash
python manage.py createsuperuser
```

Este superusuario es el único con acceso al panel `/admin/` de Django para
gestionar cuentas y contraseñas (ver [Gestión de usuarios y
contraseñas](#gestión-de-usuarios-y-contraseñas) más abajo). No pertenece por
sí solo a los grupos Cajero/Administrador del negocio.

### 6. Crear los grupos de permisos (Administrador / Cajero)

```bash
python manage.py create_groups
```

Crea (o actualiza) los grupos `Administrador` (permisos completos —
add/change/delete/view— sobre `Insumo`, `Producto`, `RecetaInsumo` y `Merma`)
y `Cajero` (permisos de alta/consulta —add/view— sobre `Venta`, `DetalleVenta`
y `Merma`).

### 7. Crear los usuarios de prueba

```bash
python manage.py create_test_users
```

Crea (o actualiza) dos usuarios y los asigna a su grupo correspondiente:

| Usuario | Contraseña | Grupo | Acceso |
|---|---|---|---|
| `cajero1` | `Cajero123!` | Cajero | Punto de venta (`/pos/`) y registro de mermas |
| `admin_coffeestock` | `Admin123!` | Administrador | Dashboard, Insumos, Productos, Mermas, Ventas (`/dashboard/`) |

### 8. (Opcional) Sembrar datos de ejemplo

Para tener insumos, productos con receta, ventas de los últimos 7 días y
mermas de ejemplo listos para explorar el POS y el dashboard sin partir de
cero:

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

### 9. Ejecutar el servidor de desarrollo

```bash
python manage.py runserver
```

La aplicación queda disponible en `http://127.0.0.1:8000/`:

- `/` — vista raíz: redirige automáticamente al POS o al dashboard según el rol del usuario autenticado (o al login si no hay sesión).
- `/login/` — inicio de sesión.
- `/pos/` — punto de venta (rol Cajero o Administrador).
- `/dashboard/` — panel de administración: dashboard, Insumos, Productos, Mermas y Ventas (rol Administrador).
- `/admin/` — administración nativa de Django (solo superusuarios, ver abajo).

## Gestión de usuarios y contraseñas

El sistema separa dos niveles de administración:

- **`/admin/`** (panel nativo de Django): solo accesible para un
  **superusuario** creado con `python manage.py createsuperuser`. Desde ahí se
  gestionan las cuentas de usuario del sistema (crear/editar/desactivar
  usuarios de Cajero o Administrador, cambiar contraseñas, asignar grupos,
  etc.). Los usuarios de negocio (`cajero1`, `admin_coffeestock` o cualquier
  otro que se cree) no tienen permisos para administrar otras cuentas desde
  ahí.
- **`/dashboard/` y `/pos/`**: son las pantallas de uso diario para los roles
  Administrador y Cajero respectivamente, protegidas por grupo
  (`GroupRequiredMixin`), sin acceso a la gestión de usuarios.

## Estructura del proyecto

- **`core`** — modelos de dominio compartidos por todo el sistema (`Insumo`,
  `Producto`, `RecetaInsumo`, `Merma`, `Venta`, `DetalleVenta`), autenticación
  (login/logout, vista raíz de redirección por grupo), el mixin
  `GroupRequiredMixin` reutilizado por `pos` y `dashboard`, el servicio de
  alertas de stock por correo (`core/services/alertas.py`) y los comandos de
  management (`create_groups`, `create_test_users`, `seed_demo_data`).
- **`pos`** — punto de venta: selección de productos, carrito en el frontend
  (JavaScript) y confirmación de venta con descuento de stock transaccional
  según receta.
- **`dashboard`** — panel de administración: CRUD de Insumos y Productos (con
  formset de receta), registro y listado de Mermas, historial de Ventas con
  filtros y detalle, y el dashboard con gráficos (Chart.js) e indicadores de
  stock.

## Antes de un uso real

Las credenciales de los usuarios de prueba (`cajero1` / `Cajero123!` y
`admin_coffeestock` / `Admin123!`) son solo para desarrollo y demostración.
**Cámbialas antes de usar el sistema en producción**, de cualquiera de estas
formas:

- Por línea de comandos:

  ```bash
  python manage.py changepassword cajero1
  python manage.py changepassword admin_coffeestock
  ```

- Desde `/admin/`, iniciando sesión como superusuario: **Usuarios** → elegir
  el usuario → *This form does not let you change the password* → seguir el
  enlace para establecer una nueva contraseña.
