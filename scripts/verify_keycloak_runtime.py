"""Probe real local Keycloak HTTPS discovery; does not claim MFA verification."""
import argparse
from datetime import datetime,timedelta,timezone
import ipaddress
import json
import os
from pathlib import Path
import signal
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

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--distribution',required=True)
    parser.add_argument('--report',required=True)
    args=parser.parse_args()
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
                        with urllib.request.urlopen(origin+'/realms/master/.well-known/openid-configuration',context=context,timeout=2) as response:
                            discovery=json.load(response)
                        break
                    except (urllib.error.URLError,TimeoutError):
                        if time.monotonic()>deadline:raise TimeoutError('Local identity startup timed out')
                        time.sleep(1)
                if discovery['issuer']!=origin+'/realms/master':raise ValueError('Issuer disagrees with HTTPS origin')
                if discovery['jwks_uri']!=origin+'/realms/master/protocol/openid-connect/certs':raise ValueError('Unexpected keys endpoint')
                with urllib.request.urlopen(discovery['jwks_uri'],context=context,timeout=5) as response:
                    keys=json.load(response)['keys']
                if not any(item.get('kty')=='RSA' for item in keys):raise ValueError('RSA verification keys unavailable')
                report={'environment':'local Ubuntu Keycloak dev runtime only',
                    'https_discovery':'passed','hostname_and_certificate_verification':True,
                    'rsa_keys_available':True,'issuer':discovery['issuer'],
                    'mfa_login':'not_run','application_realm':'not_configured_by_this_harness',
                    'hosted_identity':'not_run','runtime_uploads_activated':False}
                Path(args.report).write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
                print(json.dumps(report))
            finally:
                if process.poll() is None:
                    os.killpg(process.pid,signal.SIGTERM)
                    try:process.wait(timeout=15)
                    except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait()

if __name__=='__main__':main()
