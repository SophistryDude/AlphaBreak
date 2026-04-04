// ============================================================================
// Watchlist Tab — User Security Watchlist
// ============================================================================
// Manages watchlist of tickers with server sync for authenticated users
// and localStorage fallback for anonymous users.
// Each ticker shows: price, trend break, sector, indicators, options.

const Watchlist = {
    STORAGE_KEY: 'alphabreak_watchlist',
    tickers: [],
    data: {},
    charts: {},
    autoRefreshTimer: null,
    REFRESH_INTERVAL: 60 * 1000, // 1 minute
    syncing: false, // Prevent concurrent sync operations

    // ── Initialization ──────────────────────────────────────────────────

    async init() {
        await this.loadFromStorage();
        this.setupForm();
        this.render();

        if (this.tickers.length > 0) {
            this.fetchAllData();
        }
    },

    setupForm() {
        const form = document.getElementById('watchlistAddForm');
        if (form) {
            form.addEventListener('submit', (e) => {
                e.preventDefault();
                const input = document.getElementById('watchlistTickerInput');
                if (input && input.value.trim()) {
                    this.addTicker(input.value.trim());
                    input.value = '';
                }
            });
        }

        // Auto-uppercase
        const input = document.getElementById('watchlistTickerInput');
        if (input) {
            input.addEventListener('input', (e) => {
                e.target.value = e.target.value.toUpperCase();
            });
        }
    },

    // ── Persistence ─────────────────────────────────────────────────────

    async loadFromStorage() {
        // If authenticated, load from server
        if (typeof Auth !== 'undefined' && Auth.isAuthenticated) {
            try {
                const response = await apiRequest('/api/user/watchlist');
                if (response.ok) {
                    const data = await response.json();
                    this.tickers = data.tickers || [];
                    // Also update localStorage as cache
                    this.saveToLocalStorage();
                    return;
                }
            } catch (err) {
                console.warn('Failed to load watchlist from server, using localStorage:', err);
            }
        }

        // Fall back to localStorage
        this.loadFromLocalStorage();
    },

    loadFromLocalStorage() {
        try {
            const stored = localStorage.getItem(this.STORAGE_KEY);
            this.tickers = stored ? JSON.parse(stored) : [];
        } catch {
            this.tickers = [];
        }
    },

    saveToStorage() {
        // Always save to localStorage as cache
        this.saveToLocalStorage();

        // If authenticated, also sync to server (fire-and-forget)
        if (typeof Auth !== 'undefined' && Auth.isAuthenticated) {
            // Server sync is handled by add/remove methods directly
            // This is just for the localStorage cache
        }
    },

    saveToLocalStorage() {
        try {
            localStorage.setItem(this.STORAGE_KEY, JSON.stringify(this.tickers));
        } catch (e) {
            console.warn('Failed to save watchlist to localStorage:', e);
        }
    },

    // ── Server Sync Methods ────────────────────────────────────────────

    async addTickerToServer(ticker) {
        if (typeof Auth === 'undefined' || !Auth.isAuthenticated) return true;

        try {
            const response = await apiRequest('/api/user/watchlist', 'POST', {
                tickers: [ticker]
            });
            return response.ok;
        } catch (err) {
            console.warn('Failed to add ticker to server:', err);
            return false;
        }
    },

    async removeTickerFromServer(ticker) {
        if (typeof Auth === 'undefined' || !Auth.isAuthenticated) return true;

        try {
            const response = await apiRequest(`/api/user/watchlist/${ticker}`, 'DELETE');
            return response.ok;
        } catch (err) {
            console.warn('Failed to remove ticker from server:', err);
            return false;
        }
    },

    async migrateToServer() {
        // Called after login to merge localStorage watchlist with server
        if (typeof Auth === 'undefined' || !Auth.isAuthenticated) return;
        if (this.syncing) return;

        this.syncing = true;

        try {
            // Load current localStorage watchlist
            const localTickers = [];
            try {
                const stored = localStorage.getItem(this.STORAGE_KEY);
                if (stored) {
                    localTickers.push(...JSON.parse(stored));
                }
            } catch {}

            if (localTickers.length === 0) {
                // Nothing to migrate, just load from server
                await this.loadFromStorage();
                this.render();
                if (this.tickers.length > 0) {
                    this.fetchAllData();
                }
                return;
            }

            // Call migrate endpoint to merge localStorage with server
            const response = await apiRequest('/api/user/watchlist/migrate', 'POST', {
                tickers: localTickers
            });

            if (response.ok) {
                const data = await response.json();
                this.tickers = data.tickers || [];
                this.saveToLocalStorage();
                console.log('Watchlist migrated to server:', this.tickers.length, 'tickers');
            } else {
                // Failed to migrate, just load from server
                await this.loadFromStorage();
            }

            this.render();
            if (this.tickers.length > 0) {
                this.fetchAllData();
            }
        } catch (err) {
            console.error('Watchlist migration failed:', err);
        } finally {
            this.syncing = false;
        }
    },

    async reloadFromServer() {
        // Called after login/logout to refresh watchlist
        await this.loadFromStorage();
        this.data = {}; // Clear cached data
        this.render();
        if (this.tickers.length > 0) {
            this.fetchAllData();
        }
    },

    // ── Ticker Management ───────────────────────────────────────────────

    async addTicker(ticker) {
        ticker = ticker.toUpperCase().trim();
        if (!ticker || ticker.length > 5) {
            this.showSnackbar('Invalid ticker format', 'error');
            return;
        }
        if (!/^[A-Z]{1,5}(-[A-Z])?$/.test(ticker)) {
            this.showSnackbar('Invalid ticker format', 'error');
            return;
        }

        if (this.tickers.includes(ticker)) {
            // Already in watchlist — flash the card
            const card = document.querySelector(`[data-watchlist-ticker="${ticker}"]`);
            if (card) {
                card.classList.add('watchlist-flash');
                setTimeout(() => card.classList.remove('watchlist-flash'), 600);
            }
            this.showSnackbar(`${ticker} is already in watchlist`, 'info');
            return;
        }

        // Validate ticker exists by fetching data first
        try {
            const response = await apiRequest(`/api/watchlist/ticker/${ticker}`);
            if (!response.ok) {
                this.showSnackbar(`${ticker} is not a valid security or data unavailable`, 'error');
                return;
            }
            const data = await response.json();

            // If we got here, ticker is valid - add it
            this.tickers.push(ticker);
            this.saveToStorage();
            this.data[ticker] = data; // Cache the fetched data
            this.render();
            this.startAutoRefresh();
            this.showSnackbar(`${ticker} added to watchlist`, 'success');

            // Sync to server — log failures so client/server don't silently desync
            this.addTickerToServer(ticker).catch(err => {
                console.error(`Failed to sync add ${ticker} to server:`, err);
                this.showSnackbar(`${ticker} added locally but failed to sync to server`, 'warning');
            });
        } catch (err) {
            this.showSnackbar(`Failed to validate ${ticker}`, 'error');
        }
    },

    async removeTicker(ticker) {
        this.tickers = this.tickers.filter(t => t !== ticker);
        delete this.data[ticker];
        this.saveToStorage();
        this.render();

        if (this.tickers.length === 0 && this.autoRefreshTimer) {
            clearInterval(this.autoRefreshTimer);
            this.autoRefreshTimer = null;
        }

        // Sync to server — log failures so client/server don't silently desync
        this.removeTickerFromServer(ticker).catch(err => {
            console.error(`Failed to sync remove ${ticker} from server:`, err);
            this.showSnackbar(`${ticker} removed locally but failed to sync to server`, 'warning');
        });
    },

    // ── Data Fetching ───────────────────────────────────────────────────

    async fetchAllData() {
        if (this.tickers.length === 0) return;

        try {
            const response = await apiRequest('/api/watchlist/data', 'POST', {
                tickers: this.tickers,
            });
            if (!response.ok) throw new Error(`API error: ${response.status}`);

            const result = await response.json();
            (result.securities || []).forEach(sec => {
                this.data[sec.ticker] = sec;
            });

            this.render();
            this.startAutoRefresh();
        } catch (err) {
            console.error('Watchlist fetch failed:', err);
        }
    },

    async fetchSingleTicker(ticker) {
        try {
            const response = await apiRequest(`/api/watchlist/ticker/${ticker}`);
            if (!response.ok) throw new Error(`API error: ${response.status}`);

            const data = await response.json();
            this.data[ticker] = data;
            this.render();
        } catch (err) {
            console.error(`Failed to fetch ${ticker}:`, err);
            // Show ticker with error state
            this.data[ticker] = { ticker, error: true };
            this.render();
        }
    },

    // ── Rendering ───────────────────────────────────────────────────────

    render() {
        const container = document.getElementById('watchlistGrid');
        const emptyState = document.getElementById('watchlistEmpty');
        if (!container) return;

        // Destroy existing charts before rebuilding DOM
        Object.keys(this.charts).forEach(key => {
            if (this.charts[key]) {
                this.charts[key].destroy();
                delete this.charts[key];
            }
        });

        if (this.tickers.length === 0) {
            container.innerHTML = '';
            if (emptyState) emptyState.style.display = 'block';
            return;
        }

        if (emptyState) emptyState.style.display = 'none';

        container.innerHTML = this.tickers.map(ticker => {
            const d = this.data[ticker];
            if (!d || d.error) {
                return this.createLoadingWidget(ticker, d && d.error);
            }
            return this.createWidget(ticker, d);
        }).join('');

        // Attach remove handlers
        container.querySelectorAll('.watchlist-remove-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.removeTicker(btn.dataset.ticker);
            });
        });

        // Attach chart radio listeners and auto-load hourly charts
        this.tickers.forEach(ticker => {
            if (!this.data[ticker] || this.data[ticker].error) return;

            const radios = container.querySelectorAll(`input[name="watchlistChartInterval_${ticker}"]`);
            radios.forEach(radio => {
                radio.addEventListener('change', () => {
                    this.loadChart(ticker, radio.value);
                });
            });

            // Auto-load hourly chart
            this.loadChart(ticker, '1h');
        });
    },

    createLoadingWidget(ticker, hasError) {
        return `
            <div class="watchlist-widget" data-watchlist-ticker="${ticker}">
                <div class="watchlist-widget-header">
                    <span class="watchlist-ticker">${ticker}</span>
                    <button class="watchlist-remove-btn" data-ticker="${ticker}" title="Remove">&times;</button>
                </div>
                <div class="watchlist-widget-body">
                    <p class="watchlist-loading-text">${hasError ? 'Failed to load data' : 'Loading...'}</p>
                </div>
            </div>
        `;
    },

    createWidget(ticker, d) {
        const price = d.price || {};
        const tb = d.trend_break || {};
        const sector = d.sector || {};
        const ind = d.indicators || {};
        const opts = d.options || {};

        // Price display
        const priceVal = price.current != null ? `$${price.current.toFixed(2)}` : '--';
        const changeVal = price.change_pct != null
            ? `${price.change_pct >= 0 ? '+' : ''}${price.change_pct.toFixed(2)}%`
            : '';
        const changeClass = (price.change_pct || 0) >= 0 ? 'positive' : 'negative';

        // Trend break
        const tbProb = tb.probability != null ? `${(tb.probability * 100).toFixed(1)}%` : '--';
        const tbClass = this.getProbBadgeClass(tb.probability);
        const tbDir = (tb.direction || '--').toUpperCase();
        const tbDirClass = tb.direction === 'bullish' ? 'positive' : tb.direction === 'bearish' ? 'negative' : '';

        // Sector
        const sectorName = sector.name || '--';
        const sectorSent = (sector.sentiment || 'NEUTRAL').toLowerCase();

        // Indicators
        const indItems = [
            { label: 'CCI', value: ind.cci, decimals: 0 },
            { label: 'RSI', value: ind.rsi, decimals: 1 },
            { label: '%K', value: ind.stochastic_k, decimals: 1 },
            { label: 'ADX', value: ind.adx, decimals: 1 },
        ].filter(i => i.value != null);

        // Options
        const ivDisplay = opts.implied_volatility != null
            ? `IV: ${(opts.implied_volatility * 100).toFixed(1)}%`
            : '';
        const callDisplay = opts.nearest_call_strike != null
            ? `C: $${opts.nearest_call_strike.toFixed(0)}`
            : '';
        const putDisplay = opts.nearest_put_strike != null
            ? `P: $${opts.nearest_put_strike.toFixed(0)}`
            : '';

        return `
            <div class="watchlist-widget" data-watchlist-ticker="${ticker}">
                <div class="watchlist-widget-header">
                    <span class="watchlist-ticker">${ticker}</span>
                    <button class="watchlist-remove-btn" data-ticker="${ticker}" title="Remove">&times;</button>
                </div>
                <div class="watchlist-widget-body">
                    <div class="watchlist-price-row">
                        <span class="watchlist-price">${priceVal}</span>
                        <span class="watchlist-change ${changeClass}">${changeVal}</span>
                    </div>

                    <div class="watchlist-trend-break">
                        <span class="watchlist-tb-label">Trend Break:</span>
                        <span class="prob-badge ${tbClass}">${tbProb}</span>
                        <span class="watchlist-tb-dir ${tbDirClass}">${tbDir}</span>
                    </div>

                    <div class="watchlist-sector">
                        <span class="sector-mini-pill ${sectorSent}">${sectorName}</span>
                    </div>

                    <div class="watchlist-indicators">
                        ${indItems.map(i => `
                            <span class="indicator-mini">
                                <span class="indicator-mini-label">${i.label}</span>
                                <span class="indicator-mini-value">${Number(i.value).toFixed(i.decimals)}</span>
                            </span>
                        `).join('')}
                    </div>

                    ${opts.available ? `
                        <div class="watchlist-options">
                            ${ivDisplay ? `<span class="options-chip">${ivDisplay}</span>` : ''}
                            ${callDisplay ? `<span class="options-chip call">${callDisplay}</span>` : ''}
                            ${putDisplay ? `<span class="options-chip put">${putDisplay}</span>` : ''}
                        </div>
                    ` : ''}

                    <div class="watchlist-chart-section">
                        <div class="watchlist-chart-controls">
                            <span class="chart-label">Chart</span>
                            <label class="watchlist-radio">
                                <input type="radio" name="watchlistChartInterval_${ticker}" value="1d"> Daily
                            </label>
                            <label class="watchlist-radio">
                                <input type="radio" name="watchlistChartInterval_${ticker}" value="1h" checked> Hourly
                            </label>
                            <label class="watchlist-radio">
                                <input type="radio" name="watchlistChartInterval_${ticker}" value="5m"> 10min
                            </label>
                        </div>
                        <div class="watchlist-chart-wrapper">
                            <canvas id="watchlistChart_${ticker}"></canvas>
                        </div>
                    </div>
                </div>
                <div class="watchlist-widget-footer">
                    <span class="watchlist-updated">${d.fetched_at ? 'Updated ' + new Date(d.fetched_at).toLocaleTimeString() : ''}</span>
                </div>
            </div>
        `;
    },

    getProbBadgeClass(prob) {
        if (prob == null) return '';
        if (prob >= 0.90) return 'danger';
        if (prob >= 0.85) return 'warning';
        if (prob >= 0.80) return 'primary';
        return '';
    },

    // ── Chart Loading ─────────────────────────────────────────────────

    async loadChart(ticker, interval) {
        const canvas = document.getElementById(`watchlistChart_${ticker}`);
        if (!canvas) return;

        try {
            const response = await apiRequest(`/api/watchlist/ticker/${ticker}/chart?interval=${interval}`);
            if (!response.ok) throw new Error(`API error: ${response.status}`);
            const chartInfo = await response.json();
            this.renderWatchlistChart(ticker, chartInfo, interval);
        } catch (err) {
            console.error(`Watchlist chart load failed for ${ticker}:`, err);
        }
    },

    renderWatchlistChart(ticker, chartInfo, interval) {
        const canvas = document.getElementById(`watchlistChart_${ticker}`);
        if (!canvas) return;

        // Destroy existing chart for this ticker
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
            label: `${ticker}`,
            data: candlestickData,
        }];

        // Add resistance line from peaks
        if (chartInfo.peaks && chartInfo.peaks.length > 0) {
            const lastPeak = chartInfo.peaks[chartInfo.peaks.length - 1];
            datasets.push({
                label: `R $${lastPeak.price.toFixed(2)}`,
                data: candlestickData.map(d => ({ x: d.x, y: lastPeak.price })),
                type: 'line',
                borderColor: '#ef5350',
                borderWidth: 1,
                borderDash: [4, 4],
                pointRadius: 0,
                fill: false,
            });
        }

        // Add support line from troughs
        if (chartInfo.troughs && chartInfo.troughs.length > 0) {
            const lastTrough = chartInfo.troughs[chartInfo.troughs.length - 1];
            datasets.push({
                label: `S $${lastTrough.price.toFixed(2)}`,
                data: candlestickData.map(d => ({ x: d.x, y: lastTrough.price })),
                type: 'line',
                borderColor: '#26a69a',
                borderWidth: 1,
                borderDash: [4, 4],
                pointRadius: 0,
                fill: false,
            });
        }

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
                        labels: { color: '#8b95a5', font: { size: 9 } },
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
                        ticks: { color: '#8b95a5', maxTicksLimit: 6, font: { size: 9 } },
                    },
                    y: {
                        position: 'right',
                        grid: { color: '#2a2e3960' },
                        ticks: { color: '#8b95a5', font: { size: 9 } },
                    },
                },
            },
        });
    },

    // ── Auto-refresh ────────────────────────────────────────────────────

    startAutoRefresh() {
        if (this.autoRefreshTimer) return;
        if (this.tickers.length === 0) return;

        this.autoRefreshTimer = setInterval(() => {
            if (document.getElementById('watchlistTab') &&
                document.getElementById('watchlistTab').classList.contains('active')) {
                this.fetchAllData();
            }
        }, this.REFRESH_INTERVAL);
    },

    // ── Snackbar Notifications ─────────────────────────────────────────

    showSnackbar(message, type = 'info') {
        // Create snackbar if it doesn't exist
        let snackbar = document.getElementById('snackbar');
        if (!snackbar) {
            snackbar = document.createElement('div');
            snackbar.id = 'snackbar';
            document.body.appendChild(snackbar);
        }

        // Set message and type
        snackbar.textContent = message;
        snackbar.className = `snackbar snackbar-${type} show`;

        // Auto-hide after 3 seconds
        setTimeout(() => {
            snackbar.classList.remove('show');
        }, 3000);
    },
};

// Self-initialize
document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('watchlistTab')) {
        Watchlist.init();
    }
});

window.Watchlist = Watchlist;
