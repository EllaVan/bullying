"""0.2变更验证：部分变量绑定、规则/证据ID、密钥来源和独立API诊断。"""
import copy
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

from psych_agent.aggregate import aggregate
from psych_agent.cli import main
from psych_agent.config import load_config
from psych_agent.evidence import validate_extraction
from psych_agent.extractor import build_messages
from psych_agent.io_utils import ValidationError, read_json
from psych_agent.llm_client import call_chat, inspect_settings

ROOT=Path(__file__).resolve().parents[1]


class PartialMappingTests(unittest.TestCase):
    def extended(self):
        return load_config(ROOT,'config/round1_extended.example.json')

    def test_default_scope_preserved(self):
        cfg=load_config(ROOT)
        self.assertEqual(cfg.scope['active_item_ids'],['A01','A02','A03','A04','E01','E04','G01'])
        self.assertNotIn('R_E03_HELP_BARRIER',cfg.allowed_rules())
        self.assertNotIn('R_D04_REPAIR_EXPECTATION',cfg.allowed_rules())

    def test_partial_item_is_allowed_without_expanding_variable_scope(self):
        cfg=self.extended()
        case=read_json(ROOT/'examples/E03_D04.case.json')
        response=read_json(ROOT/'examples/E03_D04.extraction.json')
        batch=validate_extraction(case,response,cfg)
        self.assertEqual({e['variable_id'] for e in batch.evidence},{'PV10'})
        self.assertEqual([v['variable_id'] for v in aggregate(batch,cfg)['variables']],['PV01','PV02','PV03','PV10'])

    def test_other_variable_rule_on_same_item_is_filtered(self):
        def reader(path):
            data=read_json(path)
            if Path(path).name=='evidence_rubric.json':
                extra=copy.deepcopy(next(r for r in data['rules'] if r['rule_id']=='R_D04_REPAIR_EXPECTATION'))
                extra.update(rule_id='TEST_D04_PV08',variable_id='PV08')
                data['rules'].append(extra)
            return data
        with patch('psych_agent.config.read_json',side_effect=reader):
            cfg=self.extended()
        self.assertIn('TEST_D04_PV08',cfg.rules)
        self.assertNotIn('TEST_D04_PV08',cfg.allowed_rules())

    def test_binding_outside_source_mapping_is_rejected(self):
        def reader(path):
            data=read_json(path)
            if Path(path).name=='scenario_blueprint.json':
                b=next(b for b in data['scenarios'][0]['item_bindings'] if b['item_id']=='D04')
                b['target_variable_ids']=['PV03']
            return data
        with patch('psych_agent.config.read_json',side_effect=reader):
            with self.assertRaises(ValidationError): self.extended()

    def test_binding_outside_scenario_is_rejected(self):
        def reader(path):
            data=read_json(path)
            if Path(path).name=='scenario_blueprint.json':
                b=next(b for b in data['scenarios'][0]['item_bindings'] if b['item_id']=='D04')
                b['target_variable_ids']=['PV08','PV10']
            return data
        with patch('psych_agent.config.read_json',side_effect=reader):
            with self.assertRaises(ValidationError): self.extended()

    def test_prompt_distinguishes_source_and_selected_variables(self):
        cfg=self.extended()
        case=read_json(ROOT/'examples/E03_D04.case.json')
        msg=build_messages(case,cfg)[0]['content']
        measurement=json.loads(msg.split('以下是本轮只读测量配置：\n',1)[1])
        d04=next(i for i in measurement['items'] if i['item_id']=='D04')
        self.assertEqual(d04['source_variable_ids'],['PV08','PV10'])
        self.assertEqual(d04['target_variable_ids'],['PV10'])

    def test_evidence_id_is_instance_id_while_rule_id_is_shared(self):
        cfg=load_config(ROOT)
        case=read_json(ROOT/'data/single_case.json')
        response=read_json(ROOT/'fixtures/replay/S01_001.json')
        a=validate_extraction(case,response,cfg).evidence[0]
        b=validate_extraction(case,response,cfg).evidence[0]
        case['case_id']='another_case'; response['case_id']='another_case'
        c=validate_extraction(case,response,cfg).evidence[0]
        self.assertEqual(a['evidence_id'],b['evidence_id'])
        self.assertNotEqual(a['evidence_id'],c['evidence_id'])
        self.assertEqual(a['rule_id'],c['rule_id'])
        self.assertIn(a['rule_id'],cfg.rules)


