"""Basic 1099-INT scenario amounts; special treatment requires tax review."""
from decimal import Decimal


def interest_totals(forms, amount):
    taxable = Decimal(0)
    exempt = Decimal(0)
    withholding = Decimal(0)
    incomplete = False
    reviews = []
    for index, form in enumerate(forms):
        if not isinstance(form, dict):
            raise ValueError('1099-INT object required')
        for flag in ('corrected', 'fatca'):
            if not isinstance(form.get(flag, False), bool):
                raise ValueError('Checkbox values must be boolean')
        country = form.get('box7', '')
        if not isinstance(country, str) or len(country) > 2000:
            raise ValueError('Foreign country must be bounded text')
        if form.get('special_treatment', '') not in ('', 'yes', 'no', 'unsure'):
            raise ValueError('Invalid interest review answer')
        values = {key: amount(form.get(key, '')) for key in
                  ('box1', 'box2', 'box3', 'box4', 'box5', 'box6', 'box8',
                   'box9', 'box10', 'box11', 'box12', 'box13')}
        taxable += (values['box1'] or Decimal(0)) + (values['box3'] or Decimal(0))
        exempt += values['box8'] or Decimal(0)
        withholding += values['box4'] or Decimal(0)
        incomplete |= values['box4'] is None or all(values[k] is None for k in ('box1', 'box3', 'box8'))
        reasons = []
        if form.get('special_treatment', '') != 'no':
            reasons.append('Confirm whether nominee interest, bond adjustments, exclusions, previously reported interest or foreign-account reporting applies.')
        if form.get('corrected', False):
            reasons.append('Check a corrected form against its original to avoid counting both.')
        if country.strip() or any(values[k] for k in ('box2', 'box5', 'box6', 'box9', 'box10', 'box11', 'box12', 'box13')):
            reasons.append('Penalties, foreign tax, private-activity bonds, market discount or bond premiums need review before estimating.')
        if reasons:
            reviews.append({'form': '1099-INT', 'index': index + 1, 'reasons': reasons})
            incomplete = True
    if taxable > 1500:
        reviews.append({'form': '1099-INT', 'index': None,
                        'reasons': ['Total taxable interest exceeds $1,500. Complete Schedule B and its reporting questions before estimating.']})
        incomplete = True
    return taxable, exempt, withholding, incomplete, reviews
