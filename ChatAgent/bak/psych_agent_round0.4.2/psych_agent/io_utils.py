"""统一使用UTF-8和严格JSON，避免重复键与NaN悄悄改变数据。"""
import json
from pathlib import Path


class ValidationError(ValueError):
    """可供命令行清晰展示的数据校验错误。"""


def _pairs(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValidationError(f'JSON包含重复字段：{key}')
        obj[key] = value
    return obj


def _constant(value):
    raise ValidationError(f'不允许非标准JSON常量：{value}')


def parse_json(text):
    try:
        return json.loads(text, object_pairs_hook=_pairs, parse_constant=_constant)
    except json.JSONDecodeError as exc:
        raise ValidationError(f'JSON格式错误，第{exc.lineno}行第{exc.colno}列') from exc


def read_json(path):
    return parse_json(Path(path).read_text(encoding='utf-8-sig'))


def read_jsonl(path):
    rows = []
    for number, line in enumerate(Path(path).read_text(encoding='utf-8-sig').splitlines(), 1):
        if line.strip():
            try:
                rows.append(parse_json(line))
            except ValidationError as exc:
                raise ValidationError(f'JSONL第{number}行：{exc}') from exc
    return rows


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
