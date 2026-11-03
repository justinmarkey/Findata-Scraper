"""Explicit adapters. No silent cross-provider fallback or currency filtering."""
from datetime import date, timedelta
from io import StringIO
import os
import time

import pandas as pd
import requests
from .store import clean


class Http:
    def __init__(self, user_agent=None, interval=.25):
        self.session = requests.Session()
        self.session.headers['User-Agent'] = user_agent or 'Findata/0.2'
        self.interval = interval
        self.last = 0.

    def get(self, url):
        time.sleep(max(0, self.interval - (time.monotonic() - self.last)))
        self.last = time.monotonic()
        response = self.session.get(url, timeout=60)
        response.raise_for_status()
        return response


def sec_http():
    identity = os.environ.get('SEC_USER_AGENT', '').strip()
    if not identity:
        raise ValueError('Set SEC_USER_AGENT to your application name and real contact email for SEC access')
    return Http(identity)


def universe(source='nasdaq'):
    if source == 'nasdaq':
        client = Http()
        raw, rows = {}, []
        for filename in ['nasdaqlisted.txt', 'otherlisted.txt']:
            text = client.get('https://www.nasdaqtrader.com/dynamic/SymDir/' + filename).text
            raw[filename] = text
            frame = pd.read_csv(StringIO(text), sep='|', dtype='string')
            for entry in frame.to_dict('records'):
                symbol = entry.get('Symbol', entry.get('ACT Symbol'))
                if not isinstance(symbol, str) or symbol.startswith('File Creation'):
                    continue
                if entry.get('Test Issue') == 'Y' or entry.get('ETF') == 'Y':
                    continue
                rows.append({'symbol': symbol, 'name': entry.get('Security Name'),
                             'exchange': entry.get('Exchange', 'NASDAQ'),
                             'source': source, 'security_type': 'listed_non_etf',
                             'company_id': None, 'country': None, 'currency': None})
        if not rows:
            raise ValueError('Nasdaq symbol directory returned no securities')
        return raw, rows
    if source == 'sec':
        raw = sec_http().get('https://www.sec.gov/files/company_tickers_exchange.json').json()
        rows = []
        for entry in raw['data']:
            item = dict(zip(raw['fields'], entry))
            rows.append({'symbol': item['ticker'], 'name': item['name'],
                         'exchange': item.get('exchange'), 'company_id': str(item['cik']).zfill(10),
                         'source': source, 'security_type': 'sec_registered', 'country': None})
        return raw, rows
    if source == 'financedatabase':
        import financedatabase as fd
        frame = fd.Equities().select().reset_index()
        # Select US listings, not only US-domiciled issuers.
        exchanges = {'NYQ', 'NMS', 'NGM', 'NCM', 'ASE', 'PCX', 'BTS', 'NASDAQ', 'NYSE', 'AMEX'}
        selected = frame.loc[frame['exchange'].isin(exchanges)]
        rows = []
        for item in selected.to_dict('records'):
            rows.append({'symbol': item.get('symbol', item.get('index')), 'name': item.get('name'),
                         'exchange': item.get('exchange'), 'country': item.get('country'),
                         'currency': item.get('currency'), 'source': source, 'security_type': 'equity'})
        if not rows:
            raise ValueError('FinanceDatabase returned no supported US listings; inspect exchange codes')
        return clean(frame.to_dict('records')), clean(rows)
    raise ValueError(f'Unknown universe source: {source}')


def sec_facts_rows(symbol, raw):
    rows = []
    for taxonomy, concepts in raw.get('facts', {}).items():
        for concept, definition in concepts.items():
            for unit, facts in definition.get('units', {}).items():
                for fact in facts:
                    start, end = fact.get('start'), fact.get('end')
                    if end is None or fact.get('val') is None:
                        continue
                    duration = (date.fromisoformat(end) - date.fromisoformat(start)).days if start else None
                    frequency = ('instant' if duration is None else 'annual' if 330 <= duration <= 380
                                 else 'quarterly' if 60 <= duration <= 110 else 'ytd_or_stub')
                    currency = unit.split('/')[0] if len(unit.split('/')[0]) == 3 and unit.split('/')[0].isupper() else None
                    rows.append({'symbol': symbol, 'company_id': str(raw.get('cik', '')).zfill(10),
                                 'source': 'sec', 'statement': 'xbrl_fact', 'frequency': frequency,
                                 'metric': f'{taxonomy}:{concept}', 'period_start': start,
                                 'period_end': end, 'filing_date': fact.get('filed'),
                                 'accession': fact.get('accn'), 'currency': currency, 'unit': unit,
                                 'value': fact['val'], 'fiscal_year': fact.get('fy'),
                                 'fiscal_period': fact.get('fp'), 'derivation': 'reported'})
    return rows


