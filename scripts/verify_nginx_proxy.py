"""Actual isolated nginx template probe with fictional upstream; no hosted/MFA claim."""
import argparse
import ctypes
from datetime import datetime,timedelta,timezone
import hashlib
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import ipaddress
import json
import os
from pathlib import Path
import signal
import socket
import ssl
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.request
from cryptography import x509
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


def fixture_config(template,root,http_port,tls_port,upstream_port):
    """Change fixture locators only; proxy policy stays from the committed template."""
    replacements={
        'listen 80;':f'listen 127.0.0.1:{http_port};',
        'listen 443 ssl;':f'listen 127.0.0.1:{tls_port} ssl;',
        'server_name tax.example.invalid;':'server_name 127.0.0.1;',
        'return 308 https://tax.example.invalid$request_uri;':f'return 308 https://127.0.0.1:{tls_port}$request_uri;',
        'ssl_certificate /etc/ha/tls/fullchain.pem;':f'ssl_certificate {root}/cert.pem;',
        'ssl_certificate_key /etc/ha/tls/privkey.pem;':f'ssl_certificate_key {root}/key.pem;',
        'proxy_pass http://127.0.0.1:8080;':f'proxy_pass http://127.0.0.1:{upstream_port};',
        'proxy_set_header Host tax.example.invalid;':'proxy_set_header Host 127.0.0.1;'}
    for old,new in replacements.items():
        expected=2 if old.startswith('server_name ') else 1
        if template.count(old)!=expected:raise ValueError('Unexpected proxy fixture locator')
        template=template.replace(old,new)
    prefix=f"""worker_processes 1;
daemon off;
master_process off;
pid {root}/nginx.pid;
error_log {root}/inherited-error.log error;
events {{ worker_connections 64; }}
http {{
access_log {root}/inherited-access.log;
client_body_temp_path {root}/client-temp;
proxy_temp_path {root}/proxy-temp;
fastcgi_temp_path {root}/fastcgi-temp;
uwsgi_temp_path {root}/uwsgi-temp;
scgi_temp_path {root}/scgi-temp;
"""
    return prefix+template+chr(10)+'}'+chr(10)


class TempWatcher:
    """Observe create/write activity even if nginx immediately unlinks a file."""
    def __init__(self,paths):
        libc=ctypes.CDLL(None,use_errno=True);self.fd=libc.inotify_init1(os.O_NONBLOCK|os.O_CLOEXEC)
        if self.fd<0:raise ValueError('Temporary-file observation unavailable')
        for path in paths:
            if libc.inotify_add_watch(self.fd,os.fsencode(path),0x100|0x2|0x8)<0:
                os.close(self.fd);raise ValueError('Temporary-file watch unavailable')
    def changed(self):
        changed=False
        while True:
            try:data=os.read(self.fd,65536)
            except BlockingIOError:break
            if not data:break
            changed=True
        return changed
    def close(self):os.close(self.fd)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None


