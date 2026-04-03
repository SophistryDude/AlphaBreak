-- Trade Journal Schema
-- ====================
-- Stores user trade journal entries with free and premium features.
-- Free: notes, P&L, sharing, chart snapshots, AI scoring
-- Paid: tags, pre-trade plans, post-trade reviews, pattern detection

CREATE TABLE IF NOT EXISTS trade_journal (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    transaction_id UUID,  -- nullable link to portfolio_transactions
    -- Trade data
    ticker VARCHAR(10) NOT NULL,
    trade_date DATE NOT NULL,
    direction VARCHAR(10) NOT NULL DEFAULT 'long',  -- 'long' or 'short'
    entry_price DECIMAL(12,4),
    exit_price DECIMAL(12,4),
    quantity DECIMAL(12,4),
    realized_pnl DECIMAL(12,2),
    realized_pnl_pct DECIMAL(10,4),
    -- Free: User notes
    entry_notes TEXT,
    exit_notes TEXT,
    lessons_learned TEXT,
    -- Paid: Tags
    tags TEXT[],
    -- Paid/Trial: Pre-trade plan
    pre_trade_plan JSONB,
    -- Paid/Trial: Post-trade review
    post_trade_review JSONB,
    -- Free: AI trade scoring
    ai_score JSONB,
    -- Paid/Trial: Pattern recognition
    pattern_data JSONB,
    -- Free: Chart snapshots (base64)
    chart_snapshot_entry TEXT,
    chart_snapshot_exit TEXT,
    -- Free: Sharing
    is_public BOOLEAN NOT NULL DEFAULT FALSE,
    -- Auto-imported context
    signal_source VARCHAR(50),
    signal_details JSONB,
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_journal_user_id ON trade_journal(user_id);
CREATE INDEX IF NOT EXISTS idx_journal_user_date ON trade_journal(user_id, trade_date DESC);
CREATE INDEX IF NOT EXISTS idx_journal_ticker ON trade_journal(ticker);
CREATE INDEX IF NOT EXISTS idx_journal_public ON trade_journal(is_public, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_journal_tags ON trade_journal USING GIN(tags);
CREATE INDEX IF NOT EXISTS idx_journal_transaction ON trade_journal(transaction_id);

-- Auto-update updated_at trigger
CREATE TRIGGER update_trade_journal_updated_at
    BEFORE UPDATE ON trade_journal
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Permissions
GRANT ALL ON trade_journal TO trading;
GRANT USAGE, SELECT ON SEQUENCE trade_journal_id_seq TO trading;
