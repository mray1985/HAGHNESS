"""Bounded document scenario preview, separate from preparation authorization."""
from decimal import Decimal
from ha.engine.federal import bracket_tax
from ha.rules import D, year_block
from ha.interest import interest_totals

SUPPORTED_YEARS=('2024','2025','2026')
SOURCES={
    '2024':['https://www.irs.gov/irb/2023-48_IRB'],
    '2025':['https://www.irs.gov/irb/2024-45_IRB','https://www.irs.gov/irb/2025-45_IRB'],
    '2026':['https://www.irs.gov/irb/2025-45_IRB'],
}


def _amount(raw):
    if raw in ('',None):return None
    value=D(raw)
    if value<0 or value>Decimal('1000000000') or value.as_tuple().exponent < -2:
        raise ValueError('Use a nonnegative amount with at most two decimal places, up to one billion')
    return value


def estimate_w2(data):
    # Keep the original entry point compatible with existing clients/tests.
    if not isinstance(data,dict):raise ValueError('Object required')
    year=str(data.get('tax_year','2025'))
    if year not in SUPPORTED_YEARS:raise ValueError('Unsupported tax year')
    if data.get('filing_status','single')!='single':raise ValueError('This W-2 preview supports single filing status only')
    forms=data.get('w2s',[]);retirement=data.get('retirement_forms',[]);interest=data.get('interest_forms',[])
    if any(not isinstance(items,list) or len(items)>100 for items in (forms,retirement,interest)):
        raise ValueError('Up to 100 documents of each supported type are allowed')
    wages=Decimal(0);withholding=Decimal(0);retirement_income=Decimal(0)
    incomplete=not forms and not retirement and not interest;review_items=[]
    for form in forms:
        if not isinstance(form,dict):raise ValueError('W-2 object required')
        for key in ('box1','box2'):
            raw=form.get(key,'')
            value=_amount(raw)
            if value is None:incomplete=True;value=Decimal(0)
            if key=='box1':wages+=value
            else:withholding+=value
    for index,form in enumerate(retirement):
        if not isinstance(form,dict):raise ValueError('1099-R object required')
        for flag in ('taxable_not_determined','ira','corrected'):
            if not isinstance(form.get(flag,False),bool):raise ValueError('Checkbox values must be boolean')
        code=form.get('box7','')
        if not isinstance(code,str) or len(code)>2:raise ValueError('Distribution code must be text, at most two characters')
        for question in ('rolled_over','special_treatment'):
            if form.get(question,'') not in ('','yes','no','unsure'):raise ValueError('Invalid retirement review answer')
        amounts={key:_amount(form.get(key,'')) for key in ('box1','box2a','box3','box4','box5','box6','box8','box8percent','box9a','box9b','box10','box11')}
        gross=amounts['box1'];reported=amounts['box2a']
        if gross is not None and reported is not None and reported>gross:
            raise ValueError('1099-R taxable amount cannot exceed gross distribution in this preview')
        withheld=amounts['box4']
        if withheld is None:incomplete=True
        withholding+=withheld or Decimal(0)
        reasons=[]
        if gross is None or reported is None:reasons.append('Enter boxes 1 and 2a; gross distribution is not assumed taxable.')
        if form.get('taxable_not_determined',False):reasons.append('Box 2b says the taxable amount is not determined.')
        if code.strip().upper()!='7':reasons.append('Only normal distribution code 7 is included in this basic scenario; other codes need tax review.')
        if form.get('ira',False):reasons.append('IRA/SEP/SIMPLE treatment and contribution basis need review.')
        if form.get('corrected',False):reasons.append('Corrected forms must be checked against the original to avoid duplicate income.')
        if form.get('rolled_over','')!='no':reasons.append('Confirm whether any amount was rolled over or returned.')
        if form.get('special_treatment','')!='no':reasons.append('Confirm whether any special distribution treatment applies.')
        if any(amounts[key] for key in ('box3','box5','box6','box8','box8percent','box9a','box9b','box10','box11')):
            reasons.append('Capital gains, contributions or other special amounts require review before estimating.')
        if reasons:review_items.append({'form':'1099-R','index':index+1,'reasons':reasons});incomplete=True
        else:retirement_income+=reported
    taxable_interest,tax_exempt_interest,interest_withholding,interest_incomplete,interest_reviews=interest_totals(interest,_amount)
    withholding+=interest_withholding;incomplete|=interest_incomplete;review_items.extend(interest_reviews)
    deduction=D(year_block(year)['standard_deduction']['single']);income=wages+retirement_income+taxable_interest
    taxable=max(Decimal(0),income-deduction)
    tax=bracket_tax(taxable,year_block(year)['brackets']['single']).quantize(Decimal('.01'))
    net=withholding-tax
    needs_review=bool(review_items)
    return {'tax_year':year,'wages':float(wages),'retirement_income':float(retirement_income),
            'taxable_interest':float(taxable_interest),'tax_exempt_interest':float(tax_exempt_interest),
            'income':float(income),'withholding':float(withholding),
            'standard_deduction':float(deduction),'taxable_income':float(taxable),
            'estimated_tax':None if needs_review else float(tax),
            'refund':None if needs_review else float(max(Decimal(0),net)),
            'balance_due':None if needs_review else float(max(Decimal(0),-net)),
            'incomplete':incomplete,'needs_review':needs_review,'review_items':review_items,
            'may_prepare_return':False,'method':'W-2 wages, supported normal pension amounts and basic 1099-INT interest; basic deduction and ordinary federal brackets only',
            'excluded':['Credits, including EIC','Other income and adjustments','Age/blindness additions, senior and other deductions','Additional taxes and special distribution treatment','State and local returns'],
            'sources':SOURCES[year]+(['https://www.irs.gov/instructions/i1040gi','https://www.irs.gov/pub/irs-pdf/f1099int.pdf'] if interest else [])+([f'https://www.irs.gov/pub/irs-prior/f1099r--{year}.pdf'] if retirement and year!='2026' else ['https://www.irs.gov/pub/irs-pdf/f1099r.pdf'] if retirement else [])}
