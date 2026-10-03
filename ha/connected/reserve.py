"""Read-only savings scenarios; no bank transfer or IRS payment authority."""
from decimal import Decimal
import re


def reserve_choice(percent='25', extra_choice='no', extra_dollars=''):
    if (not isinstance(percent,str) or not re.fullmatch(r'\d{1,3}(?:\.\d{1,2})?',percent)
            or Decimal(percent) > 100):
        raise ValueError('Choose a percentage from 0 to 100 with at most two decimals')
    if extra_choice not in ('yes','no') or not isinstance(extra_dollars,str):
        raise ValueError('Explicit extra reserve choice required')
    if extra_choice == 'no':
        if extra_dollars not in ('','0','0.00'):
            raise ValueError('An extra reserve amount requires an explicit yes')
        extra_minor = 0
    else:
        if not re.fullmatch(r'\d{1,14}(?:\.\d{1,2})?',extra_dollars):
            raise ValueError('Extra reserve needs a positive dollar amount with at most two decimals')
        extra_minor = int(Decimal(extra_dollars) * 100)
        if not 0 < extra_minor <= 10**15:
            raise ValueError('Extra reserve amount is outside the supported range')
    return Decimal(percent) / 100, extra_minor
