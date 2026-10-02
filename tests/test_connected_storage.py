import unittest
from io import BytesIO
from ha.connected.aws_storage import S3Objects


class Client:
    def __init__(self):
        self.put_request = None
        self.get_request = None
    def put_object(self, **kwargs):
        self.put_request = kwargs
        return {'VersionId': 'v1', 'ServerSideEncryption': 'aws:kms', 'SSEKMSKeyId': 'key-arn'}
    def get_object(self, **kwargs):
        self.get_request = kwargs
        return {'Body': BytesIO(b'fictional'), 'ServerSideEncryption': 'aws:kms', 'SSEKMSKeyId': 'key-arn'}


class S3Tests(unittest.TestCase):
    def test_private_write_requires_kms_and_confirmed_version(self):
        client = Client()
        store = S3Objects(client, 'bucket', 'key-arn')
        self.assertEqual(store.put('documents/uuid', b'fictional', 'text/plain'), 'v1')
        self.assertEqual(client.put_request['ServerSideEncryption'], 'aws:kms')
        self.assertEqual(client.put_request['SSEKMSKeyId'], 'key-arn')
        self.assertNotIn('ACL', client.put_request)
        self.assertEqual(store.get('documents/uuid', 'v1'), b'fictional')
        self.assertEqual(client.get_request['VersionId'], 'v1')

    def test_bad_object_keys_denied(self):
        store = S3Objects(Client(), 'bucket', 'key-arn')
        for key in ('../secret', 'documents/../secret', 'documents/a/b', 'other/key', 'documents/'):
            with self.assertRaises(ValueError):
                store.put(key, b'fictional', 'text/plain')

    def test_unversioned_response_not_accepted(self):
        client = Client()
        client.put_object = lambda **kwargs: {'ServerSideEncryption': 'aws:kms', 'SSEKMSKeyId': 'key-arn'}
        with self.assertRaises(ValueError):
            S3Objects(client, 'bucket', 'key-arn').put('documents/uuid', b'fictional', 'text/plain')