def run_probe(binary,template):
    if os.name!='posix':raise ValueError('Linux proxy probe required')
    observations=[]
    class Upstream(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):
            observations.append((self.headers.get('Host'),self.headers.get('X-Forwarded-Proto')))
            if self.path.startswith('/large-response?'):
                self.send_response(200);self.send_header('Content-Type','application/octet-stream');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(payload)));self.end_headers()
                for index in range(0,len(payload),65536):self.wfile.write(payload[index:index+65536])
                return
            callback=self.path.startswith('/callback?')
            self.send_response(302 if callback else 200)
            self.send_header('Cache-Control','no-store')
            if callback:
                self.send_header('Location','/connected.html');self.send_header('Set-Cookie','__Host-ha_session=fictional; Secure; HttpOnly; Path=/; SameSite=Lax')
            self.send_header('Content-Length','0');self.end_headers()
        def do_POST(self):
            digest=hashlib.sha256();size=0
            if self.headers.get('Transfer-Encoding','').lower()=='chunked':
                while True:
                    count=int(self.rfile.readline(128).strip(),16)
                    if not count:self.rfile.readline(128);break
                    block=self.rfile.read(count);self.rfile.read(2);size+=len(block);digest.update(block)
            else:
                remaining=int(self.headers.get('Content-Length','0'))
                while remaining:
                    block=self.rfile.read(min(remaining,65536))
                    if not block:raise ValueError('Incomplete fictional body')
                    remaining-=len(block);size+=len(block);digest.update(block)
            observations.append((self.headers.get('Host'),self.headers.get('X-Forwarded-Proto')))
            data=json.dumps({'size':size,'digest':digest.hexdigest()}).encode()
            self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
    upstream=ThreadingHTTPServer(('127.0.0.1',0),Upstream)
    thread=threading.Thread(target=upstream.serve_forever,daemon=True);thread.start();process=None;watch=None;sockets=[]
    try:
        with tempfile.TemporaryDirectory(prefix='ha-proxy-') as folder:
            root=Path(folder);root.chmod(0o700)
            key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
            name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'Fictional HA proxy fixture')]);now=datetime.now(timezone.utc)
            cert=(x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now-timedelta(minutes=1)).not_valid_after(now+timedelta(hours=1)).add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address('127.0.0.1'))]),critical=False).sign(key,hashes.SHA256()))
            (root/'cert.pem').write_bytes(cert.public_bytes(serialization.Encoding.PEM));(root/'key.pem').write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()));(root/'key.pem').chmod(0o600)
            sockets=[]
            for _ in range(2):
                handle=socket.socket();handle.bind(('127.0.0.1',0));sockets.append(handle)
            http_port,tls_port=[handle.getsockname()[1] for handle in sockets]
            config=fixture_config(template,root,http_port,tls_port,upstream.server_port);(root/'nginx.conf').write_text(config,encoding='utf-8')
            for directory in ('client-temp','proxy-temp','fastcgi-temp','uwsgi-temp','scgi-temp'):(root/directory).mkdir(mode=0o700)
            watch=TempWatcher([root/name for name in ('client-temp','proxy-temp','fastcgi-temp','uwsgi-temp','scgi-temp')])
            command=[str(binary),'-p',str(root)+'/', '-c',str(root/'nginx.conf'),'-e','/dev/null']
            validated=subprocess.run(command+['-t'],capture_output=True,timeout=10)
            if validated.returncode:raise ValueError('nginx template validation failed')
            for handle in sockets:handle.close()
            process=subprocess.Popen(command,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
            context=ssl.create_default_context(cafile=str(root/'cert.pem'));opener=urllib.request.build_opener(NoRedirect(),urllib.request.HTTPSHandler(context=context))
            origin=f'https://127.0.0.1:{tls_port}'
            def request(url,data=None,expected=200):
                try:response=opener.open(urllib.request.Request(url,data=data),timeout=15)
                except urllib.error.HTTPError as error:response=error
                with response:
                    if response.status!=expected:raise ValueError('Unexpected proxy response status')
                    return response.read(65536),response.headers
            for _ in range(50):
                if process.poll() is not None:raise ValueError('nginx fixture startup failed')
                try:request(origin+'/ready');break
                except (urllib.error.URLError,ConnectionError):time.sleep(.1)
            else:raise ValueError('nginx fixture readiness failed')
            marker='FICTIONAL-HA-URI-MARKER'
            _,headers=request(f'http://127.0.0.1:{http_port}/callback?code='+marker,expected=308)
            if headers.get('Location')!=origin+'/callback?code='+marker:raise ValueError('HTTPS redirect mismatch')
            _,headers=request(origin+'/callback?code='+marker,expected=302)
            if headers.get('Location')!='/connected.html' or headers.get('Set-Cookie')!='__Host-ha_session=fictional; Secure; HttpOnly; Path=/; SameSite=Lax':raise ValueError('Callback headers changed')
            payload=(b'Fictional proxy body.'*((27*1024*1024)//20+1))[:27*1024*1024]
            expected_hash=hashlib.sha256(payload).hexdigest()
            for body in (payload,(payload[index:index+65536] for index in range(0,len(payload),65536))):
                raw,headers=request(origin+'/upload?profile='+marker,data=body)
                value=json.loads(raw)
                if value!={'size':len(payload),'digest':expected_hash} or headers.get('Cache-Control')!='no-store':raise ValueError('Fictional body forwarding mismatch')
            digest=hashlib.sha256();response_size=0
            with opener.open(origin+'/large-response?profile='+marker,timeout=15) as response:
                if response.status!=200 or response.headers.get('Cache-Control')!='no-store':raise ValueError('Fictional response headers changed')
                while True:
                    block=response.read(65536)
                    if not block:break
                    response_size+=len(block);digest.update(block)
            if response_size!=len(payload) or digest.hexdigest()!=expected_hash:raise ValueError('Fictional response forwarding mismatch')
            before=len(observations);request(origin+'/upload?profile='+marker,data=b'x'*(31*1024*1024),expected=413)
            if len(observations)!=before:raise ValueError('Oversized body reached upstream')
            if any(item!=('127.0.0.1','https') for item in observations):raise ValueError('Forwarded origin headers mismatch')
            upstream.shutdown();upstream.server_close();thread.join(5)
            raw,_=request(origin+'/unavailable?code='+marker,expected=502)
            if marker.encode() in raw:raise ValueError('Failure response exposed fictional request marker')
            os.killpg(process.pid,signal.SIGQUIT);process.wait(timeout=5);process=None
            if watch.changed() or any(any((root/name).iterdir()) for name in ('client-temp','proxy-temp','fastcgi-temp','uwsgi-temp','scgi-temp')):raise ValueError('Proxy temporary body write observed')
            access=(root/'inherited-access.log').read_bytes()
            if marker.encode() in access:raise ValueError('HTTP redirect logged fictional URI marker')
            if access or (root/'inherited-error.log').read_bytes():raise ValueError('Inherited request logging observed')
            allowed={'cert.pem','key.pem','nginx.conf','nginx.pid','client-temp','proxy-temp','fastcgi-temp','uwsgi-temp','scgi-temp','inherited-access.log','inherited-error.log'}
            if any(item.name not in allowed for item in root.iterdir()):raise ValueError('Unexpected proxy output file')
            return {'environment':'actual local nginx with fictional loopback upstream','template_validated':True,'certificate_and_hostname_verified':True,'http_redirect_preserved':True,'callback_location_and_cookie_preserved':True,'content_length_and_chunked_27mib_exact':True,'large_response_27mib_exact':True,'inherited_request_logs_empty':True,'oversized_body_rejected_before_upstream':True,'forwarded_origin_headers_checked':True,'upstream_failure_502_without_marker':True,'temporary_body_create_write_events':False,'unexpected_output_files':False,'application_mfa_or_storage':'not exercised','hosted_deployment':'not_run'}
    finally:
        if process is not None and process.poll() is None:
            os.killpg(process.pid,signal.SIGTERM)
            try:process.wait(timeout=5)
            except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait()
        for handle in sockets:handle.close()
        if watch is not None:watch.close()
        upstream.shutdown();upstream.server_close();thread.join(5)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--nginx',required=True);parser.add_argument('--report',required=True);args=parser.parse_args()
    template=Path('deploy/digitalocean/droplet/nginx.conf.example').read_text(encoding='utf-8')
    result=run_probe(Path(args.nginx).resolve(strict=True),template);result['template_sha256']=hashlib.sha256(template.encode()).hexdigest()
    Path(args.report).write_text(json.dumps(result,indent=2)+chr(10),encoding='utf-8');print(json.dumps(result))

if __name__=='__main__':main()
