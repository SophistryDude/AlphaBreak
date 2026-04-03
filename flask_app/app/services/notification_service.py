"""
Notification Service
====================
Handles creating in-app notifications and sending emails via AWS SES.

Two modes:
1. Flask-context mode: Uses db_manager for API-triggered sends
2. Standalone mode: Accepts psycopg2 connection for DAG-triggered sends
"""

import os
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

SES_FROM_EMAIL = os.getenv('SES_FROM_EMAIL', 'noreply@alphabreak.vip')
SES_REGION = os.getenv('AWS_SES_REGION', 'us-east-1')
SES_SANDBOX_MODE = os.getenv('SES_SANDBOX_MODE', 'true').lower() == 'true'
NOTIFICATIONS_ENABLED = os.getenv('NOTIFICATIONS_ENABLED', 'true').lower() == 'true'

DEFAULT_EVENT_TYPES = [
    'trade_signal', 'stop_loss', 'take_profit', 'reversal_exit',
    'trim', 'new_position', 'earnings_1day', 'earnings_1week', 'portfolio_summary',
]

EVENT_TYPE_LABELS = {
    'trade_signal': 'Trade Signal',
    'stop_loss': 'Stop-Loss Triggered',
    'take_profit': 'Profit Taken',
    'reversal_exit': 'Reversal Exit',
    'trim': 'Position Trimmed',
    'new_position': 'New Position Opened',
    'earnings_1day': 'Earnings Tomorrow',
    'earnings_1week': 'Earnings This Week',
    'portfolio_summary': 'Daily Portfolio Summary',
}


