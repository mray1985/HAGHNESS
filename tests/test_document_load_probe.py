import base64
import threading
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs,urlsplit
from scripts.verify_document_load import verify_document_load


class DocumentLoadProbeTests(unittest.TestCase):
    def test_load_option_requires_real_connected_session(self):
        from scripts.verify_keycloak_runtime import main
        with patch('sys.argv',['probe','--distribution','fictional','--report','fictional','--document-load']):
            with self.assertRaisesRegex(ValueError,'Document load requires connected session'):main()

    def api(self,corrupt=False):
        saved={};lock=threading.Lock()
        def call(method,path,payload=None,**kwargs):
            with lock:
                if method=='POST':
                    key=payload['idempotency_key'];saved[key]=payload['data']
                    return {'document_id':key,'version_id':key,'sha256':'fictional'}
                query=parse_qs(urlsplit(path).query);key=query['document'][0]
                return {'data':base64.b64encode(b'wrong').decode() if corrupt else saved[key]}
        return call

    def test_four_distinct_exact_reads_without_identifiers_in_report(self):
        report=verify_document_load(self.api(),{'profile':'fictional','business':'fictional','year':2026})
        self.assertEqual(report['documents'],4);self.assertEqual(report['concurrency'],4)
        self.assertEqual(report['bytes_per_document'],2*1024*1024)
        self.assertTrue(report['exact_reads']);self.assertFalse(report['hosted_capacity_verified'])
        self.assertGreater(report['elapsed_seconds'],0)

    def test_changed_readback_fails_instead_of_reporting_success(self):
        with self.assertRaisesRegex(ValueError,'Concurrent document readback mismatch'):
            verify_document_load(self.api(corrupt=True),{'profile':'fictional','business':'fictional','year':2026})
