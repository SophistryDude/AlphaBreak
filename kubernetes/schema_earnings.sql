-- ============================================================================
-- Earnings Cache Schema
-- ============================================================================
-- Caches earnings calendar data fetched from yfinance to avoid slow re-fetches.
-- Two tables:
--   1. earnings_calendar  — per-ticker earnings dates + EPS data
--   2. earnings_cache_meta — tracks when each ticker was last refreshed
-- ============================================================================

-- Earnings dates per ticker (one row per earnings date per ticker)
CREATE TABLE IF NOT EXISTS earnings_calendar (
    id              SERIAL PRIMARY KEY,
    ticker          VARCHAR(10)  NOT NULL,
    earnings_date   DATE         NOT NULL,
    eps_estimate    NUMERIC(10,2),
    eps_actual      NUMERIC(10,2),
    surprise_pct    NUMERIC(10,2),
    is_upcoming     BOOLEAN      DEFAULT TRUE,
    fetched_at      TIMESTAMP    NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_earnings_ticker_date UNIQUE (ticker, earnings_date)
);

CREATE INDEX IF NOT EXISTS idx_ec_ticker      ON earnings_calendar (ticker);
CREATE INDEX IF NOT EXISTS idx_ec_date        ON earnings_calendar (earnings_date);
CREATE INDEX IF NOT EXISTS idx_ec_upcoming    ON earnings_calendar (is_upcoming, earnings_date);
CREATE INDEX IF NOT EXISTS idx_ec_fetched     ON earnings_calendar (fetched_at);

-- Cache metadata — tracks when we last refreshed data for each ticker
CREATE TABLE IF NOT EXISTS earnings_cache_meta (
    ticker          VARCHAR(10)  PRIMARY KEY,
    last_fetched    TIMESTAMP    NOT NULL DEFAULT NOW()
);

-- Refresh policy: consider data stale after 6 hours
-- Queries should filter: WHERE last_fetched > NOW() - INTERVAL '6 hours'
