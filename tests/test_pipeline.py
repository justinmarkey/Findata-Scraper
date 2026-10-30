from pathlib import Path
import unittest
from unittest.mock import patch
import pandas as pd

from findata.yahoo import fetch_snapshot, statement_dict
from findata.screening import metrics, screen
from findata.insiders import clusters, COLUMNS
from findata.valuation import BUNDLED_AUTO_DCF, load_module, value_snapshot


def snapshot(currency='USD'):
    values = {'Total Revenue': 200, 'Net Income': 20, 'Gross Profit': 70,
              'Free Cash Flow': 30, 'Stockholders Equity': 100, 'Total Debt': 0,
              'Cash And Cash Equivalents': 40, 'Total Liabilities Net Minority Interest': 90,
              'Long Term Debt': 0, 'Preferred Stock': 0, 'Treasury Stock': 10,
              'Repurchase Of Capital Stock': -5, 'Retained Earnings': 30, 'EBIT': 15}
    annual = {k: {'2025-12-31': v} for k, v in values.items()}
    annual['Retained Earnings']['2024-12-31'] = 20
    return {'info': {'currency': 'USD', 'financialCurrency': currency, 'marketCap': 150,
                     'sharesOutstanding': 10, 'currentPrice': 15, 'beta': 1},
            'annual': annual, 'quarterly': {}, 'calendar': {}}


class PipelineTests(unittest.TestCase):
    def test_currency_missing_values_and_pe(self):
        m = metrics(snapshot('EUR'))
        self.assertIsNone(m['fcf_yield'])
        self.assertIsNone(m['price_to_earnings'])
        self.assertEqual(m['cash_minus_debt'], 40)
        self.assertEqual(metrics(snapshot('EUR'), 2)['fcf_yield'], .4)
        self.assertEqual(metrics(snapshot())['price_to_earnings'], 7.5)
        s = snapshot()
        del s['annual']['Preferred Stock']
        row = screen({'X': s}, 'buffett_user').iloc[0]
        self.assertFalse(row['passed'])
        self.assertIn('preferred_stock', row['missing_rules'])
        self.assertTrue(screen({'X': snapshot()}, 'value_pe').iloc[0]['passed'])

    def test_ttm_requires_four_complete_quarters(self):
        s = snapshot()
        s['annual'] = {}
        periods = ['2025-03-31', '2025-06-30', '2025-09-30', '2025-12-31']
        s['quarterly'] = {'Total Revenue': dict.fromkeys(periods, 50),
                          'Free Cash Flow': dict.fromkeys(periods, 10),
                          'Stockholders Equity': dict.fromkeys(periods, 100)}
        self.assertAlmostEqual(metrics(s)['fcf_yield'], 40 / 150)
        self.assertEqual(metrics(s)['price_to_book'], 1.5)
        del s['quarterly']['Free Cash Flow'][periods[0]]
        self.assertIsNone(metrics(s)['fcf_yield'])

    def test_retained_earnings_year_ago_balance(self):
        s = snapshot()
        s['annual'] = {}
        periods = ['2024-12-31', '2025-03-31', '2025-06-30', '2025-09-30', '2025-12-31']
        s['quarterly'] = {'TotalRevenue': dict.fromkeys(periods, 50),
                          'RetainedEarnings': dict(zip(periods, [10, 15, 20, 25, 30]))}
        self.assertEqual(metrics(s)['retained_earnings_change'], 20)

    def test_provider_metric_names(self):
        s = snapshot()
        s['annual'] = {k.replace(' ', ''): v for k, v in s['annual'].items()}
        self.assertEqual(metrics(s)['price_to_sales'], .75)

    def test_non_usd_download_is_retained(self):
        class Ticker:
            def get_info(self): return snapshot('EUR')['info']
            def get_calendar(self): return {}
            def get_income_stmt(self, **kw): return pd.DataFrame({pd.Timestamp('2025-12-31'): {'Total Revenue': 200}})
            get_cash_flow = get_income_stmt
            get_balance_sheet = get_income_stmt
        with patch('findata.yahoo.yfinance.Ticker', return_value=Ticker()):
            self.assertEqual(fetch_snapshot('X')['info']['financialCurrency'], 'EUR')

    def test_overlapping_statement_rows(self):
        period = pd.Timestamp('2025-12-31')
        a = pd.DataFrame({period: {'Net Income': 10}})
        b = pd.DataFrame({period: {'Net Income': float('nan'), 'Cash': 3}})
        self.assertEqual(statement_dict([a, b])['Net Income']['2025-12-31'], 10)

    def test_bundled_dcf(self):
        root = BUNDLED_AUTO_DCF
        self.assertTrue(root.is_relative_to(Path(__file__).resolve().parents[1]))
        with patch('findata.valuation.load_module', wraps=load_module) as loader:
            result = value_snapshot(snapshot())
            self.assertTrue(all(call.args[0] == root for call in loader.call_args_list))
        self.assertGreater(result['intrinsic_value'], 0)
        with self.assertRaises(ValueError): value_snapshot(snapshot('EUR'))
        with self.assertRaises(ValueError): value_snapshot(snapshot(), terminal_growth=.5)

    def test_cluster_eligibility_and_no_future_filings(self):
        rows = [[str(i), 'X', str(i), '2026-10-20', '2026-10-21', 'P', 1000, 50,
                 'USD', True, False, False, False, False, 'https://www.sec.gov/test'] for i in range(3)]
        trades = pd.DataFrame(rows, columns=COLUMNS)
        prices = pd.DataFrame({'symbol': ['X', 'X'], 'date': ['2026-09-01', '2026-10-28'],
                               'close': [100, 70], 'currency': ['USD', 'USD']})
        self.assertEqual(len(clusters(trades, prices, as_of='2026-10-28')), 1)
        trades.loc[0, 'is_10b5_1'] = True
        self.assertTrue(clusters(trades, prices, as_of='2026-10-28').empty)
        trades.loc[0, 'is_10b5_1'] = False
        trades.loc[0, 'filed_at'] = '2026-10-29'
        self.assertTrue(clusters(trades, prices, as_of='2026-10-28').empty)


if __name__ == '__main__':
    unittest.main()
