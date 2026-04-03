"""
Trade Journal Service
=====================
Business logic for trade journal: CRUD, auto-import, AI scoring, premium gating.
"""

import json
import logging
import math
from datetime import datetime, date

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# Premium Gating
# ──────────────────────────────────────────────────────────────

TRIAL_FEATURES = {
    'pre_trade_plan': 'trial_pre_trade_plan_used',
    'post_trade_review': 'trial_post_trade_review_used',
    'pattern_recognition': 'trial_pattern_recognition_used',
}


def check_premium_or_trial(user_id, feature_name, is_premium, prefs):
    """Check if user can access a premium feature (premium or unused trial)."""
    if is_premium:
        return {'allowed': True, 'is_trial': False, 'trial_used': False}

    trial_key = TRIAL_FEATURES.get(feature_name)
    if not trial_key:
        return {'allowed': False, 'is_trial': False, 'trial_used': True}

    trial_used = prefs.get(trial_key, '') == 'true'
    if trial_used:
        return {'allowed': False, 'is_trial': False, 'trial_used': True}

    return {'allowed': True, 'is_trial': True, 'trial_used': False}


def mark_trial_used(user_id, feature_name):
    """Mark a trial as used."""
    from app.utils.database import set_user_preference
    trial_key = TRIAL_FEATURES.get(feature_name)
    if trial_key:
        set_user_preference(user_id, trial_key, 'true')


# ──────────────────────────────────────────────────────────────
# CRUD
# ──────────────────────────────────────────────────────────────

def create_entry(db_manager, user_id, data):
    """Create a journal entry."""
    query = """
        INSERT INTO trade_journal
        (user_id, transaction_id, ticker, trade_date, direction, entry_price, exit_price,
         quantity, realized_pnl, realized_pnl_pct, entry_notes, exit_notes, lessons_learned,
         signal_source, signal_details, is_public)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    """
    params = (
        user_id, data.get('transaction_id'), data.get('ticker', '').upper(),
        data.get('trade_date', date.today().isoformat()), data.get('direction', 'long'),
        data.get('entry_price'), data.get('exit_price'),
        data.get('quantity'), data.get('realized_pnl'), data.get('realized_pnl_pct'),
        data.get('entry_notes', ''), data.get('exit_notes', ''), data.get('lessons_learned', ''),
        data.get('signal_source'), json.dumps(data.get('signal_details')) if data.get('signal_details') else None,
        data.get('is_public', False),
    )
    try:
        with db_manager.get_cursor(commit=True) as cur:
            cur.execute(query, params)
            entry_id = cur.fetchone()[0]
        return {'success': True, 'id': entry_id}
    except Exception as e:
        logger.error(f"Create journal entry failed: {e}")
        return {'success': False, 'error': str(e)}


def get_entry(db_manager, user_id, entry_id):
    """Get a single journal entry (ownership check)."""
    rows = db_manager.execute_query(
        "SELECT * FROM trade_journal WHERE id = %s AND user_id = %s", (entry_id, user_id)
    )
    if not rows or not rows[0]:
        return None
    return _row_to_dict(rows[0])


def list_entries(db_manager, user_id, page=1, per_page=20, filters=None):
    """List journal entries with pagination and optional filters."""
    filters = filters or {}
    query = "SELECT * FROM trade_journal WHERE user_id = %s"
    params = [user_id]

    if filters.get('ticker'):
        query += " AND ticker = %s"
        params.append(filters['ticker'].upper())
    if filters.get('direction'):
        query += " AND direction = %s"
        params.append(filters['direction'])
    if filters.get('pnl') == 'win':
        query += " AND realized_pnl > 0"
    elif filters.get('pnl') == 'loss':
        query += " AND realized_pnl < 0"
    if filters.get('date_from'):
        query += " AND trade_date >= %s"
        params.append(filters['date_from'])
    if filters.get('date_to'):
        query += " AND trade_date <= %s"
        params.append(filters['date_to'])
    if filters.get('tags') and isinstance(filters['tags'], list):
        query += " AND tags && %s::text[]"
        params.append(filters['tags'])

    # Count total
    count_rows = db_manager.execute_query(
        query.replace("SELECT *", "SELECT COUNT(*)"), tuple(params)
    )
    total = count_rows[0][0] if count_rows and count_rows[0] else 0

    query += " ORDER BY trade_date DESC LIMIT %s OFFSET %s"
    params.extend([per_page, (page - 1) * per_page])

    rows = db_manager.execute_query(query, tuple(params))
    entries = [_row_to_dict(r) for r in (rows or [])]

    return {'entries': entries, 'total': total, 'page': page, 'per_page': per_page}


