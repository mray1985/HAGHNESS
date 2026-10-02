import hashlib
from dataclasses import replace
import unittest
from ha.connected.backup_inventory import build_inventory,verify_inventory
from ha.connected.documents import DocumentVersion
from ha.connected.domain import Scope

class Objects:
    def __init__(self):self.values={'original':b'original','correction':b'corrected'}
    def get(self,key,version):return self.values[key]

class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.objects=Objects();scope=Scope('orchard','business',2026)
        self.original=DocumentVersion('document','one',scope,'original',hashlib.sha256(b'original').hexdigest(),
            'text/plain','owner','2026-10-02T00:00:00+00:00',None,'','immutable')
        self.corrected=replace(self.original,version_id='two',object_key='correction',
            sha256=hashlib.sha256(b'corrected').hexdigest(),previous_version_id='one',reason='Correction')
        self.digest='a'*64
    def build(self,versions=None):
        return build_inventory('snapshot1',versions or [self.original,self.corrected],self.objects,self.digest)
    def test_manifest_requires_restored_database_and_archive_match(self):
        manifest=self.build()
        self.assertEqual(verify_inventory(manifest,[self.corrected,self.original],self.objects,self.digest),2)
        with self.assertRaises(ValueError):verify_inventory(manifest,[self.original],self.objects,self.digest)
        with self.assertRaises(ValueError):verify_inventory(manifest,[self.original,self.corrected],self.objects,'b'*64)
    def test_missing_or_changed_object_cannot_create_verified_inventory(self):
        self.objects.values['original']=b'altered'
        with self.assertRaises(ValueError):self.build()
        del self.objects.values['original']
        with self.assertRaises(KeyError):self.build()
    def test_correction_cannot_cross_profile_or_lose_predecessor(self):
        for corrected in (replace(self.corrected,previous_version_id='absent'),
                          replace(self.corrected,scope=Scope('cedar','other',2026)),
                          replace(self.corrected,reason='')):
            with self.subTest(corrected=corrected),self.assertRaises(ValueError):self.build([self.original,corrected])
    def test_duplicate_versions_objects_and_cyclic_chains_rejected(self):
        cases=([self.original,self.original],[self.original,replace(self.corrected,object_key='original')],
            [replace(self.original,previous_version_id='two',reason='cycle'),self.corrected])
        for versions in cases:
            with self.subTest(versions=versions),self.assertRaises(ValueError):self.build(versions)

    def test_forks_and_disconnected_roots_cannot_be_verified(self):
        fork=replace(self.corrected,version_id='three',object_key='third')
        disconnected=replace(fork,previous_version_id=None)
        for extra in (fork,disconnected):
            with self.subTest(extra=extra),self.assertRaises(ValueError):self.build([self.original,self.corrected,extra])
