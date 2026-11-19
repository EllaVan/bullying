"""仅实现项目schema用到的JSON Schema子集，不是通用JSON Schema验证库。

数据格式以schemas/中的JSON为唯一来源；出现未支持的关键字会报错，
不会默默跳过校验。后续扩展复杂schema时可替换为完整验证库。
"""
from .io_utils import ValidationError

KEYWORDS = {'$schema', 'title', 'description', 'type', 'properties', 'required',
            'additionalProperties', 'items', 'enum', 'const', 'minLength', 'minItems'}


def check_schema(schema, path='$schema'):
    if not isinstance(schema, dict):
        raise ValidationError(f'{path}必须为对象')
    unknown = set(schema) - KEYWORDS
    if unknown:
        raise ValidationError(f'{path}包含此验证器未支持的关键字：{sorted(unknown)}')
    if schema.get('type') not in {'object','array','string','boolean','integer','number','null'}:
        raise ValidationError(f'{path}.type缺失或不支持')
    if schema['type'] == 'object':
        if not isinstance(schema.get('properties'), dict) or schema.get('additionalProperties') is not False:
            raise ValidationError(f'{path}对象必须定义properties并禁止额外字段')
        required = schema.get('required', [])
        if not isinstance(required, list) or any(k not in schema['properties'] for k in required):
            raise ValidationError(f'{path}.required无效')
        for name, child in schema['properties'].items():
            check_schema(child, path + '.' + name)
    if schema['type'] == 'array':
        check_schema(schema.get('items'), path + '[]')


def validate_shape(value, schema, path='$'):
    kind = schema['type']
    valid = {'object': isinstance(value, dict), 'array': isinstance(value, list),
             'string': isinstance(value, str), 'boolean': type(value) is bool,
             'integer': type(value) is int, 'number': type(value) in (int, float),
             'null': value is None}[kind]
    if not valid:
        raise ValidationError(f'{path}应为{kind}')
    if 'enum' in schema and value not in schema['enum']:
        raise ValidationError(f'{path}不在允许取值中')
    if 'const' in schema and value != schema['const']:
        raise ValidationError(f'{path}不是规定常量')
    if kind == 'object':
        missing = set(schema.get('required', [])) - set(value)
        extra = set(value) - set(schema.get('properties', {}))
        if missing:
            raise ValidationError(f'{path}缺少字段：{sorted(missing)}')
        if extra and schema.get('additionalProperties') is False:
            raise ValidationError(f'{path}包含额外字段：{sorted(extra)}')
        for name, child in value.items():
            if name in schema['properties']:
                validate_shape(child, schema['properties'][name], path + '.' + name)
    elif kind == 'array':
        if len(value) < schema.get('minItems', 0):
            raise ValidationError(f'{path}元素数量不足')
        for index, child in enumerate(value):
            validate_shape(child, schema['items'], f'{path}[{index}]')
    elif kind == 'string' and len(value) < schema.get('minLength', 0):
        raise ValidationError(f'{path}字符串长度不足')
