from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

from findata.reporting import (build_report, candidate_symbols, compact_description,
                               delivery_status, freshness, mark_delivered, render, shortlist)
from findata.store import Lake
from findata.screening import metrics


NOW = datetime(2026, 10, 29, 11, 30, tzinfo=timezone.utc)
CONFIG = {'recipient': 'justinsmarkey@gmail.com', 'timezone': 'America/New_York',
          'screens': ['value'], 'top_per_screen': 3, 'max_refresh': 4,
          'refresh_per_screen': 3, 'max_quote_age_days': 7, 'max_statement_age_days': 550,
          'profile_max_characters': 700}


def company():
    values = {'Total Revenue': 200, 'Net Income': 20, 'Stockholders Equity': 100,
              'Long Term Debt': 0, 'Free Cash Flow': 30}
    return {'source': 'yfinance', 'observed_at': NOW.isoformat(),
            'info': {'financialCurrency': 'USD', 'currency': 'USD', 'marketCap': 150,
                     'longName': 'Example Inc', 'longBusinessSummary': 'Makes equipment. Sells products and maintenance.',
                     'regularMarketTime': NOW.timestamp()},
            'annual': {k: {'2025-12-31': v} for k, v in values.items()}}


class ReportingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.lake = Lake(self.root / 'lake')

    def test_stale_historical_matches_are_not_current_picks(self):
        stale = company()
        stale['source'] = 'yfinance'
        stale['annual'] = {k: {'2024-09-30': next(iter(v.values()))} for k, v in stale['annual'].items()}
        picks, summaries = shortlist({'OLD': stale, 'X': company()}, CONFIG, NOW)
        self.assertEqual([r['symbol'] for r in picks], ['X'])
        self.assertEqual(summaries[0]['stale_matches'], 1)
        stale['info']['regularMarketTime'] = datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp()
        self.assertIn('quote/metadata stale', freshness(stale, metrics(stale), NOW, CONFIG))

    def test_escaped_business_summary_and_no_fake_earnings(self):
        s = company()
        s['info'].update(longBusinessSummary='<script>bad()</script> Makes products.', website='javascript:bad()')
        picks, summaries = shortlist({'X': s}, CONFIG, NOW)
        subject, html, plain, keys = render(picks, summaries, {'X': s}, pd.DataFrame(), CONFIG, NOW)
        self.assertIn('2026-10-29 07:30:00 EDT', subject)
        self.assertNotIn('<script>', html)
        self.assertIn('&lt;script&gt;', html)
        self.assertNotIn('href="javascript:', html)
        self.assertIn('Not available in the stored calendar', html)
        self.assertIn('Makes products', plain)
        self.assertEqual(keys, ['value:X'])

    def test_refresh_candidates_are_deduplicated_and_bounded(self):
        config = dict(CONFIG, screens=['value', 'multibagger'], max_refresh=1)
        result = candidate_symbols({'X': company(), 'Y': company()}, config)
        self.assertEqual(len(result), 1)

    def test_delivery_state_changes_only_after_confirmed_send(self):
        config_path = self.root / 'config.json'
        config_path.write_text(json.dumps(CONFIG))
        with patch('findata.reporting.load_snapshots', return_value={'X': company()}):
            message_path = build_report(self.lake, config_path=config_path, generated_at=NOW, output=self.root / 'report')
        message = json.loads(message_path.read_text())
        self.assertIsNone(message['already_delivered_gmail_id'])
        self.assertFalse((self.lake.root / 'reports/last_delivered.json').exists())
        with self.assertRaises(ValueError):
            mark_delivered(self.lake, message_path, '')
        mark_delivered(self.lake, message_path, 'confirmed-id')
        self.assertEqual(delivery_status(self.lake, message['delivery_id']), 'confirmed-id')
        state = json.loads((self.lake.root / 'reports/last_delivered.json').read_text())
        self.assertEqual(state['keys'], ['value:X'])
        with patch('findata.reporting.load_snapshots', return_value={'X': company()}):
            repeated = build_report(self.lake, config_path=config_path, generated_at=NOW, output=self.root / 'repeat')
        self.assertEqual(json.loads(repeated.read_text())['already_delivered_gmail_id'], 'confirmed-id')

    def test_missing_description_is_explicit(self):
        self.assertIn('unavailable', compact_description(None, 100))
        self.assertLessEqual(len(compact_description('word ' * 200, 100)), 101)

    def test_under_cash_report_shows_cash_date_without_requiring_annual_flows(self):
        s = company()
        s['annual'] = {}
        s['quarterly'] = {'Cash And Cash Equivalents': {'2026-09-30': 200}}
        config = dict(CONFIG, screens=['under_cash'])
        picks, summaries = shortlist({'X': s}, config, NOW)
        self.assertEqual(len(picks), 1)
        self.assertEqual(summaries[0]['fresh_matches'], 1)
        _, html, plain, _ = render(picks, summaries, {'X': s}, pd.DataFrame(), config, NOW)
        self.assertIn('P/C 0.75', html)
        self.assertIn('Balance date 2026-09-30', html)
        self.assertIn('debt is not deducted', plain)

    def test_local_report_exports_all_rows_dates_and_email_without_network(self):
        from findata.providers import snapshot_rows
        good = company()
        good['info']['regularMarketTime'] = datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp()
        bad = company()
        del bad['annual']['Long Term Debt']
        for symbol, payload in [('OLD', good), ('MISSING', bad)]:
            self.lake.write('financials', symbol, 'yfinance', payload, snapshot_rows(symbol, payload),
                            observed_at=NOW.isoformat())
        config_path = self.root / 'config.json'
        config_path.write_text(json.dumps(dict(CONFIG, recipient='', include_stale=True)))
        before = self.lake.current('financials').copy()
        with patch('requests.sessions.Session.request', side_effect=AssertionError('Network used')):
            message_path = build_report(self.lake, config_path=config_path, generated_at=NOW)
        message = json.loads(message_path.read_text())
        self.assertEqual(message['mode'], 'stored')
        self.assertEqual(message['companies_evaluated'], 2)
        self.assertIn('quote/metadata stale', message['html'])
        self.assertEqual(message['data_dates']['OLD']['statement_period'], '2025-12-31')
        self.assertIn('2025-01-01', message['data_dates']['OLD']['quote_at'])
        self.assertIn('Report generated:', message['html'])
        frame = pd.read_parquet(message_path.parent / 'screening.parquet').set_index('symbol')
        self.assertEqual(len(frame), 2)
        self.assertFalse(frame.loc['MISSING', 'passed'])
        self.assertIn('long_term_debt_to_equity', frame.loc['MISSING', 'missing_rules'])
        shortlist = pd.read_parquet(message_path.parent / 'shortlist.parquet')
        self.assertEqual(shortlist.symbol.tolist(), ['OLD'])
        draft = BytesParser(policy=policy.default).parsebytes((message_path.parent / 'report.eml').read_bytes())
        self.assertEqual(draft['X-Unsent'], '1')
        self.assertIsNone(draft['To'])
        self.assertIn('Findata Screener', draft.get_body(preferencelist=('html',)).get_content())
        self.assertIsNotNone(draft.get_body(preferencelist=('plain',)))
        pd.testing.assert_frame_equal(before, self.lake.current('financials'))
        self.assertFalse((self.lake.root / 'reports/last_delivered.json').exists())

    def test_empty_report_and_multiple_manual_runs(self):
        config_path = self.root / 'config.json'
        config_path.write_text(json.dumps(CONFIG))
        first = build_report(self.lake, config_path=config_path, generated_at=NOW)
        later = NOW.replace(microsecond=1)
        second = build_report(self.lake, config_path=config_path, generated_at=later)
        self.assertNotEqual(first, second)
        self.assertNotEqual(json.loads(first.read_text())['delivery_id'], json.loads(second.read_text())['delivery_id'])
        self.assertIn('0 companies', json.loads(first.read_text())['html'])
        self.assertEqual(pd.read_parquet(first.parent / 'screening.parquet').shape[0], 0)

    def test_refresh_uses_configured_statement_provider(self):
        from findata.reporting import refresh_candidates
        summaries = {'financials': {'partial': {}, 'failed': {}}, 'profiles': {'partial': {}, 'failed': {}}}
        with patch('findata.pipeline.backfill', return_value=summaries) as backfill:
            with patch('findata.reporting.load_snapshots', return_value={'X': company()}):
                snapshots = {}
                self.assertEqual(refresh_candidates(self.lake, snapshots, ['X']), {})
        backfill.assert_called_once_with(self.lake, ['X'], datasets=['financials', 'profiles'], refresh=True)
        self.assertIn('X', snapshots)


if __name__ == '__main__':
    unittest.main()
