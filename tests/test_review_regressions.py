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
