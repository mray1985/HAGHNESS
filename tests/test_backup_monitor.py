from datetime import datetime, timedelta, timezone
from io import BytesIO
import json
import unittest
from ha.connected.backup_monitor import assess, check

class BackupMonitorTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,10,2,12,tzinfo=timezone.utc)
        self.receipt={'format':'ha-backup-receipt-v1','snapshot_id':'fictional',
          'completed_at':self.now.isoformat(),'region':'nyc3','bucket':'ha-backups',
          'prefix':'ha-recovery/'+'a'*32+'/','recovery_key_id':'fixture-key',
          'document_versions':4,'copy_verified':True,'recovery_verified':False,
          'deletion_authorized':False}
    def test_current_and_stale_boundaries_never_claim_recovery(self):
        for hours,status in [(0,'current_locator'),(36,'current_locator'),(37,'stale_locator')]:
            with self.subTest(hours=hours):
                result=assess(self.receipt,now=self.now+timedelta(hours=hours))
                self.assertEqual(result['status'],status)
                self.assertFalse(result['archive_integrity_verified'])
                self.assertFalse(result['recovery_verified'])
                self.assertFalse(result['deletion_authorized'])
    def test_future_completion_and_invalid_monitor_time_reject(self):
        for now in [self.now-timedelta(seconds=1),self.now.replace(tzinfo=None)]:
            with self.assertRaises(ValueError):assess(self.receipt,now=now)
        with self.assertRaises(ValueError):assess(self.receipt,max_age=timedelta(0))
    def test_changed_locator_flags_reject(self):
        for field in ['copy_verified','recovery_verified','deletion_authorized']:
            changed={**self.receipt,field:not self.receipt[field]}
            with self.assertRaises(ValueError):assess(changed,now=self.now)
    def test_private_locator_read_is_required_and_body_closed(self):
        body=BytesIO(json.dumps(self.receipt).encode());calls=[]
        class Client:
            def get_object(inner,**kwargs):calls.append(kwargs);return {'Body':body}
        result=check(Client(),'ha-backups',self.receipt['prefix'],'nyc3',now=self.now)
        self.assertEqual(result['status'],'current_locator');self.assertTrue(body.closed)
        self.assertEqual(calls,[{'Bucket':'ha-backups','Key':self.receipt['prefix']+'receipt.json'}])
    def test_provider_denial_cannot_report_available(self):
        class Client:
            def get_object(self,**kwargs):raise PermissionError('denied')
        with self.assertRaises(PermissionError):check(Client(),'ha-backups',self.receipt['prefix'],'nyc3')

    def test_cli_exit_status_and_failure_output_are_sanitized(self):
        from contextlib import redirect_stdout
        from io import StringIO
        from unittest.mock import patch
        from ha.connected.backup_monitor import main
        env={'HA_SPACES_REGION':'nyc3','HA_BACKUP_SPACES_BUCKET':'ha-backups',
             'HA_BACKUP_SPACES_ACCESS_KEY':'fictional','HA_BACKUP_SPACES_SECRET_KEY':'fictional-secret'}
        for state,code in [('current_locator',0),('stale_locator',1),('denied',2)]:
            output=StringIO()
            with patch.dict('os.environ',env),patch('boto3.client'),patch('ha.connected.backup_monitor.check') as probe,redirect_stdout(output):
                if state=='denied':probe.side_effect=PermissionError('fictional-secret')
                else:probe.return_value={'status':state,'recovery_verified':False}
                self.assertEqual(main(['--prefix',self.receipt['prefix']]),code)
            self.assertNotIn('fictional-secret',output.getvalue())
            self.assertFalse(json.loads(output.getvalue())['recovery_verified'])
