"""Use the bundled Auto_DCF calculations with stored Findata inputs."""
import importlib.util
from pathlib import Path
from .screening import metrics, number

BUNDLED_AUTO_DCF = Path(__file__).resolve().parent / '_vendor' / 'auto_dcf'


def load_module(root, name):
    path = Path(root) / 'src' / f'{name}.py'
    spec = importlib.util.spec_from_file_location(f'findata_autodcf_{name}', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def value_snapshot(snapshot, auto_dcf=BUNDLED_AUTO_DCF, *, growth_rate=.08, terminal_growth=.025,
                   years=7, risk_free=.042, market_return=.095, tax_rate=.21, fx_rate=None):
    m = metrics(snapshot, fx_rate)
    required = ['fcf_quote', 'net_debt_quote', 'debt_quote', 'market_cap',
                'shares_outstanding', 'beta']
    missing = [key for key in required if m[key] is None]
    if missing:
        raise ValueError('Missing or currency-unaligned DCF inputs: ' + ', '.join(missing))
    if not isinstance(years, int) or isinstance(years, bool) or years < 1:
        raise ValueError('years must be a positive integer')
    assumptions = [growth_rate, terminal_growth, risk_free, market_return, tax_rate]
    if any(number(v) is None for v in assumptions) or growth_rate <= -1 or not 0 <= tax_rate <= 1:
        raise ValueError('Invalid valuation assumptions')
    if m['shares_outstanding'] <= 0 or m['market_cap'] <= 0 or m['fcf_quote'] <= 0 or m['debt_quote'] < 0:
        raise ValueError('DCF requires positive shares, market cap, FCF and nonnegative debt')
    if m['debt_quote'] > 0 and m['interest_expense_quote'] is None:
        raise ValueError('Interest expense missing for indebted company')
    w = load_module(auto_dcf, 'wacc')
    d = load_module(auto_dcf, 'dcf')
    ke = w.cost_of_equity(risk_free, m['beta'], market_return)
    kd = w.cost_of_debt(m['interest_expense_quote'] or 0, m['debt_quote'])
    wacc = w.calculate_wacc(m['market_cap'], m['debt_quote'], ke, kd, tax_rate)
    if not wacc > terminal_growth or wacc <= 0:
        raise ValueError('WACC must be positive and exceed terminal growth')
    intrinsic = d.calculate_dcf(m['fcf_quote'], growth_rate, wacc, terminal_growth,
                                 years, m['net_debt_quote'], m['shares_outstanding'])
    return {'intrinsic_value': intrinsic, 'currency': m['quote_currency'], 'wacc': wacc,
            'price': m['price'], 'upside': intrinsic / m['price'] - 1 if m['price'] and m['price'] > 0 else None,
            'period_end': m['period_end'], 'flow_basis': m['flow_basis'],
            'source': snapshot.get('source'), 'observed_at': snapshot.get('observed_at'),
            'growth_rate': growth_rate,
            'terminal_growth': terminal_growth, 'years': years,
            'caveat': 'Provider FCF is a proxy, not a reconstructed unlevered FCFF; verify ADR units and model assumptions.'}
