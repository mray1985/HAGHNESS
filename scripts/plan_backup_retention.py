"""Print a non-destructive retention plan for an operator-supplied inventory.

Usage: python -m scripts.plan_backup_retention inventory.json
Inventory: [{"snapshot_id":"...","created_at":"ISO8601","held":false}]
No database, storage or document is modified.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from ha.connected.backup_retention import Snapshot, retention_plan

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inventory',type=Path)
    args=parser.parse_args()
    raw=json.loads(args.inventory.read_text(encoding='utf-8'))
    if not isinstance(raw,list):raise ValueError('Backup inventory must be a list')
    snapshots=[]
    for row in raw:
        if not isinstance(row,dict) or set(row)!={'snapshot_id','created_at','held'}:
            raise ValueError('Explicit snapshot ID, creation time and hold flag required')
        snapshots.append(Snapshot(row['snapshot_id'],datetime.fromisoformat(row['created_at']),row['held']))
    print(json.dumps(retention_plan(snapshots,datetime.now(timezone.utc)),indent=2))

if __name__=='__main__':main()
