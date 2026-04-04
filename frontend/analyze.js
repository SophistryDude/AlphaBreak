// AlphaBreak — Analyze Tab
// Single-ticker deep-dive analysis

const Analyze = (() => {
    let currentTicker = null;
    let data = null;
    let searchTimeout = null;
    let currentChartPeriod = '6mo';
    let currentChartInterval = '1d';

    // ── Init ─────────────────────────────────────────────────────────────
    function init() {
        const input = document.getElementById('analyzeTickerInput');
        const btn = document.getElementById('analyzeSearchBtn');
        const periods = document.getElementById('analyzeChartPeriods');

        if (!input) return;

        // Search on enter or button click
        input.addEventListener('keydown', e => {
            if (e.key === 'Enter') {
                e.preventDefault();
                analyzeCurrent();
            }
        });
        btn.addEventListener('click', analyzeCurrent);

        // Auto-uppercase
        input.addEventListener('input', () => {
            input.value = input.value.toUpperCase();
            handleAutocomplete(input.value);
        });

        // Close autocomplete on click outside
        document.addEventListener('click', e => {
            if (!e.target.closest('.analyze-search-container')) {
                document.getElementById('analyzeAutocomplete').innerHTML = '';
            }
        });

        // Chart period buttons
        if (periods) {
            periods.addEventListener('click', e => {
                const btn = e.target.closest('button');
                if (!btn || !currentTicker) return;
                periods.querySelectorAll('button').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                loadChart(currentTicker, btn.dataset.period, btn.dataset.interval);
            });
        }

        // Toggle checkboxes for overlays — reload chart on toggle
        ['toggleTrendlines', 'toggleSMA', 'toggleBB', 'togglePatterns'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.addEventListener('change', () => {
                if (currentTicker) loadChart(currentTicker, currentChartPeriod, currentChartInterval);
            });
        });

        // Compare toggle — loads/clears comparison data
        const compareToggle = document.getElementById('toggleCompare');
        if (compareToggle) {
            compareToggle.addEventListener('change', () => {
                if (!currentTicker) return;
                if (compareToggle.checked) {
                    loadCompare(currentTicker, currentChartPeriod);
                } else {
                    AlphaCharts.clearCompare('analyzeChartContainer');
                }
            });
        }

        // Fullscreen button
        const fsBtn = document.getElementById('chartFullscreenBtn');
        if (fsBtn) fsBtn.addEventListener('click', () => AlphaCharts.toggleFullscreen('analyzeChartContainer'));

        // Check URL hash for direct ticker link, or auto-load top trend break
        const hash = window.location.hash;
        if (hash.startsWith('#analyze/')) {
            const ticker = hash.replace('#analyze/', '').toUpperCase();
            if (ticker) {
                input.value = ticker;
                analyzeTicker(ticker);
            }
        } else {
            // Auto-analyze the top trend break ticker
            loadTopTrendBreak();
        }
    }

    async function loadTopTrendBreak() {
        // Check all frequencies in parallel for speed
        const frequencies = ['daily', 'hourly', '10min'];
        try {
            const results = await Promise.all(
                frequencies.map(f =>
                    apiRequest(`/api/reports/latest?frequency=${f}`)
                        .then(r => r.json())
                        .catch(() => null)
                )
            );
            for (const data of results) {
                const report = data?.report;
                if (report && report.length > 0) {
                    const topTicker = report[0].ticker;
                    document.getElementById('analyzeTickerInput').value = topTicker;
                    analyzeTicker(topTicker);
                    return;
                }
            }
        } catch (e) { /* fall through */ }
        // Fallback: analyze a well-known ticker
        document.getElementById('analyzeTickerInput').value = 'AAPL';
        analyzeTicker('AAPL');
    }

    function analyzeCurrent() {
        const input = document.getElementById('analyzeTickerInput');
        const ticker = input.value.trim().toUpperCase();
        document.getElementById('analyzeAutocomplete').innerHTML = '';
        if (ticker) analyzeTicker(ticker);
    }

    // ── Autocomplete ─────────────────────────────────────────────────────
    function handleAutocomplete(query) {
        clearTimeout(searchTimeout);
        const container = document.getElementById('analyzeAutocomplete');
        if (query.length < 1) {
            container.innerHTML = '';
            return;
        }
        searchTimeout = setTimeout(async () => {
            try {
                const resp = await apiRequest(`/api/analyze/search?q=${encodeURIComponent(query)}`);
                const results = await resp.json();
                if (!results || !results.length) {
                    container.innerHTML = '';
                    return;
                }
                container.innerHTML = results.map(r => `
                    <div class="analyze-autocomplete-item" data-ticker="${r.ticker}">
                        <span class="ac-ticker">${r.ticker}</span>
                        <span class="ac-name">${r.name}</span>
                        <span class="ac-sector">${r.sector || ''}</span>
                    </div>
                `).join('');
                container.querySelectorAll('.analyze-autocomplete-item').forEach(item => {
                    item.addEventListener('click', () => {
                        const t = item.dataset.ticker;
                        document.getElementById('analyzeTickerInput').value = t;
                        container.innerHTML = '';
                        analyzeTicker(t);
                    });
                });
            } catch (e) {
                container.innerHTML = '';
            }
        }, 250);
    }

    // ── Main fetch ───────────────────────────────────────────────────────
    async function analyzeTicker(ticker) {
        currentTicker = ticker;
        window.location.hash = `analyze/${ticker}`;

        document.getElementById('analyzeEmpty').style.display = 'none';
        document.getElementById('analyzeLoading').style.display = 'flex';
        document.getElementById('analyzeContent').style.display = 'none';

        try {
            const response = await apiRequest(`/api/analyze/${ticker}`);
            data = await response.json();
            if (!data || data.error) throw new Error(data?.error || 'No data');

            renderHeader(data.header);
            renderAiBrief(data);
            renderStats(data.stats);
            renderTrendBreak(data.trend_break, data.signals);
            renderIndicators(data.indicators, data.signals);
            renderAnalyst(data.analyst);
            renderOptions(data.options);
            renderEarnings(data.earnings);
            renderInstitutional(data.institutional);
            renderGuides(data);
            initGuideToggles();

            document.getElementById('analyzeLoading').style.display = 'none';
            document.getElementById('analyzeContent').style.display = 'block';

            // Load chart (Lightweight Charts) — fires chart + trendlines in parallel
            loadChart(ticker, '6mo', '1d');
            // Reset active button
            document.querySelectorAll('#analyzeChartPeriods button').forEach(b => {
                b.classList.toggle('active', b.dataset.period === '6mo');
            });

        } catch (e) {
            document.getElementById('analyzeLoading').style.display = 'none';
            document.getElementById('analyzeEmpty').style.display = 'flex';
            document.getElementById('analyzeEmpty').innerHTML = `
                <div class="analyze-empty-icon" style="color:var(--danger-color)">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="48" height="48">
                        <circle cx="12" cy="12" r="10"></circle>
                        <path d="M15 9l-6 6M9 9l6 6"></path>
                    </svg>
                </div>
                <h3>Could not load data for ${ticker}</h3>
                <p>${e.message || 'Please try again.'}</p>
            `;
        }
    }

    // ── Render: Header ───────────────────────────────────────────────────
    function renderHeader(h) {
        document.getElementById('analyzeHeaderTicker').textContent = currentTicker;
        document.getElementById('analyzeHeaderName').textContent = h.name || '';
        document.getElementById('analyzeHeaderSector').textContent =
            [h.sector, h.industry].filter(Boolean).join(' / ') || '';

        document.getElementById('analyzeHeaderPrice').textContent = `$${h.price.toFixed(2)}`;

        const changeEl = document.getElementById('analyzeHeaderChange');
        const sign = h.change >= 0 ? '+' : '';
        changeEl.textContent = `${sign}${h.change.toFixed(2)} (${sign}${h.change_pct.toFixed(2)}%)`;
        changeEl.className = 'analyze-change ' + (h.change >= 0 ? 'positive' : 'negative');

        // 52-week range
        const low = h.fifty_two_week_low;
        const high = h.fifty_two_week_high;
        const range52 = document.getElementById('analyze52Week');
        if (low && high && high > low) {
            range52.style.display = '';
            document.getElementById('analyze52Low').textContent = `$${low.toFixed(2)}`;
            document.getElementById('analyze52High').textContent = `$${high.toFixed(2)}`;
            const pct = ((h.price - low) / (high - low)) * 100;
            document.getElementById('analyze52Fill').style.width = `${Math.min(100, Math.max(0, pct))}%`;
            document.getElementById('analyze52Marker').style.left = `${Math.min(100, Math.max(0, pct))}%`;
        } else {
            range52.style.display = 'none';
        }

        // Quick stats row
        const qs = document.getElementById('analyzeQuickStats');
        qs.innerHTML = [
            _quickStat('Open', h.open),
            _quickStat('High', h.day_high),
            _quickStat('Low', h.day_low),
            _quickStat('Volume', _fmtNum(h.volume)),
            _quickStat('Avg Vol', _fmtNum(h.avg_volume)),
        ].join('');
    }

    function _quickStat(label, val) {
        return `<div class="qs"><span class="qs-label">${label}</span><span class="qs-val">${val != null ? (typeof val === 'number' ? '$' + val.toFixed(2) : val) : '--'}</span></div>`;
    }

    // ── Render: Key Stats ────────────────────────────────────────────────
    function renderStats(s) {
        const el = document.getElementById('analyzeStats');
        el.innerHTML = [
            _statRow('Market Cap', _fmtLargeNum(s.market_cap)),
            _statRow('P/E (TTM)', _fmtRatio(s.pe_ratio)),
            _statRow('Forward P/E', _fmtRatio(s.forward_pe)),
            _statRow('PEG', _fmtRatio(s.peg_ratio)),
            _statRow('P/S', _fmtRatio(s.ps_ratio)),
            _statRow('P/B', _fmtRatio(s.pb_ratio)),
            _statRow('EV/EBITDA', _fmtRatio(s.ev_ebitda)),
            _statRow('EPS (TTM)', _fmtDollar(s.eps)),
            _statRow('Fwd EPS', _fmtDollar(s.forward_eps)),
            _statRow('Div Yield', _fmtPct(s.dividend_yield)),
            _statRow('Beta', _fmtRatio(s.beta)),
            _statRow('Short % Float', _fmtPct(s.short_pct_float)),
            _statRow('Insider Own', _fmtPct(s.insider_pct)),
            _statRow('Inst Own', _fmtPct(s.institution_pct)),
            _statRow('ROE', _fmtPct(s.roe)),
            _statRow('Profit Margin', _fmtPct(s.profit_margin)),
            _statRow('Rev Growth', _fmtPct(s.revenue_growth)),
            _statRow('Oper Margin', _fmtPct(s.operating_margin)),
            _statRow('D/E', _fmtRatio(s.debt_to_equity)),
            _statRow('Revenue', _fmtLargeNum(s.revenue)),
            _statRow('EBITDA', _fmtLargeNum(s.ebitda)),
            _statRow('Free Cash Flow', _fmtLargeNum(s.free_cash_flow)),
        ].join('');
    }

    function _statRow(label, val) {
        return `<div class="stat-row"><span class="stat-label">${label}</span><span class="stat-value">${val}</span></div>`;
    }

    // ── Render: Trend Break + Indicators ─────────────────────────────────
    function renderTrendBreak(tb, signals) {
        const el = document.getElementById('analyzeTrendBreak');
        if (!tb || tb.probability == null) {
            el.innerHTML = '<div class="tb-unavailable">Trend break data unavailable</div>';
            return;
        }
        const dir = tb.direction || 'NEUTRAL';
        const prob = (tb.probability * 100).toFixed(1);
        const cls = dir === 'BULLISH' ? 'positive' : dir === 'BEARISH' ? 'negative' : '';
        const composite = signals?.composite || 'NEUTRAL';
        const compCls = composite === 'BULLISH' ? 'positive' : composite === 'BEARISH' ? 'negative' : '';

        el.innerHTML = `
            <div class="tb-card ${cls}">
                <div class="tb-main">
                    <span class="tb-label">Trend Break</span>
                    <span class="tb-prob">${prob}%</span>
                    <span class="tb-dir ${cls}">${dir}</span>
                </div>
                <div class="tb-composite">
                    <span class="tb-label">Composite Signal</span>
                    <span class="tb-dir ${compCls}">${composite}</span>
                </div>
            </div>
        `;
    }

    function renderIndicators(ind, signals) {
        const el = document.getElementById('analyzeIndicators');
        const rows = [
            _indRow('RSI', ind.rsi, signals?.rsi),
            _indRow('CCI', ind.cci, signals?.cci),
            _indRow('Stoch %K', ind.stochastic_k, signals?.stochastic),
            _indRow('Stoch %D', ind.stochastic_d),
            _indRow('ADX', ind.adx, signals?.adx),
            _indRow('SMA 20', ind.sma_20, null, true),
            _indRow('SMA 50', ind.sma_50, signals?.sma_cross, true),
        ];
        el.innerHTML = rows.join('');
    }

    function _indRow(name, val, signal, isPrice) {
        const display = val != null ? (isPrice ? '$' + val.toFixed(2) : val.toFixed(2)) : '--';
        let badge = '';
        if (signal) {
            const cls = signal === 'BUY' || signal === 'BULLISH' || signal === 'STRONG TREND'
                ? 'positive' : signal === 'SELL' || signal === 'BEARISH' ? 'negative' : 'neutral';
            badge = `<span class="ind-signal ${cls}">${signal}</span>`;
        }
        const tip = _getIndicatorTooltip(name, val, signal);
        const tipAttr = tip ? ` data-tooltip="${tip.replace(/"/g, '&quot;')}"` : '';
        return `<div class="ind-row has-tooltip"${tipAttr}><span class="ind-name">${name}</span><span class="ind-val">${display}</span>${badge}</div>`;
    }

    // ── Approach A: Tooltips ─────────────────────────────────────────────
    function _getIndicatorTooltip(name, val, signal) {
        if (val == null) return null;
        const v = val;
        switch (name) {
            case 'RSI':
                if (v < 30) return `RSI at ${v.toFixed(1)} is oversold (below 30). Selling pressure has been extreme — a bounce may be coming. Watch for confirmation from other indicators before buying.`;
                if (v > 70) return `RSI at ${v.toFixed(1)} is overbought (above 70). Buying pressure has been extreme — a pullback may be coming. Consider taking profits or tightening stops.`;
                return `RSI at ${v.toFixed(1)} is neutral (30-70 range). No extreme momentum in either direction. The trend may continue or reverse — look to other indicators for confirmation.`;
            case 'CCI':
                if (v < -100) return `CCI at ${v.toFixed(1)} is below -100, indicating strong downward momentum. The security is trading well below its average. Historically, readings this low can signal oversold conditions and potential reversal.`;
                if (v > 100) return `CCI at ${v.toFixed(1)} is above +100, indicating strong upward momentum. The security is trading well above its average. Consider that overbought conditions may lead to a pullback.`;
                return `CCI at ${v.toFixed(1)} is in the normal range (-100 to +100). No strong directional bias. Wait for a breakout above +100 or below -100 for a clearer signal.`;
            case 'Stoch %K':
                if (v < 20) return `Stochastic %K at ${v.toFixed(1)} is in oversold territory (below 20). The price is near the low of its recent range. A crossover of %K above %D from here generates a buy signal.`;
                if (v > 80) return `Stochastic %K at ${v.toFixed(1)} is in overbought territory (above 80). The price is near the high of its recent range. A crossover of %K below %D from here generates a sell signal.`;
                return `Stochastic %K at ${v.toFixed(1)} is in the middle range. Neither overbought nor oversold. Wait for a move to extremes for a clearer trading signal.`;
            case 'Stoch %D':
                return `Stochastic %D (${v.toFixed(1)}) is the 3-period moving average of %K. When %K crosses above %D, it's a buy signal. When %K crosses below %D, it's a sell signal. The signal is strongest at overbought/oversold extremes.`;
            case 'ADX':
                if (v > 40) return `ADX at ${v.toFixed(1)} indicates a very strong trend. Whether bullish or bearish (check +DI/-DI), the current trend has powerful momentum. Favor trend-following strategies and avoid counter-trend trades.`;
                if (v > 25) return `ADX at ${v.toFixed(1)} indicates a moderately strong trend. Directional movement is established. Trend-following strategies are appropriate.`;
                return `ADX at ${v.toFixed(1)} indicates a weak or absent trend (below 25). The market is ranging or consolidating. Range-trading strategies work best; avoid trend-following.`;
            case 'SMA 20':
                return `SMA 20 (20-day Simple Moving Average) at $${v.toFixed(2)} represents the short-term trend. When price is above the SMA 20, short-term momentum is bullish. When below, it's bearish.`;
            case 'SMA 50':
                if (signal === 'BULLISH') return `SMA 50 at $${v.toFixed(2)}. The SMA 20 is ABOVE the SMA 50 — this is a "Golden Cross" alignment, a bullish signal indicating the short-term trend is stronger than the long-term trend.`;
                if (signal === 'BEARISH') return `SMA 50 at $${v.toFixed(2)}. The SMA 20 is BELOW the SMA 50 — this is a "Death Cross" alignment, a bearish signal indicating the short-term trend is weaker than the long-term trend.`;
                return `SMA 50 (50-day Simple Moving Average) at $${v.toFixed(2)} represents the medium-term trend. Compare with SMA 20 for crossover signals.`;
            default:
                return null;
        }
    }

    // ── Approach B: Expandable Guide Panels ──────────────────────────────
    function renderGuides(d) {
        const ind = d.indicators || {};
        const sig = d.signals || {};
        const h = d.header || {};
        const s = d.stats || {};
        const a = d.analyst || {};
        const o = d.options || {};
        const e = d.earnings || {};
        const inst = d.institutional || {};

        // Indicators guide — contextual summary
        const buySignals = [];
        const sellSignals = [];
        if (sig.rsi === 'BUY') buySignals.push('RSI oversold');
        if (sig.rsi === 'SELL') sellSignals.push('RSI overbought');
        if (sig.cci === 'BUY') buySignals.push('CCI below -100');
        if (sig.cci === 'SELL') sellSignals.push('CCI above +100');
        if (sig.stochastic === 'BUY') buySignals.push('Stochastic oversold');
        if (sig.stochastic === 'SELL') sellSignals.push('Stochastic overbought');
        if (sig.sma_cross === 'BULLISH') buySignals.push('Golden Cross (SMA 20 > 50)');
        if (sig.sma_cross === 'BEARISH') sellSignals.push('Death Cross (SMA 20 < 50)');
        const adxStr = ind.adx ? (ind.adx > 25 ? `ADX at ${ind.adx.toFixed(0)} shows a strong trend` : `ADX at ${ind.adx.toFixed(0)} shows a weak/ranging market`) : '';

        let indGuide = '<div class="guide-content">';
        indGuide += `<p><strong>Your Indicator Summary:</strong> `;
        if (buySignals.length > 0) indGuide += `<span class="positive">${buySignals.length} bullish signal${buySignals.length > 1 ? 's' : ''}</span> (${buySignals.join(', ')}). `;
        if (sellSignals.length > 0) indGuide += `<span class="negative">${sellSignals.length} bearish signal${sellSignals.length > 1 ? 's' : ''}</span> (${sellSignals.join(', ')}). `;
        if (buySignals.length === 0 && sellSignals.length === 0) indGuide += 'All indicators are neutral — no strong directional bias. ';
        if (adxStr) indGuide += adxStr + '. ';
        indGuide += `Composite: <strong class="${sig.composite === 'BULLISH' ? 'positive' : sig.composite === 'BEARISH' ? 'negative' : ''}">${sig.composite || 'NEUTRAL'}</strong>.</p>`;
        indGuide += '<p class="guide-note">Indicators work best in combination. A single signal can be a false alarm — look for 3+ indicators agreeing for higher-conviction trades.</p>';
        indGuide += '</div>';
        _setGuide('indicatorsGuide', indGuide);

        // Stats guide
        let statsGuide = '<div class="guide-content">';
        statsGuide += '<p><strong>How to read these stats:</strong></p><ul>';
        statsGuide += '<li><strong>P/E Ratio</strong> — Price relative to earnings. Lower = cheaper. Compare to sector average, not absolute value. Forward P/E uses analyst estimates.</li>';
        statsGuide += '<li><strong>PEG</strong> — P/E divided by growth rate. PEG &lt; 1 suggests undervalued relative to growth.</li>';
        statsGuide += '<li><strong>ROE</strong> — Return on equity. How efficiently the company uses shareholder capital. Above 15% is generally strong.</li>';
        statsGuide += '<li><strong>Profit Margin</strong> — Net income as % of revenue. Higher is better. Compare within same sector.</li>';
        statsGuide += '<li><strong>Short % Float</strong> — Percentage of tradeable shares sold short. Above 10% is high and may indicate bearish sentiment or squeeze potential.</li>';
        statsGuide += '<li><strong>Beta</strong> — Volatility relative to the market. Beta &gt; 1 = more volatile than S&P 500. Beta &lt; 1 = less volatile.</li>';
        statsGuide += '</ul></div>';
        _setGuide('statsGuide', statsGuide);

        // Analyst guide
        let analystGuide = '<div class="guide-content">';
        analystGuide += '<p><strong>Analyst consensus</strong> aggregates buy/hold/sell ratings from Wall Street analysts. ';
        analystGuide += 'Ratings scale: 1 = Strong Buy, 2 = Buy, 3 = Hold, 4 = Sell, 5 = Strong Sell. ';
        analystGuide += 'Price targets show where analysts expect the stock to trade in 12 months. ';
        analystGuide += 'The mean target is the average — compare to current price for implied upside/downside.</p>';
        if (a.target_mean && h.price) {
            const upside = ((a.target_mean - h.price) / h.price * 100).toFixed(1);
            analystGuide += `<p>Analysts project <strong>${upside > 0 ? '+' : ''}${upside}%</strong> from current price to mean target of $${a.target_mean.toFixed(2)}.</p>`;
        }
        analystGuide += '</div>';
        _setGuide('analystGuide', analystGuide);

        // Options guide
        let optionsGuide = '<div class="guide-content">';
        optionsGuide += '<p><strong>Options summary</strong> shows the nearest at-the-money (ATM) call and put for the closest expiration. ';
        optionsGuide += '<strong>IV (Implied Volatility)</strong> reflects how much movement the market expects. Higher IV = more expensive options. ';
        optionsGuide += 'ATM options are the most liquid and have the highest time value. ';
        optionsGuide += 'Compare IV to historical levels — if IV is unusually high, options may be overpriced (good for sellers).</p>';
        optionsGuide += '</div>';
        _setGuide('optionsGuide', optionsGuide);

        // Earnings guide
        let earningsGuide = '<div class="guide-content">';
        earningsGuide += '<p><strong>Earnings results</strong> show EPS (Earnings Per Share) vs analyst estimates for the last 4 quarters. ';
        earningsGuide += 'A <strong class="positive">positive surprise</strong> (actual beats estimate) typically drives the stock higher. ';
        earningsGuide += 'A <strong class="negative">negative surprise</strong> (actual misses estimate) often causes a selloff. ';
        earningsGuide += 'Companies that consistently beat estimates tend to outperform. Look for the trend in surprises, not just one quarter.</p>';
        earningsGuide += '</div>';
        _setGuide('earningsGuide', earningsGuide);

        // Institutional guide
        let instGuide = '<div class="guide-content">';
        instGuide += '<p><strong>Institutional ownership</strong> shows how much of the stock is held by large investors (mutual funds, pension funds, hedge funds). ';
        instGuide += 'High institutional ownership (60%+) means smart money is involved but can also mean crowded positioning. ';
        instGuide += '13F filings (quarterly SEC reports) reveal exactly which funds hold the stock and whether they are increasing or reducing positions. ';
        instGuide += 'Rising institutional ownership is generally bullish — it means funds are accumulating.</p>';
        instGuide += '</div>';
        _setGuide('institutionalGuide', instGuide);
    }

    function _setGuide(id, html) {
        const el = document.getElementById(id);
        if (el) el.innerHTML = html;
    }

    function initGuideToggles() {
        document.querySelectorAll('.guide-toggle-btn').forEach(btn => {
            // Remove old listeners by cloning
            const newBtn = btn.cloneNode(true);
            btn.parentNode.replaceChild(newBtn, btn);
            newBtn.addEventListener('click', () => {
                const guideId = newBtn.dataset.guide;
                const guide = document.getElementById(guideId);
                if (guide) {
                    guide.classList.toggle('hidden');
                    newBtn.classList.toggle('active');
                }
            });
        });
    }

    // ── Approach C: AI Analysis Brief ────────────────────────────────────
    function renderAiBrief(d) {
        const el = document.getElementById('analyzeAiBriefBody');
        if (!el) return;

        const h = d.header || {};
        const s = d.stats || {};
        const sig = d.signals || {};
        const ind = d.indicators || {};
        const tb = d.trend_break || {};
        const a = d.analyst || {};
        const e = d.earnings || {};
        const inst = d.institutional || {};
        const o = d.options || {};

        const sentences = [];

        // Price context
        const changeDir = h.change >= 0 ? 'up' : 'down';
        sentences.push(`<strong>${currentTicker}</strong> is trading at <strong>$${h.price?.toFixed(2)}</strong>, ${changeDir} ${Math.abs(h.change_pct || 0).toFixed(1)}% today.`);

        // 52-week positioning
        if (h.fifty_two_week_low && h.fifty_two_week_high) {
            const range = h.fifty_two_week_high - h.fifty_two_week_low;
            const pct = range > 0 ? ((h.price - h.fifty_two_week_low) / range * 100).toFixed(0) : 50;
            if (pct > 80) sentences.push(`The stock is near its 52-week high, trading in the top ${100 - pct}% of its range.`);
            else if (pct < 20) sentences.push(`The stock is near its 52-week low, trading in the bottom ${pct}% of its range.`);
        }

        // Trend break
        if (tb.probability != null) {
            const prob = (tb.probability * 100).toFixed(0);
            const dir = tb.direction || 'neutral';
            if (tb.probability > 0.7) sentences.push(`The trend break model gives a <strong>${prob}%</strong> probability of a <strong class="${dir === 'BULLISH' ? 'positive' : 'negative'}">${dir.toLowerCase()}</strong> move.`);
            else sentences.push(`Trend break probability is moderate at ${prob}% (${dir.toLowerCase()}).`);
        }

        // Composite signal
        const comp = sig.composite;
        if (comp === 'BULLISH') sentences.push('Technical indicators are <strong class="positive">bullish</strong> overall — multiple signals agree on upward momentum.');
        else if (comp === 'BEARISH') sentences.push('Technical indicators are <strong class="negative">bearish</strong> overall — multiple signals agree on downward pressure.');
        else sentences.push('Technical indicators are <strong>mixed</strong> — no clear directional consensus.');

        // SMA cross
        if (sig.sma_cross === 'BULLISH') sentences.push('The SMA 20/50 Golden Cross confirms the short-term uptrend.');
        else if (sig.sma_cross === 'BEARISH') sentences.push('The SMA 20/50 Death Cross signals short-term weakness.');

        // ADX trend strength
        if (ind.adx) {
            if (ind.adx > 40) sentences.push(`ADX at ${ind.adx.toFixed(0)} indicates a very strong trend — follow the direction, don't fade it.`);
            else if (ind.adx < 20) sentences.push(`ADX at ${ind.adx.toFixed(0)} indicates a weak, ranging market — breakout strategies may underperform.`);
        }

        // Analyst consensus
        if (a.recommendation && a.target_mean && h.price) {
            const upside = ((a.target_mean - h.price) / h.price * 100).toFixed(0);
            const numAnalysts = a.num_analysts || 'several';
            sentences.push(`${numAnalysts} analyst${a.num_analysts !== 1 ? 's' : ''} rate it <strong>${a.recommendation.replace('_', ' ').toUpperCase()}</strong> with a mean target of $${a.target_mean.toFixed(2)} (${upside > 0 ? '+' : ''}${upside}% implied).`);
        }

        // Earnings track record
        if (e.quarters && e.quarters.length > 0) {
            const beats = e.quarters.filter(q => {
                const surp = q.epsDifference ?? q.epsdifference ?? q.surprisePercent ?? q.surprisepercent;
                return surp != null && surp > 0;
            }).length;
            if (beats === e.quarters.length) sentences.push(`The company has <strong class="positive">beaten estimates all ${beats} of the last ${e.quarters.length} quarters</strong>.`);
            else if (beats > 0) sentences.push(`Earnings beat estimates in ${beats} of the last ${e.quarters.length} quarters.`);
            if (e.next_date) sentences.push(`Next earnings: <strong>${e.next_date}</strong>.`);
        }

        // IV context
        if (o.implied_volatility) {
            const iv = (o.implied_volatility * 100).toFixed(0);
            if (o.implied_volatility > 0.5) sentences.push(`Options IV is elevated at ${iv}%, suggesting the market expects significant movement.`);
        }

        // Institutional
        if (inst.pct_held) {
            sentences.push(`Institutional ownership: ${(inst.pct_held * 100).toFixed(0)}%.`);
        }

        // Valuation snapshot
        if (s.pe_ratio && s.forward_pe) {
            sentences.push(`Valuation: ${s.pe_ratio.toFixed(1)}x trailing P/E, ${s.forward_pe.toFixed(1)}x forward P/E.`);
        }

        el.innerHTML = `<p>${sentences.join(' ')}</p>`;
    }

    // ── Render: Analyst ──────────────────────────────────────────────────
    function renderAnalyst(a) {
        const el = document.getElementById('analyzeAnalyst');
        if (!a || (!a.recommendation && !a.target_mean)) {
            el.innerHTML = '<p class="muted">No analyst data available.</p>';
            return;
        }

        const rec = (a.recommendation || 'N/A').replace('_', ' ');
        const recScore = a.recommendation_mean;
        const recLabel = recScore ? `(${recScore.toFixed(1)}/5)` : '';
        const analysts = a.num_analysts ? `${a.num_analysts} analysts` : '';

        let targetsHtml = '';
        if (a.target_low && a.target_high && data?.header?.price) {
            const price = data.header.price;
            const low = a.target_low;
            const high = a.target_high;
            const mean = a.target_mean || (low + high) / 2;
            const range = high - low || 1;
            const pricePct = Math.min(100, Math.max(0, ((price - low) / range) * 100));
            const meanPct = Math.min(100, Math.max(0, ((mean - low) / range) * 100));

            targetsHtml = `
                <div class="analyst-targets">
                    <div class="analyst-target-labels">
                        <span>$${low.toFixed(2)}</span>
                        <span>Price Targets</span>
                        <span>$${high.toFixed(2)}</span>
                    </div>
                    <div class="analyst-target-bar">
                        <div class="analyst-target-current" style="left:${pricePct}%" title="Current: $${price.toFixed(2)}"></div>
                        <div class="analyst-target-mean" style="left:${meanPct}%" title="Mean: $${mean.toFixed(2)}"></div>
                    </div>
                    <div class="analyst-target-legend">
                        <span>Current: <strong>$${price.toFixed(2)}</strong></span>
                        <span>Mean Target: <strong>$${mean.toFixed(2)}</strong></span>
                    </div>
                </div>
            `;
        }

        el.innerHTML = `
            <div class="analyst-rec">
                <span class="analyst-rec-label">${rec.toUpperCase()}</span>
                <span class="analyst-rec-score">${recLabel}</span>
                <span class="analyst-rec-count">${analysts}</span>
            </div>
            ${targetsHtml}
        `;
    }

    // ── Render: Options ──────────────────────────────────────────────────
    function renderOptions(o) {
        const el = document.getElementById('analyzeOptions');
        if (!o || !o.available) {
            el.innerHTML = '<p class="muted">No options data available.</p>';
            return;
        }
        el.innerHTML = `
            <div class="analyze-stats-grid">
                ${_statRow('Nearest Expiry', o.nearest_expiry || '--')}
                ${_statRow('IV', o.implied_volatility ? (o.implied_volatility * 100).toFixed(1) + '%' : '--')}
                ${_statRow('ATM Call', o.nearest_call_strike ? '$' + o.nearest_call_strike.toFixed(2) : '--')}
                ${_statRow('Call Price', o.nearest_call_price ? '$' + o.nearest_call_price.toFixed(2) : '--')}
                ${_statRow('ATM Put', o.nearest_put_strike ? '$' + o.nearest_put_strike.toFixed(2) : '--')}
                ${_statRow('Put Price', o.nearest_put_price ? '$' + o.nearest_put_price.toFixed(2) : '--')}
            </div>
        `;
    }

    // ── Render: Earnings ─────────────────────────────────────────────────
    function renderEarnings(e) {
        const el = document.getElementById('analyzeEarnings');
        if (!e) {
            el.innerHTML = '<p class="muted">No earnings data available.</p>';
            return;
        }

        let html = '';
        if (e.next_date) {
            html += `<div class="earnings-next">Next Earnings: <strong>${e.next_date}</strong></div>`;
        }

        if (e.quarters && e.quarters.length > 0) {
            html += '<table class="earnings-table"><thead><tr><th>Date</th><th>EPS Est</th><th>EPS Actual</th><th>Surprise</th></tr></thead><tbody>';
            for (const q of e.quarters) {
                const est = q.epsEstimate ?? q.epsestimate ?? '--';
                const act = q.epsActual ?? q.epsactual ?? '--';
                const surp = q.epsDifference ?? q.epsdifference ?? q.surprisePercent ?? q.surprisepercent;
                const surpriseStr = surp != null ? (surp >= 0 ? '+' : '') + Number(surp).toFixed(2) : '--';
                const cls = surp != null ? (surp >= 0 ? 'positive' : 'negative') : '';
                const date = q.reportDate ?? q.reportdate ?? q['Earnings Date'] ?? '--';
                html += `<tr><td>${date}</td><td>${_fmtDollar(est)}</td><td>${_fmtDollar(act)}</td><td class="${cls}">${surpriseStr}</td></tr>`;
            }
            html += '</tbody></table>';
        } else {
            html += '<p class="muted">No quarterly earnings history available.</p>';
        }

        el.innerHTML = html;
    }

    // ── Render: Institutional ────────────────────────────────────────────
    function renderInstitutional(inst) {
        const el = document.getElementById('analyzeInstitutional');
        if (!inst) {
            el.innerHTML = '<p class="muted">No institutional data available.</p>';
            return;
        }

        let html = '';
        if (inst.pct_held != null) {
            html += `<div class="inst-pct">Institutional: <strong>${(inst.pct_held * 100).toFixed(1)}%</strong></div>`;
        }

        if (inst.top_holders && inst.top_holders.length > 0) {
            html += '<table class="inst-table"><thead><tr><th>Holder</th><th>Shares</th><th>Value</th></tr></thead><tbody>';
            for (const h of inst.top_holders.slice(0, 8)) {
                const name = h.Holder || h.holder || h.fund || '--';
                const shares = _fmtNum(h.Shares || h.shares);
                const val = _fmtLargeNum(h.Value || h.value);
                html += `<tr><td>${name}</td><td>${shares}</td><td>${val}</td></tr>`;
            }
            html += '</tbody></table>';
        }

        if (inst.thirteen_f && inst.thirteen_f.length > 0) {
            html += '<h4 style="margin-top:12px">13F Holdings</h4>';
            html += '<table class="inst-table"><thead><tr><th>Fund</th><th>Shares</th><th>Date</th></tr></thead><tbody>';
            for (const h of inst.thirteen_f) {
                html += `<tr><td>${h.fund}</td><td>${_fmtNum(h.shares)}</td><td>${h.report_date}</td></tr>`;
            }
            html += '</tbody></table>';
        }

        el.innerHTML = html || '<p class="muted">No institutional data available.</p>';
    }

    // ── Chart (Lightweight Charts) ─────────────────────────────────────
    async function loadChart(ticker, period, interval) {
        currentChartPeriod = period;
        currentChartInterval = interval;

        try {
            // Fetch chart data + trendlines + patterns in parallel
            const fetches = [
                apiRequest(`/api/analyze/${ticker}/chart?period=${period}&interval=${interval}`),
                apiRequest(`/api/analyze/${ticker}/trendlines?period=${period}&interval=${interval}`),
            ];
            if (document.getElementById('togglePatterns')?.checked) {
                fetches.push(apiRequest(`/api/analyze/${ticker}/patterns?period=${period}`));
            }

            const responses = await Promise.all(fetches);
            const chartData = await responses[0].json();
            let trendData = null;
            let patternData = null;
            try { trendData = await responses[1].json(); } catch (e) {}
            if (responses[2]) { try { patternData = await responses[2].json(); } catch (e) {} }

            if (!chartData || !chartData.data || chartData.data.length === 0) return;

            // Create or update chart
            if (!AlphaCharts.instances['analyzeChartContainer']) {
                AlphaCharts.create('analyzeChartContainer', { height: 400, volumeHeight: 60 });
            }

            // Filter overlays based on toggle state
            const overlays = chartData.overlays || {};
            const filteredOverlays = {};
            if (document.getElementById('toggleSMA')?.checked) {
                filteredOverlays.sma_10 = overlays.sma_10;
                filteredOverlays.sma_50 = overlays.sma_50;
            }
            if (document.getElementById('toggleBB')?.checked) {
                filteredOverlays.bb_upper = overlays.bb_upper;
                filteredOverlays.bb_lower = overlays.bb_lower;
            }

            AlphaCharts.setData('analyzeChartContainer', chartData.data, filteredOverlays);

            // Add trendlines if enabled
            if (document.getElementById('toggleTrendlines')?.checked && trendData) {
                AlphaCharts.setTrendlines('analyzeChartContainer', trendData);
            }

            // Add candlestick pattern markers if enabled
            if (document.getElementById('togglePatterns')?.checked && patternData) {
                AlphaCharts.setPatterns('analyzeChartContainer', patternData);
                // Render seasonality heatmap
                if (patternData.seasonality) {
                    AlphaCharts.renderSeasonality('analyzeChartContainer', patternData.seasonality);
                }
            } else {
                const patternBar = document.getElementById('patternMarkers');
                if (patternBar) patternBar.style.display = 'none';
                const seasEl = document.getElementById('seasonalityContainer');
                if (seasEl) seasEl.style.display = 'none';
            }

            // Load compare if toggle is on
            if (document.getElementById('toggleCompare')?.checked) {
                loadCompare(ticker, period);
            }

        } catch (e) {
            console.error('Chart load failed:', e);
        }
    }

    async function loadCompare(ticker, period) {
        try {
            const resp = await apiRequest(`/api/analyze/${ticker}/compare?period=${period}`);
            const data = await resp.json();
            if (data?.symbols) {
                AlphaCharts.setCompare('analyzeChartContainer', data);
            }
        } catch (e) {
            console.error('Compare load failed:', e);
        }
    }

    // ── Formatting helpers ───────────────────────────────────────────────
    function _fmtNum(n) {
        if (n == null) return '--';
        return Number(n).toLocaleString();
    }

    function _fmtLargeNum(n) {
        if (n == null) return '--';
        n = Number(n);
        if (Math.abs(n) >= 1e12) return '$' + (n / 1e12).toFixed(2) + 'T';
        if (Math.abs(n) >= 1e9) return '$' + (n / 1e9).toFixed(2) + 'B';
        if (Math.abs(n) >= 1e6) return '$' + (n / 1e6).toFixed(2) + 'M';
        if (Math.abs(n) >= 1e3) return '$' + (n / 1e3).toFixed(1) + 'K';
        return '$' + n.toFixed(2);
    }

    function _fmtPct(v) {
        if (v == null) return '--';
        return (v * 100).toFixed(2) + '%';
    }

    function _fmtRatio(v) {
        if (v == null) return '--';
        return Number(v).toFixed(2);
    }

    function _fmtDollar(v) {
        if (v == null || v === '--') return '--';
        return '$' + Number(v).toFixed(2);
    }

    return { init, analyzeTicker };
})();

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => Analyze.init());
