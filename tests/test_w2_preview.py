from decimal import Decimal
import unittest
from ha.returns import estimate_w2


class W2PreviewTests(unittest.TestCase):
    def test_2025_single_wages_and_withholding(self):
        result = estimate_w2({'tax_year':'2025','filing_status':'single','w2s':[{'box1':'45000','box2':'5200'}]})
        self.assertEqual(result['standard_deduction'],15750)
        self.assertEqual(result['taxable_income'],29250)
        self.assertEqual(result['estimated_tax'],3271.50)
        self.assertEqual(result['refund'],1928.50)
        self.assertFalse(result['may_prepare_return'])

    def test_multiple_w2s_aggregate_without_double_counting_state_wages(self):
        result = estimate_w2({'tax_year':'2025','w2s':[{'box1':30000,'box2':1000,'states':[{'wages':30000}]},{'box1':15000,'box2':2000}]})
        self.assertEqual(result['wages'],45000)
        self.assertEqual(result['withholding'],3000)
        self.assertEqual(result['balance_due'],271.50)

    def test_blank_fields_are_incomplete_and_zero_not_refund_ready(self):
        result=estimate_w2({'w2s':[{'box1':'','box2':''}]})
        self.assertTrue(result['incomplete'])
        self.assertEqual(result['refund'],0)

    def test_invalid_or_unbounded_amounts_are_rejected(self):
        for value in ('NaN','Infinity','-1',True,[], '1000000001','1.001','1e-999999'):
            with self.subTest(value=value),self.assertRaises(ValueError):
                estimate_w2({'w2s':[{'box1':value}]})

    def test_support_is_explicitly_single_filer_only(self):
        with self.assertRaises(ValueError):estimate_w2({'filing_status':'mfj','w2s':[]})

    def test_preview_and_legacy_brackets_share_updated_2025_deductions(self):
        from ha.engine.federal import explain_brackets
        from ha.rules import year_block
        self.assertEqual(year_block('2025')['standard_deduction'],
                         {'single':15750,'mfj':31500,'mfs':15750,'hoh':23625,'qss':31500})
        preview=estimate_w2({'tax_year':'2025','w2s':[{'box1':45000,'box2':0}]})
        self.assertEqual(preview['standard_deduction'],explain_brackets('2025','single')['standard_deduction'])
