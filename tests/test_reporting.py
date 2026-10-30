from datetime import datetime, timezone
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
        self.assertIn('Morning', subject)
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


if __name__ == '__main__':
    unittest.main()
