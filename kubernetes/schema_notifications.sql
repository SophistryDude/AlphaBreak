-- Notification System Schema
-- ===========================
-- Tables for in-app notifications, email delivery, and user preferences.

-- 1. User notification preferences (per event type)
CREATE TABLE IF NOT EXISTS notification_preferences (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL,
    -- Event types:
    --   trade_signal, stop_loss, take_profit, reversal_exit,
    --   trim, new_position, earnings_1day, earnings_1week, portfolio_summary
    email_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    push_enabled BOOLEAN NOT NULL DEFAULT FALSE,  -- future mobile push
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(user_id, event_type)
);

CREATE INDEX IF NOT EXISTS idx_notif_prefs_user ON notification_preferences(user_id);

-- 2. Notifications (in-app notification center)
CREATE TABLE IF NOT EXISTS notifications (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL,
    title VARCHAR(200) NOT NULL,
    body TEXT NOT NULL,
    metadata JSONB,
    is_read BOOLEAN NOT NULL DEFAULT FALSE,
    email_sent BOOLEAN NOT NULL DEFAULT FALSE,
    email_sent_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_notifications_user_unread
    ON notifications(user_id, is_read, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_notifications_user_date
    ON notifications(user_id, created_at DESC);

-- 3. Email delivery log (SES tracking)
CREATE TABLE IF NOT EXISTS notification_email_log (
    id SERIAL PRIMARY KEY,
    notification_id INTEGER REFERENCES notifications(id) ON DELETE SET NULL,
    ses_message_id VARCHAR(100),
    to_email VARCHAR(255) NOT NULL,
    subject VARCHAR(200) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'sent',
    error_message TEXT,
    sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_email_log_notification ON notification_email_log(notification_id);
CREATE INDEX IF NOT EXISTS idx_email_log_status ON notification_email_log(status, sent_at DESC);

-- Grant permissions
GRANT ALL ON notification_preferences TO trading;
GRANT ALL ON notifications TO trading;
GRANT ALL ON notification_email_log TO trading;
GRANT USAGE, SELECT ON SEQUENCE notification_preferences_id_seq TO trading;
GRANT USAGE, SELECT ON SEQUENCE notifications_id_seq TO trading;
GRANT USAGE, SELECT ON SEQUENCE notification_email_log_id_seq TO trading;

-- Seed default event types (for reference)
-- INSERT INTO notification_preferences (user_id, event_type) VALUES
--   (1, 'trade_signal'), (1, 'stop_loss'), (1, 'take_profit'),
--   (1, 'reversal_exit'), (1, 'trim'), (1, 'new_position'),
--   (1, 'earnings_1day'), (1, 'earnings_1week'), (1, 'portfolio_summary');
