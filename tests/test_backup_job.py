from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import MagicMock,patch
from ha.connected.backup_job import capture_backup

class BackupJobTests(unittest.TestCase):
    def test_dump_failure_cleans_private_staging_and_does_not_publish_bundle(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);executable=root/'pg_dump';executable.write_bytes(b'fixture')
            conn=MagicMock();snapshot=MagicMock();snapshot.fetchone.return_value=('fixture-snapshot',)
            versions=MagicMock();versions.fetchall.return_value=[]
            conn.execute.side_effect=[None,snapshot,versions]
            connection=MagicMock();connection.__enter__.return_value=conn
            with patch('ha.connected.backup_job.psycopg.connect',return_value=connection),patch('ha.connected.backup_job.subprocess.run',return_value=subprocess.CompletedProcess([],1)) as run:
                with self.assertRaises(RuntimeError):
                    capture_backup('host=127.0.0.1 dbname=fixture user=fixture password=fictional-only',None,bytes(32),root/'bundle',executable)
            args=run.call_args.args[0];env=run.call_args.kwargs['env']
            self.assertNotIn('fictional-only',' '.join(args))
            self.assertEqual(env['PGPASSWORD'],'fictional-only')
            self.assertEqual(list(root.iterdir()),[executable])

    def test_missing_explicit_database_settings_and_inline_tls_password_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);executable=root/'pg_dump';executable.write_bytes(b'fixture')
            for dsn in ('dbname=fixture','host=localhost dbname=fixture user=fixture sslpassword=fictional-only'):
                with self.subTest(dsn=dsn),self.assertRaises(ValueError):
                    capture_backup(dsn,None,bytes(32),root/'bundle',executable)

    def test_remote_failure_prevents_success_and_uses_snapshot_versions(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); executable=root/'pg_dump'; executable.write_bytes(b'fixture')
            conn=MagicMock(); snapshot=MagicMock(); snapshot.fetchone.return_value=('fixed-snapshot',)
            rows=MagicMock(); rows.fetchall.return_value=[]
            conn.execute.side_effect=[None,snapshot,rows]
            connection=MagicMock(); connection.__enter__.return_value=conn
            client=object()
            with patch('ha.connected.backup_job.psycopg.connect',return_value=connection), \
                 patch('ha.connected.backup_job.subprocess.run',return_value=subprocess.CompletedProcess([],0)), \
                 patch('ha.connected.backup_job.create_bundle',return_value={'inventory':{'snapshot_id':'fixture'}}), \
                 patch('ha.connected.backup_job.copy_bundle',side_effect=ValueError('remote mismatch')) as copied:
                with self.assertRaises(ValueError):
                    capture_backup('host=localhost dbname=fixture user=fixture',None,bytes(32),
                                   root/'bundle',executable,offhost=(client,'private-backups'))
            copied.assert_called_once_with(root/'bundle',bytes(32),[],client,'private-backups')
            self.assertEqual(list(root.iterdir()),[executable])
