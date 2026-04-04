// AlphaBreak — Analyze Tab
// Single-ticker deep-dive analysis

const Analyze = (() => {
    let currentTicker = null;
    let data = null;
    let priceChart = null;
    let volumeChart = null;
    let searchTimeout = null;

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

        // Check URL hash for direct ticker link
        const hash = window.location.hash;
        if (hash.startsWith('#analyze/')) {
            const ticker = hash.replace('#analyze/', '').toUpperCase();
            if (ticker) {
                input.value = ticker;
                analyzeTicker(ticker);
            }
        }
    }

    function analyzeCurrent() {
        const input = document.getElementById('analyzeTickerInput');
        const ticker = input.value.trim().toUpperCase();
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
                const results = await apiRequest(`/api/analyze/search?q=${encodeURIComponent(query)}`);
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
            data = await apiRequest(`/api/analyze/${ticker}`);
            if (!data || data.error) throw new Error(data?.error || 'No data');

            renderHeader(data.header);
            renderStats(data.stats);
            renderTrendBreak(data.trend_break, data.signals);
            renderIndicators(data.indicators, data.signals);
            renderAnalyst(data.analyst);
            renderOptions(data.options);
            renderEarnings(data.earnings);
            renderInstitutional(data.institutional);

            document.getElementById('analyzeLoading').style.display = 'none';
            document.getElementById('analyzeContent').style.display = 'block';

            // Load default chart (3M daily)
            loadChart(ticker, '3mo', '1d');
            // Reset active button
            document.querySelectorAll('#analyzeChartPeriods button').forEach(b => {
                b.classList.toggle('active', b.dataset.period === '3mo');
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
        return `<div class="ind-row"><span class="ind-name">${name}</span><span class="ind-val">${display}</span>${badge}</div>`;
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

    // ── Chart ────────────────────────────────────────────────────────────
    async function loadChart(ticker, period, interval) {
        try {
            const chartData = await apiRequest(
                `/api/analyze/${ticker}/chart?period=${period}&interval=${interval}`
            );
            if (!chartData || !chartData.data || chartData.data.length === 0) return;

            renderPriceChart(chartData);
            renderVolumeChart(chartData);
        } catch (e) {
            console.error('Chart load failed:', e);
        }
    }

    function renderPriceChart(chartData) {
        const ctx = document.getElementById('analyzeChart');
        if (!ctx) return;

        if (priceChart) priceChart.destroy();

        const labels = chartData.data.map(d => d.timestamp);
        const ohlc = chartData.data.map(d => ({
            x: d.timestamp,
            o: d.open,
            h: d.high,
            l: d.low,
            c: d.close,
        }));

        // Use line chart if candlestick plugin not available
        const closes = chartData.data.map(d => d.close);
        const isPositive = closes[closes.length - 1] >= closes[0];

        priceChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels,
                datasets: [{
                    data: closes,
                    borderColor: isPositive ? 'rgba(38, 166, 154, 1)' : 'rgba(239, 83, 80, 1)',
                    backgroundColor: isPositive
                        ? 'rgba(38, 166, 154, 0.08)'
                        : 'rgba(239, 83, 80, 0.08)',
                    fill: true,
                    tension: 0.1,
                    pointRadius: 0,
                    borderWidth: 1.5,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { intersect: false, mode: 'index' },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: ctx => `$${ctx.raw.toFixed(2)}`,
                        },
                    },
                },
                scales: {
                    x: {
                        display: true,
                        grid: { color: 'rgba(42, 46, 57, 0.5)' },
                        ticks: {
                            color: '#5c6578',
                            maxTicksLimit: 8,
                            maxRotation: 0,
                            callback: function(val) {
                                const label = this.getLabelForValue(val);
                                return label ? label.split('T')[0] : '';
                            },
                        },
                    },
                    y: {
                        display: true,
                        position: 'right',
                        grid: { color: 'rgba(42, 46, 57, 0.5)' },
                        ticks: {
                            color: '#5c6578',
                            callback: v => '$' + v.toFixed(2),
                        },
                    },
                },
            },
        });
    }

    function renderVolumeChart(chartData) {
        const ctx = document.getElementById('analyzeVolume');
        if (!ctx) return;

        if (volumeChart) volumeChart.destroy();

        const labels = chartData.data.map(d => d.timestamp);
        const volumes = chartData.data.map(d => d.volume);
        const colors = chartData.data.map((d, i) => {
            if (i === 0) return 'rgba(92, 101, 120, 0.5)';
            return d.close >= chartData.data[i - 1].close
                ? 'rgba(38, 166, 154, 0.4)'
                : 'rgba(239, 83, 80, 0.4)';
        });

        volumeChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels,
                datasets: [{
                    data: volumes,
                    backgroundColor: colors,
                    borderWidth: 0,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false }, tooltip: { enabled: false } },
                scales: {
                    x: { display: false },
                    y: {
                        display: false,
                        beginAtZero: true,
                    },
                },
            },
        });
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
