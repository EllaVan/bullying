"""一致率聚合逻辑的离线单测（不调 LLM）。"""
import unittest

from psych_agent.a3_consistency import pairwise_agreement


class ConsistencyAggTests(unittest.TestCase):
    def test_stable_and_unstable_keys(self):
        run1 = [
            {'key': ('T001', 'PV05', 'U_B03_JUSTIFICATION'), 'direction': 'lower'},
            {'key': ('T002', 'PV04', 'U_B03_HARM'), 'direction': 'higher'},
        ]
        run2 = [
            {'key': ('T001', 'PV05', 'U_B03_JUSTIFICATION'), 'direction': 'lower'},
            {'key': ('T002', 'PV04', 'U_B03_HARM'), 'direction': 'lower'},
        ]
        run3 = [
            {'key': ('T001', 'PV05', 'U_B03_JUSTIFICATION'), 'direction': 'lower'},
            {'key': ('T002', 'PV04', 'U_B03_HARM'), 'direction': 'higher'},
        ]
        summary = pairwise_agreement([run1, run2, run3])
        self.assertEqual(summary['keys'], 2)
        self.assertEqual(summary['agree'], 1)
        self.assertAlmostEqual(summary['rate'], 0.5)
        by_unit = {row['unit_id']: row for row in summary['per_key']}
        self.assertTrue(by_unit['U_B03_JUSTIFICATION']['stable'])
        self.assertFalse(by_unit['U_B03_HARM']['stable'])


if __name__ == '__main__':
    unittest.main()
