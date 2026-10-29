from django.db import migrations

# SQL Server reserva los IDs de 1000 en 1000 y, si el servicio se reinicia,
# los que no usó se pierden: la siguiente venta salta de la #145 a la #1145.
# Con IDENTITY_CACHE = OFF los números quedan consecutivos.
SQL = """
BEGIN TRY
    ALTER DATABASE SCOPED CONFIGURATION SET IDENTITY_CACHE = OFF;
END TRY
BEGIN CATCH
    PRINT 'IDENTITY_CACHE no se pudo desactivar (requiere SQL Server 2017+).';
END CATCH
"""


def desactivar_identity_cache(apps, schema_editor):
    if schema_editor.connection.vendor == 'microsoft':
        with schema_editor.connection.cursor() as cursor:
            cursor.execute(SQL)


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ('core', '0003_insumo_idx_insumo_nombre_and_more'),
    ]

    operations = [
        migrations.RunPython(desactivar_identity_cache, migrations.RunPython.noop),
    ]
