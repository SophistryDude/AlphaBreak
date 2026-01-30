# AlphaBreak PostgreSQL Time Series Database Schema Guide

Complete guide to AlphaBreak's time series database using TimescaleDB.

## Overview

The database uses **TimescaleDB**, a PostgreSQL extension optimized for time series data. It provides:
- Automatic partitioning (hypertables)
- Continuous aggregates for fast queries
- Data retention policies
- Compression

## Database Configuration

**Service**: `postgres-timeseries-service:5432`
**Database**: `trading_data`
**User**: `trading`
**Extension**: TimescaleDB

## Tables

### 1. stock_prices

Core OHLCV price data, partitioned by time.

```sql
CREATE TABLE stock_prices (
    id SERIAL,
    ticker VARCHAR(10) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    open NUMERIC(12, 4),
    high NUMERIC(12, 4),
    low NUMERIC(12, 4),
    close NUMERIC(12, 4),
    volume BIGINT,
    adjusted_close NUMERIC(12, 4),
    PRIMARY KEY (ticker, timestamp)
);
```

**Hypertable**: 7-day chunks
**Indexes**:
- `idx_stock_prices_ticker_time` on (ticker, timestamp DESC)

**Usage**:
```python
# Store price data
store_stock_price('AAPL', datetime.now(), 150.0, 152.0, 149.0, 151.5, 1000000, 151.5)

# Query recent prices
prices = get_recent_prices('AAPL', hours=24)
```

### 2. technical_indicators

Technical indicator values calculated from price data.

```sql
CREATE TABLE technical_indicators (
    id SERIAL,
    ticker VARCHAR(10) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    indicator_name VARCHAR(50) NOT NULL,
    indicator_value NUMERIC(12, 4),
    PRIMARY KEY (ticker, timestamp, indicator_name)
);
```

**Indicators stored**:
- RSI (14-period, 7-period for crypto)
- SMA/EMA (various periods)
- MACD (+ Signal + Histogram)
- Bollinger Bands (Upper, Lower, Mid)
- ATR (Average True Range)
- Volume indicators

**Usage**:
```python
# Store indicator
store_indicator('AAPL', datetime.now(), 'RSI_14', 65.4)

# Get indicator history
rsi_values = get_indicator_values('AAPL', 'RSI_14', hours=24)
```

### 3. engineered_features

Feature engineering outputs for model training.

```sql
CREATE TABLE engineered_features (
    id SERIAL,
    ticker VARCHAR(10) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    feature_name VARCHAR(100) NOT NULL,
    feature_value NUMERIC(12, 6),
    feature_metadata JSONB,
    PRIMARY KEY (ticker, timestamp, feature_name)
);
```

**Features stored**:
- Lag features (price_lag_1, price_lag_5, etc.)
- Rolling statistics (rolling_mean_20, rolling_std_10)
- Trend features (trend_strength, momentum_10m)
- Volume features (volume_ratio, volume_surge)
- Market regime features (volatility_regime, trend_regime)

### 4. trend_breaks

Detected and predicted trend break events.

```sql
CREATE TABLE trend_breaks (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    break_type VARCHAR(20) NOT NULL, -- 'bullish', 'bearish', 'consolidation'
    confidence NUMERIC(5, 4), -- 0.0 to 1.0
    predicted_direction VARCHAR(10), -- 'up', 'down', 'sideways'
    actual_direction VARCHAR(10),
    price_at_break NUMERIC(12, 4),
    model_version VARCHAR(50),
    metadata JSONB
);
```

**Break types**:
- `bullish`: Upward trend break
- `bearish`: Downward trend break
- `consolidation`: Sideways movement

### 5. predictions_log

All model predictions with actual outcomes for validation.

```sql
CREATE TABLE predictions_log (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,
    prediction_timestamp TIMESTAMPTZ NOT NULL,
    prediction_type VARCHAR(50) NOT NULL,
    predicted_value NUMERIC(12, 6),
    confidence NUMERIC(5, 4),
    actual_value NUMERIC(12, 6),
    actual_timestamp TIMESTAMPTZ,
    model_version VARCHAR(50),
    features_used JSONB,
    metadata JSONB
);
```

**Prediction types**:
- `trend_break`: Binary trend break prediction
- `price_target`: Price target prediction
- `direction`: Direction prediction (up/down/sideways)

