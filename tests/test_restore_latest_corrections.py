import json
from pathlib import Path
import unittest
from scripts import verify_database_restore as probe
from tests import test_connected_ledger as ledger_tests


class LatestCorrectionRestoreTests(unittest.TestCase):
    def fixture(self):
        fixture=ledger_tests.LedgerTests();fixture.setUp()
        source=json.loads(Path('docs/fixtures/day8-connected-workflow.json').read_text(encoding='utf-8'))
        for event in source['events']:fixture.post(event)
        fixture.post(dict(id='recovery-cash',date='2026-11-04',kind='correction',replaces='sale-cash',amount_minor=50000,reason='Clarify fictional cash sales',support_changes={'explanation':'Fictional recovery cash clarification'}))
        fixture.post(dict(id='recovery-payment',date='2026-11-04',kind='correction',replaces='owner-estimate',amount_minor=12500,reason='Correct fictional payment amount'))
        fixture.post(dict(id='recovery-payroll-original',date='2026-10-02',kind='employee_payroll_obligation',amount_minor=20000))
        fixture.post(dict(id='recovery-payroll-fixed',date='2026-11-04',kind='correction',replaces='recovery-payroll-original',amount_minor=25000,reason='Correct fictional payroll accrual'))
        return fixture

    def test_exact_latest_corrections_preserve_originals_and_projection(self):
        fixture=self.fixture()
        result=probe.verify_latest_corrections(fixture.ledger,fixture.owner,fixture.scope)
        self.assertTrue(result['original_cash_and_payment_preserved'])
        self.assertTrue(result['payroll_original_and_correction_preserved'])
        self.assertEqual(result['payroll_obligation_minor'],25000)
        self.assertEqual(result['recorded_payment_minor'],12500)
        self.assertEqual(result['confirmed_payment_minor'],0)

    def test_changed_original_or_confirmation_cannot_pass_restore_probe(self):
        for event_id,patch in (('sale-cash',{'explanation':'changed original'}),('recovery-payment',{'status':'government_confirmed'}),('recovery-payroll-original',{'amount_minor':1}),('recovery-payroll-fixed',{'effective_kind':'expense'})):
            fixture=self.fixture()
            event=next(event for event in fixture.ledger.store[fixture.scope] if event['id']==event_id)
            event.update(patch)
            with self.assertRaises(ValueError):probe.verify_latest_corrections(fixture.ledger,fixture.owner,fixture.scope)
