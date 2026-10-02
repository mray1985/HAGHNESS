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
