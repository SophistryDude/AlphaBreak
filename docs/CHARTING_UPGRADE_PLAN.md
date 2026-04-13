# Charting Upgrade Plan — 2 Weeks

**Drafted**: 2026-04-13
**Owner**: TBD
**Goal**: Close the "looks amateur next to TradingView" gap without chasing feature parity we can't win.

---

## Strategic premise

AlphaBreak's moat is the AI / regime / trend-break layer rendered *on top* of a competent chart — not the chart itself. Chasing TradingView on pure charting is a losing bet (100+ indicators, Pine Script, a decade of UX polish). Instead: make the chart "good enough for 90% of traders" so nobody bounces on first impression, then spend the saved calories on the AI story.

**Current baseline** — already in the repo:
- `frontend/charts.js` (1,247 lines) — TradingView `lightweight-charts` wrapper, candles + volume + SMA/BB overlays + auto trendlines + regime indicator + crosshair OHLCV tooltip
- `frontend/chart-indicators.js` (445 lines) — client-side RSI / MACD / Stochastic / VWAP sub-panes
- `frontend/chart-drawings.js` (521 lines) — canvas overlay, 4 tools (trendline, h-line, fib, rectangle), per-ticker localStorage persistence

**What we're missing vs. competitors** (see `docs/COMPETITIVE_ANALYSIS.md`):

| Gap | Competitor benchmark |
|---|---|
| Indicator library depth | TradingView ~100, thinkorswim ~400; we have ~6 |
| Full drawing toolset | TradingView / TOS 50+; we have 4 |
| Multi-timeframe synced charts | TrendSpider, TradingView |
| Volume / market profile | TradingView, TrendSpider |
| Saved layouts / workspaces | TradingView, TOS |
| Replay / bar replay | TradingView |

---

## Data gap (and how we fix it)

**There is no feature telemetry in the app today.** Portfolio analytics exist in `flask_app/app/utils/analytics.py`, but nothing tracks "user opened RSI" or "user drew a trendline." That means every charting decision right now is a guess.

**Fix**: ship a minimal event logger as step 0 so week-2 decisions are data-informed.

---

## Day 0–1 — Instrumentation (ship before anything else)

**Tasks**
- New table `feature_events (id, user_id, event_name, props_json, created_at)`
- New route `POST /api/events` — rate-limited, auth-optional
- Tiny frontend helper `Telemetry.track(event, props)` imported from `app.js`
- Wire events in `charts.js` / `chart-indicators.js` / `chart-drawings.js`:
  - `chart_loaded` — ticker, period, interval
  - `chart_period_changed` — from → to
  - `indicator_toggled` — name, state
  - `drawing_tool_used` — tool, action (create/delete)
  - `overlay_toggled` — trendlines / SMA / BB / patterns
  - `multi_chart_opened` — count
- Admin query: `SELECT event_name, COUNT(*) FROM feature_events WHERE created_at > now() - interval '7 days' GROUP BY 1 ORDER BY 2 DESC LIMIT 20;`

**Why first**: 5 days of production data before we commit week-2 features.

**Effort**: 1 day.

---

## External usage research — validating the build path

Internal telemetry takes 5+ days to be useful. In parallel, we scrape the public internet for what features traders *actually* reach for on other platforms, so week-1 picks are grounded in evidence instead of intuition.

### Methodology (repeat this quarterly)

1. **TradingView Community Scripts** — <https://www.tradingview.com/scripts/>
   Sort by "Top" (Boost-ranked). Pull the first 3 pages and tally which base indicators the top community scripts extend. TradingView exposes a Boost count per script — that's the closest thing to a public popularity number for any charting platform.

2. **TradingView per-indicator script pages** — e.g. `/scripts/vwap/`, `/scripts/volumeprofile/`, `/scripts/ichimoku/`
   Boost totals on these category pages are a direct usage proxy for that indicator.

3. **"Best TradingView indicators 2026" roundups** — journalistic aggregation, triangulate 5+ sources to filter out SEO spam. Useful because writers usually cite TradingView's own usage stats.

