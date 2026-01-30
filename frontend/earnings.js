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
        this.setupDetailClose();
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

    setupDetailClose() {
        const closeBtn = document.getElementById('earningsDetailClose');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => this.closeDetail());
        }
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
        const panel = document.getElementById('earningsDetailPanel');
        if (!panel) return;

        // Toggle off if same ticker
        if (this.expandedTicker === ticker && panel.style.display !== 'none') {
            this.closeDetail();
            return;
        }

        // Remove highlight from previously selected row
        document.querySelectorAll('.earnings-row.selected').forEach(r => r.classList.remove('selected'));

        // Highlight the selected row
        const selectedRow = document.querySelector(`.earnings-row[data-ticker="${ticker}"]`);
        if (selectedRow) {
            selectedRow.classList.add('selected');
        }

        this.expandedTicker = ticker;
        document.getElementById('earningsDetailTicker').textContent = ticker + ' — Earnings Detail';
        document.getElementById('cboeMetrics').innerHTML = '<p>Loading CBOE data...</p>';
        document.getElementById('earningsNewsGrid').innerHTML = '<p>Loading news...</p>';

        // Clear any previous chart
        if (this.charts.earningsCandlestickChart) {
            this.charts.earningsCandlestickChart.destroy();
            delete this.charts.earningsCandlestickChart;
        }

        panel.style.display = 'block';
        // Scroll panel into view at the top of the viewport
        panel.scrollIntoView({ behavior: 'smooth', block: 'start' });

        try {
            const response = await apiRequest('/api/earnings/ticker/' + ticker, 'GET');
            if (!response.ok) throw new Error('Failed to load ticker detail');

            const data = await response.json();
            this.renderCBOE(data.cboe_activity);
            this.renderDetailChart(data.daily_chart);
            this.renderNews(data.news);
        } catch (error) {
            document.getElementById('cboeMetrics').innerHTML = '<p>Failed to load details: ' + error.message + '</p>';
        }
    },

    closeDetail() {
        const panel = document.getElementById('earningsDetailPanel');
        if (panel) panel.style.display = 'none';

        // Remove highlight from selected row
        document.querySelectorAll('.earnings-row.selected').forEach(r => r.classList.remove('selected'));

        this.expandedTicker = null;

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

        container.innerHTML =
            '<div class="cboe-grid">' +
                '<div class="cboe-metric">' +
                    '<div class="cboe-metric-label">P/C Ratio</div>' +
                    '<div class="cboe-metric-value ' + pcrClass + '">' + (cboe.pc_ratio !== null ? cboe.pc_ratio.toFixed(2) : 'N/A') + '</div>' +
                '</div>' +
                '<div class="cboe-metric">' +
                    '<div class="cboe-metric-label">Call Volume</div>' +
                    '<div class="cboe-metric-value">' + this.formatNumber(cboe.call_volume) + '</div>' +
                '</div>' +
                '<div class="cboe-metric">' +
                    '<div class="cboe-metric-label">Put Volume</div>' +
                    '<div class="cboe-metric-value">' + this.formatNumber(cboe.put_volume) + '</div>' +
                '</div>' +
                '<div class="cboe-metric">' +
                    '<div class="cboe-metric-label">Total OI</div>' +
                    '<div class="cboe-metric-value">' + this.formatNumber(cboe.total_oi) + '</div>' +
                '</div>' +
                '<div class="cboe-metric">' +
                    '<div class="cboe-metric-label">Expiration</div>' +
                    '<div class="cboe-metric-value">' + cboe.expiration + '</div>' +
                '</div>' +
            '</div>';
    },

    // ──────────────────────────────────────────────────────────
    // CANDLESTICK CHART FOR EARNINGS DETAIL
    // ──────────────────────────────────────────────────────────

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
