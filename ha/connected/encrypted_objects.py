"""Encrypted local recovery fixture adapter, never selected by hosted runtime.

The caller supplies a separately managed 256-bit key and an access-restricted
root. Local filesystem ACLs and external key recovery are operator duties.
Hosted storage, key rotation, scan integration and retention are separate gates.
"""
import os
from pathlib import Path
import re
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from .documents import MAX_BYTES

HEADER=b'HAOBJ1'
VERSION='local-aesgcm-v1'
KEY_PATTERN=re.compile(r'documents/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')

class EncryptedLocalObjects:
    def __init__(self,root,key_resolver):
        self.root=Path(root).resolve()
        self.root.mkdir(parents=True,exist_ok=True,mode=0o700)
        self.key_resolver=key_resolver

    def _path(self,key):
        if not isinstance(key,str) or KEY_PATTERN.fullmatch(key) is None:
            raise ValueError('Invalid immutable object key')
        path=self.root/(key.split('/')[1]+'.haobj')
        if path.is_symlink():raise ValueError('Object links are not supported')
        return path

    def _cipher(self):
        key=self.key_resolver()
        if not isinstance(key,bytes) or len(key)!=32:
            raise ValueError('A separately managed 256-bit key is required')
        return AESGCM(key)

    def put(self,key,data,mime):
        path=self._path(key)
        if not isinstance(data,bytes) or not 0<len(data)<=MAX_BYTES:
            raise ValueError('Invalid document size')
        nonce=os.urandom(12)
        encrypted=HEADER+nonce+self._cipher().encrypt(nonce,data,key.encode('ascii'))
        try:
            handle=path.open('xb')
        except FileExistsError as error:
            raise ValueError('Object already exists') from error
        try:
            with handle:
                handle.write(encrypted)
                handle.flush()
                os.fsync(handle.fileno())
        except BaseException:
            path.unlink(missing_ok=True)
            raise
        return VERSION

    def get(self,key,version):
        path=self._path(key)
        if version!=VERSION:raise ValueError('Unsupported storage version')
        with path.open('rb') as handle:
            raw=handle.read(MAX_BYTES+len(HEADER)+12+16+1)
        if not len(HEADER)+12+16<len(raw)<=MAX_BYTES+len(HEADER)+12+16 or not raw.startswith(HEADER):
            raise ValueError('Encrypted object integrity failure')
        nonce=raw[len(HEADER):len(HEADER)+12]
        try:
            return self._cipher().decrypt(nonce,raw[len(HEADER)+12:],key.encode('ascii'))
        except InvalidTag as error:
            raise ValueError('Encrypted object integrity failure') from error
