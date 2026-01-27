-- ============================================================================
-- Trend Break Detection Schema
-- ============================================================================
-- Tables for storing detected trend breaks/reversals at multiple timeframes
-- Used for training the meta_learning_model to predict trend break probability
-- ============================================================================

-- ============================================================================
-- TREND BREAK DETECTION TABLES
-- ============================================================================

-- ----------------------------------------------------------------------------
-- Table: trend_breaks
-- Core table storing detected peaks and troughs at various timeframes
-- Each record represents a point where the trend reversed direction
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS trend_breaks (
    id SERIAL,
    ticker VARCHAR(10) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,           -- When the trend break occurred
    timeframe VARCHAR(10) NOT NULL,           -- 'daily', '1hour', '5min', '1min'

    -- Break characteristics
    break_type VARCHAR(10) NOT NULL,          -- 'peak' or 'trough'
    direction_before VARCHAR(15) NOT NULL,    -- 'increasing' or 'decreasing'
    direction_after VARCHAR(15) NOT NULL,     -- 'decreasing' or 'increasing'

    -- Price data at break point
    price_at_break DECIMAL(12, 4) NOT NULL,
    trend_value DECIMAL(18, 6),               -- Trend line value at break

    -- Break strength metrics
    magnitude DECIMAL(18, 6),                 -- Sharpness of reversal
    price_change_pct DECIMAL(10, 4),          -- % change from previous break
    volume_ratio DECIMAL(10, 4),              -- Volume vs avg volume at break

    -- Preceding trend info (for "trend length" feature)
    periods_since_last_break INTEGER,         -- How long was the preceding trend
    trend_strength DECIMAL(10, 4),            -- Avg directional movement

    -- Detection metadata
    detection_method VARCHAR(50) DEFAULT 'local_extrema',
    created_at TIMESTAMPTZ DEFAULT NOW(),

    PRIMARY KEY (ticker, timestamp, timeframe)
);

