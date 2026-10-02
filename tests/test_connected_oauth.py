import unittest
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timedelta, timezone
from ha.connected.oauth import CognitoLogin
from ha.connected.domain import Principal


class Provider:
    def describe_user_pool(self, **kwargs):
        return {'UserPool': {'MfaConfiguration': 'ON'}}
    def get_user_pool_mfa_config(self, **kwargs):
        return {'SoftwareTokenMfaConfiguration': {'Enabled': True}, 'MfaConfiguration': 'ON'}
    def describe_user_pool_client(self, **kwargs):
        return {'UserPoolClient': {'SupportedIdentityProviders': ['COGNITO'], 'AllowedOAuthFlows': ['code'], 'CallbackURLs': ['https://ha.example/auth/callback']}}


class Verifier:
    def verify(self, token, nonce, required_mfa):
        if token != 'verified-test-id-token' or not nonce or not required_mfa:
            raise PermissionError()
        return Principal('orchard-owner', datetime.now(timezone.utc)+timedelta(minutes=5), True)


class OAuthTests(unittest.TestCase):
    def setUp(self):
        self.exchanges = []
        def exchange(url, fields):
            self.exchanges.append((url, fields))
            return {'id_token': 'verified-test-id-token'}
        self.provider = Provider()
        self.login = CognitoLogin(self.provider, 'us-east-2_test', 'client', 'https://ha.auth.us-east-2.amazoncognito.com',
                                  'https://ha.example/auth/callback', Verifier(), exchange)

    def test_authorization_has_pkce_nonce_and_state_and_consumes_once(self):
        url, browser_cookie = self.login.begin()
        query = parse_qs(urlparse(url).query)
        self.assertEqual(query['code_challenge_method'], ['S256'])
        self.assertIn('nonce', query)
        principal = self.login.complete('code', query['state'][0], browser_cookie)
        self.assertEqual(principal.subject, 'orchard-owner')
        self.assertIn('code_verifier', self.exchanges[0][1])
        with self.assertRaises(PermissionError):
            self.login.complete('code', query['state'][0], browser_cookie)

    def test_bad_state_or_browser_cookie_does_not_exchange(self):
        url, cookie = self.login.begin()
        state = parse_qs(urlparse(url).query)['state'][0]
        with self.assertRaises(PermissionError):
            self.login.complete('code', state, 'wrong-browser')
        self.assertEqual(self.exchanges, [])

    def test_optional_mfa_pool_cannot_login(self):
        self.provider.describe_user_pool = lambda **kwargs: {'UserPool': {'MfaConfiguration': 'OPTIONAL'}}
        with self.assertRaises(PermissionError):
            self.login.begin()

    def test_federated_bypass_client_cannot_login(self):
        self.provider.describe_user_pool_client = lambda **kwargs: {'UserPoolClient': {'SupportedIdentityProviders': ['COGNITO', 'Google'], 'AllowedOAuthFlows': ['code']}}
        with self.assertRaises(PermissionError):
            self.login.begin()
