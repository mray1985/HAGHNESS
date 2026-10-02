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
from ha.connected.backup_transfer import copy_bundle, recover_bundle
from ha.connected.backup_receipt import write_receipt, publish_receipt, retrieve_receipt
from ha.connected.backup_job import capture_backup
from ha.connected.backup_bundle import create_bundle,inspect_bundle,digest
from ha.connected.backup_inventory import build_inventory,verify_inventory
from ha.connected.backup_archive import encrypt_backup, decrypt_backup
from ha.connected.encrypted_objects import EncryptedLocalObjects
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / '.connected-local'
BIN = LOCAL / 'postgresql/pgsql/bin'


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
        for action in ('read','post','correct','upload','restore'):
            conn.execute('INSERT INTO ha_connected.grants VALUES (%s,%s,%s,%s,%s)',('orchard-owner','orchard','business',2026,action))
    fixture = json.loads((ROOT/'docs/fixtures/day8-connected-workflow.json').read_text())
    ledger = PostgresLedger(repository)
    for event in fixture['events']:
        ledger.post_event(owner,scope,event)
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
    # Reference-table fixture only; bytes are a receipt, not a saved tax input.
    with repository.transaction() as conn:
        conn.execute("""INSERT INTO ha_connected.tax_input_versions
            (snapshot_id,profile_id,business_id,tax_year,document_id,version_id,
             actor,reason,idempotency_key,request_fingerprint)
            VALUES (%s,'orchard','business',2026,%s,%s,'fixture-owner','',%s,%s)""",
            (uuid.uuid4(),original.document_id,original.version_id,'tax-reference-fixture','c'*64))
    shutil.copytree(source_objects,object_backup)
    env = dict(os.environ,PGPASSWORD=params['password'])
    args = ['-h','127.0.0.1','-p','55432','-U','ha_test_admin']
    archive = LOCAL/('backup-'+uuid.uuid4().hex+'.dump')
    started = time.perf_counter()
    with psycopg.connect(source_dsn) as snapshot_db:
        snapshot_db.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        snapshot=snapshot_db.execute('SELECT pg_export_snapshot()').fetchone()[0]
        snapshot_rows={}
        for table in ('profiles','businesses','grants','ledger_events','document_versions','support_reviews','tax_input_versions'):
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
        for table in ('profiles','businesses','grants','ledger_events','document_versions','support_reviews','tax_input_versions'):
            query = psycopg.sql.SQL('SELECT * FROM ha_connected.{}').format(psycopg.sql.Identifier(table))
            before = snapshot_rows[table]
            after = recovered_db.execute(query).fetchall()
            if sorted(before, key=repr) != sorted(after, key=repr):
                raise ValueError('Recovered table differs: '+table)
            counts[table] = len(after)
    with psycopg.connect(source_dsn) as conn:
        source_version_count=conn.execute('SELECT count(*) FROM ha_connected.document_versions').fetchone()[0]
    if source_version_count!=3 or counts['document_versions']!=2:
        raise ValueError('Exported snapshot included a later committed upload')
    recovered_ledger = PostgresLedger(PostgresRepository(recovered_dsn))
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
    # SDK-shaped local ciphertext store: exercises transfer plumbing, not a provider.
    class FictionalStore:
        def __init__(self, root):
            self.root = root; root.mkdir(mode=0o700)
        def path(self, bucket, name):
            return self.root / hashlib.sha256((bucket+'|'+name).encode()).hexdigest()
        def upload_fileobj(self, reader, bucket, name, ExtraArgs):
            if ExtraArgs.get('ACL') != 'private':raise ValueError('Private copy required')
            with self.path(bucket,name).open('xb') as writer:shutil.copyfileobj(reader,writer)
        def put_object(self, Bucket, Key, Body, ACL, ContentType):
            if ACL != 'private':raise ValueError('Private locator required')
            self.path(Bucket,Key).write_bytes(Body)
        def get_object(self, Bucket, Key):
            return {'Body':self.path(Bucket,Key).open('rb')}
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
    if not job['completed'] or job['document_versions']!=3 or not job['offhost']['completed']:raise ValueError('Backup job did not capture current versions')
    receipt=write_receipt(job,run_id+'-database','nyc3','fictional-job-backups',recovery_root/'job.receipt.json')
    remote_receipt=publish_receipt(receipt,transfer_store)
    retrieved_receipt=retrieve_receipt(transfer_store,'fictional-job-backups',job['offhost']['prefix'],'nyc3')
    if retrieved_receipt != receipt:raise ValueError('Retrieved locator differs')
    if not remote_receipt['verified']:raise ValueError('Offhost locator failed')
    if receipt['recovery_verified'] or not receipt['copy_verified']:raise ValueError('Receipt overstates evidence')
    elapsed = time.perf_counter()-started
    report = {'environment':'local fictional PostgreSQL only','database_restore':'passed','database_backup_encryption':'passed_authenticated_stream', 'database_recovery_key':'separate ignored recovery-key file; excluded from archive','tables':counts,
              'elapsed_seconds':round(elapsed,3),'source_database_preserved':True,'fixture_source':'new isolated database; existing test data untouched',
              'recovered_book_profit_minor':118000,'recovered_cross_profile_denial':'passed',
              'aws_backup_restore':'not_run','document_object_restore':'passed_local_encrypted_files',
              'document_versions_recovered':2,'document_cross_profile_denial':'passed',
              'wrong_key_denial':'passed','encrypted_backup_plaintext_check':'passed',
              'key_storage':'separate ignored local recovery-key directory; not copied with object backup',
              'consistent_exported_snapshot':'passed', 'post_snapshot_upload_excluded':True, 'source_document_versions_after_snapshot':source_version_count, 'encrypted_version_inventory_restore':'passed', 'database_archive_inventory_binding':'passed',
              'completed_bundle_inspection':'passed','bundled_document_recovery':'passed','bundle_database_dump_matches_restore':'passed',
              'consistent_backup_job':'passed','backup_job_verified_remote_copy':'passed_local_fictional_store','durable_backup_receipt':'passed_local_fixture','offhost_backup_locator':'passed_private_copy_readback_and_retrieval_fictional_store','backup_job_current_document_versions':job['document_versions'],
              'read_only_backup_role_capture':'passed','backup_role_write_denials':denials,'temporary_backup_role_removed':True,
              'transferred_bundle_database_restore':'passed_actual_pg_restore',
              'transfer_store':'local SDK-shaped fictional adapter; not DigitalOcean',
              'transferred_support_review_queue_matches':True,'transferred_tables_match_snapshot':True,'tax_input_reference_restore':'passed_metadata_fixture_only_not_saved_input','transferred_original_and_correction':'passed',
              'transferred_book_profit_minor':118000,'transferred_cross_profile_denial':'passed',
              'hosted_storage_restore':'not_run','scanner':'synthetic fixture bypass only'}
    (ROOT/'docs/DATABASE-RESTORE-EVIDENCE.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
