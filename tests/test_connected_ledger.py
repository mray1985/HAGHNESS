import json
import unittest
from pathlib import Path
from datetime import datetime, timedelta, timezone
from tests.test_connected_access import Repository
from ha.connected.domain import Principal, Scope
from ha.connected.ledger import Ledger


class LedgerTests(unittest.TestCase):
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
