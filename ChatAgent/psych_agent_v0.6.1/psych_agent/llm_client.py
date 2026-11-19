"""可选API适配器：本地配置诊断和联网调用分开，诊断不回显密钥。"""
from __future__ import annotations

from dataclasses import dataclass, field
from http.client import HTTPException
import json
import os
import re
import socket
import ssl
from time import monotonic
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener, getproxies

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
    proxy_mode: str
    thinking_type: str | None


def _resolve_settings(settings):
    if not isinstance(settings, dict):
        raise ValidationError('LLM配置必须是JSON对象')
    allowed={'endpoint','model','api_key_env','api_key','timeout_seconds','json_object_mode','note',
             'proxy_mode','thinking'}
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
    if type(timeout) not in (int,float) or not 1<=timeout<=300:
        raise ValidationError('timeout_seconds必须在1到300之间')
    json_mode=settings.get('json_object_mode',False)
    if type(json_mode) is not bool:
        raise ValidationError('json_object_mode必须为布尔值')
    proxy_mode=settings.get('proxy_mode','system')
    if not isinstance(proxy_mode,str) or proxy_mode not in {'system','direct'}:
        raise ValidationError('proxy_mode必须是system或direct')
    thinking_type=None
    if 'thinking' in settings:
        thinking=settings['thinking']
        if (not isinstance(thinking,dict) or set(thinking)!={'type'}
                or not isinstance(thinking['type'],str) or thinking['type'] not in {'enabled','disabled'}):
            raise ValidationError('thinking仅支持包含type的对象，type为enabled或disabled；需模型支持')
        thinking_type=thinking['type']
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
    return _Resolved(endpoint,model,timeout,json_mode,credential_source,api_key,proxy_mode,thinking_type)


def inspect_settings(settings):
    resolved=_resolve_settings(settings)
    proxies=getproxies()
    return {'status':'local_config_valid','credential_source':resolved.credential_source,
            'api_key_present':bool(resolved.api_key),'endpoint_format_valid':True,
            'model_configured':True,'json_object_mode':resolved.json_mode,
            'timeout_seconds':resolved.timeout,'proxy_mode':resolved.proxy_mode,
            'system_proxy_for_endpoint_scheme_present':bool(proxies.get(urlsplit(resolved.endpoint).scheme)),
            'no_proxy_rule_present':bool(proxies.get('no')),
            'thinking_type':resolved.thinking_type or 'provider_default',
            'network_test_performed':False,
            'note':'仅通过本地检查；账号权限、余额、模型可用性和网络需--connect验证。环境变量非空时优先于api_key。'}


def _safe_detail(value, secret):
    """保留底层错误文字，隐藏API密钥、认证头及可能携带代理口令的URL。"""
    message=str(value)
    if secret:
        message=message.replace(secret,'[REDACTED]')
    message=re.sub(r'(?i)\b(?:https?|socks\d?h?)://\S+', '[URL_REDACTED]', message)
    message=re.sub(r'(?i)\b(?:bearer|basic)\s+\S+', '[AUTH_REDACTED]', message)
    message=re.sub(r'(?i)\b(?:api[_-]?key|token|password)\s*[:=]\s*[^\s,;]+',
                   '[CREDENTIAL_REDACTED]',message)
    return ' '.join(message.split())[:500]


def _network_error(exc, resolved, phase, elapsed):
    reason=exc
    # urllib通常把真正的socket/SSL异常包在URLError.reason中。
    for _ in range(4):
        if not isinstance(reason,URLError) or reason.reason is reason:
            break
        reason=reason.reason
    if isinstance(reason,socket.gaierror):
        category='DNS解析失败'
    elif isinstance(reason,ssl.SSLCertVerificationError):
        category='TLS证书校验失败'
    elif isinstance(reason,ssl.SSLError):
        category='TLS连接失败'
    elif isinstance(reason,(TimeoutError,socket.timeout)):
        category='请求超时'
    elif isinstance(reason,ConnectionRefusedError):
        category='连接被拒绝'
    elif isinstance(reason,(ConnectionResetError,ConnectionAbortedError,BrokenPipeError)):
        category='连接被中断'
    elif isinstance(reason,HTTPException):
        category='HTTP响应传输失败'
    else:
        category='网络连接失败'
    detail=_safe_detail(reason,resolved.api_key)
    cause=type(reason).__name__ if isinstance(reason,BaseException) else 'URLError.reason'
    parts=[f'LLM请求失败：{category}',f'底层异常={cause}',f'阶段={phase}',
           f'耗时={elapsed:.2f}秒',f'套接字超时设置={resolved.timeout:g}秒',
           f'代理模式={resolved.proxy_mode}']
    for attr in ('errno','winerror'):
        value=getattr(reason,attr,None)
        if isinstance(value,int):
            parts.append(f'{attr}={value}')
    if detail:
        parts.append(f'详情={detail}')
    parts.append('没有自动重复请求')
    return '；'.join(parts)


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
        message=_safe_detail(message,secret)
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
    if resolved.thinking_type:
        body['thinking']={'type':resolved.thinking_type}
    headers={'Content-Type':'application/json'}
    if resolved.api_key:
        headers['Authorization']='Bearer '+resolved.api_key
    request=Request(resolved.endpoint,data=json.dumps(body,ensure_ascii=False).encode('utf-8'),headers=headers,method='POST')
    handlers=[NoRedirect()]
    if resolved.proxy_mode=='direct':
        handlers.append(ProxyHandler({}))
    started=monotonic()
    phase='建立连接或等待响应头'
    try:
        with build_opener(*handlers).open(request,timeout=resolved.timeout) as response:
            phase='读取响应正文'
            wire=response.read(4_000_001)
        if len(wire)>4_000_000:
            raise ValidationError('模型响应超过本实验允许的大小')
        payload=parse_json(wire.decode('utf-8'))
    except HTTPError as exc:
        details=_provider_error(exc,resolved.api_key)
        message=f'LLM请求失败，HTTP状态码{exc.code}'
        if details: message+='；'+details
        raise ValidationError(message) from None
    except (URLError,TimeoutError,socket.timeout,OSError,HTTPException) as exc:
        raise ValidationError(_network_error(exc,resolved,phase,monotonic()-started)) from None
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
