import unittest
from ha.returns import estimate_w2


def interest(**changes):
    return {'box1': '500', 'box3': '100', 'box4': '60', 'box8': '800',
            'special_treatment': 'no', **changes}


class InterestPreviewTests(unittest.TestCase):
    def test_interest_and_withholding_are_separate_from_wages_and_exempt_interest(self):
        result = estimate_w2({'tax_year': '2025', 'w2s': [{'box1': '45000', 'box2': '5200'}],
                              'interest_forms': [interest()]})
        self.assertEqual(result['wages'], 45000)
        self.assertEqual(result['taxable_interest'], 600)
        self.assertEqual(result['tax_exempt_interest'], 800)
        self.assertEqual(result['income'], 45600)
        self.assertEqual(result['withholding'], 5260)
        self.assertEqual(result['estimated_tax'], 3343.5)
        self.assertEqual(result['refund'], 1916.5)
        self.assertFalse(result['needs_review'])
        self.assertFalse(result['may_prepare_return'])

    def test_multiple_interest_only_documents_do_not_require_wages(self):
        result = estimate_w2({'interest_forms': [interest(box1='100', box3='0'),
                                                interest(box1='200', box3='0')]})
        self.assertEqual(result['taxable_interest'], 300)
        self.assertEqual(result['tax_exempt_interest'], 1600)
        self.assertEqual(result['withholding'], 120)
        self.assertFalse(result['incomplete'])

    def test_special_boxes_and_unknown_answers_hold_tax_and_refund(self):
        for changes in ({'box2': '10'}, {'box5': '10'}, {'box6': '10'}, {'box7': 'Canada'},
                        {'box9': '10'}, {'box10': '10'}, {'box11': '10'},
                        {'box12': '10'}, {'box13': '10'}, {'corrected': True},
                        {'special_treatment': ''}, {'special_treatment': 'yes'}):
            with self.subTest(changes=changes):
                result = estimate_w2({'interest_forms': [interest(**changes)]})
                self.assertTrue(result['needs_review'])
                self.assertIsNone(result['estimated_tax'])
                self.assertIsNone(result['refund'])
                self.assertIsNone(result['balance_due'])
                self.assertEqual(result['review_items'][0]['form'], '1099-INT')

    def test_schedule_b_threshold_uses_aggregate_taxable_interest(self):
        result = estimate_w2({'interest_forms': [interest(box1='750', box3='0'),
                                                interest(box1='750.01', box3='0')]})
        self.assertTrue(result['needs_review'])
        self.assertTrue(any('Schedule B' in reason for item in result['review_items']
                            for reason in item['reasons']))

    def test_invalid_interest_inputs_are_rejected(self):
        for changes in ({'box1': '-1'}, {'box3': 'NaN'}, {'box4': '1.001'},
                        {'box8': '1000000001'}, {'corrected': 'yes'},
                        {'special_treatment': 'invalid'}, {'box7': 1}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                estimate_w2({'interest_forms': [interest(**changes)]})
        for forms in (None, {}, [interest()] * 101, ['not a form']):
            with self.subTest(forms_type=type(forms)), self.assertRaises(ValueError):
                estimate_w2({'interest_forms': forms})
