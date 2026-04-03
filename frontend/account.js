/**
 * Account Module
 * ==============
 * User profile, settings, preferences, linked accounts, and performance analytics.
 */

const Account = {
    data: null,
    activeSubTab: 'profile',
    equityChart: null,

    init() {
        // Observe tab activation (lazy load)
        const tab = document.getElementById('accountTab');
        if (tab) {
            const observer = new MutationObserver(() => {
                if (tab.classList.contains('active')) {
                    this.load();
                }
            });
            observer.observe(tab, { attributes: true, attributeFilter: ['class'] });
        }

        // Sub-tab clicks
        document.querySelectorAll('.account-sub-tab').forEach(btn => {
            btn.addEventListener('click', () => this.switchSubTab(btn.dataset.subtab));
        });
    },

    async load() {
        if (!Auth.isAuthenticated) return;
        await this.loadProfile();
        if (this.activeSubTab === 'performance') {
            await this.loadAnalytics();
        }
    },

    switchSubTab(name) {
        this.activeSubTab = name;
        document.querySelectorAll('.account-sub-tab').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.subtab === name);
        });
        document.querySelectorAll('.account-section').forEach(sec => {
            sec.style.display = sec.id === `accountSection-${name}` ? 'block' : 'none';
        });
        if (name === 'performance') this.loadAnalytics();
        if (name === 'journal' && typeof Journal !== 'undefined') Journal.load();
    },

    // ──────────────────────────────────────────────
    // Profile
    // ──────────────────────────────────────────────

    async loadProfile() {
        try {
            const res = await apiRequest('/api/user/profile');
            if (!res.ok) return;
            const data = await res.json();
            this.data = data.profile;
            this.renderProfile();
        } catch (e) {
            console.error('Failed to load profile:', e);
        }
    },

    renderProfile() {
        const p = this.data;
        if (!p) return;

        const el = (id) => document.getElementById(id);
        if (el('profileDisplayName')) el('profileDisplayName').value = p.display_name || '';
        if (el('profileEmail')) el('profileEmail').textContent = p.email || '';
        if (el('profileMemberSince')) {
            const d = p.created_at ? new Date(p.created_at) : null;
            el('profileMemberSince').textContent = d ? d.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' }) : 'N/A';
        }
        if (el('profileLastLogin')) {
            const d = p.last_login_at ? new Date(p.last_login_at) : null;
            el('profileLastLogin').textContent = d ? d.toLocaleString() : 'N/A';
        }
        if (el('profilePremiumBadge')) {
            el('profilePremiumBadge').style.display = p.is_premium ? 'inline-block' : 'none';
        }
    },

    async saveDisplayName() {
        const input = document.getElementById('profileDisplayName');
        if (!input) return;
        const name = input.value.trim();
        if (!name) return;

        try {
            const res = await apiRequest('/api/user/profile', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ display_name: name }),
            });
            const data = await res.json();
            if (data.success) {
                // Update auth state and header
                Auth.user.display_name = name;
                localStorage.setItem(Auth.USER_KEY, JSON.stringify(Auth.user));
                Auth.updateUI();
                if (typeof showSnackbar === 'function') showSnackbar('Display name updated', 'success');
            } else {
                if (typeof showSnackbar === 'function') showSnackbar(data.error || 'Failed', 'error');
            }
        } catch (e) {
            if (typeof showSnackbar === 'function') showSnackbar('Failed to save', 'error');
        }
    },

    async changePassword() {
        const current = document.getElementById('currentPassword');
        const newPw = document.getElementById('newPassword');
        const confirm = document.getElementById('confirmPassword');
        if (!current || !newPw || !confirm) return;

        const errEl = document.getElementById('passwordError');

        if (newPw.value !== confirm.value) {
            if (errEl) errEl.textContent = 'Passwords do not match';
            return;
        }
        if (newPw.value.length < 8) {
            if (errEl) errEl.textContent = 'Password must be at least 8 characters';
            return;
        }

        try {
            const res = await apiRequest('/api/user/password', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    current_password: current.value,
                    new_password: newPw.value,
                    confirm_password: confirm.value,
                }),
            });
            const data = await res.json();
            if (data.success) {
                current.value = ''; newPw.value = ''; confirm.value = '';
                if (errEl) errEl.textContent = '';
                if (typeof showSnackbar === 'function') showSnackbar('Password changed', 'success');
            } else {
                if (errEl) errEl.textContent = data.error || 'Failed';
            }
        } catch (e) {
            if (errEl) errEl.textContent = 'Request failed';
        }
    },

    // ──────────────────────────────────────────────
    // Performance Analytics
    // ──────────────────────────────────────────────

    async loadAnalytics() {
        await Promise.all([
            this.loadSummary(),
            this.loadEquityCurve(),
            this.loadPnLCalendar(),
            this.loadBestWorst(),
        ]);
    },

    async loadSummary() {
        try {
            const res = await apiRequest('/api/user/analytics/summary');
            if (!res.ok) return;
            const data = await res.json();
            this.renderSummary(data);
        } catch (e) { /* ignore */ }
    },

    renderSummary(d) {
        const set = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
        set('analyticsTotalValue', '$' + (d.total_value || 0).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2}));
        set('analyticsTotalReturn', (d.total_pnl_pct * 100).toFixed(2) + '%');
        set('analyticsWinRate', (d.win_rate * 100).toFixed(1) + '%');
        set('analyticsSharpe', (d.sharpe_ratio || 0).toFixed(2));
        set('analyticsMaxDrawdown', (d.max_drawdown_pct * 100).toFixed(2) + '%');
        set('analyticsTotalTrades', d.total_trades || 0);
        set('analyticsAvgWin', '$' + (d.avg_win || 0).toFixed(0));
        set('analyticsAvgLoss', '$' + (d.avg_loss || 0).toFixed(0));
        set('analyticsProfitFactor', (d.profit_factor || 0).toFixed(2));
        set('analyticsWinStreak', d.best_win_streak || 0);
        set('analyticsLossStreak', d.worst_loss_streak || 0);

        // Color coding
        const retEl = document.getElementById('analyticsTotalReturn');
        if (retEl) retEl.className = 'metric-value ' + (d.total_pnl_pct >= 0 ? 'positive' : 'negative');
        const sharpeEl = document.getElementById('analyticsSharpe');
        if (sharpeEl) sharpeEl.className = 'metric-value ' + (d.sharpe_ratio > 1 ? 'positive' : d.sharpe_ratio > 0 ? 'neutral' : 'negative');
    },

    async loadEquityCurve() {
        const days = parseInt(document.getElementById('equityCurveDays')?.value || 90);
        try {
            const res = await apiRequest(`/api/user/analytics/equity-curve?days=${days}`);
            if (!res.ok) return;
            const data = await res.json();
            this.renderEquityCurve(data.equity_curve || []);
        } catch (e) { /* ignore */ }
    },

    renderEquityCurve(curve) {
        const canvas = document.getElementById('equityCurveChart');
        if (!canvas || !curve.length) return;

        if (this.equityChart) this.equityChart.destroy();

        const labels = curve.map(d => d.date);
        const values = curve.map(d => d.value);
        const drawdowns = curve.map(d => d.drawdown_pct * 100);

        this.equityChart = new Chart(canvas, {
            type: 'line',
            data: {
                labels,
                datasets: [{
                    label: 'Portfolio Value',
                    data: values,
                    borderColor: '#00d4aa',
                    backgroundColor: 'rgba(0,212,170,0.1)',
                    fill: true,
                    tension: 0.3,
                    pointRadius: 0,
                    yAxisID: 'y',
                }, {
                    label: 'Drawdown %',
                    data: drawdowns,
                    borderColor: '#ff6b6b',
                    backgroundColor: 'rgba(255,107,107,0.1)',
                    fill: true,
                    tension: 0.3,
                    pointRadius: 0,
                    yAxisID: 'y1',
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: 'index', intersect: false },
                plugins: { legend: { labels: { color: '#e0e0e0' } } },
                scales: {
                    x: { ticks: { color: '#888', maxTicksLimit: 10 }, grid: { color: 'rgba(255,255,255,0.05)' } },
                    y: { position: 'left', ticks: { color: '#00d4aa', callback: v => '$' + v.toLocaleString() }, grid: { color: 'rgba(255,255,255,0.05)' } },
                    y1: { position: 'right', ticks: { color: '#ff6b6b', callback: v => v.toFixed(1) + '%' }, grid: { display: false }, min: -30, max: 0 },
                },
            },
        });
    },

    async loadPnLCalendar() {
        try {
            const res = await apiRequest('/api/user/analytics/pnl-calendar?days=90');
            if (!res.ok) return;
            const data = await res.json();
            this.renderPnLCalendar(data.calendar || []);
        } catch (e) { /* ignore */ }
    },

    renderPnLCalendar(calendar) {
        const container = document.getElementById('pnlCalendar');
        if (!container) return;

        if (!calendar.length) {
            container.innerHTML = '<p class="empty-state">No P&L data yet</p>';
            return;
        }

        const maxPnl = Math.max(...calendar.map(d => Math.abs(d.pnl)), 1);

        let html = '<div class="pnl-heatmap">';
        // Day labels
        html += '<div class="pnl-day-labels"><span>Mon</span><span>Tue</span><span>Wed</span><span>Thu</span><span>Fri</span></div>';
        html += '<div class="pnl-grid">';

        for (const day of calendar) {
            if (day.weekday >= 5) continue; // Skip weekends
            const intensity = Math.min(1, Math.abs(day.pnl) / maxPnl);
            const color = day.pnl > 0
                ? `rgba(0,212,170,${0.2 + intensity * 0.8})`
                : day.pnl < 0
                    ? `rgba(255,107,107,${0.2 + intensity * 0.8})`
                    : 'rgba(255,255,255,0.05)';

            html += `<div class="pnl-cell" style="background:${color}" title="${day.date}: $${day.pnl.toFixed(0)}">
                <span class="pnl-cell-date">${day.date.slice(5)}</span>
            </div>`;
        }

        html += '</div></div>';
        container.innerHTML = html;
    },

    async loadBestWorst() {
        try {
            const res = await apiRequest('/api/user/analytics/best-worst');
            if (!res.ok) return;
            const data = await res.json();
            this.renderBestWorst(data);
        } catch (e) { /* ignore */ }
    },

    renderBestWorst(data) {
        const renderTable = (trades, containerId) => {
            const el = document.getElementById(containerId);
            if (!el) return;
            if (!trades || !trades.length) {
                el.innerHTML = '<p class="empty-state">No trades yet</p>';
                return;
            }
            el.innerHTML = '<table class="data-table"><thead><tr><th>Ticker</th><th>Type</th><th>P&L</th><th>Return</th><th>Date</th></tr></thead><tbody>' +
                trades.map(t => {
                    const cls = t.realized_pnl > 0 ? 'positive' : 'negative';
                    return `<tr>
                        <td><strong>${t.ticker}</strong></td>
                        <td>${t.asset_type}${t.option_type ? ' ' + t.option_type : ''}</td>
                        <td class="${cls}">$${t.realized_pnl.toFixed(0)}</td>
                        <td class="${cls}">${(t.realized_pnl_pct * 100).toFixed(1)}%</td>
                        <td>${t.executed_at ? t.executed_at.slice(0,10) : ''}</td>
                    </tr>`;
                }).join('') +
                '</tbody></table>';
        };

        renderTable(data.best, 'bestTradesTable');
        renderTable(data.worst, 'worstTradesTable');
    },
};

window.Account = Account;
