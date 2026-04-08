// ============================================================================
// AI Dashboard — Model's market-wide view + AI Screener
// ============================================================================

const AIDashboard = (() => {
    let loaded = false;

    function init() {
        // Load data when tab becomes visible
        const observer = new MutationObserver(() => {
            const tab = document.getElementById('aidashboardTab');
            if (tab && tab.classList.contains('active') && !loaded) {
                loaded = true;
                loadDashboard();
            }
        });
        const tab = document.getElementById('aidashboardTab');
        if (tab) observer.observe(tab, { attributes: true, attributeFilter: ['class'] });

        // Screener search
        const btn = document.getElementById('aiScreenerBtn');
        const input = document.getElementById('aiScreenerInput');
        if (btn) btn.addEventListener('click', runScreener);
        if (input) {
            input.addEventListener('keydown', e => { if (e.key === 'Enter') runScreener(); });
            input.addEventListener('input', () => { input.value = input.value.toUpperCase(); });
        }
        _updateScreenerCounter();
    }

    async function loadDashboard() {
        try {
            const resp = await apiRequest('/api/analyze/ai-dashboard');
            const data = await resp.json();
            if (data.error) return;

            renderRegime(data.market_regime);
            renderModelStats(data.model_stats);
            renderSignals(data.top_signals);
            renderSectorRegimes(data.sector_regimes);
            renderHistory(data.signal_history);
        } catch (e) {
            console.error('AI Dashboard load failed:', e);
        }
    }

    // ── Market Regime ────────────────────────────────────────────────────
    function renderRegime(regime) {
        const el = document.getElementById('aiRegimeHero');
        if (!el || !regime) return;

        const colors = {
            'BULL': { bg: 'rgba(38,166,154,0.12)', border: '#26a69a', text: '#26a69a' },
            'BEAR': { bg: 'rgba(239,83,80,0.12)', border: '#ef5350', text: '#ef5350' },
            'RANGE': { bg: 'rgba(240,185,11,0.12)', border: '#f0b90b', text: '#f0b90b' },
            'HIGH_VOL': { bg: 'rgba(126,87,194,0.12)', border: '#7e57c2', text: '#7e57c2' },
        };
        const c = colors[regime.regime] || colors['RANGE'];
        const changeClass = (regime.spy_change || 0) >= 0 ? 'positive' : 'negative';
        const changeSign = (regime.spy_change || 0) >= 0 ? '+' : '';

        el.innerHTML = `
            <div class="ai-regime-card" style="background:${c.bg};border-left:4px solid ${c.border};">
                <div class="ai-regime-main">
                    <div class="ai-regime-label" style="color:${c.text}">${regime.regime}</div>
                    <div class="ai-regime-conf">${regime.confidence?.toFixed(0) || '--'}% confidence</div>
                </div>
                <div class="ai-regime-spy">
                    <span class="ai-regime-spy-label">S&P 500</span>
                    <span class="ai-regime-spy-price">$${regime.spy_price?.toFixed(2) || '--'}</span>
                    <span class="${changeClass}">${changeSign}${regime.spy_change?.toFixed(2) || '0'}%</span>
                </div>
                <div class="ai-regime-desc">
                    ${_regimeDescription(regime.regime)}
                </div>
            </div>
        `;
    }

    function _regimeDescription(regime) {
        switch (regime) {
            case 'BULL': return 'Uptrend in progress. Momentum indicators and trend-following strategies are most predictive. Buy pullbacks to support.';
            case 'BEAR': return 'Downtrend in progress. Mean-reversion at resistance and short-side momentum signals are most reliable. Protect capital.';
            case 'RANGE': return 'Market is consolidating. Range-bound strategies work best — buy support, sell resistance. Avoid breakout trades until regime shifts.';
            case 'HIGH_VOL': return 'Elevated volatility. Wide stops required. Options premiums are rich (favor selling). Reduce position sizes.';
            default: return 'Regime classification unavailable.';
        }
    }

    // ── Model Stats ──────────────────────────────────────────────────────
    function renderModelStats(stats) {
        const el = document.getElementById('aiStatsGrid');
        if (!el || !stats) return;

        el.innerHTML = `
            <div class="ai-stats-cards">
                <div class="ai-stat-card">
                    <span class="ai-stat-value">${(stats.backtest_win_rate || 0).toFixed(1)}%</span>
                    <span class="ai-stat-label">Backtest Win Rate</span>
                    <span class="ai-stat-sub">${(stats.total_trades_backtested || 0).toLocaleString()} trades</span>
                </div>
                <div class="ai-stat-card">
                    <span class="ai-stat-value">+${(stats.avg_return_per_trade || 0).toFixed(2)}%</span>
                    <span class="ai-stat-label">Avg Return / Trade</span>
                    <span class="ai-stat-sub">${stats.backtest_period || ''}</span>
                </div>
                <div class="ai-stat-card">
                    <span class="ai-stat-value">${stats.signals_today || 0}</span>
                    <span class="ai-stat-label">Signals Today</span>
                    <span class="ai-stat-sub">${stats.alerts_today || 0} alerts</span>
                </div>
                ${stats.recent_accuracy != null ? `
                <div class="ai-stat-card">
                    <span class="ai-stat-value">${stats.recent_accuracy}%</span>
                    <span class="ai-stat-label">30-Day Accuracy</span>
                    <span class="ai-stat-sub">${stats.recent_correct}/${stats.recent_total} correct</span>
                </div>
                ` : ''}
            </div>
        `;
    }

    // ── Top Signals ──────────────────────────────────────────────────────
    function renderSignals(signals) {
        const el = document.getElementById('aiSignalsList');
        if (!el) return;

        if (!signals || signals.length === 0) {
            el.innerHTML = '<p class="muted">No high-conviction signals in latest scan. Check back during market hours.</p>';
            return;
        }

        let html = '<div class="ai-signals-list">';
        for (const s of signals) {
            const dirClass = s.direction === 'bullish' ? 'positive' : 'negative';
            const arrow = s.direction === 'bullish' ? '&#9650;' : '&#9660;';
            const prob = (s.probability * 100).toFixed(0);
            const probClass = s.probability >= 0.90 ? 'prob-high' : s.probability >= 0.85 ? 'prob-mid' : 'prob-low';
            const changeStr = s.change_pct != null ? `${s.change_pct >= 0 ? '+' : ''}${s.change_pct.toFixed(2)}%` : '';
            const changeClass = (s.change_pct || 0) >= 0 ? 'positive' : 'negative';

            html += `
                <div class="ai-signal-row clickable" data-ticker="${s.ticker}">
                    <span class="ai-signal-ticker">${s.ticker}</span>
                    <span class="ai-signal-prob ${probClass}">${prob}%</span>
                    <span class="ai-signal-dir ${dirClass}">${arrow} ${(s.direction || '').toUpperCase()}</span>
                    <span class="ai-signal-price">${s.price ? '$' + s.price.toFixed(2) : '--'}</span>
                    <span class="${changeClass}">${changeStr}</span>
                    ${s.is_alert ? '<span class="ai-signal-alert">ALERT</span>' : ''}
                </div>
            `;
        }
        html += '</div>';
        el.innerHTML = html;

        // Click to analyze
        el.querySelectorAll('.ai-signal-row').forEach(row => {
            row.addEventListener('click', () => {
                const ticker = row.dataset.ticker;
                if (typeof Analyze !== 'undefined') {
                    document.querySelectorAll('.sidebar-link').forEach(l => l.classList.remove('active'));
                    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
                    document.querySelector('.sidebar-link[data-tab="watchlist"]')?.classList.add('active');
                    document.getElementById('watchlistTab')?.classList.add('active');
                    document.getElementById('currentPageTitle').textContent = 'Security Analysis';
                    document.getElementById('analyzeTickerInput').value = ticker;
                    Analyze.analyzeTicker(ticker);
                    window.scrollTo({ top: 0, behavior: 'smooth' });
                }
            });
        });
    }

    // ── Sector Regimes ───────────────────────────────────────────────────
    function renderSectorRegimes(sectors) {
        const el = document.getElementById('aiSectorGrid');
        if (!el || !sectors) return;

        if (sectors.length === 0) {
            el.innerHTML = '<p class="muted">Sector data unavailable.</p>';
            return;
        }

        const colors = {
            'BULL': '#26a69a', 'BEAR': '#ef5350',
            'RANGE': '#f0b90b', 'HIGH_VOL': '#7e57c2', 'UNKNOWN': '#5c6578',
        };

        let html = '<div class="ai-sector-grid">';
        for (const s of sectors) {
            const color = colors[s.regime] || '#5c6578';
            const changeClass = (s.change || 0) >= 0 ? 'positive' : 'negative';
            const changeSign = (s.change || 0) >= 0 ? '+' : '';

            html += `
                <div class="ai-sector-cell" style="border-left:3px solid ${color}">
                    <div class="ai-sector-name">${s.sector}</div>
                    <div class="ai-sector-regime" style="color:${color}">${s.regime}</div>
                    <div class="ai-sector-conf">${s.confidence?.toFixed(0) || '--'}%</div>
                    <div class="${changeClass}">${changeSign}${s.change?.toFixed(2) || '0'}%</div>
                </div>
            `;
        }
        html += '</div>';
        el.innerHTML = html;
    }

    // ── Signal History ───────────────────────────────────────────────────
    function renderHistory(history) {
        const el = document.getElementById('aiHistoryList');
        if (!el) return;

        if (!history || history.length === 0) {
            el.innerHTML = '<p class="muted">No recent signal history available. Signals generate during market hours.</p>';
            return;
        }

        let html = '<table class="ai-history-table"><thead><tr><th>Ticker</th><th>Prob</th><th>Direction</th><th>Price</th><th>Outcome</th><th>Result</th></tr></thead><tbody>';
        for (const h of history) {
            const dirClass = h.direction === 'bullish' ? 'positive' : 'negative';
            const prob = (h.probability * 100).toFixed(0);
            const change = h.change_pct != null ? `${h.change_pct >= 0 ? '+' : ''}${h.change_pct.toFixed(2)}%` : '--';
            const changeClass = (h.change_pct || 0) >= 0 ? 'positive' : 'negative';
            const result = h.correct === true ? '<span class="positive">Correct</span>'
                : h.correct === false ? '<span class="negative">Wrong</span>'
                : '<span class="muted">Pending</span>';

            html += `<tr>
                <td><strong>${h.ticker}</strong></td>
                <td>${prob}%</td>
                <td class="${dirClass}">${(h.direction || '').toUpperCase()}</td>
                <td>${h.price ? '$' + h.price.toFixed(2) : '--'}</td>
                <td class="${changeClass}">${change}</td>
                <td>${result}</td>
            </tr>`;
        }
        html += '</tbody></table>';
        el.innerHTML = html;
    }

    // ── AI Screener (3 free uses, then Pro) ─────────────────────────────
    const SCREENER_LIMIT = 3;
    const SCREENER_STORAGE_KEY = 'alphabreak_screener_uses';

    function _getScreenerUses() {
        try {
            const data = JSON.parse(localStorage.getItem(SCREENER_STORAGE_KEY) || '{}');
            // Reset monthly
            const now = new Date();
            const month = `${now.getFullYear()}-${now.getMonth()}`;
            if (data.month !== month) return { month, count: 0, tickers: [] };
            return data;
        } catch (e) { return { month: '', count: 0, tickers: [] }; }
    }

    function _recordScreenerUse(ticker) {
        const data = _getScreenerUses();
        const now = new Date();
        data.month = `${now.getFullYear()}-${now.getMonth()}`;
        if (!data.tickers.includes(ticker)) {
            data.count++;
            data.tickers.push(ticker);
        }
        localStorage.setItem(SCREENER_STORAGE_KEY, JSON.stringify(data));
        return data;
    }

    function _isPremiumUser() {
        return typeof Auth !== 'undefined' && Auth.isAuthenticated && Auth.user?.is_premium;
    }

    function _updateScreenerCounter() {
        const counter = document.getElementById('aiScreenerCounter');
        if (!counter) return;
        if (_isPremiumUser()) {
            counter.innerHTML = '<span class="pro-badge-sm">PRO</span> Unlimited screener access';
            return;
        }
        const uses = _getScreenerUses();
        const remaining = Math.max(0, SCREENER_LIMIT - uses.count);
        counter.innerHTML = `<span class="screener-remaining">${remaining}</span> free screen${remaining !== 1 ? 's' : ''} remaining this month`;
    }

    async function runScreener() {
        const input = document.getElementById('aiScreenerInput');
        const el = document.getElementById('aiScreenerResult');
        if (!input || !el) return;

        const ticker = input.value.trim().toUpperCase();
        if (!ticker) return;

        // Check usage limit (premium users bypass)
        if (!_isPremiumUser()) {
            const uses = _getScreenerUses();
            if (uses.count >= SCREENER_LIMIT && !uses.tickers.includes(ticker)) {
                el.innerHTML = `
                    <div class="pro-upsell">
                        <div class="pro-upsell-icon">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="32" height="32">
                                <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
                                <path d="M7 11V7a5 5 0 0110 0v4"></path>
                            </svg>
                        </div>
                        <h3>AI Screener — Pro Feature</h3>
                        <p>You've used your ${SCREENER_LIMIT} free screens this month. Upgrade to Pro for unlimited AI screening across any ticker.</p>
                        <div class="pro-upsell-features">
                            <span>Unlimited AI Screener</span>
                            <span>Auto-Detected Trendlines</span>
                            <span>Seasonality Heatmap</span>
                            <span>Peer Comparison</span>
                            <span>Real-Time Data</span>
                        </div>
                        <button class="btn btn-primary pro-locked-btn" style="margin-top:12px;">Upgrade to Pro — $99/mo</button>
                        <p class="pro-upsell-note">Resets monthly. You've screened: ${uses.tickers.join(', ')}</p>
                    </div>
                `;
                return;
            }
        }

        el.innerHTML = '<p class="muted">Scoring...</p>';

        try {
            const resp = await apiRequest(`/api/analyze/${ticker}/grades`);
            const grades = await resp.json();

            if (grades.error) {
                el.innerHTML = `<p class="muted">${grades.error}</p>`;
                return;
            }

            // Record usage (only counts unique tickers)
            if (!_isPremiumUser()) {
                _recordScreenerUse(ticker);
                _updateScreenerCounter();
            }

            const f = grades.factors || {};
            const overallCls = _gradeColor(grades.overall_grade);

            let html = `
                <div class="ai-screener-result">
                    <div class="ai-screener-header">
                        <div class="ai-screener-badge" style="background:${overallCls}20;color:${overallCls}">${grades.overall_grade}</div>
                        <div>
                            <strong>${ticker}</strong> — ${grades.sector || ''}
                            <div class="muted">Score: ${grades.overall_score}/100 | Rank #${grades.peer_rank?.rank || '?'} of ${grades.peer_rank?.total || '?'}</div>
                        </div>
                    </div>
                    <div class="ai-screener-factors">
            `;

            for (const key of ['value', 'growth', 'profitability', 'momentum', 'revisions', 'ai_score']) {
                const factor = f[key];
                if (!factor) continue;
                const fColor = _gradeColor(factor.grade);
                const exclusive = factor.exclusive ? ' <span class="grades-exclusive">AI</span>' : '';
                html += `
                    <div class="ai-screener-factor">
                        <span>${factor.factor}${exclusive}</span>
                        <span style="color:${fColor};font-weight:700;">${factor.grade}</span>
                    </div>
                `;
            }

            html += '</div>';

            // Quick action
            html += `<button class="btn btn-sm btn-primary" style="margin-top:10px;" onclick="
                document.querySelectorAll('.sidebar-link').forEach(l=>l.classList.remove('active'));
                document.querySelectorAll('.tab-content').forEach(c=>c.classList.remove('active'));
                document.querySelector('[data-tab=watchlist]').classList.add('active');
                document.getElementById('watchlistTab').classList.add('active');
                document.getElementById('currentPageTitle').textContent='Security Analysis';
                document.getElementById('analyzeTickerInput').value='${ticker}';
                Analyze.analyzeTicker('${ticker}');
                window.scrollTo({top:0,behavior:'smooth'});
            ">Full Analysis &rarr;</button>`;

            html += '</div>';
            el.innerHTML = html;

        } catch (e) {
            el.innerHTML = '<p class="muted">Failed to score ticker.</p>';
        }
    }

    function _gradeColor(grade) {
        if (!grade) return '#5c6578';
        const g = grade.charAt(0);
        if (g === 'A') return '#26a69a';
        if (g === 'B') return '#4caf50';
        if (g === 'C') return '#f0b90b';
        if (g === 'D') return '#ff9800';
        return '#ef5350';
    }

    return { init, loadDashboard };
})();

document.addEventListener('DOMContentLoaded', () => AIDashboard.init());
