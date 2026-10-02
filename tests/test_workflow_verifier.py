import unittest
from scripts.verify_connected_workflow import validate_fixture_config,check_draft

class WorkflowVerifierTests(unittest.TestCase):
    def test_nonisolated_database_configuration_is_rejected(self):
        for config in ({'synthetic_only':False,'dsn':'host=127.0.0.1 port=55432 user=ha_test_admin dbname=postgres'},
                       {'synthetic_only':True,'dsn':'host=remote.example port=55432 user=ha_test_admin dbname=postgres'},
                       {'synthetic_only':True,'dsn':'host=127.0.0.1 port=5432 user=ha_test_admin dbname=postgres'}):
            with self.assertRaises(ValueError):validate_fixture_config(config)

    def test_wrong_profit_or_filing_permission_cannot_pass_workflow(self):
        expected={'income_minor':150000,'expense_minor':32000,'book_profit_minor':118000,
            'reserve_scenario_minor':37500,'owner_payments_recorded_minor':10000,
            'owner_payments_confirmed_minor':0,'missing_receipts':['advertising'],
            'tax_liability_minor':None,'may_prepare_return':False,'filing_authorized':False}
        check_draft(expected)
        for name,value in (('book_profit_minor',120000),('filing_authorized',True),('owner_payments_confirmed_minor',10000)):
            with self.assertRaises(ValueError):check_draft({**expected,name:value})
