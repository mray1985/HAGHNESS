"""Restore a fictional development database into a new isolated database.

Requires dev_postgres.py setup. Creates new source and recovery databases,
leaving existing test data untouched; never drops a database. This is local evidence, not AWS Backup.
"""
import json
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
    shutil.copytree(source_objects,object_backup)
    env = dict(os.environ,PGPASSWORD=params['password'])
    args = ['-h','127.0.0.1','-p','55432','-U','ha_test_admin']
    archive = LOCAL/('backup-'+uuid.uuid4().hex+'.dump')
    started = time.perf_counter()
    subprocess.run([str(BIN/'pg_dump.exe'),*args,'-d',source_name,'--schema=ha_connected','--format=custom',
                    '--no-owner','--no-acl','--file='+str(archive)],env=env,check=True)
    restored_name = 'ha_restore_'+uuid.uuid4().hex
    with psycopg.connect(config['dsn'],autocommit=True) as conn:
        conn.execute(psycopg.sql.SQL('CREATE DATABASE {}').format(psycopg.sql.Identifier(restored_name)))
    subprocess.run([str(BIN/'pg_restore.exe'),*args,'-d',restored_name,'--no-owner','--no-acl',str(archive)],env=env,check=True)
    recovered_dsn = make_conninfo(**{**params,'dbname':restored_name})
    with psycopg.connect(source_dsn) as original_db, psycopg.connect(recovered_dsn) as recovered_db:
        counts = {}
        for table in ('profiles','businesses','grants','ledger_events','document_versions'):
            query = psycopg.sql.SQL('SELECT * FROM ha_connected.{}').format(psycopg.sql.Identifier(table))
            before = original_db.execute(query).fetchall()
            after = recovered_db.execute(query).fetchall()
            if sorted(before, key=repr) != sorted(after, key=repr):
                raise ValueError('Recovered table differs: '+table)
            counts[table] = len(after)
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
    elapsed = time.perf_counter()-started
    report = {'environment':'local fictional PostgreSQL only','database_restore':'passed','tables':counts,
              'elapsed_seconds':round(elapsed,3),'source_database_preserved':True,'fixture_source':'new isolated database; existing test data untouched',
              'recovered_book_profit_minor':118000,'recovered_cross_profile_denial':'passed',
              'aws_backup_restore':'not_run','document_object_restore':'passed_local_encrypted_files',
              'document_versions_recovered':2,'document_cross_profile_denial':'passed',
              'wrong_key_denial':'passed','encrypted_backup_plaintext_check':'passed',
              'key_storage':'separate ignored local recovery-key directory; not copied with object backup',
              'hosted_storage_restore':'not_run','scanner':'synthetic fixture bypass only'}
    (ROOT/'docs/DATABASE-RESTORE-EVIDENCE.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
