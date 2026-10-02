import unittest
from ha.connected.server import build_server


class ServerConfigurationTests(unittest.TestCase):
    def test_empty_configuration_provides_only_locked_preview(self):
        server = build_server(('127.0.0.1', 0), 'https://localhost:8766', {})
        server.server_close()

    def test_partial_configuration_cannot_start_connected_service(self):
        with self.assertRaises(ValueError):
            build_server(('127.0.0.1', 0), 'https://localhost:8766',
                         {'HA_DATABASE_URL': 'unused'})


if __name__ == '__main__':
    unittest.main()
