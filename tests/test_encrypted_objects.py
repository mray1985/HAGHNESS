import tempfile
import unittest
from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from ha.connected.encrypted_objects import EncryptedLocalObjects

KEY='documents/12345678-1234-1234-1234-123456789abc'
OTHER='documents/22345678-1234-1234-1234-123456789abc'

class EncryptedObjectsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.key=AESGCM.generate_key(bit_length=256)
        self.store=EncryptedLocalObjects(self.root,lambda:self.key)

    def test_reopen_reads_encrypted_bytes_without_plaintext_on_disk(self):
        version=self.store.put(KEY,b'fictional receipt secret','text/plain')
        contents=list(self.root.glob('*.haobj'))[0].read_bytes()
        self.assertNotIn(b'fictional receipt secret',contents)
        reopened=EncryptedLocalObjects(self.root,lambda:self.key)
        self.assertEqual(reopened.get(KEY,version),b'fictional receipt secret')

    def test_original_is_immutable(self):
        version=self.store.put(KEY,b'original','text/plain')
        with self.assertRaises(ValueError):self.store.put(KEY,b'correction','text/plain')
        self.assertEqual(self.store.get(KEY,version),b'original')

    def test_wrong_key_corruption_and_swapped_objects_are_rejected(self):
        version=self.store.put(KEY,b'first','text/plain')
        other=self.store.put(OTHER,b'second','text/plain')
        with self.assertRaises(ValueError):EncryptedLocalObjects(self.root,lambda:bytes(32)).get(KEY,version)
        first=self.root/(KEY.split('/')[1]+'.haobj')
        second=self.root/(OTHER.split('/')[1]+'.haobj')
        first.write_bytes(second.read_bytes())
        with self.assertRaises(ValueError):self.store.get(KEY,version)
        second.write_bytes(b'broken')
        with self.assertRaises(ValueError):self.store.get(OTHER,other)

    def test_invalid_paths_and_storage_versions_are_rejected(self):
        for key in ('../secret','documents/../../secret','documents/not-uuid','/absolute'):
            with self.subTest(key=key),self.assertRaises(ValueError):self.store.put(key,b'x','text/plain')
        version=self.store.put(KEY,b'x','text/plain')
        with self.assertRaises(ValueError):self.store.get(KEY,'unrecognized-version')
