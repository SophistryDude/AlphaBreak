// ============================================================================
// AlphaBreak Chart Presets + Saved Layouts
// ============================================================================
// Two cooperating modules:
//
//   ChartPresets   — one-click curated indicator stacks. The four presets are
//                    intentionally non-generic: each combines standard
//                    indicators with at least one AlphaBreak-proprietary
//                    signal (auto-trendlines, regime, dark-pool panel, etc.)
//                    so the bundle can't be replicated on TradingView/TOS.
//
//   ChartLayouts   — auto-saves the chart toolbar checkbox state per ticker
//                    to localStorage and restores it on the next visit. No
//                    explicit "save" action needed; the layout follows the
//                    user around.
//
// Both are wired against the existing toolbar checkbox IDs so they're
// completely independent of the underlying chart implementation.
// ============================================================================

const ChartPresets = (() => {

    // The exhaustive list of toggleable chart features. Adding a new toggle?
    // Add it here and the preset reset/save/restore logic picks it up
    // automatically.
    const ALL_TOGGLES = [
        'toggleTrendlines',
        'toggleSMA',
        'toggleBB',
        'toggleVWAP',
        'toggleCompare',
        'togglePatterns',
        'toggleRSI',
        'toggleMACD',
        'toggleStoch',
        'toggleATR',
        'toggleADX',
        'toggleOBV',
        'toggleSupertrend',
        'toggleKeltner',
        'toggleIchimoku',
        'toggleVPVR',
        'toggleSqueeze',
    ];

    // Each preset declares which toggles should end up CHECKED. Anything not
    // in the list is unchecked. Use the `notes` field for the tooltip the
    // dropdown shows on hover — keep it short, this is the user's elevator
    // pitch for why they'd pick this stack.
    const PRESETS = {
        trendBreak: {
            label: 'Trend Break Stack',
            tagline: 'Auto-trendlines + Supertrend + ADX + ATR',
            notes: 'AlphaBreak\'s auto-detected trendlines + trend-following confirmation. Best for breakout entries.',
            toggles: ['toggleTrendlines', 'toggleSupertrend', 'toggleADX', 'toggleATR'],
        },
        volumeFlow: {
            label: 'Volume Flow Stack',
            tagline: 'VPVR + OBV + VWAP',
            notes: 'Volume-by-price + on-balance volume + VWAP. Pairs with the dark pool panel below the chart.',
            toggles: ['toggleVPVR', 'toggleOBV', 'toggleVWAP'],
        },
        regimeAware: {
            label: 'Regime-Aware Stack',
            tagline: 'Trendlines (regime badge) + RSI + MACD + BB',
            notes: 'Lets the regime badge tell you which momentum signals to trust. Best for swing trading.',
            toggles: ['toggleTrendlines', 'toggleRSI', 'toggleMACD', 'toggleBB'],
        },
        aiConfluence: {
            label: 'AI Confluence Stack',
            tagline: 'Trendlines + Supertrend + Ichimoku + Squeeze Momentum',
            notes: 'Stacks the trendline AI score on top of three independent trend signals. High-conviction setups only.',
            toggles: ['toggleTrendlines', 'toggleSupertrend', 'toggleIchimoku', 'toggleSqueeze'],
        },
    };

    // Apply a preset by name. Resets every known toggle then enables only
    // the ones in the preset's list. Each toggled checkbox dispatches a
    // 'change' event so the existing analyze.js handlers fire and rerender
    // the chart — we don't poke at the chart instance directly.
    function apply(name) {
        const preset = PRESETS[name];
        if (!preset) return;

        for (const id of ALL_TOGGLES) {
            const el = document.getElementById(id);
            if (!el) continue;
            const shouldBeOn = preset.toggles.includes(id);
            if (el.checked !== shouldBeOn) {
                el.checked = shouldBeOn;
                el.dispatchEvent(new Event('change', { bubbles: true }));
            }
        }
    }

    function list() {
        return Object.entries(PRESETS).map(([key, p]) => ({ key, ...p }));
    }

    // Render the preset dropdown into a host element. Returns the menu node
    // so the caller can position it. Closes on outside click.
    function attachDropdown(triggerBtn) {
        if (!triggerBtn) return null;

        let menu = null;
        const close = () => {
            menu?.remove();
            menu = null;
            document.removeEventListener('click', onOutside, true);
        };
        const onOutside = (e) => {
            if (!menu?.contains(e.target) && e.target !== triggerBtn && !triggerBtn.contains(e.target)) close();
        };

        triggerBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            if (menu) { close(); return; }

            menu = document.createElement('div');
            menu.className = 'chart-preset-menu';
            menu.innerHTML = list().map(p => `
                <button class="chart-preset-item" data-preset="${p.key}" title="${p.notes}">
                    <div class="chart-preset-item-label">${p.label}</div>
                    <div class="chart-preset-item-tagline">${p.tagline}</div>
                </button>
            `).join('');

            menu.addEventListener('click', (ev) => {
                const item = ev.target.closest('.chart-preset-item');
                if (!item) return;
                apply(item.dataset.preset);
                close();
            });

            // Position below the trigger button
            const rect = triggerBtn.getBoundingClientRect();
            menu.style.position = 'absolute';
            menu.style.top = (rect.bottom + window.scrollY + 4) + 'px';
            menu.style.left = (rect.left + window.scrollX) + 'px';
            menu.style.zIndex = '1000';

            document.body.appendChild(menu);
            // Defer outside-click binding so the click that opened the menu
            // doesn't immediately close it.
            setTimeout(() => document.addEventListener('click', onOutside, true), 0);
        });
    }

    return { apply, list, attachDropdown, PRESETS, ALL_TOGGLES };
})();

