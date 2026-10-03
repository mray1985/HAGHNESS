"""Assess a bounded ordered journal window; no archive or recovery claim."""
from datetime import datetime,timedelta,timezone
import json
import re
import sys


def assess_attempts(events,*,now=None,max_age=timedelta(hours=36)):
    now=now or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset()!=timedelta(0) or max_age<=timedelta(0):
        raise ValueError('UTC time and positive age required')
    if not isinstance(events,list) or len(events)>2048:raise ValueError('Bounded journal window required')
    base={'format','attempt_id','status','observed_at','recovery_verified','deletion_authorized'}
    attempts={};latest=None;previous=None
    for event in events:
        if not isinstance(event,dict):raise ValueError('Invalid attempt record')
        status=event.get('status');extra={'started':set(),'failed':{'message'},
            'completed':{'document_versions','prefix','recovery_key_id','copy_verified','locator_verified'}}
        if (status not in extra or set(event)!=base|extra[status]
                or event['format']!='ha-backup-attempt-v1'
                or event['recovery_verified'] is not False or event['deletion_authorized'] is not False
                or not isinstance(event['attempt_id'],str) or not re.fullmatch(r'[0-9a-f]{32}',event['attempt_id'])):
            raise ValueError('Invalid attempt schema')
        try:observed=datetime.fromisoformat(event['observed_at'])
        except (TypeError,ValueError):raise ValueError('Invalid attempt time') from None
        if observed.utcoffset()!=timedelta(0) or observed>now or (previous and observed<previous):
            raise ValueError('Ordered nonfuture UTC journal required')
        previous=observed;identifier=event['attempt_id']
        if status=='started':
            if identifier in attempts:raise ValueError('Duplicate attempt start')
            latest=identifier;attempts[identifier]=(status,observed)
        else:
            if identifier not in attempts or attempts[identifier][0]!='started':
                raise ValueError('Unmatched or duplicate terminal record')
            if status=='failed' and event['message']!='HA backup failed; no completion confirmed':
                raise ValueError('Unexpected failure message')
            if status=='completed' and (event['copy_verified'] is not True or event['locator_verified'] is not True
                    or type(event['document_versions']) is not int or event['document_versions']<0
                    or not isinstance(event['prefix'],str) or not re.fullmatch(r'ha-recovery/[0-9a-f]{32}/',event['prefix'])
                    or not isinstance(event['recovery_key_id'],str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,100}',event['recovery_key_id'])):
                raise ValueError('Invalid completion evidence')
            attempts[identifier]=(status,observed)
    result={'status':'no_attempt_observed','journal_window_only':True,
        'archive_integrity_verified':False,'recovery_verified':False,'deletion_authorized':False}
    if latest:
        status,observed=attempts[latest];age=now-observed
        result.update(status='unfinished' if status=='started' else 'failed' if status=='failed'
            else 'stale_attempt' if age>max_age else 'completed_observed',age_seconds=int(age.total_seconds()))
    return result


def parse_events(payload):
    """Strict bounded JSONL journal parser shared by operator health checks."""
    if not isinstance(payload,bytes) or len(payload)>1048576:
        raise ValueError('Journal window too large')
    def unique(pairs):
        value={}
        for key,item in pairs:
            if key in value:raise ValueError('Duplicate JSON field')
            value[key]=item
        return value
    events=[]
    for line in payload.decode('utf-8').splitlines():
        if line.strip():
            if len(events)>=2048:raise ValueError('Journal window too many records')
            events.append(json.loads(line,object_pairs_hook=unique))
    return events


def main():
    try:
        events=parse_events(sys.stdin.buffer.read(1048577))
        result=assess_attempts(events)
    except Exception:
        print(json.dumps({'status':'invalid_journal_window','journal_window_only':True,
            'archive_integrity_verified':False,'recovery_verified':False,'deletion_authorized':False}))
        return 2
    print(json.dumps(result,sort_keys=True))
    return 0 if result['status']=='completed_observed' else 1


if __name__=='__main__':raise SystemExit(main())
