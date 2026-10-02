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
