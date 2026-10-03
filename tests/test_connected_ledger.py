import json
import unittest
from pathlib import Path
from datetime import datetime, timedelta, timezone
from tests.test_connected_access import Repository
from ha.connected.domain import Principal, Scope
from ha.connected.ledger import Ledger


class LedgerTests(unittest.TestCase):
    def test_receipts_do_not_establish_transaction_completeness(self):
        for events in ([],[dict(id='documented',date='2026-10-01',kind='expense',amount_minor=1000,evidence='fictional receipt')]):
            ledger=Ledger(self.repo)
            for event in events:ledger.post_event(self.owner,self.scope,event)
            draft=ledger.project(self.owner,self.scope,'year')
            self.assertEqual(draft['missing_receipts'],[])
            self.assertEqual(draft['entry_completeness'],'not_verified')
            self.assertIsNone(draft['missing_entries'])
            self.assertFalse(draft['may_prepare_return'])
            from ha.connected.support_review import apply_support_reviews
            reviewed=apply_support_reviews(draft,ledger.history(self.owner,self.scope),[],[])
            self.assertEqual(reviewed['entry_completeness'],'not_verified')
            self.assertIsNone(reviewed['missing_entries'])
            if not events:self.assertTrue(reviewed['support_review_complete'])

    def test_payment_correction_preserves_original_and_unverified_status(self):
        original=dict(id='payment',date='2026-10-01',kind='owner_estimated_tax_payment',amount_minor=10000,status='recorded_unverified',government_confirmation=None,method='card')
        self.post(original)
        correction=dict(id='payment-fixed',date='2026-11-02',kind='correction',replaces='payment',amount_minor=12500,reason='Correct recorded amount')
        fixed=self.post(correction)
        self.assertEqual(self.post(correction),fixed)
        self.assertEqual(fixed['status'],'recorded_unverified')
        self.assertIsNone(fixed['government_confirmation'])
        self.assertEqual(fixed['posting_date'],'2026-10-01')
        self.assertEqual(self.ledger.history(self.owner,self.scope)[0]['source'],original)
        for period in ('month','quarter','year'):
            draft=self.ledger.project(self.owner,self.scope,period,10)
            self.assertEqual(draft['owner_payments_recorded_minor'],12500)
            self.assertEqual(draft['owner_payments_confirmed_minor'],0)
            self.assertEqual(draft['book_profit_minor'],0)
            self.assertEqual(draft['reserve_scenario_minor'],0)
        for patch in ({'status':'government_confirmed'},{'status':'recorded_unverified'},{'government_confirmation':'fictional claim'},{'government_confirmation':None}):
            with self.assertRaises(ValueError):self.post({**correction,'id':'forged','replaces':'payment-fixed',**patch})
        with self.assertRaises(ValueError):self.post({**correction,'id':'stale'})
        with self.assertRaises(ValueError):self.post({**correction,'id':'blank-reason','replaces':'payment-fixed','reason':'   '})
        self.ledger.store[self.scope][-1].update(status='government_confirmed',government_confirmation='fictional legacy confirmation')
        with self.assertRaises(ValueError):self.post({**correction,'id':'confirmed','replaces':'payment-fixed'})

    def test_source_review_claims_cannot_clear_support_queue(self):
        self.setUp()
        self.post({'id':'cash','date':'2026-10-01','kind':'income','amount_minor':1000,'method':'cash','explanation':'   ','reviewed':True})
        self.post({'id':'card','date':'2026-10-01','kind':'expense','amount_minor':200,'method':'card','evidence':'typed reference','reviewed':True})
        self.post({'id':'cash-fixed','date':'2026-10-02','kind':'correction','amount_minor':1200,'replaces':'cash','reason':'Correct amount','method':'card','explanation':'invented override'})
        draft=self.ledger.project(self.owner,self.scope,'year')
        self.assertEqual(draft['cash_explanations_missing'],['cash-fixed'])
        self.assertEqual(draft['support_review_required'],['card','cash-fixed'])
        self.assertFalse(draft['support_review_complete'])
        self.assertEqual(draft['book_profit_minor'],1000)

    def test_evidence_and_cash_explanation_must_be_text(self):
        self.setUp()
        for field in ('evidence','explanation'):
            with self.assertRaises(ValueError):self.post({'id':field,'date':'2026-10-01','kind':'income','amount_minor':100,field:{'reviewed':True}})

    def test_legacy_nontext_support_remains_projectable_and_needs_review(self):
        self.post({'id':'legacy','date':'2026-10-01','kind':'expense','amount_minor':100,'method':'cash'})
        legacy=self.ledger.store[self.scope][0]
        legacy['evidence']={'old':'unverified reference'}
        legacy['explanation']=['old explanation']
        draft=self.ledger.project(self.owner,self.scope,'year')
        self.assertEqual(draft['book_profit_minor'],-100)
        self.assertEqual(draft['missing_receipts'],['legacy'])
        self.assertEqual(draft['cash_explanations_missing'],['legacy'])
        self.post({'id':'fixed','date':'2026-10-02','kind':'correction','amount_minor':120,'replaces':'legacy','reason':'Amount correction'})
        self.assertEqual(self.ledger.project(self.owner,self.scope,'year')['support_review_required'],['fixed'])

    def setUp(self):
        self.repo = Repository()
        self.repo.grants[0] = self.repo.grants[0].__class__('orchard-owner', Scope('orchard', 'business', 2026), frozenset({'read', 'post', 'correct'}))
        self.scope = Scope('orchard', 'business', 2026)
        self.owner = Principal('orchard-owner', datetime.now(timezone.utc) + timedelta(minutes=5), True)
        self.ledger = Ledger(self.repo)

    def post(self, event):
        return self.ledger.post_event(self.owner, self.scope, event)

    def test_fixture_totals_and_support_payment_reserve_separation(self):
        fixture = json.loads((Path(__file__).resolve().parents[1] / 'docs/fixtures/day8-connected-workflow.json').read_text())
        for e in fixture['events']:
            self.post(e)
        for period in ('month', 'quarter', 'year'):
            draft = self.ledger.project(self.owner, self.scope, period, 10)
            self.assertEqual(draft['book_profit_minor'], 118000)
            self.assertEqual(draft['income_minor'], 150000)
            self.assertEqual(draft['expense_minor'], 32000)
            self.assertEqual(draft['reserve_scenario_minor'], 37500)
            self.assertEqual(draft['owner_payments_recorded_minor'], 10000)
            self.assertEqual(draft['owner_payments_confirmed_minor'], 0)
            self.assertIn('advertising', draft['missing_receipts'])
            self.assertIsNone(draft['tax_liability_minor'])
            self.assertFalse(draft['may_prepare_return'])
        self.assertEqual(self.ledger.history(self.owner, self.scope)[2]['amount_minor'], 10000)

    def test_retries_do_not_duplicate_and_conflicting_retry_rejected(self):
        event = {'id': 'sale', 'date': '2026-10-01', 'kind': 'income', 'amount_minor': 1000}
        self.post(event)
        self.post(event)
        with self.assertRaises(ValueError):
            self.post({**event, 'amount_minor': 2000})
        self.assertEqual(self.ledger.project(self.owner, self.scope, 'year')['income_minor'], 1000)

    def test_invalid_money_period_currency_and_correction_rejected(self):
        base = {'id': 'bad', 'date': '2026-10-01', 'kind': 'income', 'amount_minor': 1000}
        for patch in ({'amount_minor': True}, {'amount_minor': -1}, {'amount_minor': 1.1}, {'date': '2025-10-01'}, {'date': '2026-02-29'}, {'currency': 'EUR'}, {'kind': 'correction', 'replaces': 'missing'}):
            with self.assertRaises(ValueError):
                self.post({**base, **patch})

    def test_scope_denied_and_return_data_is_not_mutable(self):
        with self.assertRaises(PermissionError):
            self.ledger.project(self.owner, Scope('cedar', 'cedar-business', 2026), 'year')
        self.post({'id': 'sale', 'date': '2026-10-01', 'kind': 'income', 'amount_minor': 1000})
        history = self.ledger.history(self.owner, self.scope)
        history[0]['amount_minor'] = 999999
        self.assertEqual(self.ledger.project(self.owner, self.scope, 'year')['income_minor'], 1000)

    def test_correction_cannot_be_applied_twice_to_original(self):
        self.post({'id': 'expense', 'date': '2026-10-01', 'kind': 'expense', 'amount_minor': 1000, 'evidence': 'original'})
        self.post({'id': 'fix', 'date': '2026-10-02', 'kind': 'correction', 'replaces': 'expense', 'amount_minor': 1200, 'reason': 'Correction'})
        with self.assertRaises(ValueError):
            self.post({'id': 'fix2', 'date': '2026-10-03', 'kind': 'correction', 'replaces': 'expense', 'amount_minor': 1400, 'reason': 'Another'})
        result = self.ledger.project(self.owner, self.scope, 'month', 10)
        self.assertEqual(result['expense_minor'], 1200)
        self.assertEqual(result['source_event_ids'], ['fix'])

    def test_client_cannot_assert_government_confirmation(self):
        with self.assertRaises(ValueError):
            self.post({'id':'fake-paid','date':'2026-10-01','kind':'owner_estimated_tax_payment',
                       'amount_minor':1000,'status':'government_confirmed','government_confirmation':'typed-by-user'})

    def test_explicit_cash_explanation_amendment_preserves_original_money_and_support(self):
        self.post({'id':'cash-original','date':'2026-10-01','kind':'expense','amount_minor':1000,'method':'cash','evidence':'receipt'})
        self.post({'id':'cash-explained','date':'2026-10-03','kind':'correction','replaces':'cash-original','amount_minor':1000,'reason':'Added cash context','support_changes':{'explanation':'Paid cash for fictional supplies'}})
        original,current=self.ledger.history(self.owner,self.scope)
        self.assertIsNone(original.get('explanation'));self.assertEqual(current['explanation'],'Paid cash for fictional supplies')
        self.assertEqual(current['posting_date'],'2026-10-01');self.assertEqual(current['method'],'cash');self.assertEqual(current['evidence'],'receipt')
        draft=self.ledger.project(self.owner,self.scope,'year');self.assertEqual(draft['expense_minor'],1000);self.assertEqual(draft['cash_explanations_missing'],[])
        self.assertEqual(draft['support_review_required'],['cash-explained']);self.assertFalse(draft['may_prepare_return'])
        self.post({'id':'cash-clear','date':'2026-10-04','kind':'correction','replaces':'cash-explained','amount_minor':1000,'reason':'Withdraw incorrect context','support_changes':{'explanation':None}})
        self.assertEqual(self.ledger.project(self.owner,self.scope,'year')['cash_explanations_missing'],['cash-clear'])
        self.assertEqual(self.ledger.history(self.owner,self.scope)[1]['explanation'],'Paid cash for fictional supplies')

    def test_support_amendment_requires_explicit_bounded_explanation_only(self):
        self.post({'id':'cash-original','date':'2026-10-01','kind':'income','amount_minor':1000,'method':'cash'})
        base={'id':'invalid','date':'2026-10-02','kind':'correction','replaces':'cash-original','amount_minor':1000,'reason':'Update'}
        for index,value in enumerate(({},[],{'method':'card'},{'evidence':'forged'},{'explanation':True},{'explanation':' '},{'explanation':'x'*2001})):
            with self.subTest(value=value),self.assertRaises(ValueError):self.post({**base,'id':'invalid-'+str(index),'support_changes':value})
        with self.assertRaises(ValueError):self.post({'id':'not-correction','date':'2026-10-01','kind':'income','amount_minor':1000,'support_changes':{'explanation':'New'}})

    def test_chosen_reserve_and_extra_do_not_change_books_or_payments(self):
        self.post(dict(id='sale',date='2026-10-02',kind='income',amount_minor=150000))
        self.post(dict(id='payment',date='2026-10-03',kind='owner_estimated_tax_payment',amount_minor=10000,status='recorded_unverified'))
        before=self.ledger.history(self.owner,self.scope)
        for period in ('month','quarter','year'):
            draft=self.ledger.project(self.owner,self.scope,period,10,'0.1725',reserve_extra_minor=1001)
            self.assertEqual(draft['reserve_percentage_minor'],25875)
            self.assertEqual(draft['reserve_extra_minor'],1001)
            self.assertEqual(draft['reserve_scenario_minor'],26876)
            self.assertEqual(draft['reserve_percent'],'17.25')
            self.assertEqual(draft['book_profit_minor'],150000)
            self.assertEqual(draft['owner_payments_recorded_minor'],10000)
            self.assertEqual(draft['owner_payments_confirmed_minor'],0)
            self.assertFalse(draft['reserve_moves_money']);self.assertFalse(draft['may_prepare_return'])
        self.assertEqual(before,self.ledger.history(self.owner,self.scope))
        for extra in (True,-1,1.5,10**15+1):
            with self.assertRaises(ValueError):self.ledger.project(self.owner,self.scope,'year',reserve_extra_minor=extra)
        for rate in ('bad','NaN','Infinity','1.1'):
            with self.assertRaises(ValueError):self.ledger.project(self.owner,self.scope,'year',reserve_rate=rate)
