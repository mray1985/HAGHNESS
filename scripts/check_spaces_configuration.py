"""Read-only Spaces versioning/ACL observations, not deployment or privacy proof."""
import json
import os
import re
from urllib.parse import urlsplit

SETTINGS=('HA_SPACES_REGION','HA_SPACES_BUCKET','HA_SPACES_ACCESS_KEY','HA_SPACES_SECRET_KEY')


def bucket_name(value):
    if not isinstance(value,str) or not re.fullmatch(r'[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]',value):
        raise ValueError('Explicit Spaces bucket required')
    return value


def result_base():
    return {'configuration_checks_passed':False,'private_objects_verified':False,
            'cdn_or_bucket_policy_verified':False,'recovery_verified':False,
            'deployment_verified':False,'resources_changed':False}


def check_configuration(client,bucket):
    bucket=bucket_name(bucket)
    versioning=client.get_bucket_versioning(Bucket=bucket)
    acl=client.get_bucket_acl(Bucket=bucket)
    if not isinstance(versioning,dict) or not isinstance(acl,dict):
        raise ValueError('Invalid configuration response')
    owner=acl.get('Owner');owner_id=owner.get('ID') if isinstance(owner,dict) else None
    grants=acl.get('Grants')
    owner_only=isinstance(owner_id,str) and bool(owner_id) and isinstance(grants,list) and bool(grants)
    if owner_only:
        for grant in grants:
            grantee=grant.get('Grantee') if isinstance(grant,dict) else None
            if (not isinstance(grantee,dict) or grantee.get('Type')!='CanonicalUser'
                    or grantee.get('ID')!=owner_id or grant.get('Permission')!='FULL_CONTROL'):
                owner_only=False;break
    enabled=versioning.get('Status')=='Enabled'
    return {**result_base(),'status':'observed','versioning_enabled':enabled,
            'bucket_acl_owner_only':owner_only,'configuration_checks_passed':enabled and owner_only}


def make_client(env):
    # Explicit provider endpoint/credentials: no ambient AWS fallback.
    region=env.get('HA_SPACES_REGION')
    if not isinstance(region,str) or not re.fullmatch(r'[a-z]{2,8}[0-9]{1,2}',region):
        raise ValueError('Explicit Spaces region required')
    bucket_name(env.get('HA_SPACES_BUCKET'))
    if not all(isinstance(env.get(name),str) and env[name].strip() for name in SETTINGS):
        raise ValueError('Explicit Spaces configuration required')
    import boto3
    from botocore.config import Config
    client=boto3.client('s3',region_name=region,endpoint_url=f'https://{region}.digitaloceanspaces.com',verify=True,
        aws_access_key_id=env['HA_SPACES_ACCESS_KEY'],aws_secret_access_key=env['HA_SPACES_SECRET_KEY'],
        config=Config(signature_version='s3v4',connect_timeout=5,read_timeout=15,
                      retries={'total_max_attempts':2},s3={'addressing_style':'path'}))
    bucket=env['HA_SPACES_BUCKET']
    def destination_guard(request,**kwargs):
        parsed=urlsplit(request.url)
        if (parsed.scheme!='https' or parsed.netloc!=f'{region}.digitaloceanspaces.com'
                or parsed.path not in ('/'+bucket,'/'+bucket+'/')
                or parsed.fragment or parsed.query not in ('acl','versioning')
                or request.method!='GET'):
            raise ValueError('Unexpected configuration check destination')
    client.meta.events.register('before-send.s3',destination_guard)
    return client


def main():
    env=os.environ
    if not all(env.get(name) for name in SETTINGS):
        print(json.dumps({**result_base(),'status':'configuration_not_supplied'}));return 2
    try:result=check_configuration(make_client(env),env['HA_SPACES_BUCKET'])
    except Exception:
        # SDK diagnostics can contain bucket names, request IDs or credentials.
        print(json.dumps({**result_base(),'status':'configuration_check_unavailable'}));return 2
    print(json.dumps(result,sort_keys=True))
    return 0 if result['configuration_checks_passed'] else 1


if __name__=='__main__':raise SystemExit(main())