def financials(symbol, source='openbb:sec', cik=None, limit=200):
    if source == 'sec':
        if not cik:
            raise ValueError(f'{symbol}: a CIK is required for SEC companyfacts; use the SEC universe or --cik-map')
        raw = sec_http().get(f'https://data.sec.gov/api/xbrl/companyfacts/CIK{str(cik).zfill(10)}.json').json()
        rows = sec_facts_rows(symbol, raw)
    elif source == 'yfinance':
        from .yahoo import fetch_snapshot
        raw = fetch_snapshot(symbol)
        rows = snapshot_rows(symbol, raw, source)
    elif source.startswith('openbb:'):
        from .settings import openbb_client
        obb = openbb_client()
        provider = source.split(':', 1)[1]
        raw, rows = {'_errors': {}}, []
        metadata = {'period_ending', 'fiscal_period', 'fiscal_year', 'filing_date', 'accepted_date',
                    'cik', 'symbol', 'reported_currency', 'currency', 'link', 'final_link'}
        for statement in ['income', 'balance', 'cash']:
            for frequency in ['annual', 'quarterly']:
                period = frequency if provider == 'sec' else ('annual' if frequency == 'annual' else 'quarter')
                options = {'pit_mode': True} if provider == 'sec' else {}
                try:
                    result = getattr(obb.equity.fundamental, statement)(
                        symbol=symbol, provider=provider, period=period, limit=limit, **options)
                    records = [item.model_dump(mode='json') for item in result.results or []]
                    if not records:
                        raw['_errors'][f'{statement}:{frequency}'] = 'No statements returned'
                except Exception as exc:
                    raw['_errors'][f'{statement}:{frequency}'] = str(exc)
                    continue
                raw[f'{statement}:{frequency}'] = records
                for item in records:
                    for metric, value in item.items():
                        if metric in metadata or not isinstance(value, (int, float)) or isinstance(value, bool):
                            continue
                        rows.append({'symbol': symbol, 'company_id': item.get('cik'),
                                     'source': source, 'statement': statement, 'frequency': frequency,
                                     'metric': metric, 'period_end': item.get('period_ending'),
                                     'filing_date': item.get('filing_date'), 'accepted_at': item.get('accepted_date'),
                                     'accession': item.get('accession_number', item.get('accession')),
                                     'currency': item.get('reported_currency', item.get('currency')),
                                     'value': value, 'fiscal_year': item.get('fiscal_year'),
                                     'fiscal_period': item.get('fiscal_period'),
                                     'derivation': 'provider_normalized'})
    else:
        raise ValueError(f'Unknown financials source: {source}')
    if not rows:
        raise ValueError(f'{symbol}: provider returned no financial facts; {raw.get("_errors", {})}')
    return clean(raw), clean(rows)


def snapshot_rows(symbol, raw, source='yfinance'):
    rows = []
    info = raw.get('info', {})
    for frequency in ['annual', 'quarterly']:
        for metric, periods in raw.get(frequency, {}).items():
            for end, value in periods.items():
                value = clean(value)
                if value is not None:
                    rows.append({'symbol': symbol, 'company_id': info.get('cik'), 'source': source,
                                 'statement': 'combined', 'frequency': frequency, 'metric': metric,
                                 'period_end': end, 'currency': info.get('financialCurrency'),
                                 'value': value, 'derivation': 'provider_normalized'})
    return rows


