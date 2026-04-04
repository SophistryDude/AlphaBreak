// Quarterly Earnings Calendar Module
// Displays upcoming earnings for top 100 stocks + user-added tickers.
// Expandable rows show CBOE options activity, daily candlestick chart, and news.

const Earnings = {
    charts: {},
    customTickers: [],
    expandedTicker: null,
    calendarData: null,
    STORAGE_KEY: 'alphabreak_earnings_custom',

    // ──────────────────────────────────────────────────────────
    // INITIALIZATION
    // ──────────────────────────────────────────────────────────

    init() {
        this.loadCustomTickers();
        this.setupForm();
        this.loadCalendar();
    },

    setupForm() {
        const form = document.getElementById('earningsAddForm');
        if (!form) return;

        const input = document.getElementById('earningsTickerInput');
        if (input) {
            input.addEventListener('input', (e) => {
                e.target.value = e.target.value.toUpperCase();
            });
        }

        form.addEventListener('submit', (e) => {
            e.preventDefault();
            const ticker = input.value.trim().toUpperCase();
            if (ticker && /^[A-Z]{1,5}$/.test(ticker)) {
                this.addCustomTicker(ticker);
                input.value = '';
            }
        });
    },

    // ──────────────────────────────────────────────────────────
    // CUSTOM TICKER MANAGEMENT (localStorage)
    // ──────────────────────────────────────────────────────────

    loadCustomTickers() {
        try {
            const stored = localStorage.getItem(this.STORAGE_KEY);
            this.customTickers = stored ? JSON.parse(stored) : [];
        } catch (e) {
            this.customTickers = [];
        }
        this.renderCustomTickers();
    },

    saveCustomTickers() {
        localStorage.setItem(this.STORAGE_KEY, JSON.stringify(this.customTickers));
    },

    addCustomTicker(ticker) {
        if (!this.customTickers.includes(ticker)) {
            this.customTickers.push(ticker);
            this.saveCustomTickers();
            this.renderCustomTickers();
            this.loadCalendar();
        }
    },

    removeCustomTicker(ticker) {
        this.customTickers = this.customTickers.filter(t => t !== ticker);
        this.saveCustomTickers();
        this.renderCustomTickers();
        this.loadCalendar();
    },

    renderCustomTickers() {
        const container = document.getElementById('earningsCustomTickers');
        if (!container) return;

        if (this.customTickers.length === 0) {
            container.innerHTML = '';
            return;
        }

        container.innerHTML = '<span class="custom-tickers-label">Custom:</span>' +
            this.customTickers.map(t =>
                '<span class="custom-ticker-chip">' + t +
                '<button class="custom-ticker-remove" data-ticker="' + t + '">&times;</button></span>'
            ).join('');

        container.querySelectorAll('.custom-ticker-remove').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.removeCustomTicker(btn.dataset.ticker);
            });
        });
    },

    // ──────────────────────────────────────────────────────────
    // CALENDAR DATA LOADING
    // ──────────────────────────────────────────────────────────

    async loadCalendar() {
        const loading = document.getElementById('earningsLoading');
        const tableContainer = document.getElementById('earningsTableContainer');
        if (loading) loading.style.display = 'block';
        if (tableContainer) tableContainer.style.display = 'none';

        try {
            let url = '/api/earnings/calendar';
            if (this.customTickers.length > 0) {
                url += '?custom_tickers=' + this.customTickers.join(',');
            }

            const response = await apiRequest(url, 'GET');
            if (!response.ok) throw new Error('Failed to load earnings calendar');

            const data = await response.json();
            this.calendarData = data;

            this.renderFuturesBar(data.futures_context);
            this.renderCalendarTable(data.earnings);

            if (loading) loading.style.display = 'none';
            if (tableContainer) tableContainer.style.display = 'block';
        } catch (error) {
            if (loading) loading.innerHTML = '<p>Failed to load earnings calendar. ' + error.message + '</p>';
        }
    },

    // ──────────────────────────────────────────────────────────
    // FUTURES BAR
    // ──────────────────────────────────────────────────────────

    renderFuturesBar(futures) {
        if (!futures) return;

        const priceEl = document.getElementById('futuresPrice');
        const changeEl = document.getElementById('futuresChange');

        if (priceEl) {
            priceEl.textContent = '$' + futures.last_price.toLocaleString(undefined, {
                minimumFractionDigits: 2, maximumFractionDigits: 2
            });
        }

        if (changeEl) {
            const sign = futures.change >= 0 ? '+' : '';
            changeEl.textContent = sign + futures.change.toFixed(2) + ' (' + sign + futures.change_pct.toFixed(2) + '%)';
            changeEl.className = 'futures-change ' + (futures.change >= 0 ? 'positive' : 'negative');
        }
    },

    // ──────────────────────────────────────────────────────────
    // CALENDAR TABLE
    // ──────────────────────────────────────────────────────────

    renderCalendarTable(earnings) {
        const tbody = document.getElementById('earningsTableBody');
        if (!tbody) return;
        tbody.innerHTML = '';

        if (!earnings || earnings.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="earnings-empty-row">No upcoming earnings found in the next 60 days.</td></tr>';
            return;
        }

        earnings.forEach(entry => {
            const row = document.createElement('tr');
            row.className = 'earnings-row clickable' + (entry.is_upcoming ? ' upcoming' : ' reported');
            if (entry.is_custom) row.classList.add('custom');
            row.dataset.ticker = entry.ticker;

            const epsEstimate = entry.eps_estimate !== null ? '$' + entry.eps_estimate.toFixed(2) : '--';
            const epsActual = entry.eps_actual !== null ? '$' + entry.eps_actual.toFixed(2) : '--';
            let surpriseHtml = '--';
            if (entry.surprise_pct !== null) {
                const surpriseClass = entry.surprise_pct >= 0 ? 'positive' : 'negative';
                const sign = entry.surprise_pct >= 0 ? '+' : '';
                surpriseHtml = '<span class="' + surpriseClass + '">' + sign + entry.surprise_pct.toFixed(1) + '%</span>';
            }

            const statusBadge = entry.is_upcoming
                ? '<span class="earnings-status upcoming-badge">Upcoming</span>'
                : '<span class="earnings-status reported-badge">Reported</span>';

            row.innerHTML =
                '<td>' + this.formatDate(entry.date) + '</td>' +
                '<td><strong>' + entry.ticker + '</strong>' + (entry.is_custom ? ' <span class="custom-tag">custom</span>' : '') + '</td>' +
                '<td>' + epsEstimate + '</td>' +
                '<td>' + epsActual + '</td>' +
                '<td>' + surpriseHtml + '</td>' +
                '<td>' + statusBadge + '</td>' +
                '<td><span class="row-expand-hint">▶</span></td>';

            // Make entire row clickable
            row.addEventListener('click', () => {
                this.expandRow(entry.ticker);
            });

            tbody.appendChild(row);
        });
    },

    // ──────────────────────────────────────────────────────────
    // DETAIL PANEL (CBOE, Candlestick Chart, News)
    // ──────────────────────────────────────────────────────────

    async expandRow(ticker) {
        // Toggle off if same ticker
        if (this.expandedTicker === ticker) {
            this.closeDetail();
            return;
        }

        // Pro feature gate
        if (typeof Premium !== 'undefined' && !Premium.canAccess('earnings_detail')) {
            this.closeDetail();
            const selectedRow = document.querySelector(`.earnings-row[data-ticker="${ticker}"]`);
            if (!selectedRow) return;
            selectedRow.classList.add('selected');
            this.expandedTicker = ticker;
            const detailRow = document.createElement('tr');
            detailRow.className = 'earnings-detail-row';
            detailRow.id = 'earningsDetailRow';
            detailRow.innerHTML = '<td colspan="7"><div style="padding:16px;" id="earningsLockedPanel"></div></td>';
            selectedRow.after(detailRow);
            Premium.showLocked('earningsLockedPanel', 'earnings_detail');
            return;
        }

        // Close any existing detail row
        this.closeDetail();

        // Find the clicked row
        const selectedRow = document.querySelector(`.earnings-row[data-ticker="${ticker}"]`);
        if (!selectedRow) return;

        // Highlight the selected row
        selectedRow.classList.add('selected');
        this.expandedTicker = ticker;

        // Create detail row
        const detailRow = document.createElement('tr');
        detailRow.className = 'earnings-detail-row';
        detailRow.id = 'earningsDetailRow';
        detailRow.innerHTML = `
            <td colspan="7">
                <div class="earnings-detail-panel-inline">
                    <div class="earnings-detail-header">
                        <h3>${ticker} — Earnings Detail</h3>
                        <button class="btn btn-sm" onclick="Earnings.closeDetail()">Close</button>
                    </div>
                    <div class="earnings-detail-grid">
                        <!-- CBOE Activity -->
                        <div class="earnings-cboe">
                            <h4>CBOE Options Activity</h4>
                            <div class="cboe-metrics" id="cboeMetrics"><p>Loading CBOE data...</p></div>
                        </div>
                        <!-- Candlestick Chart + Volume (Lightweight Charts) -->
                        <div class="earnings-chart-container">
                            <h4>3-Month Daily Chart</h4>
                            <div id="earningsLwChart" class="lw-chart-container" style="min-height:300px;"></div>
                        </div>
                    </div>
                    <!-- News Section -->
                    <div class="earnings-news-section">
                        <h4>Recent News</h4>
                        <div class="earnings-news-grid" id="earningsNewsGrid"><p>Loading news...</p></div>
                    </div>
                </div>
            </td>
        `;

        // Insert detail row after the selected row
        selectedRow.after(detailRow);

        // Scroll to the detail row
        detailRow.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

        // Record trial if applicable
        if (typeof Premium !== 'undefined') {
            const access = Premium.checkAccess('earnings_detail');
            if (access.isTrial) Premium.recordTrial('earnings_detail');
        }

        // Load data
        try {
            const response = await apiRequest('/api/earnings/ticker/' + ticker, 'GET');
            if (!response.ok) throw new Error('Failed to load ticker detail');

            const data = await response.json();
            this.renderCBOE(data.cboe_activity);
            this.renderLwChart(data.daily_chart);
            this.renderNews(data.news);
        } catch (error) {
            document.getElementById('cboeMetrics').innerHTML = '<p>Failed to load details: ' + error.message + '</p>';
        }
    },

    closeDetail() {
        // Remove inline detail row
        const detailRow = document.getElementById('earningsDetailRow');
        if (detailRow) {
            detailRow.remove();
        }

        // Remove highlight from selected row
        document.querySelectorAll('.earnings-row.selected').forEach(r => r.classList.remove('selected'));

        this.expandedTicker = null;

        // Destroy Lightweight Chart instance
        if (typeof AlphaCharts !== 'undefined') {
            AlphaCharts.destroy('earningsLwChart');
        }
        // Legacy cleanup
        if (this.charts.earningsCandlestickChart) {
            this.charts.earningsCandlestickChart.destroy();
            delete this.charts.earningsCandlestickChart;
        }
    },

    // ──────────────────────────────────────────────────────────
    // CBOE ACTIVITY
    // ──────────────────────────────────────────────────────────

    renderCBOE(cboe) {
        const container = document.getElementById('cboeMetrics');
        if (!container) return;

        if (!cboe) {
            container.innerHTML = '<p>No options data available.</p>';
            return;
        }

        const pcrClass = cboe.pc_ratio !== null
            ? (cboe.pc_ratio > 1 ? 'bearish' : cboe.pc_ratio < 0.7 ? 'bullish' : 'neutral')
            : 'neutral';

        // P/C Ratio tooltip
        let pcrTooltip = '';
        if (cboe.pc_ratio !== null) {
            if (cboe.pc_ratio > 1.3) pcrTooltip = 'Very high P/C ratio — extreme bearish sentiment. More puts than calls being traded. Contrarian traders may see this as a potential bottom signal.';
            else if (cboe.pc_ratio > 1.0) pcrTooltip = 'Elevated P/C ratio — bearish sentiment. More puts than calls. Traders are hedging or betting on downside.';
            else if (cboe.pc_ratio > 0.7) pcrTooltip = 'Balanced P/C ratio — neutral sentiment. Neither bulls nor bears dominate the options market.';
            else if (cboe.pc_ratio > 0.5) pcrTooltip = 'Low P/C ratio — bullish sentiment. More calls than puts being traded. Traders expect upside.';
            else pcrTooltip = 'Very low P/C ratio — extreme bullish sentiment. Contrarian traders may see excessive optimism as a warning sign.';
        }

        // Put/Call volume analysis
        let volumeAnalysis = '';
        if (cboe.call_volume && cboe.put_volume) {
            const totalVol = cboe.call_volume + cboe.put_volume;
            const callPct = ((cboe.call_volume / totalVol) * 100).toFixed(0);
            const putPct = ((cboe.put_volume / totalVol) * 100).toFixed(0);
            const dominant = cboe.call_volume > cboe.put_volume ? 'call' : 'put';
            const ratio = dominant === 'call'
                ? (cboe.call_volume / cboe.put_volume).toFixed(1)
                : (cboe.put_volume / cboe.call_volume).toFixed(1);

            volumeAnalysis = '<div class="cboe-analysis">' +
                '<div class="cboe-analysis-header">Options Flow Analysis</div>' +
                '<div class="cboe-vol-bar">' +
                    '<div class="cboe-vol-call" style="width:' + callPct + '%">' +
                        '<span>Calls ' + callPct + '%</span>' +
                    '</div>' +
                    '<div class="cboe-vol-put" style="width:' + putPct + '%">' +
                        '<span>Puts ' + putPct + '%</span>' +
                    '</div>' +
                '</div>' +
                '<p class="cboe-analysis-text">' +
                    (dominant === 'call'
                        ? '<span class="positive">Call-heavy flow</span> — ' + ratio + 'x more call volume than puts. Traders are positioning for upside. '
                        : '<span class="negative">Put-heavy flow</span> — ' + ratio + 'x more put volume than calls. Traders are hedging or betting on downside. ') +
                    'Total options volume: ' + this.formatNumber(totalVol) + '. ' +
                    (totalVol > 50000 ? 'High activity suggests strong conviction.' : 'Moderate activity levels.') +
                '</p>' +
            '</div>';
        }

        container.innerHTML =
            '<div class="cboe-grid">' +
                '<div class="cboe-metric has-tooltip" data-tooltip="' + pcrTooltip.replace(/"/g, '&quot;') + '">' +
                    '<div class="cboe-metric-label">P/C Ratio</div>' +
                    '<div class="cboe-metric-value ' + pcrClass + '">' + (cboe.pc_ratio !== null ? cboe.pc_ratio.toFixed(2) : 'N/A') + '</div>' +
                '</div>' +
                '<div class="cboe-metric" title="Total call (bullish) options contracts traded. High call volume suggests traders expect the stock to rise.">' +
                    '<div class="cboe-metric-label">Call Volume</div>' +
                    '<div class="cboe-metric-value">' + this.formatNumber(cboe.call_volume) + '</div>' +
                '</div>' +
                '<div class="cboe-metric" title="Total put (bearish) options contracts traded. High put volume suggests hedging or downside bets.">' +
                    '<div class="cboe-metric-label">Put Volume</div>' +
                    '<div class="cboe-metric-value">' + this.formatNumber(cboe.put_volume) + '</div>' +
                '</div>' +
                '<div class="cboe-metric" title="Total Open Interest — the number of outstanding options contracts. Rising OI with rising price = strong trend.">' +
                    '<div class="cboe-metric-label">Total OI</div>' +
                    '<div class="cboe-metric-value">' + this.formatNumber(cboe.total_oi) + '</div>' +
                '</div>' +
                '<div class="cboe-metric" title="Nearest options expiration date. Options activity concentrates near expiration — watch for increased volatility.">' +
                    '<div class="cboe-metric-label">Expiration</div>' +
                    '<div class="cboe-metric-value">' + cboe.expiration + '</div>' +
                '</div>' +
            '</div>' +
            volumeAnalysis;
    },

    // ──────────────────────────────────────────────────────────
    // LIGHTWEIGHT CHART FOR EARNINGS DETAIL
    // ──────────────────────────────────────────────────────────

    renderLwChart(chartInfo) {
        if (!chartInfo || !chartInfo.data || chartInfo.data.length === 0) return;
        if (typeof AlphaCharts === 'undefined') return;

        const chartData = chartInfo.data.map(d => ({
            timestamp: d.date,
            open: d.open, high: d.high, low: d.low, close: d.close,
            volume: d.volume || 0,
        }));

        AlphaCharts.create('earningsLwChart', { height: 250, volumeHeight: 40 });
        AlphaCharts.setData('earningsLwChart', chartData);
    },

    // Legacy renderDetailChart kept for fallback
    renderDetailChart(chartInfo) {
        const canvasId = 'earningsCandlestickChart';
        const ctx = document.getElementById(canvasId);
        if (!ctx || !chartInfo || !chartInfo.data || chartInfo.data.length === 0) return;

        if (this.charts[canvasId]) {
            this.charts[canvasId].destroy();
        }

        const chartData = chartInfo.data;
        const peaks = chartInfo.peaks || [];
        const troughs = chartInfo.troughs || [];

        // Convert dates to luxon timestamps for the time axis
        const timestamps = chartData.map(d => luxon.DateTime.fromISO(d.date).toMillis());

        // Candlestick dataset — {x, o, h, l, c} format
        const candlestickData = chartData.map((d, i) => ({
            x: timestamps[i],
            o: d.open,
            h: d.high,
            l: d.low,
            c: d.close,
        }));

        // Resistance trend line (peaks) — {x, y} points only at peak dates
        const peakDateSet = new Set(peaks.map(p => p.date));
        const resistanceData = chartData
            .map((d, i) => peakDateSet.has(d.date) ? { x: timestamps[i], y: peaks.find(p => p.date === d.date).price } : null)
            .filter(p => p !== null);

        // Support trend line (troughs) — {x, y} points only at trough dates
        const troughDateSet = new Set(troughs.map(t => t.date));
        const supportData = chartData
            .map((d, i) => troughDateSet.has(d.date) ? { x: timestamps[i], y: troughs.find(t => t.date === d.date).price } : null)
            .filter(p => p !== null);

        const datasets = [
            {
                label: this.expandedTicker || 'Price',
                data: candlestickData,
            },
        ];

        if (resistanceData.length >= 2) {
            datasets.push({
                label: 'Resistance',
                data: resistanceData,
                type: 'line',
                borderColor: '#ef5350',
                borderWidth: 1.5,
                borderDash: [6, 3],
                pointRadius: 3,
                pointBackgroundColor: '#ef5350',
                fill: false,
                tension: 0,
                order: 2,
            });
        }

        if (supportData.length >= 2) {
            datasets.push({
                label: 'Support',
                data: supportData,
                type: 'line',
                borderColor: '#26a69a',
                borderWidth: 1.5,
                borderDash: [6, 3],
                pointRadius: 3,
                pointBackgroundColor: '#26a69a',
                fill: false,
                tension: 0,
                order: 3,
            });
        }

        this.charts[canvasId] = new Chart(ctx, {
            type: 'candlestick',
            data: {
                datasets: datasets,
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: true,
                        position: 'top',
                        labels: { boxWidth: 12, font: { size: 10 }, color: '#8b95a5' },
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
                        type: 'time',
                        time: { unit: 'day' },
                        grid: { display: false },
                        ticks: { maxTicksLimit: 8, font: { size: 10 }, color: '#8b95a5' },
                    },
                    y: {
                        grid: { color: '#2a2e3960' },
                        ticks: {
                            callback: function(v) { return '$' + v.toLocaleString(); },
                            font: { size: 10 },
                            color: '#8b95a5',
                        },
                    },
                },
                interaction: { intersect: false, mode: 'index' },
            },
        });
    },

    // ──────────────────────────────────────────────────────────
    // VOLUME CHART FOR EARNINGS DETAIL
    // ──────────────────────────────────────────────────────────

    renderDetailVolume(chartInfo) {
        const ctx = document.getElementById('earningsVolumeChart');
        if (!ctx || !chartInfo || !chartInfo.data || chartInfo.data.length === 0) return;

        if (this.charts.earningsVolumeChart) {
            this.charts.earningsVolumeChart.destroy();
        }

        const chartData = chartInfo.data;
        const timestamps = chartData.map(d => luxon.DateTime.fromISO(d.date).toMillis());
        const volumes = chartData.map(d => d.volume || 0);
        const colors = chartData.map((d, i) => {
            if (i === 0) return 'rgba(92, 101, 120, 0.4)';
            return d.close >= chartData[i - 1].close
                ? 'rgba(38, 166, 154, 0.4)'
                : 'rgba(239, 83, 80, 0.4)';
        });

        this.charts.earningsVolumeChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: timestamps,
                datasets: [{
                    data: volumes,
                    backgroundColor: colors,
                    borderWidth: 0,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false }, tooltip: { enabled: false } },
                scales: {
                    x: { display: false },
                    y: { display: false, beginAtZero: true },
                },
            },
        });
    },

    // ──────────────────────────────────────────────────────────
    // NEWS
    // ──────────────────────────────────────────────────────────

    renderNews(news) {
        const container = document.getElementById('earningsNewsGrid');
        if (!container) return;

        if (!news || news.length === 0) {
            container.innerHTML = '<p>No recent news found.</p>';
            return;
        }

        container.innerHTML = news.map(item => {
            const thumbnailHtml = item.thumbnail
                ? '<img class="news-thumbnail" src="' + item.thumbnail + '" alt="" loading="lazy">'
                : '';
            const timeAgo = item.publish_time ? this.timeAgo(item.publish_time) : '';

            return '<a class="news-card" href="' + item.link + '" target="_blank" rel="noopener">' +
                thumbnailHtml +
                '<div class="news-card-body">' +
                    '<div class="news-title">' + item.title + '</div>' +
                    '<div class="news-meta">' +
                        '<span class="news-publisher">' + item.publisher + '</span>' +
                        (timeAgo ? '<span class="news-time">' + timeAgo + '</span>' : '') +
                    '</div>' +
                '</div>' +
            '</a>';
        }).join('');
    },

    // ──────────────────────────────────────────────────────────
    // UTILITIES
    // ──────────────────────────────────────────────────────────

    formatDate(dateStr) {
        const d = new Date(dateStr + 'T00:00:00');
        return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    },

    formatNumber(n) {
        if (n >= 1e6) return (n / 1e6).toFixed(1) + 'M';
        if (n >= 1e3) return (n / 1e3).toFixed(1) + 'K';
        return n.toLocaleString();
    },

    timeAgo(isoStr) {
        const now = new Date();
        const then = new Date(isoStr);
        const diffMs = now - then;
        const diffMin = Math.floor(diffMs / 60000);
        if (diffMin < 60) return diffMin + 'm ago';
        const diffHr = Math.floor(diffMin / 60);
        if (diffHr < 24) return diffHr + 'h ago';
        const diffDay = Math.floor(diffHr / 24);
        return diffDay + 'd ago';
    },
};

// Expose globally so other modules can call Earnings.addCustomTicker()
window.Earnings = Earnings;

// Auto-initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    if (typeof apiRequest !== 'undefined') {
        Earnings.init();
    } else {
        const checkReady = setInterval(() => {
            if (typeof apiRequest !== 'undefined') {
                clearInterval(checkReady);
                Earnings.init();
            }
        }, 100);
        setTimeout(() => clearInterval(checkReady), 5000);
    }
});
