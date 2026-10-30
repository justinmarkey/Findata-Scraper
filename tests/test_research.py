from pathlib import Path
import tempfile
import unittest

from findata.providers import snapshot_rows
from findata.research import load_snapshots
from findata.screening import metrics
from findata.store import Lake


class ResearchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.lake = Lake(self.temp.name)

    def test_sec_financials_and_profile_form_screen_inputs(self):
        values = {'total_revenue': 200, 'net_income': 20, 'total_equity': 100,
                  'long_term_debt': 0, 'net_cash_from_operating_activities': 40,
                  'purchase_of_plant_property_and_equipment': 10}
        rows = [{'symbol': 'X', 'source': 'openbb:sec', 'frequency': 'annual',
                 'statement': 'income', 'metric': key, 'value': value,
                 'period_end': '2025-12-31', 'currency': 'USD'} for key, value in values.items()]
        self.lake.write('financials', 'X', 'openbb:sec', {}, rows)
        self.lake.write('profiles', 'X', 'yfinance', {'marketCap': 150, 'currency': 'USD'},
                        [{'symbol': 'X', 'source': 'yfinance'}])
        snapshot = load_snapshots(self.lake)['X']
        self.assertEqual(snapshot['source'], 'openbb:sec')
        self.assertEqual(metrics(snapshot)['price_to_earnings'], 7.5)
        self.assertEqual(metrics(snapshot)['fcf_yield'], .2)
        self.assertEqual(metrics(snapshot)['price_to_book'], 1.5)

    def test_foreign_reporting_currency_is_not_replaced_by_quote_currency(self):
        raw = {'info': {'marketCap': 150, 'currency': 'USD', 'financialCurrency': 'EUR'},
               'annual': {'Total Revenue': {'2025-12-31': 200}}}
        self.lake.write('financials', 'X', 'yfinance', raw, snapshot_rows('X', raw))
        snapshot = load_snapshots(self.lake)['X']
        self.assertEqual(snapshot['info']['financialCurrency'], 'EUR')
        self.assertIsNone(metrics(snapshot)['price_to_sales'])
        self.assertEqual(metrics(snapshot, 2)['price_to_sales'], .375)

    def test_empty_lake_is_a_valid_start(self):
        self.assertEqual(load_snapshots(self.lake), {})
        self.assertFalse((Path(self.temp.name) / 'findata.sqlite3').exists())


if __name__ == '__main__':
    unittest.main()
