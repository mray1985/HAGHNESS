"""Read-only DigitalOcean account prerequisite, never a deployment approval."""
import json
import os
import re
import urllib.request

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None


def check_account(token,*,open_request=None):
    if not isinstance(token,str) or not re.fullmatch(r'[\x21-\x7e]{16,512}',token):
        raise ValueError('Configured account token required')
    request=urllib.request.Request('https://api.digitalocean.com/v2/account',
        headers={'Authorization':'Bearer '+token,'Accept':'application/json'},method='GET')
    opener=open_request or urllib.request.build_opener(NoRedirect()).open
    with opener(request,timeout=15) as response:
        if response.status!=200:raise ValueError('Account check unavailable')
        payload=response.read(65537)
        if len(payload)>65536:raise ValueError('Account response exceeds limit')
    def unique(pairs):
        value={}
        for key,item in pairs:
            if key in value:raise ValueError('Duplicate account field')
            value[key]=item
        return value
    account=json.loads(payload.decode('utf-8'),object_pairs_hook=unique)['account']
    if account.get('status') not in ('active','warning','locked') or type(account.get('email_verified')) is not bool:
        raise ValueError('Invalid account status')
    return {'account_status':account['status'],'email_verified':account['email_verified'],
        'account_prerequisite_passed':account['status']=='active' and account['email_verified'],
        'resources_created':False,'deployment_verified':False}


def main():
    token=os.environ.get('DIGITALOCEAN_ACCESS_TOKEN')
    if not token:
        print(json.dumps({'status':'token_not_configured','resources_created':False,'deployment_verified':False}))
        return 2
    try:result=check_account(token)
    except Exception:
        print(json.dumps({'status':'account_check_unavailable','resources_created':False,'deployment_verified':False}))
        return 2
    print(json.dumps(result,sort_keys=True))
    return 0 if result['account_prerequisite_passed'] else 1

if __name__=='__main__':raise SystemExit(main())
