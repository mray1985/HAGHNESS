"""Versioned input serialization only; does not save, calculate or approve returns."""
import json

MAX_SNAPSHOT = 256 * 1024
PROFILE_FIELDS = frozenset(('firstName', 'lastName', 'ssn', 'birthday', 'address', 'city', 'state', 'zip', 'status'))
TEXT_FIELDS = frozenset(('type', 'layout', 'account', 'control', 'ein', 'employeeAddress', 'employeeName',
    'employerName', 'payerAddress', 'payerName', 'payerTin', 'ssn', 'rolled_over', 'special_treatment',
    'box1', 'box2', 'box2a', 'box3', 'box4', 'box5', 'box6', 'box7', 'box8', 'box8percent',
    'box9a', 'box9b', 'box10', 'box11', 'box13', 'box14', 'box14b'))
BOOL_FIELDS = frozenset(('taxable_not_determined', 'total_distribution', 'corrected', 'ira', 'fatca'))
STATE_FIELDS = frozenset(('state', 'id', 'wages', 'tax', 'localWages', 'localTax', 'locality'))


def text_map(value, fields):
    if not isinstance(value, dict) or not set(value) <= fields:
        raise ValueError('Unexpected input fields')
    if any(not isinstance(v, str) or len(v) > 2000 for v in value.values()):
        raise ValueError('Bounded input text required')


def validate_snapshot(value, year):
    if (type(year) is not int or year not in (2023, 2024, 2025, 2026)
            or not isinstance(value, dict)
            or set(value) != {'year', 'profile', 'forms', 'active', 'stateAnswers'}
            or value['year'] != str(year)):
        raise ValueError('Matching scoped input year required')
    text_map(value['profile'], PROFILE_FIELDS)
    text_map(value['stateAnswers'], frozenset(('residence-state', 'state-move', 'state-work')))
    forms = value['forms']
    if not isinstance(forms, list) or len(forms) > 100:
        raise ValueError('Bounded form list required')
    if type(value['active']) is not int or not 0 <= value['active'] < max(1, len(forms)):
        raise ValueError('Valid active form index required')
    for form in forms:
        if not isinstance(form, dict) or not set(form) <= TEXT_FIELDS | BOOL_FIELDS | {'states', 'codes', 'checks'}:
            raise ValueError('Unexpected form fields')
        text_map({k:v for k,v in form.items() if k in TEXT_FIELDS}, TEXT_FIELDS)
        if any(type(form[k]) is not bool for k in BOOL_FIELDS & form.keys()):
            raise ValueError('Boolean checkbox required')
        if form.get('type', 'W-2') not in ('W-2', '1099-R'):
            raise ValueError('Unsupported input form')
        if form.get('layout', 'standard') not in ('standard', 'stacked'):
            raise ValueError('Unsupported input layout')
        for name, fields, limit in (('states', STATE_FIELDS, 100), ('codes', {'code', 'amount'}, 4)):
            rows = form.get(name, [])
            if not isinstance(rows, list) or len(rows) > limit:
                raise ValueError('Bounded input rows required')
            for row in rows:
                text_map(row, fields)
        checks = form.get('checks', {})
        if (not isinstance(checks, dict) or not set(checks) <= {'statutory', 'retirement', 'sick'}
                or any(type(v) is not bool for v in checks.values())):
            raise ValueError('Valid W-2 checkboxes required')


def encode_snapshot(value, year):
    validate_snapshot(value, year)
    data = json.dumps({'format': 'ha-tax-input-v1', 'input': value},
                      ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode('utf-8')
    if len(data) > MAX_SNAPSHOT:
        raise ValueError('Tax input exceeds limit')
    return data


def decode_snapshot(data, year):
    if not isinstance(data, bytes) or len(data) > MAX_SNAPSHOT:
        raise ValueError('Bounded tax input bytes required')
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError('Duplicate input field')
            value[key] = item
        return value
    try:
        envelope = json.loads(data.decode('utf-8'), object_pairs_hook=unique)
        if not isinstance(envelope, dict) or set(envelope) != {'format', 'input'} or envelope['format'] != 'ha-tax-input-v1':
            raise ValueError('Unsupported input format')
        validate_snapshot(envelope['input'], year)
    except (UnicodeError, ValueError, RecursionError):
        raise ValueError('Invalid saved tax input') from None
    return envelope['input']
