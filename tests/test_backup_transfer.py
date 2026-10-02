from io import BytesIO
import unittest
from unittest.mock import patch
from tests import test_backup_bundle as fixture
from ha.connected.backup_transfer import copy_bundle, recover_bundle


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

    def uploaded(self):
        self.create(); store = Store()
        result = copy_bundle(self.target, self.key, [self.version], store, 'private-backups')
        return store, result['prefix']

    def test_recovery_download_preserves_captured_bytes(self):
        store, prefix = self.uploaded(); destination = self.root / 'recovered'
        result = recover_bundle(store, 'private-backups', prefix, self.key,
                                [self.version], destination, 1024 * 1024)
        self.assertTrue(result['completed'])
        from ha.connected.backup_bundle import inspect_bundle
        _, reader = inspect_bundle(destination, self.key, [self.version])
        self.assertEqual(reader.get('original', 'immutable'), self.objects.data)
        self.assertEqual((destination / 'database.habackup').read_bytes(),
                         (self.target / 'database.habackup').read_bytes())

    def test_recovery_corruption_and_size_limit_never_publish(self):
        store, prefix = self.uploaded()
        for corrupt, limit in ((True, 1024 * 1024), (False, 1)):
            store.corrupt = corrupt; destination = self.root / 'rejected'
            with self.assertRaises(ValueError):
                recover_bundle(store, 'private-backups', prefix, self.key,
                               [self.version], destination, limit)
            self.assertFalse(destination.exists())
            self.assertFalse(any(p.name.startswith('.ha-download-') for p in self.root.iterdir()))

    def test_recovery_existing_destination_is_preserved(self):
        store, prefix = self.uploaded(); destination = self.root / 'existing'
        destination.write_bytes(b'keep')
        with self.assertRaises(FileExistsError):
            recover_bundle(store, 'private-backups', prefix, self.key,
                           [self.version], destination, 1024 * 1024)
        self.assertEqual(destination.read_bytes(), b'keep')

    def test_recovery_keeps_distinct_original_and_correction(self):
        from dataclasses import replace
        import hashlib
        from ha.connected.backup_bundle import create_bundle, inspect_bundle
        corrected = b'fictional corrected receipt'
        correction = replace(self.version, version_id='correction', object_key='corrected',
                             storage_version='immutable-correction', previous_version_id='version',
                             reason='Correct amount', sha256=hashlib.sha256(corrected).hexdigest())
        original = self.objects.data
        class Versions:
            def get(self, key, version):
                return original if key == 'original' else corrected
        versions = [self.version, correction]
        create_bundle('snapshot', self.dump, versions, Versions(), self.key, self.target)
        store = Store()
        copied = copy_bundle(self.target, self.key, versions, store, 'private-backups')
        destination = self.root / 'recovered-chain'
        recover_bundle(store, 'private-backups', copied['prefix'], self.key, versions,
                       destination, 1024 * 1024)
        _, reader = inspect_bundle(destination, self.key, versions)
        self.assertEqual(reader.get('original', 'immutable'), original)
        self.assertEqual(reader.get('corrected', 'immutable-correction'), corrected)
