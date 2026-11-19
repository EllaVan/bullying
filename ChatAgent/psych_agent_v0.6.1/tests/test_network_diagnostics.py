"""验证诊断不会吞掉底层原因、泄漏凭据或自动追加请求。网络故障均为模拟。"""
from contextlib import redirect_stdout
from http.client import IncompleteRead
import io
import json
from pathlib import Path
import socket
import ssl
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import URLError
from urllib.request import ProxyHandler

from psych_agent.cli import main
from psych_agent.io_utils import ValidationError
from psych_agent.llm_client import call_chat, inspect_settings


class NetworkDiagnosticTests(unittest.TestCase):
    def settings(self, **overrides):
        return {'endpoint':'https://example.invalid/chat/completions',
                'model':'test-model','api_key_env':'','api_key':'synthetic-secret',
                'timeout_seconds':45,**overrides}

    def response(self):
        response=MagicMock()
        response.__enter__.return_value.read.return_value=json.dumps(
            {'choices':[{'finish_reason':'stop','message':{'content':'OK'}}]}).encode()
        return response

    def test_wrapped_errors_retain_distinct_causes_and_do_not_retry(self):
        causes=[(socket.gaierror(-2,'name not known'),'DNS解析失败'),
                (ssl.SSLCertVerificationError(1,'certificate verify failed'),'TLS证书校验失败'),
                (ssl.SSLError(1,'handshake failed'),'TLS连接失败'),
                (TimeoutError('timed out'),'请求超时'),
                (ConnectionRefusedError(111,'connection refused'),'连接被拒绝'),
                (ConnectionResetError(104,'connection reset'),'连接被中断'),
                (OSError(101,'network unreachable'),'网络连接失败')]
        for cause,label in causes:
            with self.subTest(label=label):
                opener=MagicMock(); opener.open.side_effect=URLError(cause)
                with patch('psych_agent.llm_client.build_opener',return_value=opener), \
                     patch('psych_agent.llm_client.monotonic',side_effect=[100,145]):
                    with self.assertRaises(ValidationError) as error:
                        call_chat([],self.settings())
                text=str(error.exception)
                self.assertIn(label,text)
                self.assertIn(type(cause).__name__,text)
                self.assertIn('建立连接或等待响应头',text)
                self.assertIn('耗时=45.00秒',text)
                if cause.errno is not None:
                    self.assertIn(f'errno={cause.errno}',text)
                opener.open.assert_called_once()

    def test_timeout_reading_body_identifies_later_phase(self):
        response=self.response()
        response.__enter__.return_value.read.side_effect=TimeoutError('read timed out')
        opener=MagicMock(); opener.open.return_value=response
        with patch('psych_agent.llm_client.build_opener',return_value=opener):
            with self.assertRaises(ValidationError) as error:
                call_chat([],self.settings())
        self.assertIn('读取响应正文',str(error.exception))
        self.assertIn('请求超时',str(error.exception))
        opener.open.assert_called_once()

    def test_truncated_http_body_is_a_controlled_error(self):
        response=self.response()
        response.__enter__.return_value.read.side_effect=IncompleteRead(b'partial',100)
        opener=MagicMock(); opener.open.return_value=response
        with patch('psych_agent.llm_client.build_opener',return_value=opener):
            with self.assertRaisesRegex(ValidationError,'HTTP响应传输失败'):
                call_chat([],self.settings())

    def test_network_error_hides_key_auth_and_proxy_credentials(self):
        opener=MagicMock()
        opener.open.side_effect=URLError(
            'synthetic-secret https://proxy-user:proxy-password@proxy.invalid:8080 '
            'Bearer another-token token=third-token password=fourth-secret failed')
        with patch('psych_agent.llm_client.build_opener',return_value=opener):
            with self.assertRaises(ValidationError) as error:
                call_chat([],self.settings())
        for secret in ['synthetic-secret','proxy-user','proxy-password',
                       'another-token','third-token','fourth-secret']:
            self.assertNotIn(secret,str(error.exception))
        self.assertIn('failed',str(error.exception))

    def test_direct_mode_is_explicit_and_system_mode_keeps_default_handler(self):
        for mode in ['system','direct']:
            with self.subTest(mode=mode):
                opener=MagicMock(); opener.open.return_value=self.response()
                with patch('psych_agent.llm_client.build_opener',return_value=opener) as factory:
                    self.assertEqual(call_chat([],self.settings(proxy_mode=mode)),'OK')
                proxies=[h for h in factory.call_args.args if isinstance(h,ProxyHandler)]
                self.assertEqual(len(proxies),int(mode=='direct'))
                if proxies:
                    self.assertEqual(proxies[0].proxies,{})

    def test_diagnostics_show_proxy_presence_without_exposing_address(self):
        with patch('psych_agent.llm_client.getproxies',return_value={
                'https':'http://proxy-user:proxy-password@proxy.invalid:8080','no':'private.invalid'}):
            report=inspect_settings(self.settings())
        self.assertTrue(report['system_proxy_for_endpoint_scheme_present'])
        self.assertTrue(report['no_proxy_rule_present'])
        self.assertNotIn('proxy-password',json.dumps(report))
        self.assertNotIn('private.invalid',json.dumps(report))

    def test_thinking_is_forwarded_only_when_requested_and_timeout_can_be_120(self):
        for thinking in [None,{'type':'disabled'},{'type':'enabled'}]:
            settings=self.settings(timeout_seconds=120)
            if thinking is not None:
                settings['thinking']=thinking
            opener=MagicMock(); opener.open.return_value=self.response()
            with patch('psych_agent.llm_client.build_opener',return_value=opener):
                call_chat([],settings)
            body=json.loads(opener.open.call_args.args[0].data)
            self.assertEqual(body.get('thinking'),thinking)
            self.assertEqual(opener.open.call_args.kwargs['timeout'],120)
            self.assertNotIn('proxy_mode',body)
            self.assertNotIn('api_key',body)

    def test_invalid_new_options_fail_before_network(self):
        changes=[{'proxy_mode':'unknown'},{'proxy_mode':[]},
                 {'thinking':None},{'thinking':{'type':[]}},
                 {'thinking':{'type':'auto'}},{'thinking':{'type':'enabled','extra':1}},
                 {'timeout_seconds':301},{'timeout_seconds':True},
                 {'timeout_seconds':float('nan')}]
        for change in changes:
            with self.subTest(change=change),patch('psych_agent.llm_client.build_opener') as factory:
                with self.assertRaises(ValidationError):
                    call_chat([],self.settings(**change))
                factory.assert_not_called()

    def test_doctor_failure_is_structured_and_options_do_not_rewrite_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'llm.json'
            path.write_text(json.dumps(self.settings()),encoding='utf-8')
            original=path.read_bytes()
            opener=MagicMock(); opener.open.side_effect=URLError(socket.gaierror(-2,'name not known'))
            out=io.StringIO()
            with patch('psych_agent.llm_client.build_opener',return_value=opener), \
                 patch('psych_agent.cli.load_config') as loader,redirect_stdout(out):
                code=main(['doctor','--llm-config',str(path),'--connect','--direct','--disable-thinking'])
            report=json.loads(out.getvalue())
            self.assertEqual(code,2)
            self.assertEqual(report['status'],'api_request_failed')
            self.assertTrue(report['network_test_performed'])
            self.assertEqual(report['credential_source'],'config_file')
            self.assertEqual(report['proxy_mode'],'direct')
            self.assertEqual(report['thinking_type'],'disabled')
            self.assertIn('DNS解析失败',report['error'])
            self.assertNotIn('synthetic-secret',out.getvalue())
            body=json.loads(opener.open.call_args.args[0].data)
            self.assertEqual(body['messages'],[{'role':'user','content':'请只回复OK。'}])
            self.assertEqual(body['thinking'],{'type':'disabled'})
            self.assertNotIn('response_format',body)
            self.assertEqual(path.read_bytes(),original)
            loader.assert_not_called()
            opener.open.assert_called_once()


if __name__=='__main__':
    unittest.main()