class ApiDiagnosticTests(unittest.TestCase):
    def settings(self):
        return {'endpoint':'https://example.invalid/chat/completions','model':'test-model',
                'api_key_env':'TEST_PSYCH_KEY','api_key':'synthetic-file-key'}

    def test_config_file_key_is_supported_without_env(self):
        with patch.dict(os.environ,{},clear=True):
            report=inspect_settings(self.settings())
        self.assertEqual(report['credential_source'],'config_file')
        self.assertNotIn('synthetic-file-key',json.dumps(report))

    def test_env_key_priority_is_explicit(self):
        with patch.dict(os.environ,{'TEST_PSYCH_KEY':'synthetic-env-key'}):
            report=inspect_settings(self.settings())
        self.assertEqual(report['credential_source'],'environment')
        self.assertNotIn('synthetic-env-key',json.dumps(report))

    def test_empty_env_name_can_force_config_file_key(self):
        settings=self.settings(); settings['api_key_env']=''
        with patch.dict(os.environ,{'TEST_PSYCH_KEY':'synthetic-env-key'}):
            report=inspect_settings(settings)
        self.assertEqual(report['credential_source'],'config_file')

    def test_literal_key_in_env_field_is_rejected_without_echo(self):
        settings=self.settings(); settings['api_key_env']='sk-synthetic-secret-key'
        with self.assertRaises(ValidationError) as err: inspect_settings(settings)
        self.assertNotIn('sk-synthetic-secret-key',str(err.exception))

    def test_incomplete_endpoint_is_rejected_locally(self):
        settings=self.settings(); settings['endpoint']='https://example.invalid/v1'
        with self.assertRaises(ValidationError): inspect_settings(settings)

    def test_doctor_needs_no_measurement_config_and_is_offline(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{},clear=True):
            path=Path(tmp)/'llm.json'; path.write_text(json.dumps(self.settings()),encoding='utf-8')
            out=io.StringIO()
            with patch('psych_agent.cli.load_config') as loader,patch('psych_agent.cli.call_chat') as chat,redirect_stdout(out):
                code=main(['--project-root',str(Path(tmp)/'missing'),'doctor','--llm-config',str(path)])
            self.assertEqual(code,0); loader.assert_not_called(); chat.assert_not_called()
            self.assertFalse(json.loads(out.getvalue())['network_test_performed'])
            self.assertNotIn('synthetic-file-key',out.getvalue())

    def test_doctor_connect_sends_only_minimal_prompt(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{},clear=True):
            path=Path(tmp)/'llm.json'; path.write_text(json.dumps(self.settings()),encoding='utf-8')
            out=io.StringIO()
            with patch('psych_agent.cli.call_chat',return_value='OK') as chat,redirect_stdout(out):
                self.assertEqual(main(['doctor','--llm-config',str(path),'--connect']),0)
            self.assertEqual(chat.call_args.args[0],[{'role':'user','content':'请只回复OK。'}])
            self.assertFalse(chat.call_args.args[1]['json_object_mode'])
            self.assertEqual(json.loads(out.getvalue())['status'],'api_connected')

    def test_provider_code_is_retained_while_key_is_redacted(self):
        body=json.dumps({'error':{'code':'1211','message':'model missing; synthetic-file-key'}}).encode()
        opener=MagicMock(); opener.open.side_effect=HTTPError('https://example.invalid',400,'bad',{},io.BytesIO(body))
        with patch.dict(os.environ,{},clear=True),patch('psych_agent.llm_client.build_opener',return_value=opener):
            with self.assertRaises(ValidationError) as err: call_chat([],self.settings())
        self.assertIn('1211',str(err.exception))
        self.assertNotIn('synthetic-file-key',str(err.exception))

    def test_file_key_reaches_authorization_header(self):
        response=MagicMock()
        response.__enter__.return_value.read.return_value=json.dumps({'choices':[{'finish_reason':'stop','message':{'content':'OK'}}]}).encode()
        opener=MagicMock(); opener.open.return_value=response
        with patch.dict(os.environ,{},clear=True),patch('psych_agent.llm_client.build_opener',return_value=opener):
            self.assertEqual(call_chat([],self.settings()),'OK')
        self.assertEqual(opener.open.call_args.args[0].get_header('Authorization'),'Bearer synthetic-file-key')


if __name__=='__main__':
    unittest.main()
