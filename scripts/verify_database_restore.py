"""Restore a fictional development database into a new isolated database.

Requires dev_postgres.py setup. Creates new source and recovery databases,
leaving existing test data untouched; never drops a database. This is local evidence, not AWS Backup.
"""
import json
import secrets
import hashlib
import shutil
import os
from pathlib import Path
import subprocess
import time
import uuid
from datetime import datetime,timedelta,timezone
from io import BytesIO
import psycopg
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from psycopg.types.json import Jsonb
from ha.connected.postgres import PostgresRepository,PostgresLedger
from ha.connected.domain import Principal,Scope
from ha.connected.documents import Documents
from ha.connected.tax_inputs import TaxInputs
from ha.connected.record_confirmation import RecordConfirmations
from ha.connected.return_draft import estimate_connected_return
from ha.connected.backup_transfer import copy_bundle, recover_bundle
from ha.connected.backup_receipt import write_receipt, publish_receipt, retrieve_receipt
from ha.connected.backup_job import capture_backup
from ha.connected.backup_monitor import check as check_backup_locator, discover as discover_backup_locator
from ha.connected.backup_health import check as check_backup_health
from ha.connected.backup_bundle import create_bundle,inspect_bundle,digest
from ha.connected.backup_inventory import build_inventory,verify_inventory
from ha.connected.backup_archive import encrypt_backup, decrypt_backup
from ha.connected.encrypted_objects import EncryptedLocalObjects
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / '.connected-local'
BIN = LOCAL / 'postgresql/pgsql/bin'

LATEST_CORRECTIONS=(
    dict(id='recovery-cash',date='2026-11-04',kind='correction',replaces='sale-cash',amount_minor=50000,
         reason='Clarify fictional cash sales',support_changes={'explanation':'Fictional recovery cash clarification'}),
    dict(id='recovery-payment',date='2026-11-04',kind='correction',replaces='owner-estimate',amount_minor=12500,
         reason='Correct fictional payment amount'))


def verify_latest_corrections(ledger,owner,scope):
    history={event['id']:event for event in ledger.history(owner,scope)}
    fixture=json.loads((ROOT/'docs/fixtures/day8-connected-workflow.json').read_text(encoding='utf-8'))
    expected={event['id']:event for event in fixture['events']}
    for event_id in ('sale-cash','owner-estimate'):
        if history[event_id]['source']!=expected[event_id]:raise ValueError('Recovered original source changed')
    cash,payment=history['recovery-cash'],history['recovery-payment']
    if (history['sale-cash'].get('explanation')!='Aggregate fictional market sales'
            or cash.get('explanation')!='Fictional recovery cash clarification'
            or cash['amount_minor']!=50000 or cash['posting_date']!='2026-10-02'
            or history['owner-estimate']['amount_minor']!=10000
            or payment['amount_minor']!=12500 or payment['posting_date']!='2026-10-03'
            or payment.get('status')!='recorded_unverified' or payment.get('government_confirmation') is not None):
        raise ValueError('Recovered correction history mismatch')
    for correction in LATEST_CORRECTIONS:
        if history[correction['id']]['source']!=correction:raise ValueError('Recovered correction source changed')
    for period in ('month','quarter','year'):
        projection=ledger.project(owner,scope,period,10)
        if (projection['book_profit_minor']!=118000 or projection['reserve_scenario_minor']!=37500
                or projection['owner_payments_recorded_minor']!=12500 or projection['owner_payments_confirmed_minor']!=0
                or not {'recovery-cash','recovery-payment'}<=set(projection['source_event_ids'])
                or {'sale-cash','owner-estimate'}&set(projection['source_event_ids'])):
            raise ValueError('Recovered correction projection mismatch')
    return {'original_cash_and_payment_preserved':True,'cash_explanation_amendment_preserved':True,
            'recorded_payment_minor':12500,'confirmed_payment_minor':0,'original_periods_and_no_double_count':True}


