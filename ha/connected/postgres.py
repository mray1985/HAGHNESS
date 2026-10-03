"""Durable repository and serialized ledger transactions for PostgreSQL."""
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import timezone
from pathlib import Path
import psycopg
from psycopg.types.json import Jsonb
from .domain import Grant, Scope
from .ledger import Ledger
from .access import authorize
from .documents import DocumentVersion


class PostgresRepository:
    def __init__(self, dsn):
        self.dsn = dsn
        self.active = ContextVar('connected_connection', default=None)

    @contextmanager
    def transaction(self):
        existing = self.active.get()
        if existing is not None:
            yield existing
            return
        with psycopg.connect(self.dsn, connect_timeout=5) as conn:
            token = self.active.set(conn)
            try:
                yield conn
            finally:
                self.active.reset(token)

    def migrate(self):
        folder = Path(__file__).resolve().parents[2]/'migrations'
        with self.transaction() as conn:
            conn.execute("SELECT pg_advisory_xact_lock(hashtextextended('ha-schema-migrations',0))")
            for name in ('001_connected.sql','002_support_reviews.sql','003_tax_input_versions.sql','004_record_confirmations.sql'):
                conn.execute((folder/name).read_text(encoding='utf-8'))

    def profile_for_business(self, business):
        with self.transaction() as conn:
            row = conn.execute('SELECT profile_id FROM ha_connected.businesses WHERE business_id=%s', (business,)).fetchone()
            return row[0] if row else None

    def grants_for(self, subject):
        with self.transaction() as conn:
            rows = conn.execute('SELECT profile_id,business_id,tax_year,action FROM ha_connected.grants WHERE subject=%s',(subject,)).fetchall()
            return [Grant(subject,Scope(p,b,y),frozenset({a})) for p,b,y,a in rows]

    def read_cases_for(self, subject):
        """Read-granted cases whose business still belongs to the granted profile."""
        with self.transaction() as conn:
            rows = conn.execute(
                'SELECT g.profile_id,g.business_id,g.tax_year '
                'FROM ha_connected.grants g '
                'JOIN ha_connected.businesses b ON b.business_id=g.business_id '
                'AND b.profile_id=g.profile_id '
                "WHERE g.subject=%s AND g.action='read' "
                'AND g.tax_year BETWEEN 2023 AND 2026 '
                'AND g.profile_id<>\'\' AND g.business_id<>\'\' '
                'ORDER BY g.profile_id COLLATE "C",g.business_id COLLATE "C",g.tax_year',
                (subject,)).fetchall()
            return [{'profile':p,'business':b,'year':y} for p,b,y in rows]

    @staticmethod
    def scope_values(scope):
        return (scope.profile_id,scope.business_id,scope.tax_year)

    def lock_scope(self, conn, scope):
        conn.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',
                     ('|'.join(map(str,self.scope_values(scope))),))

    def events(self, conn, scope):
        return [row[0] for row in conn.execute('SELECT record FROM ha_connected.ledger_events WHERE profile_id=%s AND business_id=%s AND tax_year=%s ORDER BY seq',self.scope_values(scope)).fetchall()]

    @contextmanager
    def document_transaction(self, scope):
        with self.transaction() as conn:
            self.lock_scope(conn, scope)
            yield conn

    @staticmethod
    def _version(row):
        return DocumentVersion(row[1],row[0],Scope(row[2],row[3],row[4]),row[5],row[6],row[7],row[8],
                               row[9].astimezone(timezone.utc).isoformat(),row[10],row[11],row[12])

    def retry(self, scope, key):
        with self.transaction() as conn:
            row = conn.execute('SELECT * FROM ha_connected.document_versions WHERE profile_id=%s AND business_id=%s AND tax_year=%s AND idempotency_key=%s',(*self.scope_values(scope),key)).fetchone()
            if row:
                return tuple(row[14]), self._version(row)
            return None

    def add_version(self, version, key, fingerprint):
        with self.transaction() as conn:
            if version.previous_version_id:
                self.get_version(version.scope,version.document_id,version.previous_version_id)
            conn.execute('INSERT INTO ha_connected.document_versions VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                (version.version_id,version.document_id,*self.scope_values(version.scope),version.object_key,version.sha256,
                 version.mime,version.actor,version.created_at,version.previous_version_id,version.reason,version.storage_version,key,Jsonb(fingerprint)))

    def get_version(self, scope, document, version):
        with self.transaction() as conn:
            row = conn.execute('SELECT * FROM ha_connected.document_versions WHERE profile_id=%s AND business_id=%s AND tax_year=%s AND document_id=%s AND version_id=%s',(*self.scope_values(scope),document,version)).fetchone()
            if row is None:
                raise PermissionError('Resource unavailable')
            return self._version(row)

    def list_versions(self, scope, document=None):
        with self.transaction() as conn:
            rows = conn.execute('SELECT * FROM ha_connected.document_versions WHERE profile_id=%s AND business_id=%s AND tax_year=%s AND (%s::text IS NULL OR document_id=%s) ORDER BY created_at,version_id',(*self.scope_values(scope),document,document)).fetchall()
            return [self._version(row) for row in rows]


class PostgresLedger:
    def __init__(self, repository):
        self.repository = repository

    def post_event(self, principal, scope, event):
        with self.repository.transaction() as conn:
            authorize(principal,scope,'post',self.repository)
            self.repository.lock_scope(conn,scope)
            old = self.repository.events(conn,scope)
            ledger = Ledger(self.repository,{scope:old})
            count = len(old)
            result = ledger.post_event(principal,scope,event)
            if len(old) > count:
                conn.execute('INSERT INTO ha_connected.ledger_events(profile_id,business_id,tax_year,event_id,record) VALUES (%s,%s,%s,%s,%s)',
                             (*self.repository.scope_values(scope),result['id'],Jsonb(result)))
            return result

    def history(self, principal, scope):
        with self.repository.transaction() as conn:
            authorize(principal,scope,'read',self.repository)
            return self.repository.events(conn,scope)

    def project(self, principal, scope, period, month=1, reserve_rate='0.25', *, reserve_extra_minor=0):
        with self.repository.transaction() as conn:
            authorize(principal,scope,'read',self.repository)
            self.repository.lock_scope(conn,scope)
            events=self.repository.events(conn,scope)
            ledger = Ledger(self.repository,{scope:events})
            projection=ledger.project(principal,scope,period,month,reserve_rate,reserve_extra_minor=reserve_extra_minor)
            rows=conn.execute('SELECT event_id,event_fingerprint,document_id,version_id,decision '
                'FROM ha_connected.support_reviews WHERE profile_id=%s AND business_id=%s AND tax_year=%s ORDER BY seq',
                self.repository.scope_values(scope)).fetchall()
            reviews=[dict(zip(('event_id','event_fingerprint','document_id','version_id','decision'),row)) for row in rows]
            from .support_review import apply_support_reviews
            projection = apply_support_reviews(projection,events,reviews,self.repository.list_versions(scope))
            from .record_confirmation import RecordConfirmations, confirmation_status
            history = RecordConfirmations(self.repository)._history(conn,scope)
            projection['records_confirmation'] = confirmation_status(events,history)
            return projection
