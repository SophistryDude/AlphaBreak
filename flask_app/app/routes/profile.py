"""
Profile Routes
==============
User profile management, password changes, preferences, and analytics.
"""

import logging
from app.utils import error_details
from flask import Blueprint, g, jsonify, request
from app.utils.auth import log_request
from app.utils.jwt_auth import require_jwt
from app.utils.database import (
    get_user_by_public_id, get_user_full_profile,
    update_user_display_name, update_user_password, get_user_password_hash,
    get_user_preferences, set_user_preference,
)

logger = logging.getLogger(__name__)
profile_bp = Blueprint('profile', __name__)


def _get_user_internal_id():
    user = get_user_by_public_id(g.user_id)
    return user['id'] if user else None


# ──────────────────────────────────────────────────────────────
# Profile
# ──────────────────────────────────────────────────────────────

@profile_bp.route('/user/profile', methods=['GET'])
@log_request
@require_jwt
def get_profile():
    """Get full user profile."""
    user_id = _get_user_internal_id()
    if not user_id:
        return jsonify({'error': 'User not found'}), 404

    profile = get_user_full_profile(user_id)
    if not profile:
        return jsonify({'error': 'Profile not found'}), 404

    # Remove sensitive fields
    profile.pop('id', None)
    return jsonify({'profile': profile})


@profile_bp.route('/user/profile', methods=['PUT'])
@log_request
@require_jwt
def update_profile():
    """Update display name."""
    user_id = _get_user_internal_id()
    if not user_id:
        return jsonify({'error': 'User not found'}), 404

    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    display_name = data.get('display_name', '').strip()
    if not display_name or len(display_name) > 100:
        return jsonify({'error': 'Display name must be 1-100 characters'}), 400

    if update_user_display_name(user_id, display_name):
        return jsonify({'success': True, 'display_name': display_name})
    return jsonify({'error': 'Failed to update profile'}), 500


@profile_bp.route('/user/password', methods=['PUT'])
@log_request
@require_jwt
def change_password():
    """Change password (requires current password)."""
    user_id = _get_user_internal_id()
    if not user_id:
        return jsonify({'error': 'User not found'}), 404

    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    current_password = data.get('current_password', '')
    new_password = data.get('new_password', '')
    confirm_password = data.get('confirm_password', '')

    if not current_password or not new_password:
        return jsonify({'error': 'Current and new password required'}), 400
    if new_password != confirm_password:
        return jsonify({'error': 'New passwords do not match'}), 400
    if len(new_password) < 8:
        return jsonify({'error': 'Password must be at least 8 characters'}), 400

    # Verify current password
    from app.utils.jwt_auth import verify_password, hash_password
    stored_hash = get_user_password_hash(user_id)
    if not stored_hash or not verify_password(current_password, stored_hash):
        return jsonify({'error': 'Current password is incorrect'}), 401

    # Update password
    new_hash = hash_password(new_password)
    if update_user_password(user_id, new_hash):
        return jsonify({'success': True, 'message': 'Password updated'})
    return jsonify({'error': 'Failed to update password'}), 500


# ──────────────────────────────────────────────────────────────
# Preferences
# ──────────────────────────────────────────────────────────────

@profile_bp.route('/user/preferences', methods=['GET'])
@log_request
@require_jwt
def get_prefs():
    """Get user preferences."""
    user_id = _get_user_internal_id()
    if not user_id:
        return jsonify({'error': 'User not found'}), 404
    prefs = get_user_preferences(user_id)
    return jsonify({'preferences': prefs})


@profile_bp.route('/user/preferences', methods=['PUT'])
@log_request
@require_jwt
def set_pref():
    """Set a user preference."""
    user_id = _get_user_internal_id()
    if not user_id:
        return jsonify({'error': 'User not found'}), 404

    data = request.get_json()
    key = data.get('key', '').strip()
    value = data.get('value', '')

    if not key or len(key) > 50:
        return jsonify({'error': 'Invalid preference key'}), 400

    if set_user_preference(user_id, key, str(value)):
        return jsonify({'success': True, 'key': key, 'value': value})
    return jsonify({'error': 'Failed to save preference'}), 500


# ──────────────────────────────────────────────────────────────
# Analytics
# ──────────────────────────────────────────────────────────────

@profile_bp.route('/user/analytics/summary', methods=['GET'])
@log_request
@require_jwt
def analytics_summary():
    """Portfolio analytics summary: win rate, Sharpe, drawdown, streaks."""
    try:
        from app.utils.analytics import get_analytics_summary
        summary = get_analytics_summary()
        return jsonify(summary)
    except Exception as e:
        logger.error(f"Analytics summary error: {e}")
        return jsonify({'error': 'Failed to compute analytics', 'details': error_details(e)}), 500


@profile_bp.route('/user/analytics/equity-curve', methods=['GET'])
@log_request
@require_jwt
def analytics_equity_curve():
    """Equity curve time series."""
    days = int(request.args.get('days', 90))
    try:
        from app.utils.analytics import get_equity_curve
        data = get_equity_curve(days)
        return jsonify({'equity_curve': data, 'days': days})
    except Exception as e:
        logger.error(f"Equity curve error: {e}")
        return jsonify({'error': 'Failed to load equity curve'}), 500


@profile_bp.route('/user/analytics/pnl-calendar', methods=['GET'])
@log_request
@require_jwt
def analytics_pnl_calendar():
    """P&L calendar heatmap data."""
    days = int(request.args.get('days', 90))
    try:
        from app.utils.analytics import get_pnl_calendar
        data = get_pnl_calendar(days)
        return jsonify({'calendar': data, 'days': days})
    except Exception as e:
        logger.error(f"P&L calendar error: {e}")
        return jsonify({'error': 'Failed to load P&L calendar'}), 500


@profile_bp.route('/user/analytics/best-worst', methods=['GET'])
@log_request
@require_jwt
def analytics_best_worst():
    """Top 5 best and worst trades."""
    try:
        from app.utils.analytics import get_best_worst_trades
        data = get_best_worst_trades()
        return jsonify(data)
    except Exception as e:
        logger.error(f"Best/worst trades error: {e}")
        return jsonify({'error': 'Failed to load trade data'}), 500
