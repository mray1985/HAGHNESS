import unittest
from unittest.mock import patch
from scripts.verify_keycloak_mfa import totp,form,fixture_user

class MFAProbeTests(unittest.TestCase):
    def test_totp_matches_rfc6238_sha1_vector_at_six_digits(self):
        with patch('scripts.verify_keycloak_mfa.time.time',return_value=59):
            self.assertEqual(totp('12345678901234567890'),'287082')

    def test_credentials_cannot_be_posted_to_foreign_form_action(self):
        for target in ('https://unrelated.example/realms/ha/login-actions/authenticate',
                       'http://identity.example/realms/ha/login-actions/authenticate',
                       'https://identity.example/unrelated'):
            with self.subTest(target=target),self.assertRaises(ValueError):
                form('<form action="'+target+'"><input name="password"></form>',
                    'password','https://identity.example')

    def test_ambiguous_or_missing_challenge_is_rejected(self):
        challenge='<form action="https://identity.example/realms/ha/login-actions/authenticate"><input name="otp"></form>'
        for page in ('',challenge+challenge):
            with self.subTest(page=page),self.assertRaises(ValueError):
                form(page,'otp','https://identity.example')

    def test_fixture_credentials_are_fresh_per_run(self):
        first,password,secret=fixture_user()
        second,other_password,other_secret=fixture_user()
        self.assertNotEqual(password,other_password)
        self.assertNotEqual(secret,other_secret)
        self.assertEqual(first['credentials'][0]['value'],password)

    def test_enrollment_fixture_has_no_preinstalled_otp_or_reused_password(self):
        from scripts.verify_keycloak_mfa import fixture_enrollment_user
        first,password=fixture_enrollment_user();second,other=fixture_enrollment_user()
        self.assertEqual(first['requiredActions'],['CONFIGURE_TOTP'])
        self.assertEqual([c['type'] for c in first['credentials']],['password'])
        self.assertNotEqual(password,other)
        self.assertNotEqual(first['username'],fixture_user()[0]['username'])

    def test_enrollment_redirects_are_bounded_and_identity_owned(self):
        from scripts.verify_keycloak_mfa import read_enrollment_page
        from urllib.error import HTTPError
        from io import BytesIO
        origin='https://identity.example'
        class Opener:
            def __init__(self,target):self.target=target;self.calls=0
            def open(self,request,timeout):
                self.calls+=1
                if self.calls==1:raise HTTPError(origin,302,'Found',{'Location':self.target},BytesIO())
                return BytesIO(b'fictional setup')
        own=Opener(origin+'/realms/ha/login-actions/required-action')
        self.assertEqual(read_enrollment_page(own,origin,origin),'fictional setup')
        for target in ['https://foreign.example/realms/ha/login-actions/setup',origin+'/admin/',
                       'https://ha.example/api/auth/callback?code=fictional']:
            with self.subTest(target=target),self.assertRaises(HTTPError) as caught:
                read_enrollment_page(Opener(target),origin,origin)
            caught.exception.close()
        class Loop:
            def open(self,request,timeout):raise HTTPError(origin,302,'Found',{'Location':origin+'/realms/ha/login-actions/setup'},BytesIO())
        with self.assertRaises(ValueError):read_enrollment_page(Loop(),origin,origin)

    def test_rendered_enrollment_fixture_has_separate_account_and_password(self):
        from scripts.verify_keycloak_mfa import fixture_enrollment_user
        protocol,password=fixture_enrollment_user()
        rendered,other=fixture_enrollment_user('ha-fictional-rendered-enrollment')
        self.assertNotEqual(protocol['username'],rendered['username']);self.assertNotEqual(password,other)
        self.assertNotEqual(protocol['email'],rendered['email'])
        self.assertEqual([c['type'] for c in rendered['credentials']],['password'])

    def test_rendered_failure_parser_keeps_only_fixed_labels(self):
        from scripts.verify_keycloak_runtime import rendered_failure
        import json
        value={'stage':'fresh-callback','kind':'TimeoutError','error':'rendered enrollment verification failed',
               'fresh_code_submitted_matches':True,'secret':'fictional-secret'}
        result=rendered_failure('runtime warning\n'+json.dumps(value))
        self.assertIn('fresh-callback',result);self.assertIn('fresh code matches=True',result)
        self.assertNotIn('fictional-secret',result)
        self.assertEqual(rendered_failure('x'*65537),'unknown (Error)')
        self.assertEqual(rendered_failure(json.dumps({**value,'stage':'fictional-secret'})),'unknown (Error)')

    def test_automatic_enrollment_fixture_has_no_assigned_setup_action(self):
        from scripts.verify_keycloak_mfa import fixture_enrollment_user
        user,password=fixture_enrollment_user(setup_required=False)
        self.assertEqual(user['requiredActions'],[])
        self.assertEqual([c['type'] for c in user['credentials']],['password'])
        self.assertEqual(user['credentials'][0]['value'],password)
