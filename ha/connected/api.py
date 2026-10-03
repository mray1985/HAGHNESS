"""Authenticated connected API, separate from the legacy calculator server."""
import base64
from dataclasses import asdict
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
import json
import ssl
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from ha.returns import estimate_w2
from .domain import Scope
from .access import authorize
from .return_draft import estimate_connected_return

WEB = Path(__file__).resolve().parents[2] / 'web'
MAX_REQUEST = 30 * 1024 * 1024


class RequestVerificationError(Exception):
    pass


def create_server(address, sessions, ledger, documents, login, allowed_origin, *, reviews=None, tax_inputs=None, confirmations=None):
    if not allowed_origin.startswith('https://'):
        raise ValueError('HTTPS browser origin required')
    if reviews is None and ledger is not None and documents is not None:
        from .postgres import PostgresRepository
        if isinstance(ledger.repository, PostgresRepository) and documents.repository is ledger.repository:
            from .support_review import SupportReviews
            reviews = SupportReviews(ledger.repository, documents)

    if tax_inputs is None and ledger is not None and documents is not None:
        from .postgres import PostgresRepository
        if isinstance(ledger.repository, PostgresRepository) and documents.repository is ledger.repository:
            from .tax_inputs import TaxInputs
            tax_inputs = TaxInputs(ledger.repository,documents)

    if confirmations is None and ledger is not None:
        from .postgres import PostgresRepository
        if isinstance(ledger.repository, PostgresRepository):
            from .record_confirmation import RecordConfirmations
            confirmations = RecordConfirmations(ledger.repository)

    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(15)

        def log_message(self, fmt, *args):
            # OAuth codes, document IDs and source facts must not reach access logs.
            return

        def respond(self, status, value, headers=None):
            data = json.dumps(value).encode()
            try:
                self.send_response(status)
                self.send_header('Content-Type','application/json; charset=utf-8')
                self.send_header('Content-Length',str(len(data)))
                self.send_header('Cache-Control','no-store')
                self.send_header('X-Content-Type-Options','nosniff')
                self.send_header('Content-Security-Policy',"default-src 'self'; frame-ancestors 'none'; base-uri 'none'")
                for key, value in headers or []:
                    self.send_header(key,value)
                self.end_headers()
                self.wfile.write(data)
            except (BrokenPipeError,ConnectionResetError,ssl.SSLEOFError):
                self.close_connection=True

        def cookies(self):
            jar = SimpleCookie()
            jar.load(self.headers.get('Cookie',''))
            return jar

        def cookie(self, name):
            jar = self.cookies()
            return jar[name].value if name in jar else ''

        def identity(self, mutate=False):
            cookie = self.cookie('__Host-ha_session')
            principal = sessions.require(cookie)
            if mutate:
                csrf = self.headers.get('X-HA-CSRF')
                if self.headers.get('Origin') != allowed_origin or not csrf:
                    raise RequestVerificationError('Request verification failed')
                try:
                    sessions.require(cookie,csrf)
                except PermissionError as error:
                    raise RequestVerificationError('Request verification failed') from error
            return principal

        @staticmethod
        def scope(values):
            return Scope(values['profile'],values['business'],int(values['year']))

        def payload(self):
            if self.headers.get_content_type() != 'application/json':
                raise ValueError('JSON required')
            length = int(self.headers.get('Content-Length','0'))
            if not 0 < length <= MAX_REQUEST:
                raise ValueError('Invalid request size')
            raw = self.rfile.read(length)
            if len(raw) != length:
                raise ValueError('Incomplete request')
            value = json.loads(raw)
            if not isinstance(value,dict):
                raise ValueError('Object required')
            return value

        def do_GET(self):
            self.dispatch(False)

        def do_POST(self):
            self.dispatch(True)

        def dispatch(self, mutate):
            path = urlparse(self.path).path
            query = {k:v[0] for k,v in parse_qs(urlparse(self.path).query).items()}
            try:
                if not mutate and path == '/api/health':
                    return self.respond(200,{'ok':True,'connected':True,'tax_workspace':True,'login_configured':login is not None,
                        'documents_configured':documents is not None,'may_prepare_return':False})
                if mutate and path == '/api/return/estimate':
                    # Stateless arithmetic only: never reads or writes protected records.
                    if int(self.headers.get('Content-Length','0')) > 256 * 1024:
                        raise ValueError('Tax scenario too large')
                    return self.respond(200,estimate_w2(self.payload()))
                if not mutate and path in ('/','/home','/home.html','/home.js','/home.css','/connected.html','/connected.js','/connected.css','/tax','/index.html','/return.js','/return.css'):
                    name = 'home.html' if path in ('/','/home') else 'index.html' if path == '/tax' else path.lstrip('/')
                    target = WEB / name
                    if not target.is_file():
                        return self.respond(404,{'error':'Page unavailable'})
                    data = target.read_bytes()
                    if name == "index.html":
                        data = data.replace(b'id="books-link" href="/">HA home',b'id="books-link" href="/connected.html">HA Bookin')
                    self.send_response(200)
                    self.send_header('Content-Type',{'html':'text/html','js':'text/javascript','css':'text/css'}[name.rsplit('.',1)[1]]+'; charset=utf-8')
                    self.send_header('Content-Length',str(len(data)))
                    self.send_header('Cache-Control','no-store')
                    self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'; base-uri 'none'; object-src 'none'")
                    self.end_headers()
                    return self.wfile.write(data)
                if not mutate and path == '/api/auth/login':
                    if login is None:
                        return self.respond(503,{'error':'Hosted sign-in is not configured'})
                    url, browser_cookie = login.begin()
                    return self.respond(302,{},[('Location',url),('Set-Cookie','__Host-ha_login='+browser_cookie+'; Path=/; Secure; HttpOnly; SameSite=Lax; Max-Age=600')])
                if not mutate and path == '/api/auth/callback':
                    if login is None:
                        return self.respond(503,{'error':'Hosted sign-in is not configured'})
                    principal = login.complete(query.get('code',''),query.get('state',''),self.cookie('__Host-ha_login'))
                    cookie, csrf = sessions.open(principal)
                    return self.respond(302,{},[('Location','/connected.html'),
                        ('Set-Cookie','__Host-ha_session='+cookie+'; Path=/; Secure; HttpOnly; SameSite=Lax'),
                        ('Set-Cookie','__Host-ha_login=; Path=/; Secure; HttpOnly; SameSite=Lax; Max-Age=0')])
                try:
                    principal = self.identity(mutate)
                except PermissionError:
                    return self.respond(401,{'error':'Sign in required'})
                if path == '/api/auth/me' and not mutate:
                    return self.respond(200,{'subject':principal.subject,'csrf':sessions.csrf(self.cookie('__Host-ha_session'))})
                if path == '/api/auth/logout' and mutate:
                    sessions.logout(self.cookie('__Host-ha_session'))
                    return self.respond(200,{'ok':True},[('Set-Cookie','__Host-ha_session=; Path=/; Secure; HttpOnly; SameSite=Lax; Max-Age=0')])
                if path == '/api/connected/cases' and not mutate:
                    from .access import permitted_cases
                    return self.respond(200,{'cases':permitted_cases(principal,ledger.repository)})
                if path == '/api/connected/draft' and not mutate:
                    from .reserve import reserve_choice
                    rate,extra=reserve_choice(query.get('reserve_percent','25'),
                        query.get('reserve_extra_choice','no'),query.get('reserve_extra_dollars',''))
                    return self.respond(200,ledger.project(principal,self.scope(query),query.get('period','year'),
                        int(query.get('month','1')),rate,reserve_extra_minor=extra))
                if path == '/api/connected/events' and not mutate:
                    return self.respond(200,{'events':ledger.history(principal,self.scope(query))})
                if path == '/api/connected/events' and mutate:
                    body = self.payload()
                    return self.respond(201,ledger.post_event(principal,self.scope(body['scope']),body['event']))
                if path == '/api/connected/records/confirmations':
                    if confirmations is None:
                        return self.respond(503,{'error':'Record confirmation is not configured'})
                    if mutate:
                        body=self.payload()
                        return self.respond(201,confirmations.submit(principal,self.scope(body['scope']),body['confirmation']))
                    return self.respond(200,confirmations.view(principal,self.scope(query)))
                if path == '/api/connected/support/reviews':
                    if reviews is None:
                        return self.respond(503,{'error':'Supporting-record review is not configured'})
                    if mutate:
                        body=self.payload()
                        return self.respond(201,reviews.submit(principal,self.scope(body['scope']),body['review']))
                    return self.respond(200,reviews.view(principal,self.scope(query)))
                if path in ('/api/connected/tax/inputs','/api/connected/tax/input'):
                    if tax_inputs is None:
                        return self.respond(503,{'error':'Protected tax saving is not configured'})
                    if path == '/api/connected/tax/inputs':
                        if mutate:
                            if int(self.headers.get('Content-Length','0')) > 512 * 1024:
                                raise ValueError('Tax save request too large')
                            body=self.payload()
                            return self.respond(201,tax_inputs.save(principal,self.scope(body['scope']),body['save']))
                        return self.respond(200,tax_inputs.view(principal,self.scope(query)))
                    if not mutate:
                        return self.respond(200,tax_inputs.open(principal,self.scope(query),query.get('snapshot')))
                    return self.respond(404,{'error':'Resource unavailable'})
                if path == '/api/connected/return/estimate' and mutate:
                    body=self.payload()
                    return self.respond(200,estimate_connected_return(ledger,principal,self.scope(body['scope']),body['scenario']))
                if path == '/api/connected/documents':
                    if documents is None:
                        return self.respond(503,{'error':'Private document storage is not configured'})
                    if mutate:
                        body = self.payload()
                        scope = self.scope(body['scope'])
                        authorize(principal,scope,'upload',documents.repository)
                        data = base64.b64decode(body['data'],validate=True)
                        result = documents.upload(principal,scope,BytesIO(data),body['mime'],body['idempotency_key'])
                        return self.respond(201,asdict(result))
                    scope = self.scope(query)
                    authorize(principal,scope,'read',documents.repository)
                    return self.respond(200,{'versions':[asdict(v) for v in documents.repository.list_versions(scope)]})
                if path == '/api/connected/document/corrections' and mutate:
                    if documents is None:
                        return self.respond(503,{'error':'Private document storage is not configured'})
                    body=self.payload()
                    scope=self.scope(body['scope'])
                    authorize(principal,scope,'correct',documents.repository)
                    data=base64.b64decode(body['data'],validate=True)
                    result=documents.correct(principal,scope,body['document'],BytesIO(data),
                                             body['mime'],body['idempotency_key'],body['reason'])
                    return self.respond(201,asdict(result))
                if path == '/api/connected/document' and not mutate:
                    if documents is None:
                        return self.respond(503,{'error':'Private document storage is not configured'})
                    data = documents.read(principal,self.scope(query),query['document'],query['version'])
                    return self.respond(200,{'data':base64.b64encode(data).decode()})
                return self.respond(404,{'error':'Resource unavailable'})
            except (BrokenPipeError,ConnectionResetError,ssl.SSLEOFError):
                self.close_connection=True
            except PermissionError:
                self.respond(404,{'error':'Resource unavailable'})
            except RequestVerificationError:
                self.respond(403,{'error':'Request verification failed'})
            except (ValueError,TypeError,KeyError):
                self.respond(400,{'error':'Check the entered information'})
            except Exception:
                self.respond(503,{'error':'Service unavailable; no success confirmed'})

    return ThreadingHTTPServer(address,Handler)
