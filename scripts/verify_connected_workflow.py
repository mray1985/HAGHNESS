"""Fictional HTTPS/PostgreSQL/encrypted-file integration and timing evidence.

Uses a locally signed identity fixture and explicit synthetic scan bypass.
Never asserts hosted MFA, real malware detection, payments or filing readiness.
Creates a new isolated fixture database; existing databases are untouched.
"""
import base64
from datetime import datetime,timedelta,timezone
from http.client import HTTPSConnection
import ipaddress
import json
import math
from pathlib import Path
import ssl
import threading
import time
import uuid
import jwt
import psycopg
from psycopg.conninfo import conninfo_to_dict,make_conninfo
from cryptography import x509
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.x509.oid import NameOID
from ha.connected.api import create_server
from ha.connected.auth import Sessions
from ha.connected.documents import Documents
from ha.connected.encrypted_objects import EncryptedLocalObjects
from ha.connected.keycloak import KeycloakVerifier
from ha.connected.postgres import PostgresRepository,PostgresLedger

ROOT=Path(__file__).resolve().parents[1]
LOCAL=ROOT/'.connected-local'

def validate_fixture_config(config):
    params=conninfo_to_dict(config['dsn'])
    if (config.get('synthetic_only') is not True or params.get('host')!='127.0.0.1'
            or params.get('port')!='55432' or params.get('user')!='ha_test_admin' or params.get('dbname')!='postgres'):
        raise ValueError('Only isolated fictional PostgreSQL is permitted')
    return params

def check_draft(draft):
    expected={'income_minor':150000,'expense_minor':32000,'book_profit_minor':118000,
              'reserve_scenario_minor':37500,'owner_payments_recorded_minor':10000,
              'owner_payments_confirmed_minor':0,'missing_receipts':['advertising'],
              'cash_explanations_missing':[],
              'support_review_required':['sale-card','sale-cash','advertising','supplies-correction'],
              'support_review_complete':False,
              'tax_liability_minor':None,'may_prepare_return':False,'filing_authorized':False}
    for name,value in expected.items():
        if draft.get(name)!=value:raise ValueError('Connected draft mismatch: '+name)

