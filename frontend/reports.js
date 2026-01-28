// ============================================================================
// Reports Tab — Trend Break Report Viewer
// ============================================================================
// Loads and displays trend break reports at 3 frequencies (daily, hourly, 10min).
// Features: frequency sub-tabs, filters, alert pulsing, detail panels.

const Reports = {
    activeFrequency: 'daily',
    autoRefreshTimer: null,
    currentReport: null,
    charts: {},

    REFRESH_INTERVALS: {
        daily: 5 * 60 * 1000,    // 5 minutes
        hourly: 2 * 60 * 1000,   // 2 minutes
        '10min': 1 * 60 * 1000,  // 1 minute
    },

    // ── Initialization ──────────────────────────────────────────────────

    init() {
        this.setupFrequencyTabs();
        this.setupFilters();
        this.loadReport('daily');
    },

    setupFrequencyTabs() {
        const tabs = document.querySelectorAll('.freq-tab');
        tabs.forEach(tab => {
            tab.addEventListener('click', () => {
                tabs.forEach(t => t.classList.remove('active'));
                tab.classList.add('active');
                this.activeFrequency = tab.dataset.frequency;
                this.loadReport(this.activeFrequency);
            });
        });
    },

    setupFilters() {
        const applyBtn = document.getElementById('reportApplyFilters');
        if (applyBtn) {
            applyBtn.addEventListener('click', () => {
                this.loadReport(this.activeFrequency);
            });
        }

        const alertsToggle = document.getElementById('reportAlertsOnly');
        if (alertsToggle) {
            alertsToggle.addEventListener('change', () => {
                this.loadReport(this.activeFrequency);
            });
        }
    },

    // ── Data Loading ────────────────────────────────────────────────────

    async loadReport(frequency) {
        const container = document.getElementById('reportTableBody');
        const summaryBar = document.getElementById('reportSummaryBar');
        if (!container) return;

        // Show loading state
        container.innerHTML = '<tr><td colspan="9" class="report-loading">Loading report...</td></tr>';

        // Build query params
        const params = new URLSearchParams({ frequency });

        const dirFilter = document.getElementById('reportDirectionFilter');
        if (dirFilter && dirFilter.value) {
            params.set('direction_filter', dirFilter.value);
        }

        const sectorFilter = document.getElementById('reportSectorFilter');
        if (sectorFilter && sectorFilter.value) {
            params.set('sector_filter', sectorFilter.value);
        }

        const alertsOnly = document.getElementById('reportAlertsOnly');
        if (alertsOnly && alertsOnly.checked) {
            params.set('alerts_only', 'true');
        }

        try {
            const response = await apiRequest(`/api/reports/latest?${params.toString()}`);
            if (!response.ok) {
                throw new Error(`API error: ${response.status}`);
            }
            const data = await response.json();
            this.currentReport = data;
            this.renderReport(data);
            this.startAutoRefresh(frequency);
        } catch (err) {
            container.innerHTML = `<tr><td colspan="9" class="report-error">Failed to load report: ${err.message}</td></tr>`;
            if (summaryBar) summaryBar.innerHTML = '';
        }
    },

    // ── Rendering ───────────────────────────────────────────────────────

    renderReport(data) {
        this.renderSummary(data);
        this.renderTable(data.securities || []);
    },

    renderSummary(data) {
        const bar = document.getElementById('reportSummaryBar');
        if (!bar) return;

        const alertsClass = data.alerts_count > 0 ? 'report-stat-alert pulse-number' : 'report-stat-value';

        bar.innerHTML = `
            <div class="report-stat">
                <span class="report-stat-label">Securities Flagged</span>
                <span class="report-stat-value">${data.securities_count || 0}</span>
            </div>
            <div class="report-stat">
                <span class="report-stat-label">Recent Alerts</span>
                <span class="${alertsClass}">${data.alerts_count || 0}</span>
            </div>
            <div class="report-stat">
                <span class="report-stat-label">Generated</span>
                <span class="report-stat-value">${data.generated_at ? new Date(data.generated_at).toLocaleString() : '--'}</span>
            </div>
            <div class="report-stat">
                <span class="report-stat-label">Frequency</span>
                <span class="report-stat-value">${(data.frequency || '').toUpperCase()}</span>
            </div>
        `;
    },

    renderTable(securities) {
        const tbody = document.getElementById('reportTableBody');
        if (!tbody) return;

        if (securities.length === 0) {
            tbody.innerHTML = '<tr><td colspan="9" class="report-empty">No securities above 80% threshold in this report.</td></tr>';
            return;
        }

        tbody.innerHTML = securities.map((sec, idx) => {
            const probClass = this.getProbabilityClass(sec.break_probability);
            const dirClass = sec.break_direction === 'bullish' ? 'positive' : sec.break_direction === 'bearish' ? 'negative' : '';
            const alertBadge = sec.is_recent_alert
                ? '<span class="alert-badge pulse">ALERT</span>'
                : '';
            const rowClass = sec.is_recent_alert ? 'alert-row' : '';
            const priceChange = sec.price_change_pct != null
                ? `<span class="${sec.price_change_pct >= 0 ? 'positive' : 'negative'}">${sec.price_change_pct >= 0 ? '+' : ''}${sec.price_change_pct.toFixed(2)}%</span>`
                : '--';

            const indicators = sec.indicators || {};
            const rsiDisplay = indicators.rsi != null ? indicators.rsi.toFixed(1) : '--';
            const cciDisplay = indicators.cci != null ? indicators.cci.toFixed(0) : '--';

            const opts = sec.options_summary || {};
            const optionsDisplay = opts.available
                ? `IV: ${opts.implied_volatility != null ? (opts.implied_volatility * 100).toFixed(1) + '%' : '--'}`
                : 'N/A';

            const sectorSent = sec.sector_sentiment || {};
            const sectorDisplay = sec.sector
                ? `<span class="sector-mini-pill ${(sectorSent.sentiment || '').toLowerCase()}">${sec.sector}</span>`
                : '--';

            return `
                <tr class="${rowClass}" data-index="${idx}">
                    <td class="report-ticker">${sec.ticker} ${alertBadge}</td>
                    <td><span class="prob-badge ${probClass}">${(sec.break_probability * 100).toFixed(1)}%</span></td>
                    <td class="${dirClass}">${(sec.break_direction || '--').toUpperCase()}</td>
                    <td>${sec.current_price != null ? '$' + sec.current_price.toFixed(2) : '--'}</td>
                    <td>${priceChange}</td>
                    <td>${sectorDisplay}</td>
                    <td>RSI ${rsiDisplay} / CCI ${cciDisplay}</td>
                    <td>${optionsDisplay}</td>
                    <td>
                        <button class="btn-watch-add" onclick="Reports.addToWatchlist('${sec.ticker}')" title="Add to Watchlist">+ Watch</button>
                    </td>
                </tr>
                <tr class="report-detail-row" id="reportDetail_${idx}" style="display:none;">
                    <td colspan="9">
                        <div class="report-detail-panel">${this.renderDetailPanel(sec)}</div>
                    </td>
                </tr>
            `;
        }).join('');

        // Row click to expand detail — load chart + daily overview on expand
        tbody.querySelectorAll('tr[data-index]').forEach(row => {
            row.addEventListener('click', (e) => {
                if (e.target.closest('.btn-watch-add')) return;
                const idx = row.dataset.index;
                const detail = document.getElementById(`reportDetail_${idx}`);
                if (!detail) return;

                const isExpanding = detail.style.display === 'none';
                detail.style.display = isExpanding ? 'table-row' : 'none';

                if (isExpanding) {
                    const sec = securities[idx];
                    if (sec) {
                        this.loadReportChart(sec.ticker, '5m');
                        this.loadDailyOverview(sec.ticker);

                        // Attach radio button listeners
                        const radios = detail.querySelectorAll(`input[name="reportChartInterval_${sec.ticker}"]`);
                        radios.forEach(radio => {
                            radio.addEventListener('change', () => {
                                this.loadReportChart(sec.ticker, radio.value);
                            });
                        });
                    }
                }
            });
        });
    },

    renderDetailPanel(sec) {
        const ind = sec.indicators || {};
        const opts = sec.options_summary || {};
        const sent = sec.sector_sentiment || {};
        const ticker = sec.ticker;

        let alertMsg = '';
        if (sec.is_recent_alert) {
            const ago = sec.first_crossed_at
                ? this.timeAgo(new Date(sec.first_crossed_at))
                : 'recently';
            alertMsg = `
                <div class="detail-alert-msg">
                    This security is about to hit a trend break.
                    First detected ${ago}. Consecutive reports: ${sec.consecutive_reports || 1}.
                </div>
            `;
        }

        return `
            ${alertMsg}
            <div class="report-chart-section">
                <div class="report-chart-header">
                    <h5>Price Chart</h5>
                    <div class="report-chart-controls">
                        <label class="report-chart-radio">
                            <input type="radio" name="reportChartInterval_${ticker}" value="5m" checked> 10min
                        </label>
                        <label class="report-chart-radio">
                            <input type="radio" name="reportChartInterval_${ticker}" value="1h"> Hourly
                        </label>
                        <label class="report-chart-radio">
                            <input type="radio" name="reportChartInterval_${ticker}" value="1d"> Daily
                        </label>
                    </div>
                </div>
                <div class="report-chart-wrapper">
                    <canvas id="reportChart_${ticker}"></canvas>
                </div>
            </div>
            <div class="detail-grid-4col">
                <div class="detail-section">
                    <h5>Indicators</h5>
                    <div class="detail-indicators">
                        ${this.detailInd('CCI', ind.cci)}
                        ${this.detailInd('RSI', ind.rsi)}
                        ${this.detailInd('Stoch %K', ind.stochastic_k)}
                        ${this.detailInd('Stoch %D', ind.stochastic_d)}
                        ${this.detailInd('ADX', ind.adx)}
                        ${this.detailInd('TLEV', ind.tlev, 4)}
                        ${this.detailInd('SMA 20', ind.sma_20, 2)}
                        ${this.detailInd('SMA 50', ind.sma_50, 2)}
                    </div>
                </div>
                <div class="detail-section">
                    <h5>Sector</h5>
                    <p>${sec.sector || '--'} (${sec.sector_etf || '--'})</p>
                    <p>Sentiment: <strong class="${(sent.sentiment || '').toLowerCase()}">${sent.sentiment || '--'}</strong></p>
                    <p>Confidence: ${sent.confidence != null ? (sent.confidence * 100).toFixed(1) + '%' : '--'}</p>
                </div>
                <div class="detail-section">
                    <h5>Options</h5>
                    ${opts.available ? `
                        <p>Expiry: ${opts.nearest_expiry || '--'}</p>
                        <p>Call: $${opts.nearest_call_strike?.toFixed(2) || '--'} @ $${opts.nearest_call_fair_value?.toFixed(2) || opts.nearest_call_price?.toFixed(2) || '--'}</p>
                        <p>Put: $${opts.nearest_put_strike?.toFixed(2) || '--'} @ $${opts.nearest_put_fair_value?.toFixed(2) || opts.nearest_put_price?.toFixed(2) || '--'}</p>
                        <p>IV: ${opts.implied_volatility != null ? (opts.implied_volatility * 100).toFixed(1) + '%' : '--'}</p>
                    ` : '<p>Options data not available</p>'}
                </div>
                <div class="detail-section">
                    <h5>Daily Overview</h5>
                    <div id="dailyOverview_${ticker}" class="daily-overview-loading">Loading OHLC...</div>
                </div>
            </div>
        `;
    },

    detailInd(label, value, decimals = 2) {
        const display = value != null ? Number(value).toFixed(decimals) : '--';
        return `<span class="detail-ind"><strong>${label}:</strong> ${display}</span>`;
    },

    // ── Chart Loading ─────────────────────────────────────────────────

    async loadReportChart(ticker, interval) {
        const canvas = document.getElementById(`reportChart_${ticker}`);
        if (!canvas) return;

        try {
            const response = await apiRequest(`/api/reports/ticker/${ticker}/chart?interval=${interval}`);
            if (!response.ok) throw new Error(`API error: ${response.status}`);
            const chartInfo = await response.json();
            this.renderReportChart(ticker, chartInfo, interval);
        } catch (err) {
            console.error(`Report chart load failed for ${ticker}:`, err);
        }
    },

    renderReportChart(ticker, chartInfo, interval) {
        const canvas = document.getElementById(`reportChart_${ticker}`);
        if (!canvas) return;

        // Destroy existing chart
        if (this.charts[ticker]) {
            this.charts[ticker].destroy();
            delete this.charts[ticker];
        }

        const rawData = chartInfo.data || [];
        if (rawData.length === 0) return;

        const { DateTime } = luxon;

        const candlestickData = rawData.map(d => ({
            x: DateTime.fromISO(d.timestamp).toMillis(),
            o: d.open,
            h: d.high,
            l: d.low,
            c: d.close,
        }));

        const datasets = [{
            label: `${ticker} OHLC`,
            data: candlestickData,
        }];

        // Add resistance lines from peaks
        if (chartInfo.peaks && chartInfo.peaks.length > 0) {
            const lastPeak = chartInfo.peaks[chartInfo.peaks.length - 1];
            datasets.push({
                label: `Resistance ($${lastPeak.price.toFixed(2)})`,
                data: candlestickData.map(d => ({ x: d.x, y: lastPeak.price })),
                type: 'line',
                borderColor: '#ef5350',
                borderWidth: 1,
                borderDash: [4, 4],
                pointRadius: 0,
                fill: false,
            });
        }

        // Add support lines from troughs
        if (chartInfo.troughs && chartInfo.troughs.length > 0) {
            const lastTrough = chartInfo.troughs[chartInfo.troughs.length - 1];
            datasets.push({
                label: `Support ($${lastTrough.price.toFixed(2)})`,
                data: candlestickData.map(d => ({ x: d.x, y: lastTrough.price })),
                type: 'line',
                borderColor: '#26a69a',
                borderWidth: 1,
                borderDash: [4, 4],
                pointRadius: 0,
                fill: false,
            });
        }

        // Determine time unit
        const timeUnit = interval === '1d' ? 'day' : interval === '1h' ? 'hour' : 'minute';

        this.charts[ticker] = new Chart(canvas.getContext('2d'), {
            type: 'candlestick',
            data: { datasets },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: true,
                        labels: { color: '#8b95a5', font: { size: 10 } },
                    },
                    tooltip: {
                        backgroundColor: '#1c2030',
                        titleColor: '#e2e8f0',
                        bodyColor: '#8b95a5',
                        borderColor: '#2a2e39',
                        borderWidth: 1,
                    },
                },
                scales: {
                    x: {
                        type: 'timeseries',
                        time: { unit: timeUnit },
                        grid: { color: '#2a2e3960' },
                        ticks: { color: '#8b95a5', maxTicksLimit: 8 },
                    },
                    y: {
                        position: 'right',
                        grid: { color: '#2a2e3960' },
                        ticks: { color: '#8b95a5' },
                    },
                },
            },
        });
    },

    // ── Daily Overview ────────────────────────────────────────────────

    async loadDailyOverview(ticker) {
        const container = document.getElementById(`dailyOverview_${ticker}`);
        if (!container) return;

        try {
            const response = await apiRequest(`/api/reports/ticker/${ticker}/chart?interval=1d`);
            if (!response.ok) throw new Error(`API error: ${response.status}`);
            const chartInfo = await response.json();

            const data = chartInfo.data || [];
            if (data.length === 0) {
                container.innerHTML = '<p class="daily-overview-loading">No daily data available</p>';
                return;
            }

            const latest = data[data.length - 1];
            const dayChange = latest.close - latest.open;
            const dayChangePct = latest.open !== 0 ? (dayChange / latest.open * 100) : 0;
            const changeClass = dayChange >= 0 ? 'positive' : 'negative';
            const dayRange = latest.high - latest.low;

            container.innerHTML = `
                <div class="daily-overview-grid">
                    <div class="daily-overview-item">
                        <span class="daily-overview-label">Open</span>
                        <span class="daily-overview-value">$${latest.open.toFixed(2)}</span>
                    </div>
                    <div class="daily-overview-item">
                        <span class="daily-overview-label">High</span>
                        <span class="daily-overview-value">$${latest.high.toFixed(2)}</span>
                    </div>
                    <div class="daily-overview-item">
                        <span class="daily-overview-label">Low</span>
                        <span class="daily-overview-value">$${latest.low.toFixed(2)}</span>
                    </div>
                    <div class="daily-overview-item">
                        <span class="daily-overview-label">Close</span>
                        <span class="daily-overview-value">$${latest.close.toFixed(2)}</span>
                    </div>
                    <div class="daily-overview-item">
                        <span class="daily-overview-label">Volume</span>
                        <span class="daily-overview-value">${this.formatVolume(latest.volume)}</span>
                    </div>
                    <div class="daily-overview-item">
                        <span class="daily-overview-label">Day Change</span>
                        <span class="daily-overview-value ${changeClass}">${dayChange >= 0 ? '+' : ''}${dayChangePct.toFixed(2)}%</span>
                    </div>
                    <div class="daily-overview-item">
                        <span class="daily-overview-label">Day Range</span>
                        <span class="daily-overview-value">$${dayRange.toFixed(2)}</span>
                    </div>
                </div>
            `;
        } catch (err) {
            console.error(`Daily overview load failed for ${ticker}:`, err);
            container.innerHTML = '<p class="daily-overview-loading">Failed to load</p>';
        }
    },

    formatVolume(vol) {
        if (vol >= 1e9) return (vol / 1e9).toFixed(2) + 'B';
        if (vol >= 1e6) return (vol / 1e6).toFixed(2) + 'M';
        if (vol >= 1e3) return (vol / 1e3).toFixed(1) + 'K';
        return String(vol);
    },

    // ── Helpers ──────────────────────────────────────────────────────────

    getProbabilityClass(prob) {
        if (prob >= 0.90) return 'danger';
        if (prob >= 0.85) return 'warning';
        return 'primary';
    },

    timeAgo(date) {
        const seconds = Math.floor((new Date() - date) / 1000);
        if (seconds < 60) return `${seconds}s ago`;
        const minutes = Math.floor(seconds / 60);
        if (minutes < 60) return `${minutes}m ago`;
        const hours = Math.floor(minutes / 60);
        if (hours < 24) return `${hours}h ago`;
        const days = Math.floor(hours / 24);
        return `${days}d ago`;
    },

    addToWatchlist(ticker) {
        if (window.Watchlist && typeof Watchlist.addTicker === 'function') {
            Watchlist.addTicker(ticker);
        }
    },

    startAutoRefresh(frequency) {
        if (this.autoRefreshTimer) {
            clearInterval(this.autoRefreshTimer);
        }
        const interval = this.REFRESH_INTERVALS[frequency] || 5 * 60 * 1000;
        this.autoRefreshTimer = setInterval(() => {
            if (document.getElementById('reportsTab') &&
                document.getElementById('reportsTab').classList.contains('active')) {
                this.loadReport(this.activeFrequency);
            }
        }, interval);
    },
};

// Self-initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    // Only init if the reports tab exists
    if (document.getElementById('reportsTab')) {
        Reports.init();
    }
});

window.Reports = Reports;