**Usage**:
```python
# Store prediction
pred_id = store_prediction(
    ticker='AAPL',
    timestamp=datetime.now(),
    prediction_type='trend_break',
    predicted_value=0.85,  # 85% probability
    confidence=0.75,
    model_version='v2.1',
    features_used={'rsi': 65, 'macd': 0.5},
    metadata={'indicators_used': ['RSI', 'MACD']}
)

# Update with actual outcome (later)
update_prediction_actual(pred_id, actual_value=1.0, actual_timestamp=datetime.now())

# Get accuracy
accuracy = get_prediction_accuracy('v2.1', days=30)
```

### 6. indicator_accuracy

Tracks accuracy of individual indicators over time.

```sql
CREATE TABLE indicator_accuracy (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    indicator_name VARCHAR(50) NOT NULL,
    lookback_window INT,
    lookahead_window INT,
    accuracy NUMERIC(5, 4),
    precision_score NUMERIC(5, 4),
    recall_score NUMERIC(5, 4),
    f1_score NUMERIC(5, 4),
    samples_analyzed INT,
    metadata JSONB
);
```

**Usage**:
```python
# Store accuracy results
store_indicator_accuracy(
    ticker='AAPL',
    timestamp=datetime.now(),
    indicator_name='RSI_14',
    lookback_window=30,
    lookahead_window=30,
    accuracy=0.85,
    precision_score=0.82,
    recall_score=0.88,
    f1_score=0.85,
    samples_analyzed=1000,
    metadata={'threshold': 70}
)

# Get top indicators
top = get_top_indicators('AAPL', min_accuracy=0.7, days=30)
```

### 7. model_performance

Tracks overall model performance metrics.

```sql
CREATE TABLE model_performance (
    id SERIAL PRIMARY KEY,
    model_name VARCHAR(100) NOT NULL,
    model_version VARCHAR(50) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    metric_name VARCHAR(50) NOT NULL,
    metric_value NUMERIC(12, 6),
    ticker VARCHAR(10), -- NULL for aggregate
    metadata JSONB
);
```

**Metrics tracked**:
- `accuracy`: Classification accuracy
- `precision`: Precision score
- `recall`: Recall score
- `f1_score`: F1 score
- `auc_roc`: Area under ROC curve
- `sharpe_ratio`: Trading performance
- `total_return`: Backtest return

### 8. options_data

Options chain data for analysis.

```sql
CREATE TABLE options_data (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    option_type VARCHAR(4) NOT NULL, -- 'call' or 'put'
    strike_price NUMERIC(12, 4),
    expiration_date DATE,
    bid NUMERIC(12, 4),
    ask NUMERIC(12, 4),
    last_price NUMERIC(12, 4),
    volume BIGINT,
    open_interest BIGINT,
    implied_volatility NUMERIC(8, 6),
    delta NUMERIC(8, 6),
    gamma NUMERIC(8, 6),
    theta NUMERIC(8, 6),
    vega NUMERIC(8, 6),
    rho NUMERIC(8, 6)
);
```

### 9. backtest_results

Backtesting performance results.

```sql
CREATE TABLE backtest_results (
    id SERIAL PRIMARY KEY,
    backtest_name VARCHAR(100) NOT NULL,
    ticker VARCHAR(10) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    initial_capital NUMERIC(15, 2),
    final_capital NUMERIC(15, 2),
    total_return NUMERIC(8, 4),
    sharpe_ratio NUMERIC(8, 4),
    max_drawdown NUMERIC(8, 4),
    win_rate NUMERIC(5, 4),
    total_trades INT,
    winning_trades INT,
    losing_trades INT,
    avg_profit NUMERIC(12, 2),
    avg_loss NUMERIC(12, 2),
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

**Usage**:
```python
# Store backtest results
backtest_id = store_backtest_result(
    backtest_name='TrendBreak_v2.1',
    ticker='AAPL',
    start_date='2023-01-01',
    end_date='2024-01-01',
    initial_capital=100000,
    final_capital=125000,
    total_return=0.25,
    sharpe_ratio=1.8,
    max_drawdown=-0.08,
    win_rate=0.65,
    total_trades=150,
    winning_trades=98,
    losing_trades=52,
    avg_profit=500,
    avg_loss=-250,
    metadata={'strategy': 'trend_break'}
)

