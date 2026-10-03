from datetime import datetime,timedelta,timezone
from io import BytesIO
import json
import unittest
from ha.connected.backup_health import check

class CombinedHealthTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,10,2,12,tzinfo=timezone.utc)
        self.prefix='ha-recovery/'+'a'*32+'/'
        self.receipt={'format':'ha-backup-receipt-v1','snapshot_id':'fictional',
            'completed_at':self.now.isoformat(),'region':'nyc3','bucket':'ha-backups',
            'prefix':self.prefix,'recovery_key_id':'fixture','document_versions':4,
            'copy_verified':True,'recovery_verified':False,'deletion_authorized':False}
        outer=self
        class Store:
            def __init__(self):self.calls=[];self.bodies=[]
            def get_object(self,**kwargs):
                self.calls.append(kwargs);body=BytesIO(json.dumps(outer.receipt).encode())
                self.bodies.append(body);return {'Body':body}
        self.store=Store()
    def event(self,identifier,status,seconds):
        value={'format':'ha-backup-attempt-v1','attempt_id':identifier*32,'status':status,
            'observed_at':(self.now+timedelta(seconds=seconds)).isoformat(),
            'recovery_verified':False,'deletion_authorized':False}
        if status=='completed':value.update(prefix=self.prefix,document_versions=4,recovery_key_id='fixture',copy_verified=True,locator_verified=True)
        if status=='failed':value['message']='HA backup failed; no completion confirmed'
        return value
    def events(self):return [self.event('a','started',-2),self.event('a','completed',2)]
    def test_current_attempt_requires_its_matching_remote_receipt(self):
        result=check(self.events(),self.store,'ha-backups','nyc3',now=self.now+timedelta(seconds=3))
        self.assertEqual(result['status'],'current_observed_attempt')
        self.assertEqual(self.store.calls,[{'Bucket':'ha-backups','Key':self.prefix+'receipt.json'}])
        self.assertTrue(self.store.bodies[0].closed);self.assertTrue(result['journal_window_only'])
        self.assertFalse(result['archive_integrity_verified']);self.assertFalse(result['recovery_verified']);self.assertFalse(result['deletion_authorized'])
    def test_newer_failed_unfinished_or_missing_attempt_cannot_use_old_copy(self):
        for extra,status in [([self.event('b','started',3),self.event('b','failed',4)],'failed'),
                            ([self.event('b','started',3)],'unfinished')]:
            result=check(self.events()+extra,self.store,'ha-backups','nyc3',now=self.now+timedelta(seconds=5))
            self.assertEqual(result['status'],'attempt_attention');self.assertEqual(result['attempt_status'],status)
        self.assertEqual(check([],self.store,'ha-backups','nyc3',now=self.now)['attempt_status'],'no_attempt_observed')
        self.assertEqual(self.store.calls,[])
    def test_mismatched_key_count_or_completion_window_reject(self):
        for change in [{'recovery_key_id':'other'},{'document_versions':5},
            {'completed_at':(self.now-timedelta(seconds=3)).isoformat()},
            {'completed_at':(self.now+timedelta(seconds=3)).isoformat()}]:
            old=self.receipt;self.receipt={**old,**change}
            with self.subTest(change=change),self.assertRaises(ValueError):
                check(self.events(),self.store,'ha-backups','nyc3',now=self.now+timedelta(seconds=5))
            self.receipt=old
    def test_stale_attempt_and_stale_receipt_do_not_report_current(self):
        result=check(self.events(),self.store,'ha-backups','nyc3',now=self.now+timedelta(hours=37))
        self.assertEqual(result['attempt_status'],'stale_attempt');self.assertEqual(self.store.calls,[])
        events=[self.event('a','started',-7200),self.event('a','completed',0)]
        self.receipt['completed_at']=(self.now-timedelta(hours=1)).isoformat()
        result=check(events,self.store,'ha-backups','nyc3',now=self.now+timedelta(hours=36))
        self.assertEqual(result['status'],'locator_attention');self.assertEqual(result['locator_status'],'stale_locator')
    def test_provider_failure_and_invalid_journal_reject(self):
        self.store.get_object=lambda **kwargs:(_ for _ in ()).throw(PermissionError('secret'))
        with self.assertRaises(PermissionError):check(self.events(),self.store,'ha-backups','nyc3',now=self.now+timedelta(seconds=3))
        with self.assertRaises(ValueError):check([self.event('a','completed',0)],self.store,'ha-backups','nyc3',now=self.now)

    def test_cli_failure_windows_are_bounded_sanitized_and_need_no_provider(self):
        import subprocess,sys
        from datetime import datetime
        stamp=datetime.now(timezone.utc)
        events=[self.event('a','started',0),self.event('a','failed',1)]
        for event in events:event['observed_at']=stamp.isoformat()
        result=subprocess.run([sys.executable,'-m','ha.connected.backup_health'],
            input=('\n'.join(json.dumps(e) for e in events)).encode(),capture_output=True,timeout=10)
        self.assertEqual(result.returncode,1);self.assertEqual(json.loads(result.stdout)['attempt_status'],'failed')
        for payload in [b'{"status":"started","status":"completed","secret":"fictional-secret"}',b'x'*1048577]:
            result=subprocess.run([sys.executable,'-m','ha.connected.backup_health'],input=payload,capture_output=True,timeout=10)
            self.assertEqual(result.returncode,2);self.assertNotIn(b'fictional-secret',result.stdout+result.stderr)

    def test_cli_current_receipt_and_provider_failure(self):
        from contextlib import redirect_stdout
        from io import StringIO
        from unittest.mock import patch
        from ha.connected.backup_health import main
        import sys
        class Input:
            buffer=BytesIO(('\n'.join(json.dumps(e) for e in self.events())).encode())
        output=StringIO()
        with patch.object(sys,'stdin',Input()),patch('ha.connected.backup_health.configured_store',return_value=(self.store,'ha-backups','nyc3')),patch('ha.connected.backup_health.datetime') as clock,redirect_stdout(output):
            clock.now.return_value=self.now+timedelta(seconds=3);clock.fromisoformat.side_effect=datetime.fromisoformat
            self.assertEqual(main([]),0)
        self.assertEqual(json.loads(output.getvalue())['status'],'current_observed_attempt')

        output=StringIO();Input.buffer=BytesIO(('\n'.join(json.dumps(e) for e in self.events())).encode())
        with patch.object(sys,'stdin',Input()),patch('ha.connected.backup_health.configured_store',side_effect=PermissionError('fictional-secret')),patch('ha.connected.backup_health.datetime') as clock,redirect_stdout(output):
            clock.now.return_value=self.now+timedelta(seconds=3)
            self.assertEqual(main([]),2)
        self.assertNotIn('fictional-secret',output.getvalue());self.assertEqual(json.loads(output.getvalue())['status'],'unavailable')
