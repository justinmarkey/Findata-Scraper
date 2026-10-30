"""Immutable compressed JSON observations + typed Parquet, indexed by SQLite.

A partition becomes visible only after both files are written and the manifest commits.
The manifest is the source of truth; uncommitted files from crashes are never queried.
"""
from contextlib import contextmanager
import base64
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3
import tempfile
from datetime import datetime, timezone
from uuid import uuid4

import pandas as pd

SCHEMAS = {
    'profiles': {
        'symbol': 'string', 'source': 'string', 'name': 'string',
        'sector': 'string', 'industry': 'string', 'description': 'string',
        'website': 'string', 'source_url': 'string',
    },
    'financials': {
        'symbol': 'string', 'company_id': 'string', 'source': 'string',
        'statement': 'string', 'frequency': 'string', 'metric': 'string',
        'period_start': 'string', 'period_end': 'string', 'filing_date': 'string',
        'accepted_at': 'string', 'accession': 'string', 'currency': 'string', 'unit': 'string',
        'value': 'Float64', 'fiscal_year': 'Int64', 'fiscal_period': 'string',
        'derivation': 'string',
    },
    'prices': {
        'symbol': 'string', 'source': 'string', 'date': 'string', 'currency': 'string',
        'open': 'Float64', 'high': 'Float64', 'low': 'Float64', 'close': 'Float64',
        'adj_close': 'Float64', 'volume': 'Int64', 'dividend': 'Float64',
        'split_ratio': 'Float64', 'adjustment': 'string',
    },
    'earnings': {
        'symbol': 'string', 'source': 'string', 'event_id': 'string',
        'report_date': 'string', 'fiscal_period_end': 'string', 'release_time': 'string',
        'currency': 'string', 'eps_actual': 'Float64', 'eps_estimate': 'Float64',
        'revenue_actual': 'Float64', 'revenue_estimate': 'Float64',
        'date_status': 'string',
    },
    'universe': {
        'symbol': 'string', 'name': 'string', 'exchange': 'string',
        'company_id': 'string', 'source': 'string', 'security_type': 'string',
        'country': 'string', 'currency': 'string',
    },
}


def now():
    return datetime.now(timezone.utc).isoformat()


def clean(value):
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if value is None or value is pd.NA or value is pd.NaT:
        return None
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    if hasattr(value, 'item'):
        return clean(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def key(value):
    return base64.urlsafe_b64encode(value.encode()).decode().rstrip('=') or '_'


def atomic_write(path, writer):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix='.partial-')
    os.close(fd)
    try:
        writer(Path(name))
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


