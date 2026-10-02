"""Probe isolated Keycloak HTTPS/realm boundaries; no completed MFA claim."""
import argparse
from datetime import datetime,timedelta,timezone
import ipaddress
import json
import os
from pathlib import Path
import signal
import secrets
import hashlib
import base64
from urllib.parse import urlencode,urlparse,parse_qs
import ssl
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from cryptography import x509
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        return None

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--distribution',required=True)
    parser.add_argument('--report',required=True)
    parser.add_argument('--realm-file')
    parser.add_argument('--mfa-login',action='store_true')
    parser.add_argument('--connected-session',action='store_true')
    args=parser.parse_args()
    if args.connected_session and not args.mfa_login:raise ValueError('Connected probe requires MFA fixture')
    if args.mfa_login and not args.realm_file:raise ValueError('MFA probe requires realm file')
    if os.name!='posix':raise ValueError('Linux runtime probe required')
    distribution=Path(args.distribution).resolve(strict=True)
    with tempfile.TemporaryDirectory(prefix='ha-identity-') as folder:
        root=Path(folder)
        key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'HA fictional identity fixture')])
        now=datetime.now(timezone.utc)
        cert=(x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now-timedelta(minutes=1))
            .not_valid_after(now+timedelta(hours=2))
            .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address('127.0.0.1'))]),critical=False)
            .sign(key,hashes.SHA256()))
        (root/'cert.pem').write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        (root/'key.pem').write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
        (root/'key.pem').chmod(0o600)
        context=ssl.create_default_context(cafile=str(root/'cert.pem'))
        origin='https://127.0.0.1:8843'
        realm_name='master'
        if args.realm_file:
            realm=json.loads(Path(args.realm_file).read_text(encoding='utf-8'))
            if realm.get('realm')!='ha' or realm.get('users'):
                raise ValueError('Only the credential-free HA realm template is supported')
            realm_name='ha'
            realm['clients'][0]['redirectUris']=['https://127.0.0.1:8844/api/auth/callback']
            realm['clients'][0]['webOrigins']=['https://127.0.0.1:8844']
            if args.mfa_login:
                from verify_keycloak_mfa import fixture_user,verify_login
                user,password,otp_secret=fixture_user()
                realm['users']=[user]
            realm_file=root/'ha-realm.json'
            realm_file.write_text(json.dumps(realm),encoding='utf-8')
            realm_file.chmod(0o600)
            with (root/'import.log').open('wb') as import_log:
                subprocess.run(['bash',str(distribution/'bin/kc.sh'),'import','--file='+str(realm_file),
                    '--db-url=jdbc:h2:file:'+str(root/'database')+';NON_KEYWORDS=VALUE'],
                    stdout=import_log,stderr=import_log,check=True,timeout=180)
        with (root/'engine.log').open('wb') as log:
            process=subprocess.Popen(['bash',str(distribution/'bin/kc.sh'),'start-dev',
                '--db-url=jdbc:h2:file:'+str(root/'database')+';NON_KEYWORDS=VALUE',
                '--http-host=127.0.0.1','--http-enabled=false','--https-port=8843',
                '--hostname='+origin,'--https-certificate-file='+str(root/'cert.pem'),
                '--https-certificate-key-file='+str(root/'key.pem')],stdout=log,stderr=log,start_new_session=True)
            try:
                deadline=time.monotonic()+120
                while True:
                    if process.poll() is not None:raise RuntimeError('Local identity runtime exited')
                    try:
                        with urllib.request.urlopen(origin+'/realms/'+realm_name+'/.well-known/openid-configuration',context=context,timeout=2) as response:
                            discovery=json.load(response)
                        break
                    except (urllib.error.URLError,TimeoutError):
                        if time.monotonic()>deadline:raise TimeoutError('Local identity startup timed out')
                        time.sleep(1)
                if discovery['issuer']!=origin+'/realms/'+realm_name:raise ValueError('Issuer disagrees with HTTPS origin')
                if discovery['jwks_uri']!=origin+'/realms/'+realm_name+'/protocol/openid-connect/certs':raise ValueError('Unexpected keys endpoint')
                with urllib.request.urlopen(discovery['jwks_uri'],context=context,timeout=5) as response:
                    keys=json.load(response)['keys']
                if not any(item.get('kty')=='RSA' for item in keys):raise ValueError('RSA verification keys unavailable')
                realm_checks={}
                if args.realm_file:
                    endpoint=origin+'/realms/ha/protocol/openid-connect/'
                    parameters={'client_id':'ha-connected','redirect_uri':'https://127.0.0.1:8844/api/auth/callback',
                        'response_type':'code','scope':'openid','state':secrets.token_urlsafe(32),'nonce':secrets.token_urlsafe(32)}
                    no_redirect=urllib.request.build_opener(urllib.request.HTTPSHandler(context=context),NoRedirect())
                    try:
                        no_redirect.open(endpoint+'auth?'+urlencode(parameters),timeout=5)
                    except urllib.error.HTTPError as error:
                        if error.code!=302:raise
                        if error.code==302:
                            location=urlparse(error.headers.get('Location',''))
                            query=parse_qs(location.query)
                            if (location.scheme!='https' or location.netloc!='127.0.0.1:8844'
                                    or location.path!='/api/auth/callback' or query.get('error')!=['invalid_request']
                                    or 'code_challenge' not in query.get('error_description',[''])[0]):
                                raise ValueError('Unexpected missing-PKCE response')
                        realm_checks['missing_pkce_rejected']=True
                    else:raise ValueError('Missing PKCE accepted')
                    verifier=secrets.token_urlsafe(32)
                    parameters.update(code_challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('='),
                        code_challenge_method='S256',acr_values='2')
                    with urllib.request.urlopen(endpoint+'auth?'+urlencode(parameters),context=context,timeout=5) as response:
                        page=response.read(200000).decode('utf-8')
                    if 'name="password"' not in page:raise ValueError('Required password challenge unavailable')
                    realm_checks['password_challenge_available']=True
                    parameters['redirect_uri']='https://unrelated.example/api/auth/callback'
                    try:
                        urllib.request.urlopen(endpoint+'auth?'+urlencode(parameters),context=context,timeout=5)
                    except urllib.error.HTTPError as error:
                        if error.code!=400:raise
                        realm_checks['unregistered_callback_rejected']=True
                    else:raise ValueError('Unregistered callback accepted')
                    request=urllib.request.Request(endpoint+'token',data=urlencode({'client_id':'ha-connected',
                        'grant_type':'password','username':'fictional-unregistered','password':secrets.token_urlsafe(32)}).encode())
                    try:
                        urllib.request.urlopen(request,context=context,timeout=5)
                    except urllib.error.HTTPError as error:
                        body=json.loads(error.read(10000))
                        if error.code!=400 or body.get('error')!='unauthorized_client':raise ValueError('Direct grant not explicitly disabled')
                        realm_checks['password_direct_grant_disabled']=True
                    else:raise ValueError('Password direct grant accepted')
                mfa_checks=verify_login(origin,context,password,otp_secret,keys,NoRedirect) if args.mfa_login else {}
                session_checks={}
                if args.connected_session:
                    from verify_keycloak_session import verify_session
                    session_checks=verify_session(origin,context,password,otp_secret,keys,NoRedirect,root)
                report={'environment':'local Ubuntu Keycloak dev runtime only',
                    'https_discovery':'passed','hostname_and_certificate_verification':True,
                    'rsa_keys_available':True,'issuer':discovery['issuer'],
                    'mfa_login':'passed' if args.mfa_login else 'not_run','mfa_checks':mfa_checks,'application_realm':'ha_imported_and_discovered' if args.realm_file else 'not_configured_by_this_harness',
                    'realm_checks':realm_checks,'connected_session_checks':session_checks,
                    'realm_template_sha256':hashlib.sha256(Path(args.realm_file).read_bytes()).hexdigest() if args.realm_file else None,
                    'hosted_identity':'not_run','runtime_uploads_activated':False}
                Path(args.report).write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
                print(json.dumps(report))
            finally:
                if process.poll() is None:
                    os.killpg(process.pid,signal.SIGTERM)
                    try:process.wait(timeout=15)
                    except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait()

if __name__=='__main__':main()
