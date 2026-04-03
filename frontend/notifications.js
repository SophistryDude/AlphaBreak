/**
 * Notifications Module
 * ====================
 * In-app notification bell, panel, and preferences management.
 * Polls for unread count every 60 seconds when authenticated.
 */

const Notifications = {
    pollInterval: null,
    POLL_MS: 60000,
    panelOpen: false,
    prefsModalOpen: false,

    EVENT_TYPE_LABELS: {
        trade_signal: 'Trade Signals',
        stop_loss: 'Stop-Loss Alerts',
        take_profit: 'Profit Taking',
        reversal_exit: 'Reversal Exits',
        trim: 'Position Trims',
        new_position: 'New Positions',
        earnings_1day: 'Earnings (1 Day)',
        earnings_1week: 'Earnings (1 Week)',
        portfolio_summary: 'Daily Summary',
    },

    init() {
        const bellBtn = document.getElementById('notificationBellBtn');
        const markAllBtn = document.getElementById('markAllReadBtn');
        const settingsBtn = document.getElementById('notificationSettingsBtn');

        if (bellBtn) bellBtn.addEventListener('click', () => this.togglePanel());
        if (markAllBtn) markAllBtn.addEventListener('click', () => this.markAllRead());
        if (settingsBtn) settingsBtn.addEventListener('click', () => this.showPreferences());

        // Close panel on outside click
        document.addEventListener('click', (e) => {
            const bell = document.getElementById('notificationBell');
            if (bell && !bell.contains(e.target) && this.panelOpen) {
                this.closePanel();
            }
        });

        // Show/hide bell based on auth state
        this.updateVisibility();

        // Start polling if authenticated
        if (typeof Auth !== 'undefined' && Auth.isAuthenticated) {
            this.show();
            this.fetchUnreadCount();
            this.startPolling();
        }
    },

    updateVisibility() {
        const bell = document.getElementById('notificationBell');
        if (!bell) return;
        const isAuth = typeof Auth !== 'undefined' && Auth.isAuthenticated;
        bell.style.display = isAuth ? 'inline-block' : 'none';
    },

    show() {
        const bell = document.getElementById('notificationBell');
        if (bell) bell.style.display = 'inline-block';
    },

    hide() {
        const bell = document.getElementById('notificationBell');
        if (bell) bell.style.display = 'none';
        this.stopPolling();
    },

    startPolling() {
        this.stopPolling();
        this.pollInterval = setInterval(() => this.fetchUnreadCount(), this.POLL_MS);
    },

    stopPolling() {
        if (this.pollInterval) {
            clearInterval(this.pollInterval);
            this.pollInterval = null;
        }
    },

    async fetchUnreadCount() {
        try {
            const response = await apiRequest('/api/notifications/unread-count');
            if (!response.ok) return;
            const data = await response.json();
            this.updateBadge(data.count || 0);
        } catch (e) {
            // Silently fail on poll
        }
    },

    updateBadge(count) {
        const badge = document.getElementById('notificationBadge');
        if (!badge) return;
        if (count > 0) {
            badge.textContent = count > 99 ? '99+' : count;
            badge.style.display = 'flex';
        } else {
            badge.style.display = 'none';
        }
    },

    togglePanel() {
        if (this.panelOpen) {
            this.closePanel();
        } else {
            this.openPanel();
        }
    },

    async openPanel() {
        const panel = document.getElementById('notificationPanel');
        if (!panel) return;
        panel.style.display = 'block';
        this.panelOpen = true;
        await this.fetchNotifications();
    },

    closePanel() {
        const panel = document.getElementById('notificationPanel');
        if (panel) panel.style.display = 'none';
        this.panelOpen = false;
    },

    async fetchNotifications() {
        const list = document.getElementById('notificationList');
        if (!list) return;

        try {
            const response = await apiRequest('/api/notifications?limit=20');
            if (!response.ok) throw new Error('Failed to fetch');
            const data = await response.json();
            this.renderNotifications(data.notifications || []);
        } catch (e) {
            list.innerHTML = '<p class="notification-empty">Failed to load notifications</p>';
        }
    },

    renderNotifications(notifications) {
        const list = document.getElementById('notificationList');
        if (!list) return;

        if (!notifications.length) {
            list.innerHTML = '<p class="notification-empty">No notifications yet</p>';
            return;
        }

        list.innerHTML = notifications.map(n => {
            const timeAgo = this.timeAgo(n.created_at);
            const iconClass = this.getEventIcon(n.event_type);
            const unreadClass = n.is_read ? '' : 'unread';
            return `
                <div class="notification-item ${unreadClass}" data-id="${n.id}" onclick="Notifications.markRead(${n.id}, this)">
                    <div class="notification-icon ${iconClass}"></div>
                    <div class="notification-content">
                        <div class="notification-title">${this.escapeHtml(n.title)}</div>
                        <div class="notification-body">${this.escapeHtml(n.body).substring(0, 100)}</div>
                        <div class="notification-time">${timeAgo}</div>
                    </div>
                </div>
            `;
        }).join('');
    },

    getEventIcon(eventType) {
        const icons = {
            trade_signal: 'icon-signal',
            stop_loss: 'icon-loss',
            take_profit: 'icon-profit',
            reversal_exit: 'icon-loss',
            trim: 'icon-trim',
            new_position: 'icon-profit',
            earnings_1day: 'icon-earnings',
            earnings_1week: 'icon-earnings',
            portfolio_summary: 'icon-summary',
        };
        return icons[eventType] || 'icon-signal';
    },

    async markRead(id, el) {
        try {
            await apiRequest(`/api/notifications/${id}/read`, { method: 'POST' });
            if (el) el.classList.remove('unread');
            this.fetchUnreadCount();
        } catch (e) {
            // ignore
        }
    },

    async markAllRead() {
        try {
            await apiRequest('/api/notifications/read-all', { method: 'POST' });
            this.updateBadge(0);
            // Remove unread class from all items
            document.querySelectorAll('.notification-item.unread').forEach(el => {
                el.classList.remove('unread');
            });
        } catch (e) {
            // ignore
        }
    },

    async showPreferences() {
        this.closePanel();
        try {
            const response = await apiRequest('/api/notifications/preferences');
            if (!response.ok) throw new Error('Failed to load preferences');
            const data = await response.json();
            this.renderPreferencesModal(data.preferences || {});
        } catch (e) {
            if (typeof showSnackbar === 'function') showSnackbar('Failed to load preferences', 'error');
        }
    },

    renderPreferencesModal(preferences) {
        // Remove existing modal
        const existing = document.getElementById('notifPrefsModal');
        if (existing) existing.remove();

        let rows = '';
        for (const [eventType, label] of Object.entries(this.EVENT_TYPE_LABELS)) {
            const pref = preferences[eventType] || { email_enabled: true, push_enabled: false };
            const emailChecked = pref.email_enabled ? 'checked' : '';
            rows += `
                <tr>
                    <td>${label}</td>
                    <td><label class="toggle"><input type="checkbox" ${emailChecked} data-event="${eventType}" data-channel="email" onchange="Notifications.togglePref(this)"><span class="toggle-slider"></span></label></td>
                    <td><span class="coming-soon">Coming Soon</span></td>
                </tr>
            `;
        }

        const modal = document.createElement('div');
        modal.id = 'notifPrefsModal';
        modal.className = 'modal-overlay';
        modal.innerHTML = `
            <div class="modal-content notification-prefs-modal">
                <div class="modal-header">
                    <h2>Notification Settings</h2>
                    <button class="modal-close" onclick="document.getElementById('notifPrefsModal').remove()">&times;</button>
                </div>
                <div class="modal-body">
                    <table class="prefs-table">
                        <thead>
                            <tr><th>Event</th><th>Email</th><th>Push</th></tr>
                        </thead>
                        <tbody>${rows}</tbody>
                    </table>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
    },

    async togglePref(checkbox) {
        const eventType = checkbox.dataset.event;
        const channel = checkbox.dataset.channel;
        const enabled = checkbox.checked;

        try {
            const body = { event_type: eventType };
            if (channel === 'email') body.email_enabled = enabled;
            if (channel === 'push') body.push_enabled = enabled;

            await apiRequest('/api/notifications/preferences', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });
        } catch (e) {
            checkbox.checked = !enabled; // Revert on failure
        }
    },

    timeAgo(dateStr) {
        if (!dateStr) return '';
        const now = new Date();
        const date = new Date(dateStr);
        const seconds = Math.floor((now - date) / 1000);

        if (seconds < 60) return 'just now';
        if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
        if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
        if (seconds < 604800) return `${Math.floor(seconds / 86400)}d ago`;
        return date.toLocaleDateString();
    },

    escapeHtml(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    },
};

window.Notifications = Notifications;
