"""Screener digests with explicit freshness, source descriptions and delivery state."""
from datetime import datetime, timedelta, timezone
from email import policy
from email.message import EmailMessage
from email.utils import format_datetime
from html import escape
import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import pandas as pd

from .screening import presets, metrics, screen
from .settings import DEFAULT_SETTINGS, report_settings
from .providers import profile_row as profile
from .research import load_snapshots
from .store import atomic_write, now


def data_dates(snapshot):
    """Keep market time separate from the time we collected the provider response."""
    stamp = snapshot.get('info', {}).get('regularMarketTime')
    try:
        quote_at = datetime.fromtimestamp(float(stamp), timezone.utc).isoformat() if stamp else None
    except (ValueError, TypeError, OverflowError, OSError):
        quote_at = None
    return {'quote_at': quote_at, 'market_collected_at': snapshot.get('profile_observed_at') or snapshot.get('observed_at'),
            'financials_collected_at': snapshot.get('observed_at')}

def delivery_status(lake, delivery_id):
    with lake.connect() as db:
        db.execute('''CREATE TABLE IF NOT EXISTS report_deliveries (
            delivery_id TEXT PRIMARY KEY, gmail_message_id TEXT, delivered_at TEXT, recipient TEXT)''')
        row = db.execute('SELECT gmail_message_id FROM report_deliveries WHERE delivery_id=?', (delivery_id,)).fetchone()
    return row[0] if row else None


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = DEFAULT_SETTINGS


def candidate_symbols(snapshots, config):
    # Round-robin through independent methodologies; no one screen consumes the whole budget.
    pools = []
    for preset in config['screens']:
        frame = screen(snapshots, preset, rules=config.get('rules', {}).get(preset))
        pools.append(frame.loc[frame.passed, 'symbol'].head(config['refresh_per_screen']).tolist())
    result = []
    for index in range(max([len(pool) for pool in pools], default=0)):
        for pool in pools:
            if index < len(pool) and pool[index] not in result:
                result.append(pool[index])
    return result[:config['max_refresh']]


def refresh_candidates(lake, snapshots, symbols, workers=2):
    from .pipeline import backfill
    # Reuse configured providers, preserving OpenBB financials instead of replacing them with Yahoo.
    result = backfill(lake, symbols, datasets=['financials', 'profiles'], refresh=True)
    failures = {}
    for dataset, summary in result.items():
        for symbol, error in {**summary['failed'], **summary['partial']}.items():
            failures.setdefault(symbol, {})[dataset] = error
    snapshots.clear()
    snapshots.update(load_snapshots(lake))
    return failures


def freshness(snapshot, row, generated_at, config):
    reasons = []
    if metrics(snapshot).get('market_cap') is None:
        reasons.append('company market metadata unavailable')
    stamp = snapshot.get('info', {}).get('regularMarketTime')
    try:
        quote_date = datetime.fromtimestamp(float(stamp), timezone.utc) if stamp else datetime.fromisoformat(snapshot.get('profile_observed_at') or snapshot['observed_at'])
        if quote_date.tzinfo is None:
            quote_date = quote_date.replace(tzinfo=timezone.utc)
        if generated_at - quote_date > timedelta(days=config['max_quote_age_days']):
            reasons.append('quote/metadata stale')
        if quote_date - generated_at > timedelta(days=1):
            reasons.append('quote timestamp in the future')
    except (ValueError, TypeError, KeyError, OverflowError):
        reasons.append('quote timestamp unavailable')
    try:
        period = row.get('cash_period_end') if row.get('screen') == 'under_cash' else row['period_end']
        end = datetime.fromisoformat(period).replace(tzinfo=timezone.utc)
        if generated_at - end > timedelta(days=config['max_statement_age_days']):
            reasons.append('financial statements stale')
        if end > generated_at:
            reasons.append('financial period in the future')
    except (TypeError, ValueError):
        reasons.append('financial period unavailable')
    return reasons


