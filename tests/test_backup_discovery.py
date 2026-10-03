from datetime import datetime, timedelta, timezone
from io import BytesIO
import json
import unittest
from botocore.exceptions import ClientError
from ha.connected.backup_monitor import discover

class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,10,2,12,tzinfo=timezone.utc)
        self.prefixes=['ha-recovery/'+c*32+'/' for c in 'abc']
        self.receipts={p:{'format':'ha-backup-receipt-v1','snapshot_id':'fictional',
            'completed_at':(self.now-timedelta(hours=i)).isoformat(),'region':'nyc3','bucket':'ha-backups',
            'prefix':p,'recovery_key_id':'fixture-key','document_versions':4,'copy_verified':True,
            'recovery_verified':False,'deletion_authorized':False} for i,p in enumerate(self.prefixes)}
        outer=self
        class Store:
            def __init__(self):self.calls=[];self.bodies=[]
            def list_objects_v2(self,**kwargs):
                self.calls.append(kwargs)
                index=1 if kwargs.get('ContinuationToken') else 0
                return {'IsTruncated':index==0,'NextContinuationToken':'page2',
                        'CommonPrefixes':[{'Prefix':p} for p in outer.prefixes[index*2:index*2+2]]}
            def get_object(self,**kwargs):
                prefix=kwargs['Key'].removesuffix('receipt.json')
                if prefix not in outer.receipts:raise ClientError({'Error':{'Code':'NoSuchKey'}},'GetObject')
                body=BytesIO(json.dumps(outer.receipts[prefix]).encode());self.bodies.append(body);return {'Body':body}
        self.store=Store()
    def test_complete_paginated_scan_selects_completion_not_prefix_order(self):
        self.receipts[self.prefixes[2]]['completed_at']=self.now.isoformat()
        self.receipts[self.prefixes[0]]['completed_at']=(self.now-timedelta(hours=10)).isoformat()
        result=discover(self.store,'ha-backups','nyc3',now=self.now)
        self.assertEqual(result['prefix'],self.prefixes[2]);self.assertEqual(result['status'],'current_locator')
        self.assertEqual(result['listed_prefixes'],3);self.assertEqual(result['receipts_observed'],3)
        self.assertFalse(result['recovery_verified']);self.assertFalse(result['deletion_authorized'])
        self.assertEqual(self.store.calls[1]['ContinuationToken'],'page2')
        self.assertTrue(all(b.closed for b in self.store.bodies))
    def test_incomplete_prefix_without_receipt_does_not_hide_valid_copy(self):
        del self.receipts[self.prefixes[0]]
        result=discover(self.store,'ha-backups','nyc3',now=self.now)
        self.assertEqual(result['prefix'],self.prefixes[1]);self.assertEqual(result['receipts_observed'],2)
        self.receipts.clear();self.assertEqual(discover(self.store,'ha-backups','nyc3',now=self.now)['status'],'no_locator_observed')
    def test_limits_denial_and_bad_receipt_never_return_partial_success(self):
        with self.assertRaises(ValueError):discover(self.store,'ha-backups','nyc3',now=self.now,max_prefixes=2)
        self.receipts[self.prefixes[2]]['copy_verified']=False
        with self.assertRaises(ValueError):discover(self.store,'ha-backups','nyc3',now=self.now)
        def denied(**kwargs):raise ClientError({'Error':{'Code':'AccessDenied','Message':'secret'}},'GetObject')
        self.store.get_object=denied
        with self.assertRaises(ClientError):discover(self.store,'ha-backups','nyc3',now=self.now)
    def test_repeated_tokens_malformed_prefixes_and_future_receipts_reject(self):
        self.store.list_objects_v2=lambda **kwargs:{'IsTruncated':True,'NextContinuationToken':'same','CommonPrefixes':[]}
        with self.assertRaises(ValueError):discover(self.store,'ha-backups','nyc3',now=self.now)
        self.store.list_objects_v2=lambda **kwargs:{'IsTruncated':False,'CommonPrefixes':[{'Prefix':'elsewhere/'}]}
        with self.assertRaises(ValueError):discover(self.store,'ha-backups','nyc3',now=self.now)
        self.store.list_objects_v2=lambda **kwargs:{'IsTruncated':False,'CommonPrefixes':[{'Prefix':self.prefixes[0]}]}
        self.receipts[self.prefixes[0]]['completed_at']=(self.now+timedelta(seconds=1)).isoformat()
        with self.assertRaises(ValueError):discover(self.store,'ha-backups','nyc3',now=self.now)

    def test_empty_listing_requires_valid_time_age_and_bounds(self):
        self.store.list_objects_v2=lambda **kwargs:{'IsTruncated':False}
        for options in [{'max_age':timedelta(0)},{'now':self.now.replace(tzinfo=None)},
                        {'max_pages':0},{'max_prefixes':True}]:
            with self.subTest(options=options),self.assertRaises(ValueError):
                discover(self.store,'ha-backups','nyc3',**options)

    def test_discovery_cli_is_explicit_read_only_and_sanitized(self):
        from contextlib import redirect_stdout
        from io import StringIO
        from unittest.mock import patch
        from ha.connected.backup_monitor import main
        env={'HA_SPACES_REGION':'nyc3','HA_BACKUP_SPACES_BUCKET':'ha-backups',
             'HA_BACKUP_SPACES_ACCESS_KEY':'fictional','HA_BACKUP_SPACES_SECRET_KEY':'secret'}
        for state,code in [('current_locator',0),('no_locator_observed',1),('denied',2)]:
            output=StringIO()
            with patch.dict('os.environ',env),patch('boto3.client'),patch('ha.connected.backup_monitor.discover') as probe,redirect_stdout(output):
                if state=='denied':probe.side_effect=PermissionError('secret')
                else:probe.return_value={'status':state,'recovery_verified':False}
                self.assertEqual(main(['--discover']),code)
            self.assertNotIn('secret',output.getvalue());self.assertFalse(json.loads(output.getvalue())['recovery_verified'])
