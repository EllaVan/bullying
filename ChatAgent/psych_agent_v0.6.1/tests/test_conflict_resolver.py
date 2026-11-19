"""冲突消解与强度映射单元测试。"""
import unittest
from pathlib import Path

from psych_agent.conflict_resolver import (
    classify_conflict,
    intensity_to_support,
    resolve_facet,
    summarize_with_conflicts,
)
from psych_agent.dialogue_config import load_dialogue_config


ROOT = Path(__file__).resolve().parents[1]


class FakeScoring(dict):
    pass


class ConflictResolverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = load_dialogue_config(ROOT)

    def test_intensity_maps_between_zero_and_one(self):
        scoring = self.cfg.variable_scoring
        self.assertGreater(intensity_to_support('higher', 5, scoring), 0.9)
        self.assertLess(intensity_to_support('lower', 5, scoring), 0.1)
        mid_h = intensity_to_support('higher', 3, scoring)
        mid_l = intensity_to_support('lower', 3, scoring)
        self.assertGreater(mid_h, 0.4)
        self.assertLess(mid_l, 0.6)
        self.assertNotEqual(mid_h, 1.0)
        self.assertNotEqual(mid_l, 0.0)

    def test_same_group_bidirectional_soft_midpoint(self):
        groups = [{
            'group_id': 'G1', 'unit_id': 'U_B05_CONSEQUENCES', 'facet': 'x',
            'directions': ['higher', 'lower'], 'evidence_ids': ['E1', 'E2'],
            'source_item_ids': ['B05'], 'reference_frame': 'general_belief',
            'scenario_ids': ['S03'], 'condition_id': 'base', 'observation_ids': ['O1'],
        }]
        evidence = {
            'E1': {'direction': 'higher', 'intensity': 3, 'reference_frame': 'general_belief',
                   'quote': '不太好', 'turn_id': 'T021', 'source_item_ids': ['B05']},
            'E2': {'direction': 'lower', 'intensity': 3, 'reference_frame': 'general_belief',
                   'quote': '还是不太好', 'turn_id': 'T021', 'source_item_ids': ['B05']},
        }
        spec = {'facet_id': 'F', 'name': 't', 'weight': 1.0, 'unit_ids': ['U_B05_CONSEQUENCES']}
        row = resolve_facet(groups, 'PV05', spec, self.cfg, evidence_by_id=evidence)
        self.assertEqual(row['status'], 'resolved_conflict')
        self.assertIsNotNone(row['value'])
        self.assertAlmostEqual(row['value'], 0.5, delta=0.15)
        # 冲突不降低计分权重（严格计入）
        self.assertEqual(row['score_weight_factor'], 1.0)
        self.assertEqual(row['conflict_audit']['conflict_type'], 'same_group_bidirectional')
        self.assertIn('同句双命中', row['conflict_audit']['cause'])
        self.assertEqual(set(row['evidence_ids']), {'E1', 'E2'})
        # 冲突两侧应写明证据原文
        quotes = {side['quote'] for side in row['conflict_audit']['sides']}
        self.assertEqual(quotes, {'不太好', '还是不太好'})
        for side in row['conflict_audit']['sides']:
            self.assertIn(side['evidence_id'], {'E1', 'E2'})
            self.assertEqual(side['turn_id'], 'T021')

    def test_prefer_real_event_over_hypothetical(self):
        groups = [
            {
                'group_id': 'G_hyp', 'unit_id': 'U_A03_RETALIATION', 'facet': '报复',
                'directions': ['higher'], 'evidence_ids': ['EH'],
                'source_item_ids': ['A03'], 'reference_frame': 'hypothetical_intent',
                'scenario_ids': ['S01'], 'condition_id': 'base', 'observation_ids': ['O1'],
            },
            {
                'group_id': 'G_real', 'unit_id': 'U_A03_RETALIATION', 'facet': '报复',
                'directions': ['lower'], 'evidence_ids': ['ER'],
                'source_item_ids': ['A03'], 'reference_frame': 'real_event_self_report',
                'scenario_ids': ['S01'], 'condition_id': 'base', 'observation_ids': ['O2'],
            },
        ]
        evidence = {
            'EH': {'direction': 'higher', 'intensity': 2, 'reference_frame': 'hypothetical_intent'},
            'ER': {'direction': 'lower', 'intensity': 5, 'reference_frame': 'real_event_self_report'},
        }
        spec = {'facet_id': 'F', 'name': '报复意向', 'weight': 1.0, 'unit_ids': ['U_A03_RETALIATION']}
        row = resolve_facet(groups, 'PV02', spec, self.cfg, evidence_by_id=evidence)
        self.assertEqual(row['status'], 'resolved_conflict')
        # 真实经历 lower 应把消解值拉向低端
        self.assertLess(row['value'], 0.45)
        self.assertEqual(classify_conflict([
            {'direction': 'higher', 'group_id': 'G_hyp', 'reference_frame': 'hypothetical_intent', 'scenario_ids': ('S01',)},
            {'direction': 'lower', 'group_id': 'G_real', 'reference_frame': 'real_event_self_report', 'scenario_ids': ('S01',)},
        ]), 'cross_frame')

    def test_conflict_does_not_drop_facet_from_variable_mean(self):
        # 构造：一面冲突软中点，一面 observed=1.0；若旧逻辑丢弃冲突，均值会变成 1.0
        unit_conflict = self.cfg.facet_config['variables']['PV05'][0]['unit_ids'][0]
        unit_ok = self.cfg.facet_config['variables']['PV05'][1]['unit_ids'][0]
        groups = [
            {
                'group_id': 'Gc', 'unit_id': unit_conflict, 'facet': 'c',
                'directions': ['higher', 'lower'], 'evidence_ids': ['E1', 'E2'],
                'source_item_ids': ['X'], 'reference_frame': 'general_belief',
                'scenario_ids': ['S03'], 'condition_id': 'base', 'observation_ids': ['O1'],
            },
            {
                'group_id': 'Go', 'unit_id': unit_ok, 'facet': 'o',
                'directions': ['higher'], 'evidence_ids': ['E3'],
                'source_item_ids': ['Y'], 'reference_frame': 'general_belief',
                'scenario_ids': ['S03'], 'condition_id': 'base', 'observation_ids': ['O2'],
            },
        ]
        evidence = {
            'E1': {'direction': 'higher', 'intensity': 3, 'reference_frame': 'general_belief'},
            'E2': {'direction': 'lower', 'intensity': 3, 'reference_frame': 'general_belief'},
            'E3': {'direction': 'higher', 'intensity': 3, 'reference_frame': 'general_belief'},
        }
        facets, value, confidence = summarize_with_conflicts(groups, 'PV05', self.cfg, evidence_by_id=evidence)
        statuses = {f['facet_id']: f['status'] for f in facets if f['status'] != 'unknown'}
        self.assertIn('resolved_conflict', statuses.values())
        self.assertIsNotNone(value)
        self.assertLess(value, 1.0)  # 冲突面参与拉低，不再被剔除成满分
        self.assertLess(confidence, 1.0)


if __name__ == '__main__':
    unittest.main()
