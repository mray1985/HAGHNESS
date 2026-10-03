import unittest
from unittest.mock import patch
from pathlib import Path
from scripts.verify_nginx_proxy import fixture_config

class NginxProxyProbeTests(unittest.TestCase):
    def test_redirect_server_explicitly_disables_request_logging(self):
        source=Path('deploy/digitalocean/droplet/nginx.conf.example').read_text(encoding='utf-8')
        redirect=source.partition('server {')[2].partition('}')[0]
        self.assertIn('access_log off;',redirect)
        self.assertIn('error_log /dev/null crit;',redirect)

    def test_fixture_changes_only_fixed_locators(self):
        source=Path('deploy/digitalocean/droplet/nginx.conf.example').read_text(encoding='utf-8')
        config=fixture_config(source,Path('/tmp/fictional'),18880,18843,18808)
        self.assertIn('listen 127.0.0.1:18880;',config)
        self.assertIn('listen 127.0.0.1:18843 ssl;',config)
        self.assertIn('proxy_pass http://127.0.0.1:18808;',config)
        for directive in ('client_body_buffer_size 30m;','proxy_request_buffering off;','proxy_buffering off;','proxy_cache off;','ssl_protocols TLSv1.2 TLSv1.3;'):
            self.assertIn(directive,config)
        with self.assertRaises(ValueError):fixture_config(source.replace('listen 80;','listen 81;'),Path('/tmp/fictional'),18880,18843,18808)

    def test_runtime_proxy_option_requires_connected_session(self):
        from scripts.verify_keycloak_runtime import main
        with patch('sys.argv',['probe','--distribution','fictional','--report','fictional','--nginx-proxy','fictional']):
            with self.assertRaisesRegex(ValueError,'Proxy probe requires connected session'):
                main()
