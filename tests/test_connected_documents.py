import unittest
from io import BytesIO
from tests import test_connected_access as access_tests
from ha.connected.documents import Documents, MemoryDocumentRepository, MemoryObjects


class DocumentTests(unittest.TestCase):
    def setUp(self):
        fixture = access_tests.AccessTests()
        fixture.setUp()
        self.repo, self.owner, self.scope = fixture.repo, fixture.owner, fixture.scope
        self.repo = MemoryDocumentRepository(self.repo)
        self.objects = MemoryObjects()
        self.documents = Documents(self.repo, self.objects, lambda data, mime: True)

    def test_original_and_correction_preserved_and_retry_idempotent(self):
        original = self.documents.upload(self.owner, self.scope, BytesIO(b'original fictional receipt'), 'text/plain', 'key1')
        again = self.documents.upload(self.owner, self.scope, BytesIO(b'original fictional receipt'), 'text/plain', 'key1')
        self.assertEqual(original, again)
        corrected = self.documents.correct(self.owner, self.scope, original.document_id, BytesIO(b'corrected fictional receipt'), 'text/plain', 'key2', 'Updated receipt')
        self.assertEqual(self.documents.read(self.owner, self.scope, original.document_id, original.version_id), b'original fictional receipt')
        self.assertEqual(self.documents.read(self.owner, self.scope, original.document_id, corrected.version_id), b'corrected fictional receipt')
        self.assertEqual(corrected.previous_version_id, original.version_id)
        with self.assertRaises(ValueError):
            self.documents.upload(self.owner, self.scope, BytesIO(b'conflict'), 'text/plain', 'key1')

    def test_wrong_scope_read_and_correct_denied_before_store(self):
        from ha.connected.domain import Scope
        original = self.documents.upload(self.owner, self.scope, BytesIO(b'receipt'), 'text/plain', 'key')
        calls = self.objects.read_count
        with self.assertRaises(PermissionError):
            self.documents.read(self.owner, Scope('cedar', 'cedar-business', 2026), original.document_id, original.version_id)
        self.assertEqual(self.objects.read_count, calls)
        self.repo.grants.clear()
        with self.assertRaises(PermissionError):
            self.documents.read(self.owner, self.scope, original.document_id, original.version_id)

    def test_scan_failure_and_invalid_type_do_not_publish(self):
        rejected = Documents(self.repo, self.objects, lambda data, mime: False)
        with self.assertRaises(ValueError):
            rejected.upload(self.owner, self.scope, BytesIO(b'bad'), 'text/plain', 'bad')
        with self.assertRaises(ValueError):
            self.documents.upload(self.owner, self.scope, BytesIO(b'not a pdf'), 'application/pdf', 'fakepdf')
        self.assertEqual(len(self.repo.versions), 0)

    def test_correction_uses_chain_head_even_when_repository_order_reverses(self):
        original = self.documents.upload(self.owner,self.scope,BytesIO(b'first'),'text/plain','first')
        corrected = self.documents.correct(self.owner,self.scope,original.document_id,BytesIO(b'second'),'text/plain','second','Updated')
        ordered = self.repo.list_versions
        self.repo.list_versions = lambda *args: list(reversed(ordered(*args)))
        latest = self.documents.correct(self.owner,self.scope,original.document_id,BytesIO(b'third'),'text/plain','third','Updated again')
        self.assertEqual(latest.previous_version_id, corrected.version_id)

    def test_integrity_corruption_detected_and_backup_restored(self):
        original = self.documents.upload(self.owner, self.scope, BytesIO(b'fictional receipt'), 'text/plain', 'key')
        backup = self.documents.backup(self.owner, self.scope)
        self.objects.data[original.object_key] = b'corrupt'
        with self.assertRaises(ValueError):
            self.documents.read(self.owner, self.scope, original.document_id, original.version_id)
        restored = self.documents.restore(self.owner, self.scope, backup)
        self.assertEqual(restored, 1)
        self.assertEqual(self.documents.read(self.owner, self.scope, original.document_id, original.version_id), b'fictional receipt')
        backup['objects'][original.version_id] = b'tampered'
        with self.assertRaises(ValueError):
            self.documents.restore(self.owner, self.scope, backup)
