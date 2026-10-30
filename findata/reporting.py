"""Screener digests with explicit freshness, source descriptions and delivery state."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from html import escape
import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import pandas as pd

from .yahoo import fetch_snapshot
from .screening import presets, metrics, screen
from .settings import DEFAULT_SETTINGS, report_settings
from .providers import snapshot_rows, profile_row as profile
from .research import load_snapshots
from .store import Lake, atomic_write, now

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
    failures = {}
    # Network work in bounded workers; all storage writes happen on the caller thread.
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(fetch_snapshot, symbol): symbol for symbol in symbols}
        for future in as_completed(futures):
            symbol = futures[future]
            try:
                payload = future.result()
                observed = now()
                lake.write('financials', symbol, 'yfinance', payload,
                           snapshot_rows(symbol, payload, 'yfinance'), observed_at=observed,
                           request={'purpose': 'digest revalidation'})
                row = profile(symbol, payload['info'])
                lake.write('profiles', symbol, 'yfinance', payload['info'], [row], observed_at=observed)
                snapshots[symbol] = dict(payload, source='yfinance', observed_at=observed)
                print(f'Revalidated {symbol}', flush=True)
            except Exception as exc:
                failures[symbol] = str(exc)
                print(f'Revalidation failed for {symbol}: {exc}', flush=True)
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
        end = datetime.fromisoformat(row['period_end']).replace(tzinfo=timezone.utc)
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
            if not freshness(snapshots[row['symbol']], row, generated_at, config):
                eligible.append(row)
        summaries.append({'screen': preset, 'evaluated': len(frame), 'numeric_matches': len(passed),
                          'fresh_matches': len(eligible), 'stale_matches': len(passed) - len(eligible)})
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
    session = 'Morning' if local.hour < 12 else 'Evening'
    subject = f'Findata {session} Screener — {local:%b %d, %Y}'
    previous_keys = set(previous or [])
    current_keys = {f'{r["screen"]}:{r["symbol"]}' for r in picks}
    rank_text = ', then '.join(name.replace('_', ' ') for name in config.get('rank_by', ['fcf_yield', 'book_to_market']))
    sections = [f'<h1 style="margin-bottom:4px">Findata {session} Screener</h1>',
                f'<p>{escape(local.strftime("%A, %B %d, %Y · %I:%M %p %Z"))}</p>',
                f'<p>Top verified matches from your configured research screens. Ranking fields: {escape(rank_text)}. '
                'These are screening candidates for further research.</p>',
                f'<p><b>{len(set(r["symbol"] for r in picks))} companies</b> across {len(picks)} screen placements. '
                f'{len(current_keys - previous_keys)} new placements since the last successfully emailed report.</p>']
    plaintext = [subject, local.isoformat(), f'Ranking fields: {rank_text}. Research candidates.']
    for summary in summaries:
        preset = summary['screen']
        selected = [r for r in picks if r['screen'] == preset]
        sections.append(f'<h2>{escape(config.get("labels", {}).get(preset, preset.replace("_", " ").title()))}</h2><p>'
                        f'{summary["fresh_matches"]} fresh matches; {summary["stale_matches"]} historical matches excluded; '
                        f'{summary["evaluated"]} companies evaluated.</p>')
        plaintext.append(f'\n{preset}: {summary["fresh_matches"]} fresh matches; {summary["stale_matches"]} stale matches excluded.')
        if not selected:
            sections.append('<p>No current verified matches in the stored data. Historical matches are not promoted as current picks.</p>')
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
            values = f'FCF yield {number(row["fcf_yield"], True)} · P/E {number(row["price_to_earnings"])} · P/S {number(row["price_to_sales"])} · P/B {number(row["price_to_book"])}'
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
                         f'<p>{escape(str(company["sector"] or "Sector unknown"))} / {escape(str(company["industry"] or "Industry unknown"))}</p>',
                         f'<p><b>{escape(values)}</b><br>Price {escape(str(row["quote_currency"] or ""))} {number(row["price"])} · Market cap {escape(str(row["quote_currency"] or "currency unknown"))} {number(row["market_cap"])}</p>',
                         f'<p><b>Why it qualifies:</b> {escape(why)}</p>',
                         f'<p><b>Products and business overview:</b> {escape(descriptor)}</p>',
                         f'<p><a href="{escape(company["source_url"], quote=True)}">Business description source</a>{link}</p>',
                         f'<p><b>Next earnings:</b> {escape(event_text)}</p>',
                         f'<p style="color:#8a4b08">{escape(caution)}</p>' if caution else '',
                         f'<p style="color:#586578;font-size:12px">Statement period: {escape(str(row["period_end"]))}; '
                         f'basis: {escape(str(row["flow_basis"]))}; collected: {escape(str(row["observed_at"]))}; '
                         f'reporting currency: {escape(str(row["reporting_currency"]))}.</p>']
            plaintext += [f'\n{symbol} — {company["name"]}{new}', values, 'Why: ' + why,
                          'Business: ' + descriptor, company['source_url'], 'Next earnings: ' + event_text,
                          f'Statement period: {row["period_end"]}; collected: {row["observed_at"]}']
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
    body = '<!doctype html><html><body style="background:#f4f6fa;color:#192638;font:15px Arial,sans-serif;line-height:1.5">'
    body += '<main style="max-width:760px;margin:auto;background:white;padding:28px">' + ''.join(sections) + '</main></body></html>'
    return subject, body, '\n'.join(plaintext), sorted(current_keys)


def build_report(lake, config_path=DEFAULT_CONFIG, *, refresh=False,
                 output=None, generated_at=None, refresh_limit=None):
    config = report_settings(config_path)
    if refresh_limit is not None:
        config['max_refresh'] = refresh_limit
    if config['top_per_screen'] < 1 or config['max_refresh'] < 0:
        raise ValueError('Invalid report limits')
    explicit_generated_at = generated_at is not None
    generated_at = generated_at or datetime.now(timezone.utc)
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
    # Persist useful company descriptions even when loaded from existing local data.
    for symbol in dict.fromkeys(r['symbol'] for r in picks):
        info = snapshots[symbol].get('info', {})
        row = profile(symbol, info)
        if lake.current('profiles', entity=symbol, source='yfinance').empty:
            lake.write('profiles', symbol, 'yfinance', info, [row],
                       observed_at=snapshots[symbol].get('observed_at') or now())
    earnings = lake.current('earnings')
    state_path = lake.root / 'reports/last_delivered.json'
    previous = json.loads(state_path.read_text()).get('keys', []) if state_path.exists() else []
    subject, html, text, keys = render(picks, summaries, snapshots, earnings, config, generated_at,
                                       failures=failures, previous=previous)
    root = Path(output) if output else lake.root / 'reports' / generated_at.astimezone(ZoneInfo(config['timezone'])).strftime('%Y-%m-%d_%H%M%S')
    root.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(picks).to_csv(root / 'shortlist.csv', index=False)
    message = {'to': config['recipient'], 'subject': subject, 'html': html, 'text': text,
               'generated_at': generated_at.isoformat(), 'timezone': config['timezone'],
               'keys': keys, 'summaries': summaries, 'refresh_failures': failures,
               'delivery_id': hashlib.sha256((config['recipient'] + generated_at.astimezone(ZoneInfo(config['timezone'])).strftime('%Y-%m-%d') + ('AM' if generated_at.astimezone(ZoneInfo(config['timezone'])).hour < 12 else 'PM')).encode()).hexdigest()}
    message['already_delivered_gmail_id'] = delivery_status(lake, message['delivery_id'])
    for filename, content in [('report.html', html), ('report.txt', text), ('message.json', json.dumps(message, indent=2))]:
        atomic_write(root / filename, lambda path, value=content: path.write_text(value))
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
