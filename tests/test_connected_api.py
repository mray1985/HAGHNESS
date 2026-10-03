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

    def test_connected_tax_handoff_requires_same_session_scope_and_csrf(self):
        scope={'profile':'orchard','business':'business','year':2026}
        self.request('POST','/api/connected/events',{'scope':scope,'event':{'id':'sale','date':'2026-10-02','kind':'income','amount_minor':150000}})
        payload={'scope':scope,'scenario':{'tax_year':'2026','w2s':[{'box1':45000,'box2':5200}]}}
        path='/api/connected/return/estimate'
        self.assertEqual(self.request('POST',path,payload,signed=False)[0],401)
        self.assertEqual(self.request('POST',path,payload,csrf=False)[0],403)
        status,result=self.request('POST',path,payload)
        self.assertEqual(status,200)
        self.assertEqual(result['business_draft']['book_profit_minor'],150000)
        self.assertIsNone(result['refund'])
        self.assertEqual(self.request('POST',path,{**payload,'scope':{'profile':'cedar','business':'cedar-business','year':2026}})[0],404)

    def test_unconfigured_documents_cannot_return_fake_success(self):
        self.assertEqual(self.request('POST','/api/connected/documents',{'scope':{'profile':'orchard','business':'business','year':2026}})[0],503)
        self.assertEqual(self.request('POST','/api/connected/document/corrections',{})[0],503)

    def test_logout_revokes_session(self):
        self.assertEqual(self.request('POST','/api/auth/logout',{})[0],200)
        self.assertEqual(self.request('GET','/api/auth/me')[0],401)

    def test_malformed_event_returns_validation_error(self):
        self.assertEqual(self.request('POST','/api/connected/events',{'scope':{'profile':'orchard','business':'business','year':2026}})[0],400)

    def test_tax_preview_runs_on_connected_service_without_unlocking_records(self):
        status,result=self.request('POST','/api/return/estimate',
            {'tax_year':'2025','w2s':[{'box1':45000,'box2':5200}]},signed=False,csrf=False)
        self.assertEqual(status,200)
        self.assertEqual(result['refund'],1928.5)
        self.assertFalse(result['may_prepare_return'])
        self.assertEqual(self.request('GET','/api/connected/draft?profile=orchard&business=business&year=2026',signed=False)[0],401)

    def test_tax_page_assets_are_available_and_unlisted_files_are_denied(self):
        for path,mime in (('/tax','text/html'),('/return.js','text/javascript'),('/return.css','text/css')):
            conn=HTTPConnection(*self.server.server_address,timeout=3)
            conn.request('GET',path)
            response=conn.getresponse();body=response.read()
            self.assertEqual(response.status,200)
            self.assertIn(mime,response.getheader('Content-Type'))
            self.assertIn('no-store',response.getheader('Cache-Control'))
            if path=='/tax':
                self.assertIn(b'HATax',body)
                self.assertIn(b'href="/connected.html"',body)
            conn.close()
        self.assertEqual(self.request('GET','/../ha/rules/federal.json',signed=False)[0],401)

    def test_tax_saving_unconfigured_does_not_offer_public_fallback(self):
        for path in ('/api/connected/tax/inputs','/api/connected/tax/input'):
            self.assertEqual(self.request('GET',path+'?profile=orchard&business=business&year=2026')[0],503)

    def test_case_list_uses_only_current_read_grants(self):
        path='/api/connected/cases'
        self.assertEqual(self.request('GET',path,signed=False)[0],401)
        self.repo.grants.append(Grant('orchard-owner',Scope('cedar','cedar-business',2026),frozenset({'upload'})))
        self.repo.grants.append(Grant('orchard-owner',self.scope,frozenset({'read'})))
        self.repo.grants.append(Grant('cedar-owner',Scope('cedar','cedar-business',2026),frozenset({'read'})))
        self.repo.grants.append(Grant('orchard-owner',Scope('orchard','cedar-business',2026),frozenset({'read'})))
        status,result=self.request('GET',path)
        self.assertEqual(status,200)
        self.assertEqual(result,{'cases':[{'profile':'orchard','business':'business','year':2026}]})
        self.repo.grants=[]
        self.assertEqual(self.request('GET',path)[1],{'cases':[]})
        self.sessions.logout(self.cookie)
        self.assertEqual(self.request('GET',path)[0],401)

    def test_transport_disconnect_ends_response_without_retry(self):
        import ssl
        from types import SimpleNamespace
        from unittest.mock import Mock
        handler=self.server.RequestHandlerClass
        for error in (BrokenPipeError(),ConnectionResetError(),ssl.SSLEOFError()):
            fake=SimpleNamespace(path='/api/health',respond=Mock(side_effect=error),close_connection=False)
            handler.dispatch(fake,False)
            self.assertEqual(fake.respond.call_count,1)
            self.assertTrue(fake.close_connection)
    def test_json_error_response_disconnect_is_quiet(self):
        import ssl
        from types import SimpleNamespace
        from unittest.mock import Mock
        handler=self.server.RequestHandlerClass
        fake=SimpleNamespace(send_response=Mock(),send_header=Mock(),end_headers=Mock(),
            wfile=SimpleNamespace(write=Mock(side_effect=ssl.SSLEOFError())),close_connection=False)
        handler.respond(fake,503,{'error':'Service unavailable'})
        self.assertTrue(fake.close_connection)
        self.assertEqual(fake.wfile.write.call_count,1)
