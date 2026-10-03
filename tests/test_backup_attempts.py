from datetime import datetime,timedelta,timezone
import unittest
from ha.connected.backup_attempts import assess_attempts

class AttemptHealthTests(unittest.TestCase):
    def setUp(self):self.now=datetime(2026,10,2,12,tzinfo=timezone.utc)
    def event(self,attempt,status,seconds=0):
        result={'format':'ha-backup-attempt-v1','attempt_id':attempt*32,'status':status,
            'observed_at':(self.now+timedelta(seconds=seconds)).isoformat(),
            'recovery_verified':False,'deletion_authorized':False}
        if status=='completed':result.update(document_versions=4,prefix='ha-recovery/'+'a'*32+'/',
             recovery_key_id='fixture',copy_verified=True,locator_verified=True)
        if status=='failed':result['message']='HA backup failed; no completion confirmed'
        return result
    def test_newer_failure_or_unfinished_attempt_overrides_old_success(self):
        for terminal,status in [('failed','failed'),(None,'unfinished')]:
            events=[self.event('a','started'),self.event('a','completed',1),self.event('b','started',2)]
            if terminal:events.append(self.event('b',terminal,3))
            result=assess_attempts(events,now=self.now+timedelta(seconds=4))
            self.assertEqual(result['status'],status)
            self.assertFalse(result['recovery_verified'])
    def test_completed_attempt_age_and_empty_window(self):
        events=[self.event('a','started'),self.event('a','completed',1)]
        self.assertEqual(assess_attempts(events,now=self.now+timedelta(seconds=2))['status'],'completed_observed')
        self.assertEqual(assess_attempts(events,now=self.now+timedelta(hours=37))['status'],'stale_attempt')
        self.assertEqual(assess_attempts([],now=self.now)['status'],'no_attempt_observed')
    def test_invalid_transition_out_of_order_future_and_unknown_fields_reject(self):
        cases=[[self.event('a','completed')],
          [self.event('a','started'),self.event('a','failed'),self.event('a','completed')],
          [self.event('a','started',2),self.event('b','started',1)],
          [self.event('a','started',10)],
          [{**self.event('a','started'),'secret':'should not be accepted'}]]
        for events in cases:
            with self.subTest(events=events),self.assertRaises(ValueError):assess_attempts(events,now=self.now+timedelta(seconds=3))
    def test_older_attempt_finishing_late_cannot_hide_newer_start(self):
        events=[self.event('a','started'),self.event('b','started',1),self.event('a','completed',2)]
        self.assertEqual(assess_attempts(events,now=self.now+timedelta(seconds=3))['status'],'unfinished')

    def test_cli_rejects_duplicate_fields_and_oversize_without_echo(self):
        import subprocess,sys
        for payload in [b'{"status":"started","status":"completed","secret":"fictional-secret"}',b'x'*1048577]:
            result=subprocess.run([sys.executable,'-m','ha.connected.backup_attempts'],input=payload,capture_output=True,timeout=10)
            self.assertEqual(result.returncode,2)
            self.assertNotIn(b'fictional-secret',result.stdout+result.stderr)
            self.assertIn(b'invalid_journal_window',result.stdout)
