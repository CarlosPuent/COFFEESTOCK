"""PDFs con la identidad visual de CoffeeStock (reportlab)."""
from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import (
    KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

TINTA = colors.HexColor('#241B15')
ACENTO = colors.HexColor('#A9793F')
SUAVE = colors.HexColor('#7A6A5C')
FONDO = colors.HexColor('#F7F3ED')
BORDE = colors.HexColor('#E4DCD2')
PELIGRO = colors.HexColor('#B54B3A')
EXITO = colors.HexColor('#5C7C5A')

_FUENTES = Path(settings.BASE_DIR) / 'coffeestock' / 'static' / 'vendor' / 'fonts' / 'ttf'
_registradas = False


def _registrar_fuentes():
    global _registradas
    if _registradas:
        return
    for nombre, archivo in [
        ('Inter', 'inter-latin-400-normal.ttf'),
        ('Inter-SemiBold', 'inter-latin-600-normal.ttf'),
        ('Inter-Bold', 'inter-latin-700-normal.ttf'),
        ('Fraunces', 'fraunces-latin-700-normal.ttf'),
    ]:
        pdfmetrics.registerFont(TTFont(nombre, str(_FUENTES / archivo)))
    _registradas = True


def _estilos():
    _registrar_fuentes()
    return {
        'normal': ParagraphStyle('normal', fontName='Inter', fontSize=9, leading=12, textColor=TINTA),
        'suave': ParagraphStyle('suave', fontName='Inter', fontSize=8, leading=11, textColor=SUAVE),
        'seccion': ParagraphStyle(
            'seccion', fontName='Fraunces', fontSize=12.5, leading=16, textColor=TINTA,
            spaceBefore=10, spaceAfter=6,
        ),
        'celda': ParagraphStyle('celda', fontName='Inter', fontSize=8.5, leading=11, textColor=TINTA),
        'celda_der': ParagraphStyle(
            'celda_der', fontName='Inter', fontSize=8.5, leading=11, textColor=TINTA, alignment=TA_RIGHT,
        ),
        'kpi_etiqueta': ParagraphStyle(
            'kpi_etiqueta', fontName='Inter-SemiBold', fontSize=6.8, leading=9, textColor=SUAVE,
        ),
        'kpi_valor': ParagraphStyle('kpi_valor', fontName='Fraunces', fontSize=15, leading=19, textColor=TINTA),
        'kpi_detalle': ParagraphStyle('kpi_detalle', fontName='Inter', fontSize=7, leading=9, textColor=SUAVE),
    }


class _CanvasNumerado(rl_canvas.Canvas):
    """Canvas que conoce el total de páginas para escribir "Página 2 de 5"."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._paginas = []

    def showPage(self):
        self._paginas.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._paginas)
        for estado in self._paginas:
            self.__dict__.update(estado)
            self.setFont('Inter', 7.5)
            self.setFillColor(SUAVE)
            self.drawRightString(letter[0] - 18 * mm, 11 * mm, f'Página {self._pageNumber} de {total}')
            super().showPage()
        super().save()


def _dibujar_taza(c, x, y, tamano):
    """La taza del logo de CoffeeStock, en trazo de acento."""
    s = tamano / 16
    c.saveState()
    c.setStrokeColor(ACENTO)
    c.setLineWidth(1.1)
    c.roundRect(x + 3 * s, y, 9 * s, 9.5 * s, 2 * s, stroke=1, fill=0)
    c.roundRect(x + 11.6 * s, y + 4.3 * s, 2.8 * s, 3.6 * s, 1.3 * s, stroke=1, fill=0)
    for dx in (5.5, 8.5):
        c.bezier(x + dx * s, y + 11 * s, x + (dx - 0.8) * s, y + 12.5 * s,
                 x + (dx + 0.8) * s, y + 13.5 * s, x + dx * s, y + 15 * s)
    c.restoreState()


class ReportePDF:
    """Uso:
        pdf = ReportePDF('Ventas del período', 'Del 01/10/2026 al 31/10/2026', usuario)
        pdf.kpis([...]); pdf.seccion('Por día'); pdf.tabla([...], [...])
        return pdf.respuesta('ventas-octubre')
    """

    def __init__(self, titulo, periodo='', usuario=None, horizontal=False):
        self.titulo = titulo
        self.periodo = periodo
        self.usuario = usuario
        self.estilos = _estilos()
        self.elementos = []
        self.tamano = (letter[1], letter[0]) if horizontal else letter
        self.ancho_util = self.tamano[0] - 36 * mm

    # --- contenido ---

    def parrafo(self, texto, estilo='normal'):
        self.elementos.append(Paragraph(texto, self.estilos[estilo]))

    def espacio(self, alto=4):
        self.elementos.append(Spacer(1, alto * mm))

    def seccion(self, titulo):
        self.elementos.append(Paragraph(titulo, self.estilos['seccion']))

    def kpis(self, tarjetas):
        """tarjetas: lista de (etiqueta, valor, detalle). Una fila de recuadros."""
        celdas = [[
            [
                Paragraph(etiqueta.upper(), self.estilos['kpi_etiqueta']),
                Paragraph(valor, self.estilos['kpi_valor']),
                Paragraph(detalle or '&nbsp;', self.estilos['kpi_detalle']),
            ]
            for etiqueta, valor, detalle in tarjetas
        ]]
        separacion = 3 * mm
        ancho = (self.ancho_util - separacion * (len(tarjetas) - 1)) / len(tarjetas)
        anchos = []
        for i in range(len(tarjetas)):
            anchos.append(ancho)
            if i < len(tarjetas) - 1:
                anchos.append(separacion)
        fila = []
        for i, celda in enumerate(celdas[0]):
            fila.append(celda)
            if i < len(celdas[0]) - 1:
                fila.append('')
        tabla = Table([fila], colWidths=anchos)
        estilo = [
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 7),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ]
        for i in range(0, len(fila), 2):
            estilo += [
                ('BACKGROUND', (i, 0), (i, 0), FONDO),
                ('LINEABOVE', (i, 0), (i, 0), 2, ACENTO),
            ]
        tabla.setStyle(TableStyle(estilo))
        self.elementos.append(tabla)
        self.espacio(3)

    def tabla(self, encabezados, filas, anchos=None, derecha=(), total=None, mantener_junta=False):
        """Tabla con encabezado de acento. `derecha` son los índices de las
        columnas numéricas; `total` es una fila final en negrita."""
        e = self.estilos
        cabecera = [
            Paragraph(f'<font name="Inter-SemiBold" size="7" color="#7A6A5C">{h.upper()}</font>',
                      e['celda_der'] if i in derecha else e['celda'])
            for i, h in enumerate(encabezados)
        ]
        cuerpo = [
            [Paragraph(str(v), e['celda_der'] if i in derecha else e['celda']) for i, v in enumerate(fila)]
            for fila in filas
        ]
        datos = [cabecera] + cuerpo
        if total:
            datos.append([
                Paragraph(f'<font name="Inter-Bold">{v}</font>', e['celda_der'] if i in derecha else e['celda'])
                for i, v in enumerate(total)
            ])
        if anchos:
            suma = sum(anchos)
            anchos = [self.ancho_util * a / suma for a in anchos]
        tabla = Table(datos, colWidths=anchos, repeatRows=1)
        estilo = [
            ('LINEBELOW', (0, 0), (-1, 0), 1.2, ACENTO),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 4.5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4.5),
            ('LEFTPADDING', (0, 0), (-1, -1), 5),
            ('RIGHTPADDING', (0, 0), (-1, -1), 5),
            ('LINEBELOW', (0, 1), (-1, -2 if total else -1), 0.4, BORDE),
        ]
        for i in range(1, len(cuerpo) + 1):
            if i % 2 == 0:
                estilo.append(('BACKGROUND', (0, i), (-1, i), colors.HexColor('#FBF9F6')))
        if total:
            estilo += [('LINEABOVE', (0, -1), (-1, -1), 0.9, TINTA), ('BACKGROUND', (0, -1), (-1, -1), FONDO)]
        tabla.setStyle(TableStyle(estilo))
        self.elementos.append(KeepTogether(tabla) if mantener_junta else tabla)

    def firmas(self, etiquetas):
        """Líneas para firmar, una por etiqueta, lado a lado."""
        e = self.estilos
        separacion = 14 * mm
        ancho = (self.ancho_util - separacion * (len(etiquetas) - 1)) / len(etiquetas)
        fila_linea, fila_texto, anchos, estilo = [], [], [], []
        for i, etiqueta in enumerate(etiquetas):
            if i:
                fila_linea.append('')
                fila_texto.append('')
                anchos.append(separacion)
            estilo.append(('LINEBELOW', (len(anchos), 0), (len(anchos), 0), 0.8, TINTA))
            fila_linea.append('')
            fila_texto.append(Paragraph(etiqueta, e['suave']))
            anchos.append(ancho)
        tabla = Table([fila_linea, fila_texto], colWidths=anchos, rowHeights=[16 * mm, None])
        estilo.append(('LEFTPADDING', (0, 0), (-1, -1), 0))
        tabla.setStyle(TableStyle(estilo))
        self.elementos.append(KeepTogether(tabla))

    def vacio(self, texto):
        self.parrafo(f'<i>{texto}</i>', 'suave')

    # --- página ---

    def _pagina(self, c, doc):
        ancho, alto = self.tamano
        negocio = settings.NEGOCIO
        c.saveState()
        # Franja superior
        c.setFillColor(TINTA)
        c.rect(0, alto - 4 * mm, ancho, 4 * mm, stroke=0, fill=1)
        c.setFillColor(ACENTO)
        c.rect(0, alto - 5 * mm, ancho, 1 * mm, stroke=0, fill=1)
        # Marca
        y = alto - 22 * mm
        _dibujar_taza(c, 18 * mm, y - 1, 15)
        c.setFillColor(TINTA)
        c.setFont('Fraunces', 15)
        c.drawString(25 * mm, y + 3, negocio['nombre'])
        c.setFont('Inter', 7.5)
        c.setFillColor(SUAVE)
        linea = negocio['direccion'] + (f'  ·  Tel. {negocio["telefono"]}' if negocio['telefono'] else '')
        c.drawString(25 * mm, y - 7, linea)
        # Título del reporte
        c.setFillColor(TINTA)
        c.setFont('Fraunces', 13)
        c.drawRightString(ancho - 18 * mm, y + 3, self.titulo)
        c.setFont('Inter', 8)
        c.setFillColor(SUAVE)
        c.drawRightString(ancho - 18 * mm, y - 7, self.periodo)
        c.setStrokeColor(BORDE)
        c.setLineWidth(0.6)
        c.line(18 * mm, y - 13, ancho - 18 * mm, y - 13)
        # Pie
        c.line(18 * mm, 15 * mm, ancho - 18 * mm, 15 * mm)
        c.setFont('Inter', 7.5)
        c.setFillColor(SUAVE)
        generado = timezone.localtime().strftime('%d/%m/%Y %H:%M')
        quien = f' por {self.usuario.get_username()}' if self.usuario else ''
        c.drawString(18 * mm, 11 * mm, f'Generado el {generado}{quien}  ·  CoffeeStock')
        c.restoreState()

    def generar(self):
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=self.tamano, title=self.titulo, author=settings.NEGOCIO['nombre'],
            leftMargin=18 * mm, rightMargin=18 * mm, topMargin=34 * mm, bottomMargin=22 * mm,
        )
        doc.build(self.elementos, onFirstPage=self._pagina, onLaterPages=self._pagina,
                  canvasmaker=_CanvasNumerado)
        return buffer.getvalue()

