"""Transactional saved tax inputs; no tax computation or filing authorization."""
import hashlib
from io import BytesIO
import uuid
from .access import authorize
from .support_review import fingerprint
from .tax_snapshot import encode_snapshot, decode_snapshot


class TaxInputs:
    def __init__(self, repository, documents):
        if documents.repository is not repository:
            raise ValueError('Shared transactional repository required')
        self.repository, self.documents = repository, documents

    @staticmethod
    def reference(row):
        fields = ('snapshot_id','document_id','version_id','previous_snapshot_id','actor','recorded_at','reason')
        result = dict(zip(fields,row))
        result['snapshot_id'] = str(row[0])
        result['previous_snapshot_id'] = str(row[3]) if row[3] else None
        result['recorded_at'] = row[5].isoformat()
        return result

    def history(self, principal, scope):
        repo = self.repository
        with repo.transaction() as conn:
            authorize(principal,scope,'read',repo)
            rows = conn.execute('SELECT snapshot_id,document_id,version_id,previous_snapshot_id,actor,recorded_at,reason '
                'FROM ha_connected.tax_input_versions WHERE profile_id=%s AND business_id=%s AND tax_year=%s ORDER BY seq',
                repo.scope_values(scope)).fetchall()
            return [self.reference(row) for row in rows]

    def view(self, principal, scope):
        with self.repository.transaction():
            history = self.history(principal,scope)
            try:
                authorize(principal,scope,'save_tax',self.repository)
                authorize(principal,scope,'correct' if history else 'upload',self.repository)
                can_save = True
            except PermissionError:
                can_save = False
            return {'history':history,'can_save':can_save}

    def open(self, principal, scope, snapshot_id=None):
        with self.repository.transaction():
            history = self.history(principal,scope)
            if snapshot_id is None:
                selected = history[-1] if history else None
            else:
                selected = next((item for item in history if item['snapshot_id'] == snapshot_id),None)
                if selected is None:
                    raise PermissionError('Resource unavailable')
            if selected is None:
                return {'snapshot':None,'input':None}
            data = self.documents.read(principal,scope,selected['document_id'],selected['version_id'])
            return {'snapshot':selected,'input':decode_snapshot(data,scope.tax_year)}

    def save(self, principal, scope, request):
        repo = self.repository
        with repo.transaction() as conn:
            authorize(principal,scope,'read',repo)
            authorize(principal,scope,'save_tax',repo)
            repo.lock_scope(conn,scope)
            if not isinstance(request,dict) or set(request) != {'input','expected_snapshot_id','reason','idempotency_key'}:
                raise ValueError('Explicit saved-input request required')
            key, reason, expected = request['idempotency_key'],request['reason'],request['expected_snapshot_id']
            if not isinstance(key,str) or not key.strip() or len(key)>128:
                raise ValueError('Bounded idempotency key required')
            if not isinstance(reason,str) or len(reason)>2000:
                raise ValueError('Bounded correction reason required')
            if expected is not None:
                if not isinstance(expected,str) or len(expected)!=36:
                    raise ValueError('Valid expected snapshot required')
                expected = str(uuid.UUID(expected))
            data = encode_snapshot(request['input'],scope.tax_year)
            request_hash = fingerprint({'sha256':hashlib.sha256(data).hexdigest(),'expected':expected,'reason':reason})
            values = repo.scope_values(scope)
            retry = conn.execute('SELECT snapshot_id,request_fingerprint FROM ha_connected.tax_input_versions '
                'WHERE profile_id=%s AND business_id=%s AND tax_year=%s AND idempotency_key=%s',(*values,key)).fetchone()
            if retry:
                if retry[1] != request_hash:
                    raise ValueError('Conflicting saved-input retry')
                return next(item for item in self.history(principal,scope) if item['snapshot_id']==str(retry[0]))
            history = self.history(principal,scope)
            latest = history[-1] if history else None
            if expected != (latest['snapshot_id'] if latest else None):
                raise ValueError('Saved input changed; reopen before editing')
            document_key = 'tax-input:' + key
            if latest:
                if not reason.strip():
                    raise ValueError('Correction reason required')
                if any(v.previous_version_id == latest['version_id'] for v in repo.list_versions(scope,latest['document_id'])):
                    raise ValueError('Linked document changed; review required')
                # Authenticate the prior version before extending its history.
                self.documents.read(principal,scope,latest['document_id'],latest['version_id'])
                version = self.documents.correct(principal,scope,latest['document_id'],BytesIO(data),
                    'text/plain',document_key,reason)
            else:
                version = self.documents.upload(principal,scope,BytesIO(data),'text/plain',document_key)
            snapshot = uuid.uuid4()
            conn.execute('INSERT INTO ha_connected.tax_input_versions '
                '(snapshot_id,profile_id,business_id,tax_year,document_id,version_id,previous_snapshot_id,'
                'actor,reason,idempotency_key,request_fingerprint) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                (snapshot,*values,version.document_id,version.version_id,expected,principal.subject,reason,key,request_hash))
            return self.history(principal,scope)[-1]
