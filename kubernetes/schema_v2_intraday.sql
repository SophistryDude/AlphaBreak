-- ============================================================================
-- Trading System Database Schema v2 - Intraday Support
-- ============================================================================
-- Normalized multi-table design optimized for:
-- - 10-minute and hourly trend break detection
-- - S&P 500 + DJIA full history
-- - TimescaleDB hypertables for time-series performance
-- ============================================================================

-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- ============================================================================
-- CORE PRICE DATA TABLES
-- ============================================================================

-- ----------------------------------------------------------------------------
-- Table: stock_prices_intraday
-- Primary table for 1-minute to hourly OHLCV data
-- Partitioned by time (TimescaleDB hypertable)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS stock_prices_intraday (
    ticker VARCHAR(10) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    interval_type VARCHAR(10) NOT NULL,  -- '1min', '5min', '10min', '15min', '30min', '1hour'
    open DECIMAL(12, 4),
    high DECIMAL(12, 4),
    low DECIMAL(12, 4),
    close DECIMAL(12, 4),
    volume BIGINT,
    vwap DECIMAL(12, 4),                 -- Volume-weighted average price
    trade_count INTEGER,                  -- Number of trades in interval
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (ticker, timestamp, interval_type)
);

-- Convert to hypertable with 1-day chunks (optimal for intraday queries)
SELECT create_hypertable('stock_prices_intraday', 'timestamp',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

-- Create indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_intraday_ticker_interval
    ON stock_prices_intraday (ticker, interval_type, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_intraday_interval_time
    ON stock_prices_intraday (interval_type, timestamp DESC);

-- ----------------------------------------------------------------------------
-- Table: stock_prices_daily
-- Daily OHLCV data (keep existing structure, renamed for clarity)
-- For long-term analysis and indicator calculations
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS stock_prices_daily (
    ticker VARCHAR(10) NOT NULL,
    date DATE NOT NULL,
    open DECIMAL(12, 4),
    high DECIMAL(12, 4),
    low DECIMAL(12, 4),
    close DECIMAL(12, 4),
    volume BIGINT,
    adjusted_close DECIMAL(12, 4),       -- Split/dividend adjusted
    data_source VARCHAR(20) DEFAULT 'yahoo',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (ticker, date)
);

SELECT create_hypertable('stock_prices_daily', 'date',
    chunk_time_interval => INTERVAL '1 year',
    if_not_exists => TRUE
);

CREATE INDEX IF NOT EXISTS idx_daily_ticker_date
    ON stock_prices_daily (ticker, date DESC);

-- ============================================================================
-- CORPORATE ACTIONS & ADJUSTMENTS
-- ============================================================================

-- ----------------------------------------------------------------------------
-- Table: corporate_actions
-- Dividends, splits, spinoffs for price adjustment
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS corporate_actions (
    id SERIAL,
    ticker VARCHAR(10) NOT NULL,
    ex_date DATE NOT NULL,
    record_date DATE,
    payment_date DATE,
    action_type VARCHAR(20) NOT NULL,    -- 'dividend', 'split', 'spinoff', 'merger'
    value DECIMAL(12, 6),                 -- Dividend amount or split ratio
    description TEXT,
    data_source VARCHAR(20) DEFAULT 'yahoo',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (ticker, ex_date, action_type)
);

CREATE INDEX IF NOT EXISTS idx_corp_actions_ticker
    ON corporate_actions (ticker, ex_date DESC);
CREATE INDEX IF NOT EXISTS idx_corp_actions_type
    ON corporate_actions (action_type, ex_date DESC);

-- ============================================================================
-- INDEX MEMBERSHIP & CONSTITUENTS
-- ============================================================================

-- ----------------------------------------------------------------------------
-- Table: index_definitions
-- Define tracked indices (S&P 500, DJIA, etc.)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS index_definitions (
    index_symbol VARCHAR(10) PRIMARY KEY, -- 'SPY', 'DIA', 'QQQ'
    index_name VARCHAR(100) NOT NULL,
    description TEXT,
    constituent_count INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert common indices
INSERT INTO index_definitions (index_symbol, index_name, constituent_count) VALUES
    ('SPY', 'S&P 500', 500),
    ('DIA', 'Dow Jones Industrial Average', 30),
    ('QQQ', 'NASDAQ-100', 100),
    ('IWM', 'Russell 2000', 2000)
ON CONFLICT (index_symbol) DO NOTHING;

-- ----------------------------------------------------------------------------
-- Table: index_constituents
-- Historical index membership (important for survivorship bias)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS index_constituents (
    id SERIAL PRIMARY KEY,
    index_symbol VARCHAR(10) NOT NULL REFERENCES index_definitions(index_symbol),
    ticker VARCHAR(10) NOT NULL,
    added_date DATE NOT NULL,
    removed_date DATE,                    -- NULL if currently in index
    sector VARCHAR(50),
    sub_industry VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (index_symbol, ticker, added_date)
);

CREATE INDEX IF NOT EXISTS idx_constituents_index
    ON index_constituents (index_symbol, ticker);
CREATE INDEX IF NOT EXISTS idx_constituents_active
    ON index_constituents (index_symbol) WHERE removed_date IS NULL;
CREATE INDEX IF NOT EXISTS idx_constituents_date_range
    ON index_constituents (index_symbol, added_date, removed_date);

-- ============================================================================
-- TICKER METADATA
-- ============================================================================

-- ----------------------------------------------------------------------------
-- Table: ticker_metadata
-- Static and semi-static company information
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ticker_metadata (
    ticker VARCHAR(10) PRIMARY KEY,
    company_name VARCHAR(200),
    sector VARCHAR(50),
    industry VARCHAR(100),
    sub_industry VARCHAR(100),
    market_cap_category VARCHAR(20),      -- 'mega', 'large', 'mid', 'small', 'micro'
    exchange VARCHAR(20),                  -- 'NYSE', 'NASDAQ', 'AMEX'
    ipo_date DATE,
    is_active BOOLEAN DEFAULT TRUE,
    cik VARCHAR(20),                       -- SEC Central Index Key
    cusip VARCHAR(12),
    isin VARCHAR(20),
    last_updated TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_metadata_sector
    ON ticker_metadata (sector, industry);
CREATE INDEX IF NOT EXISTS idx_metadata_active
    ON ticker_metadata (is_active) WHERE is_active = TRUE;

-- ============================================================================
-- OPTIONS DATA (Limited - free sources don't have historical)
-- ============================================================================

-- ----------------------------------------------------------------------------
-- Table: options_daily_summary
-- Daily options activity summary per ticker
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS options_daily_summary (
    ticker VARCHAR(10) NOT NULL,
    date DATE NOT NULL,
    total_call_volume BIGINT,
    total_put_volume BIGINT,
    put_call_ratio DECIMAL(8, 4),
    total_call_oi BIGINT,                 -- Open interest
    total_put_oi BIGINT,
    implied_volatility_30d DECIMAL(8, 4), -- 30-day IV
    implied_volatility_60d DECIMAL(8, 4),
    iv_rank DECIMAL(5, 2),                -- IV percentile (0-100)
    iv_percentile DECIMAL(5, 2),
    data_source VARCHAR(20),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (ticker, date)
);

SELECT create_hypertable('options_daily_summary', 'date',
    chunk_time_interval => INTERVAL '1 year',
    if_not_exists => TRUE
);

-- ============================================================================
-- MARKET BREADTH & AGGREGATE METRICS
-- ============================================================================

-- ----------------------------------------------------------------------------
-- Table: market_breadth_intraday
-- Index-level breadth metrics for 10min/hourly analysis
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS market_breadth_intraday (
    index_symbol VARCHAR(10) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    interval_type VARCHAR(10) NOT NULL,   -- '10min', '1hour'
    advances INTEGER,                      -- Stocks up
    declines INTEGER,                      -- Stocks down
    unchanged INTEGER,
    advance_volume BIGINT,
    decline_volume BIGINT,
    new_highs INTEGER,                    -- 52-week highs
    new_lows INTEGER,                     -- 52-week lows
    above_200ma INTEGER,                  -- Stocks above 200-day MA
    above_50ma INTEGER,
    ad_line DECIMAL(12, 2),               -- Advance-decline line
    ad_ratio DECIMAL(8, 4),
    mcclellan_oscillator DECIMAL(8, 2),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (index_symbol, timestamp, interval_type)
);

SELECT create_hypertable('market_breadth_intraday', 'timestamp',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

-- ----------------------------------------------------------------------------
-- Table: market_breadth_daily
-- Daily market breadth for longer-term context
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS market_breadth_daily (
    index_symbol VARCHAR(10) NOT NULL,
    date DATE NOT NULL,
    advances INTEGER,
    declines INTEGER,
    unchanged INTEGER,
    advance_volume BIGINT,
    decline_volume BIGINT,
    new_highs_52w INTEGER,
    new_lows_52w INTEGER,
    percent_above_200ma DECIMAL(5, 2),
    percent_above_50ma DECIMAL(5, 2),
    percent_above_20ma DECIMAL(5, 2),
    ad_line DECIMAL(12, 2),
    mcclellan_oscillator DECIMAL(8, 2),
    mcclellan_summation DECIMAL(12, 2),
    arms_index DECIMAL(8, 4),             -- TRIN
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (index_symbol, date)
);

SELECT create_hypertable('market_breadth_daily', 'date',
    chunk_time_interval => INTERVAL '1 year',
    if_not_exists => TRUE
);

-- ============================================================================
-- TECHNICAL INDICATORS (Pre-calculated)
-- ============================================================================

-- ----------------------------------------------------------------------------
-- Table: technical_indicators_intraday
-- Pre-calculated indicators for 10min/hourly data
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS technical_indicators_intraday (
    ticker VARCHAR(10) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    interval_type VARCHAR(10) NOT NULL,
    indicator_name VARCHAR(50) NOT NULL,
    indicator_value DECIMAL(18, 6),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (ticker, timestamp, interval_type, indicator_name)
);

SELECT create_hypertable('technical_indicators_intraday', 'timestamp',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

CREATE INDEX IF NOT EXISTS idx_ti_intraday_ticker_indicator
    ON technical_indicators_intraday (ticker, indicator_name, interval_type, timestamp DESC);

-- ----------------------------------------------------------------------------
-- Table: technical_indicators_daily
-- Pre-calculated daily indicators (keep existing, add index)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS technical_indicators_daily (
    ticker VARCHAR(10) NOT NULL,
    date DATE NOT NULL,
    indicator_name VARCHAR(50) NOT NULL,
    indicator_value DECIMAL(18, 6),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (ticker, date, indicator_name)
);

SELECT create_hypertable('technical_indicators_daily', 'date',
    chunk_time_interval => INTERVAL '1 year',
    if_not_exists => TRUE
);

-- ============================================================================
-- DATA QUALITY & TRACKING
-- ============================================================================

-- ----------------------------------------------------------------------------
-- Table: data_fetch_log
-- Track what data we have and its quality
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS data_fetch_log (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,
    data_type VARCHAR(30) NOT NULL,       -- 'price_daily', 'price_intraday', 'options', etc.
    interval_type VARCHAR(10),            -- For intraday: '1min', '10min', etc.
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    records_fetched INTEGER,
    records_inserted INTEGER,
    data_source VARCHAR(30) NOT NULL,
    fetch_status VARCHAR(20) NOT NULL,    -- 'success', 'partial', 'failed'
    error_message TEXT,
    fetch_duration_ms INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_fetch_log_ticker
    ON data_fetch_log (ticker, data_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_fetch_log_status
    ON data_fetch_log (fetch_status, created_at DESC);

-- ----------------------------------------------------------------------------
-- Table: data_gaps
-- Track missing data periods for later backfill
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS data_gaps (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,
    data_type VARCHAR(30) NOT NULL,
    interval_type VARCHAR(10),
    gap_start TIMESTAMPTZ NOT NULL,
    gap_end TIMESTAMPTZ NOT NULL,
    expected_records INTEGER,
    gap_reason VARCHAR(50),               -- 'market_closed', 'fetch_failed', 'no_trading'
    is_resolved BOOLEAN DEFAULT FALSE,
    resolved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_gaps_unresolved
    ON data_gaps (ticker, data_type) WHERE is_resolved = FALSE;

-- ============================================================================
-- VIEWS FOR COMMON QUERIES
-- ============================================================================

-- View: Current S&P 500 constituents
CREATE OR REPLACE VIEW v_sp500_current AS
SELECT
    ic.ticker,
    tm.company_name,
    tm.sector,
    tm.industry,
    ic.added_date
FROM index_constituents ic
LEFT JOIN ticker_metadata tm ON ic.ticker = tm.ticker
WHERE ic.index_symbol = 'SPY'
  AND ic.removed_date IS NULL
ORDER BY tm.sector, ic.ticker;

-- View: Current DJIA constituents
CREATE OR REPLACE VIEW v_djia_current AS
SELECT
    ic.ticker,
    tm.company_name,
    tm.sector,
    ic.added_date
FROM index_constituents ic
LEFT JOIN ticker_metadata tm ON ic.ticker = tm.ticker
WHERE ic.index_symbol = 'DIA'
  AND ic.removed_date IS NULL
ORDER BY ic.ticker;

-- View: Latest intraday prices (10min)
CREATE OR REPLACE VIEW v_latest_prices_10min AS
SELECT DISTINCT ON (ticker)
    ticker,
    timestamp,
    open, high, low, close, volume, vwap
FROM stock_prices_intraday
WHERE interval_type = '10min'
ORDER BY ticker, timestamp DESC;

-- View: Data coverage summary
CREATE OR REPLACE VIEW v_data_coverage AS
SELECT
    ticker,
    'daily' as data_type,
    MIN(date) as first_date,
    MAX(date) as last_date,
    COUNT(*) as record_count
FROM stock_prices_daily
GROUP BY ticker
UNION ALL
SELECT
    ticker,
    interval_type as data_type,
    MIN(timestamp)::date as first_date,
    MAX(timestamp)::date as last_date,
    COUNT(*) as record_count
FROM stock_prices_intraday
GROUP BY ticker, interval_type
ORDER BY ticker, data_type;

-- ============================================================================
-- FUNCTIONS FOR DATA AGGREGATION
-- ============================================================================

-- Function: Aggregate 1-min data to any interval
CREATE OR REPLACE FUNCTION aggregate_ohlcv(
    p_ticker VARCHAR(10),
    p_start_time TIMESTAMPTZ,
    p_end_time TIMESTAMPTZ,
    p_interval INTERVAL
)
RETURNS TABLE (
    bucket TIMESTAMPTZ,
    open DECIMAL(12,4),
    high DECIMAL(12,4),
    low DECIMAL(12,4),
    close DECIMAL(12,4),
    volume BIGINT,
    vwap DECIMAL(12,4),
    trade_count INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        time_bucket(p_interval, timestamp) as bucket,
        first(spi.open, timestamp) as open,
        max(spi.high) as high,
        min(spi.low) as low,
        last(spi.close, timestamp) as close,
        sum(spi.volume)::BIGINT as volume,
        CASE WHEN sum(spi.volume) > 0
             THEN sum(spi.close * spi.volume) / sum(spi.volume)
             ELSE NULL END as vwap,
        sum(spi.trade_count)::INTEGER as trade_count
    FROM stock_prices_intraday spi
    WHERE spi.ticker = p_ticker
      AND spi.timestamp >= p_start_time
      AND spi.timestamp < p_end_time
      AND spi.interval_type = '1min'
    GROUP BY time_bucket(p_interval, timestamp)
    ORDER BY bucket;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- CONTINUOUS AGGREGATES (TimescaleDB auto-refresh)
-- ============================================================================

-- 10-minute OHLCV aggregate (auto-maintained)
CREATE MATERIALIZED VIEW IF NOT EXISTS cagg_prices_10min
WITH (timescaledb.continuous) AS
SELECT
    ticker,
    time_bucket('10 minutes', timestamp) AS bucket,
    first(open, timestamp) AS open,
    max(high) AS high,
    min(low) AS low,
    last(close, timestamp) AS close,
    sum(volume) AS volume,
    CASE WHEN sum(volume) > 0
         THEN sum(close * volume) / sum(volume)
         ELSE NULL END AS vwap,
    sum(trade_count) AS trade_count
FROM stock_prices_intraday
WHERE interval_type = '1min'
GROUP BY ticker, time_bucket('10 minutes', timestamp)
WITH NO DATA;

-- Refresh policy for 10-min aggregate
SELECT add_continuous_aggregate_policy('cagg_prices_10min',
    start_offset => INTERVAL '1 day',
    end_offset => INTERVAL '10 minutes',
    schedule_interval => INTERVAL '10 minutes',
    if_not_exists => TRUE);

-- 1-hour OHLCV aggregate
CREATE MATERIALIZED VIEW IF NOT EXISTS cagg_prices_1hour
WITH (timescaledb.continuous) AS
SELECT
    ticker,
    time_bucket('1 hour', timestamp) AS bucket,
    first(open, timestamp) AS open,
    max(high) AS high,
    min(low) AS low,
    last(close, timestamp) AS close,
    sum(volume) AS volume,
    CASE WHEN sum(volume) > 0
         THEN sum(close * volume) / sum(volume)
         ELSE NULL END AS vwap,
    sum(trade_count) AS trade_count
FROM stock_prices_intraday
WHERE interval_type = '1min'
GROUP BY ticker, time_bucket('1 hour', timestamp)
WITH NO DATA;

SELECT add_continuous_aggregate_policy('cagg_prices_1hour',
    start_offset => INTERVAL '3 days',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour',
    if_not_exists => TRUE);

-- ============================================================================
-- RETENTION POLICIES
-- ============================================================================

-- Keep 1-min data for 30 days, then auto-delete
SELECT add_retention_policy('stock_prices_intraday',
    INTERVAL '30 days',
    if_not_exists => TRUE);

-- Keep intraday indicators for 90 days
SELECT add_retention_policy('technical_indicators_intraday',
    INTERVAL '90 days',
    if_not_exists => TRUE);

-- Daily data: no retention (keep forever)
-- Market breadth intraday: 90 days
SELECT add_retention_policy('market_breadth_intraday',
    INTERVAL '90 days',
    if_not_exists => TRUE);

-- ============================================================================
-- COMPRESSION POLICIES (Space optimization)
-- ============================================================================

-- Compress daily data older than 7 days
ALTER TABLE stock_prices_daily SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'ticker'
);

SELECT add_compression_policy('stock_prices_daily',
    INTERVAL '7 days',
    if_not_exists => TRUE);

-- Compress intraday data older than 1 day
ALTER TABLE stock_prices_intraday SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'ticker, interval_type'
);

SELECT add_compression_policy('stock_prices_intraday',
    INTERVAL '1 day',
    if_not_exists => TRUE);

-- ============================================================================
-- GRANTS
-- ============================================================================

GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO trading;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO trading;
GRANT USAGE ON SCHEMA public TO trading;

-- Read-only for app user
GRANT SELECT ON ALL TABLES IN SCHEMA public TO app_user;

-- ============================================================================
-- ESTIMATED STORAGE REQUIREMENTS
-- ============================================================================
--
-- S&P 500 + DJIA (~530 unique tickers accounting for overlap):
--
-- Daily data (1962-2026, ~64 years):
--   530 tickers × 252 days × 64 years × 100 bytes ≈ 850 MB
--
-- 1-minute intraday (30 days retained):
--   530 tickers × 390 min/day × 30 days × 80 bytes ≈ 500 MB
--
-- 10-min aggregates (continuous, all history):
--   530 tickers × 39 intervals/day × 252 days × 5 years × 80 bytes ≈ 2 GB
--
-- Hourly aggregates (continuous, all history):
--   530 tickers × 7 hours/day × 252 days × 10 years × 80 bytes ≈ 750 MB
--
-- Total estimated: 5-10 GB (with compression: 2-4 GB)
-- ============================================================================
