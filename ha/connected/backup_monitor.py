"""Read-only backup locator freshness; never claims authenticated recovery."""
import argparse
import json
import os
import re
from datetime import datetime, timedelta, timezone
from .backup_receipt import validate_receipt, retrieve_receipt


def assess(receipt, *, now=None, max_age=timedelta(hours=36)):
    validate_receipt(receipt)
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() != timedelta(0):
        raise ValueError('UTC monitoring time required')
    if not isinstance(max_age, timedelta) or max_age <= timedelta(0):
        raise ValueError('Positive maximum age required')
    completed = datetime.fromisoformat(receipt['completed_at'])
    age = now - completed
    if age < timedelta(0):
        raise ValueError('Future backup completion rejected')
    return {'status': 'current_locator' if age <= max_age else 'stale_locator',
            'age_seconds': int(age.total_seconds()), 'locator_available': True,
            'archive_integrity_verified': False, 'recovery_verified': False,
            'deletion_authorized': False}


def check(client, bucket, prefix, region, *, now=None, max_age=timedelta(hours=36)):
    """Known locator must be read from private off-host storage, not local state."""
    return assess(retrieve_receipt(client, bucket, prefix, region), now=now, max_age=max_age)

def main(argv=None):
    parser=argparse.ArgumentParser(description='Read private backup locator freshness; does not verify recovery.')
    parser.add_argument('--prefix',required=True)
    parser.add_argument('--max-age-hours',type=int,default=36)
    args=parser.parse_args(argv)
    try:
        from boto3 import client
        from botocore.config import Config
        region=os.environ['HA_SPACES_REGION']
        # Reuse the locator validator before constructing a provider endpoint.
        if not re.fullmatch(r'[a-z]{2,8}[0-9]{1,2}',region):
            raise ValueError('Invalid region')
        store=client('s3',region_name=region,endpoint_url=f'https://{region}.digitaloceanspaces.com',
            aws_access_key_id=os.environ['HA_BACKUP_SPACES_ACCESS_KEY'],
            aws_secret_access_key=os.environ['HA_BACKUP_SPACES_SECRET_KEY'],
            config=Config(signature_version='s3v4',connect_timeout=5,read_timeout=15,
                          retries={'total_max_attempts':2}))
        result=check(store,os.environ['HA_BACKUP_SPACES_BUCKET'],args.prefix,region,
                     max_age=timedelta(hours=args.max_age_hours))
    except Exception:
        print(json.dumps({'status':'unavailable','locator_available':False,
                          'archive_integrity_verified':False,'recovery_verified':False,
                          'deletion_authorized':False}))
        return 2
    print(json.dumps(result,sort_keys=True))
    return 0 if result['status']=='current_locator' else 1


if __name__=='__main__':
    raise SystemExit(main())