window.ChartPresets = ChartPresets;


// ============================================================================
// ChartLayouts — per-ticker auto-persisted toolbar state
// ============================================================================
// Strategy: snapshot every known toggle plus the active period/interval into
// localStorage under `chartLayout_<TICKER>`. Restore on ticker change. Save
// fires on every toggle change with a 200ms debounce so we don't thrash
// localStorage during preset application (which fires 17 events back-to-back).

const ChartLayouts = (() => {

    const STORAGE_PREFIX = 'chartLayout_';
    let currentTicker = null;
    let saveTimer = null;
    let initialized = false;

    function _snapshot() {
        const state = { toggles: {}, savedAt: Date.now() };
        for (const id of ChartPresets.ALL_TOGGLES) {
            const el = document.getElementById(id);
            if (el) state.toggles[id] = el.checked;
        }
        // Active period/interval — pulled from the .active button if present
        const periodBtn = document.querySelector('#analyzeChartPeriods button.active');
        if (periodBtn) {
            state.period = periodBtn.dataset.period;
            state.interval = periodBtn.dataset.interval;
        }
        return state;
    }

    function _save() {
        if (!currentTicker) return;
        try {
            localStorage.setItem(STORAGE_PREFIX + currentTicker, JSON.stringify(_snapshot()));
        } catch (e) { /* quota or disabled — silent */ }
    }

    function _scheduleSave() {
        if (saveTimer) clearTimeout(saveTimer);
        saveTimer = setTimeout(_save, 200);
    }

    function _load(ticker) {
        try {
            const raw = localStorage.getItem(STORAGE_PREFIX + ticker);
            return raw ? JSON.parse(raw) : null;
        } catch (e) { return null; }
    }

    // Restore the saved layout for `ticker`. Returns true if a layout was
    // applied so the caller can skip its default loadout.
    function restore(ticker) {
        const layout = _load(ticker);
        if (!layout?.toggles) return false;

        for (const [id, want] of Object.entries(layout.toggles)) {
            const el = document.getElementById(id);
            if (!el) continue;
            if (el.checked !== want) {
                el.checked = want;
                el.dispatchEvent(new Event('change', { bubbles: true }));
            }
        }
        return true;
    }

    // Bind the auto-save listener once. Subsequent calls are no-ops.
    function init() {
        if (initialized) return;
        initialized = true;
        for (const id of ChartPresets.ALL_TOGGLES) {
            const el = document.getElementById(id);
            if (el) el.addEventListener('change', _scheduleSave);
        }
    }

    function setTicker(ticker) {
        currentTicker = ticker;
    }

    function clear(ticker) {
        try { localStorage.removeItem(STORAGE_PREFIX + (ticker || currentTicker)); } catch (e) {}
    }

    return { init, restore, setTicker, clear };
})();

