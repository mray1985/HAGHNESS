"""Combine latest observed attempt with its live private receipt, without writes."""
import argparse
from datetime import datetime,timedelta,timezone
import json
import sys
from .backup_attempts import assess_attempts,parse_events
from .backup_monitor import assess,configured_store
from .backup_receipt import retrieve_receipt


def check(events,client,bucket,region,*,now=None,max_age=timedelta(hours=36)):
    now=now or datetime.now(timezone.utc)
    attempt=assess_attempts(events,now=now,max_age=max_age)
    result={'status':'attempt_attention','attempt_status':attempt['status'],
        'journal_window_only':True,'locator_checked':False,
        'archive_integrity_verified':False,'recovery_verified':False,'deletion_authorized':False}
    if attempt['status']!='completed_observed':return result
    # The journal parser has validated unique starts/terminal transitions.
    started=next(event for event in reversed(events) if event['status']=='started')
    completed=next(event for event in events if event['attempt_id']==started['attempt_id'] and event['status']=='completed')
    receipt=retrieve_receipt(client,bucket,completed['prefix'],region)
    if (receipt['recovery_key_id']!=completed['recovery_key_id']
            or receipt['document_versions']!=completed['document_versions']
            or not datetime.fromisoformat(started['observed_at'])<=datetime.fromisoformat(receipt['completed_at'])<=datetime.fromisoformat(completed['observed_at'])):
        raise ValueError('Receipt does not match the observed completed attempt')
    locator=assess(receipt,now=now,max_age=max_age)
    return {**result,'status':'current_observed_attempt' if locator['status']=='current_locator' else 'locator_attention',
            'locator_checked':True,'locator_status':locator['status'],
            'attempt_age_seconds':attempt['age_seconds'],'locator_age_seconds':locator['age_seconds']}


def main(argv=None):
    parser=argparse.ArgumentParser(description='Read supplied attempt journal and matching private receipt; does not verify recovery.')
    parser.add_argument('--max-age-hours',type=int,default=36)
    args=parser.parse_args(argv)
    try:
        events=parse_events(sys.stdin.buffer.read(1048577))
        now=datetime.now(timezone.utc);max_age=timedelta(hours=args.max_age_hours)
        attempt=assess_attempts(events,now=now,max_age=max_age)
        store,bucket,region=configured_store() if attempt['status']=='completed_observed' else (None,None,None)
        result=check(events,store,bucket,region,now=now,max_age=max_age)
    except Exception:
        print(json.dumps({'status':'unavailable','journal_window_only':True,'locator_checked':False,
            'archive_integrity_verified':False,'recovery_verified':False,'deletion_authorized':False}))
        return 2
    print(json.dumps(result,sort_keys=True))
    return 0 if result['status']=='current_observed_attempt' else 1


if __name__=='__main__':raise SystemExit(main())
