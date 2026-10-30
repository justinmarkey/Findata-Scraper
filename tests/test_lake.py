import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd
from findata.store import Lake, key
from findata.providers import sec_facts_rows, earnings_rows
from findata.pipeline import collect, earnings_changes, backfill


class LakeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.lake = Lake(self.temp.name)

    def price(self, day, close):
        return {'symbol': 'X', 'source': 'test', 'date': day, 'close': close,
                'volume': 10, 'currency': 'EUR'}

    def test_parquet_roundtrip_revisions_and_provenance(self):
        self.lake.write('prices', 'X', 'test', {'x': float('nan')},
                        [self.price('2025-01-01', 10), self.price('2025-01-02', 11)],
                        observed_at='2026-01-01T00:00:00+00:00')
        self.lake.write('prices', 'X', 'test', {'x': 12}, [self.price('2025-01-02', 12)],
                        observed_at='2026-02-01T00:00:00+00:00')
        all_rows = self.lake.read('prices')
        current = self.lake.current('prices')
        self.assertEqual(len(all_rows), 3)
        self.assertEqual(current.close.tolist(), [10, 12])
        self.assertEqual(current.currency.tolist(), ['EUR', 'EUR'])
        self.assertEqual(str(current.volume.dtype), 'Int64')
        with gzip.open(Path(self.temp.name) / all_rows.iloc[0].raw_path, 'rt') as stream:
            self.assertIsNone(json.load(stream)['x'])
        old = self.lake.current('prices', as_of='2026-01-15T00:00:00+00:00')
        self.assertEqual(old.close.tolist(), [10, 11])

    def test_streaming_export_matches_current(self):
        self.lake.write('prices', 'X', 'test', {}, [self.price('2025-01-01', 10)])
        self.lake.write('prices', 'X', 'test', {}, [self.price('2025-01-01', 12)])
        path = Path(self.temp.name) / 'export.parquet'
        self.assertEqual(self.lake.export('prices', path, symbol='X'), 1)
        self.assertEqual(pd.read_parquet(path).close.tolist(), [12])

    def test_financial_annual_and_quarterly_do_not_collapse(self):
        base = {'symbol': 'X', 'source': 'test', 'metric': 'EPS', 'period_end': '2025-12-31', 'value': 1}
        self.lake.write('financials', 'X', 'test', {}, [dict(base, frequency='annual'), dict(base, frequency='quarterly')])
        self.assertEqual(len(self.lake.current('financials')), 2)

    def test_failed_write_is_not_visible(self):
        with patch('pandas.DataFrame.to_parquet', side_effect=RuntimeError('disk full')):
            with self.assertRaises(RuntimeError):
                self.lake.write('prices', '../X', 'test', {}, [self.price('2025-01-01', 10)])
        self.assertTrue(self.lake.read('prices').empty)
        self.assertNotIn('/', key('../X'))

    def test_resume_and_bounded_failure(self):
        calls = []
        def fetch(entity):
            calls.append(entity)
            if entity == 'BAD':
                raise ValueError('missing')
            return {}, [self.price('2025-01-01', 10)]
        result = collect(self.lake, 'prices', ['X', 'BAD'], 'test', {}, fetch, attempts=2, delay=0)
        self.assertEqual(result['completed'], 1)
        self.assertEqual(calls.count('BAD'), 2)
        result = collect(self.lake, 'prices', ['X'], 'test', {}, fetch)
        self.assertEqual(result['skipped'], 1)
        self.assertEqual(calls.count('X'), 1)

    def test_sec_units_vintages_and_ytd(self):
        fact = {'start': '2025-01-01', 'end': '2025-06-30', 'val': 100,
                'filed': '2025-08-01', 'accn': 'A', 'fy': 2025, 'fp': 'Q2'}
        raw = {'cik': 1, 'facts': {'ifrs-full': {'Revenue': {'units': {'EUR': [fact, dict(fact, accn='B', val=110)]}}}}}
        rows = sec_facts_rows('X', raw)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['currency'], 'EUR')
        self.assertEqual(rows[0]['frequency'], 'ytd_or_stub')
        self.assertEqual(rows[0]['value'], 100)
        self.assertNotEqual(rows[0]['accession'], rows[1]['accession'])

    def test_earnings_actuals_estimates_date_changes(self):
        raw = [{'symbol': 'X', 'report_date': '2026-11-01', 'period_ending': '2026-09',
                'eps_consensus': 1.2, 'eps_actual': None}]
        rows = earnings_rows(raw, 'openbb:nasdaq')
        self.assertEqual(rows[0]['event_id'], '2026-09')
        self.assertEqual(rows[0]['date_status'], 'unknown')
        self.assertIsNone(rows[0]['eps_actual'])
        self.lake.write('earnings', 'window', 'openbb:nasdaq', raw, rows,
                        observed_at='2026-10-01T00:00:00+00:00')
        raw[0].update(report_date='2026-11-02', eps_actual=1.4)
        self.lake.write('earnings', 'window', 'openbb:nasdaq', raw, earnings_rows(raw, 'openbb:nasdaq'),
                        observed_at='2026-11-03T00:00:00+00:00')
        changes = earnings_changes(self.lake)
        self.assertEqual(set(changes.field), {'report_date', 'eps_actual'})
        self.assertEqual(len(self.lake.current('earnings')), 1)

    def test_missing_quarters_do_not_discard_foreign_annual_statements(self):
        from types import SimpleNamespace
        import sys
        from findata.providers import financials
        def statement(**kwargs):
            if kwargs['period'] == 'quarterly':
                raise ValueError('No quarterly filings')
            record = SimpleNamespace(model_dump=lambda **_: {
                'period_ending': '2025-12-31', 'reported_currency': 'TWD', 'total_revenue': 100})
            return SimpleNamespace(results=[record])
        obb = SimpleNamespace(equity=SimpleNamespace(fundamental=SimpleNamespace(
            income=statement, balance=statement, cash=statement)))
        with patch.dict(sys.modules, {'openbb': SimpleNamespace(obb=obb)}):
            raw, rows = financials('TSM', 'openbb:sec')
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]['currency'], 'TWD')
        self.assertEqual(len(raw['_errors']), 3)
        result = collect(self.lake, 'financials', ['TSM'], 'openbb:sec', {}, lambda _: (raw, rows))
        self.assertIn('TSM', result['partial'])
        self.assertEqual(len(self.lake.current('financials')), 3)

    def test_daily_price_adjustment_flags_and_inclusive_end(self):
        from findata.providers import prices
        from types import SimpleNamespace
        from unittest.mock import Mock
        history = pd.DataFrame({'Open': [100], 'High': [102], 'Low': [99], 'Close': [101],
                                'Adj Close': [98], 'Volume': [1000], 'Dividends': [0], 'Stock Splits': [0]},
                               index=pd.DatetimeIndex(['2025-06-30'], tz='America/New_York', name='Date'))
        fetch = Mock(return_value=history)
        ticker = SimpleNamespace(history=fetch, get_history_metadata=lambda: {'currency': 'USD'})
        with patch('yfinance.Ticker', return_value=ticker) as constructor:
            raw, rows = prices('BRK.B', '2025-06-01', '2025-06-30')
        constructor.assert_called_once_with('BRK-B')
        self.assertEqual(fetch.call_args.kwargs['end'], '2025-07-01')
        self.assertFalse(fetch.call_args.kwargs['auto_adjust'])
        self.assertEqual(rows[0]['close'], 101)
        self.assertEqual(rows[0]['adj_close'], 98)
        self.assertEqual(rows[0]['date'], '2025-06-30')

    def test_explicit_date_window_and_sources(self):
        with patch('findata.providers.prices', return_value=({}, [self.price('2025-01-01', 10)])) as prices:
            backfill(self.lake, ['X'], datasets=['prices'], start='2025-01-01', end='2025-01-05')
            prices.assert_called_once_with('X', '2025-01-01', '2025-01-05', 'yfinance')
        with self.assertRaises(ValueError):
            backfill(self.lake, ['X'], start='2025-01-05', end='2025-01-01')


if __name__ == '__main__':
    unittest.main()
