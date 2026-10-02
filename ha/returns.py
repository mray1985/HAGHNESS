"""Bounded W-2-only scenario preview, separate from preparation authorization."""
from decimal import Decimal
from ha.engine.federal import bracket_tax
from ha.rules import D, year_block

DEDUCTIONS={'2024':14600,'2025':15750,'2026':16100}
SOURCES={
    '2024':['https://www.irs.gov/irb/2023-48_IRB'],
    '2025':['https://www.irs.gov/irb/2024-45_IRB','https://www.irs.gov/irb/2025-45_IRB'],
    '2026':['https://www.irs.gov/irb/2025-45_IRB'],
}


def estimate_w2(data):
    if not isinstance(data,dict):raise ValueError('Object required')
    year=str(data.get('tax_year','2025'))
    if year not in DEDUCTIONS:raise ValueError('Unsupported tax year')
    if data.get('filing_status','single')!='single':raise ValueError('This W-2 preview supports single filing status only')
    forms=data.get('w2s',[])
    if not isinstance(forms,list) or len(forms)>100:raise ValueError('Up to 100 W-2 forms are supported')
    wages=Decimal(0);withholding=Decimal(0);incomplete=not forms
    for form in forms:
        if not isinstance(form,dict):raise ValueError('W-2 object required')
        for key in ('box1','box2'):
            raw=form.get(key,'')
            if raw in ('',None):
                incomplete=True;value=Decimal(0)
            else:
                value=D(raw)
                if value<0 or value>Decimal('1000000000') or value.as_tuple().exponent < -2:
                    raise ValueError('Use a nonnegative amount with at most two decimal places, up to one billion')
            if key=='box1':wages+=value
            else:withholding+=value
    deduction=Decimal(DEDUCTIONS[year])
    taxable=max(Decimal(0),wages-deduction)
    tax=bracket_tax(taxable,year_block(year)['brackets']['single']).quantize(Decimal('.01'))
    net=withholding-tax
    return {'tax_year':year,'wages':float(wages),'withholding':float(withholding),
            'standard_deduction':float(deduction),'taxable_income':float(taxable),
            'estimated_tax':float(tax),'refund':float(max(Decimal(0),net)),
            'balance_due':float(max(Decimal(0),-net)),'incomplete':incomplete,
            'may_prepare_return':False,'method':'W-2 wages minus basic standard deduction; ordinary federal brackets only',
            'excluded':['Credits, including EIC','Other income and adjustments','Additional deductions and taxes','State and local returns'],
            'sources':SOURCES[year]}
