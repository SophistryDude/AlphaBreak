// Dashboard Widget Manager
// Handles data fetching, rendering, and auto-refresh for all 4 dashboard widgets.

const Dashboard = {
    charts: {},
    refreshTimers: {},
    data: {},

    // ──────────────────────────────────────────────────────────
    // INITIALIZATION
    // ──────────────────────────────────────────────────────────

    init() {
        this.loadAllWidgets();
        this.setupAutoRefresh();
        this.setupEventListeners();
    },

    async loadAllWidgets() {
        await Promise.allSettled([
            this.loadMarketSentiment(),
            this.loadSectorSentiment(),
            this.loadIndexSentiment(),
            this.loadCommoditiesCrypto(),
        ]);
    },

    setupAutoRefresh() {
        // Sentiment widgets: every 5 minutes
        this.refreshTimers.sentiment = setInterval(() => {
            this.loadMarketSentiment();
            this.loadSectorSentiment();
            this.loadIndexSentiment();
        }, 5 * 60 * 1000);

        // Commodities/crypto: every 1 minute
        this.refreshTimers.commodities = setInterval(() => {
            this.loadCommoditiesCrypto();
        }, 60 * 1000);
    },

    setupEventListeners() {
        const sectorSelector = document.getElementById('sectorSelector');
        if (sectorSelector) {
            sectorSelector.addEventListener('change', (e) => {
                this.filterSectors(e.target.value);
            });
        }

        document.querySelectorAll('.asset-tab').forEach(tab => {
            tab.addEventListener('click', (e) => {
                this.switchAssetChart(e.target.dataset.asset);
            });
        });
    },

    // ──────────────────────────────────────────────────────────
    // WIDGET 1: Market Sentiment
    // ──────────────────────────────────────────────────────────

    async loadMarketSentiment() {
        try {
            const response = await apiRequest('/api/dashboard/market-sentiment');
            if (!response.ok) throw new Error('Failed to load market sentiment');
            const data = await response.json();
            this.data.marketSentiment = data;
            this.renderMarketSentiment(data);
        } catch (error) {
            this.renderWidgetError('widgetMarketSentiment', 'Market data unavailable');
        }
    },

    renderMarketSentiment(data) {
        const sentimentClass = data.sentiment.toLowerCase();

        // Big label
        const label = document.getElementById('marketSentimentLabel');
        label.textContent = data.sentiment;
        label.className = 'sentiment-label ' + sentimentClass;

        // Badge
        const badge = document.getElementById('marketSentimentBadge');
        badge.textContent = data.sentiment;
        badge.className = 'widget-badge ' + sentimentClass;

        // Confidence
        document.getElementById('marketSentimentConfidence').textContent =
            Math.round(data.confidence * 100) + '% confidence';

        // Indicator chips
        const indicatorsEl = document.getElementById('marketSentimentIndicators');
        indicatorsEl.innerHTML = '';
        if (data.indicators) {
            Object.entries(data.indicators).forEach(([name, info]) => {
                const chip = document.createElement('span');
                chip.className = 'indicator-chip ' + info.signal;
                chip.textContent = name.toUpperCase() + ': ' + info.signal;
                chip.title = info.description || '';
                indicatorsEl.appendChild(chip);
            });
        }

        // CBOE context
        const contextEl = document.getElementById('marketSentimentContext');
        if (data.cboe_context) {
            contextEl.innerHTML =
                '<span class="indicator-chip">Options Sentiment: ' + data.cboe_context.pcr_regime + '</span>' +
                '<span class="indicator-chip">Market Type: ' + (data.market_type || 'unknown') + '</span>';
        } else {
            contextEl.innerHTML =
                '<span class="indicator-chip">Market Type: ' + (data.market_type || 'unknown') + '</span>';
        }

        // Chart — candlestick with trend lines
        if (data.weekly_chart_data && data.weekly_chart_data.length > 0) {
            this.renderCandlestickChart(
                'marketSentimentChart',
                data.weekly_chart_data,
                data.peaks || [],
                data.troughs || []
            );
        }

        // Timestamp
        document.getElementById('marketSentimentUpdated').textContent =
            'Updated: ' + new Date(data.last_updated).toLocaleTimeString();
    },

    // ──────────────────────────────────────────────────────────
    // WIDGET 2: Sector Sentiment
    // ──────────────────────────────────────────────────────────

    async loadSectorSentiment() {
        try {
            const response = await apiRequest('/api/dashboard/sector-sentiment');
            if (!response.ok) throw new Error('Failed to load sector sentiment');
            const data = await response.json();
            this.data.sectorSentiment = data;
            this.renderSectorSentiment(data);
        } catch (error) {
            this.renderWidgetError('widgetSectorSentiment', 'Sector data unavailable');
        }
    },

    renderSectorSentiment(data) {
        // Populate selector
        const selector = document.getElementById('sectorSelector');
        selector.innerHTML = '<option value="all">All Sectors</option>';
        data.sectors.forEach(s => {
            const opt = document.createElement('option');
            opt.value = s.name;
            opt.textContent = s.name;
            selector.appendChild(opt);
        });

        // Render sector pills
        const grid = document.getElementById('sectorGrid');
        grid.innerHTML = '';
        data.sectors.forEach(sector => {
            const pill = document.createElement('div');
            const sentimentClass = sector.sentiment.toLowerCase();
            pill.className = 'sector-pill ' + sentimentClass;
            pill.innerHTML =
                '<div class="sector-pill-name">' + sector.name + '</div>' +
                '<div class="sector-pill-sentiment">' + sector.sentiment + '</div>';
            pill.addEventListener('click', () => {
                this.showSectorChart(sector);
            });
            grid.appendChild(pill);
        });

        document.getElementById('sectorSentimentUpdated').textContent =
            'Updated: ' + new Date(data.last_updated).toLocaleTimeString();
    },

    showSectorChart(sector) {
        const container = document.getElementById('sectorChartContainer');
        container.style.display = 'block';
        if (sector.weekly_chart_data && sector.weekly_chart_data.length > 0) {
            this.renderLineChart(
                'sectorChart',
                sector.weekly_chart_data,
                ['close'],
                [sector.name],
                ['#2962ff']
            );
        }
    },

    filterSectors(sectorName) {
        if (sectorName === 'all') {
            document.querySelectorAll('.sector-pill').forEach(p => p.style.display = '');
            document.getElementById('sectorChartContainer').style.display = 'none';
        } else {
            const sector = this.data.sectorSentiment.sectors.find(s => s.name === sectorName);
            if (sector) this.showSectorChart(sector);
        }
    },

    // ──────────────────────────────────────────────────────────
    // WIDGET 3: VIX & Index Sentiment
    // ──────────────────────────────────────────────────────────

    async loadIndexSentiment() {
        try {
            const response = await apiRequest('/api/dashboard/index-sentiment');
            if (!response.ok) throw new Error('Failed to load index sentiment');
            const data = await response.json();
            this.data.indexSentiment = data;
            this.renderIndexSentiment(data);
        } catch (error) {
            this.renderWidgetError('widgetIndexSentiment', 'Index data unavailable');
        }
    },

    renderIndexSentiment(data) {
        // VIX
        if (data.vix) {
            document.getElementById('vixValue').textContent = data.vix.value.toFixed(1);

            const fearLabel = document.getElementById('vixFearLabel');
            fearLabel.textContent = data.vix.fear_level;
            fearLabel.className = 'vix-fear-label ' + this.vixFearClass(data.vix.fear_level);

            document.getElementById('vixDescription').textContent = data.vix.description;
        }

        // Index cards
        const grid = document.getElementById('indexSentimentGrid');
        grid.innerHTML = '';
        if (data.indices) {
            data.indices.forEach(idx => {
                const card = document.createElement('div');
                card.className = 'index-card';
                const changeClass = idx.weekly_change_pct >= 0 ? 'positive' : 'negative';
                const changeSign = idx.weekly_change_pct >= 0 ? '+' : '';
                const priceText = idx.current_price
                    ? '$' + idx.current_price.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })
                    : '--';
                card.innerHTML =
                    '<div class="index-name">' + idx.name + '</div>' +
                    '<div class="index-sentiment-badge ' + idx.sentiment.toLowerCase() + '">' + idx.sentiment + '</div>' +
                    '<div class="index-price">' + priceText + '</div>' +
                    '<div class="index-change ' + changeClass + '">' + changeSign + idx.weekly_change_pct.toFixed(1) + '%</div>';
                grid.appendChild(card);
            });
        }

        // Inverse ETFs
        const invSection = document.getElementById('inverseEtfSentiment');
        if (data.inverse_etfs) {
            const inv = data.inverse_etfs;
            const invClass = inv.sentiment.toLowerCase();
            invSection.innerHTML =
                '<span class="widget-badge ' + invClass + '">' + inv.sentiment + '</span>' +
                '<p style="margin-top:6px;font-size:0.8rem;color:var(--text-secondary)">' + inv.description + '</p>';
        }

        document.getElementById('indexSentimentUpdated').textContent =
            'Updated: ' + new Date(data.last_updated).toLocaleTimeString();
    },

    vixFearClass(level) {
        if (level.includes('Very Low') || level.includes('Low')) return 'low';
        if (level.includes('Normal')) return 'normal';
        if (level.includes('Elevated')) return 'elevated';
        if (level.includes('Extreme')) return 'extreme';
        return 'normal';
    },

    // ──────────────────────────────────────────────────────────
    // WIDGET 4: Commodities & Crypto
    // ──────────────────────────────────────────────────────────

    async loadCommoditiesCrypto() {
        try {
            const response = await apiRequest('/api/dashboard/commodities-crypto');
            if (!response.ok) throw new Error('Failed to load commodity/crypto data');
            const data = await response.json();
            this.data.commoditiesCrypto = data;
            this.renderCommoditiesCrypto(data);
        } catch (error) {
            this.renderWidgetError('widgetCommoditiesCrypto', 'Price data unavailable');
        }
    },

    renderCommoditiesCrypto(data) {
        // Summary cards
        const grid = document.getElementById('assetSummaryGrid');
        grid.innerHTML = '';

        data.assets.forEach((asset, i) => {
            const card = document.createElement('div');
            card.className = 'asset-summary-card' + (i === 0 ? ' active' : '');
            card.dataset.symbol = asset.symbol;
            const changeClass = asset.change_24h_pct >= 0 ? 'positive' : 'negative';
            const changeSign = asset.change_24h_pct >= 0 ? '+' : '';
            const priceText = asset.current_price ? '$' + this.formatPrice(asset.current_price) : '--';
            card.innerHTML =
                '<div class="asset-name">' + asset.name + '</div>' +
                '<div class="asset-price">' + priceText + '</div>' +
                '<div class="asset-change ' + changeClass + '">' + changeSign + asset.change_24h_pct.toFixed(1) + '%</div>' +
                '<div class="asset-tlev">TLEV: ' + asset.tlev_signal + '</div>';
            card.addEventListener('click', () => this.switchAssetChart(asset.symbol));
            grid.appendChild(card);
        });

        // Render first asset chart
        if (data.assets.length > 0) {
            this.renderAssetChart(data.assets[0]);
        }

        document.getElementById('commodityCryptoUpdated').textContent =
            'Updated: ' + new Date(data.last_updated).toLocaleTimeString();
    },

    switchAssetChart(symbol) {
        // Update tab active states
        document.querySelectorAll('.asset-tab').forEach(t => {
            t.classList.toggle('active', t.dataset.asset === symbol);
        });
        document.querySelectorAll('.asset-summary-card').forEach(c => {
            c.classList.toggle('active', c.dataset.symbol === symbol);
        });

        // Find asset data and render chart
        if (this.data.commoditiesCrypto) {
            const asset = this.data.commoditiesCrypto.assets.find(a => a.symbol === symbol);
            if (asset) this.renderAssetChart(asset);
        }
    },

    renderAssetChart(asset) {
        const ctx = document.getElementById('commodityCryptoChart');
        if (!ctx) return;

        // Destroy existing chart
        if (this.charts.commodityCryptoChart) {
            this.charts.commodityCryptoChart.destroy();
        }

        const chartData = asset.hourly_chart_data;
        if (!chartData || chartData.length === 0) return;

        // Convert timestamps to luxon millis for the time axis
        const timestamps = chartData.map(d => luxon.DateTime.fromISO(d.timestamp).toMillis());

        // Candlestick dataset — {x, o, h, l, c} format
        const candlestickData = chartData.map((d, i) => ({
            x: timestamps[i],
            o: d.open,
            h: d.high,
            l: d.low,
            c: d.close,
        }));

        this.charts.commodityCryptoChart = new Chart(ctx, {
            type: 'candlestick',
            data: {
                datasets: [{
                    label: asset.name,
                    data: candlestickData,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
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
                        time: { unit: 'hour', displayFormats: { hour: 'MMM d, ha' } },
                        grid: { display: false },
                        ticks: { maxTicksLimit: 6, font: { size: 10 }, color: '#8b95a5' },
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
    // CANDLESTICK CHART (Market Sentiment + Earnings)
    // ──────────────────────────────────────────────────────────

    renderCandlestickChart(canvasId, chartData, peaks, troughs) {
        const ctx = document.getElementById(canvasId);
        if (!ctx) return;

        if (this.charts[canvasId]) {
            this.charts[canvasId].destroy();
        }

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

        // SMA 20 overlay — {x, y} point format for time axis compatibility
        const smaData = chartData.map((d, i) => d.sma_20 !== null ? {x: timestamps[i], y: d.sma_20} : null).filter(p => p !== null);

        // Resistance trend line (peaks) — {x, y} points only at peak dates
        const peakDateSet = new Set(peaks.map(p => p.date));
        const resistanceData = chartData
            .map((d, i) => peakDateSet.has(d.date) ? {x: timestamps[i], y: peaks.find(p => p.date === d.date).price} : null)
            .filter(p => p !== null);

        // Support trend line (troughs) — {x, y} points only at trough dates
        const troughDateSet = new Set(troughs.map(t => t.date));
        const supportData = chartData
            .map((d, i) => troughDateSet.has(d.date) ? {x: timestamps[i], y: troughs.find(t => t.date === d.date).price} : null)
            .filter(p => p !== null);

        const datasets = [
            {
                label: 'S&P 500',
                data: candlestickData,
            },
            {
                label: 'SMA 20',
                data: smaData,
                type: 'line',
                borderColor: '#f59e0b',
                borderWidth: 2,
                pointRadius: 0,
                tension: 0.3,
                fill: false,
                order: 1,
            },
        ];

        // Add resistance line if we have >= 2 peaks
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

        // Add support line if we have >= 2 troughs
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
                        time: { unit: 'week' },
                        grid: { display: false },
                        ticks: { maxTicksLimit: 6, font: { size: 10 }, color: '#8b95a5' },
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
    // SHARED LINE CHART HELPER
    // ──────────────────────────────────────────────────────────

    renderLineChart(canvasId, chartData, valueKeys, labels, colors) {
        const ctx = document.getElementById(canvasId);
        if (!ctx) return;

        if (this.charts[canvasId]) {
            this.charts[canvasId].destroy();
        }

        const datasets = valueKeys.map((key, i) => {
            const ds = {
                label: labels[i],
                data: chartData.map(d => d[key]),
                borderColor: colors[i],
                borderWidth: 2,
                pointRadius: 0,
                tension: 0.3,
                fill: i === 0,
            };
            if (i === 0) {
                ds.backgroundColor = colors[0] + '15';
            }
            return ds;
        });

        this.charts[canvasId] = new Chart(ctx, {
            type: 'line',
            data: {
                labels: chartData.map(d => d.date),
                datasets: datasets,
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: valueKeys.length > 1,
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
                        grid: { display: false },
                        ticks: { maxTicksLimit: 5, font: { size: 10 }, color: '#8b95a5' },
                    },
                    y: {
                        grid: { color: '#2a2e3960' },
                        ticks: { font: { size: 10 }, color: '#8b95a5' },
                    },
                },
                interaction: { intersect: false, mode: 'index' },
            },
        });
    },

    // ──────────────────────────────────────────────────────────
    // ERROR HANDLING
    // ──────────────────────────────────────────────────────────

    renderWidgetError(widgetId, message) {
        const widget = document.getElementById(widgetId);
        if (!widget) return;
        const body = widget.querySelector('.widget-body');
        if (body) {
            body.innerHTML = '<div class="widget-loading">' + message + '</div>';
        }
    },

    // ──────────────────────────────────────────────────────────
    // UTILITY
    // ──────────────────────────────────────────────────────────

    formatPrice(price) {
        if (price >= 1000) {
            return price.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 });
        }
        return price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    },
};

// Auto-initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    if (typeof apiRequest !== 'undefined') {
        Dashboard.init();
    } else {
        // If app.js hasn't loaded yet, wait for it
        const checkReady = setInterval(() => {
            if (typeof apiRequest !== 'undefined') {
                clearInterval(checkReady);
                Dashboard.init();
            }
        }, 100);
        // Give up after 5 seconds
        setTimeout(() => clearInterval(checkReady), 5000);
    }
});
