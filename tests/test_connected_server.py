import unittest
from ha.connected.server import build_server


class ServerConfigurationTests(unittest.TestCase):
    def test_configured_document_service_is_passed_to_same_session_api(self):
        from unittest.mock import patch,Mock
        documents=Mock()
        settings={'HA_AUTH_PROVIDER':'keycloak','HA_DATABASE_URL':'unused',
                  'HA_KEYCLOAK_ISSUER':'https://identity.example/realms/ha','HA_KEYCLOAK_CLIENT':'ha-client'}
        with patch('ha.connected.server.build_documents',return_value=documents) as build,patch('ha.connected.server.create_server') as create:
            build_server(('127.0.0.1',0),'https://ha.example',settings)
            self.assertIs(create.call_args.args[3],documents)
            self.assertIsNotNone(build.call_args.args[1])

    def test_empty_configuration_provides_only_locked_preview(self):
        server = build_server(('127.0.0.1', 0), 'https://localhost:8766', {})
        server.server_close()

    def test_partial_configuration_cannot_start_connected_service(self):
        with self.assertRaises(ValueError):
            build_server(('127.0.0.1', 0), 'https://localhost:8766',
                         {'HA_DATABASE_URL': 'unused'})

    def test_keycloak_configuration_requires_all_settings_and_explicit_provider(self):
        settings={'HA_AUTH_PROVIDER':'keycloak','HA_DATABASE_URL':'unused',
                  'HA_KEYCLOAK_ISSUER':'https://identity.example/realms/ha','HA_KEYCLOAK_CLIENT':'ha-client'}
        for key in ('HA_DATABASE_URL','HA_KEYCLOAK_ISSUER','HA_KEYCLOAK_CLIENT'):
            with self.subTest(missing=key),self.assertRaises(ValueError):
                build_server(('127.0.0.1',0),'https://ha.example',{k:v for k,v in settings.items() if k!=key})
        with self.assertRaises(ValueError):
            build_server(('127.0.0.1',0),'https://ha.example',{**settings,'HA_AUTH_PROVIDER':'disabled'})
        with self.assertRaises(ValueError):
            build_server(('127.0.0.1',0),'https://ha.example',{**settings,'HA_COGNITO_POOL':'unexpected'})
        server=build_server(('127.0.0.1',0),'https://ha.example',settings)
        server.server_close()


if __name__ == '__main__':
    unittest.main()
