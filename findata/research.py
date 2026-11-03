"""Build screen/DCF inputs exclusively from the new data lake.

Use one financial source and one reporting currency per company. Do not silently
combine different statement providers, fiscal frequencies, or currency presentations.
"""
import gzip
import json
import re

import pandas as pd

from .screening import CANONICAL, number

ALIASES = {
    'totalrevenue': 'Total Revenue', 'netincome': 'Net Income',
    'netincometocommon': 'Net Income Common Stockholders',
    'totalgrossprofit': 'Gross Profit', 'grossprofit': 'Gross Profit',
    'stockholdersequity': 'Stockholders Equity', 'totalequity': 'Stockholders Equity',
    'commonstockequity': 'Common Stock Equity', 'totalcommonequity': 'Common Stock Equity',
    'cashandequivalents': 'Cash And Cash Equivalents',
    'totalliabilities': 'Total Liabilities Net Minority Interest',
    'totalinterestexpense': 'Interest Expense', 'interestexpensenonoperating': 'Interest Expense',
    'netcashfromoperatingactivities': 'Operating Cash Flow',
    'repurchaseofcommonequity': 'Repurchase Of Capital Stock',
    'purchaseofplantpropertyandequipment': 'Capital Expenditure',
    'basiceps': 'Basic EPS', 'dilutedeps': 'Diluted EPS',
    'weightedavebasicsharesos': 'Basic Average Shares',
    'weightedavedilutedsharesos': 'Diluted Average Shares',
    'totalcurrentassets': 'Current Assets', 'totalcurrentliabilities': 'Current Liabilities',
    'inventories': 'Inventory', 'totalcashandcashequivalents': 'Cash And Cash Equivalents',
    'netcashprovidedbyoperatingactivities': 'Operating Cash Flow',
    'purchaseofpropertyplantandequipment': 'Capital Expenditure',
}
ALIASES.update(CANONICAL)


def canonical_metric(name):
    return ALIASES.get(re.sub(r'[^a-z0-9]', '', str(name).lower()))


def read_raw(lake, path):
    with gzip.open(lake.root / path, 'rt') as stream:
        return json.load(stream)


def load_snapshots(lake, symbols=None, source=None):
    """Load bounded per-company frames instead of the full universe into one DataFrame."""
    with lake.connect() as db:
        entities = [r[0] for r in db.execute("SELECT DISTINCT entity FROM observations WHERE dataset='financials'")]
        profile_paths = dict(db.execute('''SELECT entity, raw_path FROM (
            SELECT *, ROW_NUMBER() OVER(PARTITION BY entity ORDER BY observed_at DESC,rowid DESC) rank
            FROM observations WHERE dataset='profiles' AND source='yfinance') WHERE rank=1''').fetchall())
        profile_dates = dict(db.execute('''SELECT entity, observed_at FROM (
            SELECT *, ROW_NUMBER() OVER(PARTITION BY entity ORDER BY observed_at DESC,rowid DESC) rank
            FROM observations WHERE dataset='profiles' AND source='yfinance') WHERE rank=1''').fetchall())
    requested = set(symbols) if symbols else None
    snapshots = {}
    for symbol in entities:
        if requested is not None and symbol not in requested:
            continue
        frame = lake.current('financials', entity=symbol, source=source)
        if frame.empty:
            continue
        # Most recently collected source wins explicitly for this company; older periods from
        # that source remain available even when a refresh covers only recent periods.
        newest = frame.sort_values('observed_at', kind='stable').iloc[-1]
        selected_source = newest['source']
        frame = frame.loc[frame.source.eq(selected_source)].copy()
        raw = read_raw(lake, newest['raw_path'])
        info = dict(raw.get('info', {})) if isinstance(raw, dict) else {}
        quote_observed = newest['observed_at'] if info else None
        if symbol in profile_paths and (not quote_observed or profile_dates[symbol] >= quote_observed):
            info.update(read_raw(lake, profile_paths[symbol]))
            quote_observed = profile_dates[symbol]
        snapshot = {'info': info, 'annual': {}, 'quarterly': {}, 'source': selected_source,
                    'observed_at': newest['observed_at'], 'profile_observed_at': quote_observed}
        frame['canonical'] = frame.metric.map(canonical_metric)
        frame = frame.loc[frame.canonical.notna() & frame.frequency.isin(['annual', 'quarterly'])]
        currencies = frame.loc[frame.currency.notna()].sort_values('period_end')
        reporting = currencies.iloc[-1]['currency'] if len(currencies) else None
        # Unknown currency never inherits the quote currency. Retain values for within-source
        # inspection, but currency-dependent valuations will remain unavailable.
        info['financialCurrency'] = reporting
        if reporting is not None:
            frame = frame.loc[frame.currency.eq(reporting)]
        frame = frame.sort_values(['observed_at', 'filing_date'], na_position='first', kind='stable')
        for item in frame.to_dict('records'):
            value = number(item['value'])
            if value is not None and isinstance(item['period_end'], str):
                snapshot[item['frequency']].setdefault(item['canonical'], {})[item['period_end']] = value
        snapshots[symbol] = snapshot
    return snapshots
