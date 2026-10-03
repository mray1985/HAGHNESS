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

def discover(client, bucket, region, *, now=None, max_age=timedelta(hours=36),
             max_prefixes=5000, max_pages=100):
    """Newest valid receipt in this completed bounded listing, not a snapshot catalog.

    Incomplete uploads have no receipt. All other receipt/read/list errors fail
    closed rather than reporting an older successful subset as newest.
    """
    from botocore.exceptions import ClientError
    if (not isinstance(bucket,str) or not re.fullmatch(r'[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]',bucket)
            or not isinstance(region,str) or not re.fullmatch(r'[a-z]{2,8}[0-9]{1,2}',region)
            or type(max_prefixes) is not int or not 1<=max_prefixes<=5000
            or type(max_pages) is not int or not 1<=max_pages<=100):
        raise ValueError('Bounded private discovery required')
    now=now or datetime.now(timezone.utc)
    if (not isinstance(now,datetime) or now.tzinfo is None or now.utcoffset()!=timedelta(0)
            or not isinstance(max_age,timedelta) or max_age<=timedelta(0)):
        raise ValueError('UTC monitoring time and positive maximum age required')
    token=None;tokens=set();prefixes=set();latest=None;observed=0
    for _ in range(max_pages):
        options={'Bucket':bucket,'Prefix':'ha-recovery/','Delimiter':'/','MaxKeys':1000}
        if token is not None:options['ContinuationToken']=token
        page=client.list_objects_v2(**options)
        if not isinstance(page,dict) or type(page.get('IsTruncated')) is not bool:
            raise ValueError('Complete listing response required')
        folders=page.get('CommonPrefixes',[])
        if not isinstance(folders,list) or len(folders)>1000 or page.get('Contents'):
            raise ValueError('Invalid recovery prefix listing')
        for folder in folders:
            prefix=folder.get('Prefix') if isinstance(folder,dict) else None
            if (not isinstance(prefix,str) or not re.fullmatch(r'ha-recovery/[0-9a-f]{32}/',prefix)
                    or prefix in prefixes or len(prefixes)>=max_prefixes):
                raise ValueError('Invalid or excessive recovery prefixes')
            prefixes.add(prefix)
            try:receipt=retrieve_receipt(client,bucket,prefix,region)
            except ClientError as error:
                if error.response.get('Error',{}).get('Code')=='NoSuchKey':continue
                raise
            assess(receipt,now=now,max_age=max_age)
            observed+=1
            order=(datetime.fromisoformat(receipt['completed_at']),prefix)
            if latest is None or order>latest[0]:latest=(order,receipt)
        if not page['IsTruncated']:break
        token=page.get('NextContinuationToken')
        if not isinstance(token,str) or not 1<=len(token)<=8192 or token in tokens:
            raise ValueError('Invalid listing continuation')
        tokens.add(token)
    else:raise ValueError('Recovery listing exceeds page limit')
    if latest is None:
        result={'status':'no_locator_observed','locator_available':False,
                'archive_integrity_verified':False,'recovery_verified':False,'deletion_authorized':False}
    else:
        result=assess(latest[1],now=now,max_age=max_age)
        result['prefix']=latest[1]['prefix']
    return {**result,'listed_prefixes':len(prefixes),'receipts_observed':observed,
            'discovery_scope':'completed listing observed during this check; not an atomic catalog'}


def configured_store():
    """Explicit read-only operator credentials; never a default AWS endpoint."""
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
    return store,os.environ['HA_BACKUP_SPACES_BUCKET'],region


def main(argv=None):
    parser=argparse.ArgumentParser(description='Read private backup locator freshness; does not verify recovery.')
    selection=parser.add_mutually_exclusive_group(required=True)
    selection.add_argument('--prefix')
    selection.add_argument('--discover',action='store_true')
    parser.add_argument('--max-age-hours',type=int,default=36)
    args=parser.parse_args(argv)
    try:
        store,bucket,region=configured_store()
        if args.discover:
            result=discover(store,bucket,region,max_age=timedelta(hours=args.max_age_hours))
        else:
            result=check(store,bucket,args.prefix,region,
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
