"""Fail-closed ClamD INSTREAM scanner over an operator-protected Unix socket.

The daemon, signatures, scan-limit policy and socket permissions must be managed
and verified separately. No network TCP endpoint or plaintext file is created.
"""
import math
from pathlib import PurePosixPath
import socket
import struct
import time
from .documents import MAX_BYTES

class ClamDScanner:
    def __init__(self,socket_path,timeout=10,socket_factory=None):
        if (not isinstance(socket_path,str) or not PurePosixPath(socket_path).is_absolute()
                or '\0' in socket_path or len(socket_path.encode('utf-8'))>100):
            raise ValueError('Protected absolute Unix socket required')
        if type(timeout) not in (int,float) or not math.isfinite(timeout) or not 0<timeout<=60:
            raise ValueError('Scanner deadline must be between zero and 60 seconds')
        self.path,self.timeout=socket_path,timeout
        self.socket_factory=socket_factory or (lambda:socket.socket(socket.AF_UNIX,socket.SOCK_STREAM))

    def __call__(self,data,mime):
        if not isinstance(data,bytes) or not 0<len(data)<=MAX_BYTES:return False
        deadline=time.monotonic()+self.timeout
        def limit(sock):
            remaining=deadline-time.monotonic()
            if remaining<=0:raise TimeoutError('Scanner deadline exceeded')
            sock.settimeout(remaining)
        try:
            with self.socket_factory() as sock:
                limit(sock);sock.connect(self.path)
                limit(sock);sock.sendall(b'zINSTREAM\0')
                for offset in range(0,len(data),65536):
                    chunk=data[offset:offset+65536]
                    limit(sock);sock.sendall(struct.pack('!I',len(chunk))+chunk)
                limit(sock);sock.sendall(bytes(4))
                reply=bytearray()
                while True:
                    limit(sock);part=sock.recv(4097-len(reply))
                    if not part:break
                    reply.extend(part)
                    if len(reply)>4096:return False
                # No suffix matching: errors, multiple records and truncation fail.
                return bytes(reply)==b'stream: OK\0'
        except OSError:
            return False
