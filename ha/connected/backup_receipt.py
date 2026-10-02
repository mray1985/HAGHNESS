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
