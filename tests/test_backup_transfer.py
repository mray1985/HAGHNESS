from io import BytesIO
import unittest
from unittest.mock import patch
from tests import test_backup_bundle as fixture
from ha.connected.backup_transfer import copy_bundle


class Store:
    def __init__(self, corrupt=False):
        self.files, self.order, self.corrupt = {}, [], corrupt
    def upload_fileobj(self, reader, bucket, name, ExtraArgs):
        assert ExtraArgs['ACL'] == 'private'
        self.files[name] = reader.read()
        self.order.append(name)
    def get_object(self, Bucket, Key):
        data = self.files[Key]
        return {'Body': BytesIO(data + b'bad' if self.corrupt is True or (self.corrupt == 'inventory' and Key.endswith('/inventory.habackup')) else data)}


class TransferTests(unittest.TestCase):
    setUp = fixture.BundleTests.setUp
    create = fixture.BundleTests.create
    def test_copy_reads_back_ciphertext_and_publishes_inventory_last(self):
        self.create(); store = Store()
        result = copy_bundle(self.target, self.key, [self.version], store, 'private-backups')
        self.assertTrue(result['completed'])
        self.assertEqual(result['artifacts'], 3)
        self.assertTrue(store.order[-1].endswith('/inventory.habackup'))
        for name, data in store.files.items():
            self.assertEqual(data, (self.target / name.split('/')[-1]).read_bytes())
    def test_failed_readback_does_not_upload_completion_inventory(self):
        self.create(); store = Store(corrupt=True)
        with self.assertRaises(ValueError):
            copy_bundle(self.target, self.key, [self.version], store, 'private-backups')
        self.assertFalse(any(name.endswith('/inventory.habackup') for name in store.order))
    def test_invalid_local_bundle_never_reaches_store(self):
        self.create(); store = Store()
        with patch('ha.connected.backup_transfer.inspect_bundle', side_effect=ValueError('invalid')):
            with self.assertRaises(ValueError):
                copy_bundle(self.target, self.key, [self.version], store, 'private-backups')
        self.assertEqual(store.order, [])

    def test_source_change_after_initial_inspection_cannot_complete(self):
        self.create(); store = Store()
        from ha.connected.backup_bundle import inspect_bundle
        def mutate(root, key, versions):
            result = inspect_bundle(root, key, versions)
            (self.target / 'database.habackup').write_bytes(b'altered ciphertext')
            return result
        with patch('ha.connected.backup_transfer.inspect_bundle', side_effect=mutate):
            with self.assertRaises(ValueError):
                copy_bundle(self.target, self.key, [self.version], store, 'private-backups')
        self.assertEqual(store.order, [])
        self.assertFalse(any(p.name.startswith('.ha-transfer-') for p in self.root.iterdir()))

    def test_final_inventory_readback_failure_is_not_success(self):
        self.create(); store = Store(corrupt='inventory')
        with self.assertRaises(ValueError):
            copy_bundle(self.target, self.key, [self.version], store, 'private-backups')
        self.assertTrue(store.order[-1].endswith('/inventory.habackup'))
