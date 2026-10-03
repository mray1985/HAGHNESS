"""Append-only user statements about entered records, never independent verification."""
from datetime import date, datetime, timezone
import uuid
from .access import authorize
from .ledger import has_text
from .support_review import fingerprint

STATEMENT_VERSION = 'records-v1'
STATEMENT = ('I reviewed income and expenses for this business and tax year through the date shown. '
             'To the best of my knowledge, I have entered them accurately and know of no omitted '
             'income or expense for that period. This is my statement, not independent verification '
             'of receipts, tax treatment, a final return or filing authorization.')
FIELDS = ('confirmation_id','ledger_revision','ledger_fingerprint','reviewed_through',
          'statement_version','reason','actor','recorded_at')


def confirmation_status(events, history):
    latest = history[-1] if history else None
    current = (latest is not None and latest['ledger_revision'] == len(events)
               and latest['ledger_fingerprint'] == fingerprint(events))
    return {'status': 'current' if current else 'stale' if latest else 'not_recorded',
            'latest': latest, 'independently_verified': False}


class RecordConfirmations:
    def __init__(self, repository):
        self.repository = repository

    def _history(self, conn, scope):
        rows = conn.execute('SELECT '+','.join(FIELDS)+' FROM ha_connected.record_confirmations '
            'WHERE profile_id=%s AND business_id=%s AND tax_year=%s ORDER BY seq',
            self.repository.scope_values(scope)).fetchall()
        return [{**dict(zip(FIELDS,row)), 'confirmation_id':str(row[0]),
                 'reviewed_through':row[3].isoformat(), 'recorded_at':row[7].isoformat()} for row in rows]

    def view(self, principal, scope):
        repo = self.repository
        with repo.transaction() as conn:
            authorize(principal,scope,'read',repo)
            repo.lock_scope(conn,scope)
            events = repo.events(conn,scope)
            history = self._history(conn,scope)
            try:
                authorize(principal,scope,'confirm_records',repo)
                can_confirm = True
            except PermissionError:
                can_confirm = False
            return {**confirmation_status(events,history), 'history':history, 'can_confirm':can_confirm,
                    'ledger_revision':len(events), 'statement':STATEMENT, 'statement_version':STATEMENT_VERSION,
                    'today':datetime.now(timezone.utc).date().isoformat()}

    def submit(self, principal, scope, request):
        fields = {'ledger_revision','reviewed_through','confirmed','reason','idempotency_key'}
        if not isinstance(request,dict) or set(request) != fields:
            raise ValueError('Explicit record confirmation fields required')
        if request['confirmed'] is not True or type(request['ledger_revision']) is not int or request['ledger_revision'] < 0:
            raise ValueError('Explicit choice and ledger revision required')
        for field,limit in (('reason',2000),('idempotency_key',128)):
            if not has_text(request[field]) or len(request[field]) > limit:
                raise ValueError('Bounded confirmation fields required')
        through = date.fromisoformat(request['reviewed_through'])
        if (through.isoformat() != request['reviewed_through'] or through.year != scope.tax_year
                or through > datetime.now(timezone.utc).date()):
            raise ValueError('Review date must be in the tax year and not in the future')
        request_hash = fingerprint(request)
        repo = self.repository
        with repo.transaction() as conn:
            authorize(principal,scope,'read',repo)
            authorize(principal,scope,'confirm_records',repo)
            repo.lock_scope(conn,scope)
            values = repo.scope_values(scope)
            previous = conn.execute('SELECT confirmation_id,request_fingerprint FROM ha_connected.record_confirmations '
                'WHERE profile_id=%s AND business_id=%s AND tax_year=%s AND idempotency_key=%s',
                (*values,request['idempotency_key'])).fetchone()
            if previous:
                if previous[1] != request_hash:
                    raise ValueError('Conflicting confirmation retry')
                return {'confirmation_id':str(previous[0])}
            events = repo.events(conn,scope)
            if len(events) != request['ledger_revision']:
                raise ValueError('Records changed; reopen and review the current entries')
            if any(date.fromisoformat(e['posting_date']) > through for e in events):
                raise ValueError('Review date must include all recorded posting dates')
            confirmation_id = uuid.uuid4()
            conn.execute('INSERT INTO ha_connected.record_confirmations '
                '(confirmation_id,profile_id,business_id,tax_year,ledger_revision,ledger_fingerprint,'
                'reviewed_through,statement_version,reason,actor,idempotency_key,request_fingerprint) '
                'VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                (confirmation_id,*values,len(events),fingerprint(events),through,STATEMENT_VERSION,
                 request['reason'],principal.subject,request['idempotency_key'],request_hash))
            return {'confirmation_id':str(confirmation_id)}
