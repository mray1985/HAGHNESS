"""Client-encrypted DigitalOcean Spaces adapter, injected trusted SDK client.

Each document-service correction uses a new UUID key. Provider versioning is
required; policies, external keys, scanning and backups are deployment duties.
No public URLs or keys are returned. Not activated by preview runtime.
"""
import json
import os
import re
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from .documents import MAX_BYTES
from .encrypted_objects import KEY_PATTERN

HEADER=b'HASPACE1'
MAX_ENVELOPE=MAX_BYTES+len(HEADER)+1+100+12+16

class SpacesObjects:
    def __init__(self,client,bucket,active_key_id,key_resolver):
        if not isinstance(bucket,str) or not re.fullmatch(r'[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]',bucket):
            raise ValueError('Private Spaces bucket required')
        self._key_id(active_key_id)
        if not callable(key_resolver):raise ValueError('External key resolver required')
        self.client,self.bucket,self.active_key_id,self.key_resolver=client,bucket,active_key_id,key_resolver

    @staticmethod
    def _key_id(value):
        if not isinstance(value,str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,100}',value):
            raise ValueError('Invalid encryption key identifier')

    @staticmethod
    def _object_key(key):
        if not isinstance(key,str) or KEY_PATTERN.fullmatch(key) is None:
            raise ValueError('Invalid immutable document key')

    @staticmethod
    def _version(version):
        if not isinstance(version,str) or not version or version=='null' or len(version)>1024:
            raise ValueError('Versioned Spaces storage required')

    def _cipher(self,key_id):
        try:key=self.key_resolver(key_id)
        except (KeyError,ValueError) as error:raise ValueError('Recovery key unavailable') from error
        if not isinstance(key,bytes) or len(key)!=32:
            raise ValueError('Separately managed 256-bit key required')
        return AESGCM(key)

    def _aad(self,key,key_id):
        return json.dumps(['HASPACE1',self.bucket,key,key_id],separators=(',',':')).encode('ascii')

    def put(self,key,data,mime):
        self._object_key(key)
        if not isinstance(data,bytes) or not 0<len(data)<=MAX_BYTES:
            raise ValueError('Invalid document size')
        key_id=self.active_key_id
        encoded=key_id.encode('ascii')
        nonce=os.urandom(12)
        raw=HEADER+bytes([len(encoded)])+encoded+nonce+self._cipher(key_id).encrypt(nonce,data,self._aad(key,key_id))
        response=self.client.put_object(Bucket=self.bucket,Key=key,Body=raw,
                                        ACL='private',ContentType='application/octet-stream')
        version=response.get('VersionId')
        self._version(version)
        return version

    def get(self,key,version):
        self._object_key(key)
        self._version(version)
        response=self.client.get_object(Bucket=self.bucket,Key=key,VersionId=version)
        body=response['Body']
        try:
            if response.get('VersionId')!=version:raise ValueError('Unexpected storage version')
            raw=body.read(MAX_ENVELOPE+1)
        finally:body.close()
        if not isinstance(raw,bytes) or len(raw)>MAX_ENVELOPE or not raw.startswith(HEADER) or len(raw)<=len(HEADER):
            raise ValueError('Encrypted document integrity failure')
        size=raw[len(HEADER)]
        if not 1<=size<=100 or len(raw)<=len(HEADER)+1+size+12+16:
            raise ValueError('Encrypted document integrity failure')
        start=len(HEADER)+1
        try:key_id=raw[start:start+size].decode('ascii')
        except UnicodeDecodeError as error:raise ValueError('Invalid encryption key identifier') from error
        self._key_id(key_id)
        start+=size
        nonce=raw[start:start+12]
        try:data=self._cipher(key_id).decrypt(nonce,raw[start+12:],self._aad(key,key_id))
        except InvalidTag as error:raise ValueError('Encrypted document integrity failure') from error
        if not 0<len(data)<=MAX_BYTES:raise ValueError('Invalid document size')
        return data