def update_entry(db_manager, user_id, entry_id, data):
    """Update a journal entry."""
    allowed_fields = [
        'entry_notes', 'exit_notes', 'lessons_learned', 'exit_price',
        'realized_pnl', 'realized_pnl_pct', 'is_public',
        'chart_snapshot_entry', 'chart_snapshot_exit',
    ]
    updates = []
    params = []
    for field in allowed_fields:
        if field in data:
            updates.append(f"{field} = %s")
            params.append(data[field])

    if not updates:
        return {'success': False, 'error': 'No fields to update'}

    params.extend([entry_id, user_id])
    try:
        with db_manager.get_cursor(commit=True) as cur:
            cur.execute(
                f"UPDATE trade_journal SET {', '.join(updates)} WHERE id = %s AND user_id = %s",
                tuple(params)
            )
            if cur.rowcount == 0:
                return {'success': False, 'error': 'Entry not found'}
        return {'success': True}
    except Exception as e:
        logger.error(f"Update journal entry failed: {e}")
        return {'success': False, 'error': str(e)}


def delete_entry(db_manager, user_id, entry_id):
    """Delete a journal entry."""
    try:
        with db_manager.get_cursor(commit=True) as cur:
            cur.execute("DELETE FROM trade_journal WHERE id = %s AND user_id = %s", (entry_id, user_id))
            if cur.rowcount == 0:
                return {'success': False, 'error': 'Entry not found'}
        return {'success': True}
    except Exception as e:
        return {'success': False, 'error': str(e)}


# ──────────────────────────────────────────────────────────────
# Shared Journal
# ──────────────────────────────────────────────────────────────

def list_public_entries(db_manager, page=1, per_page=20):
    """List public journal entries from all users."""
    count_rows = db_manager.execute_query(
        "SELECT COUNT(*) FROM trade_journal WHERE is_public = TRUE"
    )
    total = count_rows[0][0] if count_rows and count_rows[0] else 0

    rows = db_manager.execute_query("""
        SELECT j.*, u.display_name, u.public_id as author_id
        FROM trade_journal j
        JOIN users u ON j.user_id = u.id
        WHERE j.is_public = TRUE
        ORDER BY j.created_at DESC
        LIMIT %s OFFSET %s
    """, (per_page, (page - 1) * per_page))

    entries = []
    for r in (rows or []):
        entry = _row_to_dict(r)
        # Add author info (columns appended after trade_journal columns)
        entry['author_name'] = r[-2] if len(r) > 20 else 'Anonymous'
        entry['author_id'] = str(r[-1]) if len(r) > 21 else None
        entries.append(entry)

    return {'entries': entries, 'total': total, 'page': page}


# ──────────────────────────────────────────────────────────────
# Auto-Import
# ──────────────────────────────────────────────────────────────