def shortlist(snapshots, config, generated_at):
    picks, summaries = [], []
    for preset in config['screens']:
        frame = screen(snapshots, preset, rules=config.get('rules', {}).get(preset))
        passed = frame.loc[frame.passed].copy()
        eligible = []
        for row in passed.to_dict('records'):
            reasons = freshness(snapshots[row['symbol']], row, generated_at, config)
            row.update(data_dates(snapshots[row['symbol']]), freshness_warnings='; '.join(reasons))
            if not reasons or config.get('include_stale', False):
                eligible.append(row)
        stale = sum(bool(freshness(snapshots[row['symbol']], row, generated_at, config))
                    for row in passed.to_dict('records'))
        summaries.append({'screen': preset, 'evaluated': len(frame), 'numeric_matches': len(passed),
                          'fresh_matches': len(passed) - stale, 'stale_matches': stale})
        for row in eligible[:config['top_per_screen']]:
            row.update(screen=preset)
            picks.append(row)
    return picks, summaries


def number(value, percent=False):
    if value is None or pd.isna(value):
        return 'unavailable'
    return f'{float(value):.1%}' if percent else f'{float(value):,.2f}'


def compact_description(text, limit):
    text = ' '.join((text or '').split())
    if not text:
        return 'Business description unavailable; inspect the company filing before classifying its business.'
    if len(text) <= limit:
        return text
    cutoff = text[:limit].rsplit(' ', 1)[0]
    sentence = cutoff.rfind('. ')
    return cutoff[:sentence + 1] if sentence > limit // 2 else cutoff + '…'


def safe_url(value):
    return value if isinstance(value, str) and urlparse(value).scheme in ('https', 'http') else None


