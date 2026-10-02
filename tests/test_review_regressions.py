"""Independent regressions from the October 2 external review."""
import unittest
from ha.engine import federal


class ReviewRegressions(unittest.TestCase):
    def test_no_earned_income_cannot_receive_eitc(self):
        for agi in (0, 5000):
            result = federal.compute(2025, 'single', agi, earned_income=0)
            self.assertEqual(result['credits']['eitc']['credit'], 0)

    def test_unsupported_capital_loss_is_rejected(self):
        with self.assertRaises(ValueError):
            federal.compute(2025, 'single', 80000, net_capital_gain=-3000)

    def test_eitc_formula_phases_in_on_earned_income_only(self):
        from decimal import Decimal
        from ha.rules import year_block
        for year in (2024, 2025, 2026):
            for children, expected in enumerate(('0.08','0.34','0.40','0.45')):
                with self.subTest(year=year, children=children):
                    result = federal.eitc(Decimal('1'),Decimal('0'),children,Decimal('0'),year_block(year),'single')
                    self.assertEqual(result['credit'],Decimal(expected))

    def test_eitc_low_earnings_do_not_receive_maximum_despite_higher_agi(self):
        result = federal.compute(2025,'single',5000,earned_income=100)
        self.assertEqual(result['credits']['eitc']['credit'],7.65)

    def test_eitc_plateau_phaseout_and_ceiling(self):
        from decimal import Decimal as D
        from ha.rules import year_block
        # Rev Proc 2024-40 section 3.06; formula estimate, not EIC table amounts.
        for income,expected in ((10000,'649'),(10620,'649'),(15000,'313.93'),(19104,'0')):
            result=federal.eitc(D(income),D(income),0,D(0),year_block(2025),'single')
            self.assertEqual(result['credit'],D(expected))

    def test_joint_investment_limit_is_not_doubled(self):
        result=federal.compute(2025,'mfj',10000,investment_income=11951)
        self.assertEqual(result['credits']['eitc']['credit'],0)

    def test_formula_credit_never_authorizes_return(self):
        result=federal.compute(2025,'single',1)
        self.assertFalse(result['verification']['may_prepare_return'])
        self.assertFalse(result['credits']['eitc']['eligibility_checked'])
