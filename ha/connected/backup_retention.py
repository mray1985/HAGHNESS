"""Non-destructive backup retention planning; never expires source documents.

Keep 35 days, the newest snapshot in each of 12 calendar months (including
the current month), the latest available snapshot, and all held snapshots.
Actual removal requires an operator's verified recovery and inventory review.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

@dataclass(frozen=True)
class Snapshot:
    snapshot_id: str
    created_at: datetime
    held: bool = False

def retention_plan(snapshots, now):
    if not isinstance(now,datetime) or now.utcoffset() is None:
        raise ValueError('Timezone-aware inventory time required')
    items=list(snapshots)
    now=now.astimezone(timezone.utc)
    seen=set()
    for item in items:
        if (not isinstance(item,Snapshot) or not isinstance(item.snapshot_id,str)
                or not item.snapshot_id.strip() or item.snapshot_id in seen
                or not isinstance(item.created_at,datetime)
                or item.created_at.utcoffset() is None or item.created_at>now
                or type(item.held) is not bool):
            raise ValueError('Invalid backup inventory')
        seen.add(item.snapshot_id)
    ordered=sorted(items,key=lambda item:(item.created_at,item.snapshot_id),reverse=True)
    retained=set()
    months=set()
    current=now.year*12+now.month
    for index,item in enumerate(ordered):
        stamp=item.created_at.astimezone(timezone.utc)
        month=stamp.year*12+stamp.month
        monthly=0<=current-month<12 and month not in months
        if monthly:months.add(month)
        if index==0 or item.held or item.created_at>=now-timedelta(days=35) or monthly:
            retained.add(item.snapshot_id)
    return {'retain':sorted(retained),'expire_candidates':sorted(seen-retained),
            'deletion_authorized':False}
