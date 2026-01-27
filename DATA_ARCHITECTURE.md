# Data Architecture for Intraday Trend Break Detection

## Overview

This document describes the database schema and data pipeline for storing historical securities data with support for 10-minute and hourly trend break detection.

## Schema Design: Normalized Multi-Table (Option B)

### Why Normalized?
- **Query efficiency**: Only load the data you need
- **Data integrity**: Proper constraints per data type
- **Scalability**: Easy to add options, sentiment, alternative data later
- **TimescaleDB optimization**: Each hypertable tuned for its access pattern

---

## Table Structure

### Core Price Tables

```
┌─────────────────────────────────────────────────────────────────┐
│                    stock_prices_intraday                        │
│  (TimescaleDB Hypertable - 1-day chunks)                       │
├─────────────────────────────────────────────────────────────────┤
│  ticker          │ VARCHAR(10)   │ Stock symbol               │
│  timestamp       │ TIMESTAMPTZ   │ Bar timestamp (PK)         │
│  interval_type   │ VARCHAR(10)   │ '1min','5min','10min','1hour'│
│  open            │ DECIMAL(12,4) │ Opening price              │
│  high            │ DECIMAL(12,4) │ High price                 │
│  low             │ DECIMAL(12,4) │ Low price                  │
│  close           │ DECIMAL(12,4) │ Closing price              │
│  volume          │ BIGINT        │ Share volume               │
│  vwap            │ DECIMAL(12,4) │ Volume-weighted avg price  │
│  trade_count     │ INTEGER       │ Number of trades           │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    stock_prices_daily                           │
│  (TimescaleDB Hypertable - 1-year chunks)                      │
├─────────────────────────────────────────────────────────────────┤
│  ticker          │ VARCHAR(10)   │ Stock symbol               │
│  date            │ DATE          │ Trading date (PK)          │
│  open            │ DECIMAL(12,4) │ Opening price              │
│  high            │ DECIMAL(12,4) │ High price                 │
│  low             │ DECIMAL(12,4) │ Low price                  │
│  close           │ DECIMAL(12,4) │ Closing price              │
│  volume          │ BIGINT        │ Share volume               │
│  adjusted_close  │ DECIMAL(12,4) │ Split/dividend adjusted    │
│  data_source     │ VARCHAR(20)   │ 'yahoo', 'polygon', etc.   │
└─────────────────────────────────────────────────────────────────┘
```

### Supporting Tables

```
┌─────────────────────────────────────────────────────────────────┐
│                    corporate_actions                            │
├─────────────────────────────────────────────────────────────────┤
│  ticker          │ VARCHAR(10)   │ Stock symbol               │
│  ex_date         │ DATE          │ Ex-dividend/split date (PK)│
│  action_type     │ VARCHAR(20)   │ 'dividend','split','spinoff'│
│  value           │ DECIMAL(12,6) │ Amount or ratio            │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    index_constituents                           │
├─────────────────────────────────────────────────────────────────┤
│  index_symbol    │ VARCHAR(10)   │ 'SPY', 'DIA', etc.         │
│  ticker          │ VARCHAR(10)   │ Stock symbol               │
│  added_date      │ DATE          │ When added to index        │
│  removed_date    │ DATE          │ When removed (NULL=current)│
│  sector          │ VARCHAR(50)   │ GICS sector                │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    ticker_metadata                              │
├─────────────────────────────────────────────────────────────────┤
│  ticker          │ VARCHAR(10)   │ Stock symbol (PK)          │
│  company_name    │ VARCHAR(200)  │ Full company name          │
│  sector          │ VARCHAR(50)   │ GICS sector                │
│  industry        │ VARCHAR(100)  │ GICS industry              │
│  market_cap_cat  │ VARCHAR(20)   │ 'mega','large','mid','small'│
│  exchange        │ VARCHAR(20)   │ 'NYSE', 'NASDAQ'           │
└─────────────────────────────────────────────────────────────────┘
```

### Market Breadth (for Index-Level Analysis)

```
┌─────────────────────────────────────────────────────────────────┐
│                 market_breadth_intraday                         │
├─────────────────────────────────────────────────────────────────┤
│  index_symbol    │ VARCHAR(10)   │ 'SPY', 'DIA'               │
│  timestamp       │ TIMESTAMPTZ   │ Interval timestamp         │
│  interval_type   │ VARCHAR(10)   │ '10min', '1hour'           │
│  advances        │ INTEGER       │ Stocks up                  │
│  declines        │ INTEGER       │ Stocks down                │
│  new_highs       │ INTEGER       │ 52-week highs              │
│  new_lows        │ INTEGER       │ 52-week lows               │
│  ad_line         │ DECIMAL       │ Advance-decline line       │
└─────────────────────────────────────────────────────────────────┘
```

---

## Data Sources & Limitations

### Yahoo Finance (Free)