def create_notification(conn, user_id, event_type, title, body, metadata=None):
    """Create an in-app notification for a user. Returns notification ID."""
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO notifications (user_id, event_type, title, body, metadata)
            VALUES (%s, %s, %s, %s, %s) RETURNING id
        """, (user_id, event_type, title, body, json.dumps(metadata) if metadata else None))
        notification_id = cur.fetchone()[0]
        conn.commit()
    return notification_id


def should_send_email(conn, user_id, event_type):
    """Check if a user wants email for this event type."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT email_enabled FROM notification_preferences
            WHERE user_id = %s AND event_type = %s
        """, (user_id, event_type))
        row = cur.fetchone()
        if row is None:
            return True  # Default to enabled if no preference set
        return row[0]


def get_all_users(conn):
    """Get all active users with email."""
    with conn.cursor() as cur:
        cur.execute("SELECT id, email, display_name FROM users WHERE is_active = TRUE")
        return [{'id': r[0], 'email': r[1], 'display_name': r[2]} for r in cur.fetchall()]


def get_users_watching_ticker(conn, ticker):
    """Get users who have this ticker in their watchlist."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT u.id, u.email, u.display_name
            FROM users u
            JOIN user_watchlists w ON u.id = w.user_id
            WHERE w.ticker = %s AND u.is_active = TRUE
        """, (ticker,))
        return [{'id': r[0], 'email': r[1], 'display_name': r[2]} for r in cur.fetchall()]


def send_notification(conn, event_type, title, body, metadata=None, ticker=None):
    """
    Send a notification to relevant users.
    If ticker is specified, only notifies users watching that ticker.
    Otherwise notifies all users.
    """
    if not NOTIFICATIONS_ENABLED:
        logger.info(f"Notifications disabled, skipping: {title}")
        return 0

    if ticker:
        users = get_users_watching_ticker(conn, ticker)
    else:
        users = get_all_users(conn)

    if not users:
        logger.info(f"No users to notify for: {title}")
        return 0

    sent_count = 0
    for user in users:
        try:
            # Create in-app notification
            notif_id = create_notification(conn, user['id'], event_type, title, body, metadata)

            # Check email preference and send
            if should_send_email(conn, user['id'], event_type):
                email_sent = _send_email_ses(
                    conn, notif_id, user['email'],
                    f"[AlphaBreak] {title}", body, metadata
                )
                if email_sent:
                    with conn.cursor() as cur:
                        cur.execute(
                            "UPDATE notifications SET email_sent = TRUE, email_sent_at = NOW() WHERE id = %s",
                            (notif_id,)
                        )
                        conn.commit()
            sent_count += 1
        except Exception as e:
            logger.error(f"Failed to notify user {user['id']}: {e}")

    logger.info(f"Sent '{event_type}' notification to {sent_count}/{len(users)} users: {title}")
    return sent_count


def _send_email_ses(conn, notification_id, to_email, subject, body, metadata=None):
    """Send an email via AWS SES. Returns True on success."""
    if SES_SANDBOX_MODE:
        logger.info(f"SES sandbox: would send to {to_email}: {subject}")
        _log_email(conn, notification_id, to_email, subject, 'sandbox', None)
        return False

    try:
        import boto3
        client = boto3.client('ses', region_name=SES_REGION)

        html_body = _build_email_html(subject, body, metadata)

        response = client.send_email(
            Source=SES_FROM_EMAIL,
            Destination={'ToAddresses': [to_email]},
            Message={
                'Subject': {'Data': subject, 'Charset': 'UTF-8'},
                'Body': {
                    'Html': {'Data': html_body, 'Charset': 'UTF-8'},
                    'Text': {'Data': body, 'Charset': 'UTF-8'},
                }
            }
        )
        ses_id = response.get('MessageId', '')
        _log_email(conn, notification_id, to_email, subject, 'sent', None, ses_id)
        return True

    except Exception as e:
        logger.error(f"SES send failed to {to_email}: {e}")
        _log_email(conn, notification_id, to_email, subject, 'failed', str(e))
        return False


def _log_email(conn, notification_id, to_email, subject, status, error=None, ses_id=None):
    """Log email delivery attempt."""
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO notification_email_log
                (notification_id, ses_message_id, to_email, subject, status, error_message)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (notification_id, ses_id, to_email, subject, status, error))
            conn.commit()
    except Exception as e:
        logger.debug(f"Email log failed: {e}")


def _build_email_html(title, body, metadata=None):
    """Generate branded HTML email."""
    ticker_info = ''
    if metadata:
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except (json.JSONDecodeError, TypeError):
                metadata = {}
        ticker = metadata.get('ticker', '')
        price = metadata.get('price', '')
        strength = metadata.get('signal_strength', '')
        if ticker:
            ticker_info = f'<p style="color:#4fc3f7;font-size:18px;margin:10px 0;"><strong>{ticker}</strong>'
            if price:
                ticker_info += f' @ ${price}'
            if strength:
                ticker_info += f' ({float(strength)*100:.0f}% confidence)'
            ticker_info += '</p>'

    return f"""
    <div style="background:#1a1a2e;padding:20px;font-family:Arial,sans-serif;">
        <div style="max-width:600px;margin:0 auto;background:#16213e;border-radius:8px;overflow:hidden;">
            <div style="background:#0f3460;padding:15px 20px;">
                <h1 style="color:#00d4aa;margin:0;font-size:20px;">AlphaBreak</h1>
            </div>
            <div style="padding:20px;color:#e0e0e0;">
                <h2 style="color:#ffffff;margin-top:0;">{title}</h2>
                {ticker_info}
                <p style="line-height:1.6;">{body}</p>
                <hr style="border-color:#2a2a4a;margin:20px 0;">
                <p style="font-size:12px;color:#888;">
                    <a href="https://alphabreak.vip" style="color:#4fc3f7;">Open AlphaBreak</a> |
                    <a href="https://alphabreak.vip/#settings" style="color:#888;">Manage notification preferences</a>
                </p>
            </div>
        </div>
    </div>
    """


# === Batch helpers for DAGs ===

def send_trade_signal_notifications(conn, signals):
    """Send notifications for trade signals from DAG."""
    count = 0
    for signal in signals:
        if signal.get('signal_strength', 0) < 0.80:
            continue
        ticker = signal.get('ticker', '?')
        strength = signal.get('signal_strength', 0)
        direction = 'Bullish' if 'bullish' in signal.get('signal_type', '') else 'Bearish'
        title = f"{direction} Signal: {ticker} ({strength:.0%})"
        body = f"A {direction.lower()} trend break signal has been detected for {ticker} with {strength:.0%} confidence."
        send_notification(conn, 'trade_signal', title, body,
                         metadata={'ticker': ticker, 'signal_strength': strength, 'direction': direction},
                         ticker=ticker)
        count += 1
    return count


def send_portfolio_event_notification(conn, event_type, details):
    """Send notification for a portfolio event (stop-loss, take-profit, etc.)."""
    ticker = details.get('ticker', '?')
    price = details.get('price', 0)
    label = EVENT_TYPE_LABELS.get(event_type, event_type)
    title = f"{label}: {ticker}"
    body_parts = [f"{label} for {ticker}"]
    if price:
        body_parts.append(f"at ${price:,.2f}")
    if details.get('pnl_pct'):
        body_parts.append(f"(P&L: {details['pnl_pct']:+.1%})")
    if details.get('reason'):
        body_parts.append(f"Reason: {details['reason']}")
    body = ' '.join(body_parts)
    return send_notification(conn, event_type, title, body, metadata=details, ticker=ticker)


def send_earnings_warnings(conn):
    """Check for upcoming earnings and notify users watching those tickers."""
    count = 0
    try:
        with conn.cursor() as cur:
            # 1-day warnings
            cur.execute("""
                SELECT DISTINCT ticker, date FROM earnings_calendar
                WHERE date = CURRENT_DATE + INTERVAL '1 day'
            """)
            for row in cur.fetchall():
                ticker, earn_date = row[0], row[1]
                title = f"Earnings Tomorrow: {ticker}"
                body = f"{ticker} reports earnings tomorrow ({earn_date}). Review your position."
                send_notification(conn, 'earnings_1day', title, body,
                                 metadata={'ticker': ticker, 'earnings_date': str(earn_date)},
                                 ticker=ticker)
                count += 1

            # 1-week warnings
            cur.execute("""
                SELECT DISTINCT ticker, date FROM earnings_calendar
                WHERE date = CURRENT_DATE + INTERVAL '7 days'
            """)
            for row in cur.fetchall():
                ticker, earn_date = row[0], row[1]
                title = f"Earnings in 1 Week: {ticker}"
                body = f"{ticker} reports earnings on {earn_date}. Consider your strategy."
                send_notification(conn, 'earnings_1week', title, body,
                                 metadata={'ticker': ticker, 'earnings_date': str(earn_date)},
                                 ticker=ticker)
                count += 1
    except Exception as e:
        logger.warning(f"Earnings warnings failed: {e}")

    return count


def send_daily_summary(conn, snapshot):
    """Send daily portfolio summary notification to all users."""
    total_value = snapshot.get('total_value', 0)
    daily_pnl = snapshot.get('daily_pnl', 0)
    total_pnl_pct = snapshot.get('total_pnl_pct', 0)
    positions = snapshot.get('positions', 0)

    title = f"Daily Summary: ${total_value:,.0f} ({total_pnl_pct:+.1%})"
    body = (
        f"Portfolio value: ${total_value:,.2f}\n"
        f"Daily P&L: ${daily_pnl:+,.2f}\n"
        f"Total return: {total_pnl_pct:+.2%}\n"
        f"Open positions: {positions}"
    )
    return send_notification(conn, 'portfolio_summary', title, body, metadata=snapshot)
