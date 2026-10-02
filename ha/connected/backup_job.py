"""Operator-only consistent PostgreSQL capture into a completed encrypted bundle.

Requires a backup database role and exact immutable object reader. No web route,
provider provisioning, deletion or scheduler is enabled by this module.
"""
import os
from pathlib import Path
import subprocess
import tempfile
import uuid
import psycopg
from psycopg.conninfo import conninfo_to_dict,make_conninfo
from .backup_bundle import create_bundle
from .postgres import PostgresRepository

def capture_backup(dsn,objects,backup_key,destination,pg_dump):
    if not isinstance(backup_key,bytes) or len(backup_key)!=32:
        raise ValueError('Separate recovery key required')
    executable=Path(pg_dump)
    if not executable.is_absolute() or not executable.is_file():
        raise ValueError('Explicit installed pg_dump executable required')
    destination=Path(destination)
    if destination.exists():raise FileExistsError('Backup destination already exists')
    params=conninfo_to_dict(dsn)
    if not all(params.get(name) for name in ('host','dbname','user')) or params.get('sslpassword'):
        raise ValueError('Explicit database host/name/user required; inline TLS-key passwords unsupported')
    password=params.pop('password',None)
    env=dict(os.environ)
    # The caller's connection settings control the job, not inherited PG defaults.
    for name in tuple(env):
        if name.startswith('PG'):env.pop(name)
    if password is not None:env['PGPASSWORD']=password
    public_connection=make_conninfo(**params)
    with tempfile.TemporaryDirectory(prefix='.ha-capture-',dir=destination.parent) as staging:
        dump=Path(staging)/'database.dump'
        with psycopg.connect(dsn,connect_timeout=10) as conn:
            conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            snapshot=conn.execute('SELECT pg_export_snapshot()').fetchone()[0]
            versions=[PostgresRepository._version(row) for row in
                conn.execute('SELECT * FROM ha_connected.document_versions').fetchall()]
            result=subprocess.run([str(executable),'--dbname='+public_connection,'--schema=ha_connected',
                '--format=custom','--snapshot='+snapshot,'--no-owner','--no-acl','--file='+str(dump)],
                env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=3600)
            if result.returncode:raise RuntimeError('Database backup capture failed')
        # Source objects must remain immutable/available after the pinned DB snapshot.
        manifest=create_bundle(uuid.uuid4().hex,dump,versions,objects,backup_key,destination)
        return {'snapshot_id':manifest['inventory']['snapshot_id'],
            'document_versions':len(versions),'completed':True,'deletion_authorized':False}
