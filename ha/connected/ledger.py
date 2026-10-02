"""Append-only posting rules and traceable book projections.

Ledger's default event store is volatile for synthetic tests. Deployments must
inject a transactional durable store; this is not a complete tax engine.
"""
from copy import deepcopy
from datetime import date
from threading import RLock
from decimal import Decimal, ROUND_HALF_UP
from .access import authorize


class Ledger:
    def __init__(self, repository, event_store=None):
        self.repository = repository
        self.store = event_store if event_store is not None else {}
        self.lock = RLock()

    def post_event(self, principal, scope, event):
        authorize(principal, scope, 'post', self.repository)
        event = deepcopy(event)
        if not isinstance(event, dict) or not isinstance(event.get('id'), str) or not event['id']:
            raise ValueError('Event ID required')
        if type(event.get('amount_minor')) is not int or not 0 <= event['amount_minor'] <= 10**15:
            raise ValueError('Money must be nonnegative integer minor units')
        day = date.fromisoformat(event['date'])
        if day.year != scope.tax_year or event.get('currency', 'USD') != 'USD':
            raise ValueError('Year or currency unsupported')
        kind = event.get('kind')
        if kind not in ('income', 'expense', 'correction', 'owner_estimated_tax_payment', 'employee_payroll_obligation'):
            raise ValueError('Event kind unsupported')
        if kind == 'owner_estimated_tax_payment' and (event.get('status') != 'recorded_unverified' or event.get('government_confirmation')):
            raise ValueError('User entry cannot establish government payment confirmation')
        with self.lock:
            events = self.store.setdefault(scope, [])
            existing = next((e for e in events if e['id'] == event['id']), None)
            if existing:
                if existing['source'] != event:
                    raise ValueError('Conflicting retry')
                return deepcopy(existing)
            effective = self._effective(events)
            if kind == 'correction':
                authorize(principal, scope, 'correct', self.repository)
                old = next((e for e in effective if e['id'] == event.get('replaces')), None)
                if old is None or old['effective_kind'] not in ('income', 'expense') or not event.get('reason'):
                    raise ValueError('Correction requires current operating event and reason')
                effective_kind = old['effective_kind']
                evidence = old.get('evidence')
                posting_date = old['posting_date']
            else:
                effective_kind, evidence, posting_date = kind, event.get('evidence'), event['date']
            accounts = {
                'income': ('cash_or_bank', 'business_income'),
                'expense': ('business_expense', 'cash_or_bank'),
                'owner_estimated_tax_payment': ('owner_distribution', 'cash_or_bank'),
                'employee_payroll_obligation': ('payroll_expense', 'payroll_payable'),
            }
            debit, credit = accounts[effective_kind]
            amount = event['amount_minor']
            postings = [{'account': debit, 'amount_minor': amount}, {'account': credit, 'amount_minor': -amount}]
            if kind == 'correction':
                postings = [{'account': p['account'], 'amount_minor': -p['amount_minor']} for p in old['replacement_postings']] + postings
            record = {**event, 'source': event, 'actor': principal.subject, 'effective_kind': effective_kind,
                      'evidence': evidence, 'posting_date': posting_date, 'postings': postings,
                      'replacement_postings': [{'account': debit, 'amount_minor': amount}, {'account': credit, 'amount_minor': -amount}]}
            events.append(record)
            return deepcopy(record)

    @staticmethod
    def _effective(events):
        superseded = {e['replaces'] for e in events if e['kind'] == 'correction'}
        return [e for e in events if e['id'] not in superseded]

    def history(self, principal, scope):
        authorize(principal, scope, 'read', self.repository)
        with self.lock:
            return deepcopy(self.store.get(scope, []))

    def project(self, principal, scope, period, month=1, reserve_rate='0.25'):
        authorize(principal, scope, 'read', self.repository)
        if period not in ('month', 'quarter', 'year') or type(month) is not int or not 1 <= month <= 12:
            raise ValueError('Invalid reporting period')
        rate = Decimal(reserve_rate)
        if not rate.is_finite() or not 0 <= rate <= 1:
            raise ValueError('Invalid reserve rate')
        history = self.history(principal, scope)
        first = 1 if period == 'year' else ((month - 1) // 3) * 3 + 1 if period == 'quarter' else month
        last = 12 if period == 'year' else first + 2 if period == 'quarter' else month
        effective = [e for e in self._effective(history) if first <= date.fromisoformat(e['posting_date']).month <= last]
        income = sum(e['amount_minor'] for e in effective if e['effective_kind'] == 'income')
        expense = sum(e['amount_minor'] for e in effective if e['effective_kind'] in ('expense', 'employee_payroll_obligation'))
        payments = [e for e in effective if e['effective_kind'] == 'owner_estimated_tax_payment']
        return {'ledger_revision': len(history), 'income_minor': income, 'expense_minor': expense,
                'book_profit_minor': income - expense,
                'reserve_scenario_minor': int((income * rate).quantize(Decimal('1'), rounding=ROUND_HALF_UP)),
                'reserve_basis': 'recorded_receipts', 'reserve_moves_money': False,
                'owner_payments_recorded_minor': sum(e['amount_minor'] for e in payments),
                'owner_payments_confirmed_minor': sum(e['amount_minor'] for e in payments if e.get('status') == 'government_confirmed'),
                'missing_receipts': [e['id'] for e in effective if e['effective_kind'] == 'expense' and not e.get('evidence')],
                'source_event_ids': [e['id'] for e in effective], 'tax_liability_minor': None,
                'may_prepare_return': False, 'filing_authorized': False}