| Data Type | Availability | Limitations |
|-----------|--------------|-------------|
| Daily OHLCV | 1962+ for major stocks | Good quality, some gaps |
| 1-minute bars | Last 7 days only | Short retention |
| 5/15/30-min bars | Last 60 days | Moderate retention |
| Hourly bars | Last 730 days | Good for recent history |
| Dividends/Splits | Full history | Complete |
| Options | Current chain only | **NO historical volume** |

### Polygon.io (Paid - Recommended for Production)

| Tier | Cost | Data |
|------|------|------|
| Basic | $29/mo | 2 years historical, 15-min delayed |
| Starter | $79/mo | 5 years, real-time |
| Developer | $199/mo | Full history, options |

### Alpha Vantage (Free Tier)

- 5 API calls/minute, 500/day
- Intraday: 1-2 months
- Daily: 20+ years

### For Options Historical Data (Required for Options-Based Trend Breaks)

| Source | Cost | Data |
|--------|------|------|
| ORATS | ~$100/mo | Full options history, Greeks |
| OptionMetrics | Enterprise | Academic gold standard |
| CBOE DataShop | Per-request | Official exchange data |

---

## Storage Estimates

### S&P 500 + DJIA (~530 unique tickers)

| Data Type | Records | Uncompressed | Compressed |
|-----------|---------|--------------|------------|
| Daily (64 years) | 8.5M | 850 MB | 340 MB |
| 1-min (30 days) | 619M | 500 MB | 200 MB |
| 10-min aggregates (5 yrs) | 26M | 2 GB | 800 MB |
| Hourly aggregates (10 yrs) | 9.3M | 750 MB | 300 MB |
| **Total** | - | **~5 GB** | **~2 GB** |

### TimescaleDB Features Used

1. **Hypertables**: Auto-partitioned by time
2. **Continuous Aggregates**: Auto-refresh 10-min and hourly rollups from 1-min data
3. **Compression**: 60%+ space savings on older data
4. **Retention Policies**: Auto-delete 1-min data older than 30 days

---

## Data Pipeline

### Initial Load

```bash
# 1. Apply schema (run once)
kubectl exec -n trading-system postgres-pod -- psql -U trading -d trading_data \
  -f /path/to/schema_v2_intraday.sql

# 2. Estimate storage
python -m src.populate_historical_data --sp500 --estimate-only

# 3. Load DJIA first (smaller, ~30 tickers)
python -m src.populate_historical_data --djia --daily --actions --metadata

# 4. Load full S&P 500
python -m src.populate_historical_data --sp500 --daily --actions --metadata

# 5. Start intraday collection (run daily via Airflow)
python -m src.populate_historical_data --sp500 --intraday
```

### Ongoing Updates (Airflow DAGs)

| DAG | Schedule | Purpose |
|-----|----------|---------|
| `fetch_daily_prices` | 6 PM ET | Daily close data |
| `fetch_intraday_1min` | Every 1 min (market hours) | Real-time 1-min bars |
| `refresh_aggregates` | Every 10 min | Ensure continuous aggregates current |
| `check_data_gaps` | Daily | Identify and backfill missing data |

---

## Query Patterns for Trend Break Detection

### Get 10-Minute Bars for Ticker

```sql
-- Using continuous aggregate (fast)
SELECT bucket, open, high, low, close, volume
FROM cagg_prices_10min
WHERE ticker = 'AAPL'
  AND bucket >= NOW() - INTERVAL '5 days'
ORDER BY bucket;

-- Or from raw data
SELECT * FROM stock_prices_intraday
WHERE ticker = 'AAPL'
  AND interval_type = '10min'
  AND timestamp >= NOW() - INTERVAL '5 days';
```

### Get Hourly Bars with Volume Profile

```sql
SELECT
    bucket,
    open, high, low, close,
    volume,
    vwap,
    volume / AVG(volume) OVER (ORDER BY bucket ROWS 20 PRECEDING) as relative_volume
FROM cagg_prices_1hour
WHERE ticker = 'AAPL'
  AND bucket >= NOW() - INTERVAL '30 days';
```

### Market Breadth at 10-Minute Intervals

```sql
SELECT
    timestamp,
    advances,
    declines,
    advances::float / NULLIF(declines, 0) as ad_ratio,
    new_highs - new_lows as hi_lo_diff
FROM market_breadth_intraday
WHERE index_symbol = 'SPY'
  AND interval_type = '10min'
  AND timestamp >= NOW() - INTERVAL '1 day';
```

---

## Next Steps

1. **Run schema migration**: Apply `schema_v2_intraday.sql` to your TimescaleDB
2. **Load historical daily data**: Start with DJIA, then S&P 500
3. **Set up intraday pipeline**: Configure Airflow DAG for 1-min data collection
4. **Build trend break tables**: Once data is populated, create trend break detection views/tables
5. **Consider paid data**: For production, Polygon.io provides better intraday history

---

## Files Reference

| File | Purpose |
|------|---------|
| `kubernetes/schema_v2_intraday.sql` | Complete schema definition |
| `src/populate_historical_data.py` | Data fetching script |
| `src/populate_database.py` | Original daily-only script (kept for compatibility) |
| `flask_app/app/utils/database.py` | Database connection utilities |
