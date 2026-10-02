"""Private operator receipts; never substitutes for authenticated recovery."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import tempfile
from .backup_bundle import sync_directory


def write_receipt(result, key_id, region, bucket, destination):
    remote = result.get('offhost') or {}
    if (result.get('completed') is not True or remote.get('completed') is not True
            or not re.fullmatch(r'ha-recovery/[0-9a-f]{32}/', remote.get('prefix', ''))
            or not re.fullmatch(r'[a-zA-Z0-9_-]{1,128}', result.get('snapshot_id', ''))
            or not re.fullmatch(r'[a-zA-Z0-9_-]{1,100}', key_id)
            or not re.fullmatch(r'[a-z]{2,8}[0-9]{1,2}', region)
            or not re.fullmatch(r'[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]', bucket)
            or type(result.get('document_versions')) is not int or result['document_versions'] < 0):
        raise ValueError('Verified backup receipt fields required')
    receipt = {'format': 'ha-backup-receipt-v1', 'snapshot_id': result['snapshot_id'],
               'completed_at': datetime.now(timezone.utc).isoformat(),
               'region': region, 'bucket': bucket, 'prefix': remote['prefix'],
               'recovery_key_id': key_id, 'document_versions': result['document_versions'],
               'copy_verified': True, 'recovery_verified': False, 'deletion_authorized': False}
    target = Path(destination)
    descriptor, name = tempfile.mkstemp(prefix='.ha-receipt-', dir=target.parent)
    staged = Path(name); published = False
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as writer:
            json.dump(receipt, writer, sort_keys=True)
            writer.write('\n'); writer.flush(); os.fsync(writer.fileno())
        os.link(staged, target); published = True
        sync_directory(target.parent)
    except BaseException:
        if published: target.unlink(missing_ok=True)
        raise
    finally:
        staged.unlink(missing_ok=True)
    return receipt


def publish_receipt(receipt, client):
    """Preserve a private off-host locator; not an authenticated recovery claim.

    Only generated, non-secret receipt fields are accepted. A fresh bundle
    prefix belongs to one job; a retry may write identical locator bytes there.
    Provider write/read failures propagate, retaining the local receipt.
    """
    fields = {'format', 'snapshot_id', 'completed_at', 'region', 'bucket',
              'prefix', 'recovery_key_id', 'document_versions', 'copy_verified',
              'recovery_verified', 'deletion_authorized'}
    if (not isinstance(receipt, dict) or set(receipt) != fields
            or receipt.get('format') != 'ha-backup-receipt-v1'
            or receipt.get('copy_verified') is not True
            or receipt.get('recovery_verified') is not False
            or receipt.get('deletion_authorized') is not False
            or type(receipt.get('document_versions')) is not int
            or receipt['document_versions'] < 0):
        raise ValueError('Generated verified-copy receipt required')
    patterns = {'prefix': r'ha-recovery/[0-9a-f]{32}/',
                'snapshot_id': r'[a-zA-Z0-9_-]{1,128}',
                'recovery_key_id': r'[a-zA-Z0-9_-]{1,100}',
                'region': r'[a-z]{2,8}[0-9]{1,2}',
                'bucket': r'[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]'}
    for field, pattern in patterns.items():
        if not isinstance(receipt.get(field), str) or not re.fullmatch(pattern, receipt[field]):
            raise ValueError('Invalid receipt locator')
    try:
        completed = datetime.fromisoformat(receipt['completed_at'])
        if completed.utcoffset() != timezone.utc.utcoffset(completed):
            raise ValueError('UTC completion required')
    except (TypeError, ValueError):
        raise ValueError('UTC completion required') from None
    payload = (json.dumps(receipt, sort_keys=True) + '\n').encode('utf-8')
    object_key = receipt['prefix'] + 'receipt.json'
    client.put_object(Bucket=receipt['bucket'], Key=object_key, Body=payload,
                      ACL='private', ContentType='application/json')
    body = client.get_object(Bucket=receipt['bucket'], Key=object_key)['Body']
    recovered = bytearray()
    try:
        while block := body.read(min(4096, len(payload) - len(recovered) + 1)):
            recovered.extend(block)
            if len(recovered) > len(payload):
                raise ValueError('Receipt copy exceeds expected size')
    finally:
        body.close()
    if recovered != payload:
        raise ValueError('Receipt copy verification failed')
    return {'key': object_key, 'verified': True}