def main():
    config = json.loads((LOCAL/'test-database.json').read_text())
    params = conninfo_to_dict(config['dsn'])
    if (config.get('synthetic_only') is not True or params.get('host')!='127.0.0.1'
            or params.get('port')!='55432' or params.get('user')!='ha_test_admin' or params.get('dbname')!='postgres'):
        raise ValueError('Only the isolated synthetic database may be restored by this script')
    # Create a separate source fixture; never reset the existing test database.
    source_name='ha_recovery_source_'+uuid.uuid4().hex
    with psycopg.connect(config['dsn'],autocommit=True) as conn:
        conn.execute(psycopg.sql.SQL('CREATE DATABASE {}').format(psycopg.sql.Identifier(source_name)))
    source_dsn=make_conninfo(**{**params,'dbname':source_name})
    repository=PostgresRepository(source_dsn)
    repository.migrate()
    scope = Scope('orchard','business',2026)
    owner = Principal('orchard-owner',datetime.now(timezone.utc)+timedelta(minutes=10),True)
    with repository.transaction() as conn:
        conn.execute("INSERT INTO ha_connected.profiles VALUES ('orchard'),('cedar')")
        conn.execute("INSERT INTO ha_connected.businesses VALUES ('business','orchard'),('cedar-business','cedar')")
        for action in ('read','post','correct','upload','restore','save_tax','confirm_records'):
            conn.execute('INSERT INTO ha_connected.grants VALUES (%s,%s,%s,%s,%s)',('orchard-owner','orchard','business',2026,action))
    fixture = json.loads((ROOT/'docs/fixtures/day8-connected-workflow.json').read_text(encoding='utf-8'))
    ledger = PostgresLedger(repository)
    for event in fixture['events']:
        ledger.post_event(owner,scope,event)
    confirmations=RecordConfirmations(repository)
    original_confirmation=dict(ledger_revision=6,reviewed_through='2026-10-03',confirmed=True,
        reason='Compared fictional card and cash entries',idempotency_key='restore-records-original')
    confirmations.submit(owner,scope,original_confirmation)
    for event in LATEST_CORRECTIONS:ledger.post_event(owner,scope,event)
    if confirmations.view(owner,scope)['status']!='stale':raise ValueError('Correction did not invalidate review')
    confirmations.submit(owner,scope,{**original_confirmation,'ledger_revision':8,
        'reason':'Reviewed the fictional corrected entries','idempotency_key':'restore-records-current'})
    confirmation_before=confirmations.view(owner,scope)
    if (len(confirmation_before['history'])!=2 or confirmation_before['status']!='current'
            or confirmation_before['independently_verified'] is not False):raise ValueError('Confirmation fixture mismatch')
    verify_latest_corrections(ledger,owner,scope)
    run_id=uuid.uuid4().hex
    recovery_root=LOCAL/('recovery-'+run_id)
    key_root=LOCAL/'recovery-keys'
    key_root.mkdir(exist_ok=True)
    key_path=key_root/(run_id+'.key')
    with key_path.open('xb') as handle:
        handle.write(AESGCM.generate_key(bit_length=256))
    source_objects=recovery_root/'source-objects'
    object_backup=recovery_root/'encrypted-backup'
    restored_objects=recovery_root/'restored-objects'
    objects=EncryptedLocalObjects(source_objects,key_path.read_bytes)
    # Synthetic fixture only; this bypass is never configured in the runtime.
    documents = Documents(repository,objects,lambda data,mime:True)
    original = documents.upload(owner,scope,BytesIO(b'fictional original receipt'),'text/plain','restore-original')
    corrected=documents.correct(owner,scope,original.document_id,BytesIO(b'fictional corrected receipt'),'text/plain','restore-corrected','Correction')
    # Fixture decision only: no runtime reviewer approval is implied.
    with repository.transaction() as conn:
        event_id=conn.execute('SELECT event_id FROM ha_connected.ledger_events ORDER BY seq LIMIT 1').fetchone()[0]
        conn.execute("""INSERT INTO ha_connected.support_reviews
            (decision_id,profile_id,business_id,tax_year,event_id,event_fingerprint,document_id,version_id,
             decision,reason,actor,idempotency_key,request_fingerprint)
            VALUES (%s,'orchard','business',2026,%s,%s,%s,%s,'needs_information',
                    'Fictional review fixture','fixture-reviewer','review-fixture',%s)""",
            (uuid.uuid4(),event_id,'a'*64,original.document_id,original.version_id,'b'*64))
    tax_inputs=TaxInputs(repository,documents)
    tax_original_input={'year':'2026','profile':{'firstName':'fictional original','ssn':'000-00-0000'},
                        'forms':[{'layout':'standard','box1':'001.20','box2':'',
                                  'states':[{'state':'LA','tax':''},{'state':'TX'}]}],
                        'active':0,'stateAnswers':{'state-move':'Yes'}}
    tax_original=tax_inputs.save(owner,scope,{'input':tax_original_input,'expected_snapshot_id':None,
                                            'reason':'','idempotency_key':'restore-tax-original'})
    tax_corrected_input=json.loads(json.dumps(tax_original_input))
    tax_corrected_input['profile']['firstName']='fictional corrected'
    tax_corrected_input['forms'][0]['box1']='200.00'
    tax_corrected=tax_inputs.save(owner,scope,{'input':tax_corrected_input,
                                'expected_snapshot_id':tax_original['snapshot_id'],
                                'reason':'Corrected fictional wages','idempotency_key':'restore-tax-corrected'})
    def verify_saved_inputs(restored_documents):
        service=TaxInputs(restored_documents.repository,restored_documents)
        reopened=service.open(owner,scope)
        if reopened['input']!=tax_corrected_input or reopened['snapshot']!=tax_corrected:
            raise ValueError('Recovered current tax input differs')
        prior=service.open(owner,scope,tax_original['snapshot_id'])
        if prior['input']!=tax_original_input or prior['snapshot']!=tax_original:
            raise ValueError('Recovered original tax input differs')
        if len(service.history(owner,scope))!=2:
            raise ValueError('Recovered tax input history differs')
        try:service.open(owner,Scope('cedar','cedar-business',2026))
        except PermissionError:pass
        else:raise ValueError('Recovered tax input exposed another profile')
        forms=reopened['input']['forms']
        scenario={'tax_year':'2026','filing_status':'single',
                  'w2s':[{'box1':f.get('box1',''),'box2':f.get('box2','')} for f in forms],
                  'retirement_forms':[]}
        estimate=estimate_connected_return(PostgresLedger(restored_documents.repository),owner,scope,scenario)
        if (estimate['business_draft']['book_profit_minor']!=118000
                or estimate['refund'] is not None or estimate['balance_due'] is not None
                or estimate['may_prepare_return'] is not False or estimate['wages']!=200):
            raise ValueError('Reopened connected tax draft disagrees')
    shutil.copytree(source_objects,object_backup)
    env = dict(os.environ,PGPASSWORD=params['password'])
    args = ['-h','127.0.0.1','-p','55432','-U','ha_test_admin']
    archive = LOCAL/('backup-'+uuid.uuid4().hex+'.dump')
    started = time.perf_counter()
    with psycopg.connect(source_dsn) as snapshot_db:
        snapshot_db.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        snapshot=snapshot_db.execute('SELECT pg_export_snapshot()').fetchone()[0]
        snapshot_rows={}
        for table in ('profiles','businesses','grants','ledger_events','document_versions','support_reviews','tax_input_versions','record_confirmations'):
            query=psycopg.sql.SQL('SELECT * FROM ha_connected.{}').format(psycopg.sql.Identifier(table))
            snapshot_rows[table]=snapshot_db.execute(query).fetchall()
        versions=[repository._version(row) for row in snapshot_rows['document_versions']]
        # A separate committed upload after the exported snapshot must not enter this backup.
        documents.upload(owner,scope,BytesIO(b'fictional post-snapshot receipt'),'text/plain','after-snapshot')
        subprocess.run([str(BIN/'pg_dump.exe'),*args,'-d',source_name,'--schema=ha_connected','--format=custom',
                        '--snapshot='+snapshot,'--no-owner','--no-acl','--file='+str(archive)],env=env,check=True)

    backup_key_path=key_root/(run_id+'-database.key')
    with backup_key_path.open('xb') as handle:
        handle.write(AESGCM.generate_key(bit_length=256))
    encrypted_archive=recovery_root/'database.habackup'
    decrypt_archive=recovery_root/'restore.dump'
    encrypt_backup(archive,encrypted_archive,backup_key_path.read_bytes())
    archive_hash=hashlib.sha256(encrypted_archive.read_bytes()).hexdigest()
    inventory=build_inventory(run_id,versions,EncryptedLocalObjects(object_backup,key_path.read_bytes),archive_hash)
    inventory_plain=recovery_root/'inventory.json'
    inventory_plain.write_text(json.dumps(inventory,sort_keys=True),encoding='utf-8')
    inventory_encrypted=recovery_root/'inventory.habackup'
    encrypt_backup(inventory_plain,inventory_encrypted,backup_key_path.read_bytes())
    recovered_inventory=recovery_root/'recovered-inventory.json'
    decrypt_backup(inventory_encrypted,recovered_inventory,backup_key_path.read_bytes())
    inventory=json.loads(recovered_inventory.read_text(encoding='utf-8'))
    if inventory['database_archive_sha256']!=hashlib.sha256(encrypted_archive.read_bytes()).hexdigest():
        raise ValueError('Database archive does not match encrypted inventory')
    decrypt_backup(encrypted_archive,decrypt_archive,backup_key_path.read_bytes())
    if decrypt_archive.read_bytes()!=archive.read_bytes():
        raise ValueError('Authenticated database backup differs')
    restored_name = 'ha_restore_' +uuid.uuid4().hex
    with psycopg.connect(config['dsn'],autocommit=True) as conn:
        conn.execute(psycopg.sql.SQL('CREATE DATABASE {}').format(psycopg.sql.Identifier(restored_name)))
    subprocess.run([str(BIN/'pg_restore.exe'),*args,'-d',restored_name,'--no-owner','--no-acl',str(decrypt_archive)],env=env,check=True)
    recovered_dsn = make_conninfo(**{**params,'dbname':restored_name})
    with psycopg.connect(source_dsn) as original_db, psycopg.connect(recovered_dsn) as recovered_db:
        counts = {}
        for table in ('profiles','businesses','grants','ledger_events','document_versions','support_reviews','tax_input_versions','record_confirmations'):
            query = psycopg.sql.SQL('SELECT * FROM ha_connected.{}').format(psycopg.sql.Identifier(table))
            before = snapshot_rows[table]
            after = recovered_db.execute(query).fetchall()
            if sorted(before, key=repr) != sorted(after, key=repr):
                raise ValueError('Recovered table differs: '+table)
            counts[table] = len(after)
    with psycopg.connect(source_dsn) as conn:
        source_version_count=conn.execute('SELECT count(*) FROM ha_connected.document_versions').fetchone()[0]
    if source_version_count!=5 or counts['document_versions']!=4:
        raise ValueError('Exported snapshot included a later committed upload')
    recovered_ledger = PostgresLedger(PostgresRepository(recovered_dsn))
    latest_correction_checks=verify_latest_corrections(recovered_ledger,owner,scope)
    if RecordConfirmations(PostgresRepository(recovered_dsn)).view(owner,scope)!=confirmation_before:
        raise ValueError('Recovered confirmation history or authority changed')
    if recovered_ledger.project(owner,scope,'year')['book_profit_minor'] != 118000:
        raise ValueError('Recovered draft disagrees with fixture')
    try:
        recovered_ledger.project(owner,Scope('cedar','cedar-business',2026),'year')
    except PermissionError:
        pass
    else:
        raise ValueError('Recovered permissions exposed another profile')
    shutil.copytree(object_backup,restored_objects)
    recovered_documents=Documents(PostgresRepository(recovered_dsn),
                                 EncryptedLocalObjects(restored_objects,key_path.read_bytes),
                                 lambda data,mime:False)
    for version,expected in ((original,b'fictional original receipt'),
                             (corrected,b'fictional corrected receipt')):
        actual=recovered_documents.read(owner,scope,version.document_id,version.version_id)
        if actual!=expected:raise ValueError('Recovered document bytes disagree')
    verify_saved_inputs(recovered_documents)
    try:
        recovered_documents.read(owner,Scope('cedar','cedar-business',2026),
                                 original.document_id,original.version_id)
    except PermissionError:
        pass
    else:
        raise ValueError('Recovered documents exposed another profile')
    for encrypted_file in object_backup.glob('*.haobj'):
        if b'fictional' in encrypted_file.read_bytes():
            raise ValueError('Document backup contains plaintext fixture')
    try:
        EncryptedLocalObjects(restored_objects,lambda:bytes(32)).get(original.object_key,original.storage_version)
    except ValueError:
        pass
    else:
        raise ValueError('Restored object accepted wrong encryption key')
    wrong_key_repo=PostgresRepository(recovered_dsn)
    wrong_key_docs=Documents(wrong_key_repo,EncryptedLocalObjects(restored_objects,lambda:bytes(32)),
                            lambda data,mime:False)
    try:TaxInputs(wrong_key_repo,wrong_key_docs).open(owner,scope)
    except ValueError:pass
    else:raise ValueError('Restored tax input accepted wrong encryption key')
    with psycopg.connect(recovered_dsn) as conn:
        restored_versions=[repository._version(row) for row in conn.execute('SELECT * FROM ha_connected.document_versions').fetchall()]
    verify_inventory(inventory,restored_versions,EncryptedLocalObjects(restored_objects,key_path.read_bytes),archive_hash)
    bundle=recovery_root/'complete-bundle'
    create_bundle(run_id,archive,versions,objects,backup_key_path.read_bytes(),bundle)
    bundle_metadata,bundle_objects=inspect_bundle(bundle,backup_key_path.read_bytes(),restored_versions)
    bundle_dump=recovery_root/'bundle-restore.dump'
    decrypt_backup(bundle/'database.habackup',bundle_dump,backup_key_path.read_bytes())
    if digest(bundle_dump)!=digest(archive):raise ValueError('Bundled database dump differs')
    bundled_documents=Documents(PostgresRepository(recovered_dsn),bundle_objects,lambda data,mime:False)
    for version,expected in ((original,b'fictional original receipt'),(corrected,b'fictional corrected receipt')):
        if bundled_documents.read(owner,scope,version.document_id,version.version_id)!=expected:
            raise ValueError('Bundled object recovery differs')
    verify_saved_inputs(bundled_documents)
    # SDK-shaped local ciphertext store: exercises transfer plumbing, not a provider.
    class FictionalStore:
        def __init__(self, root):
            self.root = root; root.mkdir(mode=0o700);self.keys=set()
        def path(self, bucket, name):
            return self.root / hashlib.sha256((bucket+'|'+name).encode()).hexdigest()
        def upload_fileobj(self, reader, bucket, name, ExtraArgs):
            if ExtraArgs.get('ACL') != 'private':raise ValueError('Private copy required')
            with self.path(bucket,name).open('xb') as writer:shutil.copyfileobj(reader,writer)
            self.keys.add((bucket,name))
        def put_object(self, Bucket, Key, Body, ACL, ContentType):
            if ACL != 'private':raise ValueError('Private locator required')
            self.path(Bucket,Key).write_bytes(Body);self.keys.add((Bucket,Key))
        def get_object(self, Bucket, Key):
            from botocore.exceptions import ClientError
            if (Bucket,Key) not in self.keys:raise ClientError({'Error':{'Code':'NoSuchKey'}},'GetObject')
            return {'Body':self.path(Bucket,Key).open('rb')}
        def list_objects_v2(self, Bucket, Prefix, Delimiter, MaxKeys, ContinuationToken=None):
            if Prefix!='ha-recovery/' or Delimiter!='/':raise ValueError('Bounded fixture listing required')
            prefixes=sorted({name.rsplit('/',1)[0]+'/' for bucket,name in self.keys if bucket==Bucket and name.startswith(Prefix)})
            index=int(ContinuationToken or '0');more=index+1<len(prefixes)
            return {'IsTruncated':more,'NextContinuationToken':str(index+1),
                    'CommonPrefixes':[{'Prefix':p} for p in prefixes[index:index+1]]}
    transfer_store=FictionalStore(recovery_root/'fictional-offhost-store')
    copied=copy_bundle(bundle,backup_key_path.read_bytes(),versions,transfer_store,'fictional-backups')
    downloaded=recovery_root/'downloaded-bundle'
    recover_bundle(transfer_store,'fictional-backups',copied['prefix'],backup_key_path.read_bytes(),
                   versions,downloaded,(bundle/'database.habackup').stat().st_size)
    downloaded_dump=recovery_root/'downloaded-restore.dump'
    decrypt_backup(downloaded/'database.habackup',downloaded_dump,backup_key_path.read_bytes())
    transfer_database='ha_transfer_restore_'+uuid.uuid4().hex
    with psycopg.connect(config['dsn'],autocommit=True) as conn:
        conn.execute(psycopg.sql.SQL('CREATE DATABASE {}').format(psycopg.sql.Identifier(transfer_database)))
    subprocess.run([str(BIN/'pg_restore.exe'),*args,'-d',transfer_database,'--no-owner','--no-acl',
                    str(downloaded_dump)],env=env,check=True)
    transfer_dsn=make_conninfo(**{**params,'dbname':transfer_database})
    with psycopg.connect(transfer_dsn) as conn:
        for table,before in snapshot_rows.items():
            after=conn.execute(psycopg.sql.SQL('SELECT * FROM ha_connected.{}').format(
                psycopg.sql.Identifier(table))).fetchall()
            if sorted(before,key=repr)!=sorted(after,key=repr):raise ValueError('Transferred table differs')
        transfer_versions=[repository._version(row) for row in conn.execute(
            'SELECT * FROM ha_connected.document_versions').fetchall()]
    _,transfer_objects=inspect_bundle(downloaded,backup_key_path.read_bytes(),transfer_versions)
    transfer_repo=PostgresRepository(transfer_dsn)
    if verify_latest_corrections(PostgresLedger(transfer_repo),owner,scope)!=latest_correction_checks:
        raise ValueError('Transferred correction verification differs')
    if RecordConfirmations(transfer_repo).view(owner,scope)!=confirmation_before:
        raise ValueError('Transferred confirmation history or authority changed')
    if PostgresLedger(transfer_repo).project(owner,scope,'year')['book_profit_minor']!=118000:
        raise ValueError('Transferred books differ')
    recovered_support=recovered_ledger.project(owner,scope,'year')
    transferred_support=PostgresLedger(transfer_repo).project(owner,scope,'year')
    if not recovered_support['support_review_queue'] or recovered_support['support_review_queue']!=transferred_support['support_review_queue']:
        raise ValueError('Transferred support review state differs')
    transfer_documents=Documents(transfer_repo,transfer_objects,lambda data,mime:False)
    for version,expected in ((original,b'fictional original receipt'),(corrected,b'fictional corrected receipt')):
        if transfer_documents.read(owner,scope,version.document_id,version.version_id)!=expected:
            raise ValueError('Transferred document differs')
    verify_saved_inputs(transfer_documents)
    try:
        transfer_documents.read(owner,Scope('cedar','cedar-business',2026),original.document_id,original.version_id)
    except PermissionError:pass
    else:raise ValueError('Transferred documents exposed another profile')
    job_bundle=recovery_root/'job-bundle'
    role='ha_backup_'+uuid.uuid4().hex
    role_password=secrets.token_urlsafe(32)
    with psycopg.connect(config['dsn'],autocommit=True) as conn:
        conn.execute(psycopg.sql.SQL('CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD {}').format(
            psycopg.sql.Identifier(role),psycopg.sql.Literal(role_password)))
    try:
        with psycopg.connect(source_dsn,autocommit=True) as conn:
            conn.execute(psycopg.sql.SQL('GRANT CONNECT ON DATABASE {} TO {}').format(psycopg.sql.Identifier(source_name),psycopg.sql.Identifier(role)))
            conn.execute(psycopg.sql.SQL('GRANT USAGE ON SCHEMA ha_connected TO {}').format(psycopg.sql.Identifier(role)))
            conn.execute(psycopg.sql.SQL('GRANT SELECT ON ALL TABLES IN SCHEMA ha_connected TO {}').format(psycopg.sql.Identifier(role)))
            conn.execute(psycopg.sql.SQL('GRANT SELECT ON ALL SEQUENCES IN SCHEMA ha_connected TO {}').format(psycopg.sql.Identifier(role)))
        reader_dsn=make_conninfo(**{**params,'dbname':source_name,'user':role,'password':role_password})
        denials=[]
        with psycopg.connect(reader_dsn,autocommit=True) as conn:
            # Test real ACLs rather than relying on a read-only transaction setting.
            conn.execute('SET default_transaction_read_only=off')
            for label,command in (
                ('insert',"INSERT INTO ha_connected.profiles VALUES ('backup-write-denied')"),
                ('update','UPDATE ha_connected.ledger_events SET record=record WHERE false'),
                ('delete','DELETE FROM ha_connected.document_versions WHERE false'),
                ('create_table','CREATE TABLE ha_connected.backup_write_probe(id integer)')):
                try:conn.execute(command)
                except psycopg.errors.InsufficientPrivilege:denials.append(label)
                else:raise ValueError('Backup reader unexpectedly permitted '+label)
        job=capture_backup(reader_dsn,objects,backup_key_path.read_bytes(),job_bundle,(BIN/'pg_dump.exe').resolve(),
                           offhost=(transfer_store,'fictional-job-backups'))
    finally:
        with psycopg.connect(source_dsn,autocommit=True) as conn:
            conn.execute(psycopg.sql.SQL('DROP OWNED BY {}').format(psycopg.sql.Identifier(role)))
        with psycopg.connect(config['dsn'],autocommit=True) as conn:
            conn.execute(psycopg.sql.SQL('DROP ROLE {}').format(psycopg.sql.Identifier(role)))
    with psycopg.connect(source_dsn) as conn:
        current_versions=[repository._version(row) for row in conn.execute('SELECT * FROM ha_connected.document_versions').fetchall()]
    inspect_bundle(job_bundle,backup_key_path.read_bytes(),current_versions)
    if not job['completed'] or job['document_versions']!=5 or not job['offhost']['completed']:raise ValueError('Backup job did not capture current versions')
    health_start=datetime.now(timezone.utc)
    receipt=write_receipt(job,run_id+'-database','nyc3','fictional-job-backups',recovery_root/'job.receipt.json')
    remote_receipt=publish_receipt(receipt,transfer_store)
    retrieved_receipt=retrieve_receipt(transfer_store,'fictional-job-backups',job['offhost']['prefix'],'nyc3')
    if retrieved_receipt != receipt:raise ValueError('Retrieved locator differs')
    if not remote_receipt['verified']:raise ValueError('Offhost locator failed')
    if receipt['recovery_verified'] or not receipt['copy_verified']:raise ValueError('Receipt overstates evidence')
    monitoring_now=datetime.fromisoformat(receipt['completed_at'])
    health_end=datetime.now(timezone.utc)
    attempt_id=uuid.uuid4().hex
    common={'format':'ha-backup-attempt-v1','attempt_id':attempt_id,'recovery_verified':False,'deletion_authorized':False}
    observed_events=[{**common,'status':'started','observed_at':health_start.isoformat()},
        {**common,'status':'completed','observed_at':health_end.isoformat(),'prefix':receipt['prefix'],
         'document_versions':receipt['document_versions'],'recovery_key_id':receipt['recovery_key_id'],
         'copy_verified':True,'locator_verified':True}]
    combined_health=check_backup_health(observed_events,transfer_store,'fictional-job-backups','nyc3',now=health_end)
    if combined_health['status']!='current_observed_attempt' or combined_health['recovery_verified']:
        raise ValueError('Combined observed attempt and receipt mismatch')
    older_receipt={**receipt,'prefix':'ha-recovery/'+uuid.uuid4().hex+'/',
                   'completed_at':(monitoring_now-timedelta(days=2)).isoformat()}
    publish_receipt(older_receipt,transfer_store)
    transfer_store.upload_fileobj(BytesIO(b'fictional incomplete encrypted upload'),
        'fictional-job-backups','ha-recovery/'+uuid.uuid4().hex+'/database.habackup',{'ACL':'private'})
    discovered=discover_backup_locator(transfer_store,'fictional-job-backups','nyc3',now=monitoring_now)
    if (discovered['prefix']!=receipt['prefix'] or discovered['listed_prefixes']!=3
            or discovered['receipts_observed']!=2 or discovered['recovery_verified']):
        raise ValueError('Backup receipt discovery mismatch')
    current_health=check_backup_locator(transfer_store,'fictional-job-backups',job['offhost']['prefix'],'nyc3',now=monitoring_now)
    stale_health=check_backup_locator(transfer_store,'fictional-job-backups',job['offhost']['prefix'],'nyc3',now=monitoring_now+timedelta(hours=37))
    if current_health['status']!='current_locator' or stale_health['status']!='stale_locator':
        raise ValueError('Backup locator freshness mismatch')
    if any(result['recovery_verified'] or result['archive_integrity_verified'] or result['deletion_authorized'] for result in (current_health,stale_health)):
        raise ValueError('Backup monitor overstates authority')
    elapsed = time.perf_counter()-started
    report = {'records_confirmation_restore_checks':{'original_and_current_history_preserved':True,'current_revision':8,'independently_verified':False,'filing_authorized':False},'latest_correction_restore_checks':latest_correction_checks,'environment':'local fictional PostgreSQL only','database_restore':'passed','database_backup_encryption':'passed_authenticated_stream', 'database_recovery_key':'separate ignored recovery-key file; excluded from archive','tables':counts,
              'elapsed_seconds':round(elapsed,3),'source_database_preserved':True,'fixture_source':'new isolated database; existing test data untouched',
              'recovered_book_profit_minor':118000,'recovered_cross_profile_denial':'passed',
              'aws_backup_restore':'not_run','document_object_restore':'passed_local_encrypted_files',
              'document_versions_recovered':4,'document_cross_profile_denial':'passed',
              'wrong_key_denial':'passed','encrypted_backup_plaintext_check':'passed',
              'key_storage':'separate ignored local recovery-key directory; not copied with object backup',
              'consistent_exported_snapshot':'passed', 'post_snapshot_upload_excluded':True, 'source_document_versions_after_snapshot':source_version_count, 'encrypted_version_inventory_restore':'passed', 'database_archive_inventory_binding':'passed',
              'completed_bundle_inspection':'passed','bundled_document_recovery':'passed','bundle_database_dump_matches_restore':'passed',
              'consistent_backup_job':'passed','backup_job_verified_remote_copy':'passed_local_fictional_store','combined_backup_health':'passed_observed_fixture_journal_matching_actual_backup_receipt','backup_locator_discovery':'passed_paginated_newest_observed_and_incomplete_prefix_fictional_store','backup_locator_monitor':'passed_current_stale_without_recovery_or_deletion_claim_fictional_store','durable_backup_receipt':'passed_local_fixture','offhost_backup_locator':'passed_private_copy_readback_and_retrieval_fictional_store','backup_job_current_document_versions':job['document_versions'],
              'read_only_backup_role_capture':'passed','backup_role_write_denials':denials,'temporary_backup_role_removed':True,
              'transferred_bundle_database_restore':'passed_actual_pg_restore',
              'transfer_store':'local SDK-shaped fictional adapter; not DigitalOcean',
              'transferred_support_review_queue_matches':True,'transferred_tables_match_snapshot':True,'tax_input_reference_restore':'passed_actual_saved_original_and_correction',
              'saved_tax_input_restore':'passed_current_and_original_exact_input_and_metadata',
              'saved_tax_input_cross_profile_denial':'passed','saved_tax_input_wrong_key_denial':'passed',
              'reopened_connected_draft':'passed_wages200_book_profit118000_combined_balance_held','transferred_original_and_correction':'passed',
              'transferred_book_profit_minor':118000,'transferred_cross_profile_denial':'passed',
              'hosted_storage_restore':'not_run','scanner':'synthetic fixture bypass only'}
    (ROOT/'docs/DATABASE-RESTORE-EVIDENCE.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
