"""Restore a fictional development database into a new isolated database.

Requires dev_postgres.py setup and a populated synthetic fixture. Preserves the
source database; never drops a database. This is local evidence, not AWS Backup.
"""
import json
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
from ha.connected.documents import Documents,MemoryObjects

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / '.connected-local'
BIN = LOCAL / 'postgresql/pgsql/bin'


def main():
    config = json.loads((LOCAL/'test-database.json').read_text())
    params = conninfo_to_dict(config['dsn'])
    if (config.get('synthetic_only') is not True or params.get('host')!='127.0.0.1'
            or params.get('port')!='55432' or params.get('user')!='ha_test_admin' or params.get('dbname')!='postgres'):
        raise ValueError('Only the isolated synthetic database may be restored by this script')
    # Ensure the fixture, constraints and persistence tests pass before backup.
    subprocess.run([str(ROOT/'.venv/Scripts/python.exe'),str(ROOT/'scripts/dev_postgres.py'),'test',
                    '--suite','tests.test_connected_postgres'],cwd=ROOT,check=True)
    repository = PostgresRepository(config['dsn'])
    scope = Scope('orchard','business',2026)
    owner = Principal('orchard-owner',datetime.now(timezone.utc)+timedelta(minutes=10),True)
    with repository.transaction() as conn:
        conn.execute('TRUNCATE ha_connected.profiles CASCADE')
        conn.execute("INSERT INTO ha_connected.profiles VALUES ('orchard'),('cedar')")
        conn.execute("INSERT INTO ha_connected.businesses VALUES ('business','orchard'),('cedar-business','cedar')")
        for action in ('read','post','correct','upload','restore'):
            conn.execute('INSERT INTO ha_connected.grants VALUES (%s,%s,%s,%s,%s)',('orchard-owner','orchard','business',2026,action))
    fixture = json.loads((ROOT/'docs/fixtures/day8-connected-workflow.json').read_text())
    ledger = PostgresLedger(repository)
    for event in fixture['events']:
        ledger.post_event(owner,scope,event)
    documents = Documents(repository,MemoryObjects(),lambda data,mime:True)
    original = documents.upload(owner,scope,BytesIO(b'fictional original receipt'),'text/plain','restore-original')
    documents.correct(owner,scope,original.document_id,BytesIO(b'fictional corrected receipt'),'text/plain','restore-corrected','Correction')
    env = dict(os.environ,PGPASSWORD=params['password'])
    args = ['-h','127.0.0.1','-p','55432','-U','ha_test_admin']
    archive = LOCAL/('backup-'+uuid.uuid4().hex+'.dump')
    started = time.perf_counter()
    subprocess.run([str(BIN/'pg_dump.exe'),*args,'-d','postgres','--schema=ha_connected','--format=custom',
                    '--no-owner','--no-acl','--file='+str(archive)],env=env,check=True)
    restored_name = 'ha_restore_'+uuid.uuid4().hex
    with psycopg.connect(config['dsn'],autocommit=True) as conn:
        conn.execute(psycopg.sql.SQL('CREATE DATABASE {}').format(psycopg.sql.Identifier(restored_name)))
    subprocess.run([str(BIN/'pg_restore.exe'),*args,'-d',restored_name,'--no-owner','--no-acl',str(archive)],env=env,check=True)
    recovered_dsn = make_conninfo(**{**params,'dbname':restored_name})
    with psycopg.connect(config['dsn']) as original, psycopg.connect(recovered_dsn) as recovered:
        counts = {}
        for table in ('profiles','businesses','grants','ledger_events','document_versions'):
            query = psycopg.sql.SQL('SELECT * FROM ha_connected.{}').format(psycopg.sql.Identifier(table))
            before = original.execute(query).fetchall()
            after = recovered.execute(query).fetchall()
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
    elapsed = time.perf_counter()-started
    report = {'environment':'local fictional PostgreSQL only','database_restore':'passed','tables':counts,
              'elapsed_seconds':round(elapsed,3),'source_database_preserved':True,
              'recovered_book_profit_minor':118000,'recovered_cross_profile_denial':'passed',
              'aws_backup_restore':'not_run','document_object_restore':'not_run'}
    (ROOT/'docs/DATABASE-RESTORE-EVIDENCE.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
