"""Server-controlled Cognito authorization-code/PKCE exchange.

Pending handshakes are single-process, short-lived and browser-bound. Deployment
must use one worker or replace this store with a shared transactional store.
"""
import base64
import hashlib
import json
import re
import secrets
import time
from threading import RLock
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def exchange_token(url, fields):
    request = Request(url, data=urlencode(fields).encode(), headers={'Content-Type': 'application/x-www-form-urlencoded'}, method='POST')
    with urlopen(request, timeout=15) as response:
        payload = response.read(1024 * 1024 + 1)
    if len(payload) > 1024 * 1024:
        raise PermissionError('Authentication required')
    return json.loads(payload)


class CognitoLogin:
    def __init__(self, provider, pool_id, client_id, domain, redirect_uri, verifier, exchange=exchange_token):
        if not re.fullmatch(r'https://[a-z0-9-]+\.auth\.[a-z0-9-]+\.amazoncognito\.com', domain):
            raise ValueError('Verified Cognito domain required')
        if not redirect_uri.startswith('https://'):
            raise ValueError('HTTPS callback required')
        self.provider, self.pool, self.client = provider, pool_id, client_id
        self.domain, self.redirect, self.verifier, self.exchange = domain, redirect_uri, verifier, exchange
        self.pending, self.lock = {}, RLock()

    def _required_mfa(self):
        pool = self.provider.describe_user_pool(UserPoolId=self.pool)['UserPool']
        mfa = self.provider.get_user_pool_mfa_config(UserPoolId=self.pool)
        client = self.provider.describe_user_pool_client(UserPoolId=self.pool, ClientId=self.client)['UserPoolClient']
        if (pool.get('MfaConfiguration') != 'ON' or mfa.get('MfaConfiguration') != 'ON'
                or mfa.get('SoftwareTokenMfaConfiguration', {}).get('Enabled') is not True
                or client.get('SupportedIdentityProviders') != ['COGNITO']
                or client.get('AllowedOAuthFlows') != ['code']
                or self.redirect not in client.get('CallbackURLs', [])):
            raise PermissionError('Required MFA configuration is unavailable')
        return True

    def begin(self):
        self._required_mfa()
        state, cookie, nonce, verifier = [secrets.token_urlsafe(32) for _ in range(4)]
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
        with self.lock:
            self.pending = {k:v for k,v in self.pending.items() if v['expires'] > time.monotonic()}
            if len(self.pending) >= 1000:
                raise PermissionError('Try signing in later')
            self.pending[state] = dict(cookie_hash=hashlib.sha256(cookie.encode()).digest(), nonce=nonce, verifier=verifier, expires=time.monotonic()+600)
        query = urlencode(dict(response_type='code', client_id=self.client, redirect_uri=self.redirect,
                               scope='openid', state=state, nonce=nonce, code_challenge=challenge,
                               code_challenge_method='S256', prompt='login'))
        return self.domain + '/oauth2/authorize?' + query, cookie

    def complete(self, code, state, browser_cookie):
        if not all(isinstance(v, str) and 0 < len(v) <= 4096 for v in (code, state, browser_cookie)):
            raise PermissionError('Authentication required')
        with self.lock:
            pending = self.pending.pop(state, None)
        if (pending is None or pending['expires'] <= time.monotonic()
                or not secrets.compare_digest(pending['cookie_hash'], hashlib.sha256(browser_cookie.encode()).digest())):
            raise PermissionError('Authentication required')
        self._required_mfa()
        response = self.exchange(self.domain + '/oauth2/token', dict(grant_type='authorization_code', client_id=self.client,
                                 code=code, code_verifier=pending['verifier'], redirect_uri=self.redirect))
        return self.verifier.verify(response['id_token'], pending['nonce'], True)
