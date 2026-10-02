import base64
import threading
import unittest
from datetime import datetime,timedelta,timezone
from ha.connected.api import create_server
from ha.connected.auth import Sessions
from ha.connected.domain import Principal,Scope,Grant
from ha.connected.documents import Documents,MemoryDocumentRepository,MemoryObjects
from tests.test_connected_access import Repository
from tests import test_connected_api as api_tests

class CorrectionApiTests(unittest.TestCase):
    request=api_tests.ApiTests.request
    tearDown=api_tests.ApiTests.tearDown
    def setUp(self):
        self.permissions=Repository();self.scope=Scope('orchard','business',2026)
        self.permissions.grants[0]=Grant('orchard-owner',self.scope,frozenset({'read','upload','correct'}))
        self.repo=MemoryDocumentRepository(self.permissions)
        self.documents=Documents(self.repo,MemoryObjects(),lambda data,mime:True)
        self.sessions=Sessions()
        self.cookie,self.csrf=self.sessions.open(Principal('orchard-owner',datetime.now(timezone.utc)+timedelta(minutes=5),True))
        self.server=create_server(('127.0.0.1',0),self.sessions,None,self.documents,None,'https://ha.example')
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
    def body(self,data,key,**extra):
        return {'scope':{'profile':'orchard','business':'business','year':2026},'mime':'text/plain','data':base64.b64encode(data).decode(),'idempotency_key':key,**extra}
    def test_corrected_bytes_original_and_retry_are_preserved(self):
        status,original=self.request('POST','/api/connected/documents',self.body(b'original','first'))
        self.assertEqual(status,201)
        body=self.body(b'corrected','second',document=original['document_id'],reason='Correct amount')
        status,corrected=self.request('POST','/api/connected/document/corrections',body)
        self.assertEqual(status,201)
        self.assertEqual(corrected['previous_version_id'],original['version_id'])
        self.assertEqual(self.request('POST','/api/connected/document/corrections',body)[1],corrected)
        for version,expected in ((original,b'original'),(corrected,b'corrected')):
            path='/api/connected/document?profile=orchard&business=business&year=2026&document='+original['document_id']+'&version='+version['version_id']
            status,result=self.request('GET',path);self.assertEqual(status,200)
            self.assertEqual(base64.b64decode(result['data']),expected)
        self.assertEqual(len(self.repo.versions),2)
    def test_authentication_csrf_reason_and_other_profile_are_checked(self):
        _,original=self.request('POST','/api/connected/documents',self.body(b'original','first'))
        body=self.body(b'corrected','second',document=original['document_id'],reason='Updated')
        self.assertEqual(self.request('POST','/api/connected/document/corrections',body,signed=False)[0],401)
        self.assertEqual(self.request('POST','/api/connected/document/corrections',body,csrf=False)[0],403)
        self.assertEqual(self.request('POST','/api/connected/document/corrections',{**body,'reason':''})[0],400)
        body['scope']={'profile':'cedar','business':'cedar-business','year':2026}
        self.assertEqual(self.request('POST','/api/connected/document/corrections',body)[0],404)
        self.assertEqual(len(self.repo.versions),1)
        body['scope']={'profile':'orchard','business':'business','year':2026}
        self.permissions.grants[0]=Grant('orchard-owner',self.scope,frozenset({'read'}))
        self.assertEqual(self.request('POST','/api/connected/document/corrections',body)[0],404)
        self.assertEqual(len(self.repo.versions),1)

    def test_correction_only_permission_cannot_create_original_with_empty_id(self):
        self.permissions.grants[0]=Grant('orchard-owner',self.scope,frozenset({'correct'}))
        for document in ('',None,'   ',False,[]):
            with self.subTest(document=document):
                body=self.body(b'new original','attempt-'+str(document),document=document,reason='Updated')
                self.assertEqual(self.request('POST','/api/connected/document/corrections',body)[0],400)
        self.assertEqual(len(self.repo.versions),0)
