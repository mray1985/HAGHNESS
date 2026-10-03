"""Bounded fictional document concurrency probe; never hosted capacity proof."""
import base64
from concurrent.futures import ThreadPoolExecutor
import hashlib
import threading
import time
from urllib.parse import urlencode
import uuid


def verify_document_load(api,scope):
    count=4;size=2*1024*1024;barrier=threading.Barrier(count,timeout=10)
    query=urlencode(scope);prefix=uuid.uuid4().hex
    def worker(index):
        marker=f'Fictional HA load receipt {index}. '.encode()
        data=(marker*(size//len(marker)+1))[:size]
        body={'scope':scope,'mime':'text/plain','data':base64.b64encode(data).decode(),
              'idempotency_key':'load-'+prefix+'-'+str(index)}
        barrier.wait();started=time.perf_counter()
        version=api('POST','/api/connected/documents',body,status=201)
        # Exact retry must not create another document/version.
        if api('POST','/api/connected/documents',body,status=201)!=version:
            raise ValueError('Concurrent document retry mismatch')
        suffix=urlencode({'document':version['document_id'],'version':version['version_id']})
        result=api('GET','/api/connected/document?'+query+'&'+suffix,limit=4*1024*1024)
        recovered=base64.b64decode(result['data'],validate=True)
        if len(recovered)!=size or hashlib.sha256(recovered).digest()!=hashlib.sha256(data).digest():
            raise ValueError('Concurrent document readback mismatch')
        return version['document_id'],time.perf_counter()-started
    started=time.perf_counter()
    with ThreadPoolExecutor(max_workers=count) as pool:results=list(pool.map(worker,range(count)))
    if len({item[0] for item in results})!=count:raise ValueError('Concurrent document identifiers collided')
    return {'documents':count,'concurrency':count,'bytes_per_document':size,'exact_reads':True,
            'idempotent_retries':True,'elapsed_seconds':round(time.perf_counter()-started,3),
            'slowest_upload_retry_read_seconds':round(max(item[1] for item in results),3),
            'hosted_capacity_verified':False,'timing_scope':'one local fictional four-worker upload/retry/read run; excludes runtime startup and OTP wait'}
