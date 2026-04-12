"""
Trade Journal Routes
====================
Full CRUD, sharing, AI scoring, auto-import, and premium-gated features.
"""

import logging
import re
from flask import Blueprint, g, jsonify, request
from app import limiter
from app.utils.auth import log_request
from app.utils.jwt_auth import require_jwt
from app.utils.database import (
    get_user_by_public_id, get_user_preferences, set_user_preference, db_manager,
)

logger = logging.getLogger(__name__)
journal_bp = Blueprint('journal', __name__)

TICKER_PATTERN = re.compile(r'^[A-Z]{1,10}$')
VALID_DIRECTIONS = ('long', 'short')
VALID_PNL_FILTERS = ('positive', 'negative')


def _get_user():
    """Get full user record."""
    return get_user_by_public_id(g.user_id)


def _premium_gate(user, feature_name):
    """Check premium or trial access. Returns (allowed, response_or_None)."""
    from app.services.journal_service import check_premium_or_trial
    is_premium = user.get('is_premium', False)
    prefs = get_user_preferences(user['id'])
    gate = check_premium_or_trial(user['id'], feature_name, is_premium, prefs)
    if not gate['allowed']:
        return False, jsonify({
            'error': f'{feature_name.replace("_", " ").title()} is a premium feature',
            'upgrade_required': True,
            'trial_used': gate['trial_used'],
        }), 403
    return True, gate


# ──────────────────────────────────────────────────────────────
# CRUD (Free)
# ──────────────────────────────────────────────────────────────

@journal_bp.route('/journal/entries', methods=['POST'])
@limiter.limit("30/minute")
@log_request
@require_jwt
def create():
    """Create a journal entry."""
    user = _get_user()
    if not user:
        return jsonify({'error': 'User not found'}), 404

    data = request.get_json() or {}
    if not data.get('ticker'):
        return jsonify({'error': 'Ticker is required'}), 400
    data['ticker'] = data['ticker'].strip().upper()
    if not TICKER_PATTERN.match(data['ticker']):
        return jsonify({'error': 'Invalid ticker format'}), 400

    from app.services.journal_service import create_entry
    result = create_entry(db_manager, user['id'], data)
    if result.get('success'):
        return jsonify(result), 201
    return jsonify(result), 400


@journal_bp.route('/journal/entries', methods=['GET'])
@log_request
@require_jwt
def list_all():
    """List journal entries with pagination and filters."""
    user = _get_user()
    if not user:
        return jsonify({'error': 'User not found'}), 404

    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)

    filters = {}
    if request.args.get('ticker'):
        filters['ticker'] = request.args['ticker']
    if request.args.get('direction'):
        if request.args['direction'] not in VALID_DIRECTIONS:
            return jsonify({'error': 'Invalid direction filter'}), 400
        filters['direction'] = request.args['direction']
    if request.args.get('pnl'):
        if request.args['pnl'] not in VALID_PNL_FILTERS:
            return jsonify({'error': 'Invalid pnl filter'}), 400
        filters['pnl'] = request.args['pnl']
    if request.args.get('date_from'):
        filters['date_from'] = request.args['date_from']
    if request.args.get('date_to'):
        filters['date_to'] = request.args['date_to']
    # Tags filter is premium-only
    tags = request.args.get('tags')
    if tags and user.get('is_premium'):
        filters['tags'] = [t.strip() for t in tags.split(',') if t.strip()]
    # Holding type filter
    if request.args.get('holding_type'):
        filters['holding_type'] = request.args['holding_type']

    from app.services.journal_service import list_entries
    result = list_entries(db_manager, user['id'], page, per_page, filters)
    return jsonify(result)


@journal_bp.route('/journal/entries/<int:entry_id>', methods=['GET'])
@log_request
@require_jwt
def get_one(entry_id):
    """Get a single journal entry."""
    user = _get_user()
    if not user:
        return jsonify({'error': 'User not found'}), 404

    from app.services.journal_service import get_entry
    entry = get_entry(db_manager, user['id'], entry_id)
    if not entry:
        return jsonify({'error': 'Entry not found'}), 404
    return jsonify({'entry': entry})


