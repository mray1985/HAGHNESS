"""Independent Keycloak code/PKCE login with signed MFA evidence.

Requires an operator-configured realm flow and AMR mapper: LoA2 = required
password plus OTP, execution references pwd/otp. This adapter does not prove
the realm's deployed policy, recovery controls or hosted MFA journey.
"""
import base64
import hashlib
import json
import re
import secrets
import time
from datetime import datetime,timezone
from threading import RLock
from urllib.parse import urlencode,urlparse
import jwt
from .domain import Principal
from .oauth import exchange_token

def validate_issuer(issuer):
    if not isinstance(issuer,str):raise ValueError('HTTPS Keycloak realm issuer required')
    parsed=urlparse(issuer)
    if (parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password
            or parsed.query or parsed.fragment or not re.fullmatch(r'(?:/[a-zA-Z0-9_-]+)*/realms/[a-zA-Z0-9_-]+',parsed.path)):
        raise ValueError('HTTPS Keycloak realm issuer required')
    return issuer

class KeycloakVerifier:
    def __init__(self,issuer,client_id,key_resolver):
        self.issuer=validate_issuer(issuer)
        self.client_id=client_id
        self.key_resolver=key_resolver

    def verify(self,token,nonce):
        if not isinstance(nonce,str) or not nonce:raise PermissionError('Authentication required')
        try:
            claims=jwt.decode(token,self.key_resolver(token),algorithms=['RS256'],
                              audience=self.client_id,issuer=self.issuer,
                              options={'require':['exp','iat','sub','iss','aud','nonce','acr','amr','auth_time','typ','azp']})
            methods=claims['amr']
            auth_time=claims['auth_time']
            now=datetime.now(timezone.utc).timestamp()
            if (claims['typ']!='ID' or claims['azp']!=self.client_id
                    or not isinstance(claims['sub'],str) or not claims['sub'] or '|' in claims['sub']
                    or not isinstance(claims['nonce'],str) or not secrets.compare_digest(claims['nonce'],nonce)
                    or claims['acr']!='2' or not isinstance(methods,list)
                    or not all(isinstance(method,str) for method in methods)
                    or not {'pwd','otp'}.issubset(methods)
                    or isinstance(auth_time,bool) or not isinstance(auth_time,(int,float))
                    or not 0<=now-auth_time<=600):
                raise ValueError('Invalid MFA token context')
            return Principal(self.issuer+'|'+claims['sub'],datetime.fromtimestamp(claims['exp'],timezone.utc),True)
        except (jwt.PyJWTError,ValueError,TypeError,KeyError,OverflowError) as error:
            raise PermissionError('Authentication required') from error

class KeycloakLogin:
    def __init__(self,issuer,client_id,redirect_uri,verifier,exchange=exchange_token):
        self.issuer=validate_issuer(issuer)
        callback=urlparse(redirect_uri)
        if callback.scheme!='https' or not callback.hostname or callback.username or callback.password or callback.fragment:
            raise ValueError('HTTPS callback required')
        if not isinstance(client_id,str) or not client_id or len(client_id)>200:
            raise ValueError('Client ID required')
        self.client,self.redirect,self.verifier,self.exchange=client_id,redirect_uri,verifier,exchange
        self.pending,self.lock={},RLock()

    def begin(self):
        state,cookie,nonce,verifier=[secrets.token_urlsafe(32) for _ in range(4)]
        challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
        with self.lock:
            self.pending={key:value for key,value in self.pending.items() if value['expires']>time.monotonic()}
            if len(self.pending)>=1000:raise PermissionError('Try signing in later')
            self.pending[state]=dict(cookie_hash=hashlib.sha256(cookie.encode()).digest(),nonce=nonce,verifier=verifier,expires=time.monotonic()+600)
        query=urlencode(dict(response_type='code',client_id=self.client,redirect_uri=self.redirect,scope='openid',state=state,nonce=nonce,code_challenge=challenge,code_challenge_method='S256',max_age='0',claims=json.dumps({'id_token':{'acr':{'essential':True,'values':['2']}}},separators=(',',':'))))
        return self.issuer+'/protocol/openid-connect/auth?'+query,cookie

    def complete(self,code,state,browser_cookie):
        if not all(isinstance(value,str) and 0<len(value)<=4096 for value in (code,state,browser_cookie)):
            raise PermissionError('Authentication required')
        with self.lock:pending=self.pending.pop(state,None)
        if (pending is None or pending['expires']<=time.monotonic()
                or not secrets.compare_digest(pending['cookie_hash'],hashlib.sha256(browser_cookie.encode()).digest())):
            raise PermissionError('Authentication required')
        response=self.exchange(self.issuer+'/protocol/openid-connect/token',dict(grant_type='authorization_code',client_id=self.client,code=code,code_verifier=pending['verifier'],redirect_uri=self.redirect))
        if not isinstance(response,dict) or not isinstance(response.get('id_token'),str):
            raise PermissionError('Authentication required')
        return self.verifier.verify(response['id_token'],pending['nonce'])
