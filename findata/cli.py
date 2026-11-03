"""One command-line entry point: python -m findata."""
import argparse
from datetime import date, timedelta
import json
import os
from pathlib import Path

from .settings import ROOT, load_settings, screen_rules
from .store import Lake
from . import pipeline


def main(argv=None):
    initial = argparse.ArgumentParser(add_help=False)
    initial.add_argument('--config', type=Path, help='Public TOML settings file; defaults to config/settings.toml')
    known, _ = initial.parse_known_args(argv)
    if known.config:
        os.environ['FINDATA_CONFIG'] = str(known.config.resolve())
    settings = load_settings(known.config)
    sources, collection, reports = settings['providers'], settings['collection'], settings['reports']
    p = argparse.ArgumentParser(parents=[initial], description='Findata: historical financials, prices, screeners and reports')
    p.add_argument('--root', type=Path, default=ROOT / settings['storage']['root'])
    sub = p.add_subparsers(dest='command', required=True)
    universe = sub.add_parser('universe', help='Snapshot current US exchange listings')
    universe.add_argument('--source', choices=['nasdaq', 'sec', 'financedatabase'], default=sources['universe'])
    for name in ['build', 'backfill']:
        b = sub.add_parser(name, help='Build/refresh the universe and datasets' if name == 'build' else 'Resume historical collection')
        b.add_argument('--symbols', nargs='+')
        b.add_argument('--symbols-csv', type=Path)
        b.add_argument('--datasets', nargs='+', choices=['financials', 'prices', 'profiles'], default=collection['datasets'])
        b.add_argument('--start', default=collection['start_date'])
        b.add_argument('--end', default=date.today().isoformat())
        b.add_argument('--financial-source', default=sources['financials'])
        b.add_argument('--price-source', default=sources['prices'])
        b.add_argument('--cik-map', type=Path)
        b.add_argument('--attempts', type=int, default=collection['attempts'])
        b.add_argument('--refresh', action='store_true')
        b.add_argument('--statement-limit', type=int, default=collection['statement_limit'])
    earnings = sub.add_parser('earnings', help='Refresh historical/upcoming earnings events')
    earnings.add_argument('--start', default=date.today().isoformat())
    earnings.add_argument('--end', default=(date.today() + timedelta(days=30)).isoformat())
    earnings.add_argument('--source', default=sources['earnings'])
    earnings.add_argument('--attempts', type=int, default=collection['attempts'])
    sub.add_parser('status')
    report = sub.add_parser('report', help='Create local HTML, email draft, CSV and Parquet from stored data')
    report.add_argument('--refresh', action='store_true', help='Opt in to bounded network collection using configured providers')
    report.add_argument('--refresh-limit', type=int)
    report.add_argument('--output', type=Path)
    for name in ['screen', 'dcf']:
        command = sub.add_parser(name)
        command.add_argument('--symbols', nargs='+')
        command.add_argument('--source', help='Use a single financial provider')
        command.add_argument('--fx-rates', type=Path, help='JSON symbol: quote units per reporting currency unit')
        command.add_argument('--output', type=Path, default=ROOT / f'data/reports/{name}.csv')
        if name == 'screen':
            command.add_argument('--preset', choices=settings['screens'], default=reports['screens'][0])
        else:
            for key, value in settings['valuation'].items():
                command.add_argument('--' + key.replace('_', '-'), type=int if key == 'years' else float, default=value)
    insiders = sub.add_parser('insiders', help='Detect clusters in normalized filing data')
    insiders.add_argument('--transactions', type=Path, required=True)
    insiders.add_argument('--prices', type=Path, required=True)
    insiders.add_argument('--as-of', required=True)
    insiders.add_argument('--output', type=Path, default=ROOT / 'data/reports/insiders.csv')
    delivered = sub.add_parser('mark-delivered')
    delivered.add_argument('--message', type=Path, required=True)
    delivered.add_argument('--gmail-message-id', required=True)
    changes = sub.add_parser('earnings-changes')
    changes.add_argument('--source')
    changes.add_argument('--output', type=Path, default=ROOT / 'data/reports/earnings_changes.csv')
    export = sub.add_parser('export')
    export.add_argument('dataset', choices=['financials', 'prices', 'earnings', 'universe', 'profiles'])
    export.add_argument('--symbol')
    export.add_argument('--source')
    export.add_argument('--as-of', help='UTC ISO collection cutoff')
    export.add_argument('--output', type=Path, required=True)
    args = p.parse_args(argv)
    lake = Lake(args.root)
    if args.command == 'report':
        from .reporting import build_report
        path = build_report(lake, config_path=known.config, refresh=args.refresh,
                            refresh_limit=args.refresh_limit, output=args.output)
        print(json.dumps({'message': str(path.resolve()), 'html': str((path.parent / 'report.html').resolve()),
                          'email': str((path.parent / 'report.eml').resolve()),
                          'screening': str((path.parent / 'screening.parquet').resolve())}))
    elif args.command == 'mark-delivered':
        from .reporting import mark_delivered
        mark_delivered(lake, args.message, args.gmail_message_id)
        print('Delivery recorded')
    elif args.command == 'universe':
        print(json.dumps({'securities': pipeline.refresh_universe(lake, args.source)}))
    elif args.command in ['build', 'backfill']:
        if args.statement_limit < 1:
            p.error('--statement-limit must be positive')
        if args.command == 'build':
            pipeline.refresh_universe(lake, sources['universe'])
        symbols = pipeline.resolve_symbols(lake, args.symbols, args.symbols_csv)
        mapping = json.loads(args.cik_map.read_text()) if args.cik_map else {}
        if not mapping and args.financial_source == 'sec':
            frame = lake.current('universe', source='sec')
            if not frame.empty:
                mapping = dict(zip(frame.symbol, frame.company_id))
        result = pipeline.backfill(lake, symbols, datasets=args.datasets, start=args.start, end=args.end,
                                   financial_source=args.financial_source, price_source=args.price_source,
                                   cik_map=mapping, attempts=args.attempts, refresh=args.refresh,
                                   statement_limit=args.statement_limit)
        print(json.dumps(result, indent=2))
        return int(any(r['failed'] or r.get('partial') for r in result.values()))
    elif args.command == 'earnings':
        result = pipeline.track_earnings(lake, args.start, args.end, args.source, args.attempts)
        print(json.dumps(result, indent=2))
        return int(any(r['failed'] for r in result))
    elif args.command == 'status':
        print(json.dumps(lake.status(), indent=2))
    else:
        import pandas as pd
        if args.command == 'export':
            count = lake.export(args.dataset, args.output, symbol=args.symbol, source=args.source, as_of=args.as_of)
            print(f'Wrote {count} rows to {args.output}')
            return 0
        if args.command in ['screen', 'dcf']:
            from .research import load_snapshots
            snapshots = load_snapshots(lake, args.symbols, args.source)
            fx = json.loads(args.fx_rates.read_text()) if args.fx_rates else {}
            if args.command == 'screen':
                from .screening import screen
                frame = screen(snapshots, args.preset, rules=screen_rules(settings, args.preset), fx_rates=fx)
            else:
                from .valuation import value_snapshot
                rows = []
                for symbol, snapshot in snapshots.items():
                    try:
                        row = value_snapshot(snapshot, fx_rate=fx.get(symbol),
                                             **{key: getattr(args, key) for key in settings['valuation']})
                        row.update(status='ok', error='')
                    except ValueError as exc:
                        row = {'status': 'skipped', 'error': str(exc)}
                    rows.append(dict(row, symbol=symbol))
                frame = pd.DataFrame(rows, columns=None if rows else ['symbol', 'status', 'error'])
        elif args.command == 'insiders':
            from .insiders import clusters
            frame = clusters(pd.read_csv(args.transactions), pd.read_csv(args.prices),
                             as_of=args.as_of, **settings['insiders'])
        else:
            frame = pipeline.earnings_changes(lake, args.source)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        if args.output.suffix == '.parquet':
            frame.to_parquet(args.output, engine='pyarrow', compression='zstd', index=False)
        elif args.output.suffix == '.csv':
            frame.to_csv(args.output, index=False)
        else:
            p.error('Use a .csv or .parquet output filename')
        print(f'Wrote {len(frame)} rows to {args.output}')
    return 0
