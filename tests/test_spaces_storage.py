import io
import unittest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from ha.connected.spaces_storage import SpacesObjects

KEY='documents/12345678-1234-1234-1234-123456789abc'
OTHER='documents/22345678-1234-1234-1234-123456789abc'

class Client:
    def __init__(self):self.saved={};self.response_version='v1';self.last=None;self.body=None
    def put_object(self,**kwargs):
        self.last=kwargs; self.saved[(kwargs['Key'],self.response_version)]=kwargs['Body']
        return {'VersionId':self.response_version}
    def get_object(self,**kwargs):
        self.last=kwargs
        self.body=io.BytesIO(self.saved[(kwargs['Key'],kwargs['VersionId'])])
        return {'VersionId':kwargs['VersionId'],'Body':self.body}

class SpacesTests(unittest.TestCase):
    def setUp(self):
        self.client=Client()
        self.keys={'key-2026':AESGCM.generate_key(bit_length=256),'key-next':AESGCM.generate_key(bit_length=256)}
        self.store=SpacesObjects(self.client,'private-bucket','key-2026',self.keys.__getitem__)

    def test_ciphertext_private_upload_and_exact_version_read(self):
        version=self.store.put(KEY,b'fictional private receipt','text/plain')
        upload=self.client.last
        self.assertEqual(upload['ACL'],'private')
        self.assertEqual(upload['ContentType'],'application/octet-stream')
        self.assertNotIn(b'fictional private receipt',upload['Body'])
        self.assertNotIn(self.keys['key-2026'],upload['Body'])
        self.assertEqual(self.store.get(KEY,version),b'fictional private receipt')
        self.assertEqual(self.client.last['VersionId'],version)
        self.assertTrue(self.client.body.closed)

    def test_key_rotation_keeps_old_versions_readable(self):
        old=self.store.put(KEY,b'original','text/plain')
        self.client.response_version='v2'
        rotated=SpacesObjects(self.client,'private-bucket','key-next',self.keys.__getitem__)
        new=rotated.put(KEY,b'corrected','text/plain')
        self.assertEqual(rotated.get(KEY,old),b'original')
        self.assertEqual(rotated.get(KEY,new),b'corrected')

    def test_swapped_corrupt_and_wrong_key_fail_closed(self):
        version=self.store.put(KEY,b'original','text/plain')
        self.client.saved[(OTHER,version)]=self.client.saved[(KEY,version)]
        with self.assertRaises(ValueError):self.store.get(OTHER,version)
        wrong=SpacesObjects(self.client,'private-bucket','key-2026',lambda name:bytes(32))
        with self.assertRaises(ValueError):wrong.get(KEY,version)
        self.client.saved[(KEY,version)]=b'broken'
        with self.assertRaises(ValueError):self.store.get(KEY,version)
        self.assertTrue(self.client.body.closed)

    def test_missing_version_and_invalid_inputs_reject(self):
        for version in (None,'','null',False):
            self.client.response_version=version
            with self.subTest(version=version),self.assertRaises(ValueError):self.store.put(KEY,b'x','text/plain')
        for key in ('../secret','documents/not-a-uuid'):
            with self.assertRaises(ValueError):self.store.put(key,b'x','text/plain')
        for data in (b'', 'plaintext'):
            with self.assertRaises(ValueError):self.store.put(KEY,data,'text/plain')

    def test_unexpected_version_and_oversized_stream_close_without_decrypting(self):
        from unittest.mock import patch
        version=self.store.put(KEY,b'x','text/plain')
        body=io.BytesIO(b'x')
        with patch.object(self.client,'get_object',return_value={'VersionId':'different','Body':body}):
            with self.assertRaises(ValueError):self.store.get(KEY,version)
        self.assertTrue(body.closed)
        with patch('ha.connected.spaces_storage.MAX_ENVELOPE',32):
            with self.assertRaises(ValueError):self.store.get(KEY,version)
        self.assertTrue(self.client.body.closed)

    def test_missing_recovery_key_and_cross_bucket_copy_are_rejected(self):
        version=self.store.put(KEY,b'x','text/plain')
        missing=SpacesObjects(self.client,'private-bucket','key-next',lambda name:None)
        with self.assertRaises(ValueError):missing.get(KEY,version)
        other=SpacesObjects(self.client,'other-bucket','key-2026',self.keys.__getitem__)
        with self.assertRaises(ValueError):other.get(KEY,version)
