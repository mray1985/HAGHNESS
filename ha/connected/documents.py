"""Authorized immutable document versions; volatile adapters are test-only."""
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import uuid
from threading import RLock
from .access import authorize

MAX_BYTES = 20 * 1024 * 1024


@dataclass(frozen=True)
class DocumentVersion:
    document_id: str
    version_id: str
    scope: object
    object_key: str
    sha256: str
    mime: str
    actor: str
    created_at: str
    previous_version_id: str | None
    reason: str
    storage_version: str


class MemoryObjects:
    """Unencrypted volatile test double, never selected by production setup."""
    def __init__(self):
        self.data, self.read_count = {}, 0

    def put(self, key, data, mime):
        if key in self.data:
            raise ValueError('Object already exists')
        self.data[key] = bytes(data)
        return 'test-version'

    def get(self, key, version):
        self.read_count += 1
        return self.data[key]


class MemoryDocumentRepository:
    def __init__(self, permissions):
        self.permissions = permissions
        self.versions, self.retries, self.lock = {}, {}, RLock()

    @property
    def grants(self):
        return self.permissions.grants

    def grants_for(self, subject):
        return self.permissions.grants_for(subject)

    def profile_for_business(self, business):
        return self.permissions.profile_for_business(business)

    def retry(self, scope, key):
        return self.retries.get((scope, key))

    def document_transaction(self, scope):
        return self.lock

    def add_version(self, version, key, fingerprint):
        self.versions[version.version_id] = version
        self.retries[(version.scope, key)] = (fingerprint, version)

    def get_version(self, scope, document, version):
        found = self.versions.get(version)
        if found is None or found.scope != scope or found.document_id != document:
            raise PermissionError('Resource unavailable')
        return found

    def list_versions(self, scope, document=None):
        return [v for v in self.versions.values() if v.scope == scope and (document is None or v.document_id == document)]


class Documents:
    def __init__(self, repository, objects, scanner):
        self.repository, self.objects, self.scanner = repository, objects, scanner
        self.lock = RLock()

    def upload(self, principal, scope, stream, mime, idempotency_key):
        authorize(principal, scope, 'upload', self.repository)
        return self._write(principal, scope, stream, mime, idempotency_key, None, '')

    def correct(self, principal, scope, document_id, stream, mime, idempotency_key, reason):
        authorize(principal, scope, 'correct', self.repository)
        if not isinstance(document_id,str) or not document_id.strip() or len(document_id)>200:
            raise ValueError('Existing document ID required')
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 2000:
            raise ValueError('Correction reason required')
        return self._write(principal, scope, stream, mime, idempotency_key, document_id, reason)

    def _write(self, principal, scope, stream, mime, key, document, reason):
        if not isinstance(key, str) or not key or len(key) > 200:
            raise ValueError('Idempotency key required')
        data = stream.read(MAX_BYTES + 1)
        if not isinstance(data, bytes) or not data or len(data) > MAX_BYTES:
            raise ValueError('Invalid document size')
        signatures = {'application/pdf': b'%PDF-', 'image/png': b'\x89PNG\r\n\x1a\n', 'image/jpeg': b'\xff\xd8\xff'}
        if mime == 'text/plain':
            data.decode('utf-8')
        elif mime not in signatures or not data.startswith(signatures[mime]):
            raise ValueError('Invalid document type')
        digest = hashlib.sha256(data).hexdigest()
        fingerprint = (document, reason, mime, digest)
        with self.repository.document_transaction(scope):
            retry = self.repository.retry(scope, key)
            if retry:
                if retry[0] != fingerprint:
                    raise ValueError('Conflicting retry')
                return retry[1]
            if self.scanner(data, mime) is not True:
                raise ValueError('Document scan not clean')
            previous = None
            if document:
                versions = self.repository.list_versions(scope, document)
                if not versions:
                    raise PermissionError('Resource unavailable')
                predecessors = {v.previous_version_id for v in versions if v.previous_version_id}
                heads = [v for v in versions if v.version_id not in predecessors]
                if len(heads) != 1:
                    raise ValueError('Document version chain needs review')
                previous = heads[0].version_id
            else:
                document = str(uuid.uuid4())
            version_id = str(uuid.uuid4())
            object_key = 'documents/' + version_id
            storage_version = self.objects.put(object_key, data, mime)
            if not storage_version:
                raise ValueError('Storage did not confirm version')
            version = DocumentVersion(document, version_id, scope, object_key, digest, mime,
                                      principal.subject, datetime.now(timezone.utc).isoformat(), previous, reason, storage_version)
            self.repository.add_version(version, key, fingerprint)
            return version

    def read(self, principal, scope, document_id, version_id):
        authorize(principal, scope, 'read', self.repository)
        version = self.repository.get_version(scope, document_id, version_id)
        data = self.objects.get(version.object_key, version.storage_version)
        if hashlib.sha256(data).hexdigest() != version.sha256:
            raise ValueError('Document integrity failure')
        return data

    def backup(self, principal, scope):
        authorize(principal, scope, 'restore', self.repository)
        versions = self.repository.list_versions(scope)
        return {'scope': scope, 'versions': deepcopy(versions),
                'objects': {v.version_id: self.read(principal, scope, v.document_id, v.version_id) for v in versions}}

    def restore(self, principal, scope, backup):
        """Reconcile bytes against current metadata; does not replace AWS Backup."""
        authorize(principal, scope, 'restore', self.repository)
        if backup['scope'] != scope:
            raise PermissionError('Resource unavailable')
        validated = []
        for version in backup['versions']:
            current = self.repository.get_version(scope, version.document_id, version.version_id)
            data = backup['objects'][version.version_id]
            if current != version or hashlib.sha256(data).hexdigest() != current.sha256:
                raise ValueError('Backup reconciliation failure')
            validated.append((current, data))
        if not hasattr(self.objects, 'restore'):
            if not isinstance(self.objects, MemoryObjects):
                raise ValueError('Provider restore requires isolated recovery resources')
            for version, data in validated:
                self.objects.data[version.object_key] = bytes(data)
        else:
            for version, data in validated:
                self.objects.restore(version, data)
        return len(validated)
