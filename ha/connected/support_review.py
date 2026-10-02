"""Authorized append-only support decisions; not tax or filing approval."""
import hashlib
import json
import uuid
from .access import authorize
from .ledger import Ledger, has_text


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=False).encode()).hexdigest()


class SupportReviews:
    def __init__(self, repository, documents):
        if documents.repository is not repository:
            raise ValueError('Shared transactional repository required')
        self.repository, self.documents = repository, documents

    def submit(self, principal, scope, request):
        fields = {'event_id', 'decision', 'reason', 'idempotency_key', 'document_id', 'version_id'}
        if not isinstance(request, dict) or set(request) - fields:
            raise ValueError('Unsupported review fields')
        for name, maximum in (('event_id', 128), ('reason', 2000), ('idempotency_key', 128)):
            if not has_text(request.get(name)) or len(request[name]) > maximum:
                raise ValueError('Bounded review fields required')
        if request.get('decision') not in ('accepted', 'needs_information'):
            raise ValueError('Explicit support decision required')
        document, version = request.get('document_id'), request.get('version_id')
        if (document is None) != (version is None):
            raise ValueError('Complete document reference required')
        if document is not None and any(not has_text(v) or len(v) > 128 for v in (document, version)):
            raise ValueError('Bounded document reference required')
        canonical = {name: request.get(name) for name in sorted(fields)}
        request_hash = fingerprint(canonical)
        repo = self.repository
        with repo.transaction() as conn:
            authorize(principal, scope, 'review_support', repo)
            authorize(principal, scope, 'read', repo)
            repo.lock_scope(conn, scope)
            values = repo.scope_values(scope)
            previous = conn.execute('SELECT decision_id,request_fingerprint FROM ha_connected.support_reviews '
                                    'WHERE profile_id=%s AND business_id=%s AND tax_year=%s AND idempotency_key=%s',
                                    (*values, request['idempotency_key'])).fetchone()
            if previous:
                if previous[1] != request_hash: raise ValueError('Conflicting review retry')
                return {'decision_id': str(previous[0]), 'decision': request['decision']}
            events = Ledger._effective(repo.events(conn, scope))
            event = next((e for e in events if e['id'] == request['event_id']), None)
            if event is None or event['effective_kind'] not in ('income', 'expense', 'employee_payroll_obligation'):
                raise ValueError('Current operating event required')
            if document is not None:
                repo.get_version(scope, document, version)
                if any(v.previous_version_id == version for v in repo.list_versions(scope, document)):
                    raise ValueError('Current document version required')
                self.documents.read(principal, scope, document, version)
            if request['decision'] == 'accepted':
                if event['effective_kind'] == 'expense' and document is None:
                    raise ValueError('Expense receipt required')
                if event.get('method') == 'cash' and not has_text(event.get('explanation')):
                    raise ValueError('Cash explanation required')
            decision_id = uuid.uuid4()
            conn.execute('INSERT INTO ha_connected.support_reviews '
                '(decision_id,profile_id,business_id,tax_year,event_id,event_fingerprint,document_id,version_id,'
                'decision,reason,actor,idempotency_key,request_fingerprint) '
                'VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                (decision_id,*values,event['id'],fingerprint(event),document,version,request['decision'],
                 request['reason'],principal.subject,request['idempotency_key'],request_hash))
            return {'decision_id': str(decision_id), 'decision': request['decision']}

    def history(self, principal, scope):
        repo = self.repository
        with repo.transaction() as conn:
            authorize(principal, scope, 'read', repo)
            rows = conn.execute('SELECT decision_id,event_id,event_fingerprint,document_id,version_id,'
                'decision,reason,actor,recorded_at FROM ha_connected.support_reviews '
                'WHERE profile_id=%s AND business_id=%s AND tax_year=%s ORDER BY seq',
                repo.scope_values(scope)).fetchall()
            fields = ('decision_id','event_id','event_fingerprint','document_id','version_id',
                      'decision','reason','actor','recorded_at')
            return [{**dict(zip(fields,row)), 'decision_id':str(row[0]),
                     'recorded_at':row[-1].isoformat()} for row in rows]
