from io import BytesIO,StringIO
from contextlib import redirect_stdout
import json
import unittest
from unittest.mock import patch
from scripts.check_digitalocean_account import check_account,main,NoRedirect

class AccountCheckTests(unittest.TestCase):
    def response(self,account):
        result=BytesIO(json.dumps({'account':account}).encode());result.status=200;return result
    def test_fixed_https_get_and_minimal_output(self):
        calls=[]
        def open_request(request,timeout):
            calls.append((request.full_url,request.get_method(),timeout))
            self.assertEqual(request.get_header('Authorization'),'Bearer '+'x'*32)
            return self.response({'status':'active','email_verified':True,'email':'private@example.invalid','uuid':'private'})
        result=check_account('x'*32,open_request=open_request)
        self.assertTrue(result['account_prerequisite_passed']);self.assertFalse(result['deployment_verified'])
        self.assertEqual(calls,[('https://api.digitalocean.com/v2/account','GET',15)])
        self.assertNotIn('private',json.dumps(result))
    def test_warning_locked_or_unverified_do_not_pass(self):
        for status,verified in [('warning',True),('locked',True),('active',False)]:
            self.assertFalse(check_account('x'*32,open_request=lambda *a,**k:self.response({'status':status,'email_verified':verified}))['account_prerequisite_passed'])
    def test_redirect_and_invalid_token_reject_before_send(self):
        self.assertIsNone(NoRedirect().redirect_request(None,None,None,None,None,None))
        with self.assertRaises(ValueError):check_account('token\nsecret',open_request=lambda *a,**k:self.fail('Must not send'))
    def test_failure_output_never_echoes_credentials(self):
        output=StringIO()
        with patch.dict('os.environ',{'DIGITALOCEAN_ACCESS_TOKEN':'x'*32}),patch('scripts.check_digitalocean_account.check_account',side_effect=RuntimeError('private-token')),redirect_stdout(output):
            self.assertEqual(main(),2)
        self.assertNotIn('private-token',output.getvalue())
    def test_oversize_and_duplicate_account_fields_reject(self):
        for data in [b'x'*65537,b'{"account":{"status":"active","status":"locked","email_verified":true}}']:
            response=BytesIO(data);response.status=200
            with self.assertRaises(ValueError):check_account('x'*32,open_request=lambda *a,**k:response)
