import os
from pathlib import Path
import shutil
import subprocess
import unittest
from unittest.mock import patch

if os.name=='posix':
    from scripts.verify_keycloak_session import isolated_database

@unittest.skipUnless(os.name=='posix','Linux PostgreSQL orchestration only')
class SessionProbeCleanupTests(unittest.TestCase):
    def exercise_failed_start(self,fail_stop=False):
        calls=[];roots=[]
        def run(args,**kwargs):
            calls.append(args)
            data=Path(args[args.index('-D')+1]);root=data.parent
            if not roots:roots.append(root)
            if str(args[4]).endswith('/initdb'):data.mkdir()
            elif args[-1]=='start':
                (data/'postmaster.pid').write_text('fictional fixture pid')
                raise subprocess.TimeoutExpired('fictional pg_ctl start',60)
            elif args[-1]=='stop':
                if fail_stop:raise subprocess.CalledProcessError(1,'fictional pg_ctl stop')
                (data/'postmaster.pid').unlink()
            return subprocess.CompletedProcess(args,0)
        with patch('scripts.verify_keycloak_session.os.geteuid',return_value=0),patch('scripts.verify_keycloak_session.os.chown'),patch('scripts.verify_keycloak_session.subprocess.run',side_effect=run):
            with self.assertRaises(subprocess.CalledProcessError if fail_stop else subprocess.TimeoutExpired):
                with isolated_database():self.fail('Failed startup yielded a database')
        self.assertTrue(any(args[-1]=='stop' for args in calls))
        return roots[0]

    def test_startup_timeout_stops_owned_cluster_before_removing_files(self):
        root=self.exercise_failed_start()
        self.assertFalse(root.exists())

    def test_shutdown_failure_preserves_private_cluster_files(self):
        root=self.exercise_failed_start(fail_stop=True)
        try:self.assertTrue((root/'data/postmaster.pid').exists())
        finally:shutil.rmtree(root)
