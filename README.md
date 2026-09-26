# ☕ CoffeeStock

Sistema para cafeterías: punto de venta, inventario de insumos, productos con
receta, mermas, alertas de stock bajo por correo y dashboard con reportes.
Hecho con Django y SQL Server.

> **Avance 1 de 2.** Lo que falta para la entrega final está al final:
> [Pendiente para el Avance 2](#pendiente-para-el-avance-2).

**Índice**

- [A. Instalar programas (una sola vez)](#a-instalar-programas-una-sola-vez)
- [B. Empezar desde cero (si ya lo habías intentado)](#b-empezar-desde-cero-si-ya-lo-habías-intentado)
- [C. Instalar el proyecto, pasos 1 a 7](#c-instalar-el-proyecto)
- [D. Recibir las alertas en tu correo](#d-recibir-las-alertas-en-tu-correo)
- [E. Si algo falla](#e-si-algo-falla)

---

## A. Instalar programas (una sola vez)

1. **Python 3.12 o más nuevo**: [python.org/downloads](https://www.python.org/downloads/).
   Al abrir el instalador marca **"Add python.exe to PATH"** (abajo de la
   ventana) y luego **Install Now**.
2. **Git**: [git-scm.com/downloads](https://git-scm.com/downloads). Todo con
   las opciones por defecto.
3. **SQL Server Express**: [descarga](https://www.microsoft.com/sql-server/sql-server-downloads).
   Elige la instalación **Basic**.
4. **SQL Server Management Studio (SSMS)**: [descarga](https://learn.microsoft.com/sql/ssms/download-sql-server-management-studio-ssms).
5. **ODBC Driver 18 for SQL Server**: [descarga](https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server).
   Elige el de Windows **x64**.
6. **Cierra todas las ventanas de PowerShell** que tengas abiertas. Las que ya
   estaban abiertas no ven lo que acabas de instalar.

Para comprobar Python, abre una PowerShell nueva y escribe:

```powershell
py --list
```

Debe salir una línea con `3.12` o más (por ejemplo `-V:3.13 *`).

---

## B. Empezar desde cero (si ya lo habías intentado)

Salta esta parte si es la primera vez.

**1. Borra la base de datos vieja.** En SSMS: conéctate, clic en **New
Query**, pega esto y presiona **F5**:

```sql
USE master;
GO
IF DB_ID('CoffeeStockDB') IS NOT NULL
BEGIN
    ALTER DATABASE CoffeeStockDB SET SINGLE_USER WITH ROLLBACK IMMEDIATE;
    DROP DATABASE CoffeeStockDB;
END
GO
```

**2. Borra la carpeta vieja.** Cierra VS Code y cualquier PowerShell que esté
dentro de la carpeta del proyecto. Abre una PowerShell nueva y escribe:

```powershell
cd C:\
Remove-Item -Recurse -Force C:\COFFEESTOCK
```

Si dice que la carpeta no existe, no pasa nada.

---

## C. Instalar el proyecto

### Paso 1. Descargar el proyecto

Abre **PowerShell** y escribe estos comandos (uno, Enter, el siguiente):

```powershell
cd C:\
```

```powershell
git clone https://github.com/CarlosPuent/COFFEESTOCK.git
```

```powershell
cd C:\COFFEESTOCK
```

### Paso 2. Crear la base de datos

1. Abre **SSMS**.
2. En la ventana de conexión, en **Authentication** deja **Windows
   Authentication** y clic en **Connect**.
3. **Anota lo que dice en "Server name"**. Casi siempre es
   `localhost\SQLEXPRESS`. Lo necesitas en el paso 4.
4. Menú **File → Open → File…** y abre
   `C:\COFFEESTOCK\scripts\crear_base_de_datos.sql`.
5. Presiona **F5**. Abajo debe decir
   `Listo: base de datos CoffeeStockDB preparada.`

### Paso 3. Preparar Python

En la misma PowerShell (dentro de `C:\COFFEESTOCK`), un comando a la vez:

```powershell
py -m venv venv
```

```powershell
venv\Scripts\Activate.ps1
```

```powershell
pip install -r requirements.txt
```

- Después del segundo comando la línea debe empezar con `(venv)`.
- El tercero tarda un par de minutos y termina con `Successfully installed ...`.
- Si al activar dice **"la ejecución de scripts está deshabilitada"**: escribe
  `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, responde `S` y
  vuelve a correr `venv\Scripts\Activate.ps1`.

### Paso 4. Crear el archivo de configuración (`.env`)

1. En la PowerShell escribe:

   ```powershell
   notepad .env
   ```

   Si pregunta si quieres crear un archivo nuevo, di **Sí**.

2. Se abre el Bloc de notas. Presiona **Ctrl + A** (selecciona todo) y luego
   **Suprimir**, para que quede vacío.

3. **Copia el bloque de abajo, pégalo con Ctrl + V y cambia `tu_correo@gmail.com`
   por tu correo:**

   ```ini
   DB_NAME=CoffeeStockDB
   DB_HOST=localhost\SQLEXPRESS
   DB_PORT=
   DB_USER=
   DB_PASSWORD=

   ALERTA_EMAIL_PROVEEDOR=consola
   ALERTA_EMAIL_DESTINATARIOS=tu_correo@gmail.com
   ```

   Si en el paso 2 el "Server name" **no** era `localhost\SQLEXPRESS`, cambia
   también `DB_HOST` por lo que anotaste.

4. Guarda con **Ctrl + S** y cierra el Bloc de notas.

> Esto usa tu usuario de Windows para entrar a SQL Server, igual que SSMS. No
> hace falta usuario ni contraseña.

### Paso 5. Crear las tablas y los datos de prueba

Uno a la vez:

```powershell
python manage.py migrate
```

```powershell
python manage.py create_groups
```

```powershell
python manage.py create_test_users
```

```powershell
python manage.py seed_demo_data
```

Lo que debes ver:

| Comando | Mensaje final |
|---|---|
| `migrate` | Una lista de `Applying ... OK` |
| `create_groups` | `Grupos "Administrador" y "Cajero" creados...` |
| `create_test_users` | `Usuarios de prueba ... creados...` |
| `seed_demo_data` | `Datos de ejemplo creados: 10 insumos, 8 productos...` |

### Paso 6. Abrir el sistema

```powershell
python manage.py runserver
```

Deja esa PowerShell abierta. Abre el navegador en **http://127.0.0.1:8000/** y
entra con:

| Usuario | Contraseña | Qué ve |
|---|---|---|
| `admin_coffeestock` | `Admin123!` | Dashboard, insumos, productos, mermas, ventas |
| `cajero1` | `Cajero123!` | Punto de venta |

Para apagar el sistema: clic en la PowerShell y **Ctrl + C**.

### Paso 7. Probar una alerta

1. Entra como `admin_coffeestock`.
2. Menú **Mermas → Registrar merma**.
3. Insumo: **Sirope de caramelo**. Cantidad: **10**. Causa: cualquiera.
   **Guardar**.
4. Mira la PowerShell donde corre el sistema: ahí aparece el correo de alerta
   impreso (`Subject: [CoffeeStock] Stock bajo: Sirope de caramelo`).

Si lo ves, todo funciona. Todavía no llega a ningún buzón porque está en modo
`consola`. Para que llegue de verdad sigue la parte D.

### La próxima vez que quieras abrir el sistema

Abre PowerShell y:

```powershell
cd C:\COFFEESTOCK
venv\Scripts\Activate.ps1
python manage.py runserver
```

---

## D. Recibir las alertas en tu correo

Hay dos formas. Elige una.

### Opción 1: SendGrid (si alguien ya te pasó la API key)

En SendGrid hay dos correos y **no son lo mismo**:

- **Remitente** (`SENDGRID_FROM_EMAIL`): el correo del **dueño de la cuenta de
  SendGrid**, el que está verificado ahí. No se cambia.
- **Destinatario** (`ALERTA_EMAIL_DESTINATARIOS`): **quien recibe** las
  alertas. Aquí pones tu correo (o varios separados por coma).

Pasos:

1. Apaga el sistema: **Ctrl + C** en la PowerShell.
2. Abre la configuración:

   ```powershell
   notepad .env
   ```

3. Borra las dos últimas líneas (`ALERTA_EMAIL_PROVEEDOR=...` y
   `ALERTA_EMAIL_DESTINATARIOS=...`) y pega en su lugar:

   ```ini
   ALERTA_EMAIL_PROVEEDOR=sendgrid
   ALERTA_EMAIL_DESTINATARIOS=tu_correo@gmail.com
   SENDGRID_API_KEY=SG.pega_aqui_la_api_key
   SENDGRID_FROM_EMAIL=correo_del_dueño_de_sendgrid@gmail.com
   ```

   Cambia los tres valores: tu correo, la API key completa (empieza con
   `SG.`) y el correo verificado del dueño de la cuenta.

4. **Ctrl + S** y cierra el Bloc de notas.
5. Prueba el envío (ver [Probar el correo](#probar-el-correo)).

> Si tú eres el dueño de la cuenta y no tienes API key: en sendgrid.com ve a
> **Settings → Sender Authentication → Verify a Single Sender** y verifica tu
> correo; luego **Settings → API Keys → Create API Key** con permiso
> **Mail Send**. La key se muestra una sola vez, cópiala.

### Opción 2: Gmail (no necesita SendGrid)

1. En tu cuenta de Google activa la
   [verificación en dos pasos](https://myaccount.google.com/signinoptions/twosv).
2. Entra a [Contraseñas de aplicaciones](https://myaccount.google.com/apppasswords),
   escribe cualquier nombre (ej. `CoffeeStock`), clic en **Crear** y copia la
   clave de 16 letras **sin espacios**.
3. Apaga el sistema (**Ctrl + C**) y abre `notepad .env`.
4. Borra las dos últimas líneas y pega:

   ```ini
   ALERTA_EMAIL_PROVEEDOR=smtp
   ALERTA_EMAIL_DESTINATARIOS=tu_correo@gmail.com
   EMAIL_HOST=smtp.gmail.com
   EMAIL_PORT=587
   EMAIL_USE_TLS=True
   EMAIL_HOST_USER=tu_cuenta_de_gmail@gmail.com
   EMAIL_HOST_PASSWORD=clavede16letras
   ```

   `EMAIL_HOST_USER` es la cuenta que envía. `ALERTA_EMAIL_DESTINATARIOS` es
   quien recibe. Pueden ser el mismo correo.

5. **Ctrl + S**, cierra, y prueba el envío (abajo).

### Probar el correo

Con el sistema apagado, en la PowerShell:

```powershell
python manage.py probar_correo
```

- Si sale **en verde** algo como `SendGrid aceptó el correo`: revisa tu
  bandeja, y también **Spam** y **Promociones**. Puede tardar un minuto.
- Si sale **en rojo** un `CommandError`: el mensaje dice qué está mal. Los más
  comunes:

  | Dice | Qué hacer |
  |---|---|
  | `403` / `verified Sender Identity` | `SENDGRID_FROM_EMAIL` no es el correo verificado del dueño de la cuenta. |
  | `401` | La API key está mal copiada, incompleta o fue borrada. |
  | `Username and Password not accepted` | En Gmail usaste tu contraseña normal; necesitas la de aplicación de 16 letras. |
  | `Falta ...` | Esa línea no está en el `.env` o está vacía. |
  | `No se pudo conectar` | Sin internet, o un antivirus/firewall está bloqueando. |

Cuando `probar_correo` funcione, prueba una alerta real:

1. Por si ya probaste antes en modo consola, reinicia los datos de prueba (cada
   insumo avisa **una sola vez cada 24 horas**, y la prueba en consola ya
   cuenta):

   ```powershell
   python manage.py seed_demo_data --reset
   ```

2. Levanta el sistema: `python manage.py runserver`.
3. Repite el [Paso 7](#paso-7-probar-una-alerta) (merma de 10 en **Sirope de
   caramelo**).
4. Revisa tu correo (y Spam). En la PowerShell debe aparecer
   `Alerta de stock de "Sirope de caramelo" enviada.`

En el dashboard, arriba, también se ve a qué correo se están enviando las
alertas o qué falta configurar.

### Cuándo se envía una alerta

- Cuando una venta, una merma o una edición deja un insumo **en o por debajo**
  de su stock mínimo.
- Máximo **un correo por insumo cada 24 horas**. Si editas el insumo y le
  subes el stock por encima del mínimo, el contador se reinicia.
- Si el correo falla, la venta o merma se guarda igual; el error aparece en la
  PowerShell y la tarjeta roja sigue en el dashboard.

---

## E. Si algo falla

| Error | Solución |
|---|---|
| `No suitable Python runtime found`, o se abre la Microsoft Store | Python no está instalado, o la PowerShell estaba abierta al instalarlo. Ver [parte A](#a-instalar-programas-una-sola-vez) y abre una PowerShell nueva. |
| `No matching distribution found for Django==6.1` | Tu Python es menor a 3.12. Instala uno nuevo, borra la carpeta `venv` y repite el paso 3. |
| `python` no se reconoce, pero antes funcionaba | Olvidaste activar el entorno: `venv\Scripts\Activate.ps1`. |
| `Can't open lib 'ODBC Driver...'` / `Data source name not found` | Falta el ODBC Driver 18 (parte A, punto 5). |
| `Login timeout expired` / `Named Pipes Provider` | `DB_HOST` no es igual al "Server name" de SSMS, o SQL Server está apagado. En Windows abre **Servicios** y revisa que "SQL Server (SQLEXPRESS)" esté **En ejecución**. |
| `Cannot open database "CoffeeStockDB"` | No corriste el script del paso 2. |
| `Login failed for user` | Revisa `DB_USER`/`DB_PASSWORD` en el `.env`. Con el bloque del paso 4 deben ir vacíos. |
| `seed_demo_data` pregunta `¿Deseas continuar?` | Ya había datos. Escribe `n` y usa `python manage.py seed_demo_data --reset`. |
| Cambié el `.env` y no pasa nada | Apaga con **Ctrl + C** y vuelve a correr `python manage.py runserver`. |
| No llega el correo | `python manage.py probar_correo`, revisa Spam, y recuerda el límite de 24 h por insumo. |

### Usar usuario y contraseña de SQL Server (opcional)

El script del paso 2 también crea el usuario `coffeestock_app` con contraseña
`CoffeeStock_2026!`. Para usarlo:

1. En SSMS activa el modo mixto: clic derecho en el servidor → **Properties** →
   **Security** → **SQL Server and Windows Authentication mode** → **OK**.
   Luego clic derecho en el servidor → **Restart**.
2. En el `.env` pon `DB_USER=coffeestock_app` y
   `DB_PASSWORD=CoffeeStock_2026!`.

### SQL Server en Docker (macOS / Linux)

```bash
docker run -d --name coffeestock-sql -p 1433:1433 -e ACCEPT_EULA=Y -e 'MSSQL_SA_PASSWORD=CoffeeStock_2026!' mcr.microsoft.com/mssql/server:2022-latest
docker exec -i coffeestock-sql /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P 'CoffeeStock_2026!' -C < scripts/crear_base_de_datos.sql
```

En el `.env`: `DB_HOST=localhost`, `DB_PORT=1433`, `DB_USER=sa`,
`DB_PASSWORD=CoffeeStock_2026!`. Entorno virtual: `python3 -m venv venv` y
`source venv/bin/activate`. En Mac instala el driver con
`brew install msodbcsql18` y, con chip Apple, activa en Docker Desktop
**Settings → General → Use Rosetta**.

---

## Para desarrolladores

**Pruebas automáticas:** `python manage.py test` (crea y borra una base
temporal; cubren el flujo de alertas).

**Estructura:**

```
coffeestock/           Configuración de Django
core/                  Modelos, login, roles, alertas (services/alertas.py) y comandos
pos/                   Punto de venta
dashboard/             Dashboard, insumos, productos, mermas y ventas
templates/             HTML (Bootstrap 5, Chart.js)
scripts/               crear_base_de_datos.sql
```

**Otras variables del `.env`:** `DB_DRIVER` (si tienes un driver ODBC distinto
al 17/18), `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`. `SENDGRID_ADMIN_EMAIL` de
versiones anteriores se sigue aceptando como destinatario.

**Antes de un uso real** cambia las contraseñas de prueba:
`python manage.py changepassword admin_coffeestock` y `... cajero1`.

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