def import_trades(db_manager, user_id):
    """Import sell/close transactions with matched buy prices and trend break context."""
    # Get sell transactions not yet in journal
    sells = db_manager.execute_query("""
        SELECT t.transaction_id, t.ticker, t.action, t.holding_type, t.asset_type,
               t.quantity, t.price, t.total_value, t.realized_pnl, t.realized_pnl_pct,
               t.signal_source, t.signal_details, t.executed_at, t.option_type
        FROM portfolio_transactions t
        WHERE t.action IN ('sell', 'sell_to_close')
          AND t.realized_pnl IS NOT NULL
          AND t.transaction_id NOT IN (
              SELECT transaction_id FROM trade_journal WHERE user_id = %s AND transaction_id IS NOT NULL
          )
        ORDER BY t.executed_at DESC
        LIMIT 50
    """, (user_id,))

    # Get all buy transactions for entry price lookup
    buys = db_manager.execute_query("""
        SELECT ticker, action, asset_type, price, signal_source, signal_details, executed_at
        FROM portfolio_transactions
        WHERE action IN ('buy', 'buy_to_open')
        ORDER BY executed_at DESC
    """)

    # Build lookup: ticker -> most recent buy before each sell
    buy_lookup = {}
    for b in (buys or []):
        ticker = b[0]
        if ticker not in buy_lookup:
            buy_lookup[ticker] = []
        buy_details = b[5] if isinstance(b[5], dict) else (json.loads(b[5]) if b[5] else {})
        buy_lookup[ticker].append({
            'price': float(b[3]) if b[3] else None,
            'signal_source': b[4],
            'signal_details': buy_details,
            'executed_at': b[6],
        })

    imported = 0
    for r in (sells or []):
        ticker = r[1]
        exit_price = float(r[6]) if r[6] else None
        sell_date = r[12]
        direction = 'long' if r[2] == 'sell' else 'short'
        sell_details = r[11] if isinstance(r[11], dict) else (json.loads(r[11]) if r[11] else {})

        # Find the matching buy (most recent buy for this ticker before the sell)
        entry_price = None
        buy_signal_source = None
        buy_details = {}
        for buy in buy_lookup.get(ticker, []):
            if buy['executed_at'] and sell_date and buy['executed_at'] < sell_date:
                entry_price = buy['price']
                buy_signal_source = buy['signal_source']
                buy_details = buy['signal_details'] or {}
                break

        if entry_price is None:
            # Fallback: compute from P&L
            if exit_price and r[9]:  # realized_pnl_pct
                pnl_pct = float(r[9])
                if pnl_pct != 0 and abs(1 + pnl_pct) > 0.01:
                    entry_price = exit_price / (1 + pnl_pct)

        # Look up nearest trend break for this ticker around the trade date
        break_price = None
        break_timestamp = None
        if sell_date:
            breaks = db_manager.execute_query("""
                SELECT price_at_break, timestamp, magnitude, volume_ratio
                FROM trend_breaks
                WHERE ticker = %s AND timeframe = 'daily'
                  AND timestamp BETWEEN %s - INTERVAL '7 days' AND %s
                ORDER BY ABS(EXTRACT(epoch FROM timestamp - %s))
                LIMIT 1
            """, (ticker, sell_date, sell_date, sell_date))
            if breaks and breaks[0]:
                break_price = float(breaks[0][0]) if breaks[0][0] else None
                break_timestamp = breaks[0][1].isoformat() if breaks[0][1] else None

        # Merge signal details from buy + sell + trend break
        merged_details = {**buy_details, **sell_details}
        if break_price:
            merged_details['break_price'] = break_price
        if break_timestamp:
            merged_details['generated_at'] = break_timestamp
        if entry_price:
            merged_details['entry_price'] = entry_price
        if buy_signal_source:
            merged_details['buy_signal'] = buy_signal_source

        asset_label = r[4] or 'stock'
        option_label = f" {r[13]}" if r[13] else ''

        result = create_entry(db_manager, user_id, {
            'transaction_id': str(r[0]),
            'ticker': ticker,
            'trade_date': sell_date.date().isoformat() if sell_date else date.today().isoformat(),
            'direction': direction,
            'entry_price': entry_price,
            'exit_price': exit_price,
            'quantity': float(r[5]) if r[5] else None,
            'realized_pnl': float(r[8]) if r[8] else None,
            'realized_pnl_pct': float(r[9]) if r[9] else None,
            'signal_source': r[10],
            'signal_details': merged_details,
            'entry_notes': f"Entry: {buy_signal_source or 'manual'} @ ${entry_price:.2f}" if entry_price else f"Auto-imported {r[2]} {ticker}",
        })
        if result.get('success'):
            imported += 1

    return {'imported': imported}


# ──────────────────────────────────────────────────────────────
# AI Trade Scoring (Free)
# ──────────────────────────────────────────────────────────────

