"""Real persistence/authority checks for user statements, never tax approval."""
import os
import unittest
from datetime import datetime, timedelta, timezone
from ha.connected.domain import Principal, Scope
from ha.connected.postgres import PostgresRepository, PostgresLedger

DSN=os.environ.get('HA_TEST_DATABASE_URL')

@unittest.skipUnless(DSN,'Isolated real PostgreSQL configuration unavailable')
class RecordConfirmationTests(unittest.TestCase):
    def setUp(self):
        from ha.connected.record_confirmation import RecordConfirmations
        self.repo=PostgresRepository(DSN);self.repo.migrate()
        with self.repo.transaction() as conn:
            conn.execute('TRUNCATE ha_connected.profiles CASCADE')
            conn.execute("INSERT INTO ha_connected.profiles VALUES ('orchard'),('cedar')")
            conn.execute("INSERT INTO ha_connected.businesses VALUES ('business','orchard'),('cedar-business','cedar')")
            for action in ('read','post','correct'):
                conn.execute('INSERT INTO ha_connected.grants VALUES (%s,%s,%s,%s,%s)',('owner','orchard','business',2025,action))
        self.scope=Scope('orchard','business',2025)
        self.owner=Principal('owner',datetime.now(timezone.utc)+timedelta(minutes=5),True)
        self.ledger=PostgresLedger(self.repo);self.confirmations=RecordConfirmations(self.repo)
        self.ledger.post_event(self.owner,self.scope,dict(id='sale',date='2025-10-02',kind='income',amount_minor=1000))
        self.request=dict(ledger_revision=1,reviewed_through='2025-12-31',confirmed=True,reason='Checked my income and expenses against my records',idempotency_key='check-1')

    def permit(self):
        with self.repo.transaction() as conn:
            conn.execute("INSERT INTO ha_connected.grants VALUES ('owner','orchard','business',2025,'confirm_records')")

    def test_confirmation_requires_explicit_authority_and_remains_self_reported(self):
        self.assertFalse(self.confirmations.view(self.owner,self.scope)['can_confirm'])
        with self.assertRaises(PermissionError):self.confirmations.submit(self.owner,self.scope,self.request)
        self.permit();result=self.confirmations.submit(self.owner,self.scope,self.request)
        self.assertEqual(result,self.confirmations.submit(self.owner,self.scope,self.request))
        fresh=type(self.confirmations)(PostgresRepository(DSN)).view(self.owner,self.scope)
        self.assertEqual(len(fresh['history']),1);self.assertEqual(fresh['status'],'current')
        self.assertEqual(fresh['latest']['actor'],'owner');self.assertEqual(fresh['latest']['statement_version'],'records-v1')
        draft=self.ledger.project(self.owner,self.scope,'year')
        self.assertEqual(draft['records_confirmation']['status'],'current')
        self.assertEqual(draft['entry_completeness'],'not_verified');self.assertIsNone(draft['missing_entries'])
        self.assertEqual(draft['book_profit_minor'],1000);self.assertFalse(draft['filing_authorized'])
        self.assertFalse(draft['support_review_complete'])

    def test_new_entry_invalidates_and_preserves_original_and_rejects_stale_submission(self):
        self.permit();first=self.confirmations.submit(self.owner,self.scope,self.request)
        self.ledger.post_event(self.owner,self.scope,dict(id='cost',date='2025-10-03',kind='expense',amount_minor=100))
        self.assertEqual(self.confirmations.view(self.owner,self.scope)['status'],'stale')
        with self.assertRaises(ValueError):self.confirmations.submit(self.owner,self.scope,{**self.request,'idempotency_key':'stale'})
        second=self.confirmations.submit(self.owner,self.scope,{**self.request,'ledger_revision':2,'idempotency_key':'check-2'})
        self.assertNotEqual(first['confirmation_id'],second['confirmation_id'])
        self.assertEqual(len(self.confirmations.view(self.owner,self.scope)['history']),2)
        self.assertEqual(first,self.confirmations.submit(self.owner,self.scope,self.request))
        with self.assertRaises(ValueError):self.confirmations.submit(self.owner,self.scope,{**self.request,'reason':'Changed retry'})
        with self.repo.transaction() as conn:conn.execute("DELETE FROM ha_connected.grants WHERE action='confirm_records'")
        with self.assertRaises(PermissionError):self.confirmations.submit(self.owner,self.scope,self.request)

    def test_dates_explicit_choice_and_scope_are_validated(self):
        self.permit()
        invalid=[{'confirmed':False},{'confirmed':1},{'ledger_revision':True},{'ledger_revision':-1},
                 {'reviewed_through':'2025-10-01'},{'reviewed_through':'2024-12-31'},
                 {'reviewed_through':'2099-12-31'},{'reason':''},{'actor':'forged'}]
        for changes in invalid:
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                self.confirmations.submit(self.owner,self.scope,{**self.request,**changes})
        with self.assertRaises(PermissionError):self.confirmations.view(self.owner,Scope('cedar','cedar-business',2025))

    def test_append_only_and_concurrent_retry(self):
        import psycopg
        from concurrent.futures import ThreadPoolExecutor
        self.permit()
        with ThreadPoolExecutor(max_workers=3) as pool:
            results=list(pool.map(lambda _:self.confirmations.submit(self.owner,self.scope,self.request),range(3)))
        self.assertTrue(all(r==results[0] for r in results))
        self.assertEqual(len(self.confirmations.view(self.owner,self.scope)['history']),1)
        for sql in ('UPDATE ha_connected.record_confirmations SET actor=actor','DELETE FROM ha_connected.record_confirmations'):
            with self.assertRaises(psycopg.errors.CheckViolation),self.repo.transaction() as conn:conn.execute(sql)

    def test_api_session_csrf_scope_and_revocation(self):
        import json,threading
        from http.client import HTTPConnection
        from ha.connected.api import create_server
        from ha.connected.auth import Sessions
        sessions=Sessions();cookie,csrf=sessions.open(self.owner)
        server=create_server(('127.0.0.1',0),sessions,self.ledger,None,None,'https://ha.example')
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        def call(method,path,body=None,signed=True,verified=True):
            headers={'Origin':'https://ha.example','Content-Type':'application/json'}
            if signed:headers['Cookie']='__Host-ha_session='+cookie
            if verified:headers['X-HA-CSRF']=csrf
            conn=HTTPConnection(*server.server_address,timeout=3)
            conn.request(method,path,json.dumps(body) if body else None,headers)
            response=conn.getresponse();result=response.status,json.loads(response.read());conn.close();return result
        route='/api/connected/records/confirmations'
        payload={'scope':{'profile':'orchard','business':'business','year':2025},'confirmation':self.request}
        try:
            self.assertEqual(call('GET',route+'?profile=orchard&business=business&year=2025',signed=False)[0],401)
            self.assertEqual(call('POST',route,payload,verified=False)[0],403)
            status,view=call('GET',route+'?profile=orchard&business=business&year=2025')
            self.assertEqual(status,200);self.assertFalse(view['can_confirm'])
            self.assertEqual(call('POST',route,payload)[0],404)
            self.permit();self.assertEqual(call('POST',route,payload)[0],201)
            self.assertEqual(call('GET',route+'?profile=cedar&business=cedar-business&year=2025')[0],404)
            with self.repo.transaction() as conn:conn.execute("DELETE FROM ha_connected.grants WHERE action='confirm_records'")
            self.assertEqual(call('POST',route,payload)[0],404)
            sessions.logout(cookie)
            self.assertEqual(call('GET',route+'?profile=orchard&business=business&year=2025')[0],401)
        finally:server.shutdown();server.server_close();thread.join()
