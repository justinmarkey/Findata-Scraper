"""Conservative Form 4 cluster detection over normalized, filing-linked transactions."""
import pandas as pd

COLUMNS = ['transaction_id', 'symbol', 'insider_id', 'transaction_date', 'filed_at',
           'code', 'shares', 'price', 'currency', 'is_director', 'is_officer',
           'is_derivative', 'is_10b5_1', 'is_option_related', 'filing_url']


def clusters(transactions, prices, *, as_of, window_days=30, min_insiders=3,
             min_value=100000, move_threshold=.15, lookback_days=90, currency='USD'):
    """Buys below the prior price high; sells above the prior price low.

    min_value is in currency units. Unknown eligibility flags are excluded.
    Price input: symbol,date,close,currency (split-adjusted prices recommended).
    Only filings available by as_of qualify. Window includes as_of minus window_days.
    """
    if window_days < 1 or lookback_days < 1 or min_insiders < 2 or min_value < 0 or not 0 <= move_threshold < 1:
        raise ValueError('Invalid cluster thresholds')
    missing = set(COLUMNS) - set(transactions)
    if missing:
        raise ValueError('Missing insider columns: ' + ', '.join(sorted(missing)))
    if not {'symbol', 'date', 'close', 'currency'} <= set(prices):
        raise ValueError('Prices require symbol,date,close,currency')
    end = pd.Timestamp(as_of, tz='UTC') if pd.Timestamp(as_of).tzinfo is None else pd.Timestamp(as_of).tz_convert('UTC')
    if len(str(as_of)) == 10:
        end += pd.Timedelta(days=1) - pd.Timedelta(nanoseconds=1)
    t = transactions.copy()
    for key in ['transaction_date', 'filed_at']:
        t[key] = pd.to_datetime(t[key], utc=True, errors='coerce')
    for key in ['shares', 'price']:
        t[key] = pd.to_numeric(t[key], errors='coerce')
    # Strict conversion: bool("False") would incorrectly classify a planned trade.
    def flag(key):
        return t[key].map(lambda v: str(v).strip().lower()).map({'true': True, 'false': False, '1': True, '0': False})
    eligible = (flag('is_director').eq(True) | flag('is_officer').eq(True))
    for key in ['is_derivative', 'is_10b5_1', 'is_option_related']:
        eligible &= flag(key).eq(False)
    eligible &= (t['transaction_date'].between(end - pd.Timedelta(days=window_days), end)
                 & t['filed_at'].le(end) & t['filed_at'].ge(t['transaction_date'])
                 & t['shares'].gt(0) & t['price'].gt(0)
                 & t['currency'].eq(currency) & t['code'].isin(['P', 'S'])
                 & t['insider_id'].notna() & t['transaction_id'].notna()
                 & t['filing_url'].fillna('').str.startswith('https://'))
    t = t.loc[eligible].drop_duplicates(['symbol', 'transaction_id']).copy()
    t['value'] = t['shares'] * t['price']
    p = prices.copy()
    p['date'] = pd.to_datetime(p['date'], utc=True, errors='coerce')
    p['close'] = pd.to_numeric(p['close'], errors='coerce')
    p = p.loc[p['date'].between(end - pd.Timedelta(days=lookback_days), end)
              & p['close'].gt(0) & p['currency'].eq(currency)]
    output = []
    for (symbol, code), group in t.groupby(['symbol', 'code']):
        history = p.loc[p['symbol'].eq(symbol)].sort_values('date').drop_duplicates('date')
        if len(history) < 2:
            continue
        latest = history.iloc[-1]
        # A stale quote cannot establish a current dip/rip.
        if end - latest['date'] > pd.Timedelta(days=7):
            continue
        close = latest['close']
        dip = 1 - close / history['close'].max()
        rip = close / history['close'].min() - 1
        count, value = group['insider_id'].nunique(), group['value'].sum()
        if count >= min_insiders and value >= min_value and (dip if code == 'P' else rip) >= move_threshold:
            output.append({'symbol': symbol, 'signal': 'cluster_dip_buy' if code == 'P' else 'cluster_rip_sell',
                           'insiders': count, 'value': value, 'currency': currency,
                           'dip': dip, 'rip': rip, 'as_of': end.isoformat(),
                           'filings': '|'.join(sorted(set(group['filing_url'])))})
    return pd.DataFrame(output, columns=['symbol', 'signal', 'insiders', 'value', 'currency', 'dip', 'rip', 'as_of', 'filings'])
