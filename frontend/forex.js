// ============================================================================
// Forex Tab — Currency Correlation Analysis
// ============================================================================
// Displays forex pairs, correlations, and trend breaks.

const Forex = {
    charts: {},
    selectedPair: null,
    currentTimeframe: '10min',

    // Chart colors for USD pairs
    CHART_COLORS: [
        '#4fc3f7',  // Light blue - EUR/USD
        '#f06292',  // Pink - USD/JPY
        '#81c784',  // Green - GBP/USD
        '#ffb74d',  // Orange - USD/CHF
        '#ba68c8',  // Purple - USD/CAD
    ],

    // DXY backdrop color
    DXY_COLOR: 'rgba(100, 181, 246, 0.15)',  // Light blue filled area
    DXY_BORDER: 'rgba(100, 181, 246, 0.4)',

    // ──────────────────────────────────────────────────────────
    // INITIALIZATION
    // ──────────────────────────────────────────────────────────

    init() {
        this.loadUsdChart();
        this.loadSummary();
        this.loadRecentMovements();
        this.loadPairs();
        this.loadCorrelations();
        this.loadTrendBreaks();
        this.setupFilters();
        this.setupTimeframeToggle();
    },

    setupFilters() {
        const strengthFilter = document.getElementById('forexStrengthFilter');
        if (strengthFilter) {
            strengthFilter.addEventListener('change', () => {
                this.loadCorrelations(strengthFilter.value);
            });
        }

        const pairFilter = document.getElementById('forexPairFilter');
        if (pairFilter) {
            pairFilter.addEventListener('change', () => {
                this.loadTrendBreaks(pairFilter.value);
            });
        }
    },

    setupTimeframeToggle() {
        const radios = document.querySelectorAll('input[name="forexTimeframe"]');
        radios.forEach(radio => {
            radio.addEventListener('change', (e) => {
                this.currentTimeframe = e.target.value;
                this.loadUsdChart();
            });
        });
    },

    // ──────────────────────────────────────────────────────────
    // USD PAIRS CHART (Main Chart)
    // ──────────────────────────────────────────────────────────

    async loadUsdChart() {
        const canvas = document.getElementById('forexUsdChart');
        const legendEl = document.getElementById('forexChartLegend');
        if (!canvas) return;

        try {
            const response = await apiRequest(`/api/forex/usd-chart?timeframe=${this.currentTimeframe}`, 'GET');
            if (!response.ok) throw new Error('Failed to load USD chart data');

            const data = await response.json();
            this.renderUsdChart(data);
            this.renderChartLegend(data.pairs, legendEl);
            this.updateUsdStrengthIndicator(data);
        } catch (error) {
            console.error('USD Chart load failed:', error);
            if (legendEl) {
                legendEl.innerHTML = `<span class="error-text">Failed to load chart data</span>`;
            }
        }
    },

    renderUsdChart(data) {
        const canvas = document.getElementById('forexUsdChart');
        if (!canvas || !data.chart_data || data.chart_data.length === 0) return;

        // Destroy existing chart
        if (this.charts.usdChart) {
            this.charts.usdChart.destroy();
        }

        const ctx = canvas.getContext('2d');

        // Calculate DXY proxy (weighted average of USD pairs - inverted for XXX/USD pairs)
        const dxyData = data.chart_data.map(d => {
            let sum = 0;
            let count = 0;
            data.pairs.forEach(pair => {
                const val = d[pair.replace('/', '_')];
                if (val != null) {
                    // For XXX/USD pairs (EUR/USD, GBP/USD), invert to show USD strength
                    // For USD/XXX pairs, use as-is
                    const isUsdBase = pair.startsWith('USD/');
                    sum += isUsdBase ? val : (200 - val); // Invert XXX/USD pairs
                    count++;
                }
            });
            return {
                x: new Date(d.timestamp),
                y: count > 0 ? sum / count : null,
            };
        }).filter(d => d.y != null);

        // DXY backdrop dataset (filled area)
        const dxyDataset = {
            label: 'DXY (USD Index)',
            data: dxyData,
            borderColor: this.DXY_BORDER,
            backgroundColor: this.DXY_COLOR,
            fill: true,
            tension: 0.3,
            pointRadius: 0,
            borderWidth: 1,
            order: 10, // Render behind other lines
            yAxisID: 'y',
        };

        // Build datasets for each pair
        const pairDatasets = data.pairs.map((pair, idx) => {
            const chartData = data.chart_data.map(d => ({
                x: new Date(d.timestamp),
                y: d[pair.replace('/', '_')],
            })).filter(d => d.y != null);

            return {
                label: pair,
                data: chartData,
                borderColor: this.CHART_COLORS[idx % this.CHART_COLORS.length],
                backgroundColor: 'transparent',
                fill: false,
                tension: 0.2,
                pointRadius: 0,
                borderWidth: 2,
                order: idx,
            };
        });

        const datasets = [dxyDataset, ...pairDatasets];

        // Configure time unit based on timeframe
        let timeUnit = 'hour';
        if (this.currentTimeframe === 'daily') {
            timeUnit = 'day';
        } else if (this.currentTimeframe === '10min') {
            timeUnit = 'minute';
        }

        this.charts.usdChart = new Chart(ctx, {
            type: 'line',
            data: { datasets },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    mode: 'index',
                    intersect: false,
                },
                plugins: {
                    legend: { display: false }, // We use custom legend
                    tooltip: {
                        backgroundColor: '#1c2030',
                        titleColor: '#e2e8f0',
                        bodyColor: '#8b95a5',
                        callbacks: {
                            label: (context) => {
                                const value = context.parsed.y;
                                if (value != null) {
                                    const change = (value - 100).toFixed(2);
                                    const sign = change >= 0 ? '+' : '';
                                    return `${context.dataset.label}: ${sign}${change}%`;
                                }
                                return '';
                            },
                        },
                    },
                },
                scales: {
                    x: {
                        type: 'time',
                        time: { unit: timeUnit },
                        grid: { color: '#2a2e3960' },
                        ticks: { color: '#8b95a5', maxRotation: 0 },
                    },
                    y: {
                        position: 'right',
                        grid: { color: '#2a2e3960' },
                        ticks: {
                            color: '#8b95a5',
                            callback: (value) => `${(value - 100).toFixed(1)}%`,
                        },
                    },
                },
            },
        });
    },

    updateUsdStrengthIndicator(data) {
        const strengthEl = document.getElementById('usdStrengthValue');
        const risingEl = document.getElementById('risingPairs');
        const fallingEl = document.getElementById('fallingPairs');

        if (!data.chart_data || data.chart_data.length < 2) return;

        const firstData = data.chart_data[0];
        const lastData = data.chart_data[data.chart_data.length - 1];

        const rising = [];
        const falling = [];
        let usdStrengthSum = 0;
        let count = 0;

        data.pairs.forEach(pair => {
            const pairCol = pair.replace('/', '_');
            const first = firstData[pairCol];
            const last = lastData[pairCol];

            if (first != null && last != null) {
                const change = last - first;
                const isUsdBase = pair.startsWith('USD/');
                const currency = isUsdBase ? pair.split('/')[1] : pair.split('/')[0];

                // For XXX/USD: if it goes up, that currency is rising vs USD (USD weakening)
                // For USD/XXX: if it goes up, USD is strengthening vs that currency
                if (isUsdBase) {
                    // USD/XXX pair - positive change = USD strengthening
                    if (change > 0.5) falling.push(currency);
                    else if (change < -0.5) rising.push(currency);
                    usdStrengthSum += change;
                } else {
                    // XXX/USD pair - positive change = that currency rising (USD weakening)
                    if (change > 0.5) rising.push(currency);
                    else if (change < -0.5) falling.push(currency);
                    usdStrengthSum -= change; // Invert for USD perspective
                }
                count++;
            }
        });

        const avgUsdChange = count > 0 ? usdStrengthSum / count : 0;

        // Update USD strength indicator
        if (strengthEl) {
            if (avgUsdChange > 0.3) {
                strengthEl.innerHTML = '<span class="strength-up">↑ STRENGTHENING</span>';
                strengthEl.className = 'strength-value positive';
            } else if (avgUsdChange < -0.3) {
                strengthEl.innerHTML = '<span class="strength-down">↓ WEAKENING</span>';
                strengthEl.className = 'strength-value negative';
            } else {
                strengthEl.innerHTML = '<span class="strength-neutral">→ NEUTRAL</span>';
                strengthEl.className = 'strength-value neutral';
            }
        }

        // Update currency lists
        if (risingEl) {
            risingEl.textContent = rising.length > 0 ? rising.join(', ') : 'None';
        }
        if (fallingEl) {
            fallingEl.textContent = falling.length > 0 ? falling.join(', ') : 'None';
        }
    },

    renderChartLegend(pairs, container) {
        if (!container || !pairs) return;

        // Add DXY to legend first
        let html = `
            <span class="chart-legend-item">
                <span class="legend-dot" style="background:${this.DXY_BORDER}"></span>
                DXY
            </span>
        `;

        html += pairs.map((pair, idx) => {
            const color = this.CHART_COLORS[idx % this.CHART_COLORS.length];
            return `
                <span class="chart-legend-item">
                    <span class="legend-dot" style="background:${color}"></span>
                    ${pair}
                </span>
            `;
        }).join('');

        container.innerHTML = html;
    },

    // ──────────────────────────────────────────────────────────
    // RECENT MOVEMENTS WITH CORRELATIONS
    // ──────────────────────────────────────────────────────────

    async loadRecentMovements() {
        const container = document.getElementById('forexMovementsGrid');
        if (!container) return;

        try {
            const response = await apiRequest('/api/forex/recent-movements', 'GET');
            if (!response.ok) throw new Error('Failed to load recent movements');

            const data = await response.json();
            this.renderRecentMovements(data.movements || []);
        } catch (error) {
            container.innerHTML = `<p class="error-text">Failed to load movements: ${error.message}</p>`;
        }
    },

    renderRecentMovements(movements) {
        const container = document.getElementById('forexMovementsGrid');
        if (!container) return;

        if (movements.length === 0) {
            container.innerHTML = '<p class="empty-text">No recent notable movements found.</p>';
            return;
        }

        container.innerHTML = movements.map(move => {
            const dirClass = move.direction === 'bullish' ? 'positive' : 'negative';
            const arrow = move.direction === 'bullish' ? '↑' : '↓';

            // Calculate buy recommendation
            const buyRec = this.getBuyRecommendation(move.pair, move.direction);

            // Render correlated pairs with their buy recommendations
            const correlatedHtml = (move.correlated_pairs || []).map(cp => {
                const corrSign = cp.correlation >= 0 ? '+' : '';
                const corrClass = cp.correlation >= 0 ? 'positive-corr' : 'negative-corr';
                // Derive correlated pair recommendation based on correlation direction
                const corrBuyRec = this.getCorrelatedBuyRec(cp.pair, move.direction, cp.correlation);
                return `
                    <div class="correlated-pair ${corrClass}">
                        <span class="cp-pair">${cp.pair}</span>
                        <span class="cp-corr">${corrSign}${(cp.correlation * 100).toFixed(0)}%</span>
                        <span class="cp-action">${corrBuyRec}</span>
                    </div>
                `;
            }).join('');

            return `
                <div class="movement-card">
                    <div class="movement-header">
                        <span class="movement-pair">${move.pair}</span>
                        <span class="movement-direction ${dirClass}">${arrow} ${move.direction.toUpperCase()}</span>
                    </div>
                    <div class="movement-action">
                        <span class="action-label">Signal:</span>
                        <span class="action-value ${buyRec.class}">${buyRec.action}</span>
                    </div>
                    <div class="movement-details">
                        <span class="movement-date">${move.date}</span>
                        <span class="movement-change ${dirClass}">${move.change_pct >= 0 ? '+' : ''}${move.change_pct?.toFixed(2) || '--'}%</span>
                    </div>
                    <div class="movement-correlated">
                        <div class="correlated-label">Correlated Pairs:</div>
                        <div class="correlated-pairs">${correlatedHtml || '<span class="no-corr">None</span>'}</div>
                    </div>
                </div>
            `;
        }).join('');
    },

    // Get buy/sell recommendation for a pair based on trend direction
    getBuyRecommendation(pair, direction) {
        const isUsdBase = pair.startsWith('USD/');
        const [base, quote] = pair.split('/');

        // For XXX/USD pairs:
        //   - Bullish (pair rising) = Buy XXX (base currency)
        //   - Bearish (pair falling) = Buy USD (quote currency)
        // For USD/XXX pairs:
        //   - Bullish (pair rising) = Buy USD (base currency)
        //   - Bearish (pair falling) = Buy XXX (quote currency)

        if (direction === 'bullish') {
            return {
                action: `BUY ${base}`,
                class: 'buy-signal',
            };
        } else {
            return {
                action: `BUY ${quote}`,
                class: 'sell-signal',
            };
        }
    },

    // Get recommendation for correlated pair
    getCorrelatedBuyRec(pair, originalDirection, correlation) {
        const [base, quote] = pair.split('/');

        // If positive correlation: same direction as original
        // If negative correlation: opposite direction
        const effectiveDirection = correlation >= 0 ? originalDirection :
            (originalDirection === 'bullish' ? 'bearish' : 'bullish');

        if (effectiveDirection === 'bullish') {
            return `→ ${base}`;
        } else {
            return `→ ${quote}`;
        }
    },

    // ──────────────────────────────────────────────────────────
    // SUMMARY
    // ──────────────────────────────────────────────────────────

    async loadSummary() {
        const container = document.getElementById('forexSummaryStats');
        if (!container) return;

        try {
            const response = await apiRequest('/api/forex/summary', 'GET');
            if (!response.ok) throw new Error('Failed to load forex summary');

            const data = await response.json();
            this.renderSummary(data);
        } catch (error) {
            container.innerHTML = `<p class="error">Failed to load summary: ${error.message}</p>`;
        }
    },

    renderSummary(data) {
        // Update individual stat elements (new single-row layout)
        const pairsEl = document.getElementById('statPairsCount');
        const dataEl = document.getElementById('statDataPoints');
        const movementsEl = document.getElementById('statNotableMovements');
        const recentEl = document.getElementById('statRecentBreaks');

        if (pairsEl) pairsEl.textContent = data.pairs_count || 0;
        if (dataEl) dataEl.textContent = this.formatNumber(data.data_points || 0);
        if (movementsEl) movementsEl.textContent = this.formatNumber(data.total_trend_breaks || 0);
        if (recentEl) recentEl.textContent = data.recent_breaks_7d || 0;
    },

    // ──────────────────────────────────────────────────────────
    // PAIRS LIST
    // ──────────────────────────────────────────────────────────

    async loadPairs() {
        const tbody = document.getElementById('forexPairsBody');
        const pairFilter = document.getElementById('forexPairFilter');
        if (!tbody) return;

        try {
            const response = await apiRequest('/api/forex/pairs', 'GET');
            if (!response.ok) throw new Error('Failed to load forex pairs');

            const data = await response.json();
            this.renderPairs(data.pairs || []);

            // Populate pair filter
            if (pairFilter && data.pairs) {
                pairFilter.innerHTML = '<option value="">All Pairs</option>' +
                    data.pairs.map(p => `<option value="${p.pair}">${p.pair}</option>`).join('');
            }
        } catch (error) {
            tbody.innerHTML = `<tr><td colspan="6" class="error">Failed to load pairs: ${error.message}</td></tr>`;
        }
    },

    renderPairs(pairs) {
        const tbody = document.getElementById('forexPairsBody');
        if (!tbody) return;

        if (pairs.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="forex-empty">No forex pairs found. Run the data population script first.</td></tr>';
            return;
        }

        tbody.innerHTML = pairs.map(pair => {
            const yearsOfData = pair.data_start_date && pair.data_end_date
                ? ((new Date(pair.data_end_date) - new Date(pair.data_start_date)) / (365.25 * 24 * 60 * 60 * 1000)).toFixed(1)
                : '--';

            const modelStatus = pair.model_trained
                ? '<span class="status-badge trained">Trained</span>'
                : '<span class="status-badge pending">Pending</span>';

            return `
                <tr class="forex-pair-row" data-pair="${pair.pair}">
                    <td><strong>${pair.pair}</strong></td>
                    <td>${pair.base_currency} / ${pair.quote_currency}</td>
                    <td>${pair.data_start_date || '--'}</td>
                    <td>${this.formatNumber(pair.total_records || 0)}</td>
                    <td>${yearsOfData} years</td>
                    <td>${modelStatus}</td>
                </tr>
            `;
        }).join('');

        // Row click handler
        tbody.querySelectorAll('.forex-pair-row').forEach(row => {
            row.addEventListener('click', () => {
                const pair = row.dataset.pair;
                this.selectPair(pair);
            });
        });
    },

    async selectPair(pair) {
        this.selectedPair = pair;

        // Highlight selected row
        document.querySelectorAll('.forex-pair-row').forEach(row => {
            row.classList.toggle('selected', row.dataset.pair === pair);
        });

        // Load chart for selected pair
        await this.loadPairChart(pair);
    },

    // ──────────────────────────────────────────────────────────
    // CORRELATIONS
    // ──────────────────────────────────────────────────────────

    async loadCorrelations(strength = '') {
        const tbody = document.getElementById('forexCorrelationsBody');
        if (!tbody) return;

        try {
            let url = '/api/forex/correlations';
            if (strength) url += `?strength=${strength}`;

            const response = await apiRequest(url, 'GET');
            if (!response.ok) throw new Error('Failed to load correlations');

            const data = await response.json();
            this.renderCorrelations(data.correlations || [], data.thresholds);
        } catch (error) {
            tbody.innerHTML = `<tr><td colspan="6" class="error">Failed to load correlations: ${error.message}</td></tr>`;
        }
    },

    renderCorrelations(correlations, thresholds) {
        const tbody = document.getElementById('forexCorrelationsBody');
        if (!tbody) return;

        if (correlations.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="forex-empty">No correlations found. Train the model first.</td></tr>';
            return;
        }

        tbody.innerHTML = correlations.slice(0, 50).map(corr => {
            const absCorr = Math.abs(corr.correlation_all || 0);
            const corrPct = (absCorr * 100).toFixed(1);
            const strengthClass = corr.pattern_strength || 'weak';
            const corrSign = (corr.correlation_all || 0) >= 0 ? '+' : '';

            const leadLag = corr.lead_lag_days
                ? (corr.lead_lag_days > 0 ? `${corr.pair_a} leads by ${corr.lead_lag_days}d` : `${corr.pair_b} leads by ${Math.abs(corr.lead_lag_days)}d`)
                : 'Contemporaneous';

            return `
                <tr class="corr-row ${strengthClass}">
                    <td><strong>${corr.pair_a}</strong></td>
                    <td><strong>${corr.pair_b}</strong></td>
                    <td class="corr-value">${corrSign}${corrPct}%</td>
                    <td><span class="strength-badge ${strengthClass}">${strengthClass.toUpperCase()}</span></td>
                    <td>${leadLag}</td>
                    <td>${this.formatNumber(corr.data_points || 0)}</td>
                </tr>
            `;
        }).join('');

        // Update thresholds display
        if (thresholds) {
            const threshContainer = document.getElementById('forexThresholds');
            if (threshContainer) {
                threshContainer.innerHTML = `
                    <span class="threshold-item">Strong: ≥${(thresholds.strong_min * 100).toFixed(1)}%</span>
                    <span class="threshold-item">Mid: ${(thresholds.mid_min * 100).toFixed(1)}%-${(thresholds.strong_min * 100).toFixed(1)}%</span>
                    <span class="threshold-item">Weak: <${(thresholds.mid_min * 100).toFixed(1)}%</span>
                `;
            }
        }
    },

    // ──────────────────────────────────────────────────────────
    // TREND BREAKS
    // ──────────────────────────────────────────────────────────

    async loadTrendBreaks(pair = '') {
        const tbody = document.getElementById('forexTrendBreaksBody');
        if (!tbody) return;

        try {
            let url = '/api/forex/trend-breaks?days=90&limit=50';
            if (pair) url += `&pair=${encodeURIComponent(pair)}`;

            const response = await apiRequest(url, 'GET');
            if (!response.ok) throw new Error('Failed to load trend breaks');

            const data = await response.json();
            this.renderTrendBreaks(data.trend_breaks || []);
        } catch (error) {
            tbody.innerHTML = `<tr><td colspan="7" class="error">Failed to load trend breaks: ${error.message}</td></tr>`;
        }
    },

    renderTrendBreaks(breaks) {
        const tbody = document.getElementById('forexTrendBreaksBody');
        if (!tbody) return;

        if (breaks.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="forex-empty">No trend breaks found.</td></tr>';
            return;
        }

        tbody.innerHTML = breaks.map(brk => {
            const dirClass = brk.break_direction === 'bullish' ? 'positive' : 'negative';
            const probPct = ((brk.break_probability || 0) * 100).toFixed(1);

            const indicators = brk.indicators || {};
            const rsiDisplay = indicators.rsi != null ? indicators.rsi.toFixed(1) : '--';
            const cciDisplay = indicators.cci != null ? indicators.cci.toFixed(0) : '--';

            const movePct = brk.movement_pct != null
                ? `${brk.movement_pct >= 0 ? '+' : ''}${brk.movement_pct.toFixed(2)}%`
                : '--';

            return `
                <tr class="break-row">
                    <td><strong>${brk.pair}</strong></td>
                    <td>${brk.break_date || '--'}</td>
                    <td class="${dirClass}">${(brk.break_direction || '--').toUpperCase()}</td>
                    <td><span class="prob-badge">${probPct}%</span></td>
                    <td>${brk.price_at_break?.toFixed(5) || '--'}</td>
                    <td class="${brk.movement_pct >= 0 ? 'positive' : 'negative'}">${movePct}</td>
                    <td>RSI ${rsiDisplay} / CCI ${cciDisplay}</td>
                </tr>
            `;
        }).join('');
    },

    // ──────────────────────────────────────────────────────────
    // CHART
    // ──────────────────────────────────────────────────────────

    async loadPairChart(pair) {
        const canvas = document.getElementById('forexPairChart');
        const container = document.getElementById('forexChartContainer');
        if (!canvas || !container) return;

        container.style.display = 'block';

        try {
            const response = await apiRequest(`/api/forex/data/${encodeURIComponent(pair)}?days=365`, 'GET');
            if (!response.ok) throw new Error('Failed to load chart data');

            const data = await response.json();
            this.renderChart(pair, data.data || []);
        } catch (error) {
            console.error('Chart load failed:', error);
        }
    },

    renderChart(pair, data) {
        const canvas = document.getElementById('forexPairChart');
        if (!canvas || data.length === 0) return;

        // Destroy existing chart
        if (this.charts.forexChart) {
            this.charts.forexChart.destroy();
        }

        const ctx = canvas.getContext('2d');

        const chartData = data.reverse().map(d => ({
            x: new Date(d.date),
            y: d.close,
        }));

        this.charts.forexChart = new Chart(ctx, {
            type: 'line',
            data: {
                datasets: [{
                    label: pair,
                    data: chartData,
                    borderColor: '#4fc3f7',
                    backgroundColor: 'rgba(79, 195, 247, 0.1)',
                    fill: true,
                    tension: 0.1,
                    pointRadius: 0,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: true, labels: { color: '#8b95a5' } },
                    tooltip: {
                        backgroundColor: '#1c2030',
                        titleColor: '#e2e8f0',
                        bodyColor: '#8b95a5',
                    },
                },
                scales: {
                    x: {
                        type: 'time',
                        time: { unit: 'month' },
                        grid: { color: '#2a2e3960' },
                        ticks: { color: '#8b95a5' },
                    },
                    y: {
                        position: 'right',
                        grid: { color: '#2a2e3960' },
                        ticks: { color: '#8b95a5' },
                    },
                },
            },
        });

        // Update chart title
        const titleEl = document.getElementById('forexChartTitle');
        if (titleEl) titleEl.textContent = `${pair} - 1 Year`;
    },

    // ──────────────────────────────────────────────────────────
    // HELPERS
    // ──────────────────────────────────────────────────────────

    formatNumber(num) {
        if (num >= 1e6) return (num / 1e6).toFixed(1) + 'M';
        if (num >= 1e3) return (num / 1e3).toFixed(1) + 'K';
        return String(num);
    },
};

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('forexTab')) {
        // Wait for apiRequest to be available
        const checkReady = setInterval(() => {
            if (typeof apiRequest !== 'undefined') {
                clearInterval(checkReady);
                Forex.init();
            }
        }, 100);
        setTimeout(() => clearInterval(checkReady), 5000);
    }
});

window.Forex = Forex;