class Lake:
    def __init__(self, root='data/lake'):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS observations (
                    id TEXT PRIMARY KEY, dataset TEXT, entity TEXT, source TEXT,
                    observed_at TEXT, raw_path TEXT, parquet_path TEXT, rows INTEGER,
                    raw_sha256 TEXT, request_json TEXT, schema_version INTEGER);
                CREATE INDEX IF NOT EXISTS observation_lookup
                    ON observations(dataset, entity, observed_at);
                CREATE TABLE IF NOT EXISTS jobs (
                    job_key TEXT PRIMARY KEY, dataset TEXT, entity TEXT, source TEXT,
                    status TEXT, attempts INTEGER, updated_at TEXT, error TEXT);
            ''')

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.root / 'manifest.sqlite3', timeout=60)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def write(self, dataset, entity, source, raw, rows, *, request=None, observed_at=None):
        schema = SCHEMAS[dataset]
        observed_at = observed_at or now()
        observation_id = uuid4().hex
        partition = Path(dataset) / f'source={key(source)}' / f'entity={key(entity)}'
        raw_path = Path('raw') / partition / f'{observation_id}.json.gz'
        parquet_path = Path('normalized') / partition / f'{observation_id}.parquet'
        encoded = json.dumps(clean(raw), allow_nan=False, separators=(',', ':')).encode()
        frame = pd.DataFrame(rows).reindex(columns=schema)
        for column, dtype in schema.items():
            if dtype in ('Float64', 'Int64'):
                frame[column] = pd.to_numeric(frame[column], errors='raise')
            frame[column] = frame[column].astype(dtype)
        frame['observed_at'] = pd.Series([observed_at] * len(frame), dtype='string')
        frame['observation_id'] = pd.Series([observation_id] * len(frame), dtype='string')
        frame['raw_path'] = pd.Series([str(raw_path)] * len(frame), dtype='string')
        atomic_write(self.root / raw_path, lambda path: path.write_bytes(gzip.compress(encoded)))
        atomic_write(self.root / parquet_path,
                     lambda path: frame.to_parquet(path, engine='pyarrow', compression='zstd', index=False))
        with self.connect() as db:
            db.execute('INSERT INTO observations VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                       (observation_id, dataset, entity, source, observed_at,
                        str(raw_path), str(parquet_path), len(frame), hashlib.sha256(encoded).hexdigest(),
                        json.dumps(clean(request or {})), 1))
        return observation_id

    def read(self, dataset, entity=None, source=None, *, latest=False, as_of=None):
        filters, params = ['dataset=?'], [dataset]
        for column, value in [('entity', entity), ('source', source), ('observed_at', as_of)]:
            if value is not None:
                filters.append(column + ('<=?' if column == 'observed_at' else '=?'))
                params.append(value)
        sql = 'SELECT parquet_path FROM observations WHERE ' + ' AND '.join(filters)
        sql += ' ORDER BY observed_at, rowid'
        with self.connect() as db:
            paths = [row[0] for row in db.execute(sql, params)]
        if latest and paths:
            if entity is None or source is None:
                raise ValueError('latest=True requires entity and source; use current() for merged history')
            paths = paths[-1:]
        if not paths:
            return pd.DataFrame({column: pd.Series(dtype=dtype) for column, dtype in SCHEMAS[dataset].items()})
        return pd.concat([pd.read_parquet(self.root / path) for path in paths], ignore_index=True)

    def current(self, dataset, entity=None, source=None, as_of=None):
        """Latest observation per natural key, preserving older periods outside refresh windows."""
        frame = self.read(dataset, entity, source, as_of=as_of)
        if frame.empty:
            return frame
        keys = {
            'financials': ['symbol', 'source', 'statement', 'frequency', 'metric', 'unit', 'period_start', 'period_end', 'accession'],
            'prices': ['symbol', 'source', 'date'],
            'earnings': ['symbol', 'source', 'event_id'],
            'universe': ['symbol', 'source'],
            'profiles': ['symbol', 'source'],
        }[dataset]
        return frame.drop_duplicates(keys, keep='last').reset_index(drop=True)

    def job(self, dataset, entity, source, request, status=None, error=''):
        token = hashlib.sha256(json.dumps([dataset, entity, source, request], sort_keys=True).encode()).hexdigest()
        with self.connect() as db:
            if status:
                db.execute('''INSERT INTO jobs VALUES (?,?,?,?,?,1,?,?)
                    ON CONFLICT(job_key) DO UPDATE SET status=excluded.status,
                    attempts=jobs.attempts + CASE WHEN excluded.status='running' THEN 1 ELSE 0 END,
                    updated_at=excluded.updated_at, error=excluded.error''',
                           (token, dataset, entity, source, status, now(), error))
            row = db.execute('SELECT status FROM jobs WHERE job_key=?', (token,)).fetchone()
        return row[0] if row else None

    def status(self):
        with self.connect() as db:
            observations = pd.read_sql_query('''SELECT dataset, source, COUNT(*) observations,
                SUM(rows) rows, MAX(observed_at) last_observation FROM observations
                GROUP BY dataset, source''', db)
            jobs = pd.read_sql_query('SELECT dataset, status, COUNT(*) jobs FROM jobs GROUP BY dataset,status', db)
        return {'observations': observations.to_dict('records'), 'jobs': jobs.to_dict('records')}

    def export(self, dataset, output, *, symbol=None, source=None, as_of=None):
        """DuckDB scans only committed files and spills large exports instead of using pandas RAM."""
        import duckdb
        output = Path(output)
        if output.suffix not in ('.csv', '.parquet'):
            raise ValueError('Use a .csv or .parquet output filename')
        conditions, params = ['dataset=?'], [dataset]
        if source:
            conditions.append('source=?')
            params.append(source)
        if symbol and dataset in ('financials', 'prices'):
            conditions.append('entity=?')
            params.append(symbol)
        if as_of:
            conditions.append('observed_at<=?')
            params.append(as_of)
        with self.connect() as db:
            manifest = db.execute('SELECT parquet_path,rowid FROM observations WHERE ' +
                                  ' AND '.join(conditions), params).fetchall()
        if not manifest:
            empty = self.read(dataset, entity='__no_such_entity__')
            atomic_write(output, lambda path: empty.to_parquet(path, engine='pyarrow', index=False)
                         if output.suffix == '.parquet' else empty.to_csv(path, index=False))
            return 0
        keys = {
            'financials': ['symbol', 'source', 'statement', 'frequency', 'metric', 'unit', 'period_start', 'period_end', 'accession'],
            'prices': ['symbol', 'source', 'date'],
            'earnings': ['symbol', 'source', 'event_id'],
            'universe': ['symbol', 'source'],
            'profiles': ['symbol', 'source'],
        }[dataset]
        paths = [str(self.root / row[0]) for row in manifest]
        metadata = pd.DataFrame({'filename': paths, 'manifest_order': [row[1] for row in manifest]})
        connection = duckdb.connect(config={'memory_limit': '512MB',
                                           'temp_directory': str(self.root / '.query-temp')})
        try:
            connection.register('manifest_metadata', metadata)
            connection.read_parquet(paths, union_by_name=True, filename=True, hive_partitioning=False).create_view('files')
            query = '''SELECT * EXCLUDE(filename, manifest_order) FROM files
                JOIN manifest_metadata USING(filename)'''
            query_params = []
            if symbol:
                query += ' WHERE symbol=?'
                query_params.append(symbol)
            query += ' QUALIFY ROW_NUMBER() OVER (PARTITION BY ' + ','.join(keys)
            query += ' ORDER BY observed_at DESC, manifest_order DESC)=1'
            relation = connection.sql(query, params=query_params)
            count = relation.aggregate('count(*)').fetchall()[0][0]
            atomic_write(output, lambda path: relation.write_parquet(str(path), compression='zstd')
                         if output.suffix == '.parquet' else relation.write_csv(str(path), header=True))
            return count
        finally:
            connection.close()
