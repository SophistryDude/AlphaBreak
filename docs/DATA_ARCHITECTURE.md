# Data Architecture

**Last Updated**: March 15, 2026
**Database**: PostgreSQL 15 + TimescaleDB on EC2 (t3.medium)
**Total Tables**: 98 (57 application, 41 Airflow internal)

---

## Table of Contents

1. [Overview](#overview)
2. [Application Tables](#application-tables)
   - [Price & Market Data](#price--market-data)
   - [Technical Analysis & ML](#technical-analysis--ml)
   - [Options Data](#options-data)
   - [Forex](#forex)
   - [13F Institutional Holdings](#13f-institutional-holdings)
   - [Dark Pool](#dark-pool)
   - [Portfolio](#portfolio)
   - [Auth & User](#auth--user)
   - [Earnings](#earnings)
3. [Airflow Internal Tables](#airflow-internal-tables)
4. [Storage Summary](#storage-summary)
5. [Data Sources](#data-sources)
6. [Query Patterns](#query-patterns)

---

## Overview

All tables live in the `public` schema of the `trading_data` database. Tables are split between two owners:
- **`postgres`** — application tables (market data, analysis, portfolio)
- **`trading`** — Airflow metadata tables + auth/user tables

---

## Application Tables

### Price & Market Data

| Table | Owner | Size | ~Rows | Description |
|-------|-------|------|-------|-------------|
| `stock_prices` | postgres | 16 kB | — | Daily OHLCV for individual stocks |
| `stock_prices_intraday` | postgres | 24 kB | — | Intraday OHLCV (1min, 5min, 10min, 1hour) |
| `market_indices` | postgres | 24 kB | — | Daily data: S&P 500, DJI, VIX, futures, inverse ETFs |
| `market_indices_intraday` | postgres | 16 kB | — | 5min/1hr data for market ETFs |
| `market_breadth_intraday` | postgres | 8 kB | — | Advance/decline, new highs/lows by index and interval |
| `market_index_definitions` | postgres | 32 kB | 8 | Metadata for tracked indices and ETFs |
| `index_definitions` | postgres | 32 kB | 4 | Index definitions (SPY, DIA, QQQ, IWM) |
| `index_constituents` | postgres | 40 kB | 129 | Current index membership by ticker |
| `ticker_metadata` | postgres | 128 kB | 471 | Company name, sector, industry, market cap category, exchange |
| `corporate_actions` | postgres | 5.6 MB | 47,092 | Dividends, splits, spinoffs with ex-date |

**Schema notes:**
```sql
-- stock_prices_intraday
ticker          VARCHAR(10)
timestamp       TIMESTAMPTZ   -- PK with ticker
interval_type   VARCHAR(10)   -- '1min','5min','10min','1hour'
open, high, low, close  DECIMAL(12,4)
volume          BIGINT
vwap            DECIMAL(12,4)
trade_count     INTEGER

-- ticker_metadata
ticker          VARCHAR(10)   -- PK
company_name    VARCHAR(200)
sector          VARCHAR(50)   -- GICS sector
industry        VARCHAR(100)
market_cap_cat  VARCHAR(20)   -- 'mega','large','mid','small'
exchange        VARCHAR(20)   -- 'NYSE','NASDAQ'
```

---

### Technical Analysis & ML

| Table | Owner | Size | ~Rows | Description |
|-------|-------|------|-------|-------------|
| `technical_indicators` | postgres | 16 kB | — | Daily technical indicators per ticker (RSI, MACD, CCI, Stochastic, Bollinger) |
| `technical_indicators_intraday` | postgres | 8 kB | — | Intraday technical indicators |
| `engineered_features` | postgres | 24 kB | — | ML feature matrix (59 features) for model training |
| `trend_breaks` | postgres | 32 kB | — | Detected trend break events with probability scores |
| `trend_ranges` | postgres | 32 kB | — | Identified trend range periods (start, end, direction) |
| `trend_break_features` | postgres | 24 kB | — | Feature snapshot at time of each trend break |
| `trend_break_predictions` | postgres | 24 kB | — | ML model output: predicted direction + confidence |
| `indicator_accuracy` | postgres | 24 kB | — | Per-indicator accuracy tracking over time |
| `backtest_results` | postgres | 24 kB | — | Backtesting engine results by strategy/date range |
| `model_performance` | postgres | 24 kB | — | Model accuracy, precision, recall by version |
| `predictions_log` | postgres | 24 kB | — | Rolling log of all model predictions |
| `data_fetch_log` | postgres | 16 kB | — | Data pipeline run history and status |

---

### Options Data

| Table | Owner | Size | ~Rows | Description |
|-------|-------|------|-------|-------------|
| `options_data` | postgres | 16 kB | — | Options chains: strike, expiry, IV, Greeks |
| `cboe_market_options_stats` | postgres | 656 kB | 3,253 | CBOE daily market-level options statistics (put/call ratio, total volume) |
| `cboe_options_volume` | postgres | 32 kB | — | CBOE options volume by ticker |

---

### Forex

| Table | Owner | Size | ~Rows | Description |
|-------|-------|------|-------|-------------|
| `forex_pairs` | postgres | 40 kB | — | 21 currency pair definitions and metadata |
| `forex_daily_data` | postgres | 41 MB | 123,068 | Historical OHLCV from FRED + Yahoo Finance (back to 1971 for major pairs) |
| `forex_correlations` | postgres | 128 kB | 210 | Pair-to-pair correlation matrix (30d, 90d, 1yr, all-time) |
| `forex_correlation_thresholds` | postgres | 40 kB | — | Strong/Mid/Weak classification thresholds per pair |
| `forex_trend_breaks` | postgres | 18 MB | 80,833 | Notable forex movements with technical indicators |
| `forex_model_predictions` | trading | 13 MB | 80,833 | Backtest results: predicted vs actual direction |
| `forex_models` | postgres | 8 kB | — | Model configuration and version metadata |
| `forex_equity_correlations` | postgres | 32 kB | — | Cross-asset correlation: forex pairs vs equity indices |

**Currency pairs tracked (21 total):**

| Pair | Data Start | History |
|------|------------|---------|
| USD/JPY, GBP/USD, USD/CAD, USD/CHF, AUD/USD | 1971 | ~54 years |
| USD/CNY | 1981 | ~44 years |
| EUR/USD | 1999 | ~26 years |
| USD/MXN, USD/BRL, USD/INR, USD/KRW, and others | Various | 20–30 years |

---

### 13F Institutional Holdings

| Table | Owner | Size | ~Rows | Description |
|-------|-------|------|-------|-------------|
| `hedge_fund_managers` | postgres | 32 kB | 20 | 20 tracked institutions (Berkshire, Bridgewater, Renaissance, Citadel, DE Shaw, etc.) |
| `f13_filings` | postgres | 128 kB | 72 | Quarterly 13F filing metadata (CIK, period, date filed) |
| `f13_holdings` | postgres | 27 MB | 85,773 | Current holdings per filing: ticker, shares, value, cusip |
| `f13_stock_aggregates` | postgres | 5.3 MB | 20,485 | Per-stock institutional sentiment: net change, signal (STRONG_BUY → STRONG_SELL) |
| `cusip_ticker_map` | postgres | 360 kB | 2,175 | CUSIP to ticker symbol mapping |
| `f13_archive_institutions` | postgres | 248 kB | 2,222 | Historical institution records across all quarters |
| `f13_archive_stocks` | postgres | 4.2 MB | 41,242 | Historical stock universe from archive filings |
| `f13_archive_holdings` | postgres | **1,268 MB** | 8,384,814 | Full historical holdings archive — all institutions, all quarters |
| `f13_archive_aggregates` | postgres | 6.1 MB | 29,854 | Historical per-stock aggregates across archive quarters |

> **Note:** `f13_archive_holdings` is the largest table in the database at 1.27 GB with 8.4M rows, covering the full SEC EDGAR filing history for all tracked institutions.

---

### Dark Pool

| Table | Owner | Size | ~Rows | Description |
|-------|-------|------|-------|-------------|
| `darkpool_weekly_volume` | postgres | **101 MB** | 621,387 | Weekly dark pool volume by ticker: total shares, % of total volume |
| `darkpool_ticker_aggregates` | postgres | 4.0 MB | 22,940 | Aggregated dark pool metrics per ticker (rolling averages, relative volume) |

---

### Portfolio

| Table | Owner | Size | ~Rows | Description |
|-------|-------|------|-------|-------------|
| `portfolio_account` | postgres | 24 kB | — | Account balance, starting capital ($100K), allocation config |
| `portfolio_holdings` | postgres | 80 kB | 11 | Current open positions with entry price, shares, cost basis |
| `portfolio_transactions` | postgres | 64 kB | — | Trade history: buys, sells, stop-losses triggered |
| `portfolio_performance` | postgres | 56 kB | — | Daily NAV, P&L, benchmark comparison |
| `portfolio_signals` | postgres | 152 kB | 135 | Generated trade signals: ticker, direction, confidence, source model |
| `portfolio_watchlist` | postgres | 32 kB | — | Portfolio manager's tracked tickers |
| `portfolio_covered_calls` | postgres | 32 kB | — | Covered call positions: strike, expiry, premium collected |

**Portfolio configuration:**
- Starting capital: $100,000
- Long-term allocation: 65%
- Swing allocation: 35%
- Max position size: 7% ($7,000)
- Min cash reserve: 20%
- Stop-loss: 7% (stocks), 50% (options)

---

### Auth & User

| Table | Owner | Size | ~Rows | Description |
|-------|-------|------|-------|-------------|
| `users` | trading | 112 kB | — | User accounts with bcrypt-hashed passwords |
| `refresh_tokens` | trading | 88 kB | — | JWT refresh token tracking and revocation |
| `user_watchlists` | trading | 64 kB | — | Per-user watchlist persistence |

---

### Earnings

| Table | Owner | Size | ~Rows | Description |
|-------|-------|------|-------|-------------|
| `earnings_calendar` | trading | 536 kB | 2,926 | Upcoming and historical earnings dates with EPS estimates |
| `earnings_cache_meta` | trading | 24 kB | 113 | Cache metadata for earnings data freshness tracking |

---

## Airflow Internal Tables

These 41 tables are managed by Apache Airflow (LocalExecutor, running since Feb 9, 2026). Do not modify directly.

**Active DAGs (2):**
| DAG | Purpose |
|-----|---------|
| `portfolio_update_dag.py` | Daily portfolio updates at 9 AM EST: process signals, execute trades, manage positions |
| `portfolio_sync_onetime.py` | One-time portfolio state synchronization |

**Airflow metadata tables:**

| Group | Tables |
|-------|--------|
| Auth/RBAC | `ab_permission`, `ab_permission_view`, `ab_permission_view_role`, `ab_register_user`, `ab_role`, `ab_user`, `ab_user_role`, `ab_view_menu` |
| DAG management | `dag`, `dag_code`, `dag_owner_attributes`, `dag_pickle`, `dag_run`, `dag_run_note`, `dag_schedule_dataset_reference`, `dag_tag`, `dag_warning` |
| Task execution | `task_instance`, `task_instance_note`, `task_fail`, `task_map`, `task_outlet_dataset_reference`, `task_reschedule` |
| Datasets | `dataset`, `dataset_dag_run_queue`, `dataset_event`, `dagrun_dataset_event` |
| Logging | `log`, `log_template`, `import_error` |
| Other | `alembic_version`, `callback_request`, `connection`, `job`, `rendered_task_instance_fields`, `serialized_dag`, `session`, `sla_miss`, `slot_pool`, `trigger`, `variable`, `xcom` |

---

## Storage Summary

| Category | Tables | Total Size |
|----------|--------|------------|
| 13F Institutional | 9 | ~1,312 MB |
| Dark Pool | 2 | ~105 MB |
| Forex | 8 | ~72 MB |
| Airflow logs/metadata | 41 | ~10 MB |
| Portfolio | 7 | ~424 kB |
| Options | 3 | ~704 kB |
| Earnings | 2 | ~560 kB |
| All others | 26 | ~600 kB |
| **Total (approx)** | **98** | **~1.5 GB** |

---

## Data Sources

| Source | Tables Fed | Notes |
|--------|-----------|-------|
| SEC EDGAR | `f13_*` tables | Quarterly 13F filings, free |
| FRED (Federal Reserve) | `forex_daily_data` | Back to 1971 for major pairs, free |
| Yahoo Finance | `stock_prices`, `forex_daily_data` | 15-min delayed, rate limited |
| CBOE | `cboe_market_options_stats`, `cboe_options_volume` | Market-level options stats |
| Dark pool aggregators | `darkpool_*` | Weekly dark pool volume data |

---

## Query Patterns

### Get recent trend breaks with confidence
```sql
SELECT ticker, break_date, direction, confidence_score
FROM trend_breaks
WHERE break_date >= NOW() - INTERVAL '30 days'
ORDER BY confidence_score DESC
LIMIT 20;
```

### Institutional sentiment for a ticker
```sql
SELECT ticker, net_shares_change, signal, as_of_quarter
FROM f13_stock_aggregates
WHERE ticker = 'AAPL'
ORDER BY as_of_quarter DESC
LIMIT 4;
```

### Forex correlation matrix (strong pairs only)
```sql
SELECT pair_1, pair_2, correlation_30d, correlation_90d
FROM forex_correlations fc
JOIN forex_correlation_thresholds t ON fc.pair_1 = t.pair_symbol
WHERE ABS(correlation_90d) >= t.strong_threshold
ORDER BY ABS(correlation_90d) DESC;
```

### Dark pool activity (relative volume spike)
```sql
SELECT ticker, week_ending, darkpool_volume, total_volume,
       darkpool_volume::float / total_volume AS dp_pct
FROM darkpool_weekly_volume
WHERE week_ending >= NOW() - INTERVAL '4 weeks'
  AND darkpool_volume::float / total_volume > 0.40
ORDER BY dp_pct DESC;
```

### Portfolio current state
```sql
SELECT h.ticker, h.shares, h.entry_price,
       h.shares * h.entry_price AS cost_basis,
       s.direction, s.confidence
FROM portfolio_holdings h
LEFT JOIN portfolio_signals s ON h.ticker = s.ticker
ORDER BY cost_basis DESC;
```

---

## Files Reference

| File | Purpose |
|------|---------|
| `kubernetes/schema_forex.sql` | Forex table definitions |
| `kubernetes/schema_auth.sql` | Auth/user table definitions |
| `kubernetes/DATABASE_SCHEMA_GUIDE.md` | Extended schema documentation |
| `src/forex_data_fetcher.py` | Forex data pipeline (FRED + Yahoo) |
| `src/sec_13f_fetcher.py` | 13F filings from SEC EDGAR |
| `src/portfolio_manager.py` | Portfolio tracking and signal processing |
| `flask_app/app/utils/database.py` | Database connection manager |
| `kubernetes/airflow/dags/portfolio_update_dag.py` | Daily Airflow DAG |
