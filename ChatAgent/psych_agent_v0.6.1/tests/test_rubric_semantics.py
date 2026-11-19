"""固定答句：B03「停止玩笑」须映射为 PV05 lower，不得当作道德脱离↑。"""
import unittest
from pathlib import Path

from psych_agent.dialogue_config import load_dialogue_config
from psych_agent.dialogue_contracts import validate_turn
from psych_agent.measurement_controller import MeasurementController
from psych_agent.profile import build_profile
from psych_agent.scenario_agent import TemplateScenarioGenerator


ROOT = Path(__file__).resolve().parents[1]

STOP_QUOTES = (
    '太过分的时候就应该停止',
    '当时就应该停止',
    '只要对方不愿意或者已经难受，就应该停下来，不能用大家觉得好笑当理由。',
)


class RubricSemanticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = load_dialogue_config(ROOT)

    def _synthetic_task(self, unit_id='U_B03_JUSTIFICATION'):
        unit = self.cfg.units[unit_id]
        view = {
            'unit_id': unit_id,
            'source_item_ids': list(unit['source_item_ids']),
            'target_variable_ids': list(unit['target_variable_ids']),
            'facet': unit['facet'],
            'reference_frame': unit['reference_frame'],
            'reference_period': unit.get('reference_period', 'unspecified'),
            'question_template': unit['question_template'],
            'required_slots': list(unit['required_slots']),
            'rule_ids': list(unit['rule_ids']),
            'applicability': dict(unit.get('applicability') or {}),
            'interpretation_boundary': unit.get('interpretation_boundary', ''),
            'completion_rule': unit.get('completion_rule', ''),
        }
        return {
            'task_id': 'TASK_B03_SEM',
            'question_id': 'Q_B03_SEM',
            'session_id': 'B03_SEM',
            'turn_id': 'T001',
            'entry_index': 0,
            'scenario_id': 'S03',
            'condition_id': 'base',
            'scenario_instance_id': 'INST_B03',
            'scenario_text': '同学拿外号开玩笑。',
            'facts': ['有人被取笑'],
            'event_id': 'EV_B03',
            'target_unit_id': unit_id,
            'allowed_units': [view],
            'mode': 'probe',
            'reference_frame': unit['reference_frame'],
            'question_template': unit['question_template'],
        }

    def test_b03_stop_criteria_text_points_to_lower(self):
        higher = self.cfg.rules['DR_B03_JUSTIFICATION_PV05_HIGHER']
        lower = self.cfg.rules['DR_B03_JUSTIFICATION_PV05_LOWER']
        self.assertEqual(higher['direction'], 'higher')
        self.assertEqual(lower['direction'], 'lower')
        self.assertIn('停止', lower['criterion'])
        self.assertIn('LOWER', higher['do_not_infer_when'])
        blob = higher['do_not_infer_when'] + lower['criterion']
        self.assertIn('太过分', blob)
        self.assertIn('停止', blob)

    def test_stop_joke_quotes_validate_as_pv05_lower(self):
        task = self._synthetic_task()
        for quote in STOP_QUOTES:
            with self.subTest(quote=quote):
                turn = {
                    'turn_id': 'T001',
                    'task_id': task['task_id'],
                    'question': task['question_template'],
                    'answer': quote,
                    'target_unit_id': 'U_B03_JUSTIFICATION',
                }
                result = {
                    'turn_id': 'T001',
                    'observations': [{
                        'unit_id': 'U_B03_JUSTIFICATION',
                        'status': 'covered',
                        'quote': quote,
                        'reference_frame': 'general_belief',
                        'subject': 'self',
                        'context_turn_ids': [],
                        'slots': [{'slot_id': 'boundary', 'value': '应停止', 'quote': quote}],
                        'evidence': [{
                            'rule_id': 'DR_B03_JUSTIFICATION_PV05_LOWER',
                            'quote': quote,
                            'rationale': '明确反对以玩笑继续伤害。',
                            'intensity': 2,
                        }],
                        'reason': '固定答句回归：停止玩笑 → PV05 lower',
                    }],
                    'background': [],
                }
                validated = validate_turn(task, turn, [], result, self.cfg)
                self.assertEqual(len(validated.evidence), 1)
                self.assertEqual(validated.evidence[0]['direction'], 'lower')
                self.assertEqual(validated.evidence[0]['variable_id'], 'PV05')
                self.assertEqual(validated.evidence[0]['rule_id'],
                                 'DR_B03_JUSTIFICATION_PV05_LOWER')

    def test_continue_rationalization_rule_is_higher_and_excludes_stop(self):
        rule = self.cfg.rules['DR_B03_JUSTIFICATION_PV05_HIGHER']
        self.assertEqual(rule['direction'], 'higher')
        self.assertIn('好笑', rule['criterion'])
        self.assertIn('绝非 higher', rule['do_not_infer_when'])

    def test_fallback_strips_evidence_from_core(self):
        c = MeasurementController(self.cfg, 's01', 'FALLBACK_CORE', True, max_total_turns=1)
        action = c.next_action()
        c.set_scenario(TemplateScenarioGenerator().generate(action['task']))
        task = c.next_action()['task']
        c.record_question({'question': task['question_template']})
        c.record_answer('我会冷静下来。')
        unit = task['target_unit_id'] or task['allowed_units'][0]['unit_id']
        unit_view = next(u for u in task['allowed_units'] if u['unit_id'] == unit)
        rules = [r for r in unit_view['rule_ids'] if r.endswith('_HIGHER') or r.endswith('_LOWER')]
        self.assertTrue(rules)
        poisoned = {
            'turn_id': c.pending_turn()['turn_id'],
            'observations': [{
                'unit_id': unit,
                'status': 'covered',
                'quote': '我会冷静下来。',
                'reference_frame': unit_view['reference_frame'],
                'subject': 'self',
                'context_turn_ids': [],
                'slots': [{'slot_id': s['slot_id'], 'value': '冷静', 'quote': '我会冷静下来。'}
                          for s in unit_view['required_slots']],
                'evidence': [{
                    'rule_id': rules[0],
                    'quote': '我会冷静下来。',
                    'rationale': '不应进入核心计分的毒丸证据',
                }],
                'reason': 'fallback 测试毒丸',
            }],
            'background': [],
        }
        committed = c.commit(poisoned, extraction_fallback=True)
        self.assertTrue(committed['response_quality']['a3_fallback_used'])
        self.assertTrue(committed['response_quality']['fallback_excluded_from_core'])
        self.assertEqual(committed['validated_evidence'], [])
        profile = build_profile(c.snapshot(), self.cfg)
        self.assertEqual(profile['evidence_ledger'], [])
        self.assertEqual(profile['coverage']['response_quality']['a3_fallback_turns'], 1)


if __name__ == '__main__':
    unittest.main()
