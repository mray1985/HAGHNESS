import unittest
from ha.returns import estimate_w2


def pension(**changes):
    return {'box1':'10000','box2a':'10000','box4':'2000','box7':'7',
            'taxable_not_determined':False,'ira':False,'rolled_over':'no',
            'special_treatment':'no',**changes}


class RetirementPreviewTests(unittest.TestCase):
    def test_normal_pension_added_to_wages_with_separate_withholding(self):
        result=estimate_w2({'tax_year':'2025','w2s':[{'box1':45000,'box2':5200}],
                            'retirement_forms':[pension()]})
        self.assertEqual(result['retirement_income'],10000)
        self.assertEqual(result['income'],55000)
        self.assertEqual(result['withholding'],7200)
        self.assertEqual(result['estimated_tax'],4471.5)
        self.assertEqual(result['refund'],2728.5)
        self.assertFalse(result['needs_review'])
        self.assertFalse(result['may_prepare_return'])

    def test_retirement_only_return_does_not_require_w2(self):
        result=estimate_w2({'retirement_forms':[pension(box1=25000,box2a=25000,box4=2500)]})
        self.assertFalse(result['incomplete'])
        self.assertEqual(result['refund'],1575)

    def test_unknown_taxable_amount_never_assumes_gross_is_taxable(self):
        result=estimate_w2({'retirement_forms':[pension(box2a='',taxable_not_determined=True)]})
        self.assertTrue(result['needs_review'])
        self.assertIsNone(result['estimated_tax'])
        self.assertIsNone(result['refund'])
        self.assertTrue(result['review_items'])

    def test_special_codes_ira_and_missing_rollover_answers_hold_estimate(self):
        for changes in ({'box7':'G'},{'box7':'1'},{'box7':'Q'},{'box7':'7D'},
                        {'ira':True},{'rolled_over':'yes'},{'rolled_over':''},
                        {'special_treatment':'yes'},{'box3':100},{'box8percent':10},{'box9a':50},{'box11':2020}):
            with self.subTest(changes=changes):
                result=estimate_w2({'retirement_forms':[pension(**changes)]})
                self.assertTrue(result['needs_review']);self.assertIsNone(result['balance_due'])

    def test_invalid_retirement_values_and_boolean_flags_are_rejected(self):
        for changes in ({'box2a':10001},{'box4':-1},{'box1':'NaN'},
                        {'taxable_not_determined':'false'},{'ira':[]},{'box7':7}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                estimate_w2({'retirement_forms':[pension(**changes)]})

    def test_state_amounts_do_not_change_federal_income(self):
        result=estimate_w2({'retirement_forms':[pension(states=[{'distribution':10000},{'distribution':10000}])]})
        self.assertEqual(result['income'],10000)

