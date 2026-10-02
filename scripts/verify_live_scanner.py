"""Local Linux ClamD verification using fictional samples and official signatures.

Starts only its own temporary Unix-socket daemon and terminates that process.
Does not activate runtime uploads or change the installed ClamD configuration.
"""
import argparse
import json
import hashlib
from io import BytesIO
import zipfile
import os
from pathlib import Path
import subprocess
import tempfile
import time
from ha.connected.scanner import ClamDScanner
from ha.connected.documents import MAX_BYTES

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--encrypted-pdf',required=True)
    parser.add_argument('--report',required=True)
    parser.add_argument('--container-policy')
    args=parser.parse_args()
    if os.name!='posix':raise ValueError('Linux verification required')
    encrypted=Path(args.encrypted_pdf).read_bytes()
    if not encrypted.startswith(b'%PDF-') or b'/Encrypt' not in encrypted:
        raise ValueError('Fictional encrypted PDF fixture required')
    with tempfile.TemporaryDirectory(prefix='ha-scan-') as folder:
        root=Path(folder);socket=root/'clamd.sock';config=root/'clamd.conf'
        database=Path('/var/lib/clamav')
        if args.container_policy:
            database=root/'database';database.mkdir()
            for source in Path('/var/lib/clamav').iterdir():
                if source.suffix in ('.cvd','.cld'):
                    (database/source.name).symlink_to(source)
            (database/'ha-container-policy.cdb').write_bytes(Path(args.container_policy).read_bytes())
        config.write_text(f"""Foreground yes
DatabaseDirectory {database}
LocalSocket {socket}
LocalSocketMode 660
TemporaryDirectory {root}
StreamMaxLength 25M
MaxFileSize 25M
MaxScanSize 100M
ScanPDF yes
ScanArchive yes
HeuristicAlerts yes
AlertExceedsMax yes
AlertEncrypted yes
LeaveTemporaryFiles no
""",encoding='utf-8')
        with (root/'engine.log').open('wb') as log:
            process=subprocess.Popen(['clamd','--config-file='+str(config)],stdout=log,stderr=log)
            try:
                deadline=time.monotonic()+60
                while not socket.exists():
                    if process.poll() is not None:raise RuntimeError('ClamD startup failed')
                    if time.monotonic()>deadline:raise TimeoutError('ClamD startup timed out')
                    time.sleep(.1)
                scanner=ClamDScanner(str(socket))
                started=time.perf_counter()
                # Harmless standard antivirus test string; never stored as a file.
                eicar=b'X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*'
                expansion=BytesIO()
                with zipfile.ZipFile(expansion,"w",compression=zipfile.ZIP_DEFLATED) as archive:
                    archive.writestr("fictional-limit.txt",bytes(101*1024*1024))
                boundary=BytesIO()
                with zipfile.ZipFile(boundary,"w",compression=zipfile.ZIP_DEFLATED) as archive:
                    archive.writestr("fictional-boundary.txt",bytes(25*1024*1024))
                above=BytesIO()
                with zipfile.ZipFile(above,"w",compression=zipfile.ZIP_DEFLATED) as archive:
                    archive.writestr("fictional-above.txt",bytes(26*1024*1024))
                nested=BytesIO()
                with zipfile.ZipFile(nested,"w",compression=zipfile.ZIP_DEFLATED) as archive:
                    archive.writestr("fictional-nested.zip",above.getvalue())
                checks={
                    'clean_text_accepted':scanner(b'Fictional HA receipt total 10.00','text/plain'),
                    'eicar_rejected':not scanner(eicar,'text/plain'),
                    'encrypted_pdf_rejected':not scanner(encrypted,'application/pdf'),
                    'engine_expanded_file_limit_rejected':not scanner(expansion.getvalue(),'application/zip'),
                    'member_at_25m_accepted':scanner(boundary.getvalue(),'application/zip'),
                    'member_at_26m_rejected':not scanner(above.getvalue(),'application/zip'),
                    'nested_26m_member_rejected':not scanner(nested.getvalue(),'application/zip'),
                    'oversized_input_rejected':not scanner(bytes(MAX_BYTES+1),'application/pdf'),
                    'unavailable_socket_rejected':not ClamDScanner(str(root/'missing.sock'))(b'fixture','text/plain')}
                report={'environment':'local Ubuntu ClamD; fictional samples only',
                    'engine':subprocess.check_output(['clamd','--version'],text=True).strip(),
                    'checks':checks,'verification_passed':all(checks.values()),'elapsed_seconds':round(time.perf_counter()-started,3),
                    'socket_mode':oct(socket.stat().st_mode&0o777),
                    'container_policy_enabled':bool(args.container_policy),
                    'container_policy_sha256':hashlib.sha256(Path(args.container_policy).read_bytes()).hexdigest() if args.container_policy else None,
                    'hosted_verification':'not_run','runtime_uploads_activated':False}
                Path(args.report).write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
                print(json.dumps(report))
                if not all(checks.values()):raise ValueError("Live scanner policy verification failed; see saved report")
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:process.wait(timeout=10)
                    except subprocess.TimeoutExpired:process.kill();process.wait()

if __name__=='__main__':main()
