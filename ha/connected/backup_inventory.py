"""Operator-only verified version inventory; encrypt before storing off-host.

Does not schedule backups, authorize deletion, or create a database snapshot.
Callers must supply versions from the same exported snapshot used by pg_dump.
"""
from dataclasses import asdict
import hashlib
import re
from .documents import DocumentVersion,MAX_BYTES
from .domain import Scope

SHA256=re.compile(r'[0-9a-f]{64}')

def build_inventory(snapshot_id,versions,objects,database_archive_sha256):
    if not isinstance(snapshot_id,str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,128}',snapshot_id):
        raise ValueError('Bounded snapshot identifier required')
    if not isinstance(database_archive_sha256,str) or SHA256.fullmatch(database_archive_sha256) is None:
        raise ValueError('Database archive digest required')
    items=list(versions);by_id={};keys=set()
    for item in items:
        if (not isinstance(item,DocumentVersion) or not isinstance(item.scope,Scope)
                or not isinstance(item.version_id,str) or not item.version_id
                or not isinstance(item.document_id,str) or not item.document_id
                or not isinstance(item.object_key,str) or not item.object_key
                or not isinstance(item.storage_version,str) or not item.storage_version
                or (item.previous_version_id is not None and (not isinstance(item.previous_version_id,str) or not item.previous_version_id))
                or item.version_id in by_id or item.object_key in keys
                or not isinstance(item.sha256,str) or SHA256.fullmatch(item.sha256) is None):
            raise ValueError('Invalid immutable version inventory')
        by_id[item.version_id]=item;keys.add(item.object_key)
    for item in items:
        visited=set();current=item
        while current.previous_version_id is not None:
            if current.version_id in visited:raise ValueError('Cyclic correction chain')
            visited.add(current.version_id)
            previous=by_id.get(current.previous_version_id)
            if (previous is None or previous.scope!=item.scope or previous.document_id!=item.document_id
                    or not isinstance(current.reason,str) or not current.reason.strip()):
                raise ValueError('Broken correction chain')
            current=previous
    chains={}
    for item in items:chains.setdefault((item.scope,item.document_id),[]).append(item)
    for chain in chains.values():
        roots=[item for item in chain if item.previous_version_id is None]
        predecessors=[item.previous_version_id for item in chain if item.previous_version_id is not None]
        heads={item.version_id for item in chain}-set(predecessors)
        if len(roots)!=1 or len(heads)!=1 or len(predecessors)!=len(set(predecessors)):
            raise ValueError('Document history must be a single correction chain')
    entries=[]
    for item in sorted(items,key=lambda value:value.version_id):
        data=objects.get(item.object_key,item.storage_version)
        if (not isinstance(data,bytes) or not 0<len(data)<=MAX_BYTES
                or hashlib.sha256(data).hexdigest()!=item.sha256):
            raise ValueError('Backup object integrity failure')
        entries.append({**asdict(item),'size_bytes':len(data)})
    return {'format':'ha-document-inventory-v1','snapshot_id':snapshot_id,
        'database_archive_sha256':database_archive_sha256,'versions':entries}

def verify_inventory(inventory,versions,objects,database_archive_sha256):
    if not isinstance(inventory,dict):raise ValueError('Backup inventory required')
    expected=build_inventory(inventory.get('snapshot_id'),versions,objects,database_archive_sha256)
    if inventory!=expected:raise ValueError('Restored inventory disagrees with database or objects')
    return len(expected['versions'])
