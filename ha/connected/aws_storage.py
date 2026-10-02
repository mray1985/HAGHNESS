"""S3 object adapter; bucket policies and role permissions are separate gates."""
import base64
import hashlib
import re
from .documents import MAX_BYTES


class S3Objects:
    def __init__(self, client, bucket, kms_key_arn):
        if not bucket or not kms_key_arn:
            raise ValueError('Private storage configuration required')
        self.client, self.bucket, self.key = client, bucket, kms_key_arn

    @staticmethod
    def _key(key):
        if not isinstance(key, str) or not re.fullmatch(r'documents/[a-zA-Z0-9_-]{1,100}', key):
            raise ValueError('Invalid storage key')

    def put(self, key, data, mime):
        self._key(key)
        if len(data) > MAX_BYTES:
            raise ValueError('Document too large')
        response = self.client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=mime,
            ServerSideEncryption='aws:kms', SSEKMSKeyId=self.key,
            ChecksumSHA256=base64.b64encode(hashlib.sha256(data).digest()).decode())
        if (response.get('ServerSideEncryption') != 'aws:kms' or response.get('SSEKMSKeyId') != self.key
                or response.get('VersionId') in (None, '', 'null')):
            raise ValueError('Encrypted versioned storage not confirmed')
        return response['VersionId']

    def get(self, key, version):
        self._key(key)
        if not version or version == 'null':
            raise ValueError('Storage version required')
        response = self.client.get_object(Bucket=self.bucket, Key=key, VersionId=version)
        body = response['Body']
        try:
            if response.get('ServerSideEncryption') != 'aws:kms' or response.get('SSEKMSKeyId') != self.key:
                raise ValueError('Unexpected document encryption')
            data = body.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES:
                raise ValueError('Document too large')
            return data
        finally:
            body.close()
