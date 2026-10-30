# Data platform and configuration

Findata has a single `findata` package and `python -m findata` command. Screeners,
reports and DCF calculations read the new JSON/Parquet lake. No separate financial
SQLite database or older command tree is required.

## Public configuration and private secrets

`config/settings.toml` is the central public configuration:

| Section | Controls |
| --- | --- |
| `storage` | Data lake location |
| `providers` | Universe, statements, prices, profiles and earnings-calendar sources |
| `providers.key_env` | Environment-variable names for OpenBB credentials |
| `collection` | Datasets, earliest price date, attempts, statement count and worker limit |
| `screens` | Named screening rules and optional inheritance |
| `reports` | Screens to include, pick counts, refresh/discovery budgets, freshness limits, times and timezone |
| `valuation` | DCF growth, terminal growth, years, risk-free/market returns and tax rate |
| `insiders` | Cluster window, distinct-insider count, trade value, price move and currency |
| `cloud` | Remote state key, delivery receipts, storage region and SMTP connection |

Use `--config /path/to/settings.toml` **before** the subcommand to select a different
configuration. CLI overrides, such as `--start` and `--financial-source`, take priority
over the corresponding public setting. `FINDATA_CONFIG` is another optional override.
Relative storage paths are resolved against the project root.

Copy `.env.example` to `.env` and fill values locally. The local file is ignored by Git
and has owner-only permissions when created by this project setup. Existing process
and CI environment variables take priority over `.env`. Do not commit or paste the
populated file, tokens, passwords or storage credentials into chat.

Important variables:

- `REPORT_TO`: destination address or comma-separated addresses.
- `SMTP_USERNAME`, `SMTP_PASSWORD`: email sender and SMTP app password.
- `FMP_API_KEY`, `INTRINIO_API_KEY`, `ALPHA_VANTAGE_API_KEY`: optional OpenBB keys.
- `SEC_USER_AGENT`: application name and real contact email for direct SEC requests.
- `FINDATA_S3_BUCKET`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`: private cloud state.
- `AWS_DEFAULT_REGION`, `S3_ENDPOINT_URL`: optional storage routing.

OpenBB credentials are set in memory for the selected provider; they are not written
into public settings or provider archives. Empty keys are allowed for public sources.
Changing a source does not grant access to a paid provider or silently fall back to a
free source. Price and profile adapters currently support yfinance only; statement
and calendar sources can be selected from the supported OpenBB providers.

## Configuring screeners

A rule names a report metric, comparison and numeric threshold. Example:

```toml
[screens.value_pe]
label = "Value with P/E ceiling"
extends = "value"
rules = [{metric = "price_to_earnings", op = "<", threshold = 20.0}]
```

Change `20.0` to adjust the ceiling. Use `reports.rank_by` and
`reports.rank_descending` to change the ranking order. Add `value_pe` to `reports.screens` to include it
in the email. Supported comparisons: `<`, `<=`, `>`, `>=`, `=` (or `lt`, `le`, `gt`,
`ge`, `eq`). All rules must pass. Missing values do not pass. Growth/margin values use
decimal fractions: `0.09` means 9%.

| Default screen | Conditions |
| --- | --- |
| `value` | P/S < 2; long-term debt/equity < 0.5; positive net margin; P/B < 5 |
| `value_pe` | Value rules plus P/E < 20; optional in reports |
| `deep_value` | P/S < 3; P/B < 1; zero reported total debt |
| `buffett_user` | Cash >= debt; liabilities/equity > 0.8; zero reported preferred stock; retained earnings increase; treasury stock and repurchases > 0 |
| `multibagger` | Positive FCF yield and book/market; ranks by FCF yield then book/market |

The liabilities/equity **greater than 0.8** rule follows the original request. Change
its operator to `<` for a leverage ceiling. These are transparent research hypotheses,
not validated investment strategies. The reported ratios also include ROE, gross/EBIT
margins, a simple ROC proxy, retained earnings changes and cash less debt.

P/E uses market capitalization divided by annual/TTM net income available to common
shareholders when reported, otherwise reported net income. Nonpositive earnings make
P/E unavailable rather than looking inexpensive. A trailing earnings multiple is not
a forward analyst-estimate multiple. Missing preferred stock is not assumed zero.
A treasury-stock balance alone does not prove ongoing share repurchases.

## Build commands

```sh
.venv/bin/python -m findata build --symbols AAPL MSFT TSM ZIM --start 2000-01-01
.venv/bin/python -m findata build
.venv/bin/python -m findata backfill
.venv/bin/python -m findata status