# Get best strategies
best = get_best_performing_strategies(days=90, limit=10)
```

## Continuous Aggregates (Pre-computed Views)

TimescaleDB automatically maintains these aggregated views:

### stock_prices_daily

Daily OHLCV aggregates.

```sql
SELECT * FROM stock_prices_daily
WHERE ticker = 'AAPL'
  AND day > NOW() - INTERVAL '30 days'
ORDER BY day DESC;
```

### indicators_hourly

Hourly indicator statistics.

```sql
SELECT * FROM indicators_hourly
WHERE ticker = 'AAPL'
  AND indicator_name = 'RSI_14'
  AND hour > NOW() - INTERVAL '7 days'
ORDER BY hour DESC;
```

## Common Queries

### Get latest price for ticker
```sql
SELECT close, volume
FROM stock_prices
WHERE ticker = 'AAPL'
ORDER BY timestamp DESC
LIMIT 1;
```

### Get top predictions today
```sql
SELECT ticker, predicted_value, confidence, model_version
FROM predictions_log
WHERE prediction_timestamp > CURRENT_DATE
  AND confidence > 0.75
ORDER BY confidence DESC
LIMIT 10;
```

### Calculate indicator win rate
```sql
SELECT
    indicator_name,
    AVG(accuracy) as avg_accuracy,
    COUNT(*) as evaluations
FROM indicator_accuracy
WHERE ticker = 'AAPL'
  AND timestamp > NOW() - INTERVAL '30 days'
GROUP BY indicator_name
HAVING AVG(accuracy) > 0.7
ORDER BY avg_accuracy DESC;
```

### Get model performance over time
```sql
SELECT
    DATE_TRUNC('day', timestamp) as day,
    AVG(metric_value) as avg_metric
FROM model_performance
WHERE model_name = 'TrendBreakXGBoost'
  AND metric_name = 'accuracy'
  AND timestamp > NOW() - INTERVAL '90 days'
GROUP BY day
ORDER BY day;
```

## Data Retention

Configure retention policies to manage storage:

```sql
-- Drop data older than 2 years
SELECT add_retention_policy('stock_prices', INTERVAL '2 years');
SELECT add_retention_policy('technical_indicators', INTERVAL '2 years');

-- Keep predictions for 3 years for validation
SELECT add_retention_policy('predictions_log', INTERVAL '3 years');
```

## Compression

Enable compression for older data:

```sql
-- Compress chunks older than 30 days
ALTER TABLE stock_prices SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'ticker'
);

SELECT add_compression_policy('stock_prices', INTERVAL '30 days');
```

## Backup

```bash
# Full backup
pg_dump -h postgres-timeseries-service -U trading trading_data > backup.sql

# Restore
psql -h postgres-timeseries-service -U trading trading_data < backup.sql
```

## Environment Variables

Set these in your Kubernetes deployments:

```yaml
- name: TIMESERIES_DB_HOST
  value: "postgres-timeseries-service"
- name: TIMESERIES_DB_PORT
  value: "5432"
- name: TIMESERIES_DB_NAME
  value: "trading_data"
- name: TIMESERIES_DB_USER
  value: "trading"
- name: TIMESERIES_DB_PASSWORD
  valueFrom:
    secretKeyRef:
      name: trading-secrets
      key: timeseries-postgres-password
```

## Connection in Python

```python
from app.utils.database import db_manager, store_stock_price, get_recent_prices

# Store price data
store_stock_price('AAPL', datetime.now(), 150.0, 152.0, 149.0, 151.5, 1000000, 151.5)

# Query data
prices = get_recent_prices('AAPL', hours=24)

# Raw queries
with db_manager.get_cursor() as cursor:
    cursor.execute("SELECT * FROM stock_prices WHERE ticker = %s LIMIT 10", ('AAPL',))
    results = cursor.fetchall()
```

## Monitoring

```sql
-- Check database size
SELECT pg_size_pretty(pg_database_size('trading_data'));

-- Check table sizes
SELECT
    hypertable_name,
    pg_size_pretty(hypertable_size(hypertable_name::regclass))
FROM timescaledb_information.hypertables;

-- Check chunk count
SELECT hypertable_name, COUNT(*) as chunk_count
FROM timescaledb_information.chunks
GROUP BY hypertable_name;

-- Check continuous aggregate refresh status
SELECT * FROM timescaledb_information.continuous_aggregate_stats;
```
