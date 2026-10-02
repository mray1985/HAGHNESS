"""Fictional protocol-level MFA journey; never emits credentials or tokens."""
import base64
import hashlib
import hmac
import http.cookiejar
import json
import secrets
import struct
import time
from html.parser import HTMLParser
from urllib.parse import urlencode,urlparse,parse_qs
import urllib.error
import urllib.request
import jwt
from ha.connected.keycloak import KeycloakVerifier

class Forms(HTMLParser):
    def __init__(self):
        super().__init__();self.forms=[];self.current=None
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag=='form':
            self.current={'action':attrs.get('action'),'inputs':{}};self.forms.append(self.current)
        if tag=='input' and self.current is not None and attrs.get('name'):
            self.current['inputs'][attrs['name']]=attrs.get('value','')
    def handle_endtag(self,tag):
        if tag=='form':self.current=None

def form(page,field,origin):
    parser=Forms();parser.feed(page)
    found=[item for item in parser.forms if field in item['inputs']]
    if len(found)!=1:raise ValueError('Expected authentication challenge unavailable')
    parsed=urlparse(found[0]['action'])
    if (parsed.scheme+'://'+parsed.netloc!=origin or
            not parsed.path.startswith('/realms/ha/login-actions/')):
        raise ValueError('Unexpected credential destination')
    return found[0]

def fixture_user():
    password=secrets.token_urlsafe(32)
    secret=secrets.token_urlsafe(24)
    user={'username':'ha-fictional-mfa','enabled':True,'firstName':'Fictional','lastName':'Fixture',
        'email':'fixture@example.invalid','emailVerified':True,'requiredActions':[],
        'credentials':[{'type':'password','value':password,'temporary':False},
            {'type':'otp','secretData':json.dumps({'value':secret}),
             'credentialData':json.dumps({'subType':'totp','digits':6,'counter':0,'period':30,'algorithm':'HmacSHA1'})}]}
    return user,password,secret

def totp(secret):
    digest=hmac.new(secret.encode(),struct.pack('>Q',int(time.time())//30),hashlib.sha1).digest()
    offset=digest[-1]&15
    return str((struct.unpack('>I',digest[offset:offset+4])[0]&0x7fffffff)%1000000).zfill(6)

def verify_login(origin,context,password,secret,keys,no_redirect_class):
    endpoint=origin+'/realms/ha/protocol/openid-connect/'
    nonce,state,verifier=[secrets.token_urlsafe(32) for _ in range(3)]
    callback='https://127.0.0.1:8844/api/auth/callback'
    params={'client_id':'ha-connected','redirect_uri':callback,'response_type':'code','scope':'openid',
        'state':state,'nonce':nonce,'code_challenge_method':'S256','max_age':'0',
        'claims':json.dumps({'id_token':{'acr':{'essential':True,'values':['2']}}}),
        'code_challenge':base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')}
    opener=urllib.request.build_opener(urllib.request.HTTPSHandler(context=context),
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),no_redirect_class())
    def read(request):
        with opener.open(request,timeout=10) as response:return response.read(200000).decode('utf-8')
    page=read(endpoint+'auth?'+urlencode(params))
    challenge=form(page,'password',origin)
    fields={**challenge['inputs'],'username':'ha-fictional-mfa','password':password}
    page=read(urllib.request.Request(challenge['action'],data=urlencode(fields).encode()))
    challenge=form(page,'otp',origin)  # Password alone must return another challenge, not a code.
    wrong=str((int(totp(secret))+1)%1000000).zfill(6)
    page=read(urllib.request.Request(challenge['action'],data=urlencode({**challenge['inputs'],'otp':wrong}).encode()))
    challenge=form(page,'otp',origin)  # Incorrect OTP must not issue a code.
    try:
        read(urllib.request.Request(challenge['action'],data=urlencode({**challenge['inputs'],'otp':totp(secret)}).encode()))
    except urllib.error.HTTPError as error:
        if error.code!=302:raise ValueError('MFA did not produce expected callback') from None
        location=urlparse(error.headers.get('Location',''))
        query=parse_qs(location.query)
        if (location.scheme+'://'+location.netloc+location.path!=callback
                or query.get('state')!=[state] or len(query.get('code',[]))!=1 or query.get('error')):
            raise ValueError('Invalid MFA callback') from None
        code=query['code'][0]
    else:raise ValueError('MFA did not return authorization code')
    request=urllib.request.Request(endpoint+'token',data=urlencode({'grant_type':'authorization_code',
        'client_id':'ha-connected','redirect_uri':callback,'code':code,'code_verifier':verifier}).encode())
    try:tokens=json.loads(read(request))
    except urllib.error.HTTPError:raise ValueError('MFA token exchange failed') from None
    def resolve(token):
        kid=jwt.get_unverified_header(token)['kid']
        matched=[key for key in keys if key.get('kid')==kid and key.get('kty')=='RSA']
        if len(matched)!=1:raise ValueError('Unexpected signing key')
        return jwt.PyJWK.from_dict(matched[0]).key
    principal=KeycloakVerifier(origin+'/realms/ha','ha-connected',resolve).verify(tokens['id_token'],nonce)
    if not principal.mfa_verified:raise ValueError('Application rejected MFA evidence')
    try:read(request)
    except urllib.error.HTTPError as error:
        if error.code!=400 or json.loads(error.read(10000)).get('error')!='invalid_grant':
            raise ValueError('Unexpected authorization-code replay response') from None
    else:raise ValueError('Authorization-code replay accepted')
    return {'password_alone_requires_otp':True,'incorrect_otp_rejected':True,
        'correct_otp_completed':True,'signed_token_accepted_by_ha_verifier':True,
        'authorization_code_replay_rejected':True,'otp_enrollment':'pre-enrolled fictional fixture; not tested',
        'application_session_reuse':'not_run'}
