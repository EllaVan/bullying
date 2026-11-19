"""角色层冲突置信折减与标签。"""
import unittest
from pathlib import Path

from psych_agent.dialogue_config import load_dialogue_config
from psych_agent.risk_engine import (
    TestRiskScoringAgent,
    apply_conflict_confidence,
    confidence_label_for,
)
from psych_agent.risk_reporter import format_confidence_label


ROOT = Path(__file__).resolve().parents[1]


class ConflictConfidenceUnitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = load_dialogue_config(ROOT)
        cls.policy = cls.cfg.confidence_policy

    def test_apply_conflict_lowers_confidence_and_tags(self):
        value, share, factor, label, tag = apply_conflict_confidence(0.9, 1.0, self.policy)
        self.assertAlmostEqual(share, 1.0)
        self.assertAlmostEqual(factor, 1.0 - self.policy['conflict_penalty'])
        self.assertLess(value, 0.9)
        self.assertEqual(tag, 'conflict')
        self.assertIn(label, ('high', 'medium', 'low'))

    def test_no_conflict_keeps_factor_one(self):
        value, share, factor, label, tag = apply_conflict_confidence(0.9, 0.0, self.policy)
        self.assertEqual(share, 0.0)
        self.assertEqual(factor, 1.0)
        self.assertEqual(value, 0.9)
        self.assertIsNone(tag)
        self.assertEqual(label, 'high')

    def test_label_thresholds(self):
        self.assertEqual(confidence_label_for(0.8, self.policy), 'high')
        self.assertEqual(confidence_label_for(0.6, self.policy), 'medium')
        self.assertEqual(confidence_label_for(0.2, self.policy), 'low')

    def test_format_confidence_label(self):
        self.assertEqual(format_confidence_label({'confidence_label': 'medium', 'confidence_tag': 'conflict'}), '中·冲突')
        self.assertEqual(format_confidence_label({'confidence_label': 'high'}), '高')


class ConflictConfidenceAssessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = load_dialogue_config(ROOT)

    def _profile(self, with_conflict=True):
        variables = []
        for vid in self.cfg.base.variables:
            facets = [{
                'facet_id': f'{vid}_f1', 'name': 't', 'unit_ids': [], 'weight': 1.0,
                'value': 0.8, 'status': 'resolved_conflict' if (with_conflict and vid == 'PV02') else 'observed',
                'conflict_audit': {'conflict_type': 'cross_frame'} if (with_conflict and vid == 'PV02') else None,
                'score_weight_factor': 1.0,
            }]
            variables.append({
                'variable_id': vid, 'value': 0.8, 'confidence': 0.9,
                'confidence_mode': 'engineering_facet_coverage_intensity',
                'groups': [{'evidence_ids': ['E1'], 'source_item_ids': ['A01'],
                            'scenario_ids': ['S01'], 'reference_frame': 'habitual_self_report',
                            'directions': ['higher'], 'unit_id': 'U_x', 'group_id': 'G1'}],
                'facets': facets,
            })
        return {
            'schema_version': '0.6.1', 'session_id': 'S_TEST', 'profile_id': 'P_TEST',
            'config_set_id': self.cfg.config_set_id, 'synthetic': True,
            'variables': variables,
            'evidence_ledger': [{'evidence_id': 'E1', 'variable_id': 'PV02', 'turn_id': 'T001',
                                 'direction': 'higher', 'quote': 'x', 'reference_frame': 'habitual_self_report',
                                 'source_item_ids': ['A01'], 'subject': 'self'}],
            'coverage': {
                'coverage_fraction': 0.9, 'answered_turns': 10,
                'response_quality': {
                    'eligible_response_turns': 10, 'low_information_turns': 0,
                    'a3_fallback_turns': 0, 'brief_response_turns': 0,
                    'brief_response_max_characters': 6, 'brief_response_rate': 0.0,
                    'explicit_skip_turns': 0, 'alternate_probe_scheduled_turns': 0,
                    'warning_triggered': False,
                },
            },
            'experience': {'events': []},
            'conflict_resolutions': ([{'variable_id': 'PV02'}] if with_conflict else []),
            'scenario_instances': [{'scenario_id': 'S01', 'condition_id': 'base',
                                   'facts': {'form': 'physical'}}],
        }

    def test_assess_tags_conflict_and_lowers_confidence(self):
        agent = TestRiskScoringAgent(self.cfg)
        with_c = agent.assess(self._profile(True))
        without = agent.assess(self._profile(False))
        bully_c = next(r for r in with_c['roles'] if r['role'] == 'bully')
        bully_n = next(r for r in without['roles'] if r['role'] == 'bully')
        self.assertEqual(bully_c['confidence_tag'], 'conflict')
        self.assertGreater(bully_c['conflict_share'], 0)
        self.assertLess(bully_c['confidence'], bully_n['confidence'])
        self.assertIsNone(bully_n['confidence_tag'])
        self.assertEqual(bully_n['conflict_share'], 0.0)
        # 分数轴：有冲突时仍可有分，不因标签清空
        self.assertIsNotNone(bully_c['score'])


if __name__ == '__main__':
    unittest.main()