def compute_ai_score(db_manager, user_id, entry_id):
    """Compute AI trade score for a journal entry using trade data + trend breaks."""
    entry = get_entry(db_manager, user_id, entry_id)
    if not entry:
        return {'success': False, 'error': 'Entry not found'}

    entry_price = float(entry.get('entry_price') or 0)
    exit_price = float(entry.get('exit_price') or 0)
    ticker = entry.get('ticker', '')
    trade_date = entry.get('trade_date')

    signal_details = entry.get('signal_details') or {}
    if isinstance(signal_details, str):
        try:
            signal_details = json.loads(signal_details)
        except (json.JSONDecodeError, TypeError):
            signal_details = {}

    # Try to get break price from signal_details, then query trend_breaks
    break_price = signal_details.get('break_price') or signal_details.get('price_at_break') or signal_details.get('signal_price')

    if not break_price and ticker and trade_date:
        # Query nearest daily trend break for this ticker around trade date
        try:
            td = trade_date if isinstance(trade_date, date) else datetime.fromisoformat(str(trade_date)).date()
            breaks = db_manager.execute_query("""
                SELECT price_at_break, timestamp, magnitude, volume_ratio
                FROM trend_breaks
                WHERE ticker = %s AND timeframe = 'daily'
                  AND timestamp BETWEEN %s - INTERVAL '14 days' AND %s + INTERVAL '3 days'
                ORDER BY ABS(EXTRACT(epoch FROM timestamp - %s::timestamp))
                LIMIT 1
            """, (ticker, td, td, td))
            if breaks and breaks[0] and breaks[0][0]:
                break_price = float(breaks[0][0])
                if not signal_details.get('generated_at') and breaks[0][1]:
                    signal_details['generated_at'] = breaks[0][1].isoformat()
        except Exception as e:
            logger.debug(f"Trend break lookup for AI score failed: {e}")

    # Detect if this is an options trade (premium is much smaller than break price)
    is_options = False
    if break_price and entry_price and float(break_price) > 0:
        ratio = entry_price / float(break_price)
        is_options = ratio < 0.15  # Option premiums are typically <15% of stock price

    signal_src = entry.get('signal_source', '')

    # --- Entry Score (0-100) ---
    if is_options:
        # For options: score based on premium efficiency and timing
        # Good entry = low premium relative to stock price (more leverage)
        premium_pct = entry_price / float(break_price)
        if premium_pct <= 0.02:
            entry_score = 92  # Very cheap premium = great entry
        elif premium_pct <= 0.03:
            entry_score = 85
        elif premium_pct <= 0.05:
            entry_score = 75
        elif premium_pct <= 0.08:
            entry_score = 60
        else:
            entry_score = 45  # Expensive premium
    elif break_price and entry_price and float(break_price) > 0:
        # For stocks: how close to break price
        pct_diff = abs(entry_price - float(break_price)) / float(break_price)
        entry_score = max(0, min(100, int(100 - pct_diff * 1500)))
    elif entry_price and exit_price:
        entry_score = 65 if exit_price > entry_price else 35
    else:
        entry_score = 50

    # --- Exit Score (0-100): based on realized P&L quality ---
    realized_pnl_pct = float(entry.get('realized_pnl_pct') or 0)

    if is_options:
        # Options have bigger swings — calibrate differently
        if realized_pnl_pct > 1.00:
            exit_score = 97  # 100%+ gain on options = exceptional
        elif realized_pnl_pct > 0.50:
            exit_score = 90
        elif realized_pnl_pct > 0.20:
            exit_score = 78
        elif realized_pnl_pct > 0:
            exit_score = 62
        elif realized_pnl_pct > -0.20:
            exit_score = 42
        elif realized_pnl_pct > -0.40:
            exit_score = 25
        else:
            exit_score = 12  # Hit or exceeded stop loss
    else:
        # Stocks
        if realized_pnl_pct > 0.15:
            exit_score = 95
        elif realized_pnl_pct > 0.10:
            exit_score = 88
        elif realized_pnl_pct > 0.05:
            exit_score = 78
        elif realized_pnl_pct > 0.02:
            exit_score = 68
        elif realized_pnl_pct > 0:
            exit_score = 58
        elif realized_pnl_pct > -0.03:
            exit_score = 42
        elif realized_pnl_pct > -0.07:
            exit_score = 28
        else:
            exit_score = 12

    # --- Timing Grade (A-F): signal-to-entry delay ---
    timing_grade = 'B'  # Default to B if no signal timestamp
    generated_at = signal_details.get('generated_at') or signal_details.get('timestamp')
    days_delay = None
    if generated_at and trade_date:
        try:
            if isinstance(generated_at, str):
                signal_date = datetime.fromisoformat(generated_at.replace('Z', '+00:00')).date()
            else:
                signal_date = generated_at.date() if hasattr(generated_at, 'date') else generated_at
            trade_d = trade_date if isinstance(trade_date, date) else datetime.fromisoformat(str(trade_date)).date()
            days_delay = abs((trade_d - signal_date).days)
            grades = {0: 'A', 1: 'A', 2: 'B', 3: 'B', 4: 'C', 5: 'C', 6: 'D', 7: 'D'}
            timing_grade = grades.get(days_delay, 'F') if days_delay <= 14 else 'F'
        except Exception:
            pass

    # --- Suggestions ---
    suggestions = []

    if realized_pnl_pct < -0.40:
        suggestions.append("Large loss — review position sizing and stop-loss discipline")
    elif realized_pnl_pct < -0.07:
        suggestions.append("Consider a tighter stop-loss to limit downside")

    if timing_grade in ('D', 'F'):
        suggestions.append("Act faster on signals — same-day entry captures more of the move")

    if entry_score < 55 and break_price:
        suggestions.append(f"Entry was far from break price (${float(break_price):.2f}) — wait for better entry")

    if exit_score >= 85:
        suggestions.append("Excellent exit timing — continue this approach")

    if realized_pnl_pct > 0.50:
        suggestions.append("Outstanding winner — document what made this setup work")
    elif realized_pnl_pct > 0.10:
        suggestions.append("Strong winner — consider scaling into similar setups")

    signal_src = entry.get('signal_source', '')
    if 'theta_decay' in signal_src:
        suggestions.append("Theta decay exit — consider shorter DTE or more OTM strikes")
    if 'reversal' in signal_src:
        suggestions.append("Reversal exit — the trend broke against you; review entry thesis")
    if 'take_profit' in signal_src:
        suggestions.append("Profit taken on volume decline — good discipline on exits")
    if 'trim' in signal_src:
        suggestions.append("Position trimmed — multi-timeframe confirmation held the core position")

    if not suggestions:
        suggestions.append("Solid trade execution overall")

    overall = int((entry_score + exit_score) / 2)
    overall_grade = 'A' if overall >= 85 else 'B' if overall >= 70 else 'C' if overall >= 55 else 'D' if overall >= 40 else 'F'

    ai_score = {
        'entry_score': entry_score,
        'exit_score': exit_score,
        'timing_grade': timing_grade,
        'overall_score': overall,
        'overall_grade': overall_grade,
        'suggestions': suggestions,
        'computed_at': datetime.now().isoformat(),
    }

    # Save to entry
    try:
        with db_manager.get_cursor(commit=True) as cur:
            cur.execute(
                "UPDATE trade_journal SET ai_score = %s WHERE id = %s AND user_id = %s",
                (json.dumps(ai_score), entry_id, user_id)
            )
    except Exception as e:
        logger.error(f"Failed to save AI score: {e}")

    return {'success': True, 'ai_score': ai_score}


