import re
from decimal import Decimal

from django import template

register = template.Library()

_PLAIN_NUMBER = re.compile(r'-?[\d,]+(\.\d+)?')


@register.filter
def cell(value):
    """An item cell for the paper: a plain number gets thousands separators ('120000' →
    '120,000', '2.5' stays '2.5'); anything else ('10kg', '시가', '₩5,000') prints as typed."""
    text = '' if value is None else str(value).strip()
    if not _PLAIN_NUMBER.fullmatch(text):
        return text
    number = Decimal(text.replace(',', ''))
    if number == number.to_integral():
        return f'{int(number):,}'
    return f'{number.normalize():,f}'
