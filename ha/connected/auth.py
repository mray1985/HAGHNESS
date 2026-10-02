"""Verified token boundary and opaque server-owned sessions.

Only a completed server OAuth exchange may call TokenVerifier. Required MFA
must come from a verified provider policy, never from browser request data.
"""
import hashlib
import secrets
from datetime import datetime, timezone
from threading import RLock
import jwt
from .domain import Principal


class TokenVerifier:
    def __init__(self, issuer, client_id, key_resolver):
        self.issuer, self.client_id, self.key_resolver = issuer, client_id, key_resolver

    def verify(self, token, nonce, required_mfa):
        if required_mfa is not True or not nonce:
            raise PermissionError('Authentication required')
        try:
            claims = jwt.decode(token, self.key_resolver(token), algorithms=['RS256'],
                                audience=self.client_id, issuer=self.issuer,
                                options={'require': ['exp', 'iat', 'sub', 'iss', 'aud', 'nonce', 'token_use']})
            if claims['token_use'] != 'id' or not claims['sub'] or not secrets.compare_digest(claims['nonce'], nonce):
                raise ValueError('Invalid token context')
            return Principal(claims['sub'], datetime.fromtimestamp(claims['exp'], timezone.utc), True)
        except (jwt.PyJWTError, ValueError, TypeError, KeyError) as error:
            raise PermissionError('Authentication required') from error


class Sessions:
    """Single-process session store; multi-worker deployment needs shared storage."""
    def __init__(self):
        self.records, self.lock = {}, RLock()

    @staticmethod
    def _digest(cookie):
        if not isinstance(cookie, str) or len(cookie) > 256:
            raise PermissionError('Authentication required')
        return hashlib.sha256(cookie.encode()).hexdigest()

    def open(self, principal):
        if not principal.mfa_verified or principal.expires_at <= datetime.now(timezone.utc):
            raise PermissionError('Authentication required')
        cookie, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        with self.lock:
            self.records[self._digest(cookie)] = (principal, csrf)
        return cookie, csrf

    def require(self, cookie, csrf=None):
        with self.lock:
            record = self.records.get(self._digest(cookie))
            if record is None or record[0].expires_at <= datetime.now(timezone.utc):
                raise PermissionError('Authentication required')
            if csrf is not None and (not isinstance(csrf, str) or not secrets.compare_digest(csrf, record[1])):
                raise PermissionError('Request verification failed')
            return record[0]

    def logout(self, cookie):
        with self.lock:
            self.records.pop(self._digest(cookie), None)

    def csrf(self, cookie):
        self.require(cookie)
        with self.lock:
            return self.records[self._digest(cookie)][1]
