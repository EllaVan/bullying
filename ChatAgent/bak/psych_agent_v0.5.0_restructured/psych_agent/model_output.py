"""A3模型输出的格式适配，独立于配置JSON读取与证据内容校验。"""
import re

from .io_utils import ValidationError, parse_json


_JSON_FENCE = re.compile(r'```(?:json)?[ \t]*\r?\n(.*?)\r?\n```[ \t]*', re.DOTALL | re.IGNORECASE)


def strip_json_markdown(text: str) -> str:
    """仅移除包住整个响应的JSON/无语言代码围栏，保留内部文本。"""
    if not isinstance(text, str):
        raise ValidationError('模型输出必须是文本')
    stripped = text.strip()
    if stripped.startswith('```'):
        match = _JSON_FENCE.fullmatch(stripped)
        if match is None:
            raise ValidationError('模型输出的代码围栏不完整或带有额外文本；只接受纯JSON或完整的单个JSON代码块')
        return match.group(1).strip()
    return stripped


def parse_model_json(text: str):
    # 重复键、NaN及JSON语法错误仍由统一的严格解析器拒绝。
    return parse_json(strip_json_markdown(text))
