"""Operator-only encrypted off-host copy; no retention deletion or activation."""
import hashlib
from pathlib import Path
import uuid
import shutil
import tempfile
import os
import re
from .backup_bundle import inspect_bundle, digest, sync_directory, MAX_MANIFEST
from .documents import MAX_BYTES


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


def recover_bundle(client, bucket, prefix, key, versions, destination, database_limit):
    """Download ciphertext and verify against separately recovered snapshot rows.

    A trusted private parent, external historical key and explicit database size
    limit are operator requirements. This does not run pg_restore or alter rows.
    """
    if not isinstance(prefix, str) or re.fullmatch(r'ha-recovery/[0-9a-f]{32}/', prefix) is None:
        raise ValueError('Invalid recovery prefix')
    if type(database_limit) is not int or database_limit <= 0:
        raise ValueError('Explicit positive database size limit required')
    versions = list(versions)
    names = ['database.habackup'] + sorted({
        'object-' + hashlib.sha256(v.version_id.encode()).hexdigest() + '.habackup'
        for v in versions}) + ['inventory.habackup']
    target = Path(destination)
    if target.exists() or target.is_symlink():
        raise FileExistsError('Recovery destination exists')
    with tempfile.TemporaryDirectory(prefix='.ha-download-', dir=target.parent) as folder:
        staged = Path(folder)
        for name in names:
            limit = database_limit if name == 'database.habackup' else (
                MAX_MANIFEST + 4096 if name == 'inventory.habackup' else MAX_BYTES + 4096)
            body = client.get_object(Bucket=bucket, Key=prefix + name)['Body']
            count = 0
            try:
                with (staged / name).open('xb') as writer:
                    while block := body.read(min(1024 * 1024, limit - count + 1)):
                        count += len(block)
                        if count > limit:
                            raise ValueError('Recovery download exceeds limit')
                        writer.write(block)
                    writer.flush(); os.fsync(writer.fileno())
            finally:
                body.close()
        inspect_bundle(staged, key, versions)
        target.mkdir(mode=0o700)
        published = False
        try:
            for name in names[:-1]:
                os.link(staged / name, target / name)
            sync_directory(target)
            os.link(staged / names[-1], target / names[-1]); published = True
            sync_directory(target)
        except BaseException:
            if published:
                (target / 'inventory.habackup').unlink(missing_ok=True)
            raise
    return {'completed': True, 'artifacts': len(names), 'deletion_performed': False}
