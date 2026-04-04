// ============================================================================
// Long Term Trading Tab
// ============================================================================
// Displays institutional 13F holdings, benchmark comparison charts,
// Japanese candlestick charts, and user-saved holdings.

const LongTerm = {
    charts: {},
    holdingsData: null,
    selectedTicker: null,
    savedHoldings: [],
    savedHoldingsData: {},
    activeSectorFilter: null,
    STORAGE_KEY: 'alphabreak_longterm_holdings',

    SECTOR_COLORS: {
        'Technology':               '#2962ff',
        'Health Care':              '#00bcd4',
        'Financials':               '#ff9800',
        'Consumer Discretionary':   '#e91e63',
        'Communication Services':   '#9c27b0',
        'Industrials':              '#607d8b',
        'Consumer Staples':         '#4caf50',
        'Energy':                   '#f44336',
        'Utilities':                '#795548',
        'Real Estate':              '#009688',
        'Materials':                '#ffc107',
        'Unknown':                  '#8b95a5',
    },

    // ── Initialization ──────────────────────────────────────────────────

    init() {
        this.loadSavedHoldings();
        this.setupControls();
        this.setupDetailClose();
        this.loadHoldingsTable();
        this.renderSavedGrid();
    },

    setupControls() {
        const input = document.getElementById('longtermTickerInput');
        const analyzeBtn = document.getElementById('longtermAnalyzeBtn');
        const saveBtn = document.getElementById('longtermSaveBtn');

        if (input) {
            input.addEventListener('input', (e) => {
                e.target.value = e.target.value.toUpperCase();
            });
            input.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    this.analyzeCurrentTicker();
                }
            });
        }

        if (analyzeBtn) {
            analyzeBtn.addEventListener('click', () => this.analyzeCurrentTicker());
        }

        if (saveBtn) {
            saveBtn.addEventListener('click', () => {
                if (this.selectedTicker) {
                    this.addSavedHolding(this.selectedTicker);
                }
            });
        }
    },

    setupDetailClose() {
        const closeBtn = document.getElementById('longtermFundDetailClose');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => this.closeFundDetail());
        }
    },

    analyzeCurrentTicker() {
        const input = document.getElementById('longtermTickerInput');
        const ticker = input ? input.value.trim().toUpperCase() : '';
        if (ticker && /^[A-Z]{1,5}(-[A-Z])?$/.test(ticker)) {
            this.loadTickerDetail(ticker);
        }
    },

    // ── Saved Holdings (localStorage) ───────────────────────────────────

    loadSavedHoldings() {
        try {
            const stored = localStorage.getItem(this.STORAGE_KEY);
            this.savedHoldings = stored ? JSON.parse(stored) : [];
        } catch {
            this.savedHoldings = [];
        }
    },

    saveSavedHoldings() {
        try {
            localStorage.setItem(this.STORAGE_KEY, JSON.stringify(this.savedHoldings));
        } catch (e) {
            console.warn('Failed to save holdings:', e);
        }
    },

    addSavedHolding(ticker) {
        ticker = ticker.toUpperCase().trim();
        if (!ticker || this.savedHoldings.includes(ticker)) return;
        this.savedHoldings.push(ticker);
        this.saveSavedHoldings();
        this.loadSavedHoldingData(ticker);
        this.renderSavedGrid();
    },

    removeSavedHolding(ticker) {
        this.savedHoldings = this.savedHoldings.filter(t => t !== ticker);
        delete this.savedHoldingsData[ticker];
        this.saveSavedHoldings();
        this.renderSavedGrid();
    },

    // ── Data Loading ────────────────────────────────────────────────────

    async loadHoldingsTable() {
        const loading = document.getElementById('longtermHoldingsLoading');
        const container = document.getElementById('longtermHoldingsTableContainer');
        if (loading) loading.style.display = 'block';
        if (container) container.style.display = 'none';

        try {
            const response = await apiRequest('/api/longterm/holdings');
            if (!response.ok) throw new Error(`API error: ${response.status}`);
            const data = await response.json();
            this.holdingsData = data;
            this.renderHoldingsTable(data);
            this.renderSectorBar(data.holdings || []);

            const badge = document.getElementById('longtermQuarterBadge');
            if (badge) badge.textContent = data.report_quarter || '';

            if (loading) loading.style.display = 'none';
            if (container) container.style.display = 'block';
        } catch (err) {
            console.error('Holdings load failed:', err);
            if (loading) loading.textContent = 'Failed to load institutional holdings: ' + err.message;
        }
    },

    async loadTickerDetail(ticker) {
        this.selectedTicker = ticker;

        // Show save button
        const saveBtn = document.getElementById('longtermSaveBtn');
        if (saveBtn) saveBtn.style.display = 'inline-block';

        // Show loading in chart sections
        const compSection = document.getElementById('longtermComparisonSection');
        const candleSection = document.getElementById('longtermCandlestickSection');
        if (compSection) compSection.style.display = 'block';
        if (candleSection) candleSection.style.display = 'block';

        const weeks = parseInt(document.getElementById('longtermPeriod')?.value || '52', 10);

        try {
            const response = await apiRequest(`/api/longterm/ticker/${ticker}?weeks=${weeks}`);
            if (!response.ok) throw new Error(`API error: ${response.status}`);
            const data = await response.json();

            // Render comparison chart
            if (data.comparison) {
                this.renderComparisonChart(data.comparison);
            }

            // Render candlestick chart
            if (data.daily_chart) {
                this.renderCandlestickChart(data.daily_chart);
            }

            // Show fund holdings detail
            if (data.fund_holdings && data.fund_holdings.funds && data.fund_holdings.funds.length > 0) {
                this.showFundDetail(ticker, data.fund_holdings.funds);
            }

            // Store for saved grid if needed
            this.savedHoldingsData[ticker] = {
                sector: data.sector,
                industry: data.industry,
                has_dividend: data.has_dividend,
                price: data.current_price,
                change_pct: data.change_pct,
                total_funds_holding: data.fund_holdings ? data.fund_holdings.total_funds : null,
                institutional_sentiment: null,
            };

            // Scroll to comparison section
            if (compSection) {
                compSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        } catch (err) {
            console.error(`Detail load failed for ${ticker}:`, err);
        }
    },

    async loadSavedHoldingData(ticker) {
        try {
            const response = await apiRequest(`/api/longterm/ticker/${ticker}?weeks=52`);
            if (!response.ok) return;
            const data = await response.json();
            this.savedHoldingsData[ticker] = {
                sector: data.sector,
                industry: data.industry,
                has_dividend: data.has_dividend,
                price: data.current_price,
                change_pct: data.change_pct,
                total_funds_holding: data.fund_holdings ? data.fund_holdings.total_funds : null,
                institutional_sentiment: null,
            };
            this.renderSavedGrid();
        } catch (err) {
            console.error(`Saved holding data load failed for ${ticker}:`, err);
        }
    },

    // ── Holdings Table Rendering ────────────────────────────────────────

    renderHoldingsTable(data) {
        const tbody = document.getElementById('longtermHoldingsBody');
        if (!tbody) return;

        const holdings = data.holdings || [];
        if (holdings.length === 0) {
            tbody.innerHTML = '<tr><td colspan="10" class="longterm-empty-row">No institutional holdings data available.</td></tr>';
            return;
        }

        // Filter by sector if active
        const filtered = this.activeSectorFilter
            ? holdings.filter(h => h.sector === this.activeSectorFilter)
            : holdings;

        tbody.innerHTML = filtered.map(h => {
            const sectorColor = this.getSectorColor(h.sector);
            const dividendIcon = h.has_dividend ? '<span class="longterm-dividend-icon" title="Pays Dividend"></span>' : '';
            const sentimentVal = h.institutional_sentiment != null ? h.institutional_sentiment.toFixed(2) : '--';
            const sentimentClass = h.institutional_sentiment > 0.3 ? 'positive' :
                                   h.institutional_sentiment < -0.3 ? 'negative' : '';
            const netChangePct = h.net_shares_change_pct != null
                ? ((h.net_shares_change_pct >= 0 ? '+' : '') + (h.net_shares_change_pct * 100).toFixed(1) + '%')
                : '--';
            const netChangeClass = (h.net_shares_change_pct || 0) >= 0 ? 'positive' : 'negative';
            const fundsDisplay = h.total_funds_holding != null ? h.total_funds_holding : '--';

            return `
                <tr class="longterm-holding-row">
                    <td><strong class="longterm-ticker">${h.ticker}</strong>${dividendIcon}</td>
                    <td><span class="longterm-sector-tag" style="border-left: 3px solid ${sectorColor}">${h.sector || '--'}</span></td>
                    <td><strong>${fundsDisplay}</strong></td>
                    <td><span class="${sentimentClass}">${sentimentVal}</span></td>
                    <td>${h.funds_initiated != null ? h.funds_initiated : '--'}</td>
                    <td class="positive">${h.funds_increased != null ? h.funds_increased : '--'}</td>
                    <td class="negative">${h.funds_decreased != null ? h.funds_decreased : '--'}</td>
                    <td class="negative">${h.funds_sold != null ? h.funds_sold : '--'}</td>
                    <td><span class="${netChangeClass}">${netChangePct}</span></td>
                    <td><button class="btn btn-sm" data-ticker="${h.ticker}">Analyze</button></td>
                </tr>
            `;
        }).join('');

        // Attach analyze button handlers
        tbody.querySelectorAll('button[data-ticker]').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const ticker = btn.dataset.ticker;
                const input = document.getElementById('longtermTickerInput');
                if (input) input.value = ticker;
                this.loadTickerDetail(ticker);
            });
        });
    },

    renderSectorBar(holdings) {
        const bar = document.getElementById('longtermSectorBar');
        if (!bar) return;

        // Collect unique sectors
        const sectors = {};
        holdings.forEach(h => {
            const s = h.sector || 'Unknown';
            sectors[s] = (sectors[s] || 0) + 1;
        });

        const sortedSectors = Object.entries(sectors)
            .sort((a, b) => b[1] - a[1])
            .map(([s]) => s);

        bar.innerHTML = '<span class="longterm-sector-label">Sectors:</span>' +
            '<button class="longterm-sector-pill' + (!this.activeSectorFilter ? ' active' : '') +
            '" data-sector="" style="' + (!this.activeSectorFilter ? 'background: var(--primary-color); border-color: var(--primary-color);' : '') +
            '">All</button>' +
            sortedSectors.map(s => {
                const color = this.getSectorColor(s);
                const isActive = this.activeSectorFilter === s;
                const activeStyle = isActive ? `background: ${color}; border-color: ${color};` : '';
                return `<button class="longterm-sector-pill${isActive ? ' active' : ''}" data-sector="${s}" style="${activeStyle}">${s} (${sectors[s]})</button>`;
            }).join('');

        // Attach click handlers
        bar.querySelectorAll('.longterm-sector-pill').forEach(pill => {
            pill.addEventListener('click', () => {
                const sector = pill.dataset.sector;
                this.activeSectorFilter = sector || null;
                this.renderSectorBar(holdings);
                if (this.holdingsData) {
                    this.renderHoldingsTable(this.holdingsData);
                }
            });
        });
    },

    // ── Comparison Chart (Line) ─────────────────────────────────────────

    renderComparisonChart(comparison) {
        const section = document.getElementById('longtermComparisonSection');
        if (section) section.style.display = 'block';

        this.destroyChart('comparison');

        const canvas = document.getElementById('longtermComparisonChart');
        if (!canvas || !comparison || !comparison.series) return;

        const { DateTime } = luxon;
        const ticker = comparison.ticker;

        const colorMap = {};
        colorMap[ticker] = '#2962ff';
        colorMap['SPY'] = '#e2e8f0';
        colorMap['GLD'] = '#ffc107';
        colorMap['BTC'] = '#ff9800';

        const datasets = Object.entries(comparison.series).map(([key, points]) => ({
            label: key,
            data: points.map(p => ({
                x: DateTime.fromISO(p.date).toMillis(),
                y: p.pct_return,
            })),
            borderColor: colorMap[key] || '#8b95a5',
            borderWidth: key === ticker ? 2.5 : 1.5,
            pointRadius: 0,
            pointHoverRadius: 4,
            fill: false,
            tension: 0.3,
        }));

        const title = document.getElementById('longtermComparisonTitle');
        if (title) title.textContent = `${ticker} vs S&P 500, Gold, Bitcoin \u2014 Weekly % Return`;

        this.charts['comparison'] = new Chart(canvas.getContext('2d'), {
            type: 'line',
            data: { datasets },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: true,
                        position: 'top',
                        labels: { color: '#8b95a5', font: { size: 11 }, boxWidth: 14 },
                    },
                    tooltip: {
                        backgroundColor: '#1c2030',
                        titleColor: '#e2e8f0',
                        bodyColor: '#8b95a5',
                        borderColor: '#2a2e39',
                        borderWidth: 1,
                        callbacks: {
                            label: (ctx) => `${ctx.dataset.label}: ${ctx.parsed.y.toFixed(1)}%`,
                        },
                    },
                },
                scales: {
                    x: {
                        type: 'time',
                        time: { unit: 'month' },
                        grid: { color: '#2a2e3960' },
                        ticks: { color: '#8b95a5', font: { size: 10 } },
                    },
                    y: {
                        grid: { color: '#2a2e3960' },
                        ticks: {
                            callback: (v) => v.toFixed(0) + '%',
                            color: '#8b95a5',
                            font: { size: 10 },
                        },
                        title: {
                            display: true,
                            text: 'Cumulative Return %',
                            color: '#5c6578',
                            font: { size: 10 },
                        },
                    },
                },
                interaction: { intersect: false, mode: 'index' },
            },
        });

        // Render summary cards
        if (comparison.summary) {
            this.renderSummaryRow(comparison.summary, ticker);
        }
    },

    renderSummaryRow(summary, ticker) {
        const container = document.getElementById('longtermSummaryRow');
        if (!container) return;

        const order = [ticker, 'SPY', 'GLD', 'BTC'];
        const labels = {};
        labels[ticker] = ticker;
        labels['SPY'] = 'S&P 500';
        labels['GLD'] = 'Gold';
        labels['BTC'] = 'Bitcoin';

        container.innerHTML = order.map(key => {
            const s = summary[key];
            if (!s) return '';
            const retClass = s.total_return >= 0 ? 'positive' : 'negative';
            const retSign = s.total_return >= 0 ? '+' : '';
            return `
                <div class="longterm-summary-card">
                    <div class="longterm-summary-label">${labels[key] || key}</div>
                    <div class="longterm-summary-value ${retClass}">${retSign}${s.total_return.toFixed(1)}%</div>
                    <div class="longterm-summary-sub">Vol: ${s.volatility.toFixed(1)}% | Sharpe: ${s.sharpe_approx.toFixed(2)}</div>
                </div>
            `;
        }).join('');
    },

    // ── Candlestick Chart ───────────────────────────────────────────────

    renderCandlestickChart(dailyChart) {
        const section = document.getElementById('longtermCandlestickSection');
        if (section) section.style.display = 'block';

        if (!dailyChart || !dailyChart.data || dailyChart.data.length === 0) return;
        if (typeof AlphaCharts === 'undefined') return;

        const chartData = dailyChart.data.map(d => ({
            timestamp: d.date,
            open: d.open, high: d.high, low: d.low, close: d.close,
            volume: d.volume || 0,
        }));

        AlphaCharts.destroy('longtermLwChart');
        AlphaCharts.create('longtermLwChart', { height: 300, volumeHeight: 45 });
        AlphaCharts.setData('longtermLwChart', chartData);
    },

    // ── Fund Detail Panel ───────────────────────────────────────────────

    showFundDetail(ticker, funds) {
        const panel = document.getElementById('longtermFundDetail');
        const title = document.getElementById('longtermFundDetailTitle');
        const list = document.getElementById('longtermFundList');
        if (!panel || !list) return;

        if (title) title.textContent = `${ticker} \u2014 Institutional Holders`;

        // Header row
        let html = '<div class="longterm-fund-row" style="font-weight:600; color: var(--text-muted); font-size: 0.72rem; text-transform: uppercase;">' +
            '<span>Fund Name</span><span>Shares</span><span>Value</span><span>Position</span>' +
            '</div>';

        funds.forEach(f => {
            const posClass = (f.position_type || '').toLowerCase();
            html += `
                <div class="longterm-fund-row">
                    <span class="longterm-fund-name">${f.fund_name}</span>
                    <span>${this.formatNumber(f.shares_held)}</span>
                    <span>${this.formatCurrency(f.market_value)}</span>
                    <span><span class="longterm-position-badge ${posClass}">${f.position_type || '--'}</span></span>
                </div>
            `;
        });

        list.innerHTML = html;
        panel.style.display = 'block';
    },

    closeFundDetail() {
        const panel = document.getElementById('longtermFundDetail');
        if (panel) panel.style.display = 'none';
    },

    // ── Saved Holdings Grid ─────────────────────────────────────────────

    renderSavedGrid() {
        const grid = document.getElementById('longtermSavedGrid');
        const empty = document.getElementById('longtermSavedEmpty');
        if (!grid) return;

        if (this.savedHoldings.length === 0) {
            grid.innerHTML = '';
            if (empty) empty.style.display = 'block';
            return;
        }
        if (empty) empty.style.display = 'none';

        grid.innerHTML = this.savedHoldings.map(ticker => {
            const d = this.savedHoldingsData[ticker];
            return this.createSavedCard(ticker, d);
        }).join('');

        // Attach remove handlers
        grid.querySelectorAll('.longterm-saved-remove').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.removeSavedHolding(btn.dataset.ticker);
            });
        });

        // Attach card click to analyze
        grid.querySelectorAll('.longterm-saved-card').forEach(card => {
            card.addEventListener('click', () => {
                const ticker = card.dataset.ticker;
                const input = document.getElementById('longtermTickerInput');
                if (input) input.value = ticker;
                this.loadTickerDetail(ticker);
                document.getElementById('longtermTab')?.scrollIntoView({ behavior: 'smooth' });
            });
        });
    },

    createSavedCard(ticker, d) {
        const sector = d ? (d.sector || 'Unknown') : 'Unknown';
        const sectorColor = this.getSectorColor(sector);
        const dividendBadge = d && d.has_dividend
            ? '<span class="longterm-dividend-badge">DIV</span>'
            : '';
        const price = d && d.price ? '$' + d.price.toFixed(2) : '--';
        const changePct = d && d.change_pct != null
            ? ((d.change_pct >= 0 ? '+' : '') + d.change_pct.toFixed(2) + '%')
            : '';
        const changeClass = d && d.change_pct >= 0 ? 'positive' : 'negative';
        const fundsHolding = d && d.total_funds_holding != null ? d.total_funds_holding : '--';

        return `
            <div class="longterm-saved-card" data-ticker="${ticker}" style="border-top: 3px solid ${sectorColor}">
                <div class="longterm-saved-card-header">
                    <span class="longterm-saved-ticker">${ticker}</span>
                    <button class="longterm-saved-remove" data-ticker="${ticker}" title="Remove">&times;</button>
                </div>
                <div class="longterm-saved-card-body">
                    <div class="longterm-saved-price">${price}</div>
                    <div class="longterm-saved-change ${changeClass}">${changePct}</div>
                    <div class="longterm-saved-sector" style="color: ${sectorColor}">${sector}</div>
                    ${dividendBadge}
                    <div class="longterm-saved-funds">
                        <span class="longterm-saved-funds-label">Funds:</span>
                        <span class="longterm-saved-funds-value">${fundsHolding}</span>
                    </div>
                </div>
            </div>
        `;
    },

    // ── Utilities ────────────────────────────────────────────────────────

    getSectorColor(sector) {
        return this.SECTOR_COLORS[sector] || this.SECTOR_COLORS['Unknown'];
    },

    formatNumber(n) {
        if (n == null) return '--';
        if (n >= 1e9) return (n / 1e9).toFixed(2) + 'B';
        if (n >= 1e6) return (n / 1e6).toFixed(2) + 'M';
        if (n >= 1e3) return (n / 1e3).toFixed(1) + 'K';
        return String(n);
    },

    formatCurrency(v) {
        if (v == null) return '--';
        if (v >= 1e9) return '$' + (v / 1e9).toFixed(2) + 'B';
        if (v >= 1e6) return '$' + (v / 1e6).toFixed(2) + 'M';
        if (v >= 1e3) return '$' + (v / 1e3).toFixed(1) + 'K';
        return '$' + v.toFixed(2);
    },

    destroyChart(key) {
        if (this.charts[key]) {
            this.charts[key].destroy();
            delete this.charts[key];
        }
    },
};

// Self-initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('longtermTab')) {
        LongTerm.init();
    }
});

window.LongTerm = LongTerm;
