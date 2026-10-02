"""Protected books-to-return handoff without pretending books are tax profit."""
from ha.returns import estimate_w2

def estimate_connected_return(ledger,principal,scope,scenario):
    books=ledger.project(principal,scope,'year')
    if not isinstance(scenario,dict) or str(scenario.get('tax_year'))!=str(scope.tax_year):
        raise ValueError('Return and business record years must match')
    result=estimate_w2(scenario)
    result['business_draft']=books
    if books['ledger_revision']:
        result.update(estimated_tax=None,refund=None,balance_due=None,needs_review=True,incomplete=True)
        result['review_items'].append({'form':'HA Bookin','index':None,'reasons':[
            'Saved business records are connected to this draft. Book profit is not yet verified taxable business profit.',
            'Business tax adjustments, self-employment tax and payment treatment must be completed before showing a combined refund or balance.']})
    result['may_prepare_return']=False
    return result
