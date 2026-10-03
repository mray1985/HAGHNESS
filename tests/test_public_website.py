"""Public navigation must not expose protected records or displace either workspace."""
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from threading import Thread
import unittest
from ha.server import Handler
from ha.connected.api import create_server
from ha.connected.auth import Sessions


class PublicWebsiteTests(unittest.TestCase):
    def request(self, server, path):
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            connection = HTTPConnection(*server.server_address, timeout=3)
            connection.request('GET', path)
            response = connection.getresponse()
            result = response.status, response.getheader('Content-Type'), response.read().decode()
            connection.close()
            return result
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_home_is_public_on_both_servers(self):
        servers = [ThreadingHTTPServer(('127.0.0.1', 0), Handler),
                   create_server(('127.0.0.1', 0), Sessions(), None, None, None, 'https://ha.example')]
        for server in servers:
            with self.subTest(server=server.RequestHandlerClass):
                status, mime, body = self.request(server, '/')
                self.assertEqual(status, 200)
                self.assertIn('text/html', mime)
                self.assertIn('A little less', body)
                self.assertIn('id="previews"', body)

    def test_existing_tax_workspace_stays_addressable(self):
        status, _, body = self.request(ThreadingHTTPServer(('127.0.0.1', 0), Handler), '/index.html')
        self.assertEqual(status, 200)
        self.assertIn('id="tax-saving"', body)

    def test_connected_assets_public_but_data_still_requires_login(self):
        for path, expected in [('/home.css', 200), ('/home.js', 200), ('/connected.html', 200), ('/tax', 200), ('/index.html', 200), ('/home', 200), ('/home.html', 200),
                               ('/api/connected/draft?profile=a&business=b&year=2026', 401),
                               ('/../README.md', 401)]:
            with self.subTest(path=path):
                server = create_server(('127.0.0.1', 0), Sessions(), None, None, None, 'https://ha.example')
                self.assertEqual(self.request(server, path)[0], expected)

    def test_connected_health_advertises_current_tax_route_without_filing_readiness(self):
        import json
        server = create_server(('127.0.0.1', 0), Sessions(), None, None, None, 'https://ha.example')
        status, _, body = self.request(server, '/api/health')
        health = json.loads(body)
        self.assertEqual(status, 200)
        self.assertTrue(health['tax_workspace'])
        self.assertFalse(health['may_prepare_return'])
        self.assertFalse(health['login_configured'])

    def test_connected_tax_page_navigation_preserves_bookin_and_home(self):
        server = create_server(('127.0.0.1', 0), Sessions(), None, None, None, 'https://ha.example')
        status, _, body = self.request(server, '/tax')
        self.assertEqual(status, 200)
        self.assertIn('href="/connected.html">HA Bookin', body)
        self.assertIn('aria-label="Return to HA home"', body)
        self.assertIn('id="tax-saving"', body)
