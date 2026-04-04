// ============================================================================
// AlphaBreak Charts — Lightweight Charts wrapper with trendline support
// ============================================================================
// Replaces Chart.js for OHLCV charts. Provides:
// - Professional candlestick rendering (TradingView quality)
// - Volume histogram
// - SMA / Bollinger Band overlays
// - Auto-detected trendlines with confidence coloring
// - Support/resistance levels
// - Regime indicator
// - Crosshair with OHLCV tooltip

const AlphaCharts = (() => {
    const instances = {};

    // ── Theme ────────────────────────────────────────────────────────────
    const THEME = {
        background: '#131722',
        textColor: '#8b95a5',
        gridColor: 'rgba(42, 46, 57, 0.5)',
        crosshair: '#5c6578',
        upColor: '#26a69a',
        downColor: '#ef5350',
        sma10Color: '#FFB74D',
        sma50Color: '#7E57C2',
        bbColor: 'rgba(100, 181, 246, 0.5)',
        bbFill: 'rgba(100, 181, 246, 0.04)',
        volumeUpColor: 'rgba(38, 166, 154, 0.35)',
        volumeDownColor: 'rgba(239, 83, 80, 0.35)',
    };

    // ── Create Chart ─────────────────────────────────────────────────────
    function create(containerId, options = {}) {
        const container = document.getElementById(containerId);
        if (!container) return null;

        // Destroy existing
        if (instances[containerId]) {
            destroy(containerId);
        }

        // Clear container
        container.innerHTML = '';

        const chartHeight = options.height || 400;
        const volumeHeight = options.volumeHeight || 60;

        // Create sub-containers
        const chartDiv = document.createElement('div');
        chartDiv.style.height = chartHeight + 'px';
        chartDiv.style.width = '100%';
        container.appendChild(chartDiv);

        const volumeDiv = document.createElement('div');
        volumeDiv.style.height = volumeHeight + 'px';
        volumeDiv.style.width = '100%';
        volumeDiv.style.marginTop = '-1px';
        container.appendChild(volumeDiv);

        // Create Lightweight Charts instances
        const chart = LightweightCharts.createChart(chartDiv, {
            layout: {
                background: { type: 'solid', color: THEME.background },
                textColor: THEME.textColor,
                fontSize: 11,
            },
            grid: {
                vertLines: { color: THEME.gridColor },
                horzLines: { color: THEME.gridColor },
            },
            crosshair: {
                mode: LightweightCharts.CrosshairMode.Normal,
                vertLine: { color: THEME.crosshair, width: 1, style: 2 },
                horzLine: { color: THEME.crosshair, width: 1, style: 2 },
            },
            rightPriceScale: {
                borderColor: THEME.gridColor,
                scaleMargins: { top: 0.05, bottom: 0.05 },
            },
            timeScale: {
                borderColor: THEME.gridColor,
                timeVisible: true,
                secondsVisible: false,
            },
            handleScroll: { mouseWheel: true, pressedMouseMove: true },
            handleScale: { mouseWheel: true, pinch: true },
        });

        const volumeChart = LightweightCharts.createChart(volumeDiv, {
            layout: {
                background: { type: 'solid', color: THEME.background },
                textColor: THEME.textColor,
                fontSize: 10,
            },
            grid: {
                vertLines: { visible: false },
                horzLines: { visible: false },
            },
            rightPriceScale: { visible: false },
            timeScale: { visible: false },
            handleScroll: false,
            handleScale: false,
            crosshair: { mode: LightweightCharts.CrosshairMode.Hidden },
        });

        // Sync time scales
        chart.timeScale().subscribeVisibleLogicalRangeChange(range => {
            if (range) volumeChart.timeScale().setVisibleLogicalRange(range);
        });

        // Add candlestick series
        const candleSeries = chart.addCandlestickSeries({
            upColor: THEME.upColor,
            downColor: THEME.downColor,
            borderUpColor: THEME.upColor,
            borderDownColor: THEME.downColor,
            wickUpColor: THEME.upColor,
            wickDownColor: THEME.downColor,
        });

        // Add volume series
        const volumeSeries = volumeChart.addHistogramSeries({
            priceFormat: { type: 'volume' },
            priceScaleId: '',
        });

        const instance = {
            chart,
            volumeChart,
            candleSeries,
            volumeSeries,
            container,
            overlays: {},
            trendlineSeries: [],
            levelLines: [],
        };

        instances[containerId] = instance;
        return instance;
    }

    // ── Set OHLCV Data ───────────────────────────────────────────────────
    function setData(containerId, chartData, overlays) {
        const inst = instances[containerId];
        if (!inst || !chartData || !chartData.length) return;

        // Convert timestamps to Lightweight Charts format (UTC seconds)
        const candles = chartData.map(d => ({
            time: _toTime(d.timestamp),
            open: d.open,
            high: d.high,
            low: d.low,
            close: d.close,
        }));

        const volumes = chartData.map((d, i) => ({
            time: _toTime(d.timestamp),
            value: d.volume,
            color: i === 0 ? THEME.volumeDownColor
                : d.close >= chartData[i - 1].close
                    ? THEME.volumeUpColor
                    : THEME.volumeDownColor,
        }));

        inst.candleSeries.setData(candles);
        inst.volumeSeries.setData(volumes);

        // Add overlays
        if (overlays) {
            _clearOverlays(inst);
            _addOverlays(inst, chartData, overlays);
        }

        // Fit content
        inst.chart.timeScale().fitContent();
        inst.volumeChart.timeScale().fitContent();
    }

    // ── Add Trendlines ───────────────────────────────────────────────────
    function setTrendlines(containerId, trendlineData) {
        const inst = instances[containerId];
        if (!inst || !trendlineData) return;

        // Clear existing trendlines
        _clearTrendlines(inst);

        const trendlines = trendlineData.trendlines || [];
        const supportLevels = trendlineData.support_levels || [];
        const resistanceLevels = trendlineData.resistance_levels || [];
        const regime = trendlineData.regime || 'RANGE';

        // Render regime badge
        _renderRegimeBadge(containerId, regime, trendlineData.regime_confidence);

        // Draw trendlines as line series
        for (const line of trendlines) {
            _drawTrendline(inst, line);
        }

        // Draw horizontal support/resistance levels
        for (const level of supportLevels.slice(0, 3)) {
            _drawHorizontalLevel(inst, level, 'support');
        }
        for (const level of resistanceLevels.slice(0, 3)) {
            _drawHorizontalLevel(inst, level, 'resistance');
        }

        // Render trendline info panel
        _renderTrendlinePanel(containerId, trendlineData);
    }

    // ── Draw a single trendline ──────────────────────────────────────────
    function _drawTrendline(inst, line) {
        const color = line.color?.hex || (line.type === 'support' ? '#26a69a' : '#ef5350');
        const alpha = line.color?.a || 0.7;

        // Create line series for the trendline
        const lineSeries = inst.chart.addLineSeries({
            color: color,
            lineWidth: line.confidence >= 70 ? 2 : 1,
            lineStyle: line.confidence >= 60
                ? LightweightCharts.LineStyle.Solid
                : LightweightCharts.LineStyle.Dashed,
            crosshairMarkerVisible: false,
            lastValueVisible: false,
            priceLineVisible: false,
        });

        // Build line data from start to end (and project forward)
        const points = [
            { time: _toTime(line.start_timestamp), value: line.start_price },
            { time: _toTime(line.end_timestamp), value: line.end_price },
        ];

        lineSeries.setData(points);

        // Add price line showing where trendline is now
        if (line.current_line_price) {
            lineSeries.createPriceLine({
                price: line.current_line_price,
                color: color,
                lineWidth: 1,
                lineStyle: LightweightCharts.LineStyle.Dotted,
                axisLabelVisible: true,
                title: `${line.type === 'support' ? 'S' : 'R'} ${line.confidence}%`,
            });
        }

        inst.trendlineSeries.push(lineSeries);
    }

    // ── Draw horizontal level ────────────────────────────────────────────
    function _drawHorizontalLevel(inst, level, type) {
        const color = type === 'support' ? '#26a69a' : '#ef5350';
        const alpha = Math.min(0.8, 0.3 + level.strength * 0.15);

        inst.candleSeries.createPriceLine({
            price: level.price,
            color: color,
            lineWidth: 1,
            lineStyle: LightweightCharts.LineStyle.Dashed,
            axisLabelVisible: true,
            title: `${type === 'support' ? 'S' : 'R'} (${level.touches}x)`,
        });
    }

    // ── Render regime badge ──────────────────────────────────────────────
    function _renderRegimeBadge(containerId, regime, confidence) {
        const container = document.getElementById(containerId);
        if (!container) return;

        let existing = container.querySelector('.regime-badge');
        if (existing) existing.remove();

        const colors = {
            'BULL': { bg: 'rgba(38, 166, 154, 0.15)', text: '#26a69a' },
            'BEAR': { bg: 'rgba(239, 83, 80, 0.15)', text: '#ef5350' },
            'RANGE': { bg: 'rgba(240, 185, 11, 0.15)', text: '#f0b90b' },
            'HIGH_VOL': { bg: 'rgba(126, 87, 194, 0.15)', text: '#7e57c2' },
        };
        const c = colors[regime] || colors['RANGE'];
        const conf = confidence ? ` ${confidence.toFixed(0)}%` : '';

        const badge = document.createElement('div');
        badge.className = 'regime-badge';
        badge.style.cssText = `position:absolute;top:8px;left:8px;z-index:10;
            background:${c.bg};color:${c.text};padding:4px 10px;border-radius:4px;
            font-size:11px;font-weight:700;letter-spacing:0.5px;pointer-events:none;`;
        badge.textContent = `${regime}${conf}`;
        container.style.position = 'relative';
        container.appendChild(badge);
    }

    // ── Render trendline info panel ──────────────────────────────────────
    function _renderTrendlinePanel(containerId, data) {
        const parent = document.getElementById(containerId)?.parentElement;
        if (!parent) return;

        let panel = parent.querySelector('.trendline-panel');
        if (panel) panel.remove();

        const lines = data.trendlines || [];
        if (lines.length === 0) return;

        panel = document.createElement('div');
        panel.className = 'trendline-panel';

        let html = '<div class="trendline-panel-header">';
        html += `<span class="trendline-panel-title">Auto-Detected Trendlines</span>`;
        html += `<span class="trendline-count">${lines.length} found</span>`;
        html += '</div>';

        html += '<div class="trendline-list">';
        for (const line of lines.slice(0, 5)) {
            const color = line.color?.hex || '#888';
            const icon = line.type === 'support' ? '&#9650;' : '&#9660;';
            const distStr = line.distance_pct > 0
                ? `+${line.distance_pct.toFixed(1)}% above`
                : `${line.distance_pct.toFixed(1)}% below`;

            html += `<div class="trendline-item">
                <div class="trendline-item-left">
                    <span class="trendline-dot" style="background:${color}"></span>
                    <span class="trendline-type">${line.type === 'support' ? 'Support' : 'Resistance'}</span>
                </div>
                <div class="trendline-item-center">
                    <span class="trendline-conf">Confidence: <strong>${line.confidence}%</strong></span>
                    <span class="trendline-analog" title="Historical analog match: ${line.analog_score}% of similar setups in ${data.regime} regime agreed">Analog: ${line.analog_score}%</span>
                </div>
                <div class="trendline-item-right">
                    <span class="trendline-price">$${line.current_line_price?.toFixed(2)}</span>
                    <span class="trendline-dist ${line.distance_pct > 0 ? 'positive' : 'negative'}">${distStr}</span>
                </div>
            </div>`;
        }
        html += '</div>';

        panel.innerHTML = html;
        parent.appendChild(panel);
    }

    // ── Overlay helpers ──────────────────────────────────────────────────
    function _addOverlays(inst, chartData, overlays) {
        // SMA 10
        if (overlays.sma_10) {
            const series = inst.chart.addLineSeries({
                color: THEME.sma10Color,
                lineWidth: 1,
                crosshairMarkerVisible: false,
                lastValueVisible: false,
                priceLineVisible: false,
                title: 'SMA 10',
            });
            const data = overlays.sma_10
                .map((v, i) => v != null ? { time: _toTime(chartData[i].timestamp), value: v } : null)
                .filter(Boolean);
            series.setData(data);
            inst.overlays.sma10 = series;
        }

        // SMA 50
        if (overlays.sma_50) {
            const series = inst.chart.addLineSeries({
                color: THEME.sma50Color,
                lineWidth: 1,
                crosshairMarkerVisible: false,
                lastValueVisible: false,
                priceLineVisible: false,
                title: 'SMA 50',
            });
            const data = overlays.sma_50
                .map((v, i) => v != null ? { time: _toTime(chartData[i].timestamp), value: v } : null)
                .filter(Boolean);
            series.setData(data);
            inst.overlays.sma50 = series;
        }

        // Bollinger Bands
        if (overlays.bb_upper && overlays.bb_lower) {
            const upperSeries = inst.chart.addLineSeries({
                color: THEME.bbColor,
                lineWidth: 1,
                lineStyle: LightweightCharts.LineStyle.Dashed,
                crosshairMarkerVisible: false,
                lastValueVisible: false,
                priceLineVisible: false,
            });
            const lowerSeries = inst.chart.addLineSeries({
                color: THEME.bbColor,
                lineWidth: 1,
                lineStyle: LightweightCharts.LineStyle.Dashed,
                crosshairMarkerVisible: false,
                lastValueVisible: false,
                priceLineVisible: false,
            });

            const upperData = overlays.bb_upper
                .map((v, i) => v != null ? { time: _toTime(chartData[i].timestamp), value: v } : null)
                .filter(Boolean);
            const lowerData = overlays.bb_lower
                .map((v, i) => v != null ? { time: _toTime(chartData[i].timestamp), value: v } : null)
                .filter(Boolean);

            upperSeries.setData(upperData);
            lowerSeries.setData(lowerData);
            inst.overlays.bbUpper = upperSeries;
            inst.overlays.bbLower = lowerSeries;
        }
    }

    function _clearOverlays(inst) {
        for (const key of Object.keys(inst.overlays)) {
            try { inst.chart.removeSeries(inst.overlays[key]); } catch (e) {}
        }
        inst.overlays = {};
    }

    function _clearTrendlines(inst) {
        for (const s of inst.trendlineSeries) {
            try { inst.chart.removeSeries(s); } catch (e) {}
        }
        inst.trendlineSeries = [];
    }

    // ── Destroy ──────────────────────────────────────────────────────────
    function destroy(containerId) {
        const inst = instances[containerId];
        if (inst) {
            try { inst.chart.remove(); } catch (e) {}
            try { inst.volumeChart.remove(); } catch (e) {}
            delete instances[containerId];
        }
    }

    // ── Time conversion ──────────────────────────────────────────────────
    function _toTime(timestamp) {
        // Lightweight Charts expects { year, month, day } for daily bars
        // or UTC seconds for intraday
        if (typeof timestamp === 'string') {
            // Extract date part (first 10 chars) — works for:
            // "2025-10-03", "2025-10-03T00:00:00", "2025-10-03T00:00:00-04:00"
            const datePart = timestamp.substring(0, 10);
            const parts = datePart.split('-');
            if (parts.length === 3 && parts[0].length === 4) {
                const y = parseInt(parts[0]);
                const m = parseInt(parts[1]);
                const d = parseInt(parts[2]);
                // Check if this is intraday (has a non-midnight time)
                const timePart = timestamp.substring(11, 19);
                if (!timePart || timePart === '00:00:00' || timePart === '') {
                    return { year: y, month: m, day: d };
                }
                // Intraday — use UTC seconds
                return Math.floor(new Date(timestamp).getTime() / 1000);
            }
        }
        if (typeof timestamp === 'number') return timestamp;
        return Math.floor(new Date(timestamp).getTime() / 1000);
    }

    // ── Resize handler ───────────────────────────────────────────────────
    function resize(containerId) {
        const inst = instances[containerId];
        if (!inst) return;
        const rect = inst.container.getBoundingClientRect();
        inst.chart.applyOptions({ width: rect.width });
        inst.volumeChart.applyOptions({ width: rect.width });
    }

    // ── Pattern Markers ───────────────────────────────────────────────────
    function setPatterns(containerId, patternData) {
        const inst = instances[containerId];
        if (!inst || !patternData?.patterns?.length) return;

        // Add markers to candlestick series
        const markers = patternData.patterns.map(p => ({
            time: _toTime(p.timestamp),
            position: p.direction === 'bullish' ? 'belowBar' : p.direction === 'bearish' ? 'aboveBar' : 'inBar',
            color: p.direction === 'bullish' ? '#26a69a' : p.direction === 'bearish' ? '#ef5350' : '#f0b90b',
            shape: p.direction === 'bullish' ? 'arrowUp' : p.direction === 'bearish' ? 'arrowDown' : 'circle',
            text: `${p.pattern} ${p.probability}%`,
        }));

        // Sort markers by time (required by Lightweight Charts)
        markers.sort((a, b) => {
            const ta = typeof a.time === 'object' ? new Date(a.time.year, a.time.month - 1, a.time.day).getTime() : a.time * 1000;
            const tb = typeof b.time === 'object' ? new Date(b.time.year, b.time.month - 1, b.time.day).getTime() : b.time * 1000;
            return ta - tb;
        });

        inst.candleSeries.setMarkers(markers);

        // Render pattern legend bar
        _renderPatternBar(containerId, patternData.patterns);
    }

    function _renderPatternBar(containerId, patterns) {
        const bar = document.getElementById('patternMarkers');
        if (!bar || !patterns.length) return;

        bar.style.display = 'block';
        bar.innerHTML = patterns.slice(0, 5).map(p => {
            const cls = p.direction === 'bullish' ? 'positive' : p.direction === 'bearish' ? 'negative' : '';
            return `<div class="pattern-chip ${cls}" title="${p.description}">
                <span class="pattern-name">${p.pattern}</span>
                <span class="pattern-prob">${p.probability}%</span>
            </div>`;
        }).join('');
    }

    // ── Compare Overlay ──────────────────────────────────────────────────
    function setCompare(containerId, compareData) {
        const inst = instances[containerId];
        if (!inst || !compareData?.symbols?.length) return;

        // Clear existing compare series
        if (inst.compareSeries) {
            for (const s of inst.compareSeries) {
                try { inst.chart.removeSeries(s); } catch (e) {}
            }
        }
        inst.compareSeries = [];

        // Note: comparison uses a separate right price scale (percentage)
        const colors = ['#2962FF', '#FF6D00', '#AB47BC', '#00BFA5'];

        compareData.symbols.forEach((sym, idx) => {
            if (sym.symbol === inst.ticker) return; // Skip the main ticker

            const series = inst.chart.addLineSeries({
                color: colors[idx % colors.length],
                lineWidth: 1,
                crosshairMarkerVisible: true,
                lastValueVisible: true,
                priceLineVisible: false,
                title: sym.label,
                priceScaleId: 'compare',
                priceFormat: { type: 'custom', formatter: v => v.toFixed(1) + '%' },
            });

            const data = sym.data.map(d => ({
                time: _toTime(d.timestamp),
                value: d.value,
            }));

            series.setData(data);
            inst.compareSeries.push(series);
        });

        // Configure the compare scale
        inst.chart.priceScale('compare').applyOptions({
            scaleMargins: { top: 0.1, bottom: 0.1 },
            borderVisible: false,
            visible: true,
        });
    }

    function clearCompare(containerId) {
        const inst = instances[containerId];
        if (!inst?.compareSeries) return;
        for (const s of inst.compareSeries) {
            try { inst.chart.removeSeries(s); } catch (e) {}
        }
        inst.compareSeries = [];
    }

    // ── Seasonality Heatmap ──────────────────────────────────────────────
    function renderSeasonality(containerId, seasonality) {
        const el = document.getElementById('seasonalityContainer');
        if (!el || !seasonality?.monthly) return;

        el.style.display = 'block';
        const months = seasonality.monthly;

        let html = '<div class="seasonality-header">Monthly Seasonality (5yr)</div>';
        html += '<div class="seasonality-grid">';

        for (const m of months) {
            const ret = m.avg_return;
            const cls = ret > 1 ? 'strong-bull' : ret > 0 ? 'mild-bull' : ret > -1 ? 'mild-bear' : 'strong-bear';
            const bg = ret > 2 ? 'rgba(38,166,154,0.5)' : ret > 0 ? 'rgba(38,166,154,0.2)' : ret > -2 ? 'rgba(239,83,80,0.2)' : 'rgba(239,83,80,0.5)';

            html += `<div class="seasonality-cell" style="background:${bg}" title="${m.name}: avg ${ret > 0 ? '+' : ''}${ret.toFixed(1)}% return, ${m.win_rate.toFixed(0)}% win rate (${m.count} years)">
                <span class="s-month">${m.name}</span>
                <span class="s-return ${cls}">${ret > 0 ? '+' : ''}${ret.toFixed(1)}%</span>
                <span class="s-winrate">${m.win_rate.toFixed(0)}% win</span>
            </div>`;
        }

        html += '</div>';
        el.innerHTML = html;
    }

    // ── Full Screen ──────────────────────────────────────────────────────
    function toggleFullscreen(containerId) {
        const card = document.getElementById(containerId)?.closest('.analyze-chart-card');
        if (!card) return;

        card.classList.toggle('chart-fullscreen');
        document.body.classList.toggle('chart-fullscreen-active');

        // Resize after transition
        setTimeout(() => resize(containerId), 100);
    }

    return { create, setData, setTrendlines, setPatterns, setCompare, clearCompare,
             renderSeasonality, toggleFullscreen, destroy, resize, instances };
})();

// Auto-resize all charts on window resize
window.addEventListener('resize', () => {
    for (const id of Object.keys(AlphaCharts.instances)) {
        AlphaCharts.resize(id);
    }
});