4. **Reddit trading subs** — r/Daytrading, r/options, r/algotrading, r/TradingView.
   Use the site search `site:reddit.com/r/Daytrading "indicators I use"` or the Reddit JSON API. Tally indicator mentions in high-karma comments from the last 6 months.

5. **YouTube "top X indicators" videos** — sort by views in the last year. Channels like Rayner Teo, The Moving Average, Trading Heroes. Top-10 lists are highly correlated across creators.

6. **GitHub Pine Script repos** — <https://github.com/topics/pine-script>. Stars per repo signal which community scripts have legs beyond TradingView's own ranking.

7. **Our own search logs** (when we have them) — once telemetry is live, log what users type into any "add indicator" search box. Nothing beats direct user intent.

Keep the tally in a spreadsheet under `docs/research/charting-popularity-YYYY-QN.md`. Re-run quarterly so the build path stays honest.

### Findings — April 2026 pass

Web search across QuantifiedStrategies, Dhan, PipTrend, TradeNation, LiberatedStockTrader, Trader-Dale, Schwab, Zeiierman, and TradingView's own script-category pages. Rankings below combine frequency of mention with a tradingView Boost sanity-check.

**Tier 1 — universal (cited in every single source)**
- Moving Averages (SMA / EMA) — **we have**
- RSI — **we have (sub-pane)**
- MACD — **we have**
- Bollinger Bands — **we have**
- VWAP — **we have**
- **Volume Profile / VPVR** — missing. Described as "the single most important indicator for day traders" and "essential" across multiple sources. **Highest-priority gap.**
- **Supertrend** — missing. Appears in every 2026 top-indicators list we found. Combines volatility and trend in one line.

**Tier 2 — widely used, frequently cited**
- Ichimoku Cloud — missing (already in our plan ✓)
- ADX + DI± — missing (already in our plan ✓)
- ATR — missing (already in our plan ✓)
- Stochastic — **we have**
- Fibonacci retracement — **we have (drawing tool)**

**Tier 3 — niche but cited**
- Keltner Channels — volatility bands alternative to BB
- OBV — volume confirmation (pairs with our dark pool story)
- Parabolic SAR
- Pivot Points

