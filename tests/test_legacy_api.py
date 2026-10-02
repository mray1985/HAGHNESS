import json
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
import threading
import unittest
from ha.server import Handler

class LegacyValidationTests(unittest.TestCase):
    def test_w2_endpoint_returns_scenario_without_identity(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            conn=HTTPConnection(*server.server_address,timeout=5)
            conn.request('POST','/api/return/estimate',json.dumps({'tax_year':'2025','w2s':[{'box1':45000,'box2':5200}],'profile':{'name':'Fictional Person','ssn':'000-00-0000'}}),{'Content-Type':'application/json'})
            response=conn.getresponse();raw=response.read().decode();conn.close()
            self.assertEqual(response.status,200)
            self.assertEqual(json.loads(raw)['refund'],1928.50)
            self.assertNotIn('Fictional Person',raw);self.assertNotIn('000-00-0000',raw)
        finally:
            server.shutdown();server.server_close();thread.join()

    def test_malformed_inputs_return_json_errors_without_disconnect(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            cases=[('/api/calculate',value) for value in ([],None,{'agi':'abc'},{'agi':'NaN'},{'agi':[1]})]
            cases.extend([('/api/chat',{'question':123}),('/api/chat',{'question':'hello','context':[]})])
            for path,payload in cases:
                with self.subTest(payload=payload):
                    conn=HTTPConnection(*server.server_address,timeout=5)
                    conn.request('POST',path,json.dumps(payload),{'Content-Type':'application/json'})
                    response=conn.getresponse();body=json.loads(response.read());conn.close()
                    self.assertEqual(response.status,400);self.assertIn('error',body)
        finally:
            server.shutdown();server.server_close();thread.join()
