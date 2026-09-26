# ☕ CoffeeStock

Sistema de gestión para cafeterías hecho con Django y SQL Server: inventario de
insumos, productos con receta, punto de venta, mermas, alertas de stock bajo
por correo y un dashboard con reportes.

> **Estado:** Avance 1 de 2. Lo que falta para la entrega final está al final
> de este documento, en [Pendiente para el Avance 2](#pendiente-para-el-avance-2).

---

## Contenido

1. [Qué hace](#qué-hace)
2. [Qué necesitas instalar](#qué-necesitas-instalar)
3. [Preparar SQL Server](#paso-1-preparar-sql-server)
4. [Instalar el proyecto](#paso-2-descargar-el-proyecto-e-instalar-dependencias)
5. [Configurar el `.env`](#paso-3-crear-el-archivo-env)
6. [Crear tablas y datos de prueba](#paso-4-crear-las-tablas-y-cargar-datos-de-prueba)
7. [Levantar el sistema](#paso-5-levantar-el-sistema)
8. [Alertas por correo](#alertas-de-stock-bajo-por-correo)
9. [Problemas comunes](#problemas-comunes)
10. [Estructura del proyecto](#estructura-del-proyecto)
11. [Pendiente para el Avance 2](#pendiente-para-el-avance-2)

---

## Qué hace

| Módulo | Qué incluye |
|---|---|
| **Punto de venta** (`/pos/`) | Productos por categoría, buscador y carrito. Al confirmar la venta se descuentan automáticamente los insumos según la receta de cada producto, todo en una sola transacción. |
| **Insumos y productos** | Alta, edición y baja de insumos y productos. Cada producto tiene su receta (qué insumos usa y cuánto). |
| **Mermas** | Registro de pérdidas (caducidad, mala preparación, otro) que también descuentan stock. |
| **Alertas de stock bajo** | Cuando un insumo llega a su stock mínimo aparece una tarjeta roja en el dashboard y se envía un correo. Máximo un correo por insumo cada 24 horas. |
| **Dashboard** (`/dashboard/`) | Ventas de los últimos 7 días, top 5 de productos (30 días), mermas del mes por causa y alertas activas. |
| **Historial de ventas** | Listado con filtros por cajero y fechas, y detalle de cada venta. |

Hay dos roles:

- **Cajero**: usa el punto de venta y registra mermas.
- **Administrador**: todo lo anterior más el dashboard, inventario, productos,
  mermas y ventas.

Cada usuario cae en su pantalla automáticamente al iniciar sesión.

---

## Qué necesitas instalar

| Programa | Para qué | Dónde |
|---|---|---|
| **Python 3.12 o más nuevo** | Correr el proyecto (Django 6.1 no funciona con 3.11 o anteriores) | [python.org/downloads](https://www.python.org/downloads/). En Windows marca **"Add python.exe to PATH"** al instalar. |
| **Git** | Descargar el proyecto | [git-scm.com](https://git-scm.com/downloads) |
| **SQL Server** (cualquier edición) | La base de datos | Ver el paso 1 |
| **ODBC Driver 18 for SQL Server** (o el 17) | Que Python pueda hablar con SQL Server | [Descarga de Microsoft](https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server) |
| SQL Server Management Studio (SSMS) | Opcional, para ver la base de datos y correr el script | [Descarga de SSMS](https://learn.microsoft.com/sql/ssms/download-sql-server-management-studio-ssms) |

### Instalar Python en Windows

1. Entra a [python.org/downloads](https://www.python.org/downloads/) y
   descarga la versión más nueva (3.12 o mayor).
2. Abre el instalador y, **antes de darle a Install Now**, marca la casilla
   **"Add python.exe to PATH"** abajo de la ventana.
3. Cuando termine, **cierra todas las terminales** (PowerShell, CMD, VS Code)
   y abre una nueva. Las terminales que ya estaban abiertas no ven la
   instalación nueva.

También se puede instalar desde PowerShell con
`winget install Python.Python.3.13` (y luego cerrar y abrir la terminal).

Para comprobar que quedó bien, en la terminal nueva escribe:

```powershell
py --list
```

Tiene que aparecer una línea con `3.12` o más (por ejemplo `-V:3.13 *`). En
macOS/Linux usa `python3 --version`.

---

## Paso 1: Preparar SQL Server

Elige **una** de estas opciones. Si estás en Windows y no sabes cuál, usa la A.

### Opción A: SQL Server en Windows (Express, Developer o el que ya tengas)

1. Si no tienes SQL Server, instala
   [SQL Server Express o Developer](https://www.microsoft.com/sql-server/sql-server-downloads)
   (los dos son gratis). La instalación "Basic" está bien.
2. Abre **SSMS** y conéctate. Anota lo que dice en **Server name**, lo vas a
   necesitar para el `.env`. Suele ser algo como:
   - `localhost\SQLEXPRESS` (SQL Server Express)
   - `localhost` o `.` (Developer / Standard)
   - `(localdb)\MSSQLLocalDB` (LocalDB, el que trae Visual Studio)
3. En SSMS ve a **File → Open → File…** y abre
   `scripts/crear_base_de_datos.sql` de este proyecto (o copia su contenido en
   **New Query**). Presiona **Execute** (F5). Debe terminar con
   `Listo: base de datos CoffeeStockDB preparada.`

Ese script crea la base de datos `CoffeeStockDB` y, además, un usuario SQL
`coffeestock_app` con contraseña `CoffeeStock_2026!` por si prefieres
conectarte con usuario y contraseña. Las tablas **no** se crean aquí; las crea
Django en el paso 4.

**¿Windows Authentication o usuario y contraseña?**

- **Windows Authentication** (lo más fácil en Windows): no pones usuario ni
  contraseña en el `.env`. Entra con tu usuario de Windows, igual que SSMS.
- **SQL Authentication** (usuario `coffeestock_app` o `sa`): SQL Server tiene
  que tener activado el modo mixto. En SSMS: clic derecho sobre el servidor →
  **Properties** → **Security** → marca **SQL Server and Windows
  Authentication mode** → OK. Luego clic derecho sobre el servidor →
  **Restart**.

### Opción B: SQL Server en Docker (Windows, macOS o Linux)

Con [Docker Desktop](https://www.docker.com/products/docker-desktop/) abierto:

```bash
docker run -d --name coffeestock-sql -p 1433:1433 -e ACCEPT_EULA=Y -e 'MSSQL_SA_PASSWORD=CoffeeStock_2026!' mcr.microsoft.com/mssql/server:2022-latest
```

Espera unos 20 segundos a que arranque y ejecuta el script de la base de
datos (desde la carpeta del proyecto, después del paso 2):

```bash
docker exec -i coffeestock-sql /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P 'CoffeeStock_2026!' -C < scripts/crear_base_de_datos.sql
```

En el `.env` usarás `DB_HOST=localhost`, `DB_PORT=1433`, `DB_USER=sa` y
`DB_PASSWORD=CoffeeStock_2026!`.

> En Mac con chip Apple (M1/M2/M3…) activa en Docker Desktop:
> **Settings → General → Use Rosetta for x86/amd64 emulation**.
> En macOS/Linux también tienes que instalar el ODBC Driver 18 (ver tabla de
> arriba; en Mac es `brew install msodbcsql18`).

### Opción C: SQL Server remoto o en otra máquina

Solo necesitas el nombre o IP del servidor, un usuario con permiso para crear
la base de datos y que el puerto (normalmente 1433) esté abierto. Corre el
script con ese usuario y pon los datos en el `.env`.

---

## Paso 2: Descargar el proyecto e instalar dependencias

```bash
git clone https://github.com/CarlosPuent/COFFEESTOCK.git
cd COFFEESTOCK
```

Ahora crea el entorno virtual: una carpeta `venv` con las librerías del
proyecto, para no mezclarlas con las del resto de tu computadora. Son **dos
comandos distintos**: escribe el primero, presiona Enter, y luego el segundo.

**Windows (PowerShell)**

```powershell
py -m venv venv
```

```powershell
venv\Scripts\Activate.ps1
```

**Windows (CMD)**

```bat
py -m venv venv
```

```bat
venv\Scripts\activate.bat
```

**macOS / Linux**

```bash
python3 -m venv venv
```

```bash
source venv/bin/activate
```

Sabrás que funcionó porque la línea de la terminal empieza con `(venv)`, por
ejemplo `(venv) PS C:\COFFEESTOCK>`. Cada vez que abras una terminal nueva
para trabajar en el proyecto tienes que correr otra vez **solo el segundo
comando** (activar); el primero se hace una sola vez.

> Si PowerShell dice que "la ejecución de scripts está deshabilitada", corre
> una sola vez `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, responde
> `S` (o `Y`) y vuelve a correr el comando de activar.

> Si `py` dice **"No suitable Python runtime found"**, o `python` abre la
> Microsoft Store o dice **"no se encontró Python"**, es que Python no está
> instalado. Vuelve a [Qué necesitas instalar](#qué-necesitas-instalar),
> instálalo y **cierra y abre la terminal** antes de seguir.

Instala las dependencias:

```bash
pip install -r requirements.txt
```

---

## Paso 3: Crear el archivo `.env`

El `.env` guarda tu configuración local (datos de conexión, correo). No se
sube a GitHub. Copia el de ejemplo:

```bash
# Windows
copy .env.example .env

# macOS / Linux
cp .env.example .env
```

Ábrelo con cualquier editor (Bloc de notas, VS Code) y ajusta la parte de base
de datos. Ejemplos completos:

**SQL Server Express con Windows Authentication**

```ini
DB_NAME=CoffeeStockDB
DB_HOST=localhost\SQLEXPRESS
DB_PORT=
DB_USER=
DB_PASSWORD=
```

**SQL Server con el usuario que crea el script**

```ini
DB_NAME=CoffeeStockDB
DB_HOST=localhost\SQLEXPRESS
DB_PORT=
DB_USER=coffeestock_app
DB_PASSWORD=CoffeeStock_2026!
```

**Docker**

```ini
DB_NAME=CoffeeStockDB
DB_HOST=localhost
DB_PORT=1433
DB_USER=sa
DB_PASSWORD=CoffeeStock_2026!
```

En `ALERTA_EMAIL_DESTINATARIOS` pon tu correo. Por ahora deja
`ALERTA_EMAIL_PROVEEDOR=consola`; el envío real se configura más abajo en
[Alertas de stock bajo por correo](#alertas-de-stock-bajo-por-correo).

---

## Paso 4: Crear las tablas y cargar datos de prueba

Con el entorno virtual activo y desde la carpeta del proyecto, corre estos
comandos en orden:

```bash
python manage.py migrate
python manage.py create_groups
python manage.py create_test_users
python manage.py seed_demo_data
```

| Comando | Qué hace |
|---|---|
| `migrate` | Crea todas las tablas en `CoffeeStockDB`. Si falla aquí, es un problema de conexión: ver [Problemas comunes](#problemas-comunes). |
| `create_groups` | Crea los roles Administrador y Cajero con sus permisos. |
| `create_test_users` | Crea los usuarios de prueba (tabla de abajo). |
| `seed_demo_data` | Carga 10 insumos, 8 productos con receta, ventas de la última semana y algunas mermas. Dos insumos quedan a propósito bajo el mínimo para que veas las alertas. Si ya había datos te pregunta antes de seguir; con `--reset` borra lo anterior y vuelve a cargar. |

Usuarios de prueba:

| Usuario | Contraseña | Rol | Entra a |
|---|---|---|---|
| `admin_coffeestock` | `Admin123!` | Administrador | Dashboard, inventario, productos, mermas, ventas |
| `cajero1` | `Cajero123!` | Cajero | Punto de venta y registro de mermas |

Opcional: `python manage.py createsuperuser` crea una cuenta para el panel
`/admin/` de Django, desde donde se gestionan usuarios y contraseñas.

---

## Paso 5: Levantar el sistema

```bash
python manage.py runserver
```

Abre **http://127.0.0.1:8000/** y entra con uno de los usuarios de prueba.
Para detener el servidor presiona `Ctrl + C` en la terminal.

| Ruta | Qué es |
|---|---|
| `/` | Te manda al POS o al dashboard según tu rol |
| `/pos/` | Punto de venta |
| `/dashboard/` | Panel del administrador |
| `/admin/` | Admin de Django (solo superusuario) |

---

## Alertas de stock bajo por correo

### Cómo funciona

1. Una venta, una merma o una edición manual deja un insumo **en o por
   debajo** de su stock mínimo.
2. El insumo se marca como alerta (tarjeta roja en el dashboard).
3. Cuando la operación se guarda, se envía un correo a todos los que estén en
   `ALERTA_EMAIL_DESTINATARIOS`.
4. Ese insumo no vuelve a mandar correo en 24 horas. Si lo reabasteces (lo
   editas con stock por encima del mínimo) la alerta se limpia y la próxima
   caída avisa de inmediato.

Si el correo no se puede enviar, la venta o la merma **no** se cancela: el
error queda escrito en la terminal donde corre `runserver` y la tarjeta roja
del dashboard sigue ahí.

### Quién recibe las alertas

Cualquier persona. Solo cambia esta línea del `.env` (acepta varios correos
separados por coma) y reinicia `runserver`:

```ini
ALERTA_EMAIL_DESTINATARIOS=ana@gmail.com,luis@outlook.com
```

### Cómo se envían

Hay tres modos, se elige con `ALERTA_EMAIL_PROVEEDOR`:

| Modo | Cuándo usarlo | Qué necesitas |
|---|---|---|
| `consola` | Para probar sin cuentas. El correo se imprime en la terminal de `runserver`, no llega a ningún buzón. | Nada |
| `smtp` | La forma más sencilla de recibir correos reales. | Una cuenta de Gmail (u Outlook, etc.) |
| `sendgrid` | Si ya tienes cuenta de SendGrid. | API key y un remitente verificado |

#### Opción SMTP con Gmail

1. En tu cuenta de Google activa la
   [verificación en dos pasos](https://myaccount.google.com/signinoptions/twosv).
2. Entra a [Contraseñas de aplicaciones](https://myaccount.google.com/apppasswords),
   crea una (el nombre da igual, por ejemplo "CoffeeStock") y copia la clave
   de 16 letras.
3. En el `.env`:

   ```ini
   ALERTA_EMAIL_PROVEEDOR=smtp
   ALERTA_EMAIL_DESTINATARIOS=quien_recibe@gmail.com
   EMAIL_HOST=smtp.gmail.com
   EMAIL_PORT=587
   EMAIL_USE_TLS=True
   EMAIL_HOST_USER=tu_cuenta@gmail.com
   EMAIL_HOST_PASSWORD=abcdefghijklmnop
   ```

   `EMAIL_HOST_USER` es la cuenta que **envía**; `ALERTA_EMAIL_DESTINATARIOS`
   es quien **recibe**. Pueden ser la misma o distintas. La clave va sin
   espacios.

Para Outlook/Hotmail usa `EMAIL_HOST=smtp-mail.outlook.com` (algunas cuentas
de Microsoft tienen SMTP deshabilitado; en ese caso Gmail es lo más fácil).

#### Opción SendGrid

En SendGrid hay dos correos distintos y es donde normalmente se rompe todo:

- **Remitente** (`SENDGRID_FROM_EMAIL`): el correo que aparece como "De:". Tiene
  que estar **verificado dentro de tu cuenta de SendGrid**. No se cambia por
  otra persona.
- **Destinatario** (`ALERTA_EMAIL_DESTINATARIOS`): quien recibe. Puede ser
  cualquiera, no necesita cuenta en SendGrid.

Pasos:

1. Crea la cuenta en [sendgrid.com](https://sendgrid.com/).
2. **Settings → Sender Authentication → Verify a Single Sender**. Pon tu
   correo y confirma el enlace que te llega. Ese es tu remitente.
3. **Settings → API Keys → Create API Key**, con permiso **Mail Send** (o
   Full Access). Copia la clave, empieza con `SG.` y solo se muestra una vez.
4. En el `.env`:

   ```ini
   ALERTA_EMAIL_PROVEEDOR=sendgrid
   ALERTA_EMAIL_DESTINATARIOS=quien_recibe@gmail.com
   SENDGRID_API_KEY=SG.xxxxxxxxxxxxxxxx
   SENDGRID_FROM_EMAIL=el_correo_que_verificaste@gmail.com
   ```

> **Por qué no llegaban las alertas antes:** si en `SENDGRID_FROM_EMAIL` se
> pone un correo que no está verificado en esa cuenta de SendGrid (por
> ejemplo, el de otra persona para que "le lleguen a ella"), SendGrid rechaza
> todos los envíos con error 403 y no llega nada, ni a spam. Para que le
> lleguen a otra persona se cambia `ALERTA_EMAIL_DESTINATARIOS`, no el
> remitente. Además, la versión anterior no mostraba el motivo del error.

Los `.env` viejos que usan `SENDGRID_ADMIN_EMAIL` siguen funcionando: se toma
como destinatario si `ALERTA_EMAIL_DESTINATARIOS` está vacío.

### Probar que el correo funciona

```bash
python manage.py probar_correo
```

Muestra la configuración que está leyendo, manda un correo de prueba y, si
falla, dice exactamente por qué (API key inválida, remitente no verificado,
contraseña de Gmail rechazada, sin internet, etc.). Para mandarlo a otra
dirección sin tocar el `.env`:

```bash
python manage.py probar_correo --para alguien@gmail.com
```

El dashboard también muestra arriba si las alertas están configuradas y a
quién se están enviando.

### Probar una alerta real dentro del sistema

1. Entra como `admin_coffeestock`.
2. Ve a **Mermas → Registrar merma**, elige **Sirope de caramelo**, cantidad
   `10`, cualquier causa, y guarda.
3. Ese insumo ya estaba bajo el mínimo, así que se envía la alerta. Revisa tu
   bandeja (y Spam/Promociones) o la terminal si estás en modo `consola`.

Recuerda el límite de un correo por insumo cada 24 horas. Para repetir la
prueba con el mismo insumo, edítalo en **Insumos** con un stock mayor al mínimo
(eso reinicia el contador) y registra otra merma que lo deje abajo.

### Si llegan a spam

Con Gmail por SMTP casi siempre llegan a la bandeja normal. Con SendGrid usando
un remitente `@gmail.com` es común que caigan en Spam o Promociones, porque
Gmail no puede comprobar que SendGrid tiene permiso de enviar a nombre de
gmail.com. Para un uso real, SendGrid recomienda **Domain Authentication** con
un dominio propio.

---

## Problemas comunes

| Error o síntoma | Causa y solución |
|---|---|
| `No suitable Python runtime found`, o `python` abre la Microsoft Store / dice "no se encontró Python" | Python no está instalado (o se instaló con la terminal abierta). Ver [Instalar Python en Windows](#instalar-python-en-windows) y abre una terminal nueva. |
| `No matching distribution found for Django==6.1` al instalar | Tu Python es 3.11 o anterior. Instala 3.12+, borra la carpeta `venv` y vuelve a crearla con `py -m venv venv`. |
| `Can't open lib 'ODBC Driver 18 for SQL Server'` o `Data source name not found` | Falta el ODBC Driver. Instala el 18 (o el 17). Si tienes otro, ponlo en `DB_DRIVER` en el `.env`. |
| `Login timeout expired` / `Named Pipes Provider: Could not open a connection` | `DB_HOST` no coincide con el "Server name" de SSMS, o el servicio de SQL Server está apagado. Revisa en **Servicios** de Windows que "SQL Server (SQLEXPRESS)" esté iniciado. Para instancias con nombre (`\SQLEXPRESS`) también debe correr "SQL Server Browser". |
| `Login failed for user 'coffeestock_app'` o `'sa'` | Contraseña incorrecta o falta activar **SQL Server and Windows Authentication mode** (ver paso 1). |
| `Login failed for user 'MI-PC\Usuario'` | Estás usando Windows Authentication y tu usuario de Windows no tiene acceso. Usa SQL Authentication o dale acceso desde SSMS (Security → Logins). |
| `Cannot open database "CoffeeStockDB"` | No se corrió `scripts/crear_base_de_datos.sql`, o `DB_NAME` está mal escrito. |
| `SSL Provider: certificate verify failed` | Ya viene resuelto (`TrustServerCertificate=yes`). Si lo ves, confirma que tienes la última versión del proyecto. |
| No llegan los correos | Corre `python manage.py probar_correo` y lee el mensaje. Revisa Spam. Recuerda el límite de 24 h por insumo. |
| `probar_correo` dice 403 | Con SendGrid: `SENDGRID_FROM_EMAIL` no está verificado o la API key no tiene permiso Mail Send. |
| `probar_correo` dice 401 | La API key de SendGrid está mal copiada o fue eliminada. |
| `Username and Password not accepted` (Gmail) | Estás usando la contraseña normal. Necesitas la **contraseña de aplicación** de 16 letras. |
| Cambié el `.env` y no pasa nada | Detén `runserver` con `Ctrl + C` y vuelve a levantarlo. |

---

## Pruebas automáticas

```bash
python manage.py test
```

Crean una base temporal `test_CoffeeStockDB` y la borran al terminar (el
usuario de la base necesita permiso para crear bases; el script ya se lo da a
`coffeestock_app`). Cubren el flujo de alertas: venta que dispara correo,
venta revertida que no lo manda, cooldown de 24 h, edición manual, errores de
SendGrid y el comando `probar_correo`.

---

## Estructura del proyecto

```
coffeestock/           Configuración de Django (settings, urls, estilos)
core/                  Modelos, login, roles y lógica compartida
  models.py            Insumo, Producto, RecetaInsumo, Merma, Venta, DetalleVenta
  services/alertas.py  Envío de alertas (consola, SMTP o SendGrid)
  management/commands/ create_groups, create_test_users, seed_demo_data, probar_correo
pos/                   Punto de venta y confirmación de ventas
dashboard/             Dashboard, CRUD de insumos/productos, mermas y ventas
templates/             HTML (Bootstrap 5 + Bootstrap Icons + Chart.js)
scripts/               crear_base_de_datos.sql para SQL Server
```

Antes de usarlo con datos reales, cambia las contraseñas de prueba:

```bash
python manage.py changepassword cajero1
python manage.py changepassword admin_coffeestock
```

---

## Pendiente para el Avance 2

Lo que queda para la entrega final, agrupado por tema.

### Funcionalidad

- **Entradas de inventario / compras**: hoy el stock solo se sube editando el
  insumo. Falta un registro de compras con proveedor, fecha, cantidad y costo,
  que deje historial.
- **Proveedores**: catálogo básico y relación con los insumos.
- **Anular ventas / devoluciones** devolviendo el stock descontado.
- **Corte de caja por turno**: total vendido por cajero y por forma de pago.
- **Forma de pago y ticket** imprimible o en PDF.
- **Gestión de usuarios desde el dashboard**, sin depender de `/admin/`.
- **Reportes exportables** a Excel/PDF (ventas por periodo, mermas, valor del
  inventario).
- **Costo y margen por producto** calculado a partir de la receta.

### Alertas

- Enviar el correo en segundo plano (hilo o cola de tareas) para que el POS no
  espere la respuesta del proveedor de correo.
- Resumen diario con todos los insumos bajos, en vez de un correo por insumo.
- Reintentar alertas que fallaron y dejar registro de envíos en la base.
- Correo con formato HTML y enlace directo al insumo.
- Configurar los destinatarios desde el dashboard en lugar del `.env`.

### Rendimiento

- En la venta se consultan las recetas producto por producto y cada insumo se
  bloquea y relee por separado. Se puede traer todo en una sola consulta
  (`prefetch_related`) y bloquear los insumos de una vez, en orden, lo que
  además evita posibles bloqueos cruzados entre dos cajas.
- Cachear los cálculos del dashboard por unos minutos.
- Revisar índices con datos grandes (por ejemplo `DetalleVenta` por fecha de
  venta para el top de productos) y medir con muchas ventas cargadas.
- Pruebas de carga del POS con varios cajeros vendiendo a la vez.

### Diseño y experiencia de uso

- POS pensado para pantalla táctil (botones más grandes, atajos de teclado).
- Confirmaciones y mensajes más claros cuando falta stock para una venta.
- Modo oscuro y revisión de accesibilidad (contraste, navegación con teclado).
- Traducir por completo la interfaz y el admin de Django al español, y usar la
  zona horaria local (hoy fechas y gráficos se calculan en UTC).

### Calidad y despliegue

- Más pruebas automáticas (POS, permisos por rol, dashboard, formularios).
- Integración continua (GitHub Actions) corriendo las pruebas contra SQL
  Server en contenedor.
- Configuración de producción: `DEBUG=False`, una `SECRET_KEY` propia y
  `ALLOWED_HOSTS` (ya se pueden poner en el `.env`, falta documentarlo y
  probarlo), HTTPS, un servidor de aplicación en vez de `runserver`, servir
  estáticos e imágenes, y respaldos de la base de datos.