def main():
    config=json.loads((LOCAL/'test-database.json').read_text())
    params=validate_fixture_config(config)
    name='ha_workflow_'+uuid.uuid4().hex
    with psycopg.connect(config['dsn'],autocommit=True) as conn:
        conn.execute(psycopg.sql.SQL('CREATE DATABASE {}').format(psycopg.sql.Identifier(name)))
    repository=PostgresRepository(make_conninfo(**{**params,'dbname':name}))
    repository.migrate()
    with repository.transaction() as conn:
        conn.execute("INSERT INTO ha_connected.profiles VALUES ('cedar-unrelated')")
        conn.execute("INSERT INTO ha_connected.businesses VALUES ('cedar-business','cedar-unrelated')")
    run_id=uuid.uuid4().hex
    files=LOCAL/('workflow-'+run_id);files.mkdir()
    key_root=LOCAL/'recovery-keys';key_root.mkdir(exist_ok=True)
    key_path=key_root/(run_id+'.key');key_path.write_bytes(AESGCM.generate_key(bit_length=256))
    documents=Documents(repository,EncryptedLocalObjects(files/'objects',key_path.read_bytes),lambda data,mime:True)
    sessions=Sessions()
    server=create_server(('127.0.0.1',0),sessions,PostgresLedger(repository),documents,None,'https://ha.example')
    signing_key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    now=datetime.now(timezone.utc)
    identity=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'fictional local workflow')])
    certificate=(x509.CertificateBuilder().subject_name(identity).issuer_name(identity)
        .public_key(signing_key.public_key()).serial_number(x509.random_serial_number())
        .not_valid_before(now-timedelta(minutes=1)).not_valid_after(now+timedelta(hours=1))
        .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address('127.0.0.1'))]),critical=False)
        .sign(signing_key,hashes.SHA256()))
    cert=files/'localhost.pem';cert.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    private=files/'localhost.key';private.write_bytes(signing_key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
    server_tls=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);server_tls.minimum_version=ssl.TLSVersion.TLSv1_2
    server_tls.load_cert_chain(cert,private);server.socket=server_tls.wrap_socket(server.socket,server_side=True)
    client_tls=ssl.create_default_context(cafile=str(cert))
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    samples=[]
    fixture=json.loads((ROOT/'docs/fixtures/day8-connected-workflow.json').read_text())
    try:
        for trial in range(5):
            profile='orchard-'+str(trial);business='business-'+str(trial)
            issuer='https://identity.example/realms/fictional'
            subject=issuer+'|owner-'+str(trial)
            with repository.transaction() as conn:
                conn.execute('INSERT INTO ha_connected.profiles VALUES (%s)',(profile,))
                conn.execute('INSERT INTO ha_connected.businesses VALUES (%s,%s)',(business,profile))
                for action in ('read','post','correct','upload','restore'):
                    conn.execute('INSERT INTO ha_connected.grants VALUES (%s,%s,%s,%s,%s)',(subject,profile,business,2026,action))
            stamp=int(time.time())
            token=jwt.encode(dict(iss=issuer,aud='fixture',azp='fixture',sub='owner-'+str(trial),iat=stamp,
                exp=stamp+600,nonce='fixture',acr='2',amr=['pwd','otp'],auth_time=stamp,typ='ID'),signing_key,algorithm='RS256')
            principal=KeycloakVerifier(issuer,'fixture',lambda token:signing_key.public_key()).verify(token,'fixture')
            cookie,csrf=sessions.open(principal)
            scope={'profile':profile,'business':business,'year':2026}
            query=f'profile={profile}&business={business}&year=2026'
            def request(method,path,payload=None,expected=200,signed=True,verified=True):
                connection=HTTPSConnection(*server.server_address,context=client_tls,timeout=10)
                headers={'Origin':'https://ha.example'}
                if signed:headers['Cookie']='__Host-ha_session='+cookie
                if verified:headers['X-HA-CSRF']=csrf
                body=json.dumps(payload) if payload is not None else None
                if body is not None:headers['Content-Type']='application/json'
                try:
                    connection.request(method,path,body,headers)
                    response=connection.getresponse();result=json.loads(response.read())
                    if response.status!=expected:raise ValueError('Unexpected workflow HTTP status')
                    return result
                finally:connection.close()
            started=time.perf_counter()
            request('GET','/api/auth/me')
            request('GET','/api/connected/draft?'+query,expected=401,signed=False)
            request('GET','/api/connected/draft?profile=cedar-unrelated&business=cedar-business&year=2026',expected=404)
            payload={'scope':scope,'mime':'text/plain','data':base64.b64encode(b'fictional original receipt').decode(),'idempotency_key':'original'}
            request('POST','/api/connected/documents',payload,expected=403,verified=False)
            original=request('POST','/api/connected/documents',payload,expected=201)
            for event in fixture['events'][:4]:request('POST','/api/connected/events',{'scope':scope,'event':event},expected=201)
            before=request('GET','/api/connected/draft?'+query)
            if before['book_profit_minor']!=120000:raise ValueError('Initial draft mismatch')
            for event in fixture['events'][4:]:request('POST','/api/connected/events',{'scope':scope,'event':event},expected=201)
            request('POST','/api/connected/events',{'scope':scope,'event':fixture['events'][0]},expected=201)
            for period in ('month','quarter','year'):
                draft=request('GET','/api/connected/draft?'+query+'&period='+period+'&month=10')
                check_draft(draft)
                if draft['ledger_revision']!=6:raise ValueError('Retry duplicated an entry')
            if request('GET','/api/connected/draft?'+query+'&period=month&month=11')['book_profit_minor']!=0:
                raise ValueError('Monthly rollup leaked entries from another month')
            corrected=request('POST','/api/connected/document/corrections',
                {**payload,'document':original['document_id'],'reason':'Fictional correction','idempotency_key':'corrected',
                 'data':base64.b64encode(b'fictional corrected receipt').decode()},expected=201)
            if corrected['previous_version_id']!=original['version_id']:raise ValueError('Original version link lost')
            for version,text in ((original,b'fictional original receipt'),(corrected,b'fictional corrected receipt')):
                suffix='&document='+version['document_id']+'&version='+version['version_id']
                data=request('GET','/api/connected/document?'+query+suffix)
                if base64.b64decode(data['data'])!=text:raise ValueError('Document version mismatch')
                request('GET','/api/connected/document?profile=cedar-unrelated&business=cedar-business&year=2026'+suffix,expected=404)
            listing=request('GET','/api/connected/documents?'+query)
            if len(listing['versions'])!=2:raise ValueError('Document versions not preserved')
            request('POST','/api/auth/logout',{})
            request('GET','/api/auth/me',expected=401)
            samples.append(round(time.perf_counter()-started,4))
    finally:
        server.shutdown();server.server_close();thread.join()
    ordered=sorted(samples)
    report={'environment':'local fictional HTTPS + real PostgreSQL + encrypted files',
        'trials':len(samples),'elapsed_seconds_per_trial':samples,
        'p50_seconds':ordered[len(ordered)//2],'p95_seconds':ordered[math.ceil(len(ordered)*.95)-1],
        'timing_scope':'automated API workflow only; excludes user entry, hosted login and settlement',
        'identity':'locally signed MFA-claim fixture; no hosted realm or OAuth policy proof',
        'scanner':'explicit synthetic bypass; no malware-detection proof',
        'tls':'verified local certificate and hostname; no disabled certificate checks',
        'session':'same opaque session for books/documents; CSRF, unrelated scope and logout denials passed',
        'ledger':'card/cash, missing receipt, correction, retry, monthly/quarterly/annual projections passed',
        'book_profit_minor':118000,'reserve_scenario_minor':37500,
        'owner_payment_recorded_minor':10000,'owner_payment_confirmed_minor':0,
        'documents':'original and correction retrieved separately; cross-profile denial passed',
        'existing_databases_modified':False,'money_moved':False,'filing_authorized':False,
        'hosted_workflow':'not_run','complete_tax_calculation':'not_implemented'}
    (ROOT/'docs/CONNECTED-WORKFLOW-EVIDENCE.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))

if __name__=='__main__':main()
