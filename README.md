# Findata

A configurable US-equity research pipeline for historical financial statements,
reported earnings, daily prices, company profiles, screeners, DCF estimates, and
morning/evening email reports.

Financial data is stored as compressed JSON observations and typed Parquet tables.
There is one application entry point: `python -m findata`.

## Setup

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[openbb,universe,cloud]'
cp .env.example .env
```

Edit **[config/settings.toml](config/settings.toml)** for provider choices, collection
settings, screener ratios, DCF assumptions, report limits and times. Edit **`.env`**
for recipient addresses, API keys and cloud/email credentials. `.env` is ignored by
Git; **[.env.example](.env.example)** is the committed template. Do not overwrite a
populated `.env` when repeating setup.

## Build the databases

```sh
# Start with a small provider/coverage check.
.venv/bin/python -m findata build --symbols AAPL MSFT TSM ZIM --start 2000-01-01

# Build the full configured US universe and all configured datasets.
.venv/bin/python -m findata build

# Resume collection without downloading the universe again.
.venv/bin/python -m findata backfill
.venv/bin/python -m findata status

# Collect historical or upcoming earnings events separately.
.venv/bin/python -m findata earnings --start 2025-01-01 --end 2025-12-31
```

Collection is resumable. Provider gaps are recorded as partial/failed jobs, and
non-USD reporters are retained. Historical depth and delisted-stock coverage depend
on the source; a complete stock-universe backtest needs additional coverage work.

## Screen and report

```sh
.venv/bin/python -m findata screen --preset value_pe
.venv/bin/python -m findata dcf --symbols AAPL MSFT
.venv/bin/python -m findata report --refresh
.venv/bin/python -m findata export financials --output data/reports/financials.parquet
.venv/bin/python -m findata export prices --symbol AAPL --output data/reports/aapl.parquet
.venv/bin/python -m findata export profiles --output data/reports/profiles.parquet
.venv/bin/python -m unittest discover -s tests -v
```

For example, the optional `value_pe` screen inherits the value rules and adds a
P/E ceiling. Change its `threshold = 20.0` in the settings file to adjust the ceiling,
or add/remove rules and include that screen in `reports.screens`. No code change is
needed. Missing data never silently becomes zero or passes a rule.

The [data and deployment guide](docs/data-platform.md) covers schemas, sources,
configuration, screen definitions, currency handling and cloud email setup.
Cloud email delivery is prepared but is **not deployed or active** until the required
accounts/secrets, initial data upload and workflow publication are completed.
