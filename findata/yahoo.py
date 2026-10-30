"""Yahoo financial snapshots used by the lake provider and report refresh."""
import pandas as pd
import yfinance
from .store import clean


def statement_dict(frames):
    result = {}
    for frame in frames:
        for label, row in frame.items():
            period = pd.Timestamp(label).strftime('%Y-%m-%d')
            for metric, value in row.items():
                if pd.notna(value):
                    result.setdefault(str(metric), {})[period] = float(value)
    return result


def fetch_snapshot(symbol):
    stock = yfinance.Ticker(symbol.replace('.', '-'))
    info = stock.get_info()
    if not info:
        raise ValueError(f'{symbol}: empty company metadata')
    statements = {}
    for frequency, provider_frequency in [('quarterly', 'quarterly'), ('annual', 'yearly')]:
        statements[frequency] = statement_dict([
            stock.get_income_stmt(freq=provider_frequency),
            stock.get_cash_flow(freq=provider_frequency),
            stock.get_balance_sheet(freq=provider_frequency),
        ])
    if not statements['annual'] and not statements['quarterly']:
        raise ValueError(f'{symbol}: no financial statements returned')
    # Keep every reporting currency, including unknown currency metadata.
    return clean({'info': info, 'calendar': stock.get_calendar(), **statements})
