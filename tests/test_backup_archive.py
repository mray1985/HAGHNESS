import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from cryptography.exceptions import InvalidTag
from ha.connected.backup_archive import encrypt_backup,decrypt_backup,CHUNK

class BackupArchiveTests(unittest.TestCase):
    def test_multiframe_roundtrip_and_wrong_key_cleanup(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root);data=b"private database row"*(CHUNK//10)
            (p/"dump").write_bytes(data)
            encrypt_backup(p/"dump",p/"archive",bytes(range(32)))
            self.assertNotIn(b"private database row",(p/"archive").read_bytes())
            decrypt_backup(p/"archive",p/"restored",bytes(range(32)))
            self.assertEqual((p/"restored").read_bytes(),data)
            with self.assertRaises(InvalidTag):
                decrypt_backup(p/"archive",p/"wrong",bytes(32))
            self.assertFalse((p/"wrong").exists())

    def test_tampered_truncated_and_appended_archives_never_leave_restore(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root);(p/"dump").write_bytes(b"records"*100)
            encrypt_backup(p/"dump",p/"archive",bytes(32))
            raw=(p/"archive").read_bytes()
            mutations=[raw[:-1],raw+b"extra",raw[:30]+bytes([raw[30]^1])+raw[31:]]
            for n,changed in enumerate(mutations):
                damaged=p/str(n);damaged.write_bytes(changed)
                with self.assertRaises((ValueError,InvalidTag)):
                    decrypt_backup(damaged,p/"restored",bytes(32))
                self.assertFalse((p/"restored").exists())

    def test_existing_targets_preserved_and_empty_archive_supported(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root);(p/"dump").write_bytes(b"");(p/"existing").write_bytes(b"keep")
            with self.assertRaises(FileExistsError):
                encrypt_backup(p/"dump",p/"existing",bytes(32))
            self.assertEqual((p/"existing").read_bytes(),b"keep")
            encrypt_backup(p/"dump",p/"archive",bytes(32))
            decrypt_backup(p/"archive",p/"restored",bytes(32))
            self.assertEqual((p/"restored").read_bytes(),b"")

    def test_failed_publication_exposes_no_final_or_partial_file(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root);(p/"dump").write_bytes(b"private records")
            def deny_link(source,target):
                self.assertTrue(Path(source).exists())
                self.assertFalse(Path(target).exists())
                raise OSError("publication unavailable")
            with patch("ha.connected.backup_archive.os.link",side_effect=deny_link):
                with self.assertRaises(OSError):
                    encrypt_backup(p/"dump",p/"archive",bytes(32))
            self.assertFalse((p/"archive").exists())
            self.assertEqual(list(p.glob(".ha-backup-*")),[])