def prices(symbol, start, end, source='yfinance'):
    """Inclusive requested dates. Preserve provider split-adjusted OHLC and separate Adj Close."""
    if source == 'openbb:yfinance':
        from .settings import openbb_client
        result = openbb_client().equity.price.historical(
            symbol=symbol.replace('.', '-'), start_date=start,
            end_date=(date.fromisoformat(end) + timedelta(days=1)).isoformat(),
            interval='1d', provider='yfinance', adjustment='splits_only', include_actions=True)
        records = [item.model_dump(mode='json') for item in result.results or []]
        rows = []
        for item in records:
            stamp = str(item['date'])[:10]
            if not start <= stamp <= end:
                continue
            rows.append(dict(item, symbol=symbol, source=source, date=stamp,
                             adjustment='provider_split_adjusted'))
        if not rows:
            raise ValueError(f'{symbol}: no OpenBB prices in requested interval')
        return clean(records), clean(rows)
    if source != 'yfinance':
        raise ValueError('Price adapter currently supports yfinance; sources never silently fall back')
    import yfinance as yf
    # Yahoo class-share convention differs from Nasdaq's dot notation.
    ticker = yf.Ticker(symbol.replace('.', '-'))
    frame = ticker.history(start=start, end=(date.fromisoformat(end) + timedelta(days=1)).isoformat(),
                           interval='1d', auto_adjust=False, back_adjust=False, actions=True,
                           raise_errors=True)
    if frame.empty:
        raise ValueError(f'{symbol}: no prices in requested interval (may be unlisted or no trading sessions)')
    currency = ticker.get_history_metadata().get('currency')
    records = frame.reset_index().to_dict('records')
    rows = []
    for item in records:
        stamp = item.get('Date', item.get('Datetime'))
        rows.append({'symbol': symbol, 'source': source, 'date': pd.Timestamp(stamp).date().isoformat(),
                     'currency': currency, 'open': item.get('Open'), 'high': item.get('High'),
                     'low': item.get('Low'), 'close': item.get('Close'), 'adj_close': item.get('Adj Close'),
                     'volume': item.get('Volume'), 'dividend': item.get('Dividends'),
                     'split_ratio': item.get('Stock Splits'), 'adjustment': 'provider_split_adjusted'})
    return clean({'metadata': {'currency': currency, 'adjustment': 'provider_split_adjusted'},
                  'records': records}), clean(rows)


def earnings(start, end, source='openbb:nasdaq'):
    from .settings import openbb_client
    obb = openbb_client()
    if not source.startswith('openbb:'):
        raise ValueError('Use an explicit OpenBB earnings provider, e.g. openbb:nasdaq or openbb:fmp')
    result = obb.equity.calendar.earnings(start_date=start, end_date=end, provider=source.split(':', 1)[1])
    raw = [item.model_dump(mode='json') for item in result.results or []]
    rows = earnings_rows(raw, source)
    return raw, rows


def earnings_rows(records, source):
    rows = []
    for item in records:
        symbol = item.get('symbol')
        report_date = item.get('report_date', item.get('date'))
        if not symbol or not report_date:
            continue
        fiscal_end = item.get('fiscal_period_end') or item.get('fiscal_date_ending') or item.get('period_ending')
        # Date changes can be matched only when the provider supplies a stable fiscal period/id.
        event_id = str(item.get('id') or fiscal_end or report_date)
        rows.append({'symbol': symbol, 'source': source, 'event_id': event_id,
                     'report_date': str(report_date)[:10], 'fiscal_period_end': fiscal_end,
                     'release_time': item.get('time', item.get('reporting_time')),
                     'currency': item.get('currency') or ('USD' if source == 'openbb:nasdaq' else None),
                     'eps_actual': item.get('eps_actual'),
                     'eps_estimate': item.get('eps_consensus', item.get('eps_estimate')),
                     'revenue_actual': item.get('revenue_actual'),
                     'revenue_estimate': item.get('revenue_consensus', item.get('revenue_estimate')),
                     # Never infer confirmed just because a forecast date was returned.
                     'date_status': item.get('date_status', 'unknown')})
    return clean(rows)


def profile_row(symbol, info):
    from urllib.parse import quote
    return {'symbol': symbol, 'source': 'yfinance',
            'name': info.get('longName') or info.get('shortName') or symbol,
            'sector': info.get('sector'), 'industry': info.get('industry'),
            'description': info.get('longBusinessSummary'), 'website': info.get('website'),
            'source_url': f'https://finance.yahoo.com/quote/{quote(symbol, safe="")}/profile/'}


def company_profile(symbol):
    import yfinance as yf
    info = yf.Ticker(symbol.replace('.', '-')).get_info()
    if not info:
        raise ValueError(f'{symbol}: empty company profile')
    return clean(info), [clean(profile_row(symbol, info))]
