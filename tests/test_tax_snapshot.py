import unittest
from ha.connected.tax_snapshot import encode_snapshot, decode_snapshot


class TaxSnapshotTests(unittest.TestCase):
    def snapshot(self):
        return {'year': '2025', 'profile': {'firstName': 'Fictional', 'ssn': '000-00-0000'},
                'forms': [{'layout': 'standard', 'box1': '001.20', 'box2': '',
                           'states': [{'state': 'LA', 'tax': ''}, {'state': 'TX'}],
                           'codes': [{'code': 'D', 'amount': '000.50'}],
                           'checks': {'retirement': True}},
                          {'type': '1099-R', 'layout': 'stacked', 'box2a': '',
                           'rolled_over': 'unsure', 'states': [{}]}],
                'active': 1, 'stateAnswers': {'state-move': 'Yes'}}
    def test_partial_entries_roundtrip_without_changing_text_or_blank_amounts(self):
        value = self.snapshot()
        self.assertEqual(decode_snapshot(encode_snapshot(value, 2025), 2025), value)
        self.assertNotIn(b'estimated_tax', encode_snapshot(value, 2025))
    def test_interest_document_roundtrip_preserves_exact_boxes_and_state_rows(self):
        value=self.snapshot()
        value['forms'].append({'type':'1099-INT','layout':'stacked','box1':'000.50',
            'box9':'','box12':'0.00','box14':'fictional-CUSIP','corrected':False,
            'special_treatment':'unsure','states':[{'state':'LA','id':'fictional','tax':'0.00'}]})
        self.assertEqual(decode_snapshot(encode_snapshot(value,2025),2025),value)

    def test_reject_wrong_year_computed_values_unknown_fields_and_unbounded_data(self):
        for value in ({**self.snapshot(), 'year': '2026'},
                      {**self.snapshot(), 'estimate': {'refund': 100}},
                      {**self.snapshot(), 'profile': {'__proto__': 'bad'}},
                      {**self.snapshot(), 'forms': [{'box1': 1.2}]},
                      {**self.snapshot(), 'forms': [{'type': '1099-OID'}]},
                      {**self.snapshot(), 'forms': [{'employeeName': 'x' * 2001}]},
                      {**self.snapshot(), 'active': True}):
            with self.subTest(value=value), self.assertRaises(ValueError): encode_snapshot(value, 2025)
    def test_decode_rejects_duplicate_keys_corruption_and_size(self):
        for data in (b'bad', b'x' * 262145,
                     b'{"format":"ha-tax-input-v1","format":"ha-tax-input-v1","input":{}}'):
            with self.assertRaises(ValueError): decode_snapshot(data, 2025)
    def test_empty_draft_is_valid_but_invalid_active_index_rejected(self):
        value = {'year': '2025', 'profile': {}, 'forms': [], 'active': 0, 'stateAnswers': {}}
        self.assertEqual(decode_snapshot(encode_snapshot(value, 2025), 2025), value)
        value['active'] = 1
        with self.assertRaises(ValueError): encode_snapshot(value, 2025)

    def test_equivalent_key_order_has_identical_snapshot_bytes(self):
        value = self.snapshot()
        reordered = dict(reversed(list(value.items())))
        reordered['profile'] = dict(reversed(list(value['profile'].items())))
        self.assertEqual(encode_snapshot(value, 2025), encode_snapshot(reordered, 2025))
