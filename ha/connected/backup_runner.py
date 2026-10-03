"""Disabled-by-default scheduled backup entry point; sanitized status only."""
from datetime import datetime,timezone
import os
import json
from pathlib import Path
import re
import stat
import uuid
from .backup_job import capture_backup
from .document_configuration import MountedKeys
from .spaces_storage import SpacesObjects
from .backup_receipt import write_receipt, publish_receipt

REQUIRED=('HA_BACKUP_DATABASE_URL','HA_BACKUP_DIRECTORY','HA_BACKUP_KEY_DIRECTORY',
    'HA_BACKUP_KEY_ID','HA_BACKUP_PG_DUMP','HA_SPACES_REGION','HA_SPACES_BUCKET',
    'HA_SPACES_ACCESS_KEY','HA_SPACES_SECRET_KEY','HA_DOCUMENT_KEY_DIRECTORY','HA_DOCUMENT_ACTIVE_KEY_ID',
    'HA_BACKUP_SPACES_BUCKET','HA_BACKUP_SPACES_ACCESS_KEY','HA_BACKUP_SPACES_SECRET_KEY')

class ReadObjects:
    def __init__(self,objects):self.objects=objects
    def get(self,key,version):return self.objects.get(key,version)

def run(env):
    if env.get('HA_BACKUP_ENABLED')!='true':raise ValueError('Backup activation required')
    if os.name!='posix' or not all(env.get(name) for name in REQUIRED):
        raise ValueError('Complete Linux backup configuration required')
    if env['HA_BACKUP_SPACES_BUCKET']==env['HA_SPACES_BUCKET']:
        raise ValueError('Separate backup bucket required')
    root=Path(env['HA_BACKUP_DIRECTORY']).resolve(strict=True)
    application=Path(__file__).resolve().parents[2]
    info=root.stat()
    if (not stat.S_ISDIR(info.st_mode) or info.st_mode&0o077 or info.st_uid not in (0,os.geteuid())
            or root.is_relative_to(application)):
        raise ValueError('Private external backup directory required')
    region=env['HA_SPACES_REGION']
    if not re.fullmatch(r'[a-z]{2,8}[0-9]{1,2}',region):raise ValueError('Spaces region required')
    document_keys=MountedKeys(env['HA_DOCUMENT_KEY_DIRECTORY'])
    document_keys(env['HA_DOCUMENT_ACTIVE_KEY_ID'])
    backup_key=MountedKeys(env['HA_BACKUP_KEY_DIRECTORY'])(env['HA_BACKUP_KEY_ID'])
    import boto3
    from botocore.config import Config
    client=boto3.client('s3',region_name=region,endpoint_url=f'https://{region}.digitaloceanspaces.com',
        aws_access_key_id=env['HA_SPACES_ACCESS_KEY'],aws_secret_access_key=env['HA_SPACES_SECRET_KEY'],
        config=Config(signature_version='s3v4',connect_timeout=5,read_timeout=15,retries={'total_max_attempts':2}))
    objects=ReadObjects(SpacesObjects(client,env['HA_SPACES_BUCKET'],env['HA_DOCUMENT_ACTIVE_KEY_ID'],document_keys))
    backup_client=boto3.client('s3',region_name=region,endpoint_url=f'https://{region}.digitaloceanspaces.com',
        aws_access_key_id=env['HA_BACKUP_SPACES_ACCESS_KEY'],aws_secret_access_key=env['HA_BACKUP_SPACES_SECRET_KEY'],
        config=Config(signature_version='s3v4',connect_timeout=5,read_timeout=15,retries={'total_max_attempts':2}))
    name=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+env['HA_BACKUP_KEY_ID']+'-'+uuid.uuid4().hex
    result=capture_backup(env['HA_BACKUP_DATABASE_URL'],objects,backup_key,root/name,env['HA_BACKUP_PG_DUMP'],
        offhost=(backup_client,env['HA_BACKUP_SPACES_BUCKET']))
    result['recovery_key_id']=env['HA_BACKUP_KEY_ID']
    receipt=write_receipt(result,env['HA_BACKUP_KEY_ID'],region,env['HA_BACKUP_SPACES_BUCKET'],root/(name+'.receipt.json'))
    result['offhost_receipt']=publish_receipt(receipt,backup_client)
    return result

def main():
    attempt_id=uuid.uuid4().hex
    def emit(status, **fields):
        print(json.dumps({'format':'ha-backup-attempt-v1','attempt_id':attempt_id,
            'status':status,'observed_at':datetime.now(timezone.utc).isoformat(),
            'recovery_verified':False,'deletion_authorized':False,**fields},sort_keys=True),flush=True)
    emit('started')
    try:
        result=run(os.environ)
        remote=result.get('offhost') or {}
        locator=result.get('offhost_receipt') or {}
        if (result.get('completed') is not True or remote.get('completed') is not True
                or locator.get('verified') is not True
                or not re.fullmatch(r'ha-recovery/[0-9a-f]{32}/',remote.get('prefix',''))
                or type(result.get('document_versions')) is not int or result['document_versions']<0
                or not re.fullmatch(r'[a-zA-Z0-9_-]{1,100}',result.get('recovery_key_id',''))):
            raise ValueError('Verified completion fields required')
    except Exception:
        emit('failed',message='HA backup failed; no completion confirmed')
        return 1
    emit('completed',document_versions=result['document_versions'],prefix=remote['prefix'],
         recovery_key_id=result['recovery_key_id'],copy_verified=True,locator_verified=True)
    return 0

if __name__=='__main__':raise SystemExit(main())
