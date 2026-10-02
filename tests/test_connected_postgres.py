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
        self.ledger.post_event(self.owner,self.scope,dict(id='cash-review',date='2026-10-02',kind='income',method='cash',amount_minor=1000))
        with self.assertRaises(ValueError):
            service.submit(self.owner,self.scope,dict(event_id='cash-review',decision='accepted',reason='Review',idempotency_key='cash-no-explanation'))
        with self.repo.transaction() as conn:
            conn.execute("DELETE FROM ha_connected.grants WHERE action='review_support'")
        with self.assertRaises(PermissionError):service.submit(self.owner,self.scope,request)
        self.assertFalse(self.ledger.project(self.owner,self.scope,'year')['support_review_complete'])
