"""每个Agent可注入自己的JSON调用器；模型响应先落盘再解析，无自动重试。"""
import json
from pathlib import Path

from .llm_client import call_chat
from .model_output import parse_model_json
from .io_utils import write_json


class JsonTransport:
    def __init__(self, settings, role, audit_dir=None, client=None):
        self.settings = settings
        self.role = role
        self.audit_dir = Path(audit_dir) if audit_dir else None
        self.client = client or call_chat

    def request(self, system, payload, request_id):
        messages = [{'role':'system','content':system},
                    {'role':'user','content':json.dumps(payload,ensure_ascii=False)}]
        dest = None
        if self.audit_dir:
            dest = self.audit_dir / self.role / request_id
            attempt = 1
            while dest.exists():
                attempt += 1
                dest = self.audit_dir / self.role / f'{request_id}_attempt{attempt}'
            dest.mkdir(parents=True)
            write_json(dest/'messages.json',messages)
        raw = self.client(messages,self.settings)
        if dest:
            (dest/'raw_response.txt').write_text(raw,encoding='utf-8')
        parsed = parse_model_json(raw)
        if dest:
            write_json(dest/'parsed_response.json',parsed)
        return parsed