-- Convert to hypertable for time-series performance
SELECT create_hypertable('trend_breaks', 'timestamp',
    chunk_time_interval => INTERVAL '1 month',
    if_not_exists => TRUE
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_trend_breaks_ticker_tf
    ON trend_breaks (ticker, timeframe, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_trend_breaks_type
    ON trend_breaks (break_type, timeframe, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_trend_breaks_recent
    ON trend_breaks (timeframe, timestamp DESC);


-- ----------------------------------------------------------------------------
-- Table: trend_ranges
-- Stores the trend periods BETWEEN breaks
-- Each range represents a continuous upward or downward trend
-- Critical for ML training: "given we're X periods into a trend, what's break probability?"
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS trend_ranges (
    id SERIAL,
    ticker VARCHAR(10) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,           -- 'daily', '1hour', '5min', '1min'

    -- Range boundaries
    start_timestamp TIMESTAMPTZ NOT NULL,     -- When this trend started (break point)
    end_timestamp TIMESTAMPTZ NOT NULL,       -- When this trend ended (next break)
    start_break_id INTEGER,                   -- Reference to trend_breaks
    end_break_id INTEGER,

    -- Trend characteristics
    trend_direction VARCHAR(10) NOT NULL,     -- 'upward' or 'downward'
    start_break_type VARCHAR(10) NOT NULL,    -- 'peak' or 'trough' at start
    end_break_type VARCHAR(10) NOT NULL,      -- 'peak' or 'trough' at end

    -- Trend metrics
    range_periods INTEGER NOT NULL,           -- Number of periods in range
    start_price DECIMAL(12, 4),
    end_price DECIMAL(12, 4),
    price_change DECIMAL(12, 4),
    price_change_pct DECIMAL(10, 4),
    max_price DECIMAL(12, 4),
    min_price DECIMAL(12, 4),

    -- Volume profile during trend
    avg_volume BIGINT,
    total_volume BIGINT,
    volume_trend VARCHAR(15),                 -- 'increasing', 'decreasing', 'flat'

    -- Magnitude metrics
    start_magnitude DECIMAL(18, 6),           -- Break magnitude at start
    end_magnitude DECIMAL(18, 6),             -- Break magnitude at end

    created_at TIMESTAMPTZ DEFAULT NOW(),

    PRIMARY KEY (ticker, start_timestamp, timeframe)  -- start_timestamp must be part of PK for hypertable
);

SELECT create_hypertable('trend_ranges', 'start_timestamp',
    chunk_time_interval => INTERVAL '3 months',
    if_not_exists => TRUE
);

CREATE INDEX IF NOT EXISTS idx_trend_ranges_ticker_tf
    ON trend_ranges (ticker, timeframe, start_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_trend_ranges_direction
    ON trend_ranges (trend_direction, timeframe, start_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_trend_ranges_length
    ON trend_ranges (range_periods, timeframe);


-- ----------------------------------------------------------------------------
-- Table: trend_break_features
-- Pre-computed ML features for each point in time
-- Used to train model: "what features predict an upcoming break?"
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS trend_break_features (
    id SERIAL,
    ticker VARCHAR(10) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    timeframe VARCHAR(10) NOT NULL,

    -- Current trend state
    current_trend_direction VARCHAR(10),      -- 'upward' or 'downward'
    periods_in_current_trend INTEGER,         -- How long since last break
    trend_age_ratio DECIMAL(6, 4),           -- periods / typical_trend_length (13-18)

    -- Price momentum
    price_vs_trend DECIMAL(10, 4),           -- Price deviation from trend line
    momentum_1 DECIMAL(10, 4),               -- 1-period momentum
    momentum_3 DECIMAL(10, 4),               -- 3-period momentum
    momentum_5 DECIMAL(10, 4),               -- 5-period momentum

    -- Volume signals
    volume_ratio DECIMAL(10, 4),             -- Current vs average volume
    volume_momentum DECIMAL(10, 4),          -- Volume trend

    -- Volatility
    volatility_ratio DECIMAL(10, 4),         -- Current vs historical volatility
    atr_ratio DECIMAL(10, 4),                -- ATR relative to price

    -- Pattern recognition
    higher_highs INTEGER,                    -- Count of consecutive higher highs
    lower_lows INTEGER,                      -- Count of consecutive lower lows

    -- Market context (if available)
    market_trend_aligned BOOLEAN,            -- Does ticker align with market?
    sector_trend_aligned BOOLEAN,

    -- Target variable (for supervised learning)
    break_in_next_1 BOOLEAN,                 -- Did break occur in next 1 period?
    break_in_next_3 BOOLEAN,                 -- Did break occur in next 3 periods?
    break_in_next_5 BOOLEAN,                 -- Did break occur in next 5 periods?
    break_in_next_10 BOOLEAN,                -- Did break occur in next 10 periods?
    periods_until_break INTEGER,             -- Actual periods until next break

    created_at TIMESTAMPTZ DEFAULT NOW(),

    PRIMARY KEY (ticker, timestamp, timeframe)
);

SELECT create_hypertable('trend_break_features', 'timestamp',
    chunk_time_interval => INTERVAL '1 month',
    if_not_exists => TRUE
);

CREATE INDEX IF NOT EXISTS idx_tbf_ticker_tf
    ON trend_break_features (ticker, timeframe, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_tbf_trend_age
    ON trend_break_features (trend_age_ratio, timeframe);


-- ----------------------------------------------------------------------------
-- Table: trend_break_predictions
-- Stores model predictions for evaluation and serving
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS trend_break_predictions (
    id SERIAL,
    ticker VARCHAR(10) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    timeframe VARCHAR(10) NOT NULL,

    -- Prediction outputs
    break_probability_1 DECIMAL(6, 4),       -- P(break in next 1 period)
    break_probability_3 DECIMAL(6, 4),       -- P(break in next 3 periods)
    break_probability_5 DECIMAL(6, 4),       -- P(break in next 5 periods)
    break_probability_10 DECIMAL(6, 4),      -- P(break in next 10 periods)

    -- Predicted break type (if break is likely)
    predicted_break_type VARCHAR(10),        -- 'peak' or 'trough' or NULL
    confidence DECIMAL(6, 4),

    -- Model metadata
    model_version VARCHAR(50),
    model_name VARCHAR(100),
    features_hash VARCHAR(64),               -- Hash of input features for debugging

    -- Evaluation (filled in after actual outcome known)
    actual_break_in_1 BOOLEAN,
    actual_break_in_3 BOOLEAN,
    actual_break_in_5 BOOLEAN,
    actual_break_in_10 BOOLEAN,
    actual_break_type VARCHAR(10),

    created_at TIMESTAMPTZ DEFAULT NOW(),
    evaluated_at TIMESTAMPTZ,

    PRIMARY KEY (ticker, timestamp, timeframe)
);

SELECT create_hypertable('trend_break_predictions', 'timestamp',
    chunk_time_interval => INTERVAL '1 week',
    if_not_exists => TRUE
);

CREATE INDEX IF NOT EXISTS idx_tbp_ticker
    ON trend_break_predictions (ticker, timeframe, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_tbp_unevaluated
    ON trend_break_predictions (timeframe, timestamp)
    WHERE actual_break_in_5 IS NULL;


-- ============================================================================
-- TIMEFRAME MAPPING REFERENCE
-- ============================================================================
-- This shows how prediction timeframes map to data granularity
--
-- User wants prediction for:     Use price data at:    "Soon" means:
-- -------------------------     ------------------    -------------
-- Next hour                     5min or 10min bars    13-18 bars (~1-3 hours)
-- Next day                      1hour bars            13-18 bars (~2-3 days)
-- Next week                     daily bars            13-18 bars (~2-3 weeks)
-- Next month                    weekly bars           13-18 bars (~3-4 months)
--
-- The typical trend length of 13-18 periods comes from Fibonacci ratios
-- commonly used in technical analysis (13, 21 are Fibonacci numbers)
-- ============================================================================


-- ============================================================================
-- VIEWS FOR ANALYSIS
-- ============================================================================

-- View: Latest trend state per ticker/timeframe
CREATE OR REPLACE VIEW v_current_trend_state AS
SELECT DISTINCT ON (ticker, timeframe)
    ticker,
    timeframe,
    timestamp as last_break_time,
    break_type as last_break_type,
    direction_after as current_direction,
    price_at_break as last_break_price,
    periods_since_last_break,
    NOW() - timestamp as time_since_break
FROM trend_breaks
ORDER BY ticker, timeframe, timestamp DESC;


-- View: Trend break statistics by ticker
CREATE OR REPLACE VIEW v_trend_break_stats AS
SELECT
    ticker,
    timeframe,
    COUNT(*) as total_breaks,
    COUNT(*) FILTER (WHERE break_type = 'peak') as peaks,
    COUNT(*) FILTER (WHERE break_type = 'trough') as troughs,
    AVG(periods_since_last_break) as avg_trend_length,
    STDDEV(periods_since_last_break) as stddev_trend_length,
    MIN(timestamp) as first_break,
    MAX(timestamp) as last_break
FROM trend_breaks
GROUP BY ticker, timeframe;


-- View: Trend range distribution
CREATE OR REPLACE VIEW v_trend_range_distribution AS
SELECT
    timeframe,
    trend_direction,
    COUNT(*) as range_count,
    AVG(range_periods) as avg_periods,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY range_periods) as median_periods,
    MIN(range_periods) as min_periods,
    MAX(range_periods) as max_periods,
    AVG(ABS(price_change_pct)) as avg_price_change_pct
FROM trend_ranges
GROUP BY timeframe, trend_direction;


-- ============================================================================
-- GRANTS
-- ============================================================================

GRANT ALL PRIVILEGES ON trend_breaks TO trading;
GRANT ALL PRIVILEGES ON trend_ranges TO trading;
GRANT ALL PRIVILEGES ON trend_break_features TO trading;
GRANT ALL PRIVILEGES ON trend_break_predictions TO trading;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO trading;

GRANT SELECT ON trend_breaks TO app_user;
GRANT SELECT ON trend_ranges TO app_user;
GRANT SELECT ON trend_break_features TO app_user;
GRANT SELECT ON trend_break_predictions TO app_user;
GRANT SELECT ON v_current_trend_state TO app_user;
GRANT SELECT ON v_trend_break_stats TO app_user;
GRANT SELECT ON v_trend_range_distribution TO app_user;


-- ============================================================================
-- STORAGE ESTIMATES
-- ============================================================================
--
-- Trend breaks (assuming avg 1 break per 15 periods):
--   Daily (64 years): 461 tickers × (252×64/15) × 150 bytes ≈ 75 MB
--   Hourly (3 years): 460 tickers × (7×252×3/15) × 150 bytes ≈ 25 MB
--   5min (3 months): 461 tickers × (78×63/15) × 150 bytes ≈ 25 MB
--
-- Trend ranges: ~same as breaks
-- Trend features: Much larger (one row per period per ticker)
--   Daily: 461 × 252 × 64 × 200 bytes ≈ 1.5 GB
--   Hourly: 460 × 7 × 252 × 3 × 200 bytes ≈ 500 MB
--
-- Total: ~2-3 GB uncompressed
-- ============================================================================