@journal_bp.route('/journal/entries/<int:entry_id>', methods=['PUT'])
@log_request
@require_jwt
def update(entry_id):
    """Update a journal entry (free fields only; premium fields via dedicated endpoints)."""
    user = _get_user()
    if not user:
        return jsonify({'error': 'User not found'}), 404

    data = request.get_json() or {}
    from app.services.journal_service import update_entry
    result = update_entry(db_manager, user['id'], entry_id, data)
    if result.get('success'):
        return jsonify(result)
    return jsonify(result), 400


@journal_bp.route('/journal/entries/<int:entry_id>', methods=['DELETE'])
@log_request
@require_jwt
def delete(entry_id):
    """Delete a journal entry."""
    user = _get_user()
    if not user:
        return jsonify({'error': 'User not found'}), 404

    from app.services.journal_service import delete_entry
    result = delete_entry(db_manager, user['id'], entry_id)
    if result.get('success'):
        return jsonify(result)
    return jsonify(result), 404


# ──────────────────────────────────────────────────────────────
# Sharing (Free)
# ──────────────────────────────────────────────────────────────

@journal_bp.route('/journal/public', methods=['GET'])
@log_request
@require_jwt
def public_entries():
    """Browse public journal entries."""
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 50)

    from app.services.journal_service import list_public_entries
    result = list_public_entries(db_manager, page, per_page)
    return jsonify(result)


@journal_bp.route('/journal/entries/<int:entry_id>/share', methods=['PUT'])
@log_request
@require_jwt
def toggle_share(entry_id):
    """Toggle public/private sharing."""
    user = _get_user()
    if not user:
        return jsonify({'error': 'User not found'}), 404

    data = request.get_json() or {}
    is_public = data.get('is_public', False)

    from app.services.journal_service import update_entry
    result = update_entry(db_manager, user['id'], entry_id, {'is_public': is_public})
    return jsonify(result)


# ──────────────────────────────────────────────────────────────
# AI Scoring (Free)
# ──────────────────────────────────────────────────────────────

@journal_bp.route('/journal/entries/<int:entry_id>/ai-score', methods=['POST'])
@log_request
@require_jwt
def ai_score(entry_id):
    """Generate AI trade score."""
    user = _get_user()
    if not user:
        return jsonify({'error': 'User not found'}), 404

    from app.services.journal_service import compute_ai_score
    result = compute_ai_score(db_manager, user['id'], entry_id)
    if result.get('success'):
        return jsonify(result)
    return jsonify(result), 400


# ──────────────────────────────────────────────────────────────
# Auto-Import (Free)
# ──────────────────────────────────────────────────────────────

@journal_bp.route('/journal/score-all', methods=['POST'])
@log_request
@require_jwt
def score_all():
    """Generate AI scores for all unscored journal entries."""
    user = _get_user()
    if not user:
        return jsonify({'error': 'User not found'}), 404

    from app.services.journal_service import list_entries, compute_ai_score
    result = list_entries(db_manager, user['id'], page=1, per_page=200)
    scored = 0
    for entry in result.get('entries', []):
        compute_ai_score(db_manager, user['id'], entry['id'])
        scored += 1

    return jsonify({'success': True, 'scored': scored})


@journal_bp.route('/journal/import-trades', methods=['POST'])
@log_request
@require_jwt
def import_trades():
    """Import trades from portfolio transactions."""
    user = _get_user()
    if not user:
        return jsonify({'error': 'User not found'}), 404

    from app.services.journal_service import import_trades as do_import
    result = do_import(db_manager, user['id'])
    return jsonify(result)


# ──────────────────────────────────────────────────────────────
# Premium: Pre-Trade Plan
# ──────────────────────────────────────────────────────────────

