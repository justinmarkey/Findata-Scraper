"""One public configuration file and one ignored local secrets file."""
import copy
import json
import math
import os
from pathlib import Path
import tomllib
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SETTINGS = ROOT / 'config/settings.toml'
OPS = {'>': 'gt', '>=': 'ge', '<': 'lt', '<=': 'le', '=': 'eq', '==': 'eq',
       'gt': 'gt', 'ge': 'ge', 'lt': 'lt', 'le': 'le', 'eq': 'eq'}


def load_secrets():
    # CI/repository secrets always win over the local file. Never print secret values.
    load_dotenv(ROOT / '.env', override=False)


def screen_rules(settings, name, ancestry=()):
    if name in ancestry:
        raise ValueError(f'Circular screen inheritance: {name}')
    definition = settings['screens'][name]
    rules = screen_rules(settings, definition['extends'], ancestry + (name,)) if definition.get('extends') else []
    for rule in definition.get('rules', []):
        field, op, cutoff = rule['metric'], rule['op'], rule['threshold']
        if not isinstance(field, str) or not field or op not in OPS:
            raise ValueError(f'Invalid rule in screen {name}')
        if isinstance(cutoff, bool) or not isinstance(cutoff, (float, int)) or not math.isfinite(cutoff):
            raise ValueError(f'Invalid numeric threshold in screen {name}')
        rules.append((field, OPS[op], cutoff))
    return rules


def load_settings(path=None):
    load_secrets()
    path = Path(path or os.environ.get('FINDATA_CONFIG') or DEFAULT_SETTINGS)
    with path.open('rb') as stream:
        settings = tomllib.load(stream)
    if settings.get('schema_version') != 1:
        raise ValueError('Unsupported settings schema_version')
    from .screening import metrics
    numeric_fields = set(metrics({})) - {'period_end', 'observed_at', 'flow_basis', 'source',
                                        'reporting_currency', 'quote_currency'}
    for name in settings['screens']:
        for field, _, _ in screen_rules(settings, name):
            if field not in numeric_fields:
                raise ValueError(f'Unknown numeric metric {field!r} in screen {name}')
    rank = settings['reports']['rank_by']
    descending = settings['reports']['rank_descending']
    if not rank or len(rank) != len(descending) or any(field not in numeric_fields for field in rank) or any(type(value) is not bool for value in descending):
        raise ValueError('Invalid reports.rank_by / reports.rank_descending')
    if not settings['reports']['screens']:
        raise ValueError('reports.screens must contain at least one screen')
    for field in ['attempts', 'statement_limit', 'workers']:
        value = settings['collection'][field]
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError(f'collection.{field} must be a positive integer')
    if settings['providers']['prices'] != 'yfinance' or settings['providers']['profiles'] != 'yfinance':
        raise ValueError('The current price and profile adapters support yfinance only')
    for name in settings['reports']['screens']:
        if name not in settings['screens']:
            raise ValueError(f'Report refers to unknown screen: {name}')
    for field in ['top_per_screen', 'refresh_per_screen', 'max_quote_age_days', 'max_statement_age_days', 'profile_max_characters']:
        value = settings['reports'][field]
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError(f'reports.{field} must be a positive integer')
    for field in ['max_refresh', 'discovery_per_run']:
        value = settings['reports'][field]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f'reports.{field} must be a nonnegative integer')
    ZoneInfo(settings['reports']['timezone'])
    for field in ['morning_time', 'evening_time']:
        from datetime import time
        time.fromisoformat(settings['reports'][field])
    return settings


def report_settings(path=None):
    # Explicit JSON report configurations remain a useful API for isolated tests/integrators.
    if path and Path(path).suffix == '.json':
        return json.loads(Path(path).read_text())
    settings = load_settings(path)
    result = copy.deepcopy(settings['reports'])
    result['recipient'] = os.environ.get(result['recipient_env'], '').strip()
    result['rules'] = {name: screen_rules(settings, name) for name in result['screens']}
    result['labels'] = {name: settings['screens'][name].get('label', name) for name in result['screens']}
    result['workers'] = settings['collection']['workers']
    return result


def openbb_client():
    settings = load_settings()
    from openbb import obb
    for credential, variable in settings['providers'].get('key_env', {}).items():
        value = os.environ.get(variable, '').strip()
        if value:
            setattr(obb.user.credentials, credential, value)
    return obb
