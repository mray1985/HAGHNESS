import unittest
from datetime import datetime,timezone
from urllib.parse import urlparse,parse_qs
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from ha.connected.keycloak import KeycloakVerifier,KeycloakLogin

class KeycloakTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    def setUp(self):
        self.issuer='https://identity.example/realms/ha'
        now=int(datetime.now(timezone.utc).timestamp())
        self.claims=dict(iss=self.issuer,aud='ha-client',azp='ha-client',sub='owner',iat=now,exp=now+300,nonce='expected',acr='2',amr=['pwd','otp'],auth_time=now,typ='ID')
        self.verifier=KeycloakVerifier(self.issuer,'ha-client',lambda token:self.key.public_key())
    def token(self,**changes):return jwt.encode({**self.claims,**changes},self.key,algorithm='RS256')
    def test_verified_password_and_otp_token_creates_issuer_scoped_identity(self):
        principal=self.verifier.verify(self.token(),'expected')
        self.assertTrue(principal.mfa_verified)
        self.assertEqual(principal.subject,self.issuer+'|owner')
    def test_wrong_claims_missing_mfa_and_wrong_token_type_rejected(self):
        for changes in ({'iss':'https://other'},{'aud':'other'},{'azp':'other'},{'acr':'1'},{'amr':['pwd']},{'amr':['otp']},{'amr':'pwd otp'},{'nonce':'wrong'},{'exp':1},{'typ':'Bearer'},{'auth_time':1}):
            with self.subTest(changes=changes),self.assertRaises(PermissionError):self.verifier.verify(self.token(**changes),'expected')
        for key in ('amr','acr','nonce','sub','typ','auth_time'):
            claims={k:v for k,v in self.claims.items() if k!=key}
            with self.subTest(missing=key),self.assertRaises(PermissionError):self.verifier.verify(jwt.encode(claims,self.key,algorithm='RS256'),'expected')
    def test_unsigned_or_wrong_algorithm_is_rejected(self):
        with self.assertRaises(PermissionError):self.verifier.verify(jwt.encode(self.claims,'a'*32,algorithm='HS256'),'expected')
    def test_pkce_browser_binding_single_use_and_mfa_request(self):
        calls=[]
        def exchange(url,fields):
            calls.append((url,fields))
            nonce=parse_qs(urlparse(login_url).query)['nonce'][0]
            return {'id_token':self.token(nonce=nonce)}
        login=KeycloakLogin(self.issuer,'ha-client','https://ha.example/api/auth/callback',self.verifier,exchange=exchange)
        login_url,cookie=login.begin();query=parse_qs(urlparse(login_url).query)
        self.assertEqual(query['code_challenge_method'],['S256'])
        self.assertIn('"essential":true',query['claims'][0])
        state=query['state'][0]
        self.assertTrue(login.complete('code',state,cookie).mfa_verified)
        self.assertIn('code_verifier',calls[0][1])
        with self.assertRaises(PermissionError):login.complete('code',state,cookie)
        url,cookie=login.begin();state=parse_qs(urlparse(url).query)['state'][0]
        with self.assertRaises(PermissionError):login.complete('code',state,'wrong-browser')
        self.assertEqual(len(calls),1)
    def test_only_https_keycloak_realm_and_callback_accepted(self):
        for issuer in ('http://identity.example/realms/ha','https://identity.example/not-a-realm','https://user:pass@identity.example/realms/ha','https://identity.example/realms/ha?query'):
            with self.subTest(issuer=issuer),self.assertRaises(ValueError):KeycloakLogin(issuer,'ha-client','https://ha.example/api/auth/callback',self.verifier)
