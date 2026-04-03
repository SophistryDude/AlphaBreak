"""
Notification Routes
===================
Handles in-app notifications and user notification preferences.

Endpoints:
  GET  /api/notifications              - List recent notifications
  GET  /api/notifications/unread-count - Badge count
  POST /api/notifications/<id>/read    - Mark one as read
  POST /api/notifications/read-all     - Mark all as read
  GET  /api/notifications/preferences  - Get preference toggles
  PUT  /api/notifications/preferences  - Update a preference toggle
"""

import logging
from flask import Blueprint, g, jsonify, request
from app.utils.auth import log_request
from app.utils.jwt_auth import require_jwt
from app.utils.database import get_user_by_public_id

logger = logging.getLogger(__name__)

notifications_bp = Blueprint('notifications', __name__)

DEFAULT_EVENT_TYPES = [
    'trade_signal', 'stop_loss', 'take_profit', 'reversal_exit',
    'trim', 'new_position', 'earnings_1day', 'earnings_1week', 'portfolio_summary',
]


def _get_user_internal_id():
    user = get_user_by_public_id(g.user_id)
    return user['id'] if user else None


@notifications_bp.route('/notifications', methods=['GET'])
@log_request
@require_jwt
def list_notifications():
    """List recent notifications for the authenticated user."""
    user_id = _get_user_internal_id()
    if not user_id:
        return jsonify({'error': 'User not found'}), 404

    limit = min(int(request.args.get('limit', 20)), 100)
    offset = int(request.args.get('offset', 0))
    unread_only = request.args.get('unread_only', 'false').lower() == 'true'

    from app.utils.database import db_manager
    query = """
        SELECT id, event_type, title, body, metadata, is_read, created_at
        FROM notifications
        WHERE user_id = %s
    """
    params = [user_id]
    if unread_only:
        query += " AND is_read = FALSE"
    query += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
    params.extend([limit, offset])

    rows = db_manager.execute_query(query, tuple(params))
    notifications = []
    for row in (rows or []):
        notifications.append({
            'id': row[0],
            'event_type': row[1],
            'title': row[2],
            'body': row[3],
            'metadata': row[4],
            'is_read': row[5],
            'created_at': row[6].isoformat() if row[6] else None,
        })

    return jsonify({'notifications': notifications, 'count': len(notifications)})


@notifications_bp.route('/notifications/unread-count', methods=['GET'])
@log_request
@require_jwt
def unread_count():
    """Get unread notification count for badge display."""
    user_id = _get_user_internal_id()
    if not user_id:
        return jsonify({'count': 0})

    from app.utils.database import db_manager
    rows = db_manager.execute_query(
        "SELECT COUNT(*) FROM notifications WHERE user_id = %s AND is_read = FALSE",
        (user_id,)
    )
    count = rows[0][0] if rows and rows[0] else 0
    return jsonify({'count': count})


@notifications_bp.route('/notifications/<int:notification_id>/read', methods=['POST'])
@log_request
@require_jwt
def mark_read(notification_id):
    """Mark a single notification as read."""
    user_id = _get_user_internal_id()
    if not user_id:
        return jsonify({'error': 'User not found'}), 404

    from app.utils.database import db_manager
    try:
        with db_manager.get_cursor(commit=True) as cursor:
            cursor.execute(
                "UPDATE notifications SET is_read = TRUE WHERE id = %s AND user_id = %s",
                (notification_id, user_id)
            )
            if cursor.rowcount == 0:
                return jsonify({'error': 'Notification not found'}), 404
    except Exception as e:
        logger.error(f"Failed to mark notification read: {e}")
        return jsonify({'error': 'Failed to update'}), 500

    return jsonify({'success': True})


@notifications_bp.route('/notifications/read-all', methods=['POST'])
@log_request
@require_jwt
def mark_all_read():
    """Mark all notifications as read for the authenticated user."""
    user_id = _get_user_internal_id()
    if not user_id:
        return jsonify({'error': 'User not found'}), 404

    from app.utils.database import db_manager
    try:
        with db_manager.get_cursor(commit=True) as cursor:
            cursor.execute(
                "UPDATE notifications SET is_read = TRUE WHERE user_id = %s AND is_read = FALSE",
                (user_id,)
            )
            updated = cursor.rowcount
    except Exception as e:
        logger.error(f"Failed to mark all read: {e}")
        return jsonify({'error': 'Failed to update'}), 500

    return jsonify({'success': True, 'updated': updated})


@notifications_bp.route('/notifications/preferences', methods=['GET'])
@log_request
@require_jwt
def get_preferences():
    """Get notification preferences for the authenticated user."""
    user_id = _get_user_internal_id()
    if not user_id:
        return jsonify({'error': 'User not found'}), 404

    from app.utils.database import db_manager

    # Ensure defaults exist
    _seed_default_preferences(user_id, db_manager)

    rows = db_manager.execute_query(
        "SELECT event_type, email_enabled, push_enabled FROM notification_preferences WHERE user_id = %s ORDER BY event_type",
        (user_id,)
    )
    preferences = {}
    for row in (rows or []):
        preferences[row[0]] = {
            'email_enabled': row[1],
            'push_enabled': row[2],
        }

    return jsonify({'preferences': preferences})


@notifications_bp.route('/notifications/preferences', methods=['PUT'])
@log_request
@require_jwt
def update_preference():
    """Update a notification preference toggle."""
    user_id = _get_user_internal_id()
    if not user_id:
        return jsonify({'error': 'User not found'}), 404

    data = request.get_json()
    if not data or 'event_type' not in data:
        return jsonify({'error': 'event_type required'}), 400

    event_type = data['event_type']
    if event_type not in DEFAULT_EVENT_TYPES:
        return jsonify({'error': f'Invalid event_type: {event_type}'}), 400

    email_enabled = data.get('email_enabled')
    push_enabled = data.get('push_enabled')

    from app.utils.database import db_manager
    try:
        with db_manager.get_cursor(commit=True) as cursor:
            updates = []
            params = []
            if email_enabled is not None:
                updates.append("email_enabled = %s")
                params.append(email_enabled)
            if push_enabled is not None:
                updates.append("push_enabled = %s")
                params.append(push_enabled)
            if not updates:
                return jsonify({'error': 'No fields to update'}), 400

            updates.append("updated_at = NOW()")
            params.extend([user_id, event_type])

            cursor.execute(
                f"UPDATE notification_preferences SET {', '.join(updates)} WHERE user_id = %s AND event_type = %s",
                tuple(params)
            )
            if cursor.rowcount == 0:
                # Insert if not exists
                cursor.execute(
                    "INSERT INTO notification_preferences (user_id, event_type, email_enabled, push_enabled) VALUES (%s, %s, %s, %s)",
                    (user_id, event_type, email_enabled or True, push_enabled or False)
                )
    except Exception as e:
        logger.error(f"Failed to update preference: {e}")
        return jsonify({'error': 'Failed to update'}), 500

    return jsonify({'success': True, 'event_type': event_type})


def _seed_default_preferences(user_id, db_manager):
    """Ensure all default event types exist for a user."""
    try:
        with db_manager.get_cursor(commit=True) as cursor:
            for event_type in DEFAULT_EVENT_TYPES:
                cursor.execute(
                    "INSERT INTO notification_preferences (user_id, event_type) VALUES (%s, %s) ON CONFLICT (user_id, event_type) DO NOTHING",
                    (user_id, event_type)
                )
    except Exception as e:
        logger.debug(f"Seed preferences: {e}")
