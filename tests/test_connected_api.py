import json
import threading
import unittest
from datetime import datetime, timedelta, timezone
from http.client import HTTPConnection
from ha.connected.api import create_server
from ha.connected.auth import Sessions
from ha.connected.domain import Principal, Scope, Grant
from ha.connected.ledger import Ledger
from tests.test_connected_access import Repository


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.repo = Repository()
        self.scope = Scope('orchard','business',2026)
        self.repo.grants[0] = Grant('orchard-owner',self.scope,frozenset({'read','post','correct'}))
        self.sessions = Sessions()
        self.cookie,self.csrf = self.sessions.open(Principal('orchard-owner',datetime.now(timezone.utc)+timedelta(minutes=5),True))
        self.server = create_server(('127.0.0.1',0),self.sessions,Ledger(self.repo),None,None,'https://ha.example')
        self.thread = threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def request(self, method, path, payload=None, signed=True, csrf=True):
        conn = HTTPConnection(*self.server.server_address,timeout=3)
        headers = {'Origin':'https://ha.example'}
        if signed:
            headers['Cookie'] = '__Host-ha_session='+self.cookie
        if csrf:
            headers['X-HA-CSRF'] = self.csrf
        body = json.dumps(payload).encode() if payload is not None else None
        if body:
            headers['Content-Type'] = 'application/json'
        conn.request(method,path,body,headers)
        response = conn.getresponse()
        status, data = response.status, json.loads(response.read())
        conn.close()
        return status,data

    def test_authentication_required_and_scope_checked(self):
        self.assertEqual(self.request('GET','/api/connected/draft?profile=orchard&business=business&year=2026',signed=False)[0],401)
        self.assertEqual(self.request('GET','/api/connected/draft?profile=cedar&business=cedar-business&year=2026')[0],404)

    def test_post_requires_csrf_and_updates_running_draft(self):
        payload = {'scope':{'profile':'orchard','business':'business','year':2026},'event':{'id':'sale','date':'2026-10-02','kind':'income','amount_minor':150000}}
        self.assertEqual(self.request('POST','/api/connected/events',payload,csrf=False)[0],403)
        self.assertEqual(self.request('POST','/api/connected/events',payload)[0],201)
        status,result = self.request('GET','/api/connected/draft?profile=orchard&business=business&year=2026')
        self.assertEqual(status,200)
        self.assertEqual(result['book_profit_minor'],150000)
        self.assertFalse(result['may_prepare_return'])

    def test_unconfigured_documents_cannot_return_fake_success(self):
        self.assertEqual(self.request('POST','/api/connected/documents',{'scope':{'profile':'orchard','business':'business','year':2026}})[0],503)

    def test_logout_revokes_session(self):
        self.assertEqual(self.request('POST','/api/auth/logout',{})[0],200)
        self.assertEqual(self.request('GET','/api/auth/me')[0],401)

    def test_malformed_event_returns_validation_error(self):
        self.assertEqual(self.request('POST','/api/connected/events',{'scope':{'profile':'orchard','business':'business','year':2026}})[0],400)
