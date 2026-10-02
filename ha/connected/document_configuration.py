"""Explicit private storage/scanner configuration; disabled by default.

Mounted key files must be administered outside application code and backed up
separately. Linux ownership/mode checks fail closed on unsupported platforms.
"""
import os
from pathlib import Path
import re
import stat
from .documents import Documents
from .scanner import ClamDScanner
from .spaces_storage import SpacesObjects

SETTINGS=('HA_SPACES_REGION','HA_SPACES_BUCKET','HA_SPACES_ACCESS_KEY',
          'HA_SPACES_SECRET_KEY','HA_DOCUMENT_KEY_DIRECTORY',
          'HA_DOCUMENT_ACTIVE_KEY_ID','HA_CLAMD_SOCKET')

class MountedKeys:
    def __init__(self,directory):
        self.root=Path(directory).resolve(strict=True)
        application=Path(__file__).resolve().parents[2]
        if not self.root.is_dir() or self.root.is_relative_to(application):
            raise ValueError('Recovery keys must be mounted outside application code')

    def __call__(self,key_id):
        SpacesObjects._key_id(key_id)
        if os.name!='posix':raise ValueError('Mounted keys require Linux permission verification')
        root=self.root.stat()
        if root.st_mode&0o077 or root.st_uid not in (0,os.geteuid()):
            raise ValueError('Recovery key directory permissions are too broad')
        path=self.root/(key_id+'.key')
        try:
            descriptor=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
            with os.fdopen(descriptor,'rb') as handle:
                info=os.fstat(handle.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_mode&0o077 or info.st_uid not in (0,os.geteuid()):
                    raise ValueError('Recovery key permissions are too broad')
                key=handle.read(33)
        except OSError as error:raise ValueError('Recovery key unavailable') from error
        if len(key)!=32:raise ValueError('Recovery key must contain exactly 32 bytes')
        return key

def build_documents(env,repository):
    provider=env.get('HA_DOCUMENT_STORAGE','disabled')
    if provider=='disabled':
        if any(env.get(name) for name in SETTINGS):raise ValueError('Select document storage explicitly')
        return None
    if provider!='spaces' or repository is None or not all(env.get(name) for name in SETTINGS):
        raise ValueError('Document storage configuration is incomplete')
    region=env['HA_SPACES_REGION']
    if not re.fullmatch(r'[a-z]{2,8}[0-9]{1,2}',region):raise ValueError('Spaces region required')
    keys=MountedKeys(env['HA_DOCUMENT_KEY_DIRECTORY'])
    active=env['HA_DOCUMENT_ACTIVE_KEY_ID']
    keys(active) # Validate the active key before accepting uploads.
    scanner=ClamDScanner(env['HA_CLAMD_SOCKET'])
    import boto3
    from botocore.config import Config
    client=boto3.client('s3',region_name=region,
        endpoint_url=f'https://{region}.digitaloceanspaces.com',
        aws_access_key_id=env['HA_SPACES_ACCESS_KEY'],aws_secret_access_key=env['HA_SPACES_SECRET_KEY'],
        config=Config(signature_version='s3v4',connect_timeout=5,read_timeout=15,retries={'total_max_attempts':2}))
    return Documents(repository,SpacesObjects(client,env['HA_SPACES_BUCKET'],active,keys),scanner)
