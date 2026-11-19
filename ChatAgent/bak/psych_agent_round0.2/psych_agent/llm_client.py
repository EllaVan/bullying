"""可选API适配器：本地配置诊断和联网调用分开，诊断不回显密钥。"""
from dataclasses import dataclass, field
import json
import os
import re
import socket
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .io_utils import ValidationError, parse_json


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


@dataclass(frozen=True)
class _Resolved:
    endpoint: str
    model: str
    timeout: float
    json_mode: bool
    credential_source: str
    api_key: str = field(repr=False)


def _resolve_settings(settings):
    if not isinstance(settings, dict):
        raise ValidationError('LLM配置必须是JSON对象')
    allowed={'endpoint','model','api_key_env','api_key','timeout_seconds','json_object_mode','note'}
    if set(settings)-allowed:
        raise ValidationError('LLM配置含不支持的字段；请对照llm.example.json，密钥字段使用api_key或api_key_env')
    endpoint=settings.get('endpoint','')
    model=settings.get('model','')
    if not isinstance(endpoint,str) or not endpoint.strip() or not isinstance(model,str) or not model.strip():
        raise ValidationError('请填写完整endpoint和账号实际可用的model；只填密钥不足以发起请求')
    endpoint=endpoint.strip(); model=model.strip()
    try:
        parsed=urlsplit(endpoint)
        parsed.port
    except ValueError:
        raise ValidationError('endpoint地址或端口格式错误') from None
    local=parsed.hostname in {'localhost','127.0.0.1','::1'}
    if parsed.scheme not in ({'https','http'} if local else {'https'}) or not parsed.hostname:
        raise ValidationError('远程endpoint必须使用HTTPS；HTTP仅允许本机回环地址')
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValidationError('endpoint不能包含用户名、密码、查询参数或片段')
    if not parsed.path.rstrip('/').endswith('/chat/completions'):
        raise ValidationError('endpoint需要填写完整的/chat/completions接口地址，不能只填base_url')
    timeout=settings.get('timeout_seconds',45)
    if type(timeout) not in (int,float) or not 1<=timeout<=60:
        raise ValidationError('timeout_seconds必须在1到60之间')
    json_mode=settings.get('json_object_mode',False)
    if type(json_mode) is not bool:
        raise ValidationError('json_object_mode必须为布尔值')
    env_name=settings.get('api_key_env','PSYCH_LLM_API_KEY')
    if not isinstance(env_name,str) or (env_name and not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,127}',env_name)):
        raise ValidationError('api_key_env填写环境变量名称，不是密钥本身；直接填写密钥请用api_key字段')
    file_key=settings.get('api_key','')
    if not isinstance(file_key,str):
        raise ValidationError('api_key必须为字符串')
    env_key=os.environ.get(env_name,'').strip() if env_name else ''
    file_key=file_key.strip()
    api_key=env_key or file_key
    credential_source='environment' if env_key else ('config_file' if file_key else 'none_local')
    if not api_key and not local:
        raise ValidationError('未找到API密钥：指定的环境变量未设置，且api_key为空。api_key_env只是变量名称')
    if any(c.isspace() for c in api_key):
        raise ValidationError('API密钥包含内部空白字符，请核对复制内容')
    return _Resolved(endpoint,model,timeout,json_mode,credential_source,api_key)


def inspect_settings(settings):
    resolved=_resolve_settings(settings)
    return {'status':'local_config_valid','credential_source':resolved.credential_source,
            'api_key_present':bool(resolved.api_key),'endpoint_format_valid':True,
            'model_configured':True,'json_object_mode':resolved.json_mode,
            'network_test_performed':False,
            'note':'仅通过本地检查；账号权限、余额、模型可用性和网络需--connect验证。环境变量非空时优先于api_key。'}


def _provider_error(exc, secret):
    """保留业务码与脱敏消息，不输出完整错误体或HTTP头。"""
    try:
        wire=exc.read(16384)
        payload=parse_json(wire.decode('utf-8'))
        error=payload.get('error',{})
        if not isinstance(error,dict):
            return ''
        raw_code=error.get('code','')
        code=str(raw_code) if type(raw_code) in (str,int) else ''
        if not re.fullmatch(r'[A-Za-z0-9_.-]{1,64}',code):
            code=''
        message=error.get('message','')
        message=message if isinstance(message,str) else ''
        if secret:
            message=message.replace(secret,'[REDACTED]')
            code=code.replace(secret,'[REDACTED]')
        message=' '.join(message.split())[:500]
        pieces=[]
        if code: pieces.append('业务码'+code)
        if message: pieces.append(message)
        return '；'.join(pieces)
    except (OSError,ValueError,TypeError,AttributeError):
        return ''


def call_chat(messages,settings):
    resolved=_resolve_settings(settings)
    body={'model':resolved.model,'messages':messages,'stream':False}
    if resolved.json_mode:
        body['response_format']={'type':'json_object'}
    headers={'Content-Type':'application/json'}
    if resolved.api_key:
        headers['Authorization']='Bearer '+resolved.api_key
    request=Request(resolved.endpoint,data=json.dumps(body,ensure_ascii=False).encode('utf-8'),headers=headers,method='POST')
    try:
        with build_opener(NoRedirect()).open(request,timeout=resolved.timeout) as response:
            wire=response.read(4_000_001)
        if len(wire)>4_000_000:
            raise ValidationError('模型响应超过本实验允许的大小')
        payload=parse_json(wire.decode('utf-8'))
    except HTTPError as exc:
        details=_provider_error(exc,resolved.api_key)
        message=f'LLM请求失败，HTTP状态码{exc.code}'
        if details: message+='；'+details
        raise ValidationError(message) from None
    except (URLError,TimeoutError,socket.timeout,OSError):
        raise ValidationError('LLM请求超时或网络连接失败；没有自动重复请求') from None
    except UnicodeDecodeError:
        raise ValidationError('LLM接口返回的内容不是UTF-8文本') from None
    try:
        choice=payload['choices'][0]
        content=choice['message']['content']
    except (TypeError,KeyError,IndexError):
        raise ValidationError('LLM响应不符合choices[0].message.content协议；需要调整适配器') from None
    if choice.get('finish_reason') not in (None,'stop'):
        raise ValidationError('模型响应未正常结束或被截断，不能用于证据汇总')
    if not isinstance(content,str) or not content.strip():
        raise ValidationError('LLM未返回可解析的文本内容')
    return content
