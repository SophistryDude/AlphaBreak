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

        // Auto-uppercase + autocomplete (only on manual typing, not programmatic)
        let suppressAutocomplete = false;
        input.addEventListener('input', () => {
            input.value = input.value.toUpperCase();
            if (!suppressAutocomplete) {
                handleAutocomplete(input.value);
            }
            suppressAutocomplete = false;
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

        // VWAP toggle
        const vwapToggle = document.getElementById('toggleVWAP');
        if (vwapToggle) {
            vwapToggle.addEventListener('change', () => {
                AlphaCharts.toggleIndicator('analyzeChartContainer', 'vwap');
            });
        }

        // Indicator sub-pane toggles (RSI, MACD, Stochastic)
        ['toggleRSI', 'toggleMACD', 'toggleStoch'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.addEventListener('change', () => {
                const indicator = id === 'toggleRSI' ? 'rsi' : id === 'toggleMACD' ? 'macd' : 'stochastic';
                AlphaCharts.toggleIndicator('analyzeChartContainer', indicator);
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
                if (!resp.ok) { container.innerHTML = ''; return; }
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
        document.getElementById('analyzeAutocomplete').innerHTML = '';
        if (typeof Onboarding !== 'undefined') Onboarding.trackSearch();

        document.getElementById('analyzeEmpty').style.display = 'none';
        document.getElementById('analyzeLoading').style.display = 'flex';
        document.getElementById('analyzeContent').style.display = 'none';

        try {
            const response = await apiRequest(`/api/analyze/${ticker}`);
            if (!response.ok) throw new Error(`API error: ${response.status}`);
            data = await response.json();
            if (!data || data.error) throw new Error(data?.error || 'No data');

            renderHeader(data.header);
            renderAiBrief(data);
            renderStats(data.stats);
            renderTrendBreak(data.trend_break, data.signals);
            renderIndicators(data.indicators, data.signals);
            renderShortInterest(data.short_interest);
            loadDarkPool(ticker);
            // Pro-gated: Peer Comparison (async, non-blocking)
            if (Premium.canAccess('peer_comparison')) {
                loadPeerComparison(ticker);
            } else {
                Premium.showLocked('analyzePeerComparison', 'peer_comparison');
            }
            renderDividend(data.dividend);
            renderAnalyst(data.analyst);
            renderOptions(data.options);
            // Pro-gated: Unusual Options Activity (async, non-blocking)
            if (Premium.canAccess('unusual_options')) {
                loadUnusualOptions(ticker);
            } else {
                Premium.showLocked('analyzeUnusualOptions', 'unusual_options');
            }
            renderEarnings(data.earnings);
            renderNews(data.news, data.news_sentiment);

            // Pro-gated features
            if (Premium.canAccess('institutional_13f')) {
                renderInstitutional(data.institutional);
                const access = Premium.checkAccess('institutional_13f');
                if (access.isTrial) {
                    Premium.recordTrial('institutional_13f');
                    Premium.showTrialBanner('analyzeInstitutional', 'institutional_13f');
                }
            } else {
                Premium.showLocked('analyzeInstitutional', 'institutional_13f');
            }

            // Pro-gated: Insider Trading (async, non-blocking)
            if (Premium.canAccess('insider_trading')) {
                loadInsiderTrading(ticker);
            } else {
                Premium.showLocked('analyzeInsiderTrading', 'insider_trading');
            }

            renderGuides(data);
            initGuideToggles();

            if (Premium.canAccess('quant_grades')) {
                loadGrades(ticker);
            } else {
                Premium.showLocked('analyzeGrades', 'quant_grades');
            }

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
        optionsGuide += 'Compare IV to historical levels — if IV is unusually high, options may be overpriced (good for sellers). ';
        optionsGuide += '<strong>PoP (Probability of Profit)</strong> uses the Black-Scholes model to estimate the chance an option expires in-the-money. ';
        optionsGuide += 'Green (>60%) = favorable odds, yellow (40-60%) = coin flip, red (<40%) = unfavorable odds.</p>';
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

    // ── Render: Short Interest ──────────────────────────────────────────
    function renderShortInterest(si) {
        const el = document.getElementById('analyzeShortInterest');
        if (!si || si.short_pct_float == null) {
            el.innerHTML = '<p class="muted">No short interest data available.</p>';
            return;
        }

        const shortPct = si.short_pct_float ? (si.short_pct_float * 100).toFixed(1) + '%' : '--';
        const daysTo = si.days_to_cover ? si.days_to_cover.toFixed(1) : '--';
        const sharesShort = si.shares_short ? _fmtLargeNum(si.shares_short) : '--';
        const priorShort = si.shares_short_prior ? _fmtLargeNum(si.shares_short_prior) : '--';
        const momChange = si.short_change_mom != null ? (si.short_change_mom >= 0 ? '+' : '') + (si.short_change_mom * 100).toFixed(1) + '%' : '--';
        const momCls = si.short_change_mom != null ? (si.short_change_mom > 0 ? 'negative' : 'positive') : '';

        // Squeeze risk: >20% short float + <3 days to cover = high risk
        let squeezeRisk = 'Low';
        let squeezeCls = 'muted';
        if (si.short_pct_float > 0.2 && si.days_to_cover && si.days_to_cover < 3) {
            squeezeRisk = 'High';
            squeezeCls = 'negative';
        } else if (si.short_pct_float > 0.1) {
            squeezeRisk = 'Moderate';
            squeezeCls = 'warning';
        }

        el.innerHTML = `
            <div class="analyze-stats-grid">
                ${_statRow('Short % of Float', shortPct)}
                ${_statRow('Days to Cover', daysTo)}
                ${_statRow('Shares Short', sharesShort)}
                ${_statRow('Prior Month', priorShort)}
                ${_statRow('MoM Change', `<span class="${momCls}">${momChange}</span>`)}
                ${_statRow('Squeeze Risk', `<span class="${squeezeCls}">${squeezeRisk}</span>`)}
            </div>
        `;
    }

    // ── Render: Dark Pool Activity ─────────────────────────────────────
    async function loadDarkPool(ticker) {
        const el = document.getElementById('analyzeDarkPool');
        if (!el) return;
        el.innerHTML = '<p class="muted">Loading dark pool data...</p>';

        try {
            const resp = await fetch(`/api/darkpool/${ticker}`, {
                headers: { 'Authorization': 'Bearer ' + (localStorage.getItem('access_token') || '') }
            });
            if (!resp.ok) throw new Error('No data');
            const dp = await resp.json();
            if (!dp || dp.error) throw new Error(dp?.error || 'No data');

            const latest = dp.latest || {};
            const totalShares = latest.total_shares ? _fmtLargeNum(latest.total_shares) : '--';
            const totalTrades = latest.total_trades ? _fmtNum(latest.total_trades) : '--';
            const venues = latest.num_ats_venues || '--';
            const concentration = latest.concentration_ratio
                ? (latest.concentration_ratio * 100).toFixed(1) + '%' : '--';

            let wowHtml = '--';
            if (dp.wow_change != null) {
                const pct = (dp.wow_change * 100).toFixed(1);
                const arrow = dp.wow_change >= 0 ? '&#9650;' : '&#9660;';
                const cls = dp.wow_change >= 0 ? 'positive' : 'negative';
                wowHtml = `<span class="${cls}">${arrow} ${pct}%</span>`;
            }

            let venueTable = '';
            if (dp.top_venues && dp.top_venues.length > 0) {
                venueTable = '<table class="inst-table" style="margin-top:8px"><thead><tr><th>Venue</th><th>Shares</th></tr></thead><tbody>';
                for (const v of dp.top_venues) {
                    venueTable += `<tr><td>${v.ats_name || v.ats_mpid}</td><td>${_fmtLargeNum(v.shares)}</td></tr>`;
                }
                venueTable += '</tbody></table>';
            }

            let sparkHtml = '';
            if (dp.weeks && dp.weeks.length > 1) {
                const vols = dp.weeks.map(w => w.total_shares).reverse();
                const max = Math.max(...vols);
                sparkHtml = '<div style="display:flex;align-items:flex-end;gap:2px;height:40px;margin-top:10px">';
                for (const v of vols) {
                    const h = max > 0 ? Math.max(2, Math.round((v / max) * 38)) : 2;
                    sparkHtml += `<div style="flex:1;height:${h}px;background:var(--accent);border-radius:2px" title="${_fmtNum(v)}"></div>`;
                }
                sparkHtml += '</div><div class="muted" style="font-size:11px;margin-top:2px">12-week volume trend</div>';
            }

            el.innerHTML = `
                <div class="analyze-stats-grid">
                    ${_statRow('Dark Pool Volume', totalShares)}
                    ${_statRow('WoW Change', wowHtml)}
                    ${_statRow('Total Trades', totalTrades)}
                    ${_statRow('ATS Venues', venues)}
                    ${_statRow('Concentration', concentration)}
                </div>
                ${venueTable}
                ${sparkHtml}
            `;
        } catch (e) {
            el.innerHTML = '<p class="muted">No dark pool data available.</p>';
        }
    }

    // ── Render: Insider Trading (Pro) ─────────────────────────────────
    async function loadInsiderTrading(ticker) {
        const el = document.getElementById('analyzeInsiderTrading');
        if (!el) return;
        el.innerHTML = '<p class="muted">Loading insider trading data...</p>';

        try {
            const resp = await apiRequest(`/api/analyze/${ticker}/insiders`);
            if (!resp.ok) throw new Error('No data');
            const data = await resp.json();
            if (!data || data.error) throw new Error(data?.error || 'No data');

            const txns = data.transactions || [];
            const summary = data.summary || {};

            // Summary line
            const buys = summary.total_buys || 0;
            const sells = summary.total_sells || 0;
            const sentiment = summary.net_sentiment || 'N/A';
            let sentimentCls = '';
            if (sentiment === 'Bullish') sentimentCls = 'positive';
            else if (sentiment === 'Bearish') sentimentCls = 'negative';

            let summaryHtml = `
                <div class="analyze-stats-grid">
                    ${_statRow('Buys (90d)', `<span class="positive">${buys}</span>`)}
                    ${_statRow('Sells (90d)', `<span class="negative">${sells}</span>`)}
                    ${_statRow('Buy Value', _fmtLargeNum(summary.buy_value))}
                    ${_statRow('Sell Value', _fmtLargeNum(summary.sell_value))}
                    ${_statRow('Net Sentiment', `<span class="${sentimentCls}">${sentiment}</span>`)}
                </div>
            `;

            // Transaction table
            let tableHtml = '';
            if (txns.length > 0) {
                tableHtml = `
                    <table class="inst-table" style="margin-top:8px">
                        <thead>
                            <tr>
                                <th>Date</th>
                                <th>Insider</th>
                                <th>Title</th>
                                <th>Type</th>
                                <th>Shares</th>
                                <th>Value</th>
                            </tr>
                        </thead>
                        <tbody>
                `;
                for (const t of txns) {
                    const typeCls = t.type === 'Buy' ? 'positive' : 'negative';
                    const typeLabel = t.type === 'Buy' ? '&#9650; Buy' : '&#9660; Sell';
                    const valStr = t.value ? _fmtLargeNum(t.value) : '--';
                    const sharesStr = t.shares ? _fmtNum(t.shares) : '--';
                    tableHtml += `
                        <tr>
                            <td>${t.date || '--'}</td>
                            <td>${t.insider || 'Unknown'}</td>
                            <td>${t.title || '--'}</td>
                            <td><span class="${typeCls}">${typeLabel}</span></td>
                            <td>${sharesStr}</td>
                            <td>${valStr}</td>
                        </tr>
                    `;
                }
                tableHtml += '</tbody></table>';
            } else {
                tableHtml = '<p class="muted" style="margin-top:8px">No insider transactions in the last 90 days.</p>';
            }

            el.innerHTML = summaryHtml + tableHtml;

            // Record trial if applicable
            const access = Premium.checkAccess('insider_trading');
            if (access.isTrial) {
                Premium.recordTrial('insider_trading');
                Premium.showTrialBanner('analyzeInsiderTrading', 'insider_trading');
            }
        } catch (e) {
            el.innerHTML = '<p class="muted">No insider trading data available.</p>';
        }
    }

    // ── Render: Unusual Options Activity (Pro) ─────────────────────────
    async function loadUnusualOptions(ticker) {
        const el = document.getElementById('analyzeUnusualOptions');
        if (!el) return;
        el.innerHTML = '<p class="muted">Loading unusual options activity...</p>';

        try {
            const resp = await apiRequest(`/api/analyze/${ticker}/unusual-options`);
            if (!resp.ok) throw new Error('No data');
            const data = await resp.json();
            if (!data || data.error) throw new Error(data?.error || 'No data');

            const s = data.summary || {};
            const contracts = data.unusual_contracts || [];

            if (s.total_unusual === 0) {
                el.innerHTML = '<p class="muted">No unusual options activity detected.</p>';
                return;
            }

            // Summary line
            const premiumStr = _fmtLargeNum(s.total_premium);
            let summaryHtml = `<div class="unusual-options-summary" style="margin-bottom:12px;padding:10px;border-radius:6px;background:var(--card-bg);border:1px solid var(--border);">`;
            summaryHtml += `<strong>${s.total_unusual} unusual contract${s.total_unusual !== 1 ? 's' : ''} detected</strong> &mdash; `;
            summaryHtml += `<span style="color:var(--green)">${s.bullish_count} bullish</span>, `;
            summaryHtml += `<span style="color:var(--red)">${s.bearish_count} bearish</span>, `;
            summaryHtml += `${premiumStr} total premium`;
            summaryHtml += `</div>`;

            // Table
            let tableHtml = '<div style="overflow-x:auto"><table class="inst-table"><thead><tr>';
            tableHtml += '<th>Expiry</th><th>Strike</th><th>Type</th><th>Volume</th><th>OI</th><th>Vol/OI</th><th>IV</th><th>Sweep</th>';
            tableHtml += '</tr></thead><tbody>';

            for (const c of contracts) {
                const typeColor = c.type === 'call' ? 'var(--green)' : 'var(--red)';
                const typeLabel = c.type === 'call' ? 'CALL' : 'PUT';
                const sweepBadge = c.is_sweep
                    ? '<span style="background:var(--accent);color:#fff;padding:1px 6px;border-radius:3px;font-size:11px;font-weight:600">SWEEP</span>'
                    : '';
                const volOi = c.vol_oi_ratio != null ? c.vol_oi_ratio.toFixed(1) + 'x' : '--';
                const iv = c.iv != null ? (c.iv * 100).toFixed(1) + '%' : '--';

                tableHtml += `<tr>`;
                tableHtml += `<td>${c.expiry}</td>`;
                tableHtml += `<td>$${c.strike.toFixed(2)}</td>`;
                tableHtml += `<td style="color:${typeColor};font-weight:600">${typeLabel}</td>`;
                tableHtml += `<td>${_fmtNum(c.volume)}</td>`;
                tableHtml += `<td>${_fmtNum(c.open_interest)}</td>`;
                tableHtml += `<td>${volOi}</td>`;
                tableHtml += `<td>${iv}</td>`;
                tableHtml += `<td>${sweepBadge}</td>`;
                tableHtml += `</tr>`;
            }

            tableHtml += '</tbody></table></div>';

            el.innerHTML = summaryHtml + tableHtml;

            // Show trial banner if applicable
            const access = Premium.checkAccess('unusual_options');
            if (access.isTrial) {
                Premium.recordTrial('unusual_options');
                Premium.showTrialBanner('analyzeUnusualOptions', 'unusual_options');
            }
        } catch (e) {
            el.innerHTML = '<p class="muted">Unusual options data unavailable.</p>';
        }
    }

    // ── Render: Peer Comparison (Pro) ──────────────────────────────────
    async function loadPeerComparison(ticker) {
        const el = document.getElementById('analyzePeerComparison');
        if (!el) return;
        el.innerHTML = '<p class="muted">Loading peer comparison...</p>';

        try {
            const resp = await apiRequest(`/api/analyze/${ticker}/peers`);
            if (!resp.ok) throw new Error(`Peers API error: ${resp.status}`);
            const result = await resp.json();
            if (result.error) {
                el.innerHTML = `<p class="muted">${result.error}</p>`;
                return;
            }
            renderPeerComparison(result);
            const access = Premium.checkAccess('peer_comparison');
            if (access.isTrial) {
                Premium.recordTrial('peer_comparison');
                Premium.showTrialBanner('analyzePeerComparison', 'peer_comparison');
            }
        } catch (e) {
            el.innerHTML = '<p class="muted">Peer comparison unavailable.</p>';
        }
    }

    function renderPeerComparison(result) {
        const el = document.getElementById('analyzePeerComparison');
        if (!el) return;

        const peers = result.peers || [];
        if (peers.length === 0) {
            el.innerHTML = '<p class="muted">No peer data available.</p>';
            return;
        }

        let html = `<div class="peer-sector-info muted" style="margin-bottom:8px;font-size:12px">${result.sector || ''}${result.industry ? ' / ' + result.industry : ''}</div>`;
        html += '<div style="overflow-x:auto"><table class="inst-table peer-table"><thead><tr>';
        html += '<th>Ticker</th><th>Market Cap</th><th>P/E</th><th>EV/EBITDA</th><th>ROE</th><th>Rev Growth</th><th>Profit Margin</th>';
        html += '</tr></thead><tbody>';

        for (const p of peers) {
            const rowCls = p.is_target ? ' class="peer-target-row"' : '';
            const tickerLabel = p.is_target ? `<strong>${p.ticker}</strong>` : p.ticker;
            html += `<tr${rowCls}>`;
            html += `<td title="${p.name || ''}">${tickerLabel}</td>`;
            html += `<td>${_fmtLargeNum(p.market_cap)}</td>`;
            html += `<td>${_fmtRatio(p.pe_ratio)}</td>`;
            html += `<td>${_fmtRatio(p.ev_ebitda)}</td>`;
            html += `<td>${_fmtPct(p.roe)}</td>`;
            html += `<td>${_fmtPct(p.revenue_growth)}</td>`;
            html += `<td>${_fmtPct(p.profit_margin)}</td>`;
            html += '</tr>';
        }

        html += '</tbody></table></div>';
        el.innerHTML = html;
    }

    // ── Render: Dividend Analysis ────────────────────────────────────────
    function renderDividend(d) {
        const el = document.getElementById('analyzeDividend');
        if (!d || (d.dividend_yield == null && d.dividend_rate == null)) {
            el.innerHTML = '<p class="muted">This stock does not pay a dividend.</p>';
            return;
        }

        const annualRate = d.dividend_rate ? '$' + d.dividend_rate.toFixed(2) : '--';
        const yld = d.dividend_yield ? (d.dividend_yield * 100).toFixed(2) + '%' : '--';
        const payout = d.payout_ratio ? (d.payout_ratio * 100).toFixed(1) + '%' : '--';
        const fiveYrAvg = d.five_yr_avg_yield ? d.five_yr_avg_yield.toFixed(2) + '%' : '--';

        // Ex-date: yfinance returns epoch seconds
        let exDate = '--';
        if (d.ex_date) {
            try {
                const dt = new Date(d.ex_date * 1000);
                exDate = dt.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
            } catch (e) { exDate = String(d.ex_date); }
        }

        // Dividend safety: payout < 60% = safe, 60-80% = caution, >80% = high risk
        let safety = '--';
        let safetyCls = '';
        if (d.payout_ratio != null) {
            if (d.payout_ratio < 0.6) { safety = 'Safe'; safetyCls = 'positive'; }
            else if (d.payout_ratio < 0.8) { safety = 'Caution'; safetyCls = 'warning'; }
            else { safety = 'At Risk'; safetyCls = 'negative'; }
        }

        el.innerHTML = `
            <div class="analyze-stats-grid">
                ${_statRow('Annual Dividend', annualRate)}
                ${_statRow('Yield', yld)}
                ${_statRow('Payout Ratio', payout)}
                ${_statRow('Safety', `<span class="${safetyCls}">${safety}</span>`)}
                ${_statRow('5-Yr Avg Yield', fiveYrAvg)}
                ${_statRow('Ex-Dividend Date', exDate)}
            </div>
        `;
    }

    // ── Render: Options ──────────────────────────────────────────────────
    function renderOptions(o) {
        const el = document.getElementById('analyzeOptions');
        if (!o || !o.available) {
            el.innerHTML = '<p class="muted">No options data available.</p>';
            return;
        }

        // Market Maker Move
        let mmHtml = '';
        if (o.mm_move_pct) {
            const movePct = (o.mm_move_pct * 100).toFixed(1);
            const moveDollar = o.mm_move_dollar.toFixed(2);
            const rangeLow = o.mm_move_range ? '$' + o.mm_move_range[0].toFixed(2) : '--';
            const rangeHigh = o.mm_move_range ? '$' + o.mm_move_range[1].toFixed(2) : '--';
            mmHtml = `
                <div class="mm-move-box">
                    <div class="mm-move-header">Market Maker Expected Move</div>
                    <div class="mm-move-value">&plusmn;${movePct}% ($${moveDollar})</div>
                    <div class="mm-move-range">Range: ${rangeLow} — ${rangeHigh}</div>
                </div>
            `;
        }

        el.innerHTML = `
            ${mmHtml}
            <div class="analyze-stats-grid">
                ${_statRow('Nearest Expiry', o.nearest_expiry || '--')}
                ${_statRow('IV', o.implied_volatility ? (o.implied_volatility * 100).toFixed(1) + '%' : '--')}
                ${_statRow('ATM Call', o.nearest_call_strike ? '$' + o.nearest_call_strike.toFixed(2) : '--')}
                ${_statRow('Call Price', o.nearest_call_price ? '$' + o.nearest_call_price.toFixed(2) : '--')}
                ${_statRow('ATM Put', o.nearest_put_strike ? '$' + o.nearest_put_strike.toFixed(2) : '--')}
                ${_statRow('Put Price', o.nearest_put_price ? '$' + o.nearest_put_price.toFixed(2) : '--')}
                <div class="stat-row" id="popCallRow" style="display:none"><span class="stat-label">Call PoP</span><span class="stat-value" id="popCallValue">--</span></div>
                <div class="stat-row" id="popPutRow" style="display:none"><span class="stat-label">Put PoP</span><span class="stat-value" id="popPutValue">--</span></div>
            </div>
        `;

        // Pro-gated: Load Probability of Profit asynchronously
        if (currentTicker && Premium.canAccess('probability_of_profit')) {
            _loadPoP(currentTicker);
        }
    }

    // ── Load Probability of Profit (Pro feature) ────────────────────────
    async function _loadPoP(ticker) {
        try {
            const resp = await apiRequest(`/api/analyze/${ticker}/pop`);
            if (!resp.ok) return;
            const pop = await resp.json();
            if (!pop || !pop.available) return;

            const callRow = document.getElementById('popCallRow');
            const putRow = document.getElementById('popPutRow');
            const callVal = document.getElementById('popCallValue');
            const putVal = document.getElementById('popPutValue');
            if (!callRow || !putRow) return;

            if (pop.atm_call_pop != null) {
                const pct = (pop.atm_call_pop * 100).toFixed(1);
                callVal.innerHTML = _popBadge(pct);
                callRow.style.display = '';
            }
            if (pop.atm_put_pop != null) {
                const pct = (pop.atm_put_pop * 100).toFixed(1);
                putVal.innerHTML = _popBadge(pct);
                putRow.style.display = '';
            }

            // Record trial if applicable
            const access = Premium.checkAccess('probability_of_profit');
            if (access.isTrial) {
                Premium.recordTrial('probability_of_profit');
            }
        } catch (e) {
            // Silently fail — PoP is supplemental
        }
    }

    function _popBadge(pctStr) {
        const pct = parseFloat(pctStr);
        let cls = 'pop-red';
        if (pct >= 60) cls = 'pop-green';
        else if (pct >= 40) cls = 'pop-yellow';
        return `<span class="pop-badge ${cls}">${pctStr}% PoP</span>`;
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
    // ── Render: News ───────────────────────────────────────────────────
    function renderNews(news, sentiment) {
        const el = document.getElementById('analyzeNews');
        if (!el) return;

        if (!news || news.length === 0) {
            el.innerHTML = '<p class="muted">No recent news available.</p>';
            return;
        }

        // Build sentiment lookup by title
        const sentMap = {};
        if (sentiment && sentiment.headlines) {
            sentiment.headlines.forEach(h => { sentMap[h.title] = h; });
        }

        const canSeeSentiment = Premium.canAccess('news_sentiment');

        // Overall sentiment summary (Pro-gated)
        let summaryHtml = '';
        if (canSeeSentiment && sentiment && sentiment.overall) {
            const o = sentiment.overall;
            const total = o.bullish_count + o.bearish_count + o.neutral_count;

            if (total > 0) {
                const bullPct = Math.round(o.bullish_count / total * 100);
                const neutPct = Math.round(o.neutral_count / total * 100);
                const bearPct = 100 - bullPct - neutPct;
                const labelClass = o.label === 'Bullish' ? 'sentiment-bullish'
                    : o.label === 'Bearish' ? 'sentiment-bearish'
                    : 'sentiment-neutral';

                summaryHtml = `
                    <div class="news-sentiment-summary">
                        <div class="news-sentiment-header">
                            <span>News Sentiment: <strong class="${labelClass}">${o.label}</strong>
                            (${o.bullish_count}/${total} positive)</span>
                            <span class="pro-badge-sm">PRO</span>
                        </div>
                        <div class="sentiment-bar">
                            <div class="sentiment-bar-bull" style="width:${bullPct}%"></div>
                            <div class="sentiment-bar-neut" style="width:${neutPct}%"></div>
                            <div class="sentiment-bar-bear" style="width:${bearPct}%"></div>
                        </div>
                        <div class="sentiment-bar-labels">
                            <span class="sentiment-bullish">${o.bullish_count} Bullish</span>
                            <span class="sentiment-neutral">${o.neutral_count} Neutral</span>
                            <span class="sentiment-bearish">${o.bearish_count} Bearish</span>
                        </div>
                    </div>`;
            }
        }

        const newsHtml = news.map(item => {
            const thumb = item.thumbnail
                ? `<img class="news-thumb" src="${item.thumbnail}" alt="" loading="lazy">`
                : '';
            const time = item.published
                ? _timeAgo(item.published)
                : '';

            // Sentiment badge (Pro-gated)
            let badge = '';
            if (canSeeSentiment) {
                const s = sentMap[item.title];
                if (s) {
                    const cls = s.sentiment_label === 'Bullish' ? 'sentiment-badge-bull'
                        : s.sentiment_label === 'Bearish' ? 'sentiment-badge-bear'
                        : 'sentiment-badge-neut';
                    badge = ` <span class="sentiment-badge ${cls}">${s.sentiment_label}</span>`;
                }
            }

            return `<a class="news-item" href="${item.link}" target="_blank" rel="noopener">
                ${thumb}
                <div class="news-item-body">
                    <div class="news-item-title">${item.title}${badge}</div>
                    <div class="news-item-meta">
                        <span class="news-item-publisher">${item.publisher}</span>
                        ${time ? `<span class="news-item-time">${time}</span>` : ''}
                    </div>
                </div>
            </a>`;
        }).join('');

        el.innerHTML = summaryHtml + newsHtml;
    }

    function _timeAgo(unixTs) {
        const now = Date.now() / 1000;
        const diff = now - unixTs;
        if (diff < 3600) return Math.floor(diff / 60) + 'm ago';
        if (diff < 86400) return Math.floor(diff / 3600) + 'h ago';
        return Math.floor(diff / 86400) + 'd ago';
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

    // ── Chart Pro Banner Helper ────────────────────────────────────────
    function _showChartProBanner(message) {
        const container = document.getElementById('analyzeChartContainer');
        if (!container) return;
        // Remove any existing banner
        const existing = container.parentElement.querySelector('.chart-pro-banner');
        if (existing) existing.remove();
        const banner = document.createElement('div');
        banner.className = 'chart-pro-banner';
        banner.innerHTML = message;
        container.parentElement.insertBefore(banner, container.nextSibling);
    }

    // ── Chart (Lightweight Charts) ─────────────────────────────────────
    async function loadChart(ticker, period, interval) {
        currentChartPeriod = period;
        currentChartInterval = interval;

        try {
            // Fetch chart data first (critical), trendlines + patterns as best-effort
            const chartResp = await apiRequest(`/api/analyze/${ticker}/chart?period=${period}&interval=${interval}`);
            if (!chartResp.ok) throw new Error(`Chart API error: ${chartResp.status}`);
            const chartData = await chartResp.json();

            if (!chartData || !chartData.data || chartData.data.length === 0) return;

            // Fetch trendlines + patterns in background (non-blocking)
            let trendData = null;
            let patternData = null;
            try {
                const extras = await Promise.all([
                    apiRequest(`/api/analyze/${ticker}/trendlines?period=${period}&interval=${interval}`)
                        .then(r => r.json()).catch(() => null),
                    document.getElementById('togglePatterns')?.checked
                        ? apiRequest(`/api/analyze/${ticker}/patterns?period=${period}`)
                            .then(r => r.json()).catch(() => null)
                        : Promise.resolve(null),
                ]);
                trendData = extras[0];
                patternData = extras[1];
            } catch (e) { /* non-critical */ }

            // Always destroy and recreate — time format changes between daily/intraday
            AlphaCharts.destroy('analyzeChartContainer');
            AlphaCharts.create('analyzeChartContainer', { height: 400, volumeHeight: 60 });

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

            // Add trendlines if enabled (Pro feature)
            if (document.getElementById('toggleTrendlines')?.checked && trendData) {
                const tlAccess = Premium.checkAccess('trendlines');
                if (tlAccess.allowed) {
                    AlphaCharts.setTrendlines('analyzeChartContainer', trendData);
                    if (tlAccess.isTrial) {
                        Premium.recordTrial('trendlines');
                        _showChartProBanner('Free trial of <strong>Auto-Detected Trendlines</strong>. Upgrade to Pro for permanent access.');
                    }
                } else {
                    _showChartProBanner('🔒 <strong>Auto-Detected Trendlines</strong> is a Pro feature. <button class="btn btn-primary btn-xs pro-locked-btn">Upgrade to Pro — $99/mo</button>');
                }
            }

            // Add candlestick pattern markers if enabled (Pro feature)
            if (document.getElementById('togglePatterns')?.checked && patternData) {
                const pAccess = Premium.checkAccess('candlestick_patterns');
                if (pAccess.allowed) {
                    AlphaCharts.setPatterns('analyzeChartContainer', patternData);
                    if (pAccess.isTrial) Premium.recordTrial('candlestick_patterns');

                    // Seasonality (Pro feature)
                    if (patternData.seasonality) {
                        const sAccess = Premium.checkAccess('seasonality');
                        if (sAccess.allowed) {
                            AlphaCharts.renderSeasonality('analyzeChartContainer', patternData.seasonality);
                            if (sAccess.isTrial) {
                                Premium.recordTrial('seasonality');
                            }
                        } else {
                            const seasEl = document.getElementById('seasonalityContainer');
                            if (seasEl) {
                                seasEl.style.display = 'block';
                                seasEl.innerHTML = '<div class="pro-locked"><div class="pro-locked-title">Seasonality Heatmap</div><div class="pro-locked-desc">5-year monthly return analysis. Upgrade to Pro for access.</div><button class="btn btn-primary btn-sm pro-locked-btn">Upgrade to Pro — $99/mo</button></div>';
                            }
                        }
                    }
                } else {
                    _showChartProBanner('🔒 <strong>Candlestick Patterns</strong> is a Pro feature. <button class="btn btn-primary btn-xs pro-locked-btn">Upgrade to Pro — $99/mo</button>');
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

            // Initialize drawing tools
            AlphaCharts.initDrawings('analyzeChartContainer', ticker);

            // Re-apply indicator pane toggles if they were on
            if (document.getElementById('toggleVWAP')?.checked) {
                AlphaCharts.toggleIndicator('analyzeChartContainer', 'vwap');
            }
            if (document.getElementById('toggleRSI')?.checked) {
                AlphaCharts.toggleIndicator('analyzeChartContainer', 'rsi');
            }
            if (document.getElementById('toggleMACD')?.checked) {
                AlphaCharts.toggleIndicator('analyzeChartContainer', 'macd');
            }
            if (document.getElementById('toggleStoch')?.checked) {
                AlphaCharts.toggleIndicator('analyzeChartContainer', 'stochastic');
            }

        } catch (e) {
            console.error('Chart load failed:', e);
        }
    }

    async function loadCompare(ticker, period) {
        try {
            const resp = await apiRequest(`/api/analyze/${ticker}/compare?period=${period}`);
            if (!resp.ok) throw new Error(`Compare API error: ${resp.status}`);
            const data = await resp.json();
            if (data?.symbols) {
                AlphaCharts.setCompare('analyzeChartContainer', data);
            }
        } catch (e) {
            console.error('Compare load failed:', e);
        }
    }

    // ── Quant Grades ─────────────────────────────────────────────────────
    async function loadGrades(ticker) {
        const el = document.getElementById('analyzeGrades');
        if (!el) return;
        el.innerHTML = '<p class="muted">Loading grades...</p>';

        try {
            const resp = await apiRequest(`/api/analyze/${ticker}/grades`);
            if (!resp.ok) throw new Error(`Grades API error: ${resp.status}`);
            const grades = await resp.json();
            if (grades.error) {
                el.innerHTML = `<p class="muted">${grades.error}</p>`;
                return;
            }
            renderGrades(grades);
            renderGradesGuide(grades);
            appendGradesToBrief(grades);
            const gradeAccess = Premium.checkAccess('quant_grades');
            if (gradeAccess.isTrial) {
                Premium.recordTrial('quant_grades');
                Premium.showTrialBanner('analyzeGrades', 'quant_grades');
            }
        } catch (e) {
            el.innerHTML = '<p class="muted">Grades unavailable</p>';
        }
    }

    function renderGrades(g) {
        const el = document.getElementById('analyzeGrades');
        if (!el) return;

        const factors = g.factors || {};
        const factorOrder = ['value', 'growth', 'profitability', 'momentum', 'revisions', 'ai_score'];

        // Overall grade badge
        const overallCls = _gradeClass(g.overall_grade);
        let html = `
            <div class="grades-overall">
                <div class="grades-overall-badge ${overallCls}">${g.overall_grade}</div>
                <div class="grades-overall-info">
                    <span class="grades-overall-label">Overall Quant Score</span>
                    <span class="grades-overall-sector">${g.sector || ''}</span>
                    ${g.peer_rank ? `<span class="grades-overall-rank">#${g.peer_rank.rank} of ${g.peer_rank.total} peers (top ${g.peer_rank.percentile}%)</span>` : ''}
                </div>
            </div>
        `;

        // Factor bars
        html += '<div class="grades-factors">';
        for (const key of factorOrder) {
            const f = factors[key];
            if (!f) continue;
            const cls = _gradeClass(f.grade);
            const exclusive = f.exclusive ? ' <span class="grades-exclusive">AI</span>' : '';
            html += `
                <div class="grades-factor-row">
                    <span class="grades-factor-name">${f.factor}${exclusive}</span>
                    <div class="grades-factor-bar">
                        <div class="grades-factor-fill ${cls}" style="width:${Math.min(100, f.score)}%"></div>
                    </div>
                    <span class="grades-factor-grade ${cls}">${f.grade}</span>
                </div>
            `;
        }
        html += '</div>';

        // Peer ranking mini table
        if (g.peer_rank?.peers?.length > 0) {
            html += '<div class="grades-peers">';
            html += '<div class="grades-peers-title">Sector Ranking</div>';
            for (const p of g.peer_rank.peers) {
                const isCurrent = p.ticker === g.ticker;
                html += `<div class="grades-peer-row ${isCurrent ? 'current' : ''}">
                    <span class="grades-peer-ticker">${p.ticker}</span>
                    <div class="grades-peer-bar-bg"><div class="grades-peer-bar-fill" style="width:${Math.min(100, p.score)}%"></div></div>
                    <span class="grades-peer-score">${p.score}</span>
                </div>`;
            }
            html += '</div>';
        }

        el.innerHTML = html;
    }

    function renderGradesGuide(g) {
        const el = document.getElementById('gradesGuide');
        if (!el) return;
        const f = g.factors || {};

        let html = '<div class="guide-content">';
        html += '<p><strong>Quant Grades</strong> score this stock across 6 factors vs sector peers. Each factor gets A+ through F based on percentile rank.</p>';
        html += '<ul>';
        html += '<li><strong>Value</strong> — P/E, P/S, P/B, EV/EBITDA, PEG (lower = better value)</li>';
        html += '<li><strong>Growth</strong> — Revenue growth, earnings growth, forward EPS growth</li>';
        html += '<li><strong>Profitability</strong> — ROE, profit margin, operating margin, gross margin</li>';
        html += '<li><strong>Momentum</strong> — Price position in 52-week range, 3-month return</li>';
        html += '<li><strong>Revisions</strong> — Forward EPS vs trailing EPS (positive = analysts raising estimates)</li>';
        html += '<li><strong>AI Score</strong> — <em>AlphaBreak exclusive.</em> Trend break probability + regime alignment. No competitor has this.</li>';
        html += '</ul>';
        if (g.peer_rank) {
            html += `<p>Ranked <strong>#${g.peer_rank.rank} of ${g.peer_rank.total}</strong> stocks in ${g.sector} sector.</p>`;
        }
        html += '</div>';
        el.innerHTML = html;
    }

    function appendGradesToBrief(grades) {
        const el = document.getElementById('analyzeAiBriefBody');
        if (!el || !grades?.overall_grade) return;

        const p = el.querySelector('p');
        if (!p) return;

        const grade = grades.overall_grade;
        const cls = _gradeClass(grade);

        // Add grade to the brief
        let extra = ` Quant grade: <strong class="${cls}">${grade}</strong> (${grades.sector}).`;

        // Check for divergence between trend break and quant grade
        const tb = data?.trend_break;
        if (tb?.probability != null) {
            const tbHigh = tb.probability > 0.80;
            const gradeGood = grades.overall_score >= 60; // B- or better
            const gradeBad = grades.overall_score < 45; // D or worse

            if (tbHigh && gradeBad) {
                extra += ' <em style="color:var(--warning-color)">Note: High trend break probability with weak fundamentals often signals a momentum-driven move that may not sustain. Manage risk tightly.</em>';
            } else if (!tbHigh && gradeGood) {
                extra += ' <em style="color:var(--text-muted)">Strong fundamentals with low trend break probability suggests stability — look for entry on pullbacks.</em>';
            }
        }

        p.innerHTML += extra;
    }

    function _gradeClass(grade) {
        if (!grade) return '';
        const g = grade.charAt(0);
        if (g === 'A') return 'grade-a';
        if (g === 'B') return 'grade-b';
        if (g === 'C') return 'grade-c';
        if (g === 'D') return 'grade-d';
        return 'grade-f';
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
