# Findata

A local US-equity research database and on-demand screener report. Collect financial
statements with OpenBB, store observations in JSON/Parquet, then run screeners against
your database. No GitHub schedule, cloud storage, or paid data key is required.

## Setup

Use Python 3.11 or newer (Python 3.13 is supported):

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[openbb]'
```

Copy `.env.example` to `.env` if you do not already have one. Set `SEC_USER_AGENT`
to your application name and real contact email for direct SEC access. `REPORT_TO`
is optional and fills in the recipient of the generated email draft. Creating and
reading reports requires no SMTP credentials. `.env` is ignored by Git.

Edit [config/settings.toml](config/settings.toml) for collection sources, screening
rules, ranking, report size and freshness policy. Defaults use OpenBB/SEC for income,
balance-sheet and cash-flow statements, OpenBB/Yahoo for historical prices, Yahoo for
rich company profiles, and OpenBB/Nasdaq for the optional earnings calendar. No paid
provider credentials are needed for these defaults.

## Build or update your database

```sh
# Start with a small coverage check.
.venv/bin/python -m findata build --symbols AAPL MSFT --start 2000-01-01

# Build the configured US universe, or resume stored collection jobs.
.venv/bin/python -m findata build
.venv/bin/python -m findata backfill
.venv/bin/python -m findata status

# Explicitly update stored statements and company/market metadata.
.venv/bin/python -m findata backfill --datasets financials profiles --refresh

# Optional earnings calendar.
.venv/bin/python -m findata earnings
```

Collection is resumable and records provider gaps. Public sources can throttle requests
or have missing statements; report generation works with the stored data without
contacting those services. A report does not automatically update your database.

## Generate a local report

```sh
.venv/bin/python -m findata report

# Use a database copied from another machine.
.venv/bin/python -m findata --root /path/to/copied/lake report

# Choose an output folder, or explicitly request a bounded provider refresh first.
.venv/bin/python -m findata report --output data/reports/my-report
.venv/bin/python -m findata report --refresh --refresh-limit 20
```

The command prints absolute output paths. Each default run creates a timestamped
folder under `data/lake/reports/` containing:

| File | Use |
| --- | --- |
| `report.html` | Open in any browser to read the report |
| `report.eml` | Email draft with plain-text and HTML versions; open in a compatible mail client |
| `report.txt` | Plain-text report |
| `shortlist.csv`, `shortlist.parquet` | Top ranked matches for each configured screen |
| `screening.csv`, `screening.parquet` | Every evaluated company/screen, metrics, failed/missing rules and freshness warnings |
| `message.json` | Report metadata, source/data dates and email content |

Reports show the run timestamp separately from statement period ends, financial-data
collection times, quote timestamps and market-metadata collection times. Historical
matches are included with warnings by default so you can inspect an older database.
Set `reports.include_stale = false` to exclude them from the shortlist. All evaluated
rows remain available in `screening.parquet`. Missing values never pass screening rules.
An empty database produces an explicitly empty report; populate or copy the lake first.

Generating a report does not send mail. You can read the HTML without an email account,
or review/send the `.eml` draft using your own mail client. There is no automatic cadence.

## Screen, analyze and export

```sh
.venv/bin/python -m findata screen --preset value_pe
.venv/bin/python -m findata screen --preset under_cash
.venv/bin/python -m findata dcf --symbols AAPL MSFT
.venv/bin/python -m findata export financials --output data/reports/financials.parquet
.venv/bin/python -m findata export prices --symbol AAPL --output data/reports/prices.parquet
.venv/bin/python -m unittest discover -s tests -v
```

Stored statements retain all numeric fields returned by the provider. Screen metrics
include P/E, P/S, P/B, FCF yield, margins, ROE, ROA, current/quick ratios, debt/equity,
debt/assets and interest coverage, plus balance-sheet and cash-flow amounts. Ratios
are calculated transparently from stored statements and market metadata, rather than
requiring a paid vendor-ratios feed. Currency-dependent ratios stay unavailable when
reporting and quote currencies do not align.

The default report also includes **Trading below cash**: market capitalization divided
by the latest reported cash and cash equivalents must be strictly below 1. The report
shows P/C, the cash balance date and available quote timestamp. This uses gross cash
before debt, excludes short-term investments, and never treats missing cash as zero.

To move between machines, copy the **entire `data/lake` directory**, including
`manifest.sqlite3`, `raw/`, and `normalized/`, after collection has stopped. Copying
only the SQLite manifest is insufficient. Install Findata on the destination machine
and point `--root` at that directory. The recipient and timezone can be configured there.

The [data and deployment guide](docs/data-platform.md) describes source coverage,
calculation details and legacy cloud utilities. The scheduled GitHub workflow has been
removed; that removal takes effect on GitHub once these changes reach the default branch.
