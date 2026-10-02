"""Operator-only completed recovery bundles with separate externally supplied keys.

A bundle is usable only after its authenticated inventory is published last.
Failed captures remain private incomplete directories for operator diagnosis.
Trusted private parent directories are required; no automatic deletion occurs.
"""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from .backup_archive import encrypt_backup,decrypt_backup
from .backup_inventory import build_inventory,verify_inventory
from .documents import MAX_BYTES

FILE=re.compile(r'object-[0-9a-f]{64}\.habackup')
MAX_MANIFEST=64*1024*1024

def digest(path):
    hasher=hashlib.sha256()
    with open(path,'rb') as source:
        while block:=source.read(1024*1024):hasher.update(block)
    return hasher.hexdigest()

@contextmanager
def private_file(parent):
    descriptor,name=tempfile.mkstemp(prefix='.ha-recovery-',dir=parent)
    os.close(descriptor);path=Path(name)
    try:yield path
    finally:path.unlink(missing_ok=True)

def encrypted_bytes(data,target,key):
    with private_file(target.parent) as plain:
        with plain.open('wb') as writer:
            writer.write(data);writer.flush();os.fsync(writer.fileno())
        encrypt_backup(plain,target,key)

def decrypted_bytes(source,key,maximum):
    # Normal archive framing adds less than 1024 bytes at this document limit.
    if source.is_symlink() or source.stat().st_size>maximum+4096:
        raise ValueError('Unexpected recovery artifact')
    with private_file(source.parent) as occupied:
        # decrypt_backup publishes exclusively; reserve a different nonexistent sibling.
        target=occupied.with_name(occupied.name+'-plain')
        published=False
        try:
            decrypt_backup(source,target,key)
            published=True
            with target.open('rb') as reader:data=reader.read(maximum+1)
            if len(data)>maximum:raise ValueError('Recovery artifact exceeds limit')
            return data
        finally:
            if published:target.unlink(missing_ok=True)

class BundleObjects:
    """Recovery-only plaintext reader after authenticated inventory inspection."""
    def __init__(self,root,key,manifest):
        self.root,self.key=Path(root),key
        inventory=manifest['inventory'];files=manifest['object_files']
        if set(files)!={entry['version_id'] for entry in inventory['versions']}:
            raise ValueError('Incomplete object capture map')
        self.mapping={}
        for entry in inventory['versions']:
            name=files[entry['version_id']]
            expected='object-'+hashlib.sha256(entry['version_id'].encode()).hexdigest()+'.habackup'
            if not isinstance(name,str) or FILE.fullmatch(name) is None or name!=expected:
                raise ValueError('Invalid recovery object path')
            self.mapping[(entry['object_key'],entry['storage_version'])]=name
    def get(self,object_key,storage_version):
        name=self.mapping[(object_key,storage_version)]
        return decrypted_bytes(self.root/name,self.key,MAX_BYTES)

def sync_directory(root):
    if os.name=='posix':
        descriptor=os.open(root,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(descriptor)
        finally:os.close(descriptor)

def create_bundle(snapshot_id,dump_path,versions,objects,key,destination):
    if not isinstance(key,bytes) or len(key)!=32:raise ValueError('Separate recovery key required')
    versions=list(versions);root=Path(destination)
    root.mkdir(mode=0o700)  # Exclusive reservation; never overwrite another backup.
    archive=root/'database.habackup'
    encrypt_backup(dump_path,archive,key)
    files={}
    for version in versions:
        if version.version_id in files:raise ValueError('Duplicate captured version')
        data=objects.get(version.object_key,version.storage_version)
        if (not isinstance(data,bytes) or not 0<len(data)<=MAX_BYTES
                or hashlib.sha256(data).hexdigest()!=version.sha256):
            raise ValueError('Source object disagrees with snapshot')
        name='object-'+hashlib.sha256(version.version_id.encode()).hexdigest()+'.habackup'
        encrypted_bytes(data,root/name,key);files[version.version_id]=name
    metadata={'format':'ha-recovery-bundle-v1','object_files':files}
    # Re-read encrypted captured objects, not source objects, before completion.
    source_inventory=build_inventory(snapshot_id,versions,objects,digest(archive))
    metadata['inventory']=source_inventory
    verify_inventory(source_inventory,versions,BundleObjects(root,key,metadata),digest(archive))
    encoded=json.dumps(metadata,sort_keys=True,separators=(',',':')).encode()
    if len(encoded)>MAX_MANIFEST:raise ValueError('Inventory too large')
    # Publication of the authenticated inventory is the completion gate.
    sync_directory(root)
    completed=root/'inventory.habackup'
    published=False
    try:
        encrypted_bytes(encoded,completed,key);published=True
        sync_directory(root)
    except BaseException:
        if published:completed.unlink(missing_ok=True)
        raise
    return metadata

def inspect_bundle(root,key,versions):
    root=Path(root)
    if root.is_symlink() or not root.is_dir():raise ValueError('Private recovery directory required')
    metadata=json.loads(decrypted_bytes(root/'inventory.habackup',key,MAX_MANIFEST))
    if set(metadata)!={'format','inventory','object_files'} or metadata['format']!='ha-recovery-bundle-v1':
        raise ValueError('Unsupported recovery bundle')
    reader=BundleObjects(root,key,metadata)
    verify_inventory(metadata['inventory'],versions,reader,digest(root/'database.habackup'))
    return metadata,reader
