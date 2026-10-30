"""Auditable annual fundamentals; missing inputs never silently pass a rule."""
import math
from datetime import date
import pandas as pd


def number(value):
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except (TypeError, ValueError):
        return None


def ratio(a, b):
    return a / b if a is not None and b is not None and b > 0 else None


FLOW_METRICS = {'Total Revenue', 'Net Income', 'EBIT', 'Gross Profit', 'Free Cash Flow',
                'Operating Cash Flow', 'Capital Expenditure', 'Interest Expense', 'Net Income Common Stockholders',
                'Repurchase Of Capital Stock'}


BALANCE_METRICS = {'Stockholders Equity', 'Common Stock Equity', 'Total Debt',
                   'Cash And Cash Equivalents', 'Total Liabilities Net Minority Interest',
                   'Long Term Debt', 'Preferred Stock', 'Retained Earnings', 'Treasury Stock'}
CANONICAL = {name.replace(' ', '').lower(): name for name in FLOW_METRICS | BALANCE_METRICS}


def normalize_statements(statements):
    # Yahoo's API uses CamelCase; older exports and pretty=True use spaces.
    return {CANONICAL.get(name.replace(' ', '').lower(), name): values
            for name, values in statements.items()}


def annual_basis(snapshot):
    if snapshot.get('annual'):
        return normalize_statements(snapshot['annual']), 'annual'
    quarterly = normalize_statements(snapshot.get('quarterly', {}))
    # Use only period ends with actual revenue observations, ignoring empty provider columns.
    periods = sorted(p for p, value in quarterly.get('Total Revenue', {}).items()
                     if number(value) is not None)
    if len(periods) < 4:
        return {}, 'insufficient_quarters'
    annual = {}
    for index in range(3, len(periods)):
        window = periods[index - 3:index + 1]
        dates = [date.fromisoformat(p) for p in window]
        gaps = [(b - a).days for a, b in zip(dates, dates[1:])]
        if not all(60 <= gap <= 110 for gap in gaps):
            continue
        for metric, values in quarterly.items():
            if metric in FLOW_METRICS:
                inputs = [number(values.get(p)) for p in window]
                value = sum(inputs) if all(v is not None for v in inputs) else None
            else:
                value = number(values.get(window[-1]))
            if value is not None:
                annual.setdefault(metric, {})[window[-1]] = value
    return annual, 'ttm_from_quarters'


