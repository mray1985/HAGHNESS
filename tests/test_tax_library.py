import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from ha.ai.library import TaxLibrary

class TaxLibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'library.sqlite3'
        with sqlite3.connect(self.path) as conn:
            conn.execute('CREATE VIRTUAL TABLE passages USING fts5(id UNINDEXED,title UNINDEXED,url UNINDEXED,page UNINDEXED,year UNINDEXED,text)')
            conn.execute('INSERT INTO passages VALUES (?,?,?,?,?,?)',('one','Rental','https://www.irs.gov/example',1,'2025','A residence rented for fewer than 15 days excludes rental receipts.'))
        conn.close()
    def tearDown(self):self.temp.cleanup()
    def test_year_filter_does_not_mix_rules(self):
        library=TaxLibrary(self.path)
        self.assertEqual(library.retrieve('rented residence',2026),[])
        self.assertEqual(len(library.retrieve('rented residence',2025)),1)
    def test_generated_citation_must_match_retrieved_source(self):
        library=TaxLibrary(self.path,transport=lambda payload:dict(answer='Explanation',supported=True,source_ids=['invented']))
        self.assertIsNone(library.answer('rented residence',2025))
    def test_supported_explanation_remains_unverified(self):
        library=TaxLibrary(self.path,transport=lambda payload:dict(answer='Explanation',supported=True,source_ids=['one']))
        result=library.answer('rented residence',2025)
        self.assertFalse(result['verified']);self.assertFalse(result['may_prepare_return'])
    def test_excerpt_mode_never_calls_model(self):
        def forbidden(payload):raise AssertionError('Model must not run in excerpt mode')
        result=TaxLibrary(self.path,transport=forbidden,generate=False).answer('rented residence',2025)
        self.assertEqual(result['confidence'],'source_excerpt_unverified')
        self.assertFalse(result['may_prepare_return'])