# ──────────────────────────────────────────────────────────────
# Premium: Tags & Stats
# ──────────────────────────────────────────────────────────────

def get_user_tags(db_manager, user_id):
    """Get all distinct tags for a user."""
    rows = db_manager.execute_query(
        "SELECT DISTINCT unnest(tags) as tag FROM trade_journal WHERE user_id = %s ORDER BY tag",
        (user_id,)
    )
    return [r[0] for r in (rows or [])]


def get_stats_by_tag(db_manager, user_id):
    """Get performance stats grouped by tag."""
    rows = db_manager.execute_query("""
        SELECT tag,
               COUNT(*) as trades,
               COUNT(*) FILTER (WHERE realized_pnl > 0) as wins,
               COUNT(*) FILTER (WHERE realized_pnl <= 0) as losses,
               COALESCE(AVG(realized_pnl_pct), 0) as avg_return,
               COALESCE(SUM(realized_pnl), 0) as total_pnl
        FROM trade_journal, unnest(tags) as tag
        WHERE user_id = %s AND tags IS NOT NULL
        GROUP BY tag
        ORDER BY trades DESC
    """, (user_id,))

    return [{
        'tag': r[0], 'trades': r[1], 'wins': r[2], 'losses': r[3],
        'win_rate': r[2] / r[1] if r[1] > 0 else 0,
        'avg_return': float(r[4]), 'total_pnl': float(r[5]),
    } for r in (rows or [])]


# ──────────────────────────────────────────────────────────────
# Premium: Pre-Trade Plan & Post-Trade Review
# ──────────────────────────────────────────────────────────────

