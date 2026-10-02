import unittest
from datetime import datetime, timedelta, timezone
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from ha.connected.auth import TokenVerifier, Sessions


class TokenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    def setUp(self):
        self.issuer = 'https://cognito-idp.us-east-2.amazonaws.com/test-pool'
        self.verifier = TokenVerifier(self.issuer, 'client', lambda token: self.key.public_key())
        now = int(datetime.now(timezone.utc).timestamp())
        self.claims = dict(iss=self.issuer, sub='orchard-owner', aud='client', token_use='id', iat=now, exp=now+300, nonce='expected')

    def token(self, **changes):
        return jwt.encode({**self.claims, **changes}, self.key, algorithm='RS256')

    def test_valid_signature_nonce_and_required_mfa_pool(self):
        principal = self.verifier.verify(self.token(), 'expected', True)
        self.assertEqual(principal.subject, 'orchard-owner')
        self.assertTrue(principal.mfa_verified)

    def test_bad_issuer_audience_expiry_nonce_and_non_mfa_denied(self):
        for changes in ({'iss': 'https://other'}, {'aud': 'other'}, {'exp': 1}, {'nonce': 'wrong'}, {'token_use': 'access'}):
            with self.assertRaises(PermissionError):
                self.verifier.verify(self.token(**changes), 'expected', True)
        with self.assertRaises(PermissionError):
            self.verifier.verify(self.token(), 'expected', False)
        with self.assertRaises(PermissionError):
            self.verifier.verify(jwt.encode(self.claims, 'wrong-key-for-rejection-test-only-123456789', algorithm='HS256'), 'expected', True)

    def test_missing_nonce_and_subject_denied(self):
        for key in ('nonce', 'sub', 'exp'):
            claims = {k:v for k,v in self.claims.items() if k != key}
            with self.assertRaises(PermissionError):
                self.verifier.verify(jwt.encode(claims, self.key, algorithm='RS256'), 'expected', True)

    def test_session_reuse_csrf_expiry_and_logout(self):
        sessions = Sessions()
        principal = self.verifier.verify(self.token(), 'expected', True)
        cookie, csrf = sessions.open(principal)
        self.assertEqual(sessions.require(cookie), principal)
        self.assertEqual(sessions.require(cookie, csrf), principal)
        with self.assertRaises(PermissionError):
            sessions.require(cookie, 'wrong')
        sessions.logout(cookie)
        with self.assertRaises(PermissionError):
            sessions.require(cookie)
        with self.assertRaises(PermissionError):
            sessions.open(principal.__class__(principal.subject, datetime.now(timezone.utc)-timedelta(seconds=1), True))
