import hashlib
from contextlib import contextmanager
from unittest.mock import patch
from pathlib import Path
import tempfile
import unittest
from cryptography.exceptions import InvalidTag
from ha.connected.backup_bundle import create_bundle,inspect_bundle,decrypted_bytes,MAX_MANIFEST
from ha.connected.documents import DocumentVersion
from ha.connected.domain import Scope

class Objects:
    def __init__(self):self.data=b'fictional receipt'
    def get(self,key,version):return self.data

class BundleTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory();self.addCleanup(self.folder.cleanup)
        self.root=Path(self.folder.name);self.dump=self.root/'fixture.dump';self.dump.write_bytes(b'fictional database')
        self.key=bytes(range(32));self.objects=Objects()
        self.version=DocumentVersion('doc','version',Scope('orchard','business',2026),'original',
            hashlib.sha256(self.objects.data).hexdigest(),'text/plain','owner','2026-10-02',None,'','immutable')
        self.target=self.root/'bundle'
    def create(self):return create_bundle('snapshot',self.dump,[self.version],self.objects,self.key,self.target)
    def test_completed_bundle_recovers_captured_bytes_and_contains_no_plaintext(self):
        self.create();metadata,reader=inspect_bundle(self.target,self.key,[self.version])
        self.assertEqual(reader.get('original','immutable'),self.objects.data)
        self.assertEqual(len(list(self.target.iterdir())),3)
        for item in self.target.iterdir():self.assertNotIn(b'fictional',item.read_bytes())
    def test_bad_object_leaves_no_completion_inventory_or_plaintext(self):
        self.objects.data=b'changed'
        with self.assertRaises(ValueError):self.create()
        self.assertFalse((self.target/'inventory.habackup').exists())
        with self.assertRaises(FileNotFoundError):inspect_bundle(self.target,self.key,[self.version])
        self.assertFalse(any(item.name.startswith('.ha-recovery-') for item in self.target.iterdir()))
    def test_existing_backup_is_not_replaced(self):
        self.create();before={item.name:item.read_bytes() for item in self.target.iterdir()}
        with self.assertRaises(FileExistsError):self.create()
        self.assertEqual(before,{item.name:item.read_bytes() for item in self.target.iterdir()})
    def test_wrong_key_or_changed_database_rejects_complete_bundle(self):
        self.create()
        with self.assertRaises(InvalidTag):inspect_bundle(self.target,bytes(32),[self.version])
        with (self.target/'database.habackup').open('ab') as file:file.write(b'altered')
        with self.assertRaises(ValueError):inspect_bundle(self.target,self.key,[self.version])

    def test_recovery_collision_preserves_preexisting_plaintext_target(self):
        self.create();existing=self.target/'reserved-plain';existing.write_bytes(b'preserve me')
        @contextmanager
        def reserved(parent):yield self.target/'reserved'
        with patch('ha.connected.backup_bundle.private_file',reserved),self.assertRaises(FileExistsError):
            decrypted_bytes(self.target/'inventory.habackup',self.key,MAX_MANIFEST)
        self.assertEqual(existing.read_bytes(),b'preserve me')

    def test_failed_completion_directory_sync_does_not_leave_completed_marker(self):
        with patch('ha.connected.backup_bundle.sync_directory',side_effect=[None,OSError('sync failed')]),self.assertRaises(OSError):
            self.create()
        self.assertFalse((self.target/'inventory.habackup').exists())
