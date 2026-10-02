import unittest
from datetime import datetime, timedelta, timezone
from ha.connected.backup_retention import Snapshot, retention_plan

class BackupRetentionTests(unittest.TestCase):
    def test_daily_monthly_latest_and_holds_are_preserved(self):
        now=datetime(2026,10,2,tzinfo=timezone.utc)
        snapshots=[Snapshot('recent',now-timedelta(days=34)),
                   Snapshot('boundary',now-timedelta(days=35)),
                   Snapshot('old-september',datetime(2026,7,1,tzinfo=timezone.utc)),
                   Snapshot('monthly',datetime(2026,7,31,tzinfo=timezone.utc)),
                   Snapshot('older-same-month',datetime(2026,7,2,tzinfo=timezone.utc)),
                   Snapshot('held',datetime(2024,1,1,tzinfo=timezone.utc),True),
                   Snapshot('expired',datetime(2024,2,1,tzinfo=timezone.utc))]
        plan=retention_plan(snapshots,now)
        self.assertEqual(set(plan['retain']),{'recent','boundary','monthly','held'})
        self.assertEqual(set(plan['expire_candidates']),{'old-september','older-same-month','expired'})
        self.assertFalse(plan['deletion_authorized'])

    def test_latest_is_kept_even_when_all_backups_are_old(self):
        now=datetime(2026,10,2,tzinfo=timezone.utc)
        self.assertEqual(retention_plan([Snapshot('only',now-timedelta(days=800))],now)['retain'],['only'])

    def test_twelve_month_boundary_and_timezone_are_consistent(self):
        now=datetime(2026,10,2,tzinfo=timezone.utc)
        west=timezone(timedelta(hours=-5))
        plan=retention_plan([Snapshot('latest',now),
            Snapshot('november-utc',datetime(2025,10,31,23,30,tzinfo=west)),
            Snapshot('october-utc',datetime(2025,10,31,22,tzinfo=timezone.utc))],now)
        self.assertEqual(set(plan['retain']),{'latest','november-utc'})
        self.assertEqual(plan['expire_candidates'],['october-utc'])

    def test_invalid_inventory_fails_closed(self):
        now=datetime(2026,10,2,tzinfo=timezone.utc)
        for snapshots in ([Snapshot('x',now),Snapshot('x',now)],
                          [Snapshot('x',now+timedelta(seconds=1))],
                          [Snapshot('x',datetime(2026,1,1))],
                          [Snapshot('',now)], [Snapshot('x',now,'false')]):
            with self.subTest(snapshots=snapshots),self.assertRaises(ValueError):
                retention_plan(snapshots,now)

