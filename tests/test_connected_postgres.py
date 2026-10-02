"""Real PostgreSQL tests. Missing config is a reported skip, never cloud proof."""
import json
import os
import unittest
from pathlib import Path
from datetime import datetime, timedelta, timezone
from ha.connected.domain import Principal, Scope
from ha.connected.postgres import PostgresRepository, PostgresLedger

DSN = os.environ.get('HA_TEST_DATABASE_URL')


@unittest.skipUnless(DSN, 'Real PostgreSQL test configuration unavailable')
class PostgresTests(unittest.TestCase):
    def setUp(self):
        self.repo = PostgresRepository(DSN)
        self.repo.migrate()
        with self.repo.transaction() as conn:
            conn.execute('TRUNCATE ha_connected.profiles CASCADE')
            conn.execute("INSERT INTO ha_connected.profiles VALUES ('orchard'),('cedar')")
            conn.execute("INSERT INTO ha_connected.businesses VALUES ('business','orchard'),('cedar-business','cedar')")
            for action in ('read', 'post', 'correct', 'upload', 'restore'):
                conn.execute('INSERT INTO ha_connected.grants VALUES (%s,%s,%s,%s,%s)', ('orchard-owner','orchard','business',2026,action))
        self.scope = Scope('orchard','business',2026)
        self.owner = Principal('orchard-owner', datetime.now(timezone.utc)+timedelta(minutes=5), True)
        self.ledger = PostgresLedger(self.repo)

    def test_fixture_persists_across_repository_restart(self):
        fixture = json.loads((Path(__file__).resolve().parents[1]/'docs/fixtures/day8-connected-workflow.json').read_text())
        for event in fixture['events']:
            self.ledger.post_event(self.owner, self.scope, event)
        fresh = PostgresLedger(PostgresRepository(DSN))
        draft = fresh.project(self.owner, self.scope, 'year')
        self.assertEqual(draft['book_profit_minor'],118000)
        self.assertEqual(draft['owner_payments_confirmed_minor'],0)
        self.assertEqual(len(fresh.history(self.owner,self.scope)),6)

    def test_retry_conflict_and_revoked_membership(self):
        event = dict(id='sale',date='2026-10-02',kind='income',amount_minor=1000)
        self.ledger.post_event(self.owner,self.scope,event)
        self.ledger.post_event(self.owner,self.scope,event)
        self.assertEqual(len(self.ledger.history(self.owner,self.scope)),1)
        with self.assertRaises(ValueError):
            self.ledger.post_event(self.owner,self.scope,{**event,'amount_minor':2000})
        with self.repo.transaction() as conn:
            conn.execute('DELETE FROM ha_connected.grants')
        with self.assertRaises(PermissionError):
            self.ledger.project(self.owner,self.scope,'year')

    def test_cross_profile_foreign_key_constraint(self):
        import psycopg
        with self.assertRaises(psycopg.errors.ForeignKeyViolation):
            with self.repo.transaction() as conn:
                conn.execute('INSERT INTO ha_connected.grants VALUES (%s,%s,%s,%s,%s)', ('orchard-owner','orchard','cedar-business',2026,'read'))

    def test_document_versions_survive_new_repository(self):
        from io import BytesIO
        from ha.connected.documents import Documents,MemoryObjects
        objects = MemoryObjects()
        docs = Documents(self.repo,objects,lambda data,mime:True)
        original = docs.upload(self.owner,self.scope,BytesIO(b'original fictional receipt'),'text/plain','original-key')
        again = docs.upload(self.owner,self.scope,BytesIO(b'original fictional receipt'),'text/plain','original-key')
        self.assertEqual(original,again)
        corrected = docs.correct(self.owner,self.scope,original.document_id,BytesIO(b'corrected fictional receipt'),'text/plain','fix-key','Corrected source')
        new = Documents(PostgresRepository(DSN),objects,lambda data,mime:True)
        self.assertEqual(new.read(self.owner,self.scope,original.document_id,original.version_id),b'original fictional receipt')
        self.assertEqual(new.read(self.owner,self.scope,original.document_id,corrected.version_id),b'corrected fictional receipt')
        self.assertEqual(len(new.repository.list_versions(self.scope)),2)

    def test_concurrent_retries_and_corrections_are_serialized(self):
        from concurrent.futures import ThreadPoolExecutor
        event = dict(id='sale',date='2026-10-02',kind='income',amount_minor=1000)
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _:self.ledger.post_event(self.owner,self.scope,event),range(4)))
        self.assertEqual(len(self.ledger.history(self.owner,self.scope)),1)
        self.assertTrue(all(r['id']=='sale' for r in results))
        def correct(n):
            try:
                self.ledger.post_event(self.owner,self.scope,dict(id='fix'+str(n),date='2026-10-03',kind='correction',replaces='sale',reason='Updated',amount_minor=2000))
                return True
            except ValueError:
                return False
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(correct,range(2)))
        self.assertEqual(sum(outcomes),1)
        self.assertEqual(self.ledger.project(self.owner,self.scope,'year')['income_minor'],2000)

    def test_support_review_scope_integrity_and_append_only_history(self):
        import uuid
        import psycopg
        self.ledger.post_event(self.owner,self.scope,dict(id='review-sale',date='2026-10-02',kind='income',amount_minor=1000))
        statement = """INSERT INTO ha_connected.support_reviews
            (decision_id,profile_id,business_id,tax_year,event_id,event_fingerprint,decision,reason,actor,idempotency_key,request_fingerprint)
            VALUES (%s,%s,%s,2026,'review-sale',%s,'needs_information','Provide support','fixture-reviewer',%s,%s)"""
        with self.repo.transaction() as conn:
            self.assertEqual(conn.execute("SELECT count(*) FROM ha_connected.grants WHERE action='review_support'").fetchone()[0],0)
            conn.execute(statement,(uuid.uuid4(),'orchard','business','a'*64,'review-key','b'*64))
        with self.assertRaises(psycopg.errors.ForeignKeyViolation):
            with self.repo.transaction() as conn:
                conn.execute(statement,(uuid.uuid4(),'cedar','cedar-business','a'*64,'foreign-review','b'*64))
        with self.assertRaises(psycopg.errors.ForeignKeyViolation):
            with self.repo.transaction() as conn:
                conn.execute("""INSERT INTO ha_connected.support_reviews
                    (decision_id,profile_id,business_id,tax_year,event_id,event_fingerprint,document_id,version_id,
                     decision,reason,actor,idempotency_key,request_fingerprint)
                    VALUES (%s,'orchard','business',2026,'review-sale',%s,'missing-document','missing-version',
                            'accepted','Review fixture','fixture-reviewer','missing-reference',%s)""",
                    (uuid.uuid4(),'a'*64,'b'*64))
        for command in ("UPDATE ha_connected.support_reviews SET reason='Changed'",'DELETE FROM ha_connected.support_reviews'):
            with self.assertRaises(psycopg.errors.CheckViolation):
                with self.repo.transaction() as conn:conn.execute(command)
        with PostgresRepository(DSN).transaction() as conn:
            self.assertEqual(conn.execute('SELECT count(*) FROM ha_connected.support_reviews').fetchone()[0],1)

    def test_support_service_requires_reviewer_and_authenticates_receipt(self):
        from io import BytesIO
        from ha.connected.documents import Documents, MemoryObjects
        from ha.connected.support_review import SupportReviews
        event=dict(id='expense-review',date='2026-10-02',kind='expense',amount_minor=1000)
        self.ledger.post_event(self.owner,self.scope,event)
        objects=MemoryObjects(); docs=Documents(self.repo,objects,lambda data,mime:True)
        version=docs.upload(self.owner,self.scope,BytesIO(b'fictional receipt'),'text/plain','review-doc')
        service=SupportReviews(self.repo,docs)
        request=dict(event_id=event['id'],decision='accepted',reason='Receipt matches',idempotency_key='review-1',
                     document_id=version.document_id,version_id=version.version_id)
        with self.assertRaises(PermissionError):service.submit(self.owner,self.scope,request)
        with self.repo.transaction() as conn:
            conn.execute("INSERT INTO ha_connected.grants VALUES ('orchard-owner','orchard','business',2026,'review_support')")
        accepted=service.submit(self.owner,self.scope,request)
        self.assertEqual(service.submit(self.owner,self.scope,request),accepted)
        self.assertEqual(len(service.history(self.owner,self.scope)),1)
        reviewed=self.ledger.project(self.owner,self.scope,'year')
        self.assertTrue(reviewed['support_review_complete'])
        self.assertEqual(reviewed['missing_receipts'],[])
        self.assertEqual(reviewed['book_profit_minor'],-1000)
        self.assertFalse(reviewed['filing_authorized'])
        self.assertEqual(service.history(self.owner,self.scope)[0]['actor'],self.owner.subject)
        with self.assertRaises(ValueError):service.submit(self.owner,self.scope,{**request,'reason':'different'})
        objects.data[version.object_key]=b'corrupted'
        with self.assertRaises(ValueError):service.submit(self.owner,self.scope,{**request,'idempotency_key':'review-2'})
        with self.assertRaises(ValueError):service.submit(self.owner,self.scope,{**request,'actor':'forged'})
        self.assertEqual(len(service.history(self.owner,self.scope)),1)
        with self.assertRaises(ValueError):
            service.submit(self.owner,self.scope,dict(event_id=event['id'],decision='accepted',reason='No receipt',idempotency_key='missing-receipt'))
        objects.data[version.object_key]=b'fictional receipt'
        docs.correct(self.owner,self.scope,version.document_id,BytesIO(b'corrected receipt'),'text/plain','review-doc-fix','Correction')
        with self.assertRaises(ValueError):service.submit(self.owner,self.scope,{**request,'idempotency_key':'stale-doc'})
        stale=self.ledger.project(self.owner,self.scope,'year')
        self.assertIn('document_changed',stale['support_review_queue'][0]['reasons'])
        self.assertFalse(stale['support_review_complete'])
        self.ledger.post_event(self.owner,self.scope,dict(id='cash-review',date='2026-10-02',kind='income',method='cash',amount_minor=1000))
        with self.assertRaises(ValueError):
            service.submit(self.owner,self.scope,dict(event_id='cash-review',decision='accepted',reason='Review',idempotency_key='cash-no-explanation'))
        with self.repo.transaction() as conn:
            conn.execute("DELETE FROM ha_connected.grants WHERE action='review_support'")
        with self.assertRaises(PermissionError):service.submit(self.owner,self.scope,request)
        self.assertFalse(self.ledger.project(self.owner,self.scope,'year')['support_review_complete'])

    def test_review_reopens_after_money_correction_and_reconsideration(self):
        from ha.connected.documents import Documents,MemoryObjects
        from ha.connected.support_review import SupportReviews
        self.ledger.post_event(self.owner,self.scope,dict(id='review-income',date='2026-10-02',kind='income',amount_minor=1000))
        service=SupportReviews(self.repo,Documents(self.repo,MemoryObjects(),lambda data,mime:True))
        with self.repo.transaction() as conn:
            conn.execute("INSERT INTO ha_connected.grants VALUES ('orchard-owner','orchard','business',2026,'review_support')")
        request=dict(event_id='review-income',decision='accepted',reason='Checked income',idempotency_key='income-review')
        service.submit(self.owner,self.scope,request)
        self.assertTrue(self.ledger.project(self.owner,self.scope,'year')['support_review_complete'])
        service.submit(self.owner,self.scope,{**request,'decision':'needs_information','idempotency_key':'income-reconsider'})
        self.assertFalse(self.ledger.project(self.owner,self.scope,'year')['support_review_complete'])
        self.ledger.post_event(self.owner,self.scope,dict(id='income-fixed',date='2026-10-03',kind='correction',replaces='review-income',reason='New amount',amount_minor=2000))
        draft=self.ledger.project(self.owner,self.scope,'year')
        self.assertEqual(draft['income_minor'],2000)
        self.assertIn('entry_changed',draft['support_review_queue'][0]['reasons'])
        self.assertEqual(len(service.history(self.owner,self.scope)),2)

    def test_support_review_http_session_csrf_scope_and_revocation(self):
        import threading
        import http.client
        from ha.connected.api import create_server
        from ha.connected.auth import Sessions
        from ha.connected.documents import Documents,MemoryObjects
        self.ledger.post_event(self.owner,self.scope,dict(id='http-income',date='2026-10-02',kind='income',amount_minor=1000))
        sessions=Sessions(); cookie,csrf=sessions.open(self.owner)
        server=create_server(('127.0.0.1',0),sessions,self.ledger,Documents(self.repo,MemoryObjects(),lambda data,mime:True),None,'https://ha.example')
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        def cleanup():
            server.shutdown();server.server_close();thread.join(5)
        self.addCleanup(cleanup)
        def request(method,path,body=None,signed=True,verified=True):
            headers={'Content-Type':'application/json','Origin':'https://ha.example'}
            if signed:headers['Cookie']='__Host-ha_session='+cookie
            if verified:headers['X-HA-CSRF']=csrf
            client=http.client.HTTPConnection(*server.server_address,timeout=5)
            try:
                client.request(method,path,json.dumps(body) if body is not None else None,headers)
                response=client.getresponse();return response.status,json.loads(response.read())
            finally:client.close()
        path='/api/connected/support/reviews'
        body={'scope':{'profile':'orchard','business':'business','year':2026},
              'review':{'event_id':'http-income','decision':'accepted','reason':'Verified income','idempotency_key':'http-review'}}
        self.assertEqual(request('POST',path,body,signed=False)[0],401)
        self.assertEqual(request('POST',path,body,verified=False)[0],403)
        self.assertEqual(request('POST',path,body)[0],404)
        self.assertFalse(request('GET',path+'?profile=orchard&business=business&year=2026')[1]['can_review'])
        with self.repo.transaction() as conn:
            conn.execute("INSERT INTO ha_connected.grants VALUES ('orchard-owner','orchard','business',2026,'review_support')")
        accepted=request('POST',path,body)
        self.assertEqual(accepted[0],201)
        self.assertEqual(request('POST',path,body),accepted)
        status,history=request('GET',path+'?profile=orchard&business=business&year=2026')
        self.assertEqual(status,200);self.assertEqual(len(history['reviews']),1);self.assertTrue(history['can_review'])
        self.assertEqual(request('GET',path+'?profile=cedar&business=cedar-business&year=2026')[0],404)
        self.assertTrue(request('GET','/api/connected/draft?profile=orchard&business=business&year=2026')[1]['support_review_complete'])
        with self.repo.transaction() as conn:
            conn.execute("DELETE FROM ha_connected.grants WHERE action='review_support'")
        self.assertEqual(request('POST',path,body)[0],404)
        self.assertFalse(request('GET',path+'?profile=orchard&business=business&year=2026')[1]['can_review'])
        sessions.logout(cookie)
        self.assertEqual(request('GET',path+'?profile=orchard&business=business&year=2026')[0],401)

    def test_document_correction_waits_for_inflight_review_then_reopens_queue(self):
        from concurrent.futures import ThreadPoolExecutor, TimeoutError
        from threading import Event, local
        from io import BytesIO
        from ha.connected.documents import Documents,MemoryObjects
        from ha.connected.support_review import SupportReviews
        entered,release,attempted=Event(),Event(),Event()
        worker=local()
        original_lock=self.repo.lock_scope
        def observed_lock(conn,scope):
            if getattr(worker,'correcting',False):attempted.set()
            return original_lock(conn,scope)
        self.repo.lock_scope=observed_lock
        self.addCleanup(setattr,self.repo,'lock_scope',original_lock)
        class BlockingObjects(MemoryObjects):
            def get(self,key,version):
                entered.set()
                if not release.wait(10):raise RuntimeError('Fixture release timeout')
                return super().get(key,version)
        docs=Documents(self.repo,BlockingObjects(),lambda data,mime:True)
        original=docs.upload(self.owner,self.scope,BytesIO(b'original fictional receipt'),'text/plain','race-original')
        self.ledger.post_event(self.owner,self.scope,dict(id='race-expense',date='2026-10-02',kind='expense',amount_minor=1000))
        with self.repo.transaction() as conn:
            conn.execute("INSERT INTO ha_connected.grants VALUES ('orchard-owner','orchard','business',2026,'review_support')")
        service=SupportReviews(self.repo,docs)
        request=dict(event_id='race-expense',decision='accepted',reason='Checked original',idempotency_key='race-review',
                     document_id=original.document_id,version_id=original.version_id)
        with ThreadPoolExecutor(max_workers=2) as pool:
            review=pool.submit(service.submit,self.owner,self.scope,request)
            try:
                self.assertTrue(entered.wait(5))
                def correct():
                    worker.correcting=True
                    return docs.correct(self.owner,self.scope,original.document_id,
                        BytesIO(b'corrected fictional receipt'),'text/plain','race-correction','Changed source')
                correction=pool.submit(correct)
                self.assertTrue(attempted.wait(5))
                with self.assertRaises(TimeoutError):correction.result(timeout=0.2)
            finally:release.set()
            self.assertEqual(review.result(timeout=5)['decision'],'accepted')
            corrected=correction.result(timeout=5)
        self.assertEqual(corrected.previous_version_id,original.version_id)
        draft=self.ledger.project(self.owner,self.scope,'year')
        self.assertFalse(draft['support_review_complete'])
        self.assertIn('document_changed',draft['support_review_queue'][0]['reasons'])
        self.assertEqual(draft['expense_minor'],1000)
        self.assertEqual(len(service.history(self.owner,self.scope)),1)
