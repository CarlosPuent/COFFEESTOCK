"""Libros de Excel con formato (openpyxl): título, encabezado, formatos de
moneda y cantidad, filtros, paneles fijos y fila de totales."""
import datetime
from decimal import Decimal
from io import BytesIO

from django.conf import settings
from django.utils import timezone
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

TINTA = '241B15'
ACENTO = 'A9793F'
SUAVE = '7A6A5C'
FONDO = 'F7F3ED'

FORMATOS = {
    'moneda': '"$"#,##0.00',
    'costo': '"$"#,##0.0000',
    'cantidad': '#,##0.##',
    'entero': '#,##0',
    'porcentaje': '0.0"%"',
    'fecha': 'dd/mm/yyyy',
    'fechahora': 'dd/mm/yyyy hh:mm',
    'hora': 'hh:mm',
    'texto': '@',
}
NUMERICOS = {'moneda', 'costo', 'cantidad', 'entero', 'porcentaje'}


def _columna(spec):
    """(titulo, formato, ancho[, sumar]). Por defecto solo se suman los montos."""
    titulo, formato, ancho = spec[:3]
    sumar = spec[3] if len(spec) > 3 else formato == 'moneda'
    return titulo, formato, ancho, sumar


def _valor(v):
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, datetime.datetime):
        return timezone.localtime(v).replace(tzinfo=None) if timezone.is_aware(v) else v
    return v


class LibroExcel:
    """Uso:
        libro = LibroExcel('Ventas detalladas', 'Del 01/10/2026 al 31/10/2026', usuario)
        libro.hoja('Ventas', [('Folio', 'texto', 12), ('Total', 'moneda', 12)], filas, totales=True)
        return libro.respuesta('ventas')
    """

    def __init__(self, titulo, periodo='', usuario=None):
        self.titulo = titulo
        self.periodo = periodo
        self.usuario = usuario
        self.libro = Workbook()
        self._primera = True

    def hoja(self, nombre, columnas, filas, totales=False):
        """columnas: lista de (encabezado, formato, ancho[, sumar])."""
        columnas = [_columna(c) for c in columnas]
        if self._primera:
            hoja = self.libro.active
            hoja.title = nombre[:31]
            self._primera = False
        else:
            hoja = self.libro.create_sheet(nombre[:31])

        n = len(columnas)
        ultima = get_column_letter(n)
        hoja.sheet_view.showGridLines = False

        # Título
        hoja['A1'] = settings.NEGOCIO['nombre']
        hoja['A1'].font = Font(name='Calibri', size=15, bold=True, color=TINTA)
        hoja['A2'] = self.titulo
        hoja['A2'].font = Font(name='Calibri', size=12, bold=True, color=ACENTO)
        generado = timezone.localtime().strftime('%d/%m/%Y %H:%M')
        quien = f' por {self.usuario.get_username()}' if self.usuario else ''
        hoja['A3'] = f'{self.periodo}  ·  Generado el {generado}{quien}'.strip(' ·')
        hoja['A3'].font = Font(name='Calibri', size=9, color=SUAVE)

        # Encabezado
        fila_enc = 5
        borde_acento = Border(bottom=Side(style='medium', color=ACENTO))
        for i, (titulo, formato, ancho, _) in enumerate(columnas, start=1):
            celda = hoja.cell(row=fila_enc, column=i, value=titulo)
            celda.font = Font(name='Calibri', size=10, bold=True, color='FFFFFF')
            celda.fill = PatternFill('solid', fgColor=TINTA)
            celda.alignment = Alignment(
                horizontal='right' if formato in NUMERICOS else 'left',
                vertical='center',
            )
            celda.border = borde_acento
            hoja.column_dimensions[get_column_letter(i)].width = ancho
        hoja.row_dimensions[fila_enc].height = 22

        # Datos
        fila = fila_enc
        relleno_par = PatternFill('solid', fgColor='FBF9F6')
        for fila, datos in enumerate(filas, start=fila_enc + 1):
            for col, (valor, (_, formato, _, _)) in enumerate(zip(datos, columnas), start=1):
                celda = hoja.cell(row=fila, column=col, value=_valor(valor))
                celda.number_format = FORMATOS.get(formato, 'General')
                celda.font = Font(name='Calibri', size=10, color=TINTA)
                if (fila - fila_enc) % 2 == 0:
                    celda.fill = relleno_par
        ultima_fila_datos = fila
        if ultima_fila_datos == fila_enc:
            vacia = hoja.cell(row=fila_enc + 1, column=1, value='Sin registros en el período seleccionado.')
            vacia.font = Font(name='Calibri', size=10, italic=True, color=SUAVE)

        if ultima_fila_datos > fila_enc:
            hoja.auto_filter.ref = f'A{fila_enc}:{ultima}{ultima_fila_datos}'
        hoja.freeze_panes = hoja.cell(row=fila_enc + 1, column=1)

        if totales and ultima_fila_datos > fila_enc:
            fila_total = ultima_fila_datos + 1
            borde = Border(top=Side(style='thin', color=TINTA))
            for col, (_, formato, _, sumar) in enumerate(columnas, start=1):
                celda = hoja.cell(row=fila_total, column=col)
                if col == 1:
                    celda.value = 'Total'
                elif sumar:
                    letra = get_column_letter(col)
                    celda.value = f'=SUBTOTAL(9,{letra}{fila_enc + 1}:{letra}{ultima_fila_datos})'
                    celda.number_format = FORMATOS[formato]
                celda.font = Font(name='Calibri', size=10, bold=True, color=TINTA)
                celda.fill = PatternFill('solid', fgColor=FONDO)
                celda.border = borde
        return hoja

    def generar(self):
        buffer = BytesIO()
        self.libro.save(buffer)
        return buffer.getvalue()
