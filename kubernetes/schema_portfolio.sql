-- ============================================================================
-- Theoretical Portfolio Schema
-- ============================================================================
-- Paper trading portfolio to validate prediction model effectiveness.
-- Starting balance: $100,000 USD
-- Allocation: 75% long-term investing, 25% intra-day swing trading
-- ============================================================================

-- Portfolio account summary
CREATE TABLE IF NOT EXISTS portfolio_account (
    id SERIAL PRIMARY KEY,
    account_name VARCHAR(50) NOT NULL DEFAULT 'Theoretical Portfolio',
    starting_balance DECIMAL(15, 2) NOT NULL DEFAULT 100000.00,
    cash_balance DECIMAL(15, 2) NOT NULL DEFAULT 100000.00,
    long_term_allocation DECIMAL(5, 4) NOT NULL DEFAULT 0.75,  -- 75%
    swing_allocation DECIMAL(5, 4) NOT NULL DEFAULT 0.25,       -- 25%
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Portfolio holdings (current positions)
CREATE TABLE IF NOT EXISTS portfolio_holdings (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,
    holding_type VARCHAR(20) NOT NULL,          -- 'long_term' or 'swing'
    asset_type VARCHAR(20) NOT NULL DEFAULT 'stock',  -- 'stock', 'option', 'etf'

    -- Position details
    quantity DECIMAL(15, 6) NOT NULL,
    avg_cost_basis DECIMAL(12, 4) NOT NULL,
    current_price DECIMAL(12, 4),
    market_value DECIMAL(15, 2),

    -- P&L tracking
    unrealized_pnl DECIMAL(15, 2) DEFAULT 0,
    unrealized_pnl_pct DECIMAL(10, 4) DEFAULT 0,

    -- Options-specific fields
    option_type VARCHAR(4),                     -- 'call' or 'put'
    strike_price DECIMAL(12, 4),
    expiration_date DATE,

    -- Entry details
    entry_date TIMESTAMPTZ NOT NULL,
    entry_signal VARCHAR(50),                   -- 'trend_break', '13f_sentiment', etc.
    entry_rationale TEXT,

    -- Risk management
    stop_loss_price DECIMAL(12, 4),
    target_price DECIMAL(12, 4),

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(ticker, holding_type, asset_type, option_type, strike_price, expiration_date)
);

-- Transaction history
CREATE TABLE IF NOT EXISTS portfolio_transactions (
    id SERIAL PRIMARY KEY,
    transaction_id UUID NOT NULL DEFAULT gen_random_uuid(),

    -- Transaction details
    ticker VARCHAR(10) NOT NULL,
    action VARCHAR(20) NOT NULL,                -- 'buy', 'sell', 'buy_to_open', 'sell_to_close'
    holding_type VARCHAR(20) NOT NULL,          -- 'long_term' or 'swing'
    asset_type VARCHAR(20) NOT NULL DEFAULT 'stock',

    quantity DECIMAL(15, 6) NOT NULL,
    price DECIMAL(12, 4) NOT NULL,
    total_value DECIMAL(15, 2) NOT NULL,
    commission DECIMAL(10, 2) DEFAULT 0,

    -- Options-specific
    option_type VARCHAR(4),
    strike_price DECIMAL(12, 4),
    expiration_date DATE,

    -- Signal that triggered the trade
    signal_source VARCHAR(50),                  -- 'dag_trend_break', 'dag_13f', 'manual'
    signal_details JSONB,

    -- P&L (for sell transactions)
    realized_pnl DECIMAL(15, 2),
    realized_pnl_pct DECIMAL(10, 4),

    -- Metadata
    executed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Daily performance snapshots
CREATE TABLE IF NOT EXISTS portfolio_performance (
    id SERIAL PRIMARY KEY,
    snapshot_date DATE NOT NULL,

    -- Account values
    total_value DECIMAL(15, 2) NOT NULL,
    cash_balance DECIMAL(15, 2) NOT NULL,
    holdings_value DECIMAL(15, 2) NOT NULL,

    -- Allocation breakdown
    long_term_value DECIMAL(15, 2) DEFAULT 0,
    swing_value DECIMAL(15, 2) DEFAULT 0,

    -- Daily P&L
    daily_pnl DECIMAL(15, 2) DEFAULT 0,
    daily_pnl_pct DECIMAL(10, 4) DEFAULT 0,

    -- Cumulative metrics
    total_pnl DECIMAL(15, 2) DEFAULT 0,
    total_pnl_pct DECIMAL(10, 4) DEFAULT 0,

    -- Risk metrics
    max_drawdown DECIMAL(10, 4),
    sharpe_ratio DECIMAL(10, 4),
    win_rate DECIMAL(5, 4),

    -- Position counts
    open_positions INTEGER DEFAULT 0,
    long_term_positions INTEGER DEFAULT 0,
    swing_positions INTEGER DEFAULT 0,

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(snapshot_date)
);

-- Watchlist for re-entry opportunities (exited positions we want to buy back)
CREATE TABLE IF NOT EXISTS portfolio_watchlist (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,
    sector VARCHAR(50),

    -- Exit details
    exit_date TIMESTAMPTZ NOT NULL,
    exit_price DECIMAL(12, 4) NOT NULL,
    exit_reason VARCHAR(50),                   -- 'trend_break_bearish', 'stop_loss', 'manual'
    realized_pnl DECIMAL(15, 2),

    -- Re-entry criteria
    target_reentry_price DECIMAL(12, 4),       -- Price we'd like to buy back at
    reentry_signal_type VARCHAR(50),           -- 'trend_break_bullish', '13f_buy'
    min_signal_strength DECIMAL(6, 4) DEFAULT 0.80,

    -- Status
    status VARCHAR(20) DEFAULT 'watching',     -- 'watching', 'reentry_triggered', 'closed'
    reentry_date TIMESTAMPTZ,
    reentry_price DECIMAL(12, 4),

    -- Original position info
    original_quantity DECIMAL(15, 6),
    original_cost_basis DECIMAL(12, 4),
    holding_type VARCHAR(20) DEFAULT 'long_term',

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(ticker, exit_date)
);

-- Covered calls written against long positions
CREATE TABLE IF NOT EXISTS portfolio_covered_calls (
    id SERIAL PRIMARY KEY,
    call_id UUID NOT NULL DEFAULT gen_random_uuid(),

    -- Underlying position
    ticker VARCHAR(10) NOT NULL,
    underlying_quantity DECIMAL(15, 6) NOT NULL,  -- Shares covered (must be 100x contracts)

    -- Call details
    contracts INTEGER NOT NULL,                   -- Number of contracts (1 contract = 100 shares)
    strike_price DECIMAL(12, 4) NOT NULL,
    expiration_date DATE NOT NULL,
    premium_received DECIMAL(12, 4) NOT NULL,     -- Premium per share
    total_premium DECIMAL(15, 2) NOT NULL,        -- Total premium collected

    -- Status tracking
    status VARCHAR(20) DEFAULT 'open',            -- 'open', 'expired', 'assigned', 'bought_back'
    close_date TIMESTAMPTZ,
    close_price DECIMAL(12, 4),                   -- Price if bought back
    close_reason VARCHAR(50),                     -- 'expired_worthless', 'assigned', 'bought_back'

    -- P&L
    realized_pnl DECIMAL(15, 2),                  -- Profit from the call itself

    -- Metadata
    opened_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Trade signals queue (for DAG to process)
CREATE TABLE IF NOT EXISTS portfolio_signals (
    id SERIAL PRIMARY KEY,
    signal_id UUID NOT NULL DEFAULT gen_random_uuid(),

    -- Signal details
    ticker VARCHAR(10) NOT NULL,
    signal_type VARCHAR(50) NOT NULL,           -- 'trend_break_bullish', 'trend_break_bearish', '13f_buy', etc.
    signal_strength DECIMAL(6, 4),              -- 0.0 to 1.0

    -- Suggested action
    suggested_action VARCHAR(20) NOT NULL,      -- 'buy', 'sell', 'hold'
    holding_type VARCHAR(20) NOT NULL,          -- 'long_term' or 'swing'
    asset_type VARCHAR(20) DEFAULT 'stock',

    -- Price info at signal time
    signal_price DECIMAL(12, 4),

    -- Signal source data
    source_report_id UUID,
    source_data JSONB,

    -- Processing status
    status VARCHAR(20) DEFAULT 'pending',       -- 'pending', 'processed', 'rejected', 'expired'
    processed_at TIMESTAMPTZ,
    rejection_reason TEXT,

    -- Metadata
    generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_holdings_ticker ON portfolio_holdings (ticker);
CREATE INDEX IF NOT EXISTS idx_holdings_type ON portfolio_holdings (holding_type);
CREATE INDEX IF NOT EXISTS idx_transactions_ticker ON portfolio_transactions (ticker);
CREATE INDEX IF NOT EXISTS idx_transactions_date ON portfolio_transactions (executed_at DESC);
CREATE INDEX IF NOT EXISTS idx_performance_date ON portfolio_performance (snapshot_date DESC);
CREATE INDEX IF NOT EXISTS idx_signals_status ON portfolio_signals (status, generated_at DESC);
CREATE INDEX IF NOT EXISTS idx_signals_ticker ON portfolio_signals (ticker, status);
CREATE INDEX IF NOT EXISTS idx_watchlist_ticker ON portfolio_watchlist (ticker, status);
CREATE INDEX IF NOT EXISTS idx_watchlist_status ON portfolio_watchlist (status);
CREATE INDEX IF NOT EXISTS idx_covered_calls_ticker ON portfolio_covered_calls (ticker, status);
CREATE INDEX IF NOT EXISTS idx_covered_calls_expiration ON portfolio_covered_calls (expiration_date, status);

-- Initialize default account if not exists
INSERT INTO portfolio_account (account_name, starting_balance, cash_balance)
SELECT 'Theoretical Portfolio', 100000.00, 100000.00
WHERE NOT EXISTS (SELECT 1 FROM portfolio_account LIMIT 1);

-- Grants
GRANT ALL PRIVILEGES ON portfolio_account TO trading;
GRANT ALL PRIVILEGES ON portfolio_holdings TO trading;
GRANT ALL PRIVILEGES ON portfolio_transactions TO trading;
GRANT ALL PRIVILEGES ON portfolio_performance TO trading;
GRANT ALL PRIVILEGES ON portfolio_signals TO trading;
GRANT ALL PRIVILEGES ON portfolio_watchlist TO trading;
GRANT ALL PRIVILEGES ON portfolio_covered_calls TO trading;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO trading;
