import unittest
from ha.connected.return_draft import estimate_connected_return
from tests import test_connected_ledger as ledger_tests

class ConnectedReturnTests(unittest.TestCase):
    def setUp(self):
        fixture=ledger_tests.LedgerTests();fixture.setUp()
        self.fixture=fixture

    def test_saved_books_hold_incomplete_wage_only_refund(self):
        f=self.fixture
        f.post({'id':'sale','date':'2026-10-01','kind':'income','amount_minor':150000})
        result=estimate_connected_return(f.ledger,f.owner,f.scope,{'tax_year':'2026','w2s':[{'box1':45000,'box2':5200}]})
        self.assertEqual(result['business_draft']['book_profit_minor'],150000)
        self.assertIsNone(result['refund'])
        self.assertIsNone(result['balance_due'])
        self.assertIsNone(result['estimated_tax'])
        self.assertTrue(result['needs_review'])
        self.assertEqual(result['review_items'][-1]['form'],'HA Bookin')
        self.assertEqual(result['business_draft']['entry_completeness'],'not_verified')
        self.assertIsNone(result['business_draft']['missing_entries'])
        self.assertIn('Entry completeness has not been verified',result['review_items'][-1]['reasons'][0])

    def test_scope_and_year_cannot_be_changed_to_bypass_authorization(self):
        from ha.connected.domain import Scope
        f=self.fixture
        with self.assertRaises(PermissionError):estimate_connected_return(f.ledger,f.owner,Scope('cedar','cedar-business',2026),{'tax_year':'2026'})
        with self.assertRaises(ValueError):estimate_connected_return(f.ledger,f.owner,f.scope,{'tax_year':'2025'})