def render(picks, summaries, snapshots, earnings, config, generated_at, failures=None, previous=None):
    local = generated_at.astimezone(ZoneInfo(config['timezone']))
    subject = f'Findata Screener — {local:%Y-%m-%d %H:%M:%S %Z}'
    previous_keys = set(previous or [])
    current_keys = {f'{r["screen"]}:{r["symbol"]}' for r in picks}
    rank_text = ', then '.join(name.replace('_', ' ') for name in config.get('rank_by', ['fcf_yield', 'book_to_market']))
    periods = sorted({str(metrics(s).get('period_end')) for s in snapshots.values() if metrics(s).get('period_end')})
    period_text = f'{periods[0]} through {periods[-1]}' if periods else 'unavailable'
    collected = sorted({str(s['observed_at']) for s in snapshots.values() if s.get('observed_at')})
    collected_text = f'{collected[0]} through {collected[-1]}' if collected else 'unavailable'
    sections = ['<h1 style="margin-bottom:4px">Findata Screener</h1>',
                f'<p><b>Report generated:</b> {escape(local.isoformat())}</p>',
                f'<p><b>Stored statement periods:</b> {escape(period_text)}<br>'
                f'<b>Financial data collected:</b> {escape(collected_text)}</p>',
                '<p>Company data has different dates. Report generation does not update the database.</p>',
                f'<p>Matches from your configured research screens. Ranking fields: {escape(rank_text)}. '
                'These are screening candidates for further research.</p>',
                f'<p><b>{len(set(r["symbol"] for r in picks))} companies</b> across {len(picks)} screen placements. '
                f'{len(current_keys - previous_keys)} new placements since the last successfully emailed report.</p>']
    plaintext = [subject, 'Report generated: ' + local.isoformat(),
                 'Stored statement periods: ' + period_text, 'Financial data collected: ' + collected_text,
                 f'Ranking fields: {rank_text}. Research candidates.']
    for summary in summaries:
        preset = summary['screen']
        selected = [r for r in picks if r['screen'] == preset]
        sections.append(f'<h2>{escape(config.get("labels", {}).get(preset, preset.replace("_", " ").title()))}</h2><p>'
                        f'{summary["fresh_matches"]} fresh matches; {summary["stale_matches"]} matches with freshness warnings '
                        f'({"included and labeled" if config.get("include_stale") else "excluded"}); '
                        f'{summary["evaluated"]} companies evaluated.</p>')
        plaintext.append(f'\n{preset}: {summary["fresh_matches"]} fresh matches; {summary["stale_matches"]} matches with freshness warnings.')
        if not selected:
            sections.append('<p>No matches meet the rules and configured freshness policy in the stored data. See screening.parquet for missing values and failed rules.</p>')
        for row in selected:
            symbol = row['symbol']
            snapshot = snapshots[symbol]
            company = profile(symbol, snapshot.get('info', {}))
            descriptor = compact_description(company['description'], config['profile_max_characters'])
            earned = earnings.loc[earnings.symbol.eq(symbol)] if not earnings.empty else earnings
            upcoming = earned.loc[earned.report_date.ge(local.date().isoformat())].sort_values('report_date') if not earned.empty else earned
            event = upcoming.iloc[0].to_dict() if len(upcoming) else None
            event_text = (f'{event["report_date"]}; {event.get("release_time") or "time unknown"}; '
                          f'status {event.get("date_status") or "unknown"}') if event else 'Not available in the stored calendar'
            values = f'P/C {number(row["price_to_cash"])} · FCF yield {number(row["fcf_yield"], True)} · P/E {number(row["price_to_earnings"])} · P/S {number(row["price_to_sales"])} · P/B {number(row["price_to_book"])}'
            symbols = {'gt': '>', 'ge': '≥', 'lt': '<', 'le': '≤', 'eq': '='}
            why = '; '.join(f'{field.replace("_", " ")} {number(row.get(field))} {symbols[op]} {threshold:g}'
                            for field, op, threshold in config.get('rules', {}).get(preset, presets().get(preset, [])))
            caution = ''
            if row['fcf_yield'] is not None and pd.notna(row['fcf_yield']) and row['fcf_yield'] > 1:
                caution = 'FCF exceeds market capitalization; check one-off cash flows and share units.'
            if company['sector'] == 'Financial Services':
                caution += ' Financial-company cash flow and leverage require industry-specific interpretation.'
            new = ' · NEW' if f'{preset}:{symbol}' not in previous_keys else ''
            website = safe_url(company['website'])
            link = f' · <a href="{escape(website, quote=True)}">Company website</a>' if website else ''
            sections += [f'<h3>{escape(symbol)} — {escape(company["name"])}{new}</h3>',
                         f'<p style="color:#8a4b08"><b>Freshness:</b> {escape(row.get("freshness_warnings") or "Within configured age limits")}</p>',
                         f'<p>{escape(str(company["sector"] or "Sector unknown"))} / {escape(str(company["industry"] or "Industry unknown"))}</p>',
                         f'<p><b>{escape(values)}</b><br>Price {escape(str(row["quote_currency"] or ""))} {number(row["price"])} · Market cap {escape(str(row["quote_currency"] or "currency unknown"))} {number(row["market_cap"])}</p>',
                         f'<p><b>Why it qualifies:</b> {escape(why)}</p>',
                         f'<p><b>Latest reported cash and cash equivalents:</b> '
                         f'{escape(str(row["reporting_currency"] or "currency unknown"))} {number(row["latest_cash"])} · '
                         f'Balance date {escape(str(row["cash_period_end"] or "unavailable"))}. '
                         'Price/cash compares market capitalization with this cash balance; debt is not deducted.</p>',
                         f'<p><b>Financial details ({escape(str(row["reporting_currency"]))}):</b> '
                         f'Revenue {number(row["revenue"])} · Net income {number(row["net_income"])} · '
                         f'Assets {number(row["total_assets"])} · Liabilities {number(row["total_liabilities"])} · '
                         f'Equity {number(row["total_equity"])} · Cash {number(row["cash"])} · Debt {number(row["total_debt"])} · '
                         f'Free cash flow {number(row["free_cash_flow"])}</p>',
                         f'<p>ROE {number(row["roe"], True)} · ROA {number(row["roa"], True)} · '
                         f'Net margin {number(row["net_margin"], True)} · Current ratio {number(row["current_ratio"])} · '
                         f'Debt/equity {number(row["debt_to_equity"])}</p>',
                         f'<p><b>Products and business overview:</b> {escape(descriptor)}</p>',
                         f'<p><a href="{escape(company["source_url"], quote=True)}">Business description source</a>{link}</p>',
                         f'<p><b>Next earnings:</b> {escape(event_text)}</p>',
                         f'<p style="color:#8a4b08">{escape(caution)}</p>' if caution else '',
                         f'<p style="color:#586578;font-size:12px">Statement period: {escape(str(row["period_end"]))}; '
                         f'basis: {escape(str(row["flow_basis"]))}; collected: {escape(str(row["observed_at"]))}; '
                         f'statement source: {escape(str(row["source"]))}; '
                         f'quote time: {escape(str(row.get("quote_at") or "unavailable"))}; '
                         f'market metadata collected: {escape(str(row.get("market_collected_at") or "unavailable"))}; '
                         f'reporting currency: {escape(str(row["reporting_currency"]))}.</p>']
            plaintext += [f'\n{symbol} — {company["name"]}{new}', values, 'Why: ' + why,
                          'Business: ' + descriptor, company['source_url'], 'Next earnings: ' + event_text,
                          f'Statement period: {row["period_end"]}; collected: {row["observed_at"]}']
            plaintext += [f'Statement source: {row["source"]}; quote time: {row.get("quote_at") or "unavailable"}; '
                          f'market collected: {row.get("market_collected_at") or "unavailable"}',
                          f'Latest cash and cash equivalents: {row["latest_cash"]} {row["reporting_currency"]}; '
                          f'balance date: {row["cash_period_end"]}; debt is not deducted.',
                          'Freshness: ' + (row.get('freshness_warnings') or 'Within configured age limits')]
    removed = sorted(previous_keys - current_keys)
    if removed:
        sections.append('<h2>Left the shortlist</h2><p>' + escape(', '.join(removed)) +
                        '. A removal may reflect a changed rank, failed rule, missing data or freshness cutoff.</p>')
    sections += ['<hr><p><b>Coverage:</b> current results depend on stored coverage and a bounded refresh of stored '
                 'candidates; this is not a fresh scan of every US stock. Business descriptions are provider summaries, '
                 'not verified product revenue breakdowns. Unknown earnings dates remain unknown.</p>',
                 '<p>Rule definitions and ranking settings come from your configuration. '
                 'Insider-cluster signals are not included until filing ingestion is populated.</p>']
    if failures:
        sections.append(f'<p><b>Refresh gaps:</b> {len(failures)} candidates failed refresh: {escape(", ".join(sorted(failures)))}.</p>')
    plaintext += ['Coverage: bounded refresh of stored candidates; this is not a fresh scan of every US stock.',
                  'Business descriptions are provider summaries, not verified revenue breakdowns.',
                  'Rule definitions come from your configuration; insider-cluster signals are not yet populated.']
    body = '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Findata Screener</title></head><body style="background:#f4f6fa;color:#192638;font:15px Arial,sans-serif;line-height:1.5">'
    body += '<main style="max-width:760px;margin:auto;background:white;padding:28px">' + ''.join(sections) + '</main></body></html>'
    return subject, body, '\n'.join(plaintext), sorted(current_keys)


