"""Real local MFA -> HTTPS session -> PostgreSQL/books/scanned encrypted documents.

Own isolated PostgreSQL cluster/ClamD; no hosted resource or existing DB changes.
"""
import base64
from contextlib import contextmanager
import http.cookiejar
import json
import os
import re
from pathlib import Path
import pwd
import ssl
import shutil
import subprocess
import tempfile
import threading
import time
from urllib.parse import urlencode,urlparse,parse_qs
import urllib.error
import urllib.request
import jwt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from ha.connected.api import create_server
from ha.connected.auth import Sessions
from ha.connected.documents import Documents
from ha.connected.encrypted_objects import EncryptedLocalObjects
from ha.connected.keycloak import KeycloakLogin,KeycloakVerifier
from ha.connected.postgres import PostgresRepository,PostgresLedger
from ha.connected.scanner import ClamDScanner
if __package__:
    from .verify_keycloak_mfa import form,totp
else:
    from verify_keycloak_mfa import form,totp

@contextmanager
def isolated_database():
    if os.geteuid()!=0:raise ValueError('Root fixture orchestration required for isolated postgres user')
    binary=Path('/usr/lib/postgresql/16/bin')
    account=pwd.getpwnam('postgres')
    root=Path(tempfile.mkdtemp(prefix='ha-mfa-database-'))
    safe_remove=True
    try:
        os.chown(root,account.pw_uid,account.pw_gid);root.chmod(0o700)
        def command(*args):
            subprocess.run(['runuser','-u','postgres','--',*map(str,args)],check=True,
                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=60)
        command(binary/'initdb','-D',root/'data','-U','ha_fixture','--auth-local=trust','--auth-host=reject')
        try:
            command(binary/'pg_ctl','-D',root/'data','-l',root/'database.log','-o',
                "-c listen_addresses='' -k "+str(root)+' -p 55439','-w','start')
            yield 'host='+str(root)+' port=55439 user=ha_fixture dbname=postgres'
        finally:
            if (root/'data/postmaster.pid').exists():
                safe_remove=False
                command(binary/'pg_ctl','-D',root/'data','-m','fast','-w','stop')
                safe_remove=True
    finally:
        # Preserve a private fixture cluster for diagnosis if shutdown failed.
        # Never remove files beneath a potentially running database.
        if safe_remove:shutil.rmtree(root)

@contextmanager
def isolated_scanner(root):
    database=root/'signatures';database.mkdir()
    for item in Path('/var/lib/clamav').iterdir():
        if item.suffix in ('.cvd','.cld'):(database/item.name).symlink_to(item)
    policy=Path(__file__).resolve().parents[1]/'deploy/digitalocean/droplet/ha-container-policy.cdb'
    (database/policy.name).write_bytes(policy.read_bytes())
    socket=root/'clamd.sock';config=root/'clamd.conf'
    config.write_text(f"""Foreground yes
DatabaseDirectory {database}
LocalSocket {socket}
LocalSocketMode 660
TemporaryDirectory {root}
StreamMaxLength 25M
MaxFileSize 25M
MaxScanSize 100M
ScanPDF yes
ScanArchive yes
HeuristicAlerts yes
AlertExceedsMax yes
AlertEncrypted yes
LeaveTemporaryFiles no
""",encoding='utf-8')
    with (root/'scanner.log').open('wb') as log:
        process=subprocess.Popen(['clamd','--config-file='+str(config)],stdout=log,stderr=log)
        try:
            deadline=time.monotonic()+60
            while not socket.exists():
                if process.poll() is not None:raise RuntimeError('Fixture scanner exited')
                if time.monotonic()>deadline:raise TimeoutError('Fixture scanner startup timed out')
                time.sleep(.1)
            yield ClamDScanner(str(socket))
        finally:
            if process.poll() is None:
                process.terminate()
                try:process.wait(timeout=15)
                except subprocess.TimeoutExpired:process.kill();process.wait()