# Override datasets or sources for specific work.
.venv/bin/python -m findata backfill --datasets prices --symbols AAPL --start 1980-01-01
.venv/bin/python -m findata backfill --datasets financials --financial-source yfinance --symbols TSM
.venv/bin/python -m findata backfill --datasets profiles --symbols AAPL MSFT
```

`build` refreshes the configured universe, then collects the selected datasets.
`backfill` uses the stored universe and resumes successful requests. `--refresh` forces
new observations. Requests are checkpointed per symbol, provider and options; failures
are bounded and recorded. Partial annual/quarterly coverage is preserved and returns a
nonzero status. For example, a foreign issuer can have annual SEC statements without
quarterly SEC filing dates. Its annual data is kept.

The default Nasdaq directory covers current US-listed non-ETF securities and excludes
test issues. Some preferred shares, warrants and units remain in that directory. It is
not a complete historic registry of every delisted or OTC stock. FinanceDatabase and
the SEC directory are optional universe sources. Each source's observations remain
separate; the stored universe does not silently erase previously observed symbols.

The earliest requested price date is 1900 by default: this asks for all available
history, not nonexistent pre-IPO data. Statement collection requests up to the configured
period limit; actual history depends on the provider. Price start/end dates do not
truncate financial statements.

## Storage

- `data/lake/raw/`: immutable gzip JSON records returned by the adapter.
- `data/lake/normalized/`: typed, long-format Parquet with Zstandard compression.
- `data/lake/manifest.sqlite3`: a small internal file/job index, not financial records.
- `data/lake/reports/`: dated report artifacts and confirmed delivery state.

Direct SEC JSON contains companyfacts; OpenBB JSON contains the normalized models
returned by OpenBB, not original filing XML. Facts retain period, currency, source,
observation timestamp, unit and filing metadata where available. Company profiles
retain names, sector, industry, business descriptions and source links. Price records
retain provider OHLC, separate adjusted close, volume, dividends and split ratios.

New observations preserve revisions. Only files committed to the manifest are queried;
a crash can leave unreferenced files, which are ignored. Atomic writes protect individual
files. Back up the manifest with the lake. Run one writer for a dataset/source at a time.
DuckDB handles large exports with bounded working memory and disk spill; in-process
pandas reads should be scoped to a company for large price datasets.

## Screen inputs and coverage

The screen adapter uses one financial source per company: the most recently collected
source, with its older periods preserved. It joins current company/market metadata from
stored profiles. It maps supported Yahoo/OpenBB fields into common screen inputs, and
shows the selected source. It does not silently combine different financial providers.

Annual flows are used by default. When only quarterly data exists, four consecutive
complete quarters form TTM flows. Balance-sheet stocks are never summed. Native SEC
companyfacts retain their full taxonomies, units and annual/quarterly/YTD/instantaneous
contexts, but arbitrary native taxonomy concepts are not yet harmonized for the screens;
use the standardized OpenBB or Yahoo statement adapters for screening.

Foreign reporting currencies are retained. Currency-dependent P/E, P/S, P/B, FCF yield
and DCF inputs stay unavailable until currencies align or you provide an explicit
`--fx-rates` JSON mapping from symbol to quote units per reporting currency unit.
Verify rate dates, ADR ratios, share counts and quote subunits before valuation.

Yahoo OHLC are provider split-adjusted, not necessarily original tape prices. Adjusted
close remains separate and must not be confused with close. Session dates retain the
exchange calendar date. Complete delisted coverage and point-in-time backtesting need
additional source/filing work. Collection time is not automatically publication time.

## Earnings, screening and reports

```sh
.venv/bin/python -m findata earnings
.venv/bin/python -m findata earnings --start 2025-01-01 --end 2025-12-31
.venv/bin/python -m findata earnings-changes
.venv/bin/python -m findata screen --preset value_pe
.venv/bin/python -m findata dcf --symbols AAPL MSFT
.venv/bin/python -m findata report --refresh
.venv/bin/python -m findata export financials --output data/reports/financials.parquet
.venv/bin/python -m findata export prices --symbol AAPL --output data/reports/aapl.parquet
```

The default earnings-calendar feed is OpenBB/Nasdaq. Estimates and actual EPS/revenue
are separate fields, and unknown confirmation status remains unknown. Historical
coverage differs by provider. A stable fiscal-period/event key permits date-change
tracking; without one, rescheduling cannot be linked reliably. Calendar removal is not
assumed cancellation. Calendar EPS may use a different basis from statement EPS.

Reports contain the configured top picks, qualifying values, business/product summaries,
next known earnings, freshness gaps and changes since the last confirmed delivery.
They exclude stale statements and market data from current picks. `max_refresh` bounds
revalidation; `discovery_per_run` reserves part of that budget for unseen universe
symbols. Run the full backfill separately: the digest is not a fresh full-universe scan.
Company summaries are vendor descriptions, not audited product revenue breakdowns.
Insider-cluster detection accepts normalized filing CSVs through `insiders`; automatic
filing ingestion must be completed before those signals can be included in reports.

## DCF

`findata/valuation.py` reads the same lake-backed screen inputs and uses the bundled
DCF/WACC calculations under `findata/_vendor/auto_dcf/`. No external project is needed.
The copied source files and FCF model spreadsheet have a checksum manifest. Forecast
assumptions come from `[valuation]` and can also be overridden on the command line.

Missing required debt, cash, shares, beta or interest data is reported as skipped.
WACC must exceed terminal growth. Provider FCF is a proxy rather than a reconstruction
of unlevered FCFF; review the model assumptions before treating estimates as valuations.

## Cloud delivery while the computer is off

The prepared GitHub Actions workflow runs on hosted Linux, stores private persistent
state in S3-compatible storage and sends through SMTP. It does not need the desktop
app, an open browser or a Gmail plugin connection. **It is not deployed or active yet.**

The default schedule is 07:30 and 20:00 `America/New_York`, including weekends and DST.
After changing report times/timezone in the settings file, synchronize and publish the
workflow:

```sh
.venv/bin/python -m findata sync-schedule
```

GitHub can delay scheduled starts, and report generation/SMTP acceptance take time;
these are scheduled run times, not an exact-minute inbox delivery guarantee.

Configure these repository secrets before activation:

| Secret | Purpose |
| --- | --- |
| `FINDATA_REPORT_TO` | Report recipients |
| `FINDATA_SMTP_USERNAME` | Sending account |
| `FINDATA_SMTP_PASSWORD` | SMTP app password |
| `FINDATA_S3_BUCKET` | Private state bucket |
| `FINDATA_AWS_ACCESS_KEY_ID` | Storage identity |
| `FINDATA_AWS_SECRET_ACCESS_KEY` | Storage credential |

Optional repository variables: `FINDATA_AWS_REGION`, `FINDATA_S3_ENDPOINT_URL`.
Use private encrypted storage and bucket versioning. The storage identity needs access
to Findata's state and receipts, not permission to create buckets or change policies.
Conditional object creation must be supported for duplicate protection. Gmail app
passwords require 2-Step Verification and are not available on every account. Put the
app password directly in GitHub Secrets; do not use the ordinary Google password.

After building fresh data, upload the initial lake with storage credentials set securely
in the environment:

```sh
.venv/bin/python -m findata.cloud --seed --data-dir data
```

Publish the reviewed workflow to the default branch, run a manual `dry_run=true`
preview, then test a real delivery. The archive contains only the new lake. It does not
include `.env`. SQLite index backups are consistent. Delivery receipts prevent duplicate
editions; an ambiguous pending send stops automatic retries until sent-mail/provider
logs are checked. SMTP acceptance does not guarantee final inbox placement.

References: [OpenBB earnings](https://docs.openbb.co/odp/v4/python/reference/equity/calendar/earnings),
[SEC APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces),
[GitHub schedules](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#onschedule),
[Google app passwords](https://support.google.com/accounts/answer/185833).
