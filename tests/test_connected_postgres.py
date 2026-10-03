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
    def test_payment_correction_is_durable_without_confirmation_or_profit_change(self):
        original=dict(id='owner-payment',date='2026-10-02',kind='owner_estimated_tax_payment',amount_minor=10000,status='recorded_unverified',government_confirmation=None)
        self.ledger.post_event(self.owner,self.scope,original)
        fixed=dict(id='owner-payment-fixed',date='2026-11-02',kind='correction',replaces='owner-payment',amount_minor=12500,reason='Correct recorded payment amount')
        self.ledger.post_event(self.owner,self.scope,fixed)
        fresh=PostgresLedger(PostgresRepository(DSN));fresh.post_event(self.owner,self.scope,fixed)
        history=fresh.history(self.owner,self.scope)
        self.assertEqual(len(history),2);self.assertEqual(history[0]['source'],original)
        self.assertEqual(history[1]['status'],'recorded_unverified');self.assertIsNone(history[1]['government_confirmation'])
        draft=fresh.project(self.owner,self.scope,'month',10)
        self.assertEqual(draft['owner_payments_recorded_minor'],12500);self.assertEqual(draft['owner_payments_confirmed_minor'],0)
        self.assertEqual(draft['book_profit_minor'],0)
        with self.assertRaises(ValueError):fresh.post_event(self.owner,self.scope,{**fixed,'id':'forged','replaces':'owner-payment-fixed','status':'government_confirmed'})
        with self.repo.transaction() as conn:conn.execute("DELETE FROM ha_connected.grants WHERE action='correct'")
        with self.assertRaises(PermissionError):fresh.post_event(self.owner,self.scope,{**fixed,'id':'denied','replaces':'owner-payment-fixed'})

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

    def test_explanation_amendment_persists_and_requires_new_review(self):
        from ha.connected.documents import Documents,MemoryObjects
        from ha.connected.support_review import SupportReviews
        service=SupportReviews(self.repo,Documents(self.repo,MemoryObjects(),lambda data,mime:True))
        with self.repo.transaction() as conn:
            conn.execute("INSERT INTO ha_connected.grants VALUES ('orchard-owner','orchard','business',2026,'review_support')")
        self.ledger.post_event(self.owner,self.scope,dict(id='cash-income',date='2026-10-01',kind='income',amount_minor=1000,method='cash'))
        with self.assertRaises(ValueError):service.submit(self.owner,self.scope,dict(event_id='cash-income',decision='accepted',reason='Checked',idempotency_key='missing-explanation'))
        amended=dict(id='cash-explained',date='2026-10-03',kind='correction',replaces='cash-income',amount_minor=1000,reason='Added explanation',support_changes={'explanation':'Fictional cash sale'})
        self.ledger.post_event(self.owner,self.scope,amended);self.ledger.post_event(self.owner,self.scope,amended)
        fresh=PostgresLedger(PostgresRepository(DSN));history=fresh.history(self.owner,self.scope)
        self.assertEqual(len(history),2);self.assertIsNone(history[0].get('explanation'));self.assertEqual(history[1]['explanation'],'Fictional cash sale')
        self.assertEqual(history[1]['posting_date'],'2026-10-01');self.assertEqual(history[1]['method'],'cash');self.assertEqual(fresh.project(self.owner,self.scope,'year')['income_minor'],1000)
        self.assertFalse(fresh.project(self.owner,self.scope,'year')['support_review_complete'])
        service.submit(self.owner,self.scope,dict(event_id='cash-explained',decision='accepted',reason='Checked explanation',idempotency_key='explained-review'))
        self.assertTrue(fresh.project(self.owner,self.scope,'year')['support_review_complete'])
        supported=fresh.project(self.owner,self.scope,'year')
        self.assertEqual(supported['entry_completeness'],'not_verified');self.assertIsNone(supported['missing_entries'])
        cleared=dict(id='cash-cleared',date='2026-10-04',kind='correction',replaces='cash-explained',amount_minor=1000,reason='Withdraw explanation',support_changes={'explanation':None})
        fresh.post_event(self.owner,self.scope,cleared);draft=fresh.project(self.owner,self.scope,'year')
        self.assertEqual(draft['income_minor'],1000);self.assertEqual(draft['cash_explanations_missing'],['cash-cleared']);self.assertFalse(draft['support_review_complete'])
        self.assertIn('entry_changed',draft['support_review_queue'][0]['reasons']);self.assertEqual(len(service.history(self.owner,self.scope)),1)
        with self.assertRaises(ValueError):service.submit(self.owner,self.scope,dict(event_id='cash-cleared',decision='accepted',reason='Cannot accept missing context',idempotency_key='cleared-review'))
        with self.repo.transaction() as conn:conn.execute("DELETE FROM ha_connected.grants WHERE action='correct'")
        with self.assertRaises(PermissionError):fresh.post_event(self.owner,self.scope,{**amended,'id':'denied-amendment','replaces':'cash-cleared'})
        self.assertEqual(len(fresh.history(self.owner,self.scope)),3)

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

    def test_tax_input_versions_are_scoped_append_only_and_do_not_grant_editing(self):
        import psycopg
        from io import BytesIO
        from ha.connected.documents import Documents, MemoryObjects
        docs = Documents(self.repo, MemoryObjects(), lambda data,mime: True)
        version = docs.upload(self.owner, self.scope, BytesIO(b'fictional input'), 'text/plain', 'tax-original')
        statement = """INSERT INTO ha_connected.tax_input_versions
            (snapshot_id,profile_id,business_id,tax_year,document_id,version_id,
             previous_snapshot_id,actor,reason,idempotency_key,request_fingerprint)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"""
        snapshot = '00000000-0000-4000-8000-000000000001'
        args = (snapshot,'orchard','business',2026,version.document_id,version.version_id,
                None,'orchard-owner','','tax-key','a'*64)
        with self.repo.transaction() as conn:
            conn.execute(statement,args)
            self.assertEqual(conn.execute("SELECT count(*) FROM ha_connected.grants WHERE action='save_tax'").fetchone()[0],0)
        for foreign in (('cedar','cedar-business',2026), ('orchard','business',2025)):
            with self.assertRaises(psycopg.errors.ForeignKeyViolation),self.repo.transaction() as conn:
                conn.execute(statement,('00000000-0000-4000-8000-000000000002',*foreign,
                    version.document_id,version.version_id,None,'actor','','other','b'*64))
        for command in ("UPDATE ha_connected.tax_input_versions SET actor='other'", 'DELETE FROM ha_connected.tax_input_versions'):
            with self.assertRaises(psycopg.errors.CheckViolation),self.repo.transaction() as conn:
                conn.execute(command)
        corrected = docs.correct(self.owner,self.scope,version.document_id,BytesIO(b'fictional corrected input'),
                                 'text/plain','tax-correction','Correction')
        correction_args=('00000000-0000-4000-8000-000000000003','orchard','business',2026,
                         version.document_id,corrected.version_id,snapshot,'orchard-owner','Updated inputs','tax-key-2','c'*64)
        with self.repo.transaction() as conn: conn.execute(statement,correction_args)
        third = docs.correct(self.owner,self.scope,version.document_id,BytesIO(b'fictional third input'),
                             'text/plain','tax-third','Another correction')
        fork_args=('00000000-0000-4000-8000-000000000004','orchard','business',2026,
                   version.document_id,third.version_id,snapshot,'orchard-owner','Fork attempt','fork-key','d'*64)
        with self.assertRaises(psycopg.errors.UniqueViolation) as error,self.repo.transaction() as conn:
            conn.execute(statement,fork_args)
        self.assertEqual(error.exception.diag.constraint_name,'tax_input_one_successor')
        with self.assertRaises(psycopg.errors.CheckViolation),self.repo.transaction() as conn:
            conn.execute(statement,(*fork_args[:8],'',*fork_args[9:]))
        with self.assertRaises(psycopg.errors.UniqueViolation) as error,self.repo.transaction() as conn:
            conn.execute(statement,(*fork_args[:6],None,*fork_args[7:]))
        self.assertEqual(error.exception.diag.constraint_name,'tax_input_one_original')
        fourth = docs.correct(self.owner,self.scope,version.document_id,BytesIO(b'fictional fourth input'),
                              'text/plain','tax-fourth','Another correction')
        cycle_a='00000000-0000-4000-8000-000000000005'
        cycle_b='00000000-0000-4000-8000-000000000006'
        with self.assertRaises(psycopg.errors.CheckViolation),self.repo.transaction() as conn:
            conn.execute("""INSERT INTO ha_connected.tax_input_versions
                (snapshot_id,profile_id,business_id,tax_year,document_id,version_id,
                 previous_snapshot_id,actor,reason,idempotency_key,request_fingerprint)
                VALUES (%s,'orchard','business',2026,%s,%s,%s,'actor','cycle','cycle-a',%s),
                       (%s,'orchard','business',2026,%s,%s,%s,'actor','cycle','cycle-b',%s)""",
                (cycle_a,version.document_id,third.version_id,cycle_b,'e'*64,
                 cycle_b,version.document_id,fourth.version_id,cycle_a,'f'*64))
        self.repo.migrate()
        with self.repo.transaction() as conn:
            self.assertEqual(conn.execute('SELECT count(*) FROM ha_connected.tax_input_versions').fetchone()[0],2)
            conn.execute("INSERT INTO ha_connected.grants VALUES ('orchard-owner','orchard','business',2026,'save_tax')")
        self.repo.migrate()
        self.assertTrue(any('save_tax' in grant.actions for grant in self.repo.grants_for(self.owner.subject)))

    def test_tax_input_service_saves_reopens_and_rejects_stale_or_unauthorized_edits(self):
        from ha.connected.tax_inputs import TaxInputs
        from ha.connected.documents import Documents, MemoryObjects
        objects = MemoryObjects()
        documents = Documents(self.repo,objects,lambda data,mime: True)
        service = TaxInputs(self.repo,documents)
        value = {'year':'2026','profile':{'firstName':'Fictional'},'forms':[], 'active':0,'stateAnswers':{}}
        request={'input':value,'expected_snapshot_id':None,'reason':'','idempotency_key':'tax-save-1'}
        with self.assertRaises(PermissionError): service.save(self.owner,self.scope,request)
        self.assertEqual(objects.data,{})
        with self.repo.transaction() as conn:
            conn.execute("INSERT INTO ha_connected.grants VALUES ('orchard-owner','orchard','business',2026,'save_tax')")
        original=service.save(self.owner,self.scope,request)
        self.assertEqual(service.save(self.owner,self.scope,request),original)
        self.assertEqual(service.save(self.owner,self.scope,{**request,'input':dict(reversed(list(value.items())))}),original)
        fresh=TaxInputs(self.repo,documents)
        self.assertEqual(fresh.open(self.owner,self.scope)['input'],value)
        changed={**value,'profile':{'firstName':'Fictional correction'}}
        correction={'input':changed,'expected_snapshot_id':original['snapshot_id'],
                    'reason':'Corrected fictional name','idempotency_key':'tax-save-2'}
        current=service.save(self.owner,self.scope,correction)
        self.assertEqual(fresh.open(self.owner,self.scope)['input'],changed)
        self.assertEqual(fresh.open(self.owner,self.scope,original['snapshot_id'])['input'],value)
        self.assertEqual(len(service.history(self.owner,self.scope)),2)
        with self.assertRaises(ValueError): service.save(self.owner,self.scope,{**correction,'idempotency_key':'stale-tab'})
        with self.assertRaises(ValueError): service.save(self.owner,self.scope,{**request,'input':changed})
        with self.assertRaises(ValueError): service.save(self.owner,self.scope,{**correction,'actor':'forged'})
        with self.assertRaises(PermissionError): service.open(self.owner,Scope('cedar','cedar-business',2026))
        with self.repo.transaction() as conn:
            conn.execute("DELETE FROM ha_connected.grants WHERE action='save_tax'")
        with self.assertRaises(PermissionError): service.save(self.owner,self.scope,correction)
        self.assertEqual(service.open(self.owner,self.scope)['snapshot']['snapshot_id'],current['snapshot_id'])
        version=self.repo.get_version(self.scope,current['document_id'],current['version_id'])
        objects.data[version.object_key]=b'corrupt'
        with self.assertRaises(ValueError): service.open(self.owner,self.scope)

    def test_tax_inputs_encrypted_concurrent_and_failed_saves_preserve_active_version(self):
        from concurrent.futures import ThreadPoolExecutor
        from tempfile import TemporaryDirectory
        from unittest.mock import patch
        from ha.connected.tax_inputs import TaxInputs
        from ha.connected.documents import Documents
        from ha.connected.encrypted_objects import EncryptedLocalObjects
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        folder=TemporaryDirectory(); self.addCleanup(folder.cleanup)
        objects=EncryptedLocalObjects(folder.name,lambda: key)
        key=AESGCM.generate_key(bit_length=256)
        docs=Documents(self.repo,objects,lambda data,mime: False)
        service=TaxInputs(self.repo,docs)
        with self.repo.transaction() as conn:
            conn.execute("INSERT INTO ha_connected.grants VALUES ('orchard-owner','orchard','business',2026,'save_tax')")
        value={'year':'2026','profile':{'firstName':'SecretFictionalInput'},'forms':[],'active':0,'stateAnswers':{}}
        request={'input':value,'expected_snapshot_id':None,'reason':'','idempotency_key':'encrypted-tax-1'}
        with self.assertRaises(ValueError): service.save(self.owner,self.scope,request)
        self.assertEqual(list(Path(folder.name).iterdir()),[])
        self.assertEqual(service.history(self.owner,self.scope),[])
        docs.scanner=lambda data,mime: True
        original=service.save(self.owner,self.scope,request)
        self.assertTrue(all(b'SecretFictionalInput' not in p.read_bytes() for p in Path(folder.name).iterdir()))
        correction={'input':value,'expected_snapshot_id':original['snapshot_id'],'reason':'Correction','idempotency_key':'failure-tax'}
        with patch.object(objects,'put',side_effect=OSError('storage unavailable')):
            with self.assertRaises(OSError): service.save(self.owner,self.scope,correction)
        self.assertEqual(service.open(self.owner,self.scope)['snapshot'],original)
        with self.repo.transaction() as conn:
            self.assertEqual(conn.execute('SELECT count(*) FROM ha_connected.document_versions').fetchone()[0],1)
        with patch.object(self.repo,'add_version',side_effect=RuntimeError('metadata failure')):
            with self.assertRaises(RuntimeError): service.save(self.owner,self.scope,{**correction,'idempotency_key':'metadata-failure'})
        self.assertEqual(service.open(self.owner,self.scope)['snapshot'],original)
        with self.repo.transaction() as conn:
            self.assertEqual(conn.execute('SELECT count(*) FROM ha_connected.document_versions').fetchone()[0],1)
        # A private encrypted orphan may remain; it has no active metadata reference.
        def save(index):
            try:
                return service.save(self.owner,self.scope,{**correction,'idempotency_key':'parallel-'+str(index)})
            except ValueError:
                return None
        with ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(save,range(2)))
        self.assertEqual(sum(r is not None for r in results),1)
        self.assertEqual(len(service.history(self.owner,self.scope)),2)
        self.assertEqual(service.open(self.owner,self.scope,original['snapshot_id'])['input'],value)

    def test_tax_input_http_uses_session_csrf_scope_and_explicit_edit_permission(self):
        import threading
        import http.client
        from ha.connected.api import create_server
        from ha.connected.auth import Sessions
        from ha.connected.documents import Documents,MemoryObjects
        sessions=Sessions(); cookie,csrf=sessions.open(self.owner)
        server=create_server(('127.0.0.1',0),sessions,self.ledger,
                             Documents(self.repo,MemoryObjects(),lambda data,mime:True),None,'https://ha.example')
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
        path='/api/connected/tax/inputs'; query='?profile=orchard&business=business&year=2026'
        value={'year':'2026','profile':{'firstName':'Fictional'},'forms':[],'active':0,'stateAnswers':{}}
        body={'scope':{'profile':'orchard','business':'business','year':2026},
              'save':{'input':value,'expected_snapshot_id':None,'reason':'','idempotency_key':'http-tax-1'}}
        self.assertEqual(request('POST',path,body,signed=False)[0],401)
        self.assertEqual(request('POST',path,body,verified=False)[0],403)
        self.assertEqual(request('POST',path,body)[0],404)
        self.assertFalse(request('GET',path+query)[1]['can_save'])
        with self.repo.transaction() as conn:
            conn.execute("INSERT INTO ha_connected.grants VALUES ('orchard-owner','orchard','business',2026,'save_tax')")
        saved=request('POST',path,body)
        self.assertEqual(saved[0],201)
        self.assertEqual(request('POST',path,body),saved)
        self.assertTrue(request('GET',path+query)[1]['can_save'])
        opened=request('GET','/api/connected/tax/input'+query)
        self.assertEqual(opened[0],200);self.assertEqual(opened[1]['input'],value)
        self.assertEqual(len(request('GET',path+query)[1]['history']),1)
        self.assertEqual(request('GET','/api/connected/tax/input?profile=cedar&business=cedar-business&year=2026')[0],404)
        self.assertEqual(request('GET','/api/connected/tax/input'+query+'&snapshot=00000000-0000-4000-8000-000000000000')[0],404)
        wrongyear={**body,'scope':{**body['scope'],'year':2025}}
        self.assertEqual(request('POST',path,wrongyear)[0],404)
        bad={**body,'save':{**body['save'],'input':{**value,'year':'2025'}}}
        self.assertEqual(request('POST',path,bad)[0],400)
        oversized={**body,'save':{**body['save'],'input':{'huge':'x'*524288}}}
        self.assertEqual(request('POST',path,oversized)[0],400)
        with self.repo.transaction() as conn:
            conn.execute("DELETE FROM ha_connected.grants WHERE action='save_tax'")
        self.assertFalse(request('GET',path+query)[1]['can_save'])
        self.assertEqual(request('POST',path,body)[0],404)
        sessions.logout(cookie)
        self.assertEqual(request('GET',path+query)[0],401)

    def test_case_discovery_is_one_joined_read_query_and_revocation_is_fresh(self):
        from unittest.mock import patch
        from ha.connected.access import permitted_cases
        with self.repo.transaction() as conn:
            conn.execute("INSERT INTO ha_connected.businesses VALUES ('second-business','orchard')")
            for subject,profile,business,year,action in [('orchard-owner','orchard','business',2025,'read'),
                ('orchard-owner','orchard','second-business',2026,'read'),
                ('orchard-owner','cedar','cedar-business',2026,'upload'),
                ('cedar-owner','cedar','cedar-business',2026,'read')]:
                conn.execute('INSERT INTO ha_connected.grants VALUES (%s,%s,%s,%s,%s)',(subject,profile,business,year,action))
        with patch.object(self.repo,'transaction',wraps=self.repo.transaction) as transactions,patch.object(self.repo,'profile_for_business',side_effect=AssertionError('N+1 lookup')),patch.object(self.repo,'grants_for',side_effect=AssertionError('Unfiltered grants')):
            cases=permitted_cases(self.owner,self.repo)
        self.assertEqual(transactions.call_count,1)
        self.assertEqual(cases,[{'profile':'orchard','business':'business','year':2025},
            {'profile':'orchard','business':'business','year':2026},
            {'profile':'orchard','business':'second-business','year':2026}])
        with self.repo.transaction() as conn:
            conn.execute("DELETE FROM ha_connected.grants WHERE subject='orchard-owner' AND action='read'")
        self.assertEqual(permitted_cases(self.owner,self.repo),[])
        expired=Principal('orchard-owner',datetime.now(timezone.utc)-timedelta(seconds=1),True)
        with patch.object(self.repo,'transaction',side_effect=AssertionError('No expired query')),self.assertRaises(PermissionError):
            permitted_cases(expired,self.repo)
