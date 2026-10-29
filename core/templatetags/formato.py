"""Filtros de presentación de números para las plantillas.

Formatean siempre con punto decimal y coma de miles (como se usa en
El Salvador), sin depender del idioma configurado en Django.
"""
from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()

UNIDADES_CORTAS = {'g': 'g', 'ml': 'ml', 'unidad': 'u'}


def _a_decimal(valor):
    if valor is None or valor == '':
        return None
    try:
        return Decimal(str(valor))
    except (InvalidOperation, ValueError):
        return None


@register.filter
def moneda(valor):
    """1234.5 -> "$1,234.50"."""
    numero = _a_decimal(valor)
    if numero is None:
        return '—'
    signo = '-' if numero < 0 else ''
    return f'{signo}${abs(numero):,.2f}'


@register.filter
def cantidad(valor):
    """8000.00 -> "8,000"; 12.50 -> "12.5"; 0.25 -> "0.25"."""
    numero = _a_decimal(valor)
    if numero is None:
        return '—'
    texto = f'{numero:,.2f}'
    if '.' in texto:
        texto = texto.rstrip('0').rstrip('.')
    return texto


@register.filter
def unidad_corta(codigo):
    """Código de unidad de medida -> abreviatura (g, ml, u)."""
    return UNIDADES_CORTAS.get(codigo, codigo)


@register.filter
def porcentaje(valor):
    """35.456 -> "35.5 %"."""
    numero = _a_decimal(valor)
    if numero is None:
        return '—'
    return f'{numero:,.1f} %'
