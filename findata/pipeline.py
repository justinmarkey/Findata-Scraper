"""Resumable, bounded collection jobs; successes and failures are recorded independently."""
from datetime import date
import json
import time

import pandas as pd
from . import providers


def validate_dates(start, end):
    if date.fromisoformat(start) > date.fromisoformat(end):
        raise ValueError('start must be on or before end')


def collect(lake, dataset, entities, source, request, fetch, *, attempts=3, delay=2, refresh=False):
    if attempts < 1 or delay < 0:
        raise ValueError('attempts must be positive and delay nonnegative')
    summary = {'completed': 0, 'skipped': 0, 'partial': {}, 'failed': {}}
    for entity in dict.fromkeys(entities):
        if not refresh and lake.job(dataset, entity, source, request) == 'complete':
            summary['skipped'] += 1
            continue
        for attempt in range(attempts):
            lake.job(dataset, entity, source, request, 'running')
            try:
                raw, rows = fetch(entity)
                lake.write(dataset, entity, source, raw, rows, request=request)
                gaps = raw.get('_errors') if isinstance(raw, dict) else None
                status = 'partial' if gaps else 'complete'
                lake.job(dataset, entity, source, request, status, json.dumps(gaps) if gaps else '')
                if gaps:
                    summary['partial'][entity] = gaps
                else:
                    summary['completed'] += 1
                print(json.dumps({'dataset': dataset, 'entity': entity, 'status': status, 'rows': len(rows)}), flush=True)
                break
            except Exception as exc:
                lake.job(dataset, entity, source, request, 'failed', str(exc))
                if attempt + 1 == attempts:
                    summary['failed'][entity] = str(exc)
                    print(json.dumps({'dataset': dataset, 'entity': entity, 'status': 'failed', 'error': str(exc)}), flush=True)
                else:
                    time.sleep(delay * (2 ** attempt))
    return summary


def refresh_universe(lake, source='nasdaq'):
    raw, rows = providers.universe(source)
    lake.write('universe', 'US', source, raw, rows)
    return len(rows)


def resolve_symbols(lake, symbols=None, csv=None):
    if symbols:
        return list(dict.fromkeys(s.strip().upper() for s in symbols if s.strip()))
    if csv:
        frame = pd.read_csv(csv, dtype='string')
        column = 'Symbol' if 'Symbol' in frame else 'symbol'
        return frame[column].dropna().str.strip().str.upper().drop_duplicates().tolist()
    frame = lake.current('universe')
    if frame.empty:
        raise ValueError('No universe stored. Run universe or pass --symbols / --symbols-csv')
    return frame['symbol'].dropna().drop_duplicates().tolist()


def backfill(lake, symbols, *, datasets=None, start=None, end=None,
             financial_source=None, price_source=None, cik_map=None,
             attempts=None, refresh=False, statement_limit=None):
    from .settings import load_settings
    settings = load_settings()
    collection, sources = settings['collection'], settings['providers']
    datasets = collection['datasets'] if datasets is None else datasets
    start = start or collection['start_date']
    financial_source = financial_source or sources['financials']
    price_source = price_source or sources['prices']
    attempts = collection['attempts'] if attempts is None else attempts
    statement_limit = collection['statement_limit'] if statement_limit is None else statement_limit
    end = end or date.today().isoformat()
    validate_dates(start, end)
    results = {}
    cik_map = cik_map or {}
    for dataset in datasets:
        if dataset == 'financials':
            # SEC/provider history is fetched in full, not truncated by the requested price interval.
            request = {'limit': statement_limit, 'cik_map': cik_map, 'normalization_version': 1}
            results[dataset] = collect(
                lake, dataset, symbols, financial_source, request,
                lambda symbol: providers.financials(symbol, financial_source, cik_map.get(symbol), statement_limit),
                attempts=attempts, refresh=refresh)
        elif dataset == 'prices':
            request = {'start': start, 'end': end, 'interval': '1d', 'auto_adjust': False}
            results[dataset] = collect(
                lake, dataset, symbols, price_source, request,
                lambda symbol: providers.prices(symbol, start, end, price_source),
                attempts=attempts, refresh=refresh)
        elif dataset == 'profiles':
            results[dataset] = collect(lake, dataset, symbols, 'yfinance',
                                       {'schema_version': 1}, providers.company_profile,
                                       attempts=attempts, refresh=refresh)
        else:
            raise ValueError(f'Unknown backfill dataset: {dataset}')
    return results


def track_earnings(lake, start, end, source='openbb:nasdaq', attempts=3):
    validate_dates(start, end)
    # Split long ranges to keep provider requests bounded and independently resumable/retryable.
    results = []
    for stamp in pd.date_range(start, end, freq='7D'):
        first = stamp.date().isoformat()
        last = min(stamp + pd.Timedelta(days=6), pd.Timestamp(end)).date().isoformat()
        results.append(collect(lake, 'earnings', [f'{first}_{last}'], source,
                               {'start': first, 'end': last},
                               lambda _, a=first, b=last: providers.earnings(a, b, source),
                               attempts=attempts, refresh=True))
    return results


def earnings_changes(lake, source=None):
    """Compare observation vintages; never invent a date-change link without an event key."""
    frame = lake.read('earnings', source=source)
    output = []
    if frame.empty:
        return pd.DataFrame(columns=['symbol', 'source', 'event_id', 'field', 'before', 'after', 'observed_at'])
    for (symbol, provider, event_id), group in frame.groupby(['symbol', 'source', 'event_id']):
        previous = None
        for row in group.sort_values('observed_at', kind='stable').to_dict('records'):
            if previous is not None:
                for field in ['report_date', 'eps_actual', 'eps_estimate', 'revenue_actual', 'revenue_estimate', 'date_status']:
                    before, after = previous[field], row[field]
                    a, b = None if pd.isna(before) else before, None if pd.isna(after) else after
                    if a != b:
                        output.append({'symbol': symbol, 'source': provider, 'event_id': event_id,
                                       'field': field, 'before': a, 'after': b, 'observed_at': row['observed_at']})
            previous = row
    return pd.DataFrame(output, columns=['symbol', 'source', 'event_id', 'field', 'before', 'after', 'observed_at'])
