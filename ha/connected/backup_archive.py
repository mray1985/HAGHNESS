"""Authenticated streaming backup files; keys are supplied separately.

Database dumps contain private records even when document objects are encrypted.
Never publish a partial archive or restore over an existing file.
"""
import os
import struct
import tempfile
from contextlib import ExitStack
from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

HEADER=b"HABACKUP1"
CHUNK=1024*1024
FRAME=struct.Struct(">BI")

def _transform(source,target,key,decrypt):
    if not isinstance(key,bytes) or len(key)!=32:
        raise ValueError("A separate 32-byte recovery key is required")
    cipher=AESGCM(key)
    target=Path(target)
    temporary=None
    try:
        with ExitStack() as stack:
            reader=stack.enter_context(open(source,"rb"))
            descriptor,name=tempfile.mkstemp(prefix=".ha-backup-",dir=target.parent)
            temporary=Path(name)
            writer=stack.enter_context(os.fdopen(descriptor,"wb"))
            if decrypt:
                header=reader.read(len(HEADER)+8)
                if len(header)!=len(HEADER)+8 or not header.startswith(HEADER):
                    raise ValueError("Invalid backup header")
            else:
                header=HEADER+os.urandom(8)
                writer.write(header)
            index=0
            while True:
                if index>=2**32:
                    raise ValueError("Backup exceeds frame limit")
                nonce=header[-8:]+index.to_bytes(4,"big")
                if decrypt:
                    raw=reader.read(FRAME.size)
                    if len(raw)!=FRAME.size:
                        raise ValueError("Truncated backup")
                    final,length=FRAME.unpack(raw)
                    if final not in (0,1) or not 16<=length<=CHUNK+16:
                        raise ValueError("Invalid backup frame")
                    encrypted=reader.read(length)
                    if len(encrypted)!=length:
                        raise ValueError("Truncated backup frame")
                    data=cipher.decrypt(nonce,encrypted,header+index.to_bytes(4,"big")+raw)
                    if final:
                        if data or reader.read(1):
                            raise ValueError("Invalid backup ending")
                        break
                    if not data:
                        raise ValueError("Empty backup data frame")
                    writer.write(data)
                else:
                    data=reader.read(CHUNK)
                    final=int(not data)
                    raw=FRAME.pack(final,len(data)+16)
                    writer.write(raw)
                    writer.write(cipher.encrypt(nonce,data,header+index.to_bytes(4,"big")+raw))
                    if final:break
                index+=1
            writer.flush()
            os.fsync(writer.fileno())

        # Hard-link publication is atomic and refuses an existing destination.
        # Temporary and destination are siblings on the same filesystem.
        os.link(temporary,target)
    finally:
        if temporary is not None:temporary.unlink(missing_ok=True)

def encrypt_backup(source,target,key):
    """Create a new authenticated archive, refusing existing targets."""
    _transform(source,target,key,False)

def decrypt_backup(source,target,key):
    """Recover into a new file; remove partial output on authentication failure."""
    _transform(source,target,key,True)
