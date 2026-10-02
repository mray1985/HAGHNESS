"""Isolated synthetic PostgreSQL tests; never installs a Windows service.

Run with the project's .venv Python. Official EDB archive must already exist in
.connected-local/postgresql.zip. Credentials/data stay in that ignored folder.
"""
import argparse
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import zipfile
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / '.connected-local'
BIN = LOCAL / 'postgresql' / 'pgsql' / 'bin'
DATA = LOCAL / 'pgdata'
CONFIG = LOCAL / 'test-database.json'


def extract():
    destination = (LOCAL / 'postgresql').resolve()
    with zipfile.ZipFile(LOCAL / 'postgresql.zip') as archive:
        for entry in archive.infolist():
            if not entry.filename.startswith(('pgsql/bin/','pgsql/lib/','pgsql/share/')):
                continue
            target = (destination / entry.filename).resolve()
            target.relative_to(destination)
            if '..' in Path(entry.filename).parts:
                raise ValueError('Unsafe archive path')
            archive.extract(entry,destination)


def run(*args, check=True):
    return subprocess.run(args,cwd=ROOT,check=check)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action',choices=['start','test','stop'])
    parser.add_argument('--suite',default='')
    args = parser.parse_args()
    LOCAL.mkdir(exist_ok=True)
    if args.action == 'start':
        if not BIN.is_dir():
            extract()
        if not CONFIG.exists():
            if DATA.exists():
                raise RuntimeError('Existing data without config: manual review required')
            password = secrets.token_urlsafe(32)
            pwfile = LOCAL / 'init-password.txt'
            pwfile.write_text(password)
            try:
                run(str(BIN/'initdb.exe'),'-D',str(DATA),'-U','ha_test_admin','--auth=scram-sha-256',
                    '--encoding=UTF8','--locale=C','--pwfile='+str(pwfile))
            finally:
                pwfile.unlink(missing_ok=True)
            dsn = 'postgresql://ha_test_admin:'+quote(password,safe='')+'@127.0.0.1:55432/postgres'
            CONFIG.write_text(json.dumps({'dsn':dsn,'synthetic_only':True}))
        status = subprocess.run([str(BIN/'pg_ctl.exe'),'-D',str(DATA),'status'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        if status.returncode != 0:
            run(str(BIN/'pg_ctl.exe'),'-D',str(DATA),'-l',str(LOCAL/'postgres.log'),'-o','-h 127.0.0.1 -p 55432','start','-w')
        print('Synthetic PostgreSQL available on loopback port 55432.')
    elif args.action == 'test':
        config = json.loads(CONFIG.read_text())
        if config.get('synthetic_only') is not True:
            raise ValueError('Synthetic database required')
        env = dict(os.environ,HA_TEST_DATABASE_URL=config['dsn'])
        command = [sys.executable,'-m','unittest']
        command += [args.suite,'-v'] if args.suite else ['discover','-s','tests','-t','.']
        result = subprocess.run(command,cwd=ROOT,env=env)
        sys.exit(result.returncode)
    else:
        if not DATA.is_dir():
            raise ValueError('No project database to stop')
        run(str(BIN/'pg_ctl.exe'),'-D',str(DATA),'stop','-m','fast','-w')


if __name__ == '__main__':
    main()