def save_pre_trade_plan(db_manager, user_id, entry_id, plan_data):
    """Save pre-trade plan JSONB."""
    try:
        with db_manager.get_cursor(commit=True) as cur:
            cur.execute(
                "UPDATE trade_journal SET pre_trade_plan = %s WHERE id = %s AND user_id = %s",
                (json.dumps(plan_data), entry_id, user_id)
            )
            return {'success': cur.rowcount > 0}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def save_post_trade_review(db_manager, user_id, entry_id, review_data):
    """Save post-trade review JSONB."""
    try:
        with db_manager.get_cursor(commit=True) as cur:
            cur.execute(
                "UPDATE trade_journal SET post_trade_review = %s WHERE id = %s AND user_id = %s",
                (json.dumps(review_data), entry_id, user_id)
            )
            return {'success': cur.rowcount > 0}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def save_tags(db_manager, user_id, entry_id, tags):
    """Save tags array on a journal entry."""
    try:
        with db_manager.get_cursor(commit=True) as cur:
            cur.execute(
                "UPDATE trade_journal SET tags = %s WHERE id = %s AND user_id = %s",
                (tags, entry_id, user_id)
            )
            return {'success': cur.rowcount > 0}
    except Exception as e:
        return {'success': False, 'error': str(e)}


# ──────────────────────────────────────────────────────────────
# Premium: Pattern Detection
# ──────────────────────────────────────────────────────────────

def detect_pattern(db_manager, user_id, entry_id):
    """Rule-based pattern detection from signal_details and indicators."""
    entry = get_entry(db_manager, user_id, entry_id)
    if not entry:
        return {'success': False, 'error': 'Entry not found'}

    sd = entry.get('signal_details') or {}
    if isinstance(sd, str):
        try:
            sd = json.loads(sd)
        except (json.JSONDecodeError, TypeError):
            sd = {}

    magnitude = float(sd.get('magnitude', 0))
    volume_ratio = float(sd.get('volume_ratio', 1.0))
    direction = sd.get('entry_direction', entry.get('direction', 'long'))

    # Simple rule-based classification
    pattern = 'unknown'
    confidence = 0.5

    if magnitude >= 1.0 and volume_ratio >= 1.5:
        pattern = 'momentum_breakout'
        confidence = 0.85
    elif magnitude >= 0.5 and volume_ratio >= 1.2:
        pattern = 'trend_continuation'
        confidence = 0.75
    elif magnitude < 0.3 and volume_ratio < 0.8:
        pattern = 'mean_reversion'
        confidence = 0.60
    elif volume_ratio >= 2.0:
        pattern = 'volume_climax'
        confidence = 0.70
    elif magnitude >= 0.5:
        pattern = 'breakout_consolidation'
        confidence = 0.65

    pattern_data = {
        'detected_pattern': pattern,
        'confidence': confidence,
        'direction': direction,
        'magnitude': magnitude,
        'volume_ratio': volume_ratio,
        'detected_at': datetime.now().isoformat(),
    }

    try:
        with db_manager.get_cursor(commit=True) as cur:
            cur.execute(
                "UPDATE trade_journal SET pattern_data = %s WHERE id = %s AND user_id = %s",
                (json.dumps(pattern_data), entry_id, user_id)
            )
    except Exception as e:
        logger.error(f"Pattern save failed: {e}")

    return {'success': True, 'pattern_data': pattern_data}


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────

def _row_to_dict(row):
    """Convert a trade_journal row tuple to dict."""
    if not row:
        return None
    # Column order matches CREATE TABLE
    keys = [
        'id', 'user_id', 'transaction_id', 'ticker', 'trade_date', 'direction',
        'entry_price', 'exit_price', 'quantity', 'realized_pnl', 'realized_pnl_pct',
        'entry_notes', 'exit_notes', 'lessons_learned', 'tags',
        'pre_trade_plan', 'post_trade_review', 'ai_score', 'pattern_data',
        'chart_snapshot_entry', 'chart_snapshot_exit', 'is_public',
        'signal_source', 'signal_details', 'created_at', 'updated_at',
    ]
    d = {}
    for i, key in enumerate(keys):
        if i >= len(row):
            break
        val = row[i]
        if isinstance(val, date) and not isinstance(val, datetime):
            val = val.isoformat()
        elif isinstance(val, datetime):
            val = val.isoformat()
        elif hasattr(val, '__str__') and key == 'transaction_id' and val is not None:
            val = str(val)
        d[key] = val

    # Parse JSONB fields if they're strings
    for jf in ('pre_trade_plan', 'post_trade_review', 'ai_score', 'pattern_data', 'signal_details'):
        if jf in d and isinstance(d[jf], str):
            try:
                d[jf] = json.loads(d[jf])
            except (json.JSONDecodeError, TypeError):
                pass

    # Convert Decimal types
    for nf in ('entry_price', 'exit_price', 'quantity', 'realized_pnl', 'realized_pnl_pct'):
        if nf in d and d[nf] is not None:
            d[nf] = float(d[nf])

    return d
