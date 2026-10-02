import struct
import unittest
from io import BytesIO
from unittest.mock import patch
from ha.connected.scanner import ClamDScanner

class Socket:
    def __init__(self,replies):self.replies=iter(replies);self.sent=[];self.closed=False
    def __enter__(self):return self
    def __exit__(self,*args):self.closed=True
    def settimeout(self,value):self.timeout=value
    def connect(self,path):self.path=path
    def sendall(self,data):self.sent.append(data)
    def recv(self,size):return next(self.replies,b'')

class ScannerTests(unittest.TestCase):
    def scanner(self,replies):
        sock=Socket(replies)
        return ClamDScanner('/run/clamav/clamd.sock',socket_factory=lambda:sock),sock

    def test_exact_clean_fragmented_result_and_protocol(self):
        scanner,sock=self.scanner([b'stream:',b' OK\0',b''])
        self.assertIs(scanner(b'fictional receipt','text/plain'),True)
        self.assertEqual(b''.join(sock.sent),b'zINSTREAM\0'+struct.pack('!I',17)+b'fictional receipt'+bytes(4))
        self.assertTrue(sock.closed)

    def test_infected_error_incomplete_extra_and_unbounded_replies_reject(self):
        for replies in ([b'stream: Eicar-Signature FOUND\0'],[b'stream: limit ERROR\0'],
                        [b'stream: OK'],[b'stream: OK\0stream: ERROR\0'],
                        [b'x'*4097],[b''],[b'garbage OK\0']):
            scanner,sock=self.scanner(replies)
            with self.subTest(replies=replies):self.assertIs(scanner(b'x','text/plain'),False)
            self.assertTrue(sock.closed)

    def test_transport_failure_and_invalid_document_reject(self):
        scanner,sock=self.scanner([])
        with patch.object(sock,'connect',side_effect=OSError('unavailable')):
            self.assertIs(scanner(b'x','text/plain'),False)
        self.assertTrue(sock.closed)
        for data in (b'', 'x', b'x'*21*1024*1024):
            self.assertIs(scanner(data,'text/plain'),False)

    def test_total_deadline_cannot_be_extended_by_partial_replies(self):
        scanner,sock=self.scanner([b'stream:',b' OK\0'])
        with patch('ha.connected.scanner.time.monotonic',side_effect=[0,0,0,11]):
            self.assertIs(scanner(b'x','text/plain'),False)
        self.assertTrue(sock.closed)

    def test_remote_or_relative_paths_and_invalid_timeout_reject(self):
        for path in ('host:3310','relative.sock','/run/bad\0sock'):
            with self.assertRaises(ValueError):ClamDScanner(path)
        for timeout in (0,-1,61,float('nan'),True):
            with self.assertRaises(ValueError):ClamDScanner('/run/clamav/clamd.sock',timeout=timeout)

    def test_scanner_failure_prevents_object_and_metadata_publication(self):
        from tests.test_connected_documents import DocumentTests
        from ha.connected.documents import Documents
        fixture=DocumentTests();fixture.setUp()
        scanner,sock=self.scanner([b'stream: threat FOUND\0'])
        docs=Documents(fixture.repo,fixture.objects,scanner)
        with self.assertRaises(ValueError):docs.upload(fixture.owner,fixture.scope,BytesIO(b'fictional'),'text/plain','blocked')
        self.assertEqual(fixture.objects.data,{})
        self.assertEqual(fixture.repo.versions,{})
