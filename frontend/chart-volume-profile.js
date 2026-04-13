// ============================================================================
// AlphaBreak Volume Profile (VPVR) — canvas overlay on the main price chart
// ============================================================================
// Renders a horizontal volume-by-price histogram on the right edge of the
// chart. Standard fixed-range profile: bins prices into N buckets across the
// full data range, sums volume per bucket, highlights the Point of Control
// and ~70% Value Area band.
//
// Built as a separate canvas overlay because lightweight-charts v4 has no
// native horizontal histogram series. The overlay reads the candlestick
// series' priceToCoordinate() so bars stay aligned when the chart is panned
// or resized.

const ChartVolumeProfile = (() => {

    const DEFAULTS = {
        bins: 30,
        widthPx: 110,         // how far bars extend from right edge
        valueAreaPct: 0.70,
        barColor: 'rgba(100, 181, 246, 0.55)',
        valueAreaColor: 'rgba(100, 181, 246, 0.85)',
        pocColor: 'rgba(255, 235, 59, 0.95)',
        textColor: '#cfd8dc',
    };

    function _computeProfile(chartData, bins) {
        let min = Infinity, max = -Infinity;
        for (const d of chartData) {
            if (d.low < min) min = d.low;
            if (d.high > max) max = d.high;
        }
        if (!isFinite(min) || !isFinite(max) || max === min) {
            return { profile: [], min, max, step: 0, pocIdx: 0, vaLow: 0, vaHigh: 0 };
        }

        const step = (max - min) / bins;
        const profile = new Array(bins).fill(0);

        // Distribute each candle's volume across the bins it touches.
        for (const d of chartData) {
            const vol = d.volume || 0;
            if (vol <= 0) continue;
            const lo = Math.max(0, Math.floor((d.low - min) / step));
            const hi = Math.min(bins - 1, Math.floor((d.high - min) / step));
            const span = hi - lo + 1;
            const perBin = vol / span;
            for (let i = lo; i <= hi; i++) profile[i] += perBin;
        }

        // Point of Control: bin with highest volume.
        let pocIdx = 0;
        for (let i = 1; i < bins; i++) if (profile[i] > profile[pocIdx]) pocIdx = i;

        // Value Area: expand from POC outward until ~70% of total volume.
        const total = profile.reduce((s, v) => s + v, 0);
        const target = total * DEFAULTS.valueAreaPct;
        let lo = pocIdx, hi = pocIdx, acc = profile[pocIdx];
        while (acc < target && (lo > 0 || hi < bins - 1)) {
            const downNext = lo > 0 ? profile[lo - 1] : -1;
            const upNext = hi < bins - 1 ? profile[hi + 1] : -1;
            if (upNext >= downNext) { hi++; acc += upNext; }
            else { lo--; acc += downNext; }
        }

        return { profile, min, max, step, pocIdx, vaLow: lo, vaHigh: hi };
    }

    function attach(instance, chartData, options = {}) {
        if (!instance || !chartData?.length || !instance.container) return null;

        const opts = { ...DEFAULTS, ...options };
        const wrapper = instance.container;

        // Wrapper must be position:relative so the overlay can sit on top.
        const cs = getComputedStyle(wrapper);
        if (cs.position === 'static') wrapper.style.position = 'relative';

        const canvas = document.createElement('canvas');
        canvas.className = 'vpvr-overlay';
        canvas.style.cssText = `
            position: absolute;
            top: 0;
            right: 60px;
            pointer-events: none;
            z-index: 3;
        `;
        wrapper.appendChild(canvas);

        const data = _computeProfile(chartData, opts.bins);

        const draw = () => {
            const wrapperRect = wrapper.getBoundingClientRect();
            // Match canvas to wrapper height; width is fixed.
            const dpr = window.devicePixelRatio || 1;
            const cssW = opts.widthPx;
            const cssH = wrapperRect.height;
            canvas.style.width = cssW + 'px';
            canvas.style.height = cssH + 'px';
            canvas.width = Math.floor(cssW * dpr);
            canvas.height = Math.floor(cssH * dpr);

            const ctx = canvas.getContext('2d');
            ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
            ctx.clearRect(0, 0, cssW, cssH);

            if (!data.profile.length || data.step === 0) return;

            const maxVol = Math.max(...data.profile);
            if (maxVol <= 0) return;

            // For each bin, project its midpoint price to a y-coordinate via
            // the candlestick series, then draw a horizontal bar.
            const binPxHeight = Math.max(2, Math.floor(cssH / data.profile.length) - 1);

            for (let i = 0; i < data.profile.length; i++) {
                const vol = data.profile[i];
                if (vol <= 0) continue;
                const midPrice = data.min + (i + 0.5) * data.step;
                const y = instance.candleSeries.priceToCoordinate(midPrice);
                if (y == null) continue;

                const barW = Math.max(1, (vol / maxVol) * cssW);
                const inValueArea = i >= data.vaLow && i <= data.vaHigh;
                const isPoc = i === data.pocIdx;

                ctx.fillStyle = isPoc ? opts.pocColor
                              : inValueArea ? opts.valueAreaColor
                              : opts.barColor;
                ctx.fillRect(cssW - barW, y - binPxHeight / 2, barW, binPxHeight);
            }

            // POC label
            const pocPrice = data.min + (data.pocIdx + 0.5) * data.step;
            const pocY = instance.candleSeries.priceToCoordinate(pocPrice);
            if (pocY != null) {
                ctx.fillStyle = opts.textColor;
                ctx.font = '10px -apple-system, "Segoe UI", Roboto, sans-serif';
                ctx.textBaseline = 'middle';
                ctx.fillText('POC', 4, pocY);
            }
        };

        draw();

        // Re-draw on visible-range changes (panning) and resize. We don't need
        // to recompute the profile — only the y-mapping changes.
        const unsubscribe = instance.chart.timeScale()
            .subscribeVisibleLogicalRangeChange(draw);

        const resizeObserver = new ResizeObserver(draw);
        resizeObserver.observe(wrapper);

        return {
            canvas,
            draw,
            destroy() {
                try { instance.chart.timeScale().unsubscribeVisibleLogicalRangeChange(draw); } catch (e) {}
                try { resizeObserver.disconnect(); } catch (e) {}
                canvas.remove();
            },
        };
    }

    return { attach };
})();

window.ChartVolumeProfile = ChartVolumeProfile;
