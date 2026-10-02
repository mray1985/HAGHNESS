"""Operator-only encrypted off-host copy; no retention deletion or activation."""
import hashlib
from pathlib import Path
import uuid
import shutil
import tempfile
from .backup_bundle import inspect_bundle, digest


def copy_bundle(root, key, versions, client, bucket):
    """Verify locally, copy ciphertext to a fresh prefix, read every byte back.

    The caller supplies a separately scoped private backup-store client. Failed
    prefixes are retained for diagnosis and never count as successful copies.
    """
    root = Path(root)
    versions = list(versions)
    metadata, _ = inspect_bundle(root, key, versions)
    names = ['database.habackup', *metadata['object_files'].values(), 'inventory.habackup']
    # Freeze ciphertext privately, then authenticate the copy, avoiding changes
    # to the original bundle between inspection and transfer.
    with tempfile.TemporaryDirectory(prefix='.ha-transfer-', dir=root.parent) as folder:
        staged = Path(folder)
        for name in names:
            source = root / name
            if source.is_symlink() or not source.is_file():
                raise ValueError('Invalid backup artifact')
            shutil.copyfile(source, staged / name)
        metadata, _ = inspect_bundle(staged, key, versions)
        return _copy_verified(staged, metadata, client, bucket)


def _copy_verified(root, metadata, client, bucket):
    names = ['database.habackup', *sorted(metadata['object_files'].values())]
    names.append('inventory.habackup')
    prefix = 'ha-recovery/' + uuid.uuid4().hex + '/'
    for name in names:
        source = root / name
        if source.is_symlink() or not source.is_file():
            raise ValueError('Invalid backup artifact')
        expected_size, expected_hash = source.stat().st_size, digest(source)
        with source.open('rb') as reader:
            client.upload_fileobj(reader, bucket, prefix + name,
                                  ExtraArgs={'ACL': 'private', 'ContentType': 'application/octet-stream'})
        response = client.get_object(Bucket=bucket, Key=prefix + name)
        body = response['Body']
        count, hasher = 0, hashlib.sha256()
        try:
            while block := body.read(min(1024 * 1024, expected_size - count + 1)):
                count += len(block)
                if count > expected_size:
                    raise ValueError('Backup copy exceeds expected size')
                hasher.update(block)
        finally:
            body.close()
        if count != expected_size or hasher.hexdigest() != expected_hash:
            raise ValueError('Backup copy verification failed')
    return {'prefix': prefix, 'artifacts': len(names), 'completed': True,
            'deletion_performed': False}