**Popular community Pine scripts (not in any platform's "built-in" list, but huge Boost counts)**
- Squeeze Momentum Indicator (LazyBear) — Bollinger + Keltner squeeze detection
- WaveTrend Oscillator
- QQE Mod — RSI + smoothed MAs
- LuxAlgo-style blended buy/sell signal systems

**What we were about to build but shouldn't (based on this data)**
- **CMF (20)** — rarely top-of-list. *Cut from week 1.*
- **Williams %R** — niche, almost never mentioned. *Cut from week 1.*

**What we were not planning but should add**
- **Volume Profile (VPVR)** — promoted from week-2 optional to **week-1 must-have**. This is the single biggest indicator gap in our build path.
- **Supertrend** — added to week-1. Zero-cost calc, visible-on-chart overlay, huge popularity.

### Drawing tools — major finding

Our plan was to hand-code 5 new drawing tools over 2 days. Research surfaced an open-source library worth spiking on first:

- **`deepentropy/lightweight-charts-drawing`** (GitHub) — 68 drawing tools for `lightweight-charts` v5: trendlines, Fibonacci (all variants), Gann, channels, pitchforks, shapes, annotations, forecasting tools.

**Recommendation**: Day 2 of week 1, spend 2 hours evaluating the library (license, code quality, bundle size, v5 compatibility since we may still be on v4). If it clears, we get 68 tools for the effort of integrating + themeing one — an order-of-magnitude leverage win. If it doesn't clear, fall back to the hand-coded list below.

### Sources

- [QuantifiedStrategies — 100 Best Trading Indicators 2026](https://www.quantifiedstrategies.com/trading-indicators/)
- [Dhan — Top 20 Trading Indicators 2026](https://dhan.co/blog/technical-analysis/top-20-trading-indicators/)
- [PipTrend — Best Indicators for Trading 2026](https://piptrend.com/best-indicators-for-trading/)
- [TradeNation — 14 Most Used TradingView Indicators](https://tradenation.com/articles/tradingview-indicators/)
- [LiberatedStockTrader — I Tested 103 Free TradingView Indicators](https://www.liberatedstocktrader.com/best-tradingview-indicators/)
- [Trader-Dale — Anchored VWAP + Volume Profile](https://www.trader-dale.com/day-trading-with-anchored-vwap-and-volume-profile-17th-jul-2024/)
- [Schwab — How to Use Volume-Weighted Indicators](https://www.schwab.com/learn/story/how-to-use-volume-weighted-indicators-trading)
- [Zeiierman — Most Accurate Trading Indicator 2026](https://www.zeiierman.com/blog/the-most-accurate-trading-indicator)
- [TradingView — VWAP Scripts](https://www.tradingview.com/scripts/vwap/)
- [TradingView — Volume Profile Scripts](https://www.tradingview.com/scripts/volumeprofile/)
- [TradingView — Drawing Tools Reference](https://www.tradingview.com/support/solutions/43000703396-drawing-tools-available-on-tradingview/)
- [deepentropy/lightweight-charts-drawing (GitHub)](https://github.com/deepentropy/lightweight-charts-drawing)

---

## Week 1 — Indicator depth (revised per research)

Goal: take ChartIndicators from 4 built-in indicators to **11**. All client-side from OHLCV (no new API work). Order reflects research-backed priority.

| # | Indicator | Pane | Value prop | Priority | Effort |
|---|---|---|---|---|---|
| 1 | **Volume Profile (VPVR)** | Main overlay (right-side histogram) | Tier-1 gap per research; "essential" for day traders; TrendSpider differentiator | ⭐ Must | 4 hr |
| 2 | **Supertrend** | Main overlay | Tier-1 gap; appears in every 2026 top-indicators list | ⭐ Must | 45 min |
| 3 | **ADX + DI±** | Sub-pane | Trend strength; plugs into regime story | Must | 45 min |
| 4 | **ATR** | Sub-pane | Feeds stop-loss widget naturally; underpins Supertrend calc | Must | 30 min |
| 5 | **Ichimoku Cloud** | Main overlay | Visually distinctive; Tier-2 cited | Must | 90 min |
| 6 | **Keltner Channels** | Main overlay | Volatility bands; unlocks Squeeze-style setups later | Should | 40 min |
| 7 | **OBV** | Sub-pane | Volume confirmation; pairs with dark pool story | Should | 30 min |

**Cut from the original plan** (research showed low usage): CMF (20), Williams %R. Re-add only if telemetry post-launch surfaces demand.

**Deliverables per indicator**: calc function, sub-pane render (or overlay series), settings UI toggle, `localStorage` persistence, telemetry event.

**Effort**: 3–4 days.

### Week 1 parallel track — Drawing tools (revised strategy)

**Day 2 spike — RESULT: do not adopt** (2026-04-13, ~10 min)

Evaluated `deepentropy/lightweight-charts-drawing`:

| Check | Result |
|---|---|
| License | MIT ✓ |
| Required `lightweight-charts` version | **v5** ✗ — we're on v4.1.3 (`index.html:16`) |
| Tool count | 68 (verified — full list in fetched README) |
| Maintenance | 13 stars, 7 forks, 0 issues, last commit 2026-02-26, single maintainer |
| Version | v0.1.1 (pre-1.0 alpha) |
| Integration | npm `DrawingManager` class — we currently use script-tag CDN |
| Modifies chart | No (overlay/plugin pattern) |

**Two blockers**:
1. **v5 dependency** — adopting this means migrating `lightweight-charts` v4 → v5 first. v5 introduces a new series creation API and renamed options; the migration touches every `addCandlestickSeries`/`addLineSeries`/`addHistogramSeries` call across `charts.js`, `chart-indicators.js`, and `chart-volume-profile.js`. Rough estimate: 4–6 hours of careful work plus regression testing across all chart features (trendlines, multi-chart, fullscreen, indicators, volume profile, drawings).
2. **Maturity risk** — 13 stars, single maintainer, v0.1.1 alpha. Acceptable for prototypes, not for production charting that users see daily.

**Decision**: skip the library. Fall back to the hand-coded list. **Revisit in 6 months** if (a) we've already migrated to lightweight-charts v5 for unrelated reasons, and (b) the library has matured to v1.x with broader adoption.

**Hand-coded drawing tools fallback list:**

| # | Tool | Value prop | Effort |
|---|---|---|---|
| 1 | **Parallel channel** | 2 anchors + width — most-requested missing tool | 3 hr |
| 2 | **Measure tool** | Distance & % between two points — highest daily utility | 2 hr |
| 3 | **Arrow / text annotation** | Journal integration hook later | 2 hr |
| 4 | **Clone + delete-all** UX | Currently missing, painful without it | 1 hr |
| 5 | **Snap-to-price** (hold shift) | Polish, looks pro | 1 hr |

**Effort**: 2 days either branch.

---

## Week 2 — Workflow features

By this point we have ~5 days of internal telemetry *and* the external research above. Pick the **top 2** of the following based on what the combined data says is hurting us most:

1. **Saved chart layouts** — localStorage first, server-sync later. Power users keep indicator stacks per ticker.
2. **Multi-timeframe synced crosshair** — multi-chart already exists; just wire shared crosshair. ~1 day.
3. **Quick indicator presets** — "Momentum stack", "Mean-reversion stack", "Breakout stack", "VWAP + Volume Profile day-trader stack" (this last one is high-signal per research). 2 hours each, huge beginner UX win. Pairs with the education blog strategy.
4. **Squeeze Momentum indicator** — community Pine script favorite; we already have the BB + Keltner pieces after week 1, so this is mostly a visualization layer on top. Differentiates from stock indicator libraries.

Note: Volume Profile was promoted out of this list into week 1 based on research.

**Effort**: 3–4 days for the chosen two.

### Week 2 polish

- Settings modal for indicator parameters (currently hardcoded periods)
- "What does this indicator mean?" tooltip overlay — ties into the SEO education content
- Export chart as PNG (one-liner with `lightweight-charts`)

**Effort**: 1 day.

---

## Explicitly NOT doing

These are competitor-only features we're deliberately skipping:

- **Pine Script clone** — months of work, trivially out-TradingViewed, no moat
- **Bar replay mode** — nice but niche; revisit if usage data shows demand
- **TradingView widget embed** — kills our AI overlay story, licensing cliff above a few thousand users
- **Raindrop / market profile charts** — TrendSpider's moat, not ours
- **50+ drawing tools** — diminishing returns past ~10 well-chosen tools

---

## Success criteria

At end of week 2:
- [ ] `feature_events` table live with >10k events/week
- [ ] `ChartIndicators` supports 11+ indicators (up from 4), including Volume Profile and Supertrend
- [ ] `ChartDrawings` supports 9+ tools (up from 4) — or 60+ if the `lightweight-charts-drawing` spike succeeds
- [ ] At least 2 week-2 workflow features shipped, chosen by telemetry + external research
- [ ] Indicator settings persist across sessions
- [ ] No "TradingView embed" in the codebase
- [ ] Chart load time unchanged (<500ms TTI)
- [ ] `docs/research/charting-popularity-2026-Q2.md` checked in with the raw tally from the external research pass

## Tradeoff to flag

Week-1 indicator expansion is the safest bet — mechanical, low-risk, visibly closes the feature-matrix gap that reviewers fixate on. But week-2 workflow features are where users actually feel the difference day-to-day. **If telemetry shows chart-time is already high, cut half of week 1 and double down on week 2.** The data earns that right.

---

## Related docs

- `docs/COMPETITIVE_ANALYSIS.md` — full competitor feature matrix
- `docs/ROADMAP.md` — broader product roadmap
- `frontend/charts.js`, `chart-indicators.js`, `chart-drawings.js` — current implementation
