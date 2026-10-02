import json
from io import BytesIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from ha.connected.backup_receipt import write_receipt, publish_receipt


class ReceiptTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory(); self.addCleanup(folder.cleanup)
        self.target = Path(folder.name) / 'receipt.json'
        self.result = {'snapshot_id': 'snapshot', 'document_versions': 2, 'completed': True,
                       'offhost': {'completed': True, 'prefix': 'ha-recovery/' + 'a'*32 + '/'}}
    def write(self):
        return write_receipt(self.result, 'historical-key', 'nyc3', 'private-backups', self.target)
    def test_receipt_records_copy_without_claiming_restore_or_deletion(self):
        receipt = self.write()
        self.assertEqual(json.loads(self.target.read_text()), receipt)
        self.assertTrue(receipt['copy_verified'])
        self.assertFalse(receipt['recovery_verified'])
        self.assertFalse(receipt['deletion_authorized'])
        self.assertEqual(receipt['recovery_key_id'], 'historical-key')
        with self.assertRaises(FileExistsError): self.write()
        self.assertEqual(json.loads(self.target.read_text()), receipt)
    def test_unverified_copy_cannot_get_a_receipt(self):
        self.result['offhost']['completed'] = False
        with self.assertRaises(ValueError): self.write()
        self.assertFalse(self.target.exists())
    def test_failed_directory_sync_removes_only_owned_receipt(self):
        with patch('ha.connected.backup_receipt.sync_directory', side_effect=OSError('sync')):
            with self.assertRaises(OSError): self.write()
        self.assertEqual(list(self.target.parent.iterdir()), [])

    def test_offhost_locator_is_private_and_read_back(self):
        receipt = self.write()
        class Store:
            def put_object(store, **kwargs):
                store.request = kwargs
            def get_object(store, **kwargs):
                self.assertEqual(kwargs['Key'], receipt['prefix'] + 'receipt.json')
                store.body = BytesIO(store.request['Body'])
                return {'Body': store.body}
        store = Store()
        result = publish_receipt(receipt, store)
        self.assertEqual(store.request['ACL'], 'private')
        self.assertEqual(store.request['Bucket'], 'private-backups')
        self.assertEqual(json.loads(store.request['Body']), receipt)
        self.assertTrue(store.body.closed)
        self.assertTrue(result['verified'])

    def test_offhost_locator_mismatch_or_oversize_cannot_report_success(self):
        receipt = self.write()
        for payload in (b'corrupted', b'x' * 65537):
            class Store:
                def put_object(store, **kwargs): pass
                def get_object(store, **kwargs):
                    store.body = BytesIO(payload)
                    return {'Body': store.body}
            store = Store()
            with self.assertRaises(ValueError): publish_receipt(receipt, store)
            self.assertTrue(store.body.closed)

    def test_offhost_locator_rejects_added_fields_and_unverified_flags_before_write(self):
        receipt = self.write()
        for changed in ({**receipt, 'secret': 'must not copy'},
                        {**receipt, 'copy_verified': False},
                        {**receipt, 'deletion_authorized': True},
                        {**receipt, 'prefix': '../unsafe/'}):
            from unittest.mock import Mock
            store = Mock()
            with self.assertRaises(ValueError): publish_receipt(changed, store)
            store.put_object.assert_not_called()

    def test_provider_failures_propagate_and_keep_local_receipt(self):
        receipt = self.write()
        from unittest.mock import Mock
        for method in ('put_object', 'get_object'):
            store = Mock()
            getattr(store, method).side_effect = OSError('provider unavailable')
            with self.assertRaises(OSError): publish_receipt(receipt, store)
            self.assertEqual(json.loads(self.target.read_text()), receipt)
