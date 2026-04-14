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
            chartData: null, // stored for indicator calculations
            indicatorPanes: {},
        };

        instances[containerId] = instance;
        return instance;
    }

    // ── Set OHLCV Data ───────────────────────────────────────────────────
    function setData(containerId, chartData, overlays) {
        const inst = instances[containerId];
        if (!inst || !chartData || !chartData.length) return;

        // Store raw data for indicator calculations
        inst.chartData = chartData;

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

        // Draw horizontal support/resistance levels (top 2 only to reduce clutter)
        for (const level of supportLevels.slice(0, 2)) {
            _drawHorizontalLevel(inst, level, 'support');
        }
        for (const level of resistanceLevels.slice(0, 2)) {
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

        // Only show price line for high-confidence trendlines (reduce clutter)
        if (line.current_line_price && line.confidence >= 70) {
            lineSeries.createPriceLine({
                price: line.current_line_price,
                color: color,
                lineWidth: 1,
                lineStyle: LightweightCharts.LineStyle.Dotted,
                axisLabelVisible: false,
                title: '',
            });
        }

        inst.trendlineSeries.push(lineSeries);
    }

    // ── Draw horizontal level ────────────────────────────────────────────
    function _drawHorizontalLevel(inst, level, type) {
        const color = type === 'support' ? 'rgba(38,166,154,0.4)' : 'rgba(239,83,80,0.4)';

        inst.candleSeries.createPriceLine({
            price: level.price,
            color: color,
            lineWidth: 1,
            lineStyle: LightweightCharts.LineStyle.Dashed,
            axisLabelVisible: false,
            title: '',
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

    // ── Render trendline info panel (clickable with AI popover) ────────
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
        for (let idx = 0; idx < Math.min(lines.length, 5); idx++) {
            const line = lines[idx];
            const color = line.color?.hex || '#888';
            const distStr = line.distance_pct > 0
                ? `+${line.distance_pct.toFixed(1)}% above`
                : `${line.distance_pct.toFixed(1)}% below`;

            html += `<div class="trendline-item trendline-clickable" data-trendline-idx="${idx}" title="Click for AI analysis">
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

        // Bind click handlers for AI popover
        panel.querySelectorAll('.trendline-clickable').forEach(item => {
            item.addEventListener('click', (e) => {
                const idx = parseInt(item.dataset.trendlineIdx);
                const line = lines[idx];
                if (line) _showTrendlinePopover(item, line, data);
            });
        });
    }

    // ── AI Trendline Popover ────────────────────────────────────────────
    function _showTrendlinePopover(anchor, line, data) {
        // Remove existing popover
        document.querySelector('.trendline-popover')?.remove();

        const regime = data.regime || 'RANGE';
        const projections = line.projections || {};
        const breakdown = line.score_breakdown || {};

        // Build confidence breakdown bar chart
        const factors = [
            { label: 'Touches', value: breakdown.touches || 0, max: 25 },
            { label: 'Recency', value: breakdown.recency || 0, max: 20 },
            { label: 'Volume', value: breakdown.volume || 0, max: 15 },
            { label: 'Proximity', value: breakdown.proximity || 0, max: 20 },
            { label: 'Regime', value: breakdown.regime || 0, max: 10 },
            { label: 'Span', value: breakdown.span || 0, max: 10 },
        ];

        const typeLabel = line.type === 'support' ? 'Support' : 'Resistance';
        const actionLabel = line.type === 'support'
            ? (line.distance_pct < 1 ? 'Near support — potential bounce entry' : 'Support below — hold / add on pullback')
            : (line.distance_pct > -1 ? 'Near resistance — consider profit-taking' : 'Resistance above — watch for breakout');

        const analogText = line.analog_score >= 70
            ? `Strong historical match: ${line.analog_score}% of similar ${regime} setups resolved in the expected direction.`
            : line.analog_score >= 40
                ? `Moderate analog match: ${line.analog_score}% agreement. Mixed historical outcomes.`
                : `Weak analog match: ${line.analog_score}%. Insufficient historical precedent for high-conviction trading.`;

        const popover = document.createElement('div');
        popover.className = 'trendline-popover';
        popover.innerHTML = `
            <div class="tp-header">
                <h4>${typeLabel} Line — AI Analysis</h4>
                <button class="tp-close">&times;</button>
            </div>
            <div class="tp-body">
                <div class="tp-row tp-action">
                    <span class="tp-action-icon">${line.type === 'support' ? '&#9650;' : '&#9660;'}</span>
                    <span>${actionLabel}</span>
                </div>

                <div class="tp-section">
                    <h5>Confidence Breakdown (${line.confidence}/100)</h5>
                    <div class="tp-factors">
                        ${factors.map(f => `
                            <div class="tp-factor">
                                <span class="tp-factor-label">${f.label}</span>
                                <div class="tp-factor-bar">
                                    <div class="tp-factor-fill" style="width:${(f.value / f.max * 100).toFixed(0)}%;background:${f.value >= f.max * 0.7 ? '#26a69a' : f.value >= f.max * 0.4 ? '#f0b90b' : '#ef5350'}"></div>
                                </div>
                                <span class="tp-factor-val">${f.value}/${f.max}</span>
                            </div>
                        `).join('')}
                    </div>
                </div>

                <div class="tp-section">
                    <h5>Historical Analog</h5>
                    <p class="tp-analog-text">${analogText}</p>
                </div>

                ${projections.bars_5 ? `
                <div class="tp-section">
                    <h5>Price Projections</h5>
                    <div class="tp-projections">
                        <div class="tp-proj"><span>5 bars</span><strong>$${projections.bars_5.toFixed(2)}</strong></div>
                        <div class="tp-proj"><span>10 bars</span><strong>$${projections.bars_10.toFixed(2)}</strong></div>
                        <div class="tp-proj"><span>20 bars</span><strong>$${projections.bars_20.toFixed(2)}</strong></div>
                    </div>
                </div>
                ` : ''}

                <div class="tp-section tp-levels">
                    <div class="tp-level-row">
                        <span>Current Line Price</span>
                        <strong>$${line.current_line_price?.toFixed(2)}</strong>
                    </div>
                    <div class="tp-level-row">
                        <span>Distance from Price</span>
                        <strong class="${line.distance_pct > 0 ? 'positive' : 'negative'}">${line.distance_pct > 0 ? '+' : ''}${line.distance_pct.toFixed(2)}%</strong>
                    </div>
                    <div class="tp-level-row">
                        <span>Touch Count</span>
                        <strong>${line.touch_count || line.touches?.length || 0}</strong>
                    </div>
                    <div class="tp-level-row">
                        <span>Market Regime</span>
                        <strong>${regime}</strong>
                    </div>
                </div>
            </div>
        `;

        // Position near the anchor
        document.body.appendChild(popover);
        const anchorRect = anchor.getBoundingClientRect();
        popover.style.top = `${anchorRect.bottom + 8}px`;
        popover.style.left = `${Math.min(anchorRect.left, window.innerWidth - 340)}px`;

        // Close handlers
        popover.querySelector('.tp-close').addEventListener('click', () => popover.remove());
        setTimeout(() => {
            const closeOnClick = (e) => {
                if (!popover.contains(e.target) && !anchor.contains(e.target)) {
                    popover.remove();
                    document.removeEventListener('click', closeOnClick);
                }
            };
            document.addEventListener('click', closeOnClick);
        }, 100);
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

    // ── Export Chart as PNG ─────────────────────────────────────────────
    // Uses lightweight-charts' native takeScreenshot() which returns an
    // HTMLCanvasElement of the price pane only. For the final PNG we stitch
    // the main chart on top of the volume histogram, plus any indicator
    // sub-panes, so the export looks like what the user sees on screen.
    function exportPNG(containerId) {
        const inst = instances[containerId];
        if (!inst?.chart) return;

        const panes = [inst.chart];
        if (inst.volumeChart) panes.push(inst.volumeChart);
        for (const key of Object.keys(inst.indicatorPanes || {})) {
            const p = inst.indicatorPanes[key]?.pane?.chart;
            if (p) panes.push(p);
        }

        const canvases = panes
            .map(c => { try { return c.takeScreenshot(); } catch (e) { return null; } })
            .filter(Boolean);
        if (!canvases.length) return;

        const width = Math.max(...canvases.map(c => c.width));
        const totalHeight = canvases.reduce((sum, c) => sum + c.height, 0);

        const out = document.createElement('canvas');
        out.width = width;
        out.height = totalHeight;
        const ctx = out.getContext('2d');
        ctx.fillStyle = '#131722';
        ctx.fillRect(0, 0, width, totalHeight);

        let y = 0;
        for (const c of canvases) {
            ctx.drawImage(c, 0, y);
            y += c.height;
        }

        // Watermark
        ctx.fillStyle = 'rgba(139, 149, 165, 0.5)';
        ctx.font = 'bold 11px Inter, sans-serif';
        ctx.textAlign = 'right';
        ctx.textBaseline = 'bottom';
        ctx.fillText('alphabreak.vip', width - 8, totalHeight - 6);

        const ticker = inst.ticker || 'chart';
        const fileName = `${ticker}_${new Date().toISOString().slice(0, 10)}.png`;
        out.toBlob(blob => {
            if (!blob) return;
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = fileName;
            document.body.appendChild(a);
            a.click();
            a.remove();
            URL.revokeObjectURL(url);
        }, 'image/png');
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

    // ── Indicator Pane Toggles ─────────────────────────────────────────
    function toggleIndicator(containerId, indicator) {
        const inst = instances[containerId];
        if (!inst?.chartData) return;

        if (typeof ChartIndicators === 'undefined') return;

        // If already rendered, destroy it
        if (inst.indicatorPanes[indicator]) {
            const pane = inst.indicatorPanes[indicator];
            if (pane.pane?.wrapper) pane.pane.wrapper.remove();
            delete inst.indicatorPanes[indicator];
            return;
        }

        // Render the indicator pane
        switch (indicator) {
            case 'rsi':
                inst.indicatorPanes.rsi = ChartIndicators.renderRSI(containerId, inst.chartData, inst.chart);
                break;
            case 'macd':
                inst.indicatorPanes.macd = ChartIndicators.renderMACD(containerId, inst.chartData, inst.chart);
                break;
            case 'stochastic':
                inst.indicatorPanes.stochastic = ChartIndicators.renderStochastic(containerId, inst.chartData, inst.chart);
                break;
            case 'atr':
                inst.indicatorPanes.atr = ChartIndicators.renderATR(containerId, inst.chartData, inst.chart);
                break;
            case 'adx':
                inst.indicatorPanes.adx = ChartIndicators.renderADX(containerId, inst.chartData, inst.chart);
                break;
            case 'obv':
                inst.indicatorPanes.obv = ChartIndicators.renderOBV(containerId, inst.chartData, inst.chart);
                break;
            case 'squeeze':
                inst.indicatorPanes.squeeze = ChartIndicators.renderSqueezeMomentum(containerId, inst.chartData, inst.chart);
                break;
            case 'vwap':
                if (inst.overlays.vwap) {
                    try { inst.chart.removeSeries(inst.overlays.vwap); } catch (e) {}
                    delete inst.overlays.vwap;
                } else {
                    ChartIndicators.addVWAP(inst, inst.chartData);
                }
                break;
            case 'supertrend':
                if (inst.overlays.supertrendUp || inst.overlays.supertrendDown) {
                    ChartIndicators.removeSupertrend(inst);
                } else {
                    ChartIndicators.addSupertrend(inst, inst.chartData);
                }
                break;
            case 'keltner':
                if (inst.overlays.keltnerMid) {
                    ChartIndicators.removeKeltner(inst);
                } else {
                    ChartIndicators.addKeltner(inst, inst.chartData);
                }
                break;
            case 'ichimoku':
                if (inst.overlays.ichiTenkan) {
                    ChartIndicators.removeIchimoku(inst);
                } else {
                    ChartIndicators.addIchimoku(inst, inst.chartData);
                }
                break;
            case 'vpvr':
                if (inst.overlays.vpvr) {
                    inst.overlays.vpvr.destroy();
                    delete inst.overlays.vpvr;
                } else if (typeof ChartVolumeProfile !== 'undefined') {
                    inst.overlays.vpvr = ChartVolumeProfile.attach(inst, inst.chartData);
                }
                break;
        }
    }

    // ── Drawing Tools Integration ───────────────────────────────────────
    function initDrawings(containerId, ticker) {
        const inst = instances[containerId];
        if (!inst || typeof ChartDrawings === 'undefined') return;

        ChartDrawings.init(containerId, inst, ticker);
        ChartDrawings.createToolbar(containerId);
        ChartDrawings.bindChartUpdates(inst);
    }

    // ── Quick-create: Candlestick from raw data ────────────────────────
    // Usage: AlphaCharts.quickCandlestick('myDiv', data, { height: 200 })
    // data = [{ date/timestamp, open, high, low, close, volume?, sma_20? }]
    function quickCandlestick(containerId, rawData, options = {}) {
        if (!rawData || !rawData.length) return null;

        // Ensure we have a div container (replace canvas if needed)
        _ensureDiv(containerId, options.height || 200);

        destroy(containerId);

        const height = options.height || 200;
        const showVolume = options.showVolume !== false && rawData[0].volume != null;
        const volH = showVolume ? (options.volumeHeight || 40) : 0;

        // Set container height before creating chart
        const el = document.getElementById(containerId);
        if (!el) return null;
        el.style.height = height + 'px';

        const inst = create(containerId, { height: height - volH, volumeHeight: volH });
        if (!inst) return null;

        // Normalize data
        const chartData = rawData.map(d => ({
            timestamp: d.date || d.timestamp,
            open: d.open, high: d.high, low: d.low, close: d.close,
            volume: d.volume || 0,
        }));

        // Build overlays
        const overlays = {};
        if (rawData[0].sma_20 !== undefined) {
            overlays.sma_10 = rawData.map(d => d.sma_20 != null ? d.sma_20 : null);
        }

        setData(containerId, chartData, Object.keys(overlays).length ? overlays : null);

        if (options.ticker) inst.ticker = options.ticker;
        return inst;
    }

    // ── Quick-create: Line chart ─────────────────────────────────────
    // Usage: AlphaCharts.quickLine('myDiv', data, { keys, labels, colors, height })
    // data = [{ date/timestamp, value1, value2, ... }]
    // ── Helper: ensure container is a div ──────────────────────────────
    function _ensureDiv(containerId, height) {
        let el = document.getElementById(containerId);
        if (!el) return null;

        if (el.tagName === 'CANVAS') {
            const div = document.createElement('div');
            div.id = containerId;
            div.style.width = '100%';
            div.style.height = (height || 200) + 'px';
            el.parentNode.replaceChild(div, el);
            return div;
        }
        return el;
    }

    function quickLine(containerId, rawData, options = {}) {
        if (!rawData || !rawData.length) return null;

        _ensureDiv(containerId, options.height || 200);
        destroy(containerId);

        const height = options.height || 200;
        const chartDiv = document.getElementById(containerId);
        if (!chartDiv) return null;
        chartDiv.innerHTML = '';
        chartDiv.style.height = height + 'px';

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
            rightPriceScale: {
                borderColor: THEME.gridColor,
                scaleMargins: { top: 0.08, bottom: 0.08 },
            },
            timeScale: {
                borderColor: THEME.gridColor,
                timeVisible: true,
            },
            handleScroll: { mouseWheel: true, pressedMouseMove: true },
            handleScale: { mouseWheel: true, pinch: true },
            crosshair: {
                mode: LightweightCharts.CrosshairMode.Normal,
                vertLine: { color: THEME.crosshair, width: 1, style: 2 },
                horzLine: { color: THEME.crosshair, width: 1, style: 2 },
            },
        });

        const keys = options.keys || ['close', 'value'];
        const colors = options.colors || ['#2962FF', '#FF6D00', '#AB47BC', '#26a69a'];
        const labels = options.labels || keys;
        const seriesList = [];

        for (let i = 0; i < keys.length; i++) {
            const key = keys[i];
            // Check if data has this key
            if (rawData[0][key] === undefined) continue;

            const isArea = i === 0 && options.area !== false;
            let series;

            if (isArea) {
                series = chart.addAreaSeries({
                    lineColor: colors[i % colors.length],
                    topColor: colors[i % colors.length] + '30',
                    bottomColor: colors[i % colors.length] + '05',
                    lineWidth: 2,
                    crosshairMarkerVisible: true,
                    lastValueVisible: true,
                    priceLineVisible: false,
                    title: labels[i],
                });
            } else {
                series = chart.addLineSeries({
                    color: colors[i % colors.length],
                    lineWidth: 2,
                    crosshairMarkerVisible: true,
                    lastValueVisible: true,
                    priceLineVisible: false,
                    title: labels[i],
                });
            }

            const lineData = rawData
                .map(d => {
                    if (d[key] == null) return null;
                    return { time: _toTime(d.date || d.timestamp), value: d[key] };
                })
                .filter(Boolean);

            series.setData(lineData);
            seriesList.push(series);
        }

        chart.timeScale().fitContent();

        // Custom price formatter if provided
        if (options.priceFormat === 'currency') {
            chart.priceScale('right').applyOptions({
                mode: 0,
            });
        }

        instances[containerId] = { chart, volumeChart: null, candleSeries: seriesList[0], volumeSeries: null, container: chartDiv, overlays: {}, trendlineSeries: [], levelLines: [], chartData: rawData, indicatorPanes: {} };

        return instances[containerId];
    }

    // ── Multi-Chart Layout with Synced Crosshairs ───────────────────────
    // Usage: AlphaCharts.multiChart('containerId', [
    //   { ticker: 'AAPL', period: '6mo', interval: '1d' },
    //   { ticker: 'AAPL', period: '1mo', interval: '1h' },
    // ], { onLoadChart: async (ticker, period, interval) => chartData })
    //
    // Returns a controller object with methods: addChart, removeChart, destroy, getCharts

    const multiChartInstances = {};

    function multiChart(containerId, configs, options = {}) {
        const container = document.getElementById(containerId);
        if (!container) return null;

        // Destroy existing multi-chart
        destroyMultiChart(containerId);

        const count = Math.min(4, Math.max(2, configs.length));
        const cols = count <= 2 ? 2 : 2; // Always 2 columns; 2 charts = 1 row, 3-4 = 2 rows

        // Build grid container
        container.innerHTML = '';
        container.classList.add('multi-chart-grid');
        container.style.gridTemplateColumns = `repeat(${cols}, 1fr)`;

        const chartCells = [];
        const chartInstances = [];
        let syncingCrosshair = false;

        for (let i = 0; i < count; i++) {
            const cfg = configs[i] || configs[0];
            const cell = _createMultiChartCell(containerId, i, cfg, options);
            container.appendChild(cell.wrapper);
            chartCells.push(cell);
        }

        // Store the multi-chart controller
        const controller = {
            containerId,
            cells: chartCells,
            configs: configs.slice(0, count),
            options,
            syncingCrosshair: false,
        };

        multiChartInstances[containerId] = controller;

        // Load data for each chart
        for (let i = 0; i < chartCells.length; i++) {
            const cfg = configs[i] || configs[0];
            _loadMultiChartData(controller, i, cfg.ticker, cfg.period, cfg.interval);
        }

        return controller;
    }

    function _createMultiChartCell(parentId, index, cfg, options) {
        const wrapper = document.createElement('div');
        wrapper.className = 'multi-chart-cell';
        wrapper.dataset.index = index;

        // Header with ticker input + period buttons
        const header = document.createElement('div');
        header.className = 'multi-chart-cell-header';

        // Ticker input
        const tickerInput = document.createElement('input');
        tickerInput.type = 'text';
        tickerInput.className = 'multi-chart-ticker-input';
        tickerInput.value = cfg.ticker || '';
        tickerInput.placeholder = 'TICKER';
        tickerInput.maxLength = 10;
        tickerInput.addEventListener('input', () => {
            tickerInput.value = tickerInput.value.toUpperCase();
        });
        tickerInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                const ticker = tickerInput.value.trim().toUpperCase();
                if (ticker) {
                    const ctrl = multiChartInstances[parentId];
                    if (ctrl) {
                        const cell = ctrl.cells[index];
                        const period = cell.currentPeriod || '6mo';
                        const interval = cell.currentInterval || '1d';
                        _loadMultiChartData(ctrl, index, ticker, period, interval);
                    }
                }
            }
        });
        header.appendChild(tickerInput);

        // Period buttons
        const periods = document.createElement('div');
        periods.className = 'multi-chart-periods';
        const periodConfigs = [
            { label: '1D', period: '1d', interval: '5m' },
            { label: '5D', period: '5d', interval: '15m' },
            { label: '1M', period: '1mo', interval: '1d' },
            { label: '6M', period: '6mo', interval: '1d' },
            { label: '1Y', period: '1y', interval: '1d' },
        ];
        for (const pc of periodConfigs) {
            const btn = document.createElement('button');
            btn.textContent = pc.label;
            btn.dataset.period = pc.period;
            btn.dataset.interval = pc.interval;
            if (pc.period === cfg.period) btn.classList.add('active');
            btn.addEventListener('click', () => {
                periods.querySelectorAll('button').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                const ctrl = multiChartInstances[parentId];
                if (ctrl) {
                    const ticker = tickerInput.value.trim().toUpperCase() || cfg.ticker;
                    _loadMultiChartData(ctrl, index, ticker, pc.period, pc.interval);
                }
            });
            periods.appendChild(btn);
        }
        header.appendChild(periods);

        wrapper.appendChild(header);

        // Chart container
        const chartDiv = document.createElement('div');
        chartDiv.id = `${parentId}_mc_${index}`;
        chartDiv.className = 'multi-chart-inner lw-chart-container';
        wrapper.appendChild(chartDiv);

        return {
            wrapper,
            chartDivId: chartDiv.id,
            tickerInput,
            periods,
            currentPeriod: cfg.period || '6mo',
            currentInterval: cfg.interval || '1d',
            instance: null,
            candleData: null,
        };
    }

    async function _loadMultiChartData(controller, index, ticker, period, interval) {
        const cell = controller.cells[index];
        if (!cell) return;

        cell.currentPeriod = period;
        cell.currentInterval = interval;
        cell.tickerInput.value = ticker;

        // Show loading state
        const chartDiv = document.getElementById(cell.chartDivId);
        if (!chartDiv) return;

        // Use the provided data loader, or the default API
        const onLoadChart = controller.options.onLoadChart;
        let chartData = null;

        try {
            if (onLoadChart) {
                chartData = await onLoadChart(ticker, period, interval);
            } else {
                const resp = await apiRequest(`/api/analyze/${ticker}/chart?period=${period}&interval=${interval}`);
                if (!resp.ok) throw new Error(`Chart API error: ${resp.status}`);
                chartData = await resp.json();
            }
        } catch (e) {
            chartDiv.innerHTML = `<div class="empty-state empty-state--fill">Failed to load ${ticker}</div>`;
            return;
        }

        if (!chartData?.data?.length) {
            chartDiv.innerHTML = `<div class="empty-state empty-state--fill">No data for ${ticker}</div>`;
            return;
        }

        // Destroy existing chart in this cell
        destroy(cell.chartDivId);

        // Create new chart
        const inst = create(cell.chartDivId, { height: 220, volumeHeight: 40 });
        if (!inst) return;

        inst.ticker = ticker;
        cell.instance = inst;
        cell.candleData = chartData.data;

        // Set data with overlays
        const overlays = chartData.overlays || {};
        setData(cell.chartDivId, chartData.data, overlays);

        // Set up crosshair sync
        _setupCrosshairSync(controller, index);
    }

    // Normalize a lightweight-charts time to unix seconds for cross-timeframe
    // comparison. Day-resolution charts emit {year, month, day}; intraday
    // charts emit a number (seconds). Returns null if we can't parse.
    function _timeToSec(time) {
        if (time == null) return null;
        if (typeof time === 'number') return time;
        if (typeof time === 'object' && 'year' in time) {
            return Math.floor(new Date(Date.UTC(time.year, time.month - 1, time.day)).getTime() / 1000);
        }
        return null;
    }

    // Binary-search the nearest candle in a cell's data to a given unix-seconds
    // target. Returns the candle (which has timestamp + OHLCV fields) or null.
    function _findNearestCandle(cell, targetSec) {
        const data = cell?.candleData;
        if (!data?.length || targetSec == null) return null;

        let bestIdx = 0, bestDist = Infinity;
        for (let i = 0; i < data.length; i++) {
            const ts = data[i].timestamp || data[i].date;
            const s = typeof ts === 'string'
                ? Math.floor(new Date(ts).getTime() / 1000)
                : Number(ts);
            if (!isFinite(s)) continue;
            const dist = Math.abs(s - targetSec);
            if (dist < bestDist) { bestDist = dist; bestIdx = i; }
        }
        return data[bestIdx] || null;
    }

    // Convert a candle's timestamp back to the lightweight-charts time shape
    // the destination chart expects. Day-resolution target charts need the
    // {year,month,day} form; intraday targets want unix seconds.
    function _candleTimeForCell(candle, cell) {
        const interval = cell.currentInterval || '1d';
        const isDaily = interval === '1d' || interval === '1wk' || interval === '1mo';
        const ts = candle.timestamp || candle.date;
        if (isDaily) {
            const d = new Date(ts);
            return { year: d.getUTCFullYear(), month: d.getUTCMonth() + 1, day: d.getUTCDate() };
        }
        return typeof ts === 'string'
            ? Math.floor(new Date(ts).getTime() / 1000)
            : Number(ts);
    }

    function _setupCrosshairSync(controller, sourceIndex) {
        const sourceCell = controller.cells[sourceIndex];
        if (!sourceCell?.instance?.chart) return;

        sourceCell.instance.chart.subscribeCrosshairMove((param) => {
            if (controller.syncingCrosshair) return;
            controller.syncingCrosshair = true;

            try {
                const sourceSec = _timeToSec(param.time);
                if (sourceSec == null) {
                    // Clear crosshairs on other charts
                    for (let i = 0; i < controller.cells.length; i++) {
                        if (i === sourceIndex) continue;
                        const cell = controller.cells[i];
                        if (cell?.instance?.chart) {
                            try { cell.instance.chart.clearCrosshairPosition(); } catch (e) {}
                        }
                    }
                    return;
                }

                // For each other cell, find the nearest candle to the source
                // time and set crosshair at (close, time-in-target-shape).
                // Passing undefined for price breaks silently in v4.1 — we
                // need a real finite number.
                for (let i = 0; i < controller.cells.length; i++) {
                    if (i === sourceIndex) continue;
                    const cell = controller.cells[i];
                    if (!cell?.instance?.chart || !cell?.instance?.candleSeries) continue;

                    const candle = _findNearestCandle(cell, sourceSec);
                    if (!candle) continue;

                    const targetTime = _candleTimeForCell(candle, cell);
                    const price = Number(candle.close);
                    if (!isFinite(price)) continue;

                    try {
                        cell.instance.chart.setCrosshairPosition(
                            price,
                            targetTime,
                            cell.instance.candleSeries
                        );
                    } catch (e) { /* silently skip this cell */ }
                }
            } finally {
                controller.syncingCrosshair = false;
            }
        });
    }

    function multiChartAddCell(containerId, cfg) {
        const controller = multiChartInstances[containerId];
        if (!controller) return;
        if (controller.cells.length >= 4) return; // Max 4

        const container = document.getElementById(containerId);
        if (!container) return;

        const index = controller.cells.length;
        const cell = _createMultiChartCell(containerId, index, cfg, controller.options);
        container.appendChild(cell.wrapper);
        controller.cells.push(cell);
        controller.configs.push(cfg);

        // Update grid: always 2 columns
        container.style.gridTemplateColumns = 'repeat(2, 1fr)';

        _loadMultiChartData(controller, index, cfg.ticker, cfg.period, cfg.interval);
    }

    function multiChartRemoveCell(containerId, index) {
        const controller = multiChartInstances[containerId];
        if (!controller || controller.cells.length <= 2) return; // Min 2

        const cell = controller.cells[index];
        if (!cell) return;

        destroy(cell.chartDivId);
        cell.wrapper.remove();
        controller.cells.splice(index, 1);
        controller.configs.splice(index, 1);

        // Re-index remaining cells
        controller.cells.forEach((c, i) => {
            c.wrapper.dataset.index = i;
        });
    }

    function destroyMultiChart(containerId) {
        const controller = multiChartInstances[containerId];
        if (!controller) return;

        for (const cell of controller.cells) {
            destroy(cell.chartDivId);
        }

        const container = document.getElementById(containerId);
        if (container) {
            container.innerHTML = '';
            container.classList.remove('multi-chart-grid');
            container.style.gridTemplateColumns = '';
        }

        delete multiChartInstances[containerId];
    }

    function getMultiChartController(containerId) {
        return multiChartInstances[containerId] || null;
    }

    return { create, setData, setTrendlines, setPatterns, setCompare, clearCompare,
             renderSeasonality, toggleFullscreen, toggleIndicator, initDrawings, exportPNG,
             quickCandlestick, quickLine,
             multiChart, multiChartAddCell, multiChartRemoveCell, destroyMultiChart,
             getMultiChartController,
             destroy, resize, instances };
})();

// Auto-resize all charts on window resize
window.addEventListener('resize', () => {
    for (const id of Object.keys(AlphaCharts.instances)) {
        AlphaCharts.resize(id);
    }
});