window.ChartLayouts = ChartLayouts;


// ============================================================================
// ChartTooltips — rich hover tooltips for chart-toolbar indicators
// ============================================================================
// Hovering any chart-toggle label shows a floating card with the indicator's
// definition and a one-line "when to use" hint. This is the discoverability
// story for beginners — the toolbar now has 17 indicators and nobody's going
// to remember what ADX or Ichimoku do without a nudge.
//
// The descriptions intentionally stay short (two lines each) so the tooltip
// is scannable. Deeper explanations live in the blog — we can add a "Learn
// more" link later that deep-links into the education content.

const ChartTooltips = (() => {

    const DESCRIPTIONS = {
        toggleTrendlines: {
            title: 'Auto-Detected Trendlines',
            what: 'AlphaBreak\'s proprietary algorithm detects support and resistance lines with confidence scoring.',
            when: 'Always on — the regime badge and AI score popover depend on these.',
        },
        toggleSMA: {
            title: 'Simple Moving Average (SMA)',
            what: 'Average closing price over the last N bars. Smooths price action to reveal trend direction.',
            when: 'Trend-following. Price above SMA = uptrend, below = downtrend.',
        },
        toggleBB: {
            title: 'Bollinger Bands (20, 2)',
            what: '20-SMA with ±2 standard deviations. Bands expand in volatility, contract in consolidation.',
            when: 'Mean reversion (touches of outer band) or volatility-breakout setups.',
        },
        toggleVWAP: {
            title: 'Volume-Weighted Average Price',
            what: 'Average price weighted by volume for the session. Where the "smart money" average trade sits.',
            when: 'Day trading. Price above VWAP = bullish bias, below = bearish.',
        },
        toggleCompare: {
            title: 'Symbol Comparison',
            what: 'Overlay SPY and VIX normalized to the same starting point as this ticker.',
            when: 'Checking relative strength vs. the market and volatility regime.',
        },
        togglePatterns: {
            title: 'Candlestick Patterns',
            what: 'Automatic detection of doji, engulfing, hammer, shooting star, and other reversal patterns.',
            when: 'Short-term reversal entries at support/resistance.',
        },
        toggleRSI: {
            title: 'Relative Strength Index (14)',
            what: '0–100 momentum oscillator. Above 70 = overbought, below 30 = oversold.',
            when: 'Classic overbought/oversold signals in ranging markets.',
        },
        toggleMACD: {
            title: 'MACD (12, 26, 9)',
            what: 'Difference between 12- and 26-EMA, with a 9-EMA signal line. Histogram shows momentum.',
            when: 'Trend-following. Signal-line crossover = entry, histogram flip = warning.',
        },
        toggleStoch: {
            title: 'Stochastic (14, 3)',
            what: 'Compares close to the high/low range. Faster than RSI. Above 80 = overbought, below 20 = oversold.',
            when: 'Range-bound markets. Watch for %K crossing %D for entries.',
        },
        toggleATR: {
            title: 'Average True Range (14)',
            what: 'Wilder\'s measure of volatility in the same units as price.',
            when: 'Sizing stops and position size. Higher ATR = wider stops needed.',
        },
        toggleADX: {
            title: 'ADX + Directional Index (14)',
            what: 'ADX measures trend strength (0–100). +DI vs -DI shows direction.',
            when: 'Above 25 = strong trend (trend-follow). Below 20 = chop (mean-revert).',
        },
        toggleOBV: {
            title: 'On-Balance Volume',
            what: 'Running sum of volume, positive on up days and negative on down days.',
            when: 'Volume confirmation. OBV divergence from price often precedes reversals.',
        },
        toggleSupertrend: {
            title: 'Supertrend (10, 3)',
            what: 'ATR-based trend-following line. Flips from green (up) to red (down) on trend changes.',
            when: 'Clear trend entries and stop placement. Ride the line.',
        },
        toggleKeltner: {
            title: 'Keltner Channels (20, 10, 2)',
            what: 'EMA with ATR-based bands. Similar to Bollinger Bands but uses range instead of stdev.',
            when: 'Volatility breakout entries. Inside Keltner + outside Bollinger = squeeze setup.',
        },
        toggleIchimoku: {
            title: 'Ichimoku Cloud (9, 26, 52)',
            what: 'Tenkan, Kijun, Senkou A/B cloud, and Chikou lag line — a full trading system in one indicator.',
            when: 'Price above the cloud = bullish, below = bearish, inside = no-trade zone.',
        },
        toggleVPVR: {
            title: 'Volume Profile (VPVR)',
            what: 'Horizontal volume histogram showing where the most shares traded. POC = highest-volume price.',
            when: 'Identifying real support/resistance and the Value Area for day trading.',
        },
        toggleSqueeze: {
            title: 'Squeeze Momentum (LazyBear)',
            what: 'Bollinger Bands inside Keltner = squeeze on (low vol). Histogram shows breakout momentum.',
            when: 'Waiting for volatility-compression breakouts. Fires when the squeeze releases.',
        },
    };

    let tooltipEl = null;
    let hoverTimer = null;

    function _ensureEl() {
        if (tooltipEl) return tooltipEl;
        tooltipEl = document.createElement('div');
        tooltipEl.className = 'chart-tooltip-card';
        tooltipEl.style.display = 'none';
        document.body.appendChild(tooltipEl);
        return tooltipEl;
    }

    function _show(labelEl, desc) {
        const el = _ensureEl();
        el.innerHTML = `
            <div class="chart-tooltip-title">${desc.title}</div>
            <div class="chart-tooltip-what">${desc.what}</div>
            <div class="chart-tooltip-when"><strong>When:</strong> ${desc.when}</div>
        `;
        el.style.display = 'block';

        // Position below the label, clamped to viewport.
        const rect = labelEl.getBoundingClientRect();
        const elRect = el.getBoundingClientRect();
        const pad = 8;
        let left = rect.left + window.scrollX;
        if (left + elRect.width + pad > window.innerWidth) {
            left = window.innerWidth - elRect.width - pad;
        }
        el.style.left = Math.max(pad, left) + 'px';
        el.style.top = (rect.bottom + window.scrollY + 6) + 'px';
    }

    function _hide() {
        if (tooltipEl) tooltipEl.style.display = 'none';
    }

    function init() {
        // Attach to every label that wraps a known toggle.
        for (const toggleId of Object.keys(DESCRIPTIONS)) {
            const input = document.getElementById(toggleId);
            if (!input) continue;
            const label = input.closest('label.chart-toggle');
            if (!label) continue;
            // Suppress the native title tooltip so it doesn't overlap ours.
            if (label.title) label.dataset.titleOrig = label.title;
            label.title = '';

            label.addEventListener('mouseenter', () => {
                if (hoverTimer) clearTimeout(hoverTimer);
                hoverTimer = setTimeout(() => _show(label, DESCRIPTIONS[toggleId]), 350);
            });
            label.addEventListener('mouseleave', () => {
                if (hoverTimer) clearTimeout(hoverTimer);
                _hide();
            });
        }
    }

    return { init, DESCRIPTIONS };
})();

window.ChartTooltips = ChartTooltips;