def verify_session(identity_origin,context,password,secret,keys,no_redirect_class,root):
    # The preceding MFA probe consumed this fixture's current TOTP counter.
    # Wait for the next period instead of relying on reusable OTP policy.
    time.sleep(31-time.time()%30)
    app_origin='https://127.0.0.1:8844'
    with isolated_database() as dsn,isolated_scanner(root) as scanner:
        repository=PostgresRepository(dsn);repository.migrate()
        key=AESGCM.generate_key(bit_length=256)
        objects=EncryptedLocalObjects(root/'objects',lambda:key)
        documents=Documents(repository,objects,scanner)
        def exchange(url,fields):
            if url!=identity_origin+'/realms/ha/protocol/openid-connect/token':raise ValueError('Unexpected exchange destination')
            with urllib.request.urlopen(urllib.request.Request(url,data=urlencode(fields).encode()),context=context,timeout=10) as response:
                return json.load(response)
        def resolve(token):
            kid=jwt.get_unverified_header(token)['kid']
            matched=[item for item in keys if item.get('kid')==kid and item.get('kty')=='RSA']
            if len(matched)!=1:raise ValueError('Unknown signing key')
            return jwt.PyJWK.from_dict(matched[0]).key
        login=KeycloakLogin(identity_origin+'/realms/ha','ha-connected',app_origin+'/api/auth/callback',
            KeycloakVerifier(identity_origin+'/realms/ha','ha-connected',resolve),exchange=exchange)
        server=create_server(('127.0.0.1',8844),Sessions(),PostgresLedger(repository),documents,login,app_origin)
        tls=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);tls.minimum_version=ssl.TLSVersion.TLSv1_2
        tls.load_cert_chain(root/'cert.pem',root/'key.pem');server.socket=tls.wrap_socket(server.socket,server_side=True)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        jar=http.cookiejar.CookieJar()
        opener=urllib.request.build_opener(urllib.request.HTTPSHandler(context=context),
            urllib.request.HTTPCookieProcessor(jar),no_redirect_class())
        def call(url,data=None,expected=200,headers=None):
            try:response=opener.open(urllib.request.Request(url,data=data,headers=headers or {}),timeout=10)
            except urllib.error.HTTPError as error:response=error
            with response:
                status=response.code;body=response.read(200000);result_headers=response.headers
            if status!=expected:raise ValueError('Unexpected local connected HTTP status: '+str(status))
            return body,result_headers
        def api(method,path,payload=None,status=200,csrf=None):
            headers={'Origin':app_origin}
            if csrf:headers['X-HA-CSRF']=csrf
            data=json.dumps(payload).encode() if method=='POST' else None
            if data is not None:headers['Content-Type']='application/json'
            return json.loads(call(app_origin+path,data,status,headers)[0])
        try:
            api('GET','/api/auth/me',status=401)
            api('GET','/api/connected/cases',status=401)
            _,headers=call(app_origin+'/api/auth/login',expected=302)
            login_url=headers['Location'];params=parse_qs(urlparse(login_url).query)
            page=call(login_url)[0].decode('utf-8')
            challenge=form(page,'password',identity_origin)
            fields={**challenge['inputs'],'username':'ha-fictional-mfa','password':password}
            page=call(challenge['action'],urlencode(fields).encode())[0].decode('utf-8')
            challenge=form(page,'otp',identity_origin)
            _,headers=call(challenge['action'],urlencode({**challenge['inputs'],'otp':totp(secret)}).encode(),302)
            callback=headers['Location'];parsed=urlparse(callback);query=parse_qs(parsed.query)
            if (parsed.scheme+'://'+parsed.netloc+parsed.path!=app_origin+'/api/auth/callback'
                    or query.get('state')!=params['state'] or len(query.get('code',[]))!=1):
                raise ValueError('Unexpected connected callback')
            _,headers=call(callback,expected=302)
            if headers['Location']!='/connected.html':raise ValueError('Unexpected post-login route')
            session_headers=headers.get_all('Set-Cookie')
            if not any('__Host-ha_session=' in item and all(flag in item for flag in ('Secure','HttpOnly','SameSite=Lax','Path=/')) for item in session_headers):
                raise ValueError('Secure opaque session cookie unavailable')
            identity=api('GET','/api/auth/me');csrf=identity['csrf'];subject=identity['subject']
            if not subject.startswith(identity_origin+'/realms/ha|'):raise ValueError('Identity issuer not preserved')
            with repository.transaction() as conn:
                for profile,business in (('orchard','business'),('cedar','cedar-business')):
                    conn.execute('INSERT INTO ha_connected.profiles VALUES (%s)',(profile,))
                    conn.execute('INSERT INTO ha_connected.businesses VALUES (%s,%s)',(business,profile))
                for action in ('read','post','correct','upload','restore'):
                    conn.execute('INSERT INTO ha_connected.grants VALUES (%s,%s,%s,%s,%s)',(subject,'orchard','business',2026,action))
            scope={'profile':'orchard','business':'business','year':2026};query='profile=orchard&business=business&year=2026'
            if api('GET','/api/connected/cases')!={'cases':[scope]}:raise ValueError('Case list scope mismatch')
            fixture=json.loads((Path(__file__).resolve().parents[1]/'docs/fixtures/day8-connected-workflow.json').read_text(encoding='utf-8'))
            for event in fixture['events']:api('POST','/api/connected/events',{'scope':scope,'event':event},status=201,csrf=csrf)
            draft=api('GET','/api/connected/draft?'+query)
            if draft['book_profit_minor']!=118000 or draft['owner_payments_confirmed_minor']!=0:raise ValueError('Book projection mismatch')
            api('GET','/api/connected/draft?profile=cedar&business=cedar-business&year=2026',status=404)
            linked=api('POST','/api/connected/return/estimate',{'scope':scope,'scenario':{'tax_year':'2026','w2s':[{'box1':45000,'box2':5200}]}},csrf=csrf)
            if linked['business_draft']['book_profit_minor']!=118000 or linked['refund'] is not None:raise ValueError('Tax handoff mismatch')
            payload={'scope':scope,'mime':'text/plain','data':base64.b64encode(b'Fictional receipt original').decode(),'idempotency_key':'original'}
            api('POST','/api/connected/documents',payload,status=403)
            original=api('POST','/api/connected/documents',payload,status=201,csrf=csrf)
            review={'scope':scope,'review':{'event_id':'advertising','decision':'accepted',
                'reason':'Fictional receipt checked','idempotency_key':'live-review',
                'document_id':original['document_id'],'version_id':original['version_id']}}
            api('POST','/api/connected/support/reviews',review,status=403)
            api('POST','/api/connected/support/reviews',review,status=404,csrf=csrf)
            with repository.transaction() as conn:
                conn.execute('INSERT INTO ha_connected.grants VALUES (%s,%s,%s,%s,%s)',
                    (subject,'orchard','business',2026,'review_support'))
            accepted=api('POST','/api/connected/support/reviews',review,status=201,csrf=csrf)
            if api('POST','/api/connected/support/reviews',review,status=201,csrf=csrf)!=accepted:
                raise ValueError('Review retry changed decision')
            if 'advertising' in api('GET','/api/connected/draft?'+query)['support_review_required']:
                raise ValueError('Accepted support remains queued')
            api('GET','/api/connected/support/reviews?profile=cedar&business=cedar-business&year=2026',status=404)
            corrected=api('POST','/api/connected/document/corrections',{**payload,'document':original['document_id'],
                'reason':'Fictional correction','idempotency_key':'correction','data':base64.b64encode(b'Fictional receipt correction').decode()},status=201,csrf=csrf)
            for version,text in ((original,b'Fictional receipt original'),(corrected,b'Fictional receipt correction')):
                suffix='&document='+version['document_id']+'&version='+version['version_id']
                result=api('GET','/api/connected/document?'+query+suffix)
                if base64.b64decode(result['data'])!=text:raise ValueError('Preserved document read mismatch')
                api('GET','/api/connected/document?profile=cedar&business=cedar-business&year=2026'+suffix,status=404)
            reviewed_draft=api('GET','/api/connected/draft?'+query)
            advertising=next(item for item in reviewed_draft['support_review_queue'] if item['event_id']=='advertising')
            if 'document_changed' not in advertising['reasons']:raise ValueError('Corrected support did not reopen')
            if len(api('GET','/api/connected/support/reviews?'+query)['reviews'])!=1:
                raise ValueError('Review history changed')
            tax_input={'year':'2026','profile':{'firstName':'Fictional tax original','ssn':'000-00-0000'},
                       'forms':[{'layout':'standard','box1':'001.20','box2':'',
                                 'states':[{'state':'LA','tax':''},{'state':'TX'}]}],
                       'active':0,'stateAnswers':{'state-move':'Yes'}}
            tax_save={'scope':scope,'save':{'input':tax_input,'expected_snapshot_id':None,
                      'reason':'','idempotency_key':'real-mfa-tax-original'}}
            api('POST','/api/connected/tax/inputs',tax_save,status=403)
            api('POST','/api/connected/tax/inputs',tax_save,status=404,csrf=csrf)
            if api('GET','/api/connected/tax/inputs?'+query)['can_save']:
                raise ValueError('Missing tax edit grant advertised as permitted')
            with repository.transaction() as conn:
                conn.execute('INSERT INTO ha_connected.grants VALUES (%s,%s,%s,%s,%s)',
                             (subject,'orchard','business',2026,'save_tax'))
            tax_original=api('POST','/api/connected/tax/inputs',tax_save,status=201,csrf=csrf)
            if tax_original['actor']!=subject:raise ValueError('Tax saved actor differs from MFA identity')
            if api('POST','/api/connected/tax/inputs',tax_save,status=201,csrf=csrf)!=tax_original:
                raise ValueError('Tax retry changed snapshot')
            tax_changed=json.loads(json.dumps(tax_input))
            tax_changed['profile']['firstName']='Fictional tax corrected'
            tax_changed['forms'][0]['box1']='200.00'
            tax_correction={'scope':scope,'save':{'input':tax_changed,
                            'expected_snapshot_id':tax_original['snapshot_id'],
                            'reason':'Corrected fictional wage entry','idempotency_key':'real-mfa-tax-corrected'}}
            tax_corrected=api('POST','/api/connected/tax/inputs',tax_correction,status=201,csrf=csrf)
            current=api('GET','/api/connected/tax/input?'+query)
            prior=api('GET','/api/connected/tax/input?'+query+'&snapshot='+tax_original['snapshot_id'])
            if current!={'snapshot':tax_corrected,'input':tax_changed} or prior!={'snapshot':tax_original,'input':tax_input}:
                raise ValueError('Tax input versions did not reopen exactly')
            tax_history=api('GET','/api/connected/tax/inputs?'+query)
            if len(tax_history['history'])!=2 or not tax_history['can_save']:
                raise ValueError('Tax history/edit capability mismatch')
            api('POST','/api/connected/tax/inputs',{'scope':scope,'save':{**tax_correction['save'],
                'idempotency_key':'real-mfa-tax-stale'}},status=400,csrf=csrf)
            api('GET','/api/connected/tax/input?profile=cedar&business=cedar-business&year=2026',status=404)
            api('GET','/api/connected/tax/inputs?profile=cedar&business=cedar-business&year=2026',status=404)
            reopened_estimate=api('POST','/api/connected/return/estimate',{'scope':scope,
                'scenario':{'tax_year':'2026','w2s':[{'box1':current['input']['forms'][0]['box1'],'box2':''}]}},csrf=csrf)
            if (reopened_estimate['wages']!=200 or reopened_estimate['refund'] is not None
                    or reopened_estimate['balance_due'] is not None or reopened_estimate['may_prepare_return'] is not False
                    or reopened_estimate['business_draft']['book_profit_minor']!=118000):
                raise ValueError('Reopened tax draft differs from connected records')
            with repository.transaction() as conn:
                conn.execute("DELETE FROM ha_connected.grants WHERE subject=%s AND action='save_tax'",(subject,))
            if api('GET','/api/connected/tax/inputs?'+query)['can_save']:
                raise ValueError('Revoked tax editing still advertised')
            api('POST','/api/connected/tax/inputs',tax_correction,status=404,csrf=csrf)
            if api('GET','/api/connected/tax/input?'+query)['input']!=tax_changed:
                raise ValueError('Revoking editing incorrectly removed authorized read access')
            before_objects=set(objects.root.iterdir())
            eicar=b'X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*'
            api('POST','/api/connected/documents',{**payload,'idempotency_key':'rejected','data':base64.b64encode(eicar).decode()},status=400,csrf=csrf)
            if len(api('GET','/api/connected/documents?'+query)['versions'])!=4:raise ValueError('Rejected upload published metadata')
            if set(objects.root.iterdir())!=before_objects:raise ValueError('Rejected upload published object')
            if any(any(marker in item.read_bytes() for marker in (b'Fictional receipt',b'Fictional tax')) for item in before_objects):raise ValueError('Plaintext object discovered')
            browser_checks={'rendered_workflow':'not_run'}
            browser_node=os.environ.get('HA_MFA_BROWSER_NODE')
            if browser_node:
                # Re-enable only the fictional editor grant for this optional
                # live browser extension after the API revocation checks.
                with repository.transaction() as conn:
                    conn.execute('INSERT INTO ha_connected.grants VALUES (%s,%s,%s,%s,%s)',
                        (subject,'orchard','business',2026,'save_tax'))
                # Give the browser its own unused TOTP period.
                time.sleep(31-time.time()%30)
                script=Path(__file__).with_name('verify_mfa_tax_browser.cjs').resolve()
                script_path=subprocess.check_output(['wslpath','-w',str(script)],text=True).strip()
                browser_run=subprocess.run([browser_node,script_path],
                    input=json.dumps({'origin':app_origin,'password':password,'secret':secret,
                        'document':corrected['document_id'],'version':corrected['version_id']}),text=True,
                    capture_output=True,timeout=90)
                if browser_run.returncode:
                    diagnostic=browser_run.stderr.strip()
                    allowed={'password-wait','password-action','username-fill','password-fill','password-submit','browser-password','browser-otp','browser-logout','startup','books-open','book-totals','period-totals','document-download','foreign-scope','tax-handoff','tax-reopen','tax-save','tax-reload'}
                    stage,_,kind=diagnostic.removeprefix('Rendered local MFA tax verification failed at ').partition(' ')
                    raise ValueError('Rendered local MFA tax verification failed at '+(stage if stage in allowed else 'unknown')+' '+(kind if kind in {'timeout','assertion','operation'} or re.fullmatch(r'net::ERR_[A-Z_]{1,80}',kind) else 'unknown'))
                browser_checks=json.loads(browser_run.stdout)
            with repository.transaction() as conn:
                conn.execute('DELETE FROM ha_connected.grants WHERE subject=%s',(subject,))
            api('GET','/api/auth/me')
            if api('GET','/api/connected/cases')!={'cases':[]}:raise ValueError('Revoked cases remain listed')
            api('GET','/api/connected/draft?'+query,status=404)
            api('GET','/api/connected/document?'+query+suffix,status=404)
            api('GET','/api/connected/support/reviews?'+query,status=404)
            api('POST','/api/connected/support/reviews',review,status=404,csrf=csrf)
            api('GET','/api/connected/tax/input?'+query,status=404)
            api('POST','/api/connected/tax/inputs',tax_correction,status=404,csrf=csrf)
            call(callback,expected=404)  # HA pending exchange is single use.
            api('POST','/api/auth/logout',{},csrf=csrf)
            api('GET','/api/auth/me',status=401)
            api('GET','/api/connected/draft?'+query,status=401)
            api('GET','/api/connected/tax/inputs?'+query,status=401)
            return {'rendered_browser_checks':browser_checks,
                'same_real_mfa_session_tax_save_reopen':'passed',
                'tax_original_correction_exact_input_and_metadata':True,'tax_csrf_edit_grant_retry_stale_checks':True,
                'tax_foreign_revocation_and_logout_denials':True,'tax_reopened_connected_estimate_held':True,
                'tax_refund_and_balance_held':True,'tax_preparation_not_authorized':True,
                'real_mfa_https_callback':'passed','same_session_books_tax_documents':'passed','same_real_mfa_session_support_review':'passed',
                'review_csrf_and_explicit_authority_denials':True,'review_retry_history_preserved':True,
                'review_document_correction_reopens_queue':True,'review_foreign_scope_and_revocation_denials':True,
                'postgresql':'isolated real PostgreSQL 16 Unix-socket cluster',
                'scanner':'actual ClamD with project container policy','objects':'AES-GCM encrypted local fixture objects; not Spaces',
                'cross_profile_document_and_books_denial':True,'csrf_upload_denial':True,'original_and_correction_preserved':True,
                'eicar_upload_rejected_without_metadata_or_object':True,'grant_revocation_denies_active_session':True,'callback_replay_rejected':True,'logout_revokes_access':True,
                'book_profit_minor':118000,'refund_withheld_pending_business_review':True,
                'hosted_workflow':'not_run','otp_enrollment':'pre-enrolled fictional fixture; not tested'}
        finally:
            server.shutdown();server.server_close();thread.join(timeout=10)
