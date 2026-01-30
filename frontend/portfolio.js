// ============================================================================
// Portfolio Tracker — Manages theoretical portfolio display and interactions
// ============================================================================

const Portfolio = {
    data: null,
    charts: {},
    refreshInterval: null,

    async init() {
        await this.loadPortfolioData();
        this.setupEventListeners();
        this.startAutoRefresh();
    },

    setupEventListeners() {
        // Chart range selector
        const rangeSelector = document.getElementById('portfolioChartRange');
        if (rangeSelector) {
            rangeSelector.addEventListener('change', () => this.updatePerformanceChart());
        }
    },

    startAutoRefresh() {
        // Refresh every 60 seconds
        this.refreshInterval = setInterval(() => {
            if (document.getElementById('portfolioTab')?.classList.contains('active')) {
                this.loadPortfolioData();
            }
        }, 60000);
    },

    async loadPortfolioData() {
        try {
            const response = await apiRequest('/api/portfolio/summary');
            this.data = response;
            this.renderAll();
        } catch (error) {
            console.error('Failed to load portfolio data:', error);
            this.renderError('Failed to load portfolio data. API may not be available.');
        }
    },

    renderAll() {
        if (!this.data) return;

        this.renderOverview();
        this.renderPerformanceChart();
        this.renderAllocationChart();
        this.renderHoldings();
        this.renderTransactions();
        this.loadSignals();
    },

    renderOverview() {
        const portfolio = this.data.portfolio_value || {};
        const account = this.data.account || {};

        const totalValue = portfolio.total_value || 100000;
        const startingBalance = parseFloat(account.starting_balance) || 100000;
        const totalPnL = totalValue - startingBalance;
        const totalPnLPct = (totalPnL / startingBalance) * 100;

        // Total value
        this.setText('portfolioTotalValue', this.formatCurrency(totalValue));

        // Total change
        const changeEl = document.getElementById('portfolioTotalChange');
        if (changeEl) {
            const sign = totalPnL >= 0 ? '+' : '';
            changeEl.textContent = `${sign}${this.formatCurrency(totalPnL)} (${sign}${totalPnLPct.toFixed(2)}%)`;
            changeEl.className = `portfolio-card-change ${totalPnL >= 0 ? 'positive' : 'negative'}`;
        }

        // Cash balance
        this.setText('portfolioCashBalance', this.formatCurrency(portfolio.cash_balance || 100000));
        this.setText('portfolioCashPct', `${((portfolio.cash_pct || 1) * 100).toFixed(1)}% of portfolio`);

        // Long-term holdings
        this.setText('portfolioLongTermValue', this.formatCurrency(portfolio.long_term_value || 0));
        this.setText('portfolioLongTermPct', `${((portfolio.long_term_pct || 0) * 100).toFixed(1)}% (Target: 75%)`);

        // Swing positions
        this.setText('portfolioSwingValue', this.formatCurrency(portfolio.swing_value || 0));
        this.setText('portfolioSwingPct', `${((portfolio.swing_pct || 0) * 100).toFixed(1)}% (Target: 25%)`);
    },

    async renderPerformanceChart() {
        const days = parseInt(document.getElementById('portfolioChartRange')?.value || 30);

        try {
            const response = await apiRequest(`/api/portfolio/performance?days=${days}`);
            const history = response.history || [];

            if (history.length === 0) {
                // Show empty state
                return;
            }

            const ctx = document.getElementById('portfolioPerformanceChart');
            if (!ctx) return;

            // Destroy existing chart
            if (this.charts.performance) {
                this.charts.performance.destroy();
            }

            const labels = history.map(d => d.snapshot_date);
            const values = history.map(d => parseFloat(d.total_value));
            const startValue = values[0] || 100000;

            this.charts.performance = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Portfolio Value',
                        data: values,
                        borderColor: '#00d4aa',
                        backgroundColor: 'rgba(0, 212, 170, 0.1)',
                        fill: true,
                        tension: 0.3,
                        pointRadius: 2,
                        pointHoverRadius: 5,
                    }, {
                        label: 'Starting Balance',
                        data: labels.map(() => startValue),
                        borderColor: 'rgba(255, 255, 255, 0.3)',
                        borderDash: [5, 5],
                        pointRadius: 0,
                        fill: false,
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            display: true,
                            labels: { color: '#e0e0e0' }
                        },
                        tooltip: {
                            callbacks: {
                                label: (ctx) => `${ctx.dataset.label}: ${this.formatCurrency(ctx.raw)}`
                            }
                        }
                    },
                    scales: {
                        x: {
                            ticks: { color: '#888' },
                            grid: { color: 'rgba(255,255,255,0.05)' }
                        },
                        y: {
                            ticks: {
                                color: '#888',
                                callback: (value) => this.formatCurrency(value)
                            },
                            grid: { color: 'rgba(255,255,255,0.05)' }
                        }
                    }
                }
            });

            // Update stats
            const latest = history[history.length - 1] || {};
            this.setText('portfolioWinRate', latest.win_rate ? `${(parseFloat(latest.win_rate) * 100).toFixed(1)}%` : '--');
            this.setText('portfolioDailyPnL', this.formatCurrency(parseFloat(latest.daily_pnl) || 0));
            this.setText('portfolioTotalPnL', this.formatCurrency(parseFloat(latest.total_pnl) || 0));

        } catch (error) {
            console.error('Failed to load performance data:', error);
        }
    },

    async updatePerformanceChart() {
        await this.renderPerformanceChart();
    },

    renderAllocationChart() {
        const portfolio = this.data?.portfolio_value || {};
        const ctx = document.getElementById('portfolioAllocationChart');
        if (!ctx) return;

        if (this.charts.allocation) {
            this.charts.allocation.destroy();
        }

        const cash = portfolio.cash_balance || 100000;
        const longTerm = portfolio.long_term_value || 0;
        const swing = portfolio.swing_value || 0;

        this.charts.allocation = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['Cash', 'Long-Term', 'Swing'],
                datasets: [{
                    data: [cash, longTerm, swing],
                    backgroundColor: [
                        'rgba(100, 100, 100, 0.8)',
                        'rgba(0, 212, 170, 0.8)',
                        'rgba(255, 193, 7, 0.8)',
                    ],
                    borderColor: [
                        'rgba(100, 100, 100, 1)',
                        'rgba(0, 212, 170, 1)',
                        'rgba(255, 193, 7, 1)',
                    ],
                    borderWidth: 1,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: { color: '#e0e0e0' }
                    },
                    tooltip: {
                        callbacks: {
                            label: (ctx) => {
                                const total = ctx.dataset.data.reduce((a, b) => a + b, 0);
                                const pct = ((ctx.raw / total) * 100).toFixed(1);
                                return `${ctx.label}: ${this.formatCurrency(ctx.raw)} (${pct}%)`;
                            }
                        }
                    }
                }
            }
        });
    },

    renderHoldings() {
        const holdings = this.data?.holdings || { long_term: [], swing: [] };

        // Long-term holdings
        this.renderHoldingsTable('portfolioLongTermBody', holdings.long_term, 'No long-term positions yet');

        // Swing holdings
        this.renderHoldingsTable('portfolioSwingBody', holdings.swing, 'No swing positions yet');

        // Update total trades count
        const transactions = this.data?.recent_transactions || [];
        this.setText('portfolioTotalTrades', transactions.length.toString());
    },

    renderHoldingsTable(tableId, holdings, emptyMessage) {
        const tbody = document.getElementById(tableId);
        if (!tbody) return;

        if (!holdings || holdings.length === 0) {
            tbody.innerHTML = `<tr class="portfolio-empty-row"><td colspan="8">${emptyMessage}</td></tr>`;
            return;
        }

        tbody.innerHTML = holdings.map(h => {
            const pnl = parseFloat(h.unrealized_pnl) || 0;
            const pnlPct = parseFloat(h.unrealized_pnl_pct) || 0;
            const pnlClass = pnl >= 0 ? 'positive' : 'negative';

            return `
                <tr>
                    <td class="ticker-cell">${h.ticker}</td>
                    <td>${parseFloat(h.quantity).toFixed(2)}</td>
                    <td>${this.formatCurrency(parseFloat(h.avg_cost_basis))}</td>
                    <td>${this.formatCurrency(parseFloat(h.current_price) || 0)}</td>
                    <td>${this.formatCurrency(parseFloat(h.market_value) || 0)}</td>
                    <td class="${pnlClass}">${this.formatCurrency(pnl)}</td>
                    <td class="${pnlClass}">${(pnlPct * 100).toFixed(2)}%</td>
                    <td><span class="signal-badge">${h.entry_signal || 'manual'}</span></td>
                </tr>
            `;
        }).join('');
    },

    renderTransactions() {
        const transactions = this.data?.recent_transactions || [];
        const tbody = document.getElementById('portfolioTransactionsBody');
        if (!tbody) return;

        if (transactions.length === 0) {
            tbody.innerHTML = '<tr class="portfolio-empty-row"><td colspan="9">No transactions yet</td></tr>';
            return;
        }

        tbody.innerHTML = transactions.map(t => {
            const realizedPnL = parseFloat(t.realized_pnl) || 0;
            const pnlClass = realizedPnL > 0 ? 'positive' : realizedPnL < 0 ? 'negative' : '';
            const actionClass = t.action.includes('buy') ? 'action-buy' : 'action-sell';

            const date = new Date(t.executed_at);
            const dateStr = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });

            return `
                <tr>
                    <td>${dateStr}</td>
                    <td class="ticker-cell">${t.ticker}</td>
                    <td class="${actionClass}">${t.action.toUpperCase()}</td>
                    <td>${t.holding_type}</td>
                    <td>${parseFloat(t.quantity).toFixed(2)}</td>
                    <td>${this.formatCurrency(parseFloat(t.price))}</td>
                    <td>${this.formatCurrency(parseFloat(t.total_value))}</td>
                    <td class="${pnlClass}">${realizedPnL !== 0 ? this.formatCurrency(realizedPnL) : '--'}</td>
                    <td><span class="signal-badge">${t.signal_source || 'manual'}</span></td>
                </tr>
            `;
        }).join('');
    },

    async loadSignals() {
        try {
            const response = await apiRequest('/api/portfolio/signals');
            this.renderSignals(response.signals || []);
        } catch (error) {
            console.error('Failed to load signals:', error);
        }
    },

    renderSignals(signals) {
        const tbody = document.getElementById('portfolioSignalsBody');
        if (!tbody) return;

        if (signals.length === 0) {
            tbody.innerHTML = '<tr class="portfolio-empty-row"><td colspan="8">No pending signals</td></tr>';
            return;
        }

        tbody.innerHTML = signals.map(s => {
            const strength = parseFloat(s.signal_strength) || 0;
            const strengthClass = strength >= 0.9 ? 'strength-high' : strength >= 0.75 ? 'strength-medium' : 'strength-low';

            const expires = new Date(s.expires_at);
            const expiresStr = expires.toLocaleString('en-US', {
                month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
            });

            return `
                <tr>
                    <td class="ticker-cell">${s.ticker}</td>
                    <td>${s.signal_type}</td>
                    <td class="${s.suggested_action.includes('buy') ? 'action-buy' : 'action-sell'}">${s.suggested_action.toUpperCase()}</td>
                    <td>${s.holding_type}</td>
                    <td class="${strengthClass}">${(strength * 100).toFixed(0)}%</td>
                    <td>${s.signal_price ? this.formatCurrency(parseFloat(s.signal_price)) : '--'}</td>
                    <td>${expiresStr}</td>
                    <td><span class="status-badge status-${s.status}">${s.status}</span></td>
                </tr>
            `;
        }).join('');
    },

    renderError(message) {
        // Could show error state in UI
        console.error(message);
    },

    // Utility functions
    formatCurrency(value) {
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: 'USD',
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        }).format(value);
    },

    setText(id, text) {
        const el = document.getElementById(id);
        if (el) el.textContent = text;
    },

    destroy() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
        }
        Object.values(this.charts).forEach(chart => chart?.destroy());
    }
};

// Initialize when DOM is ready and portfolio tab is available
document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('portfolioTab')) {
        // Initialize when tab becomes active
        const observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                if (mutation.target.id === 'portfolioTab' &&
                    mutation.target.classList.contains('active') &&
                    !Portfolio.data) {
                    Portfolio.init();
                }
            });
        });

        const portfolioTab = document.getElementById('portfolioTab');
        if (portfolioTab) {
            observer.observe(portfolioTab, { attributes: true, attributeFilter: ['class'] });

            // Also init if tab is already active
            if (portfolioTab.classList.contains('active')) {
                Portfolio.init();
            }
        }
    }
});

window.Portfolio = Portfolio;
