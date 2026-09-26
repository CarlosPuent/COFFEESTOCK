# ☕ CoffeeStock

Sistema para cafeterías: punto de venta, inventario de insumos, productos con
receta, mermas, alertas de stock bajo por correo y dashboard con reportes.
Hecho con Django y SQL Server.

> **Avance 1 de 2.** Lo que falta para la entrega final está al final:
> [Pendiente para el Avance 2](#pendiente-para-el-avance-2).

Esta guía es para **Windows**. Sigue los pasos en orden, del 1 al 12, sin
saltarte ninguno. Cada paso dice qué hacer y qué deberías ver si salió bien.

| Paso | Qué haces | Tiempo aprox. |
|---|---|---|
| [1](#paso-1-instalar-los-programas) | Instalar los programas | 20 min (solo la primera vez) |
| [2](#paso-2-averiguar-el-nombre-de-tu-servidor-sql) | Averiguar el nombre de tu servidor SQL | 2 min |
| [3](#paso-3-conectarte-con-sql-server-management-studio) | Conectarte con SQL Server Management Studio | 2 min |
| [4](#paso-4-descargar-el-proyecto) | Descargar el proyecto | 1 min |
| [5](#paso-5-crear-la-base-de-datos) | Crear la base de datos | 1 min |
| [6](#paso-6-preparar-python) | Preparar Python | 3 min |
| [7](#paso-7-crear-el-archivo-de-configuración-env) | Crear el archivo de configuración | 2 min |
| [8](#paso-8-crear-las-tablas-y-los-datos-de-prueba) | Crear las tablas y los datos de prueba | 1 min |
| [9](#paso-9-abrir-el-sistema) | Abrir el sistema | 1 min |
| [10](#paso-10-probar-el-sistema-completo) | Probar el sistema completo | 5 min |
| [11](#paso-11-recibir-las-alertas-en-tu-correo) | Recibir las alertas en tu correo | 5 min |
| [12](#paso-12-probar-la-alerta-por-correo) | Probar la alerta por correo | 2 min |

¿Algo falló? Ve a [Si algo falla](#si-algo-falla).
¿Ya lo habías intentado y quieres empezar limpio? Ve a
[Empezar desde cero](#empezar-desde-cero).

---

## Paso 1. Instalar los programas

Instala estos cinco programas. Si ya tienes alguno, sáltalo.

1. **Python 3.12 o más nuevo**: [python.org/downloads](https://www.python.org/downloads/).
   Al abrir el instalador marca la casilla **"Add python.exe to PATH"** (abajo
   de la ventana) y luego clic en **Install Now**.
2. **Git**: [git-scm.com/downloads](https://git-scm.com/downloads). Siguiente,
   siguiente, con todo por defecto.
3. **SQL Server Express**: [descarga](https://www.microsoft.com/sql-server/sql-server-downloads).
   Elige **Express**, luego la instalación **Basic**.
4. **SQL Server Management Studio (SSMS)**: [descarga](https://learn.microsoft.com/sql/ssms/download-sql-server-management-studio-ssms).
5. **ODBC Driver 18 for SQL Server**: [descarga](https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server).
   Elige el instalador de Windows **x64**.

Cuando termines, **cierra todas las ventanas de PowerShell** que tengas
abiertas. Las ventanas que ya estaban abiertas no ven lo que acabas de
instalar.

**Comprueba:** abre una PowerShell nueva (tecla Windows, escribe
`PowerShell`, Enter) y escribe:

```powershell
py --list
```

✅ Debe salir una línea con `3.12` o mayor, por ejemplo `-V:3.13 *`.

---

## Paso 2. Averiguar el nombre de tu servidor SQL

Este es **el dato más importante de toda la instalación**. Lo vas a usar en
SSMS (paso 3) y en la configuración (paso 7). Si está mal, nada conecta.

En la PowerShell copia y pega esto, y presiona Enter:

```powershell
Get-Service | Where-Object DisplayName -like 'SQL Server (*' | Select-Object Status, DisplayName
```

Te sale algo parecido a esto:

```
 Status DisplayName
 ------ -----------
Running SQL Server (SQLEXPRESS)
```

Busca lo que está **entre paréntesis** y usa esta tabla:

| Si dice… | Tu nombre de servidor es… |
|---|---|
| `SQL Server (SQLEXPRESS)` | `localhost\SQLEXPRESS` |
| `SQL Server (MSSQLSERVER)` | `localhost` |
| `SQL Server (OTRO_NOMBRE)` | `localhost\OTRO_NOMBRE` |

**Anota tu nombre de servidor.** En el resto de la guía lo llamamos
**TU_SERVIDOR**.

- Si salen **varias líneas**, tienes varios SQL Server instalados. Elige el que
  diga `Running`, preferiblemente `SQLEXPRESS`.
- Si dice **`Stopped`**: el servidor está apagado. Tecla Windows → escribe
  `Servicios` → abre **Servicios** → busca esa línea (por ejemplo
  "SQL Server (SQLEXPRESS)") → clic derecho → **Iniciar**.
- Si **no sale nada**: SQL Server no está instalado. Vuelve al paso 1, punto 3.

> Si usas **LocalDB** (viene con Visual Studio) y no tienes SQL Server
> Express, tu servidor es `(localdb)\MSSQLLocalDB`. Lo compruebas con
> `sqllocaldb info`.

---

## Paso 3. Conectarte con SQL Server Management Studio

1. Abre **SQL Server Management Studio** (tecla Windows → escribe `SSMS`).
2. Aparece la ventana **Connect to Server**. Llénala así:

   | Campo | Qué poner |
   |---|---|
   | Server type | `Database Engine` |
   | Server name | **TU_SERVIDOR** (por ejemplo `localhost\SQLEXPRESS`) |
   | Authentication | `Windows Authentication` |
   | Encryption | `Optional` (si aparece este campo) |
   | Trust server certificate | ✔ marcado (si aparece esta casilla) |

3. Clic en **Connect**.

✅ A la izquierda, en **Object Explorer**, aparece tu servidor con una
carpeta **Databases** debajo.

❌ Si sale un error:

- **"A network-related or instance-specific error"** o **"server was not
  found"**: el nombre no es correcto o el servidor está apagado. Repite el
  paso 2.
- **"certificate chain was issued by an authority that is not trusted"**:
  marca **Trust server certificate** (clic en **Options >>** si no la ves).

> Si en **Server name** despliegas la lista y eliges **<Browse for more…>** →
> **Local Servers** → **Database Engine**, SSMS te muestra los servidores
> instalados en tu computadora. Es otra forma de encontrar TU_SERVIDOR.

---

## Paso 4. Descargar el proyecto

En la PowerShell escribe estos comandos, **uno a la vez** (escribes uno,
Enter, y luego el siguiente):

```powershell
cd C:\
```

```powershell
git clone https://github.com/CarlosPuent/COFFEESTOCK.git
```

```powershell
cd C:\COFFEESTOCK
```

✅ La línea de la PowerShell ahora dice `PS C:\COFFEESTOCK>`.

> Si dice `destination path 'COFFEESTOCK' already exists`, ya lo habías
> descargado antes. Ve a [Empezar desde cero](#empezar-desde-cero).

---

## Paso 5. Crear la base de datos

En SSMS, ya conectado (paso 3):

1. Menú **File → Open → File…**
2. Abre el archivo `C:\COFFEESTOCK\scripts\crear_base_de_datos.sql`.
3. Presiona **F5** (o el botón **Execute**).

✅ Abajo, en **Messages**, dice
`Listo: base de datos CoffeeStockDB preparada.` Si en Object Explorer das clic
derecho en **Databases → Refresh**, aparece `CoffeeStockDB`.

> Las tablas todavía no existen; se crean en el paso 8.

---

## Paso 6. Preparar Python

De vuelta en la PowerShell (en `C:\COFFEESTOCK`), uno a la vez:

```powershell
py -m venv venv
```

```powershell
venv\Scripts\Activate.ps1
```

```powershell
pip install -r requirements.txt
```

✅ Después del segundo comando, la línea empieza con `(venv)`, así:
`(venv) PS C:\COFFEESTOCK>`. El tercero tarda un par de minutos y termina con
`Successfully installed ...`.

❌ Si al activar dice **"la ejecución de scripts está deshabilitada"**:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Responde `S` (o `Y`), Enter, y vuelve a correr `venv\Scripts\Activate.ps1`.

---

## Paso 7. Crear el archivo de configuración (`.env`)

1. En la PowerShell:

   ```powershell
   notepad .env
   ```

   Si pregunta si quieres crear un archivo nuevo, di **Sí**.

2. En el Bloc de notas presiona **Ctrl + A** y luego **Suprimir**, para que
   quede vacío.

3. Copia este bloque y pégalo con **Ctrl + V**:

   ```ini
   DB_NAME=CoffeeStockDB
   DB_HOST=localhost\SQLEXPRESS
   DB_PORT=
   DB_USER=
   DB_PASSWORD=

   ALERTA_EMAIL_PROVEEDOR=consola
   ALERTA_EMAIL_DESTINATARIOS=tu_correo@gmail.com
   ```

4. Cambia dos cosas:
   - En `DB_HOST=` pon **TU_SERVIDOR** del paso 2, si no es
     `localhost\SQLEXPRESS`.
   - En `ALERTA_EMAIL_DESTINATARIOS=` pon **tu correo**.

5. Guarda con **Ctrl + S** y cierra el Bloc de notas.

> `DB_USER` y `DB_PASSWORD` van **vacíos**: así el sistema entra a SQL Server
> con tu usuario de Windows, igual que SSMS en el paso 3.
>
> `ALERTA_EMAIL_PROVEEDOR=consola` significa que, por ahora, las alertas se
> muestran en la PowerShell en vez de enviarse. En el paso 11 lo cambias para
> que lleguen a tu correo.

---

## Paso 8. Crear las tablas y los datos de prueba

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

✅ Lo que debes ver:

| Comando | Mensaje final |
|---|---|
| `migrate` | Una lista de `Applying ... OK` |
| `create_groups` | `Grupos "Administrador" y "Cajero" creados/actualizados...` |
| `create_test_users` | `Usuarios de prueba "cajero1" y "admin_coffeestock" creados/actualizados.` |
| `seed_demo_data` | `Datos de ejemplo creados: 10 insumos, 8 productos, ...` |

❌ Si `migrate` falla, es un problema de conexión con SQL Server. Revisa que
`DB_HOST` en el `.env` sea exactamente TU_SERVIDOR y mira
[Si algo falla](#si-algo-falla).

---

## Paso 9. Abrir el sistema

```powershell
python manage.py runserver
```

✅ Sale `Starting WSGI development server at http://127.0.0.1:8000/`.

**Deja esa PowerShell abierta** mientras usas el sistema. Abre el navegador en
**http://127.0.0.1:8000/**.

Usuarios de prueba:

| Usuario | Contraseña | Qué puede hacer |
|---|---|---|
| `admin_coffeestock` | `Admin123!` | Todo: dashboard, insumos, productos, ventas, mermas y POS |
| `cajero1` | `Cajero123!` | Punto de venta y registrar mermas |

Para apagar el sistema: clic en la PowerShell y **Ctrl + C**.

---

## Paso 10. Probar el sistema completo

**A. Hacer una venta (como cajero)**

1. Entra con `cajero1` / `Cajero123!`. Se abre el **punto de venta**.
2. Clic en **Cappuccino** y en **Croissant**. Aparecen en el carrito a la
   derecha con su total.
3. Clic en **Confirmar venta**. Arriba sale en verde
   `Venta #... registrada correctamente. Total: ...`.
4. Arriba a la derecha, **Salir**.

**B. Revisar como administrador**

1. Entra con `admin_coffeestock` / `Admin123!`. Se abre el **Dashboard**:
   - Tarjetas rojas con los insumos que están bajo el mínimo
     (**Café en grano robusta** y **Sirope de caramelo**).
   - Gráficas de ventas de 7 días, top 5 de productos y mermas del mes.
2. Menú **Ventas**: la venta del cajero aparece de primera. Clic en ella para
   ver el detalle.
3. Menú **Insumos**: la leche, el café y la harina bajaron por la receta de lo
   que se vendió.

**C. Provocar una alerta de stock bajo**

1. Menú **Registrar merma**.
2. Insumo: **Sirope de caramelo**. Cantidad: `10`. Causa: la que quieras.
3. Clic en **Registrar merma**.
4. Mira la PowerShell donde corre el sistema. Aparece el correo de alerta
   impreso, con el asunto `[CoffeeStock] Stock bajo: Sirope de caramelo`, y al
   final la línea `Alerta de stock de "Sirope de caramelo" enviada.`

✅ Si ves todo esto, el sistema funciona completo. Solo falta que la alerta
llegue a un correo real (paso 11).

---

## Paso 11. Recibir las alertas en tu correo

Elige **una** opción: **A** si tienes una API key de SendGrid, **B** si
prefieres usar Gmail.

Primero apaga el sistema: clic en la PowerShell y **Ctrl + C**. Luego abre la
configuración:

```powershell
notepad .env
```

Presiona **Ctrl + A**, **Suprimir**, y pega el bloque de tu opción.

### Opción A: SendGrid

```ini
DB_NAME=CoffeeStockDB
DB_HOST=localhost\SQLEXPRESS
DB_PORT=
DB_USER=
DB_PASSWORD=

ALERTA_EMAIL_PROVEEDOR=sendgrid
ALERTA_EMAIL_DESTINATARIOS=tu_correo@gmail.com
SENDGRID_API_KEY=SG.pega_aqui_la_api_key
SENDGRID_FROM_EMAIL=correo_verificado_en_sendgrid@gmail.com
```

Cambia:

- `DB_HOST`: TU_SERVIDOR (el mismo del paso 7).
- `ALERTA_EMAIL_DESTINATARIOS`: **quien recibe** las alertas. Puede ser
  cualquier correo, o varios separados por coma.
- `SENDGRID_API_KEY`: la API key completa. Empieza con `SG.`.
- `SENDGRID_FROM_EMAIL`: el correo **verificado en la cuenta de SendGrid** (el
  del dueño de la cuenta). **No lo cambies por el correo de quien recibe**: si
  no está verificado, SendGrid rechaza todo con error 403.

> ¿No tienes API key y quieres crear tu propia cuenta? En
> [sendgrid.com](https://sendgrid.com/): **Settings → Sender Authentication →
> Verify a Single Sender** (verifica tu correo) y después **Settings → API
> Keys → Create API Key** con permiso **Mail Send**. La key se muestra una
> sola vez.

### Opción B: Gmail

Antes, crea una contraseña de aplicación:

1. Activa la [verificación en dos pasos](https://myaccount.google.com/signinoptions/twosv)
   de tu cuenta de Google.
2. Entra a [Contraseñas de aplicaciones](https://myaccount.google.com/apppasswords),
   escribe `CoffeeStock`, clic en **Crear** y copia la clave de 16 letras.

Luego pega en el `.env`:

```ini
DB_NAME=CoffeeStockDB
DB_HOST=localhost\SQLEXPRESS
DB_PORT=
DB_USER=
DB_PASSWORD=

ALERTA_EMAIL_PROVEEDOR=smtp
ALERTA_EMAIL_DESTINATARIOS=tu_correo@gmail.com
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=tu_cuenta_de_gmail@gmail.com
EMAIL_HOST_PASSWORD=clavede16letras
```

Cambia `DB_HOST`, `ALERTA_EMAIL_DESTINATARIOS` (quien recibe),
`EMAIL_HOST_USER` (la cuenta de Gmail que envía) y `EMAIL_HOST_PASSWORD` (la
clave de 16 letras, **sin espacios**).

### Guarda y prueba

Guarda con **Ctrl + S**, cierra el Bloc de notas y escribe:

```powershell
python manage.py probar_correo
```

✅ Debe verse así:

```
Configuración actual de alertas por correo:
  Archivo:       C:\COFFEESTOCK\.env
  Proveedor:     sendgrid
  Remitente:     correo_verificado_en_sendgrid@gmail.com
  Destinatarios: tu_correo@gmail.com
  API key:       SG.abc...

SendGrid aceptó el correo (status 202).
```

Revisa tu bandeja: llega **"[CoffeeStock] Correo de prueba"**. Si no está,
busca en **Spam** o **Correo no deseado**, y si está ahí márcalo como "No es
spam".

❌ Si algo sale mal, el mensaje dice por qué:

| Si ves… | Qué hacer |
|---|---|
| `Proveedor: consola` | El `.env` no se guardó o la línea `ALERTA_EMAIL_PROVEEDOR` está mal escrita. Repite este paso. |
| `403` o `verified Sender Identity` | `SENDGRID_FROM_EMAIL` no es el correo verificado en SendGrid. |
| `401` | La API key está mal copiada o fue borrada. |
| `Username and Password not accepted` | En Gmail pusiste tu contraseña normal; necesitas la de 16 letras. |
| `Falta ...` | Esa línea está vacía en el `.env`. |
| `No se pudo conectar` | Sin internet, o el antivirus/firewall lo bloquea. |
| `CERTIFICATE_VERIFY_FAILED` | Un antivirus o la red inspecciona HTTPS. Corre `pip install -r requirements.txt` (instala `truststore`) y vuelve a probar. |
| `202` pero el correo no llega ni a Spam | Algunos correos institucionales (universidad, empresa) filtran estos envíos. Prueba con un Gmail: `python manage.py probar_correo --para tucorreo@gmail.com` |

---

## Paso 12. Probar la alerta por correo

Cada insumo avisa **una sola vez cada 24 horas**, y la prueba del paso 10 ya
contó. Así que primero reinicia los datos de prueba:

```powershell
python manage.py seed_demo_data --reset
```

```powershell
python manage.py runserver
```

1. Entra con `admin_coffeestock` / `Admin123!`.
2. Menú **Registrar merma** → Insumo **Sirope de caramelo** → Cantidad `10` →
   **Registrar merma**.
3. En la PowerShell aparece:
   `Alerta de stock de "Sirope de caramelo" enviada. SendGrid aceptó el correo (status 202).`
4. En tu correo llega **"[CoffeeStock] Stock bajo: Sirope de caramelo"**.

✅ Listo. La instalación está completa.

**Para mostrar otra alerta** sin reiniciar: registra una merma de `10` en
**Café en grano robusta**, que también está bajo el mínimo.

**Cuándo se manda una alerta:** cuando una venta, una merma o una edición de
insumo deja el stock **en o por debajo del mínimo**. Si el correo falla, la
venta o merma se guarda igual y el error aparece en la PowerShell.

---

## La próxima vez que quieras abrir el sistema

Abre PowerShell y escribe, uno a la vez:

```powershell
cd C:\COFFEESTOCK
```

```powershell
venv\Scripts\Activate.ps1
```

```powershell
python manage.py runserver
```

Y abre http://127.0.0.1:8000/. Si SQL Server está apagado, enciéndelo como en
el paso 2.

---

## Empezar desde cero

Si ya lo habías intentado y quieres dejar todo limpio antes de empezar de
nuevo en el paso 4:

**1. Borra la base de datos.** En SSMS (conectado como en el paso 3), clic en
**New Query**, pega esto y presiona **F5**:

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

**2. Borra la carpeta del proyecto.** Cierra VS Code y cualquier PowerShell
que esté dentro de `C:\COFFEESTOCK`. Abre una PowerShell nueva y escribe, uno a
la vez:

```powershell
cd C:\
```

```powershell
Remove-Item -Recurse -Force C:\COFFEESTOCK
```

Si dice que no existe, no pasa nada. Ahora sigue desde el
[paso 4](#paso-4-descargar-el-proyecto).

---

## Si algo falla

| Error | Solución |
|---|---|
| `No suitable Python runtime found`, o se abre la Microsoft Store | Python no está instalado, o la PowerShell estaba abierta al instalarlo. Paso 1 y abre una PowerShell nueva. |
| `No matching distribution found for Django==6.1` | Tu Python es menor a 3.12. Instala uno nuevo, borra la carpeta `venv` y repite el paso 6. |
| `No module named 'django'` | Falta activar el entorno: `venv\Scripts\Activate.ps1` (la línea debe empezar con `(venv)`). |
| `Can't open lib 'ODBC Driver...'` / `Data source name not found` | Falta el ODBC Driver 18 (paso 1, punto 5). |
| `Login timeout expired` / `Named Pipes Provider` / `server was not found` | `DB_HOST` no es TU_SERVIDOR, o SQL Server está apagado. Repite el paso 2. |
| `Cannot open database "CoffeeStockDB"` | Falta el paso 5. |
| `Login failed for user` | Deja `DB_USER` y `DB_PASSWORD` vacíos en el `.env` (paso 7). |
| `seed_demo_data` pregunta `¿Deseas continuar?` | Ya había datos. Escribe `n` y usa `python manage.py seed_demo_data --reset`. |
| Cambié el `.env` y no pasa nada | Guarda con Ctrl + S, apaga con Ctrl + C y vuelve a correr `python manage.py runserver`. |
| No llega el correo | `python manage.py probar_correo` y lee el mensaje (paso 11). Revisa Spam. Recuerda el límite de 24 h por insumo. |
| El dashboard muestra un aviso amarillo de correo | Falta un dato del correo en el `.env`; el aviso dice cuál. |

---

## Otras formas de conectar SQL Server (opcional)

### Con usuario y contraseña en vez de Windows

El script del paso 5 también crea el usuario `coffeestock_app` con la
contraseña `CoffeeStock_2026!`.

1. En SSMS activa el modo mixto: clic derecho sobre el servidor →
   **Properties** → **Security** → **SQL Server and Windows Authentication
   mode** → **OK**. Luego clic derecho sobre el servidor → **Restart**.
2. En el `.env`: `DB_USER=coffeestock_app` y `DB_PASSWORD=CoffeeStock_2026!`.

### SQL Server en Docker (macOS / Linux / Windows)

```bash
docker run -d --name coffeestock-sql -p 1433:1433 -e ACCEPT_EULA=Y -e 'MSSQL_SA_PASSWORD=CoffeeStock_2026!' mcr.microsoft.com/mssql/server:2022-latest
docker exec -i coffeestock-sql /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P 'CoffeeStock_2026!' -C < scripts/crear_base_de_datos.sql
```

En el `.env`: `DB_HOST=localhost`, `DB_PORT=1433`, `DB_USER=sa`,
`DB_PASSWORD=CoffeeStock_2026!`. En macOS/Linux el entorno se crea con
`python3 -m venv venv` y se activa con `source venv/bin/activate`. En Mac
instala el driver con `brew install msodbcsql18` y, si tu Mac tiene chip Apple,
activa en Docker Desktop **Settings → General → Use Rosetta**.

---

## Para desarrolladores

**Pruebas automáticas:** `python manage.py test`. Crean y borran una base
temporal; cubren el flujo de alertas y la lectura del `.env`.

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
`python manage.py changepassword admin_coffeestock` y
`python manage.py changepassword cajero1`.

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
