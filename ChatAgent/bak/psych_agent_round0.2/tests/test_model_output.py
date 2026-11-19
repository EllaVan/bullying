"""模型包装兼容与gaps范围约束；保留越界输出供审阅，不改写其内容。"""
from contextlib import redirect_stderr, redirect_stdout
import copy
from dataclasses import replace
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from psych_agent_round1.psych_agent.cli import main
from psych_agent.config import load_config
from psych_agent_round1.psych_agent.evidence import validate_extraction
from psych_agent_round1.psych_agent.extractor import build_messages
from psych_agent.io_utils import ValidationError, parse_json, read_json
from psych_agent_round1.psych_agent.model_output import parse_model_json


ROOT = Path(__file__).resolve().parents[1]


class ModelOutputTests(unittest.TestCase):
    def test_plain_or_whole_fenced_json_has_identical_content(self):
        expected={'quote':'原话含```符号；路径\\n保持原样','gaps':[]}
        plain=json.dumps(expected,ensure_ascii=False)
        for raw in [plain,' \n'+plain+'\n ',f'```json\n{plain}\n```',
                    f'```\n{plain}\n```',f'```JSON  \r\n{plain}\r\n```\r\n']:
            with self.subTest(raw=raw):
                self.assertEqual(parse_model_json(raw),expected)

    def test_does_not_extract_json_from_prose_or_discard_extra_blocks(self):
        for raw in ['说明\n```json\n{}\n```','```json\n{}\n```\n额外说明',
                    '```json\n{}\n```\n```json\n{}\n```','```json\n{}',
                    '```python\n{}\n```','```json\n{"incomplete":\n```','{}\n{}']:
            with self.subTest(raw=raw):
                with self.assertRaises(ValidationError): parse_model_json(raw)

    def test_wrapped_json_still_rejects_duplicate_keys_and_nan(self):
        for raw in ['{"x":1,"x":2}','{"x":NaN}']:
            with self.subTest(raw=raw):
                with self.assertRaises(ValidationError): parse_model_json(f'```json\n{raw}\n```')

    def test_configuration_json_parser_remains_strict(self):
        with self.assertRaises(ValidationError): parse_json('```json\n{}\n```')


class GapScopeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg=load_config(ROOT)

    def pair(self):
        return read_json(ROOT/'data/single_case.json'), read_json(ROOT/'fixtures/replay/S01_001.json')

    def measurement(self, case, cfg):
        return json.loads(build_messages(case,cfg)[0]['content'].split('以下是本轮只读测量配置：\n',1)[1])

    def test_prompt_separates_background_and_constrains_gaps_without_mutating_config(self):
        case,_=self.pair()
        before=copy.deepcopy((self.cfg.scope,self.cfg.extraction_schema,self.cfg.variables))
        prompt=self.measurement(case,self.cfg)
        active=self.cfg.scope['active_variable_ids']
        self.assertEqual([v['variable_id'] for v in prompt['variables']],active)
        self.assertEqual({v['variable_id'] for v in prompt['context_variables']},{'PV05','PV08'})
        self.assertEqual(prompt['gaps_allowed_variable_ids'],active)
        self.assertEqual(prompt['output_schema']['properties']['gaps']['items']['properties']['variable_id']['enum'],active)
        self.assertTrue(any(r['rule_id']=='R_F02_SUPPORT' for r in prompt['evidence_rules']))
        self.assertEqual((self.cfg.scope,self.cfg.extraction_schema,self.cfg.variables),before)

    def test_whitelist_follows_selected_scope_instead_of_hardcoded_four_variables(self):
        scope={**self.cfg.scope,'active_variable_ids':['PV01','PV10'],'active_item_ids':['E01','E04']}
        cfg=replace(self.cfg,scope=scope)
        case,_=self.pair()
        prompt=self.measurement(case,cfg)
        self.assertEqual(prompt['gaps_allowed_variable_ids'],['PV01','PV10'])
        self.assertEqual(prompt['output_schema']['properties']['gaps']['items']['properties']['variable_id']['enum'],['PV01','PV10'])
        with self.assertRaisesRegex(ValidationError,'PV03'):
            validate_extraction(case,{'case_id':case['case_id'],'evidence':[],
                                    'gaps':[{'variable_id':'PV03','reason':'缺少归因信息'}]},cfg)

    def test_error_names_invalid_gap_indices_and_retains_original_data(self):
        case,result=self.pair()
        result['gaps'].extend([{'variable_id':vid,'reason':'模拟越界缺口'} for vid in ['PV08','PV05','PV1']])
        before=copy.deepcopy(result)
        with self.assertRaises(ValidationError) as error:
            validate_extraction(case,result,self.cfg)
        text=str(error.exception)
        self.assertIn("gaps[2].variable_id='PV08'",text)
        self.assertIn("gaps[3].variable_id='PV05'",text)
        self.assertIn("gaps[4].variable_id='PV1'",text)
        self.assertIn('本轮允许：PV01, PV02, PV03, PV10',text)
        self.assertEqual(result,before)

    def test_cli_preserves_fenced_api_response_and_validates_it(self):
        case,result=self.pair()
        raw='```json\n'+json.dumps(result,ensure_ascii=False)+'\n```'
        with tempfile.TemporaryDirectory() as tmp:
            config_path=Path(tmp)/'llm.json'
            config_path.write_text('{}',encoding='utf-8')
            dest=Path(tmp)/'run'
            with patch('psych_agent.cli.extract_text',return_value=raw) as extract,redirect_stdout(io.StringIO()):
                code=main(['extract','--case-file',str(ROOT/'data/single_case.json'),
                           '--llm-config',str(config_path),'--output',str(dest)])
            self.assertEqual(code,0)
            extract.assert_called_once()
            self.assertEqual((dest/'raw_response.txt').read_text(encoding='utf-8'),raw)
            self.assertEqual(read_json(dest/'parsed_response.json'),result)
            self.assertEqual(read_json(dest/'extraction.json'),result)
            self.assertIsNone(read_json(dest/'summary.json')['risk_result'])

    def test_cli_can_inspect_prior_bad_response_offline_without_filtering_gaps(self):
        _,result=self.pair()
        result['gaps'].append({'variable_id':'PV08','reason':'模拟越界缺口'})
        raw='```json\n'+json.dumps(result,ensure_ascii=False)+'\n```'
        with tempfile.TemporaryDirectory() as tmp:
            response_path=Path(tmp)/'prior_response.txt'; response_path.write_text(raw,encoding='utf-8')
            dest=Path(tmp)/'run'; err=io.StringIO()
            with patch('psych_agent.llm_client.build_opener') as network,redirect_stderr(err):
                code=main(['extract','--case-file',str(ROOT/'data/single_case.json'),
                           '--response-json',str(response_path),'--output',str(dest)])
            self.assertEqual(code,2)
            network.assert_not_called()
            self.assertEqual((dest/'raw_response.txt').read_text(encoding='utf-8'),raw)
            self.assertEqual(read_json(dest/'parsed_response.json'),result)
            self.assertEqual(read_json(dest/'error.json')['stage'],'validate_extraction')
            self.assertEqual(read_json(dest/'error.json')['active_variable_ids'],self.cfg.scope['active_variable_ids'])
            self.assertIn(str(dest),err.getvalue())
            self.assertFalse((dest/'summary.json').exists())
            self.assertFalse((dest/'validated_evidence.json').exists())

    def test_cli_distinguishes_parse_failure_from_scope_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'prior_response.txt'; path.write_text('```json\n{}\n``` extra',encoding='utf-8')
            dest=Path(tmp)/'run'
            with redirect_stderr(io.StringIO()):
                code=main(['extract','--case-file',str(ROOT/'data/single_case.json'),
                           '--response-json',str(path),'--output',str(dest)])
            self.assertEqual(code,2)
            self.assertEqual(read_json(dest/'error.json')['stage'],'parse_response')
            self.assertFalse((dest/'parsed_response.json').exists())


if __name__=='__main__':
    unittest.main()
