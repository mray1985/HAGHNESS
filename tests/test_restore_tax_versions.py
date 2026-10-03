import copy
import unittest
from scripts import verify_database_restore as probe


class SavedTaxRestoreTests(unittest.TestCase):
    def fixture(self):
        original={'year':'2026','profile':{},'forms':[{'type':'1099-INT','box1':'000.50','box9':'','corrected':False,'states':[{'state':'LA','tax':'0'},{'state':'TX','tax':''}]}],'active':0,'stateAnswers':{}}
        current=copy.deepcopy(original);current['forms'][0]['box1']='500.00';current['forms'][0]['corrected']=True
        expected=[(original,{'snapshot_id':'original','reason':''}),(current,{'snapshot_id':'current','reason':'Correct interest'})]
        class Service:
            def __init__(self): self.versions=copy.deepcopy(expected)
            def open(self,owner,scope,snapshot=None):
                value=next((v for v in self.versions if v[1]['snapshot_id']==snapshot),self.versions[-1])
                return {'input':value[0],'snapshot':value[1]}
            def history(self,owner,scope):return [v[1] for v in self.versions]
        return Service(),expected

    def test_exact_original_current_and_metadata(self):
        service,expected=self.fixture()
        self.assertEqual(probe.verify_saved_tax_versions(service,None,None,expected),expected[-1][0])

    def test_changed_recovery_amount_checkbox_state_metadata_or_history_is_rejected(self):
        for mutation in ('amount','checkbox','state','reason','history','original'):
            with self.subTest(mutation=mutation):
                service,expected=self.fixture()
                if mutation=='amount':service.versions[-1][0]['forms'][0]['box1']='500'
                elif mutation=='checkbox':service.versions[-1][0]['forms'][0]['corrected']=False
                elif mutation=='state':service.versions[-1][0]['forms'][0]['states'].pop()
                elif mutation=='reason':service.versions[-1][1]['reason']='Changed'
                elif mutation=='history':service.versions.append(copy.deepcopy(service.versions[-1]))
                else:service.versions[0][0]['forms'][0]['box1']='0.50'
                with self.assertRaises(ValueError):probe.verify_saved_tax_versions(service,None,None,expected)
