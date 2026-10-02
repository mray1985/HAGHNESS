import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from ha.connected.backup_receipt import write_receipt


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