def build_report(lake, config_path=DEFAULT_CONFIG, *, refresh=False,
                 output=None, generated_at=None, refresh_limit=None, delivery_scope='run'):
    config = report_settings(config_path)
    if refresh_limit is not None:
        config['max_refresh'] = refresh_limit
    if config['top_per_screen'] < 1 or config['max_refresh'] < 0:
        raise ValueError('Invalid report limits')
    explicit_generated_at = generated_at is not None
    generated_at = generated_at or datetime.now(timezone.utc)
    if generated_at.tzinfo is None:
        raise ValueError('Report generation time must include a timezone')
    if delivery_scope not in ('run', 'session'):
        raise ValueError('Unknown delivery scope')
    snapshots = load_snapshots(lake)
    failures = {}
    if refresh:
        symbols = candidate_symbols(snapshots, config)
        universe = lake.current('universe')
        if not universe.empty:
            unseen = [symbol for symbol in universe.symbol.dropna().drop_duplicates() if symbol not in snapshots]
            discovery_budget = config.get('discovery_per_run', 10) if symbols else config['max_refresh']
            discovery = unseen[:min(discovery_budget, config['max_refresh'])]
            symbols = symbols[:max(0, config['max_refresh'] - len(discovery))] + discovery
        failures = refresh_candidates(lake, snapshots, symbols, workers=config.get('workers', 2))
        if not explicit_generated_at:
            generated_at = datetime.now(timezone.utc)
    picks, summaries = shortlist(snapshots, config, generated_at)
    earnings = lake.current('earnings')
    state_path = lake.root / 'reports/last_delivered.json'
    previous = json.loads(state_path.read_text()).get('keys', []) if state_path.exists() else []
    subject, html, text, keys = render(picks, summaries, snapshots, earnings, config, generated_at,
                                       failures=failures, previous=previous)
    root = Path(output) if output else lake.root / 'reports' / generated_at.astimezone(ZoneInfo(config['timezone'])).strftime('%Y-%m-%d_%H%M%S_%f')
    root.mkdir(parents=True, exist_ok=True)
    # Export all companies and rule outcomes, including missing/stale/nonmatching rows.
    rows = []
    for preset in config['screens']:
        for row in screen(snapshots, preset, rules=config.get('rules', {}).get(preset)).to_dict('records'):
            snapshot = snapshots[row['symbol']]
            row.update(data_dates(snapshot), screen=preset, generated_at=generated_at.isoformat(),
                       freshness_warnings='; '.join(freshness(snapshot, row, generated_at, config)))
            rows.append(row)
    columns = ['symbol', 'screen', 'passed', 'failed_rules', 'missing_rules', 'generated_at',
               'freshness_warnings', 'quote_at', 'market_collected_at', 'financials_collected_at']
    columns += [key for key in metrics({}) if key not in columns]
    for name, frame in [('shortlist', pd.DataFrame(picks).reindex(columns=columns)),
                        ('screening', pd.DataFrame(rows).reindex(columns=columns))]:
        if name == 'shortlist':
            frame['generated_at'] = generated_at.isoformat()
        atomic_write(root / f'{name}.csv', lambda path, frame=frame: frame.to_csv(path, index=False))
        atomic_write(root / f'{name}.parquet', lambda path, frame=frame: frame.to_parquet(path, index=False))
    message = {'to': config['recipient'], 'subject': subject, 'html': html, 'text': text,
               'generated_at': generated_at.isoformat(), 'timezone': config['timezone'],
               'mode': 'refreshed' if refresh else 'stored', 'companies_evaluated': len(snapshots),
               'data_dates': {symbol: dict(data_dates(snapshot), statement_period=metrics(snapshot)['period_end'],
                                          cash_period=metrics(snapshot)['cash_period_end'],
                                          source=snapshot['source']) for symbol, snapshot in snapshots.items()},
               'keys': keys, 'summaries': summaries, 'refresh_failures': failures,
               'delivery_id': hashlib.sha256((config['recipient'] + generated_at.isoformat()).encode()).hexdigest()}
    if delivery_scope == 'session':
        # Preserve edition-level retry protection for optional legacy cloud integrations.
        local = generated_at.astimezone(ZoneInfo(config['timezone']))
        edition = local.strftime('%Y-%m-%d') + ('AM' if local.hour < 12 else 'PM')
        message['delivery_id'] = hashlib.sha256((config['recipient'] + edition).encode()).hexdigest()
    message['already_delivered_gmail_id'] = delivery_status(lake, message['delivery_id'])
    draft = EmailMessage(policy=policy.SMTP)
    draft['Subject'] = subject
    draft['Date'] = format_datetime(generated_at)
    if config['recipient']:
        draft['To'] = config['recipient']
    draft['X-Unsent'] = '1'
    draft.set_content(text)
    draft.add_alternative(html, subtype='html')
    atomic_write(root / 'report.eml', lambda path: path.write_bytes(draft.as_bytes()))
    for filename, content in [('report.html', html), ('report.txt', text), ('message.json', json.dumps(message, indent=2))]:
        atomic_write(root / filename, lambda path, value=content: path.write_text(value, encoding='utf-8'))
    return root / 'message.json'


def mark_delivered(lake, message_path, gmail_message_id, provider='gmail'):
    if not gmail_message_id or not str(gmail_message_id).strip():
        raise ValueError('A confirmed email message ID is required')
    message = json.loads(Path(message_path).read_text())
    state = {'keys': message['keys'], 'delivery_id': message['delivery_id'],
             'gmail_message_id': gmail_message_id, 'message_id': gmail_message_id, 'provider': provider,
             'delivered_at': now(), 'to': message['to']}
    atomic_write(lake.root / 'reports/last_delivered.json', lambda path: path.write_text(json.dumps(state, indent=2)))
    with lake.connect() as db:
        db.execute('''CREATE TABLE IF NOT EXISTS report_deliveries (
            delivery_id TEXT PRIMARY KEY, gmail_message_id TEXT, delivered_at TEXT, recipient TEXT)''')
        db.execute('INSERT OR IGNORE INTO report_deliveries VALUES (?,?,?,?)',
                   (message['delivery_id'], gmail_message_id, state['delivered_at'], message['to']))