@journal_bp.route('/journal/entries/<int:entry_id>/pre-trade-plan', methods=['POST'])
@log_request
@require_jwt
def save_plan(entry_id):
    """Save pre-trade plan (premium or 1 trial)."""
    user = _get_user()
    if not user:
        return jsonify({'error': 'User not found'}), 404

    allowed, gate = _premium_gate(user, 'pre_trade_plan')
    if not allowed:
        return gate  # Returns (jsonify, 403)

    data = request.get_json() or {}
    from app.services.journal_service import save_pre_trade_plan, mark_trial_used
    result = save_pre_trade_plan(db_manager, user['id'], entry_id, data)

    if result.get('success') and isinstance(gate, dict) and gate.get('is_trial'):
        mark_trial_used(user['id'], 'pre_trade_plan')

    return jsonify(result)


@journal_bp.route('/journal/entries/<int:entry_id>/post-trade-review', methods=['POST'])
@log_request
@require_jwt
def save_review(entry_id):
    """Save post-trade review (premium or 1 trial)."""
    user = _get_user()
    if not user:
        return jsonify({'error': 'User not found'}), 404

    allowed, gate = _premium_gate(user, 'post_trade_review')
    if not allowed:
        return gate

    data = request.get_json() or {}
    from app.services.journal_service import save_post_trade_review, mark_trial_used
    result = save_post_trade_review(db_manager, user['id'], entry_id, data)

    if result.get('success') and isinstance(gate, dict) and gate.get('is_trial'):
        mark_trial_used(user['id'], 'post_trade_review')

    return jsonify(result)


# ──────────────────────────────────────────────────────────────
# Premium: Pattern Detection
# ──────────────────────────────────────────────────────────────

@journal_bp.route('/journal/entries/<int:entry_id>/pattern', methods=['POST'])
@log_request
@require_jwt
def detect_pattern_route(entry_id):
    """Auto-detect trade pattern (premium or 1 trial)."""
    user = _get_user()
    if not user:
        return jsonify({'error': 'User not found'}), 404

    allowed, gate = _premium_gate(user, 'pattern_recognition')
    if not allowed:
        return gate

    from app.services.journal_service import detect_pattern, mark_trial_used
    result = detect_pattern(db_manager, user['id'], entry_id)

    if result.get('success') and isinstance(gate, dict) and gate.get('is_trial'):
        mark_trial_used(user['id'], 'pattern_recognition')

    return jsonify(result)


# ──────────────────────────────────────────────────────────────
# Premium: Tags & Stats
# ──────────────────────────────────────────────────────────────

@journal_bp.route('/journal/tags', methods=['GET'])
@log_request
@require_jwt
def get_tags():
    """List all user tags (premium only)."""
    user = _get_user()
    if not user or not user.get('is_premium'):
        return jsonify({'error': 'Premium feature', 'upgrade_required': True}), 403

    from app.services.journal_service import get_user_tags
    tags = get_user_tags(db_manager, user['id'])
    return jsonify({'tags': tags})


@journal_bp.route('/journal/stats-by-tag', methods=['GET'])
@log_request
@require_jwt
def stats_by_tag():
    """Performance stats grouped by tag (premium only)."""
    user = _get_user()
    if not user or not user.get('is_premium'):
        return jsonify({'error': 'Premium feature', 'upgrade_required': True}), 403

    from app.services.journal_service import get_stats_by_tag
    stats = get_stats_by_tag(db_manager, user['id'])
    return jsonify({'stats': stats})


@journal_bp.route('/journal/entries/<int:entry_id>/tags', methods=['PUT'])
@log_request
@require_jwt
def update_tags(entry_id):
    """Update tags on a journal entry (premium only)."""
    user = _get_user()
    if not user or not user.get('is_premium'):
        return jsonify({'error': 'Premium feature', 'upgrade_required': True}), 403

    data = request.get_json() or {}
    tags = data.get('tags', [])
    if not isinstance(tags, list):
        return jsonify({'error': 'Tags must be an array'}), 400

    from app.services.journal_service import save_tags
    result = save_tags(db_manager, user['id'], entry_id, tags)
    return jsonify(result)
