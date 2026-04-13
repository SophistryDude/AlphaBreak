// ============================================================================
// AlphaBreak Chart Indicators — Sub-pane indicators + client-side calculations
// ============================================================================
// Adds RSI, MACD, Stochastic, VWAP as proper chart sub-panes below main chart.
// All calculations done client-side from OHLCV data — no extra API calls.

const ChartIndicators = (() => {

    // ── Indicator Calculation Functions ──────────────────────────────────

    function calcRSI(closes, period = 14) {
        const rsi = new Array(closes.length).fill(null);
        if (closes.length < period + 1) return rsi;

        let avgGain = 0, avgLoss = 0;
        for (let i = 1; i <= period; i++) {
            const diff = closes[i] - closes[i - 1];
            if (diff > 0) avgGain += diff;
            else avgLoss -= diff;
        }
        avgGain /= period;
        avgLoss /= period;

        rsi[period] = avgLoss === 0 ? 100 : 100 - (100 / (1 + avgGain / avgLoss));

        for (let i = period + 1; i < closes.length; i++) {
            const diff = closes[i] - closes[i - 1];
            avgGain = (avgGain * (period - 1) + (diff > 0 ? diff : 0)) / period;
            avgLoss = (avgLoss * (period - 1) + (diff < 0 ? -diff : 0)) / period;
            rsi[i] = avgLoss === 0 ? 100 : 100 - (100 / (1 + avgGain / avgLoss));
        }
        return rsi;
    }

    function _ema(data, period) {
        const result = new Array(data.length).fill(null);
        const k = 2 / (period + 1);
        let first = 0, count = 0;
        for (let i = 0; i < data.length; i++) {
            if (data[i] != null) { first += data[i]; count++; }
            if (count === period) {
                result[i] = first / period;
                for (let j = i + 1; j < data.length; j++) {
                    if (data[j] != null) {
                        result[j] = data[j] * k + result[j - 1] * (1 - k);
                    }
                }
                break;
            }
        }
        return result;
    }

    function calcMACD(closes, fast = 12, slow = 26, signal = 9) {
        const emaFast = _ema(closes, fast);
        const emaSlow = _ema(closes, slow);
        const macdLine = new Array(closes.length).fill(null);

        for (let i = 0; i < closes.length; i++) {
            if (emaFast[i] != null && emaSlow[i] != null) {
                macdLine[i] = emaFast[i] - emaSlow[i];
            }
        }

        const signalLine = _ema(macdLine, signal);
        const histogram = new Array(closes.length).fill(null);
        for (let i = 0; i < closes.length; i++) {
            if (macdLine[i] != null && signalLine[i] != null) {
                histogram[i] = macdLine[i] - signalLine[i];
            }
        }

        return { macd: macdLine, signal: signalLine, histogram };
    }

    function calcStochastic(highs, lows, closes, kPeriod = 14, dPeriod = 3) {
        const kValues = new Array(closes.length).fill(null);

        for (let i = kPeriod - 1; i < closes.length; i++) {
            let highest = -Infinity, lowest = Infinity;
            for (let j = i - kPeriod + 1; j <= i; j++) {
                if (highs[j] > highest) highest = highs[j];
                if (lows[j] < lowest) lowest = lows[j];
            }
            const range = highest - lowest;
            kValues[i] = range === 0 ? 50 : ((closes[i] - lowest) / range) * 100;
        }

        // %D is SMA of %K
        const dValues = new Array(closes.length).fill(null);
        for (let i = kPeriod - 1 + dPeriod - 1; i < closes.length; i++) {
            let sum = 0;
            for (let j = 0; j < dPeriod; j++) {
                sum += kValues[i - j];
            }
            dValues[i] = sum / dPeriod;
        }

        return { k: kValues, d: dValues };
    }

    function calcVWAP(highs, lows, closes, volumes) {
        const vwap = new Array(closes.length).fill(null);
        let cumVol = 0, cumTP = 0;

        for (let i = 0; i < closes.length; i++) {
            const tp = (highs[i] + lows[i] + closes[i]) / 3;
            cumVol += volumes[i];
            cumTP += tp * volumes[i];
            vwap[i] = cumVol > 0 ? cumTP / cumVol : null;
        }
        return vwap;
    }

    // ── True Range + ATR ────────────────────────────────────────────────
    // Wilder's ATR: first value is a simple average of TR over `period`,
    // subsequent values use Wilder's smoothing: ATR = ((prev * (n-1)) + TR) / n.
    function calcATR(highs, lows, closes, period = 14) {
        const len = closes.length;
        const atr = new Array(len).fill(null);
        if (len < period + 1) return atr;

        const tr = new Array(len).fill(null);
        tr[0] = highs[0] - lows[0];
        for (let i = 1; i < len; i++) {
            const a = highs[i] - lows[i];
            const b = Math.abs(highs[i] - closes[i - 1]);
            const c = Math.abs(lows[i] - closes[i - 1]);
            tr[i] = Math.max(a, b, c);
        }

        let sum = 0;
        for (let i = 1; i <= period; i++) sum += tr[i];
        atr[period] = sum / period;
        for (let i = period + 1; i < len; i++) {
            atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period;
        }
        return atr;
    }

    // ── Supertrend ──────────────────────────────────────────────────────
    // Returns { value, direction } where direction is +1 (uptrend) or -1 (down).
    function calcSupertrend(highs, lows, closes, period = 10, multiplier = 3) {
        const len = closes.length;
        const atr = calcATR(highs, lows, closes, period);
        const value = new Array(len).fill(null);
        const direction = new Array(len).fill(null);

        let finalUpper = null, finalLower = null, prevDirection = 1;

        for (let i = 0; i < len; i++) {
            if (atr[i] == null) continue;
            const hl2 = (highs[i] + lows[i]) / 2;
            const basicUpper = hl2 + multiplier * atr[i];
            const basicLower = hl2 - multiplier * atr[i];

            const prevClose = closes[i - 1] ?? closes[i];
            finalUpper = (finalUpper == null || basicUpper < finalUpper || prevClose > finalUpper)
                ? basicUpper : finalUpper;
            finalLower = (finalLower == null || basicLower > finalLower || prevClose < finalLower)
                ? basicLower : finalLower;

            if (prevDirection === 1 && closes[i] < finalLower) prevDirection = -1;
            else if (prevDirection === -1 && closes[i] > finalUpper) prevDirection = 1;

            direction[i] = prevDirection;
            value[i] = prevDirection === 1 ? finalLower : finalUpper;
        }
        return { value, direction };
    }

    // ── Keltner Channels ────────────────────────────────────────────────
    function calcKeltner(highs, lows, closes, emaPeriod = 20, atrPeriod = 10, multiplier = 2) {
        const mid = _ema(closes, emaPeriod);
        const atr = calcATR(highs, lows, closes, atrPeriod);
        const upper = new Array(closes.length).fill(null);
        const lower = new Array(closes.length).fill(null);
        for (let i = 0; i < closes.length; i++) {
            if (mid[i] != null && atr[i] != null) {
                upper[i] = mid[i] + multiplier * atr[i];
                lower[i] = mid[i] - multiplier * atr[i];
            }
        }
        return { upper, mid, lower };
    }

    // ── ADX + DI± ───────────────────────────────────────────────────────
    // Classic Wilder calculation. Returns { adx, plusDI, minusDI }.
    function calcADX(highs, lows, closes, period = 14) {
        const len = closes.length;
        const plusDM = new Array(len).fill(0);
        const minusDM = new Array(len).fill(0);
        const tr = new Array(len).fill(0);

        for (let i = 1; i < len; i++) {
            const up = highs[i] - highs[i - 1];
            const down = lows[i - 1] - lows[i];
            plusDM[i] = (up > down && up > 0) ? up : 0;
            minusDM[i] = (down > up && down > 0) ? down : 0;
            const a = highs[i] - lows[i];
            const b = Math.abs(highs[i] - closes[i - 1]);
            const c = Math.abs(lows[i] - closes[i - 1]);
            tr[i] = Math.max(a, b, c);
        }

        // Wilder smoothing
        const smTR = new Array(len).fill(null);
        const smPlus = new Array(len).fill(null);
        const smMinus = new Array(len).fill(null);
        let sumTR = 0, sumPlus = 0, sumMinus = 0;
        for (let i = 1; i <= period; i++) {
            sumTR += tr[i]; sumPlus += plusDM[i]; sumMinus += minusDM[i];
        }
        smTR[period] = sumTR;
        smPlus[period] = sumPlus;
        smMinus[period] = sumMinus;
        for (let i = period + 1; i < len; i++) {
            smTR[i] = smTR[i - 1] - smTR[i - 1] / period + tr[i];
            smPlus[i] = smPlus[i - 1] - smPlus[i - 1] / period + plusDM[i];
            smMinus[i] = smMinus[i - 1] - smMinus[i - 1] / period + minusDM[i];
        }

        const plusDI = new Array(len).fill(null);
        const minusDI = new Array(len).fill(null);
        const dx = new Array(len).fill(null);
        for (let i = period; i < len; i++) {
            if (smTR[i] > 0) {
                plusDI[i] = (smPlus[i] / smTR[i]) * 100;
                minusDI[i] = (smMinus[i] / smTR[i]) * 100;
                const sum = plusDI[i] + minusDI[i];
                dx[i] = sum > 0 ? (Math.abs(plusDI[i] - minusDI[i]) / sum) * 100 : 0;
            }
        }

        const adx = new Array(len).fill(null);
        const firstAdxIdx = period * 2;
        if (firstAdxIdx < len) {
            let s = 0;
            for (let i = period; i < firstAdxIdx; i++) s += (dx[i] || 0);
            adx[firstAdxIdx - 1] = s / period;
            for (let i = firstAdxIdx; i < len; i++) {
                adx[i] = (adx[i - 1] * (period - 1) + (dx[i] || 0)) / period;
            }
        }
        return { adx, plusDI, minusDI };
    }

    // ── On-Balance Volume ───────────────────────────────────────────────
    function calcOBV(closes, volumes) {
        const obv = new Array(closes.length).fill(0);
        for (let i = 1; i < closes.length; i++) {
            const v = volumes[i] || 0;
            if (closes[i] > closes[i - 1]) obv[i] = obv[i - 1] + v;
            else if (closes[i] < closes[i - 1]) obv[i] = obv[i - 1] - v;
            else obv[i] = obv[i - 1];
        }
        return obv;
    }

    // ── Ichimoku Cloud ──────────────────────────────────────────────────
    // Returns tenkan (9), kijun (26), senkouA & senkouB shifted forward 26, chikou shifted back 26.
    // We don't render the forward shift visually (would require projecting future time slots);
    // instead we align senkouA/B to the *current* bar so the cloud covers the visible range.
    function calcIchimoku(highs, lows, closes, tenkanP = 9, kijunP = 26, senkouP = 52) {
        const len = closes.length;
        const tenkan = new Array(len).fill(null);
        const kijun = new Array(len).fill(null);
        const senkouA = new Array(len).fill(null);
        const senkouB = new Array(len).fill(null);
        const chikou = new Array(len).fill(null);

        const midpoint = (from, to) => {
            let hi = -Infinity, lo = Infinity;
            for (let j = from; j <= to; j++) {
                if (highs[j] > hi) hi = highs[j];
                if (lows[j] < lo) lo = lows[j];
            }
            return (hi + lo) / 2;
        };

        for (let i = 0; i < len; i++) {
            if (i >= tenkanP - 1) tenkan[i] = midpoint(i - tenkanP + 1, i);
            if (i >= kijunP - 1) kijun[i] = midpoint(i - kijunP + 1, i);
            if (tenkan[i] != null && kijun[i] != null) senkouA[i] = (tenkan[i] + kijun[i]) / 2;
            if (i >= senkouP - 1) senkouB[i] = midpoint(i - senkouP + 1, i);
            if (i + kijunP < len) chikou[i + kijunP] = closes[i];
        }
        return { tenkan, kijun, senkouA, senkouB, chikou };
    }

    // ── Theme colors for indicators ─────────────────────────────────────

    const COLORS = {
        rsi: '#2962FF',
        rsiOverbought: 'rgba(239, 83, 80, 0.3)',
        rsiOversold: 'rgba(38, 166, 154, 0.3)',
        macdLine: '#2962FF',
        macdSignal: '#FF6D00',
        macdHistUp: 'rgba(38, 166, 154, 0.6)',
        macdHistDown: 'rgba(239, 83, 80, 0.6)',
        stochK: '#2962FF',
        stochD: '#FF6D00',
        vwap: '#E040FB',
        // Week-1 additions
        supertrendUp: '#26a69a',
        supertrendDown: '#ef5350',
        keltnerUpper: 'rgba(255, 183, 77, 0.9)',
        keltnerMid: 'rgba(255, 183, 77, 0.5)',
        keltnerLower: 'rgba(255, 183, 77, 0.9)',
        adx: '#FFEB3B',
        plusDI: '#26a69a',
        minusDI: '#ef5350',
        adxThreshold: 'rgba(255, 255, 255, 0.25)',
        atr: '#80DEEA',
        obv: '#BA68C8',
        ichiTenkan: '#2962FF',
        ichiKijun: '#E040FB',
        ichiCloudUp: 'rgba(38, 166, 154, 0.2)',
        ichiCloudDown: 'rgba(239, 83, 80, 0.2)',
        ichiChikou: '#FFEB3B',
        paneBackground: '#131722',
        paneBorder: 'rgba(42, 46, 57, 0.8)',
        textColor: '#8b95a5',
        gridColor: 'rgba(42, 46, 57, 0.5)',
    };

    // ── Create an indicator sub-pane ────────────────────────────────────

    function _createPane(container, height, label) {
        const wrapper = document.createElement('div');
        wrapper.className = 'indicator-pane';
        wrapper.style.height = height + 'px';
        wrapper.style.width = '100%';
        wrapper.style.position = 'relative';
        wrapper.style.borderTop = `1px solid ${COLORS.paneBorder}`;
        container.appendChild(wrapper);

        // Label
        const labelEl = document.createElement('div');
        labelEl.className = 'indicator-pane-label';
        labelEl.textContent = label;
        labelEl.style.cssText = `position:absolute;top:4px;left:8px;z-index:5;
            font-size:10px;font-weight:600;color:${COLORS.textColor};
            text-transform:uppercase;letter-spacing:0.5px;pointer-events:none;`;
        wrapper.appendChild(labelEl);

        const chart = LightweightCharts.createChart(wrapper, {
            layout: {
                background: { type: 'solid', color: COLORS.paneBackground },
                textColor: COLORS.textColor,
                fontSize: 10,
            },
            grid: {
                vertLines: { color: COLORS.gridColor },
                horzLines: { color: COLORS.gridColor },
            },
            rightPriceScale: {
                borderColor: COLORS.gridColor,
                scaleMargins: { top: 0.12, bottom: 0.08 },
            },
            timeScale: { visible: false },
            handleScroll: false,
            handleScale: false,
            crosshair: {
                mode: LightweightCharts.CrosshairMode.Normal,
                vertLine: { visible: true, color: '#5c6578', width: 1, style: 2 },
                horzLine: { visible: true, color: '#5c6578', width: 1, style: 2 },
            },
        });

        return { chart, wrapper, label: labelEl };
    }

    // ── Render RSI Pane ─────────────────────────────────────────────────

    function renderRSI(containerId, chartData, mainChart) {
        const container = document.getElementById(containerId);
        if (!container || !chartData?.length) return null;

        const closes = chartData.map(d => d.close);
        const rsiValues = calcRSI(closes, 14);

        const pane = _createPane(container, 100, 'RSI (14)');

        // Overbought/oversold bands
        const overboughtLine = pane.chart.addLineSeries({
            color: COLORS.rsiOverbought,
            lineWidth: 1,
            lineStyle: LightweightCharts.LineStyle.Dashed,
            crosshairMarkerVisible: false,
            lastValueVisible: false,
            priceLineVisible: false,
        });
        const oversoldLine = pane.chart.addLineSeries({
            color: COLORS.rsiOversold,
            lineWidth: 1,
            lineStyle: LightweightCharts.LineStyle.Dashed,
            crosshairMarkerVisible: false,
            lastValueVisible: false,
            priceLineVisible: false,
        });

        // RSI line
        const rsiSeries = pane.chart.addLineSeries({
            color: COLORS.rsi,
            lineWidth: 2,
            crosshairMarkerVisible: true,
            lastValueVisible: true,
            priceLineVisible: false,
        });

        const timeData = chartData.map(d => _toTime(d.timestamp));

        const rsiLineData = rsiValues
            .map((v, i) => v != null ? { time: timeData[i], value: v } : null)
            .filter(Boolean);

        const obData = timeData.map(t => ({ time: t, value: 70 }));
        const osData = timeData.map(t => ({ time: t, value: 30 }));

        overboughtLine.setData(obData);
        oversoldLine.setData(osData);
        rsiSeries.setData(rsiLineData);

        // Fixed scale 0-100
        pane.chart.priceScale('right').applyOptions({
            autoScale: false,
            scaleMargins: { top: 0.05, bottom: 0.05 },
        });
        rsiSeries.applyOptions({ autoscaleInfoProvider: () => ({ priceRange: { minValue: 0, maxValue: 100 } }) });

        // Sync time scale with main chart
        _syncTimeScale(mainChart, pane.chart);

        return { pane, series: rsiSeries };
    }

    // ── Render MACD Pane ─────────────────────────────────────────────────

    function renderMACD(containerId, chartData, mainChart) {
        const container = document.getElementById(containerId);
        if (!container || !chartData?.length) return null;

        const closes = chartData.map(d => d.close);
        const { macd, signal, histogram } = calcMACD(closes, 12, 26, 9);

        const pane = _createPane(container, 120, 'MACD (12, 26, 9)');

        // Histogram
        const histSeries = pane.chart.addHistogramSeries({
            priceScaleId: '',
            priceFormat: { type: 'price', precision: 4, minMove: 0.0001 },
        });

        // MACD line
        const macdSeries = pane.chart.addLineSeries({
            color: COLORS.macdLine,
            lineWidth: 2,
            crosshairMarkerVisible: true,
            lastValueVisible: true,
            priceLineVisible: false,
        });

        // Signal line
        const signalSeries = pane.chart.addLineSeries({
            color: COLORS.macdSignal,
            lineWidth: 1,
            crosshairMarkerVisible: false,
            lastValueVisible: true,
            priceLineVisible: false,
        });

        const timeData = chartData.map(d => _toTime(d.timestamp));

        const histData = histogram
            .map((v, i) => v != null ? {
                time: timeData[i],
                value: v,
                color: v >= 0 ? COLORS.macdHistUp : COLORS.macdHistDown,
            } : null)
            .filter(Boolean);

        const macdData = macd
            .map((v, i) => v != null ? { time: timeData[i], value: v } : null)
            .filter(Boolean);

        const signalData = signal
            .map((v, i) => v != null ? { time: timeData[i], value: v } : null)
            .filter(Boolean);

        histSeries.setData(histData);
        macdSeries.setData(macdData);
        signalSeries.setData(signalData);

        _syncTimeScale(mainChart, pane.chart);

        return { pane, series: { macd: macdSeries, signal: signalSeries, histogram: histSeries } };
    }

    // ── Render Stochastic Pane ───────────────────────────────────────────

    function renderStochastic(containerId, chartData, mainChart) {
        const container = document.getElementById(containerId);
        if (!container || !chartData?.length) return null;

        const highs = chartData.map(d => d.high);
        const lows = chartData.map(d => d.low);
        const closes = chartData.map(d => d.close);
        const { k, d } = calcStochastic(highs, lows, closes, 14, 3);

        const pane = _createPane(container, 100, 'Stochastic (14, 3)');

        // Overbought/oversold
        const obLine = pane.chart.addLineSeries({
            color: COLORS.rsiOverbought, lineWidth: 1,
            lineStyle: LightweightCharts.LineStyle.Dashed,
            crosshairMarkerVisible: false, lastValueVisible: false, priceLineVisible: false,
        });
        const osLine = pane.chart.addLineSeries({
            color: COLORS.rsiOversold, lineWidth: 1,
            lineStyle: LightweightCharts.LineStyle.Dashed,
            crosshairMarkerVisible: false, lastValueVisible: false, priceLineVisible: false,
        });

        // %K and %D lines
        const kSeries = pane.chart.addLineSeries({
            color: COLORS.stochK, lineWidth: 2,
            crosshairMarkerVisible: true, lastValueVisible: true, priceLineVisible: false,
        });
        const dSeries = pane.chart.addLineSeries({
            color: COLORS.stochD, lineWidth: 1,
            crosshairMarkerVisible: false, lastValueVisible: true, priceLineVisible: false,
        });

        const timeData = chartData.map(d => _toTime(d.timestamp));

        obLine.setData(timeData.map(t => ({ time: t, value: 80 })));
        osLine.setData(timeData.map(t => ({ time: t, value: 20 })));
        kSeries.setData(k.map((v, i) => v != null ? { time: timeData[i], value: v } : null).filter(Boolean));
        dSeries.setData(d.map((v, i) => v != null ? { time: timeData[i], value: v } : null).filter(Boolean));

        kSeries.applyOptions({ autoscaleInfoProvider: () => ({ priceRange: { minValue: 0, maxValue: 100 } }) });

        _syncTimeScale(mainChart, pane.chart);

        return { pane, series: { k: kSeries, d: dSeries } };
    }

    // ── Add VWAP Overlay (on main chart, not sub-pane) ──────────────────

    function addVWAP(instance, chartData) {
        if (!instance || !chartData?.length) return null;

        const highs = chartData.map(d => d.high);
        const lows = chartData.map(d => d.low);
        const closes = chartData.map(d => d.close);
        const volumes = chartData.map(d => d.volume || 0);
        const vwapValues = calcVWAP(highs, lows, closes, volumes);

        const series = instance.chart.addLineSeries({
            color: COLORS.vwap,
            lineWidth: 2,
            lineStyle: LightweightCharts.LineStyle.Solid,
            crosshairMarkerVisible: true,
            lastValueVisible: true,
            priceLineVisible: false,
            title: 'VWAP',
        });

        const data = vwapValues
            .map((v, i) => v != null ? { time: _toTime(chartData[i].timestamp), value: v } : null)
            .filter(Boolean);

        series.setData(data);
        instance.overlays.vwap = series;
        return series;
    }

    // ── Render ATR Pane ─────────────────────────────────────────────────

    function renderATR(containerId, chartData, mainChart) {
        const container = document.getElementById(containerId);
        if (!container || !chartData?.length) return null;

        const highs = chartData.map(d => d.high);
        const lows = chartData.map(d => d.low);
        const closes = chartData.map(d => d.close);
        const atrValues = calcATR(highs, lows, closes, 14);

        const pane = _createPane(container, 90, 'ATR (14)');
        const series = pane.chart.addLineSeries({
            color: COLORS.atr, lineWidth: 2,
            crosshairMarkerVisible: true, lastValueVisible: true, priceLineVisible: false,
        });

        const timeData = chartData.map(d => _toTime(d.timestamp));
        series.setData(atrValues.map((v, i) => v != null ? { time: timeData[i], value: v } : null).filter(Boolean));

        _syncTimeScale(mainChart, pane.chart);
        return { pane, series };
    }

    // ── Render ADX Pane ─────────────────────────────────────────────────

    function renderADX(containerId, chartData, mainChart) {
        const container = document.getElementById(containerId);
        if (!container || !chartData?.length) return null;

        const highs = chartData.map(d => d.high);
        const lows = chartData.map(d => d.low);
        const closes = chartData.map(d => d.close);
        const { adx, plusDI, minusDI } = calcADX(highs, lows, closes, 14);

        const pane = _createPane(container, 110, 'ADX (14)  +DI  -DI');

        // 25 threshold reference line
        const threshold = pane.chart.addLineSeries({
            color: COLORS.adxThreshold, lineWidth: 1,
            lineStyle: LightweightCharts.LineStyle.Dashed,
            crosshairMarkerVisible: false, lastValueVisible: false, priceLineVisible: false,
        });
        const adxSeries = pane.chart.addLineSeries({
            color: COLORS.adx, lineWidth: 2,
            crosshairMarkerVisible: true, lastValueVisible: true, priceLineVisible: false,
        });
        const plusSeries = pane.chart.addLineSeries({
            color: COLORS.plusDI, lineWidth: 1,
            crosshairMarkerVisible: false, lastValueVisible: true, priceLineVisible: false,
        });
        const minusSeries = pane.chart.addLineSeries({
            color: COLORS.minusDI, lineWidth: 1,
            crosshairMarkerVisible: false, lastValueVisible: true, priceLineVisible: false,
        });

        const timeData = chartData.map(d => _toTime(d.timestamp));
        threshold.setData(timeData.map(t => ({ time: t, value: 25 })));
        adxSeries.setData(adx.map((v, i) => v != null ? { time: timeData[i], value: v } : null).filter(Boolean));
        plusSeries.setData(plusDI.map((v, i) => v != null ? { time: timeData[i], value: v } : null).filter(Boolean));
        minusSeries.setData(minusDI.map((v, i) => v != null ? { time: timeData[i], value: v } : null).filter(Boolean));

        adxSeries.applyOptions({ autoscaleInfoProvider: () => ({ priceRange: { minValue: 0, maxValue: 100 } }) });

        _syncTimeScale(mainChart, pane.chart);
        return { pane, series: { adx: adxSeries, plusDI: plusSeries, minusDI: minusSeries } };
    }

    // ── Render OBV Pane ─────────────────────────────────────────────────

    function renderOBV(containerId, chartData, mainChart) {
        const container = document.getElementById(containerId);
        if (!container || !chartData?.length) return null;

        const closes = chartData.map(d => d.close);
        const volumes = chartData.map(d => d.volume || 0);
        const obv = calcOBV(closes, volumes);

        const pane = _createPane(container, 90, 'OBV');
        const series = pane.chart.addLineSeries({
            color: COLORS.obv, lineWidth: 2,
            crosshairMarkerVisible: true, lastValueVisible: true, priceLineVisible: false,
        });

        const timeData = chartData.map(d => _toTime(d.timestamp));
        series.setData(obv.map((v, i) => ({ time: timeData[i], value: v })));

        _syncTimeScale(mainChart, pane.chart);
        return { pane, series };
    }

    // ── Add Supertrend Overlay ──────────────────────────────────────────
    // Main-chart overlay. Uses color changes to signal trend flips.
    // Because lightweight-charts line series can't change color mid-series
    // cleanly, we split into two series (up and down) and null out the other.
    function addSupertrend(instance, chartData) {
        if (!instance || !chartData?.length) return null;

        const highs = chartData.map(d => d.high);
        const lows = chartData.map(d => d.low);
        const closes = chartData.map(d => d.close);
        const { value, direction } = calcSupertrend(highs, lows, closes, 10, 3);

        const upSeries = instance.chart.addLineSeries({
            color: COLORS.supertrendUp, lineWidth: 2,
            lineStyle: LightweightCharts.LineStyle.Solid,
            crosshairMarkerVisible: true, lastValueVisible: true, priceLineVisible: false,
            title: 'Supertrend ↑',
        });
        const downSeries = instance.chart.addLineSeries({
            color: COLORS.supertrendDown, lineWidth: 2,
            lineStyle: LightweightCharts.LineStyle.Solid,
            crosshairMarkerVisible: true, lastValueVisible: true, priceLineVisible: false,
            title: 'Supertrend ↓',
        });

        const times = chartData.map(d => _toTime(d.timestamp));
        const upData = [];
        const downData = [];
        for (let i = 0; i < value.length; i++) {
            if (value[i] == null) continue;
            if (direction[i] === 1) upData.push({ time: times[i], value: value[i] });
            else downData.push({ time: times[i], value: value[i] });
        }
        upSeries.setData(upData);
        downSeries.setData(downData);

        instance.overlays.supertrendUp = upSeries;
        instance.overlays.supertrendDown = downSeries;
        return { up: upSeries, down: downSeries };
    }

    function removeSupertrend(instance) {
        if (!instance) return;
        ['supertrendUp', 'supertrendDown'].forEach(k => {
            if (instance.overlays[k]) {
                try { instance.chart.removeSeries(instance.overlays[k]); } catch (e) {}
                delete instance.overlays[k];
            }
        });
    }

    // ── Add Keltner Channels Overlay ────────────────────────────────────

    function addKeltner(instance, chartData) {
        if (!instance || !chartData?.length) return null;

        const highs = chartData.map(d => d.high);
        const lows = chartData.map(d => d.low);
        const closes = chartData.map(d => d.close);
        const { upper, mid, lower } = calcKeltner(highs, lows, closes, 20, 10, 2);

        const commonOpts = {
            lineWidth: 1,
            crosshairMarkerVisible: false,
            lastValueVisible: false,
            priceLineVisible: false,
        };

        const upperSeries = instance.chart.addLineSeries({ ...commonOpts, color: COLORS.keltnerUpper, title: 'KC Upper' });
        const midSeries = instance.chart.addLineSeries({ ...commonOpts, color: COLORS.keltnerMid, lineStyle: LightweightCharts.LineStyle.Dotted, title: 'KC Mid' });
        const lowerSeries = instance.chart.addLineSeries({ ...commonOpts, color: COLORS.keltnerLower, title: 'KC Lower' });

        const times = chartData.map(d => _toTime(d.timestamp));
        upperSeries.setData(upper.map((v, i) => v != null ? { time: times[i], value: v } : null).filter(Boolean));
        midSeries.setData(mid.map((v, i) => v != null ? { time: times[i], value: v } : null).filter(Boolean));
        lowerSeries.setData(lower.map((v, i) => v != null ? { time: times[i], value: v } : null).filter(Boolean));

        instance.overlays.keltnerUpper = upperSeries;
        instance.overlays.keltnerMid = midSeries;
        instance.overlays.keltnerLower = lowerSeries;
        return { upper: upperSeries, mid: midSeries, lower: lowerSeries };
    }

    function removeKeltner(instance) {
        if (!instance) return;
        ['keltnerUpper', 'keltnerMid', 'keltnerLower'].forEach(k => {
            if (instance.overlays[k]) {
                try { instance.chart.removeSeries(instance.overlays[k]); } catch (e) {}
                delete instance.overlays[k];
            }
        });
    }

    // ── Add Ichimoku Cloud Overlay ──────────────────────────────────────
    // Senkou A/B are rendered on the current bar (not projected forward) so the
    // cloud covers the historical range. Area series fill between two lines is
    // emulated by drawing senkouA and senkouB as separate line series and
    // relying on the user's eye — proper cloud fill would need a custom series.
    function addIchimoku(instance, chartData) {
        if (!instance || !chartData?.length) return null;

        const highs = chartData.map(d => d.high);
        const lows = chartData.map(d => d.low);
        const closes = chartData.map(d => d.close);
        const { tenkan, kijun, senkouA, senkouB, chikou } = calcIchimoku(highs, lows, closes, 9, 26, 52);

        const mkLine = (color, title, extra = {}) => instance.chart.addLineSeries({
            color, lineWidth: 1,
            crosshairMarkerVisible: false, lastValueVisible: false, priceLineVisible: false,
            title, ...extra,
        });

        const tenkanSeries = mkLine(COLORS.ichiTenkan, 'Tenkan');
        const kijunSeries = mkLine(COLORS.ichiKijun, 'Kijun');
        // Senkou A/B rendered as thin lines. Cloud fill would need Area series
        // with baseline support; lightweight-charts v4 has no 2-line band fill,
        // so we draw the boundaries and let color do the work.
        const senkouASeries = mkLine(COLORS.supertrendUp, 'Senkou A');
        const senkouBSeries = mkLine(COLORS.supertrendDown, 'Senkou B');
        const chikouSeries = mkLine(COLORS.ichiChikou, 'Chikou', { lineStyle: LightweightCharts.LineStyle.Dashed });

        const times = chartData.map(d => _toTime(d.timestamp));
        const toSeriesData = arr => arr.map((v, i) => v != null ? { time: times[i], value: v } : null).filter(Boolean);

        tenkanSeries.setData(toSeriesData(tenkan));
        kijunSeries.setData(toSeriesData(kijun));
        senkouASeries.setData(toSeriesData(senkouA));
        senkouBSeries.setData(toSeriesData(senkouB));
        chikouSeries.setData(toSeriesData(chikou));

        instance.overlays.ichiTenkan = tenkanSeries;
        instance.overlays.ichiKijun = kijunSeries;
        instance.overlays.ichiSenkouA = senkouASeries;
        instance.overlays.ichiSenkouB = senkouBSeries;
        instance.overlays.ichiChikou = chikouSeries;
        return { tenkanSeries, kijunSeries, senkouASeries, senkouBSeries, chikouSeries };
    }

    function removeIchimoku(instance) {
        if (!instance) return;
        ['ichiTenkan', 'ichiKijun', 'ichiSenkouA', 'ichiSenkouB', 'ichiChikou'].forEach(k => {
            if (instance.overlays[k]) {
                try { instance.chart.removeSeries(instance.overlays[k]); } catch (e) {}
                delete instance.overlays[k];
            }
        });
    }

    // ── Time scale sync ─────────────────────────────────────────────────

    function _syncTimeScale(mainChart, paneChart) {
        mainChart.timeScale().subscribeVisibleLogicalRangeChange(range => {
            if (range) {
                try { paneChart.timeScale().setVisibleLogicalRange(range); } catch (e) {}
            }
        });
    }

    // ── Time conversion (mirrors AlphaCharts._toTime) ───────────────────

    function _toTime(timestamp) {
        if (typeof timestamp === 'string') {
            const datePart = timestamp.substring(0, 10);
            const parts = datePart.split('-');
            if (parts.length === 3 && parts[0].length === 4) {
                const y = parseInt(parts[0]);
                const m = parseInt(parts[1]);
                const d = parseInt(parts[2]);
                const timePart = timestamp.substring(11, 19);
                if (!timePart || timePart === '00:00:00' || timePart === '') {
                    return { year: y, month: m, day: d };
                }
                return Math.floor(new Date(timestamp).getTime() / 1000);
            }
        }
        if (typeof timestamp === 'number') return timestamp;
        return Math.floor(new Date(timestamp).getTime() / 1000);
    }

    // ── Resize all indicator panes ──────────────────────────────────────

    function resizePanes(containerId) {
        const container = document.getElementById(containerId);
        if (!container) return;
        const panes = container.querySelectorAll('.indicator-pane');
        panes.forEach(pane => {
            const charts = pane.querySelectorAll('canvas');
            // Lightweight Charts handles internal resize via container width
        });
    }

    // ── Destroy indicator panes ─────────────────────────────────────────

    function destroyPanes(containerId) {
        const container = document.getElementById(containerId);
        if (!container) return;
        const panes = container.querySelectorAll('.indicator-pane');
        panes.forEach(pane => pane.remove());
    }

    return {
        calcRSI, calcMACD, calcStochastic, calcVWAP,
        calcATR, calcSupertrend, calcKeltner, calcADX, calcOBV, calcIchimoku,
        renderRSI, renderMACD, renderStochastic, addVWAP,
        renderATR, renderADX, renderOBV,
        addSupertrend, removeSupertrend,
        addKeltner, removeKeltner,
        addIchimoku, removeIchimoku,
        destroyPanes, resizePanes,
    };
})();

window.ChartIndicators = ChartIndicators;
