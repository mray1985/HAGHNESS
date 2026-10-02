import contextlib
from io import StringIO
import unittest
from unittest.mock import patch
from ha.connected.backup_runner import run,main,ReadObjects,REQUIRED

class RunnerTests(unittest.TestCase):
    def test_backup_cannot_run_without_explicit_activation(self):
        for env in ({},{'HA_BACKUP_ENABLED':'false'},{'HA_BACKUP_ENABLED':'TRUE'}):
            with self.subTest(env=env),self.assertRaises(ValueError):run(env)
    def test_partial_configuration_cannot_start_capture(self):
        with patch('ha.connected.backup_runner.capture_backup') as capture,self.assertRaises(ValueError):
            run({'HA_BACKUP_ENABLED':'true'})
        capture.assert_not_called()
    def test_failure_status_does_not_emit_exception_credentials(self):
        output=StringIO()
        with patch('ha.connected.backup_runner.run',side_effect=RuntimeError('fictional-secret-password')),contextlib.redirect_stdout(output):
            self.assertEqual(main(),1)
        self.assertNotIn('fictional-secret-password',output.getvalue())
        self.assertIn('no completion confirmed',output.getvalue())
    def test_reader_surface_does_not_offer_object_publication(self):
        class Objects:
            def get(self,key,version):return b'fixture'
            def put(self,*args):raise AssertionError('Not used')
        reader=ReadObjects(Objects())
        self.assertEqual(reader.get('key','version'),b'fixture')
        self.assertFalse(hasattr(reader,'put'))

    def test_source_bucket_cannot_double_as_backup_destination(self):
        env={name:'fixture' for name in REQUIRED}; env['HA_BACKUP_ENABLED']='true'
        with patch('ha.connected.backup_runner.os.name','posix'),self.assertRaises(ValueError):
            run(env)