def metrics(snapshot, fx_rate=None):
    """fx_rate = quote currency units per reporting currency unit, same observation date.

    Annual statements only: never compare one quarter's flow to a full market cap.
    FX and ADR/share-unit alignment must be supplied/verified before cross-currency valuation.
    """
    info = snapshot.get('info', {})
    annual, basis = annual_basis(snapshot)
    periods = sorted({p for values in annual.values() for p in values}, reverse=True)
    period = periods[0] if periods else None

    def get(*names, at=period):
        for name in names:
            value = number(annual.get(name, {}).get(at))
            if value is not None:
                return value
        return None

    reporting, quote = info.get('financialCurrency'), info.get('currency')
    fx = 1.0 if reporting and quote and reporting == quote else number(fx_rate)
    if fx is not None and fx <= 0:
        raise ValueError('FX rate must be positive')
    equity = get('Stockholders Equity', 'Common Stock Equity')
    debt = get('Total Debt')
    cash = get('Cash And Cash Equivalents')
    revenue = get('Total Revenue')
    fcf = get('Free Cash Flow')
    if fcf is None:
        operating, capex = get('Operating Cash Flow'), get('Capital Expenditure')
        if operating is not None and capex is not None:
            fcf = operating - abs(capex)
    net_income = get('Net Income')
    retained = get('Retained Earnings')
    retained_history = (normalize_statements(snapshot.get('quarterly', {}))
                        if basis == 'ttm_from_quarters' else annual).get('Retained Earnings', {})
    retained_dates = sorted(retained_history, reverse=True)
    prior_dates = [p for p in retained_dates if period and 300 <= (date.fromisoformat(period) - date.fromisoformat(p)).days <= 430]
    previous = number(retained_history.get(prior_dates[0])) if prior_dates else None
    market_cap = number(info.get('marketCap'))
    convert = lambda v: v * fx if v is not None and fx is not None else None
    price = number(info.get('currentPrice', info.get('regularMarketPrice')))
    result = {
        'period_end': period, 'flow_basis': basis, 'source': snapshot.get('source'),
        'observed_at': snapshot.get('observed_at'),
        'reporting_currency': reporting, 'quote_currency': quote,
        'currency_aligned': fx is not None, 'fx_rate': fx,
        'market_cap': market_cap, 'price': price,
        'shares_outstanding': number(info.get('sharesOutstanding')),
        'beta': number(info.get('beta')), 'cash': cash, 'total_debt': debt,
        'net_debt_quote': convert(debt - cash) if debt is not None and cash is not None else None,
        'fcf_quote': convert(fcf), 'debt_quote': convert(debt),
        'interest_expense_quote': convert(abs(get('Interest Expense'))) if get('Interest Expense') is not None else None,
        'cash_minus_debt': cash - debt if cash is not None and debt is not None else None,
        'liabilities_to_equity': ratio(get('Total Liabilities Net Minority Interest'), equity),
        'long_term_debt_to_equity': ratio(get('Long Term Debt'), equity),
        'preferred_stock': get('Preferred Stock'),
        'retained_earnings_change': retained - previous if retained is not None and previous is not None else None,
        'retained_earnings_growth': ratio(retained - previous, previous) if retained is not None and previous is not None else None,
        'treasury_stock': get('Treasury Stock'),
        'buyback_cash': abs(get('Repurchase Of Capital Stock')) if get('Repurchase Of Capital Stock') is not None else None,
        'fcf_yield': ratio(convert(fcf), market_cap),
        'book_to_market': ratio(convert(equity), market_cap),
        'price_to_book': ratio(market_cap, convert(equity)),
        'price_to_sales': ratio(market_cap, convert(revenue)),
        'price_to_earnings': ratio(market_cap, convert(get('Net Income Common Stockholders', 'Net Income'))),
        'revenue': revenue, 'net_margin': ratio(net_income, revenue),
        'roe': ratio(net_income, equity),
        'ebit_margin': ratio(get('EBIT'), revenue),
        'gross_margin': ratio(get('Gross Profit'), revenue),
        'roc': ratio(get('EBIT'), equity + debt - cash) if all(v is not None for v in (equity, debt, cash)) else None,
    }
    return result


def presets(config_path=None):
    from .settings import load_settings, screen_rules
    settings = load_settings(config_path)
    return {name: screen_rules(settings, name) for name in settings['screens']}


def screen(snapshots, preset='value', rules=None, fx_rates=None):
    import operator
    operators = {'gt': operator.gt, 'ge': operator.ge, 'lt': operator.lt,
                 'le': operator.le, 'eq': operator.eq}
    rules = presets()[preset] if rules is None else rules
    rows = []
    for symbol, snapshot in snapshots.items():
        row = metrics(snapshot, (fx_rates or {}).get(symbol))
        failed, missing = [], []
        for field, op, cutoff in rules:
            if row.get(field) is None:
                missing.append(field)
            elif not operators[op](row[field], cutoff):
                failed.append(field)
        row.update(symbol=symbol, passed=not failed and not missing,
                   failed_rules=','.join(failed), missing_rules=','.join(missing))
        rows.append(row)
    if not rows:
        return pd.DataFrame(columns=['symbol', 'passed'])
    from .settings import load_settings
    ordering = load_settings()['reports']
    return pd.DataFrame(rows).sort_values(['passed'] + ordering['rank_by'],
                                         ascending=[False] + [not value for value in ordering['rank_descending']],
                                         na_position='last')
