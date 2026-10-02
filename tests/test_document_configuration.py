import unittest
from unittest.mock import patch,Mock
from ha.connected.document_configuration import build_documents,MountedKeys

class DocumentConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.settings={'HA_DOCUMENT_STORAGE':'spaces','HA_SPACES_REGION':'nyc3','HA_SPACES_BUCKET':'ha-private',
            'HA_SPACES_ACCESS_KEY':'fictional-access','HA_SPACES_SECRET_KEY':'fictional-secret',
            'HA_DOCUMENT_KEY_DIRECTORY':'/run/secrets/ha-keys','HA_DOCUMENT_ACTIVE_KEY_ID':'key-2026',
            'HA_CLAMD_SOCKET':'/run/clamav/clamd.sock'}

    def test_disabled_and_partial_configuration_fail_closed(self):
        self.assertIsNone(build_documents({},None))
        for key in self.settings:
            with self.subTest(missing=key),self.assertRaises(ValueError):
                build_documents({k:v for k,v in self.settings.items() if k!=key},Mock())
        with self.assertRaises(ValueError):build_documents({**self.settings,'HA_DOCUMENT_STORAGE':'disabled'},Mock())

    def test_explicit_regional_client_scanner_and_key_resolver_wired(self):
        repository=Mock()
        with patch('ha.connected.document_configuration.MountedKeys') as keys,patch('boto3.client') as client:
            keys.return_value.return_value=bytes(32)
            docs=build_documents(self.settings,repository)
            self.assertIs(docs.repository,repository)
            self.assertEqual(docs.objects.bucket,'ha-private')
            self.assertEqual(docs.scanner.path,'/run/clamav/clamd.sock')
            request=client.call_args.kwargs
            self.assertEqual(request['endpoint_url'],'https://nyc3.digitaloceanspaces.com')
            self.assertEqual(request['aws_access_key_id'],'fictional-access')
            self.assertEqual(request['aws_secret_access_key'],'fictional-secret')
            keys.return_value.assert_called_once_with('key-2026')

    def test_endpoint_injection_and_missing_repository_reject(self):
        for region in ('https://evil.example','nyc3/evil','nyc3.digitaloceanspaces.com',''):
            with self.assertRaises(ValueError):build_documents({**self.settings,'HA_SPACES_REGION':region},Mock())
        with self.assertRaises(ValueError):build_documents(self.settings,None)

    def test_keys_reject_application_directory_and_untrusted_identifiers(self):
        from pathlib import Path
        with self.assertRaises(ValueError):MountedKeys(Path(__file__).resolve().parents[1])
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            keys=MountedKeys(directory)
            for key_id in ('../secret','',None):
                with self.assertRaises(ValueError):keys(key_id)

    def test_mounted_key_length_and_permission_checks(self):
        import tempfile,stat
        from pathlib import Path
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);file=root/'key-2026.key';file.write_bytes(bytes(32))
            keys=MountedKeys(root)
            directory_info=Mock(st_mode=stat.S_IFDIR|0o700,st_uid=0)
            file_info=Mock(st_mode=stat.S_IFREG|0o600,st_uid=0)
            # POSIX policy simulation only; Windows ACLs are not claimed verified.
            with patch('os.name','posix'),patch('os.geteuid',return_value=10001,create=True),patch('os.O_NOFOLLOW',0,create=True),patch.object(type(root),'stat',return_value=directory_info),patch('os.fstat',return_value=file_info):
                self.assertEqual(keys('key-2026'),bytes(32))
                file.write_bytes(bytes(33))
                with self.assertRaises(ValueError):keys('key-2026')
                file.write_bytes(bytes(32))
                file_info.st_mode=stat.S_IFREG|0o644
                with self.assertRaises(ValueError):keys('key-2026')
                file_info.st_mode=stat.S_IFREG|0o600
                directory_info.st_mode=stat.S_IFDIR|0o755
                with self.assertRaises(ValueError):keys('key-2026')
