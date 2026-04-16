# Product Roadmap

**Version**: 4.6
**Last Updated**: April 15, 2026
**Domain**: alphabreak.vip

---

## Table of Contents

1. [Vision](#vision)
2. [Features — Free Tier](#features--free-tier)
3. [Features — Pro Tier ($99/mo)](#features--pro-tier-99mo)
4. [Features — Elite Tier ($299/mo)](#features--elite-tier-299mo)
5. [Features — API Tier ($499–999/mo)](#features--api-tier-499999mo)
6. [Features — Future (Unscheduled)](#features--future-unscheduled)
7. [Customer Acquisition](#customer-acquisition)
8. [Infrastructure](#infrastructure)
9. [Recently Completed](#recently-completed)

---

## Vision

Build the single-security analysis platform that bridges the charting/TA world and the fundamental/data world — something no competitor does today. Deliver Bloomberg-grade depth at 1/80th the price, with AI-powered scoring and an integrated trade journal that no one else offers.

**The market is bifurcated.** You either get great charting (TradingView, thinkorswim) OR great fundamentals (Seeking Alpha, Koyfin). Nobody does both. Nobody integrates options analytics with both. Nobody has AI scoring + journaling + analysis in one workflow.

AlphaBreak bridges both sides and adds what nobody has: AI trade scoring, regime-aware analysis, trade thesis → execute → review in one platform.

**Scale target**: Architecture every feature for hundreds of thousands of concurrent users, millions of daily requests.

---

## Features — Free Tier

The free tier drives user acquisition. It must be good enough that traders switch from their current tools and tell others.

### Market Analysis — ✅ Complete
- [x] Sentiment analysis (8-indicator composite, 4 timeframes)
- [x] Sector sentiment (11 GICS sectors)
- [x] VIX & index sentiment (SPY, QQQ, DIA, Russell 2000)
- [x] Commodities & crypto widget (Gold, Silver, BTC, ETH)
- [x] Trend break reports (daily, hourly, 10-min, 80%+ probability)
- [x] All widgets collapsible with persistent state

### Security Analysis (Single-Ticker Deep Dive) — ✅ Complete
*Formerly "Intra-Day Trading Watchlist". Now the landing page.*

- [x] Ticker search bar with auto-complete (100+ tickers)
- [x] Company overview (name, sector, industry, exchange)
- [x] Price, change, 52-week range bar
- [x] Key stats grid (22 metrics: P/E, EPS, market cap, ROE, margins, etc.)
- [x] Analyst consensus & price targets (buy/hold/sell, mean/high/low)
- [x] Earnings (next date + last 4 quarters beat/miss)
- [x] Options summary (IV, ATM call/put, nearest expiry)
- [x] Institutional ownership + 13F holdings
- [x] Auto-loads top trend break ticker on page load (fallback: AAPL)
- [x] Ticker news feed (yfinance stock.news — top 10 headlines with thumbnails)

### Charting — ✅ Phase 1 Complete
- [x] TradingView Lightweight Charts (WebGL, 50K+ candles at 60fps)
- [x] Japanese candlestick + volume histogram
- [x] SMA 10 + SMA 50 overlays
- [x] Bollinger Bands overlay
- [x] 7 timeframe buttons (1D, 5D, 1M, 3M, 6M, 1Y, 5Y)
- [x] Toggle checkboxes: Trendlines / SMA / BB / Compare / Patterns
- [x] Full-screen mode
- [x] Auto-detected trendlines with confidence scoring (0-100%)
- [x] Market regime classification (BULL/BEAR/RANGE/HIGH_VOL) with badge
- [x] Historical analog matching (cosine similarity, agreement %)
- [x] Trendline projection (5/10/20 bars forward)
- [x] Horizontal support/resistance levels from pivot clustering
- [x] Candlestick pattern recognition (Doji, Hammer, Shooting Star, Engulfing, Morning/Evening Star, Three White Soldiers/Black Crows) with probability %
- [x] Seasonality heatmap (5yr monthly avg return + win rate)
- [x] Symbol comparison overlay (SPY, VIX, sector ETF — normalized %)
- [x] Trendline info panel with confidence + analog scores
- [x] Pattern markers on chart (arrows with pattern name + probability)
- [x] Charts deployed across: Security Analysis, Earnings detail, Reports detail, Long Term Trading

### AI Dashboard — ✅ Complete
- [x] Dedicated AI Dashboard tab (2nd in sidebar)
- [x] Market regime hero (SPY-based BULL/BEAR/RANGE/HIGH_VOL with confidence + strategy description)
- [x] Model performance stats (854K trades backtested, win rate, avg return, signals today, 30-day accuracy)
- [x] Top AI signals list (highest-conviction trend breaks, clickable to Security Analysis)
- [x] Sector regime map (11 sectors independently classified)
- [x] Signal history table (7 days of predictions vs outcomes — correct/wrong/pending)
- [x] AI Screener (enter any ticker for instant quant grades scorecard)

### Quant Letter Grades — ✅ Complete
- [x] 6-factor scoring: Value, Growth, Profitability, Momentum, Revisions, AI Score (exclusive)
- [x] A+ through F grades based on percentile rank vs 8 sector peers
- [x] Overall grade with weighted composite
- [x] Sector peer ranking with mini bar chart
- [x] AI Score factor: trend break probability + regime alignment (no competitor has this)
- [x] Grade/trend-break divergence note in AI Brief

### AI & Educational Content — ✅ Complete
- [x] AI Analysis Brief — plain-English synthesis of price, trend break, technicals, analyst consensus, earnings, IV, institutional ownership
- [x] Inline tooltips on all indicator rows (contextual explanation of RSI 28.5, CCI > 100, etc.)
- [x] Expandable "?" guide panels per section (indicators, stats, analyst, options, earnings, institutional)
- [x] Educational content on Reports tab (AI brief, guide panel, probability/IV tooltips)
- [x] Educational content on Earnings tab (AI brief, guide panel, EPS tooltips)
- [x] Educational content on Options tab (AI brief, guide panel, IV/delta/recommendation tooltips)
- [x] Earnings CBOE: P/C Ratio tooltips, put/call volume flow analysis bar

### Options Analysis — ✅ Complete
- [x] Options chain with bid/ask, volume, OI, IV
- [x] Fair value calculation (Black-Scholes, Binomial Tree)
- [x] Option chain by expiration

### Portfolio & Journal — ✅ Complete
- [x] Portfolio tracker (paper trading, $100K)
- [x] Trade journal (full CRUD, notes, P&L tracking)
- [x] AI trade scoring on journal entries
- [x] Auto-import trades from portfolio
- [x] Community / shared journal (public/private toggle)
- [x] Watchlist management (server-synced, batch fetch up to 50 tickers)

### Long Term Trading — ✅ Updated
- [x] My Holdings section (above Hedge Fund, collapsible widget)
- [x] Hedge Fund Holdings with real 13F data (funds holding, sentiment, new/increased/decreased/sold, net change)
- [x] Click-to-analyze any holding row (opens detail panel)
- [x] Comparison chart: Growth of $100 (base=100, area fill, legend toggle, range selector 1M-5Y)
- [x] Daily candlestick chart (Lightweight Charts)

### Notifications — ✅ Complete
- [x] Email alerts via AWS SES (sandbox mode)
- [x] Notification preferences (moved to Account page)
- [x] 9 event types (trade signal, stop-loss, take-profit, earnings, etc.)
- [x] Per-event notification preferences
- [x] Unsubscribe-all endpoint

### UI/UX — ✅ Complete
- [x] All tabs converted to widget-card pattern with collapsible sections
- [x] Security Analysis as landing page (top of sidebar)
- [x] Header: centered page title, API status in footer
- [x] Subtitle: "AI-Driven Trend and Sentiment Analysis"
- [x] Contact link in footer
- [x] Sign out moved to Account page

### Data — ✅ Complete
- [x] Delayed data (15-min via yfinance)
- [x] Institutional ownership / 13F (20 funds, 8.4M-row archive, 20K aggregates)
- [x] Forex correlations (21 pairs, 54 years, 123K rows)
- [x] Earnings calendar with surprise history

### Authentication — ✅ Complete
- [x] JWT + refresh tokens (bcrypt password hashing)
- [x] Registration, login, logout
- [x] Self-service password reset (email link, 1-hour token TTL, all-device logout on reset)
- [x] User profiles (display name, email, is_premium flag)
- [x] 1 free trial per premium feature

---

## Features — Pro Tier ($99/mo)

Pro is the revenue engine. These features justify the price by replacing 2-3 separate subscriptions (TradingView + Seeking Alpha + Barchart = $75-135/mo).

### Analyze Tab — Advanced Analytics
*Quant Grades and AI Dashboard moved to Free tier (already built). Auto-Detected Trendlines and Seasonality remain Pro features (built but need premium gating).*

- [x] **Premium gate: Auto-Detected Trendlines** — Pro badge on toggle, locked overlay with upgrade CTA, 1 free trial
- [x] **Premium gate: Seasonality Heatmap** — Pro badge on toggle, locked overlay with upgrade CTA, 1 free trial

- [x] **Peer Comparison Table** — Side-by-side P/E, EV/EBITDA, ROE, revenue growth vs sector peers (Bloomberg COMP-style), Pro-gated
- [x] **Short Interest Data** — Short float %, days to cover, MoM change, squeeze risk score
- [x] **Dividend Analysis** — Yield, payout ratio, ex-date, safety grade, 5-yr avg yield
- [x] **Insider Trading Signals** — SEC Form 4 parsing, buy/sell signals with net sentiment, Pro-gated
- [x] **News NLP Sentiment Scoring** — VADER-scored headlines with sentiment bar + badges, Pro-gated

### Options — Enhanced
- [x] **Unusual Options Activity** — Volume/OI detection, sweep detection, premium summary, Pro-gated
- [x] **Probability of Profit** — Black-Scholes PoP for ATM and full chain, Pro-gated
- [x] **Market Maker Move** — Implied move from ATM straddle pricing with ±% and dollar range

### Charting — Phase 2 — ✅ Complete
- [x] **Drawing Tools (7)** — Trendline, horizontal line, Fibonacci, rectangle, parallel channel, measure tool, text annotation. Keyboard shortcuts (T/H/F/R/P/M/A/D), clone-last, delete-all confirm, **shift-to-snap-to-OHLC**, undo, per-ticker localStorage persistence
- [x] **Indicator Sub-Panes** — RSI (14), MACD (12,26,9), Stochastic (14,3) as synced sub-charts below main chart, toggle on/off
- [x] **VWAP Overlay** — Volume-weighted average price as main chart overlay
- [x] **AI Trendline Popover** — Click any auto-detected trendline for confidence breakdown, analog analysis, price projections, suggested action
- [x] **Multi-Chart Layout** — 2-4 charts side-by-side with **synced crosshairs across timeframes** (1d ↔ 15m nearest-candle matching)
- [ ] **Multi-Timeframe Analysis** — Overlay indicators from daily + hourly + 15min on single view *(multi-chart done; full indicator overlay still pending)*

### Charting — Phase 3 — ✅ Core Complete (research-prioritized indicator expansion)
- [x] **Indicator library expansion (4 → 17)**: ATR, Supertrend, Keltner Channels, ADX + DI±, OBV, Ichimoku Cloud, Volume Profile (VPVR with POC + Value Area), Squeeze Momentum (LazyBear). All client-side, no API work.
- [x] **Differentiated presets (4 stacks)** — Trend Break / Volume Flow / Regime-Aware / AI Confluence. Each bundles standard indicators with proprietary AlphaBreak signals so the stack can't be replicated on TradingView/TOS.
- [x] **Per-ticker saved chart layouts** — auto-persist toolbar state to localStorage, restore on ticker change
- [x] **Rich indicator tooltips** — 17 curated "what is this + when to use" hover cards on every chart-toolbar indicator
- [x] **Export chart as PNG** — stitches main pane + volume + all indicator sub-panes, alphabreak.vip watermark
- [ ] **Indicator Library (100+)** — ship remaining long-tail (Parabolic SAR, CMF, Williams %R, Elder Ray, Aroon, CCI, MFI, etc.)
- [ ] **Indicator settings modal** — configurable periods (currently hardcoded), parameter presets
- [ ] **Regime-Aware Weighting** — In BULL regime, weight momentum indicators. In RANGE, weight mean-reversion. Only highlight top 5 most predictive for current regime.
- [ ] **Indicator Search + Add** — Search bar to find and overlay any indicator with custom parameters

### Charting — Phase 4
- [x] **Smart Alerts** — Rule-based price/indicator alerts (up to 10 rules, 3 AND-chained conditions, 12 indicator fields). 10-min evaluator DAG during market hours. Delivery via in-app bell + SES email. Account > Smart Alerts sub-tab + "+ Alert" button on chart toolbar.
- [ ] **Custom Screeners** — "Show me all stocks with bullish engulfing AND above 200 SMA AND insider buying" — natural language to filter
- [ ] **Strategy Builder** — "Backtest buying when trend break > 90% bullish, selling when RSI > 70" — automated strategy

### Journal — Premium
- [x] Tags + filters + performance by tag
- [x] Pre-trade plans
- [x] Post-trade reviews
- [x] Pattern recognition
- [ ] **Automated Annotations** — Auto-tag entries with detected signals, indicators, market conditions at time of trade
- [ ] **Multi-Timeframe Context** — Attach daily/hourly/15min chart context to each journal entry
- [ ] **Backtesting Integration** — Link journal entries to historical backtest results

### Smart Checklists
- [ ] **Multi-Indicator Scoring Rules** — Configurable conditions (e.g., RSI < 30 AND above 200 SMA AND bullish 13F AND insider buying)
- [ ] Preset and custom checklist templates

### Data — Pro
- [ ] **Real-Time Data** — Live quotes via Polygon.io (no 15-min delay)
- [ ] **WebSocket Streaming** — Real-time price updates pushed to client
- [x] **Dark Pool Data** — API routes + analyze-tab panel exposing the 621K-row FINRA dataset (volume, WoW change, top ATS venues, 12-week trend sparkline)

### Trade Thesis Builder
- [x] Pre-trade plans (premium-gated)
- [x] **Structured thesis template** — entry criteria, price target, stop loss, time horizon, catalysts, risks, conviction level (7 fields in a JSONB column)

---

## Features — Elite Tier ($299/mo)

Elite delivers institutional-grade tools for serious traders and small funds.

### Analyze Tab — Institutional
- [ ] **Revenue by Segment & Geography** — Business unit and regional revenue breakdowns
- [ ] **3-Statement Financials with Trends** — Income, balance sheet, cash flow with historical time-series charts
- [ ] **DuPont Decomposition** — ROE breakdown into margin × turnover × leverage
- [ ] **Supply Chain Mapping** — Revenue exposure by customer/supplier (Bloomberg SPLC-style)
- [ ] **IV History & Volatility Surface** — Historical IV, term structure, skew visualization
- [ ] **Greeks (Full Suite)** — Delta, Gamma, Theta, Vega with real-time updates

### Options — Professional
- [ ] **IV Crush Modeling** — Predicted post-earnings IV decline for options sizing
- [ ] **ORATS Historical Data** — Full IV history, earnings IV spikes, Greeks history ($100/mo data cost)
- [ ] **Options Flow Dashboard** — Aggregated whale alerts, unusual activity across all tickers

### AI — Advanced
- [ ] **Earnings Surprise Prediction (ML)** — Predict beats/misses using options IV, analyst revisions, historical patterns

### Backtesting
- [ ] **Advanced Backtesting Framework** — Expose existing backtest engine (854K trades analyzed) to users
  - [ ] Strategy configuration UI
  - [ ] Date range selection
  - [ ] Performance metrics (Sharpe, max drawdown, win rate)
  - [ ] Equity curve visualization
  - [ ] Strategy comparison tool

---

## Features — API Tier ($499–999/mo)

Programmatic access for quant teams, hedge funds, and fintech builders.

| Tier | Price | Rate Limit | Use Case |
|------|-------|------------|----------|
| Starter | $499/mo | 10K requests/day | Individual quant |
| Growth | $749/mo | 50K requests/day | Small fund / fintech |
| Enterprise | $999/mo | Unlimited | Institutional / white-label |

- [ ] REST API — Full access to all endpoints
- [ ] WebSocket Feeds — Real-time price + signal streaming
- [ ] Bulk Data Downloads — Historical OHLCV, trend breaks, 13F, forex
- [ ] Webhook Alerts — Push trade signals to external systems
- [ ] API key management dashboard
- [ ] Usage analytics
- [ ] Custom data exports (CSV, JSON)
- [ ] SLA guarantees (Enterprise tier)

---

## Features — Future (Unscheduled)

Not committed to a tier or timeline. Will be prioritized based on user demand and business needs.

### Analysis
- [ ] Raindrop / volume profile charts
- [ ] DCF / intrinsic value model with adjustable assumptions
- [ ] Earnings call transcripts with key quote extraction
- [ ] Correlation matrix — cross-asset heatmap (stocks, forex, crypto, commodities)

### Options
- [ ] Risk profile / P&L diagram (visual profit/loss across prices)
- [ ] Strategy builder (spreads, condors, butterflies — point-and-click construction)

### Trading
- [ ] **Brokerage Integration (Schwab API)** — OAuth, account linking, order execution (market, limit, stop-loss), paper trading mode
- [ ] Options + technical confluence signals (e.g., "heavy call buying at breakout above 200 SMA")

### Social & Community
- [ ] Portfolio sharing — publish and follow top-performing portfolios
- [ ] Strategy marketplace — buy/sell trading strategies
- [ ] Social trading — copy trades from experienced traders
- [ ] Community forum for trading ideas

### Alternative Data
- [ ] Social sentiment (Twitter/Reddit for meme stocks)
- [ ] Web scraping (supply chain data, hiring trends)

### Machine Learning
- [ ] Reinforcement learning for position sizing
- [ ] Ensemble models (XGBoost + LightGBM + LSTM)
- [ ] Auto-ML hyperparameter tuning
- [ ] Explainable AI (SHAP values for feature importance)

### Platform Expansion
- [ ] Crypto trading (Bitcoin, Ethereum)
- [ ] Futures & commodities (ES, CL, GC)
- [ ] International markets (Europe, Asia)

### Enterprise
- [ ] White-label solution for hedge funds / RIAs
- [ ] Multi-user teams with role-based access
- [ ] Custom ML model training
- [ ] Dedicated infrastructure with SLA

---

## Customer Acquisition

### Pre-Launch (Current)
- [x] **Pricing Page** — 4-tier funnel (Free/Pro/Elite/API), monthly/annual toggle, FAQ, all upgrade CTAs wired
- [x] **Landing Page** — Hero, social proof (854K trades), problem/solution comparison, 6-feature grid, CTAs, shown to unauthenticated visitors
- [x] **Contact Page** — Contact form (name, email, subject dropdown, message), info card, FAQ, mailto fallback
- [ ] **Stripe Integration** — Billing, plan management, trial periods (14-day), upgrade/downgrade flows
- [x] **SEO Content** — 20 in-depth trading education articles + blog page + viewer + social posts shipped
- [x] **Social Proof** — Landing page expanded to 6 data points (854K trades, 98.5% win rate, 8.4M 13F holdings, etc.)
- [ ] **Competitive Positioning** — "Bloomberg depth at 1/80th the cost" messaging
- [x] **Free Tool Hooks** — "Start free, upgrade when you're ready" section with AI scoring, trend breaks, portfolio tracker

### Launch
- [ ] **Product Hunt Launch** — First-day push for visibility
- [ ] **r/wallstreetbets, r/options, r/algotrading** — Authentic engagement showing platform capabilities
- [ ] **FinTwit / X** — Daily market analysis posts with AlphaBreak screenshots
- [ ] **YouTube** — Screen recordings: "How I analyze AAPL using AlphaBreak" tutorials
- [ ] **Discord / Telegram Community** — Trading community around the platform
- [ ] **Email Drip Campaign** — Waitlist → free trial → Pro conversion (7-day sequence)

### Growth
- [ ] **Referral Program** — "Give a friend 30 days Pro, get 30 days free"
- [ ] **Freemium Conversion Funnel** — Track free → Pro conversion rate, optimize upgrade prompts
- [ ] **Partnership** — Integrate with trading educators, finance YouTubers, newsletters
- [ ] **Affiliate Program** — Revenue share for influencers driving paid signups
- [ ] **App Store Presence** — iOS + Android apps with ASO optimization
- [ ] **Stripe Integration** — Billing, plan management, trial periods (14-day), upgrade/downgrade flows

### Retention
- [ ] **Daily Email Digest** — Personalized watchlist alerts, trend breaks, earnings reminders
- [ ] **Gamification** — Streak tracking, journal consistency badges, community leaderboards
- [x] **Onboarding Flow** — 6-step tooltip tour, 5-item checklist banner with progress bar, empty state prompts
- [ ] **NPS Surveys** — Quarterly user satisfaction measurement
- [ ] **Feature Request Voting** — Public board where users vote on priorities

### Metrics to Track
| Metric | Target |
|--------|--------|
| Free signups / week | 500+ |
| Free → Pro conversion | 5-8% |
| Pro → Elite upgrade | 10-15% |
| Monthly churn (Pro) | <5% |
| DAU / MAU ratio | >30% |
| NPS | >50 |
| Time to first value | <5 minutes |

---

## Infrastructure

Everything below is required to serve hundreds of thousands to millions of users reliably.

### Current State — ✅ Complete
- [x] k0s Kubernetes single-node (all services containerized)
- [x] PostgreSQL 15 + TimescaleDB (106 tables, ~8GB)
- [x] Redis caching layer
- [x] Airflow with KubernetesExecutor (12 DAGs)
- [x] Nginx reverse proxy
- [x] SSL/HTTPS via Let's Encrypt (HTTP auto-redirect)
- [x] Domain: alphabreak.vip with www redirect
- [x] EC2 t3.medium, 100GB EBS gp2
- [x] Docker images: trading-api + airflow-trading
- [x] HPA auto-scaling, health/readiness probes
- [x] AWS CLI configured

### Scale Readiness — Must Build

#### Database
- [x] **Connection Pooling** — psycopg2 ThreadedConnectionPool (min=2, max=20, env-configurable)
- [x] **Query Optimization** — 25 indexes added across 17 tables, applied to production DB
- [ ] **Read Replicas** — Postgres streaming replication for read-heavy endpoints (analyze, reports)
- [x] **Database Backups** — Manual pg_dump backup/restore procedure documented, first backup taken (643MB)
- [x] **Query Caching** — Flask-Caching with RedisCache in prod, SimpleCache in dev. Replaced in-memory dicts in analyze/dashboard/earnings routes.

#### Compute
- [ ] **Horizontal Scaling** — Move from single-node k0s to multi-node cluster (EKS or multi-node k0s)
- [ ] **API Response Time** — Target <200ms p95 (currently 200-500ms)
- [x] **CDN** — CloudFront setup scripts ready (kubernetes/scripts/setup-cloudfront.sh, update-nginx-cloudfront.conf)
- [ ] **Load Balancer** — ALB in front of API pods for traffic distribution

#### Real-Time
- [ ] **WebSocket Infrastructure** — Flask-SocketIO + Redis Pub/Sub for real-time streaming
- [ ] **Connection Management** — Handle 10K+ concurrent WebSocket connections
- [ ] **Price Feed Integration** — Polygon.io WebSocket → Redis → Client pipeline

#### Monitoring & Observability
- [ ] **Prometheus** — Metrics collection (API latency, error rate, DB query time)
- [ ] **Grafana Dashboards** — System (CPU, RAM, disk), application (requests, errors), business (DAU, trades)
- [ ] **Alerting** — PagerDuty or Slack for critical metrics (>500ms latency, >1% error rate, disk >80%)
- [ ] **Structured Logging** — JSON logs → centralized log aggregation (Loki or CloudWatch)
- [ ] **Uptime Monitoring** — External health check pings, status page

#### Security
- [x] **Rate Limiting** — Per-user JWT key function, per-endpoint limits (analyze 60/min, auth 5-10/min, dashboard 30/min)
- [x] **Input Validation** — Ticker regex, interval/period whitelists, safe int conversions across journal/reports/notifications/analyze routes
- [x] **CORS Configuration** — Locked down to alphabreak.vip + www.alphabreak.vip origins
- [ ] **Secrets Management** — Rotate API keys, DB passwords; move to AWS Secrets Manager (password defaults now stripped from src/ modules, still need AWS Secrets Manager migration)
- [x] **DDoS Protection** — AWS WAF setup script with rate limiting, common rules, bad inputs, IP reputation
- [ ] **Penetration Testing** — Before public launch

#### Email & Notifications
- [x] **SES Domain Verification** — Domain identity + DKIM verified and signing in us-east-1
- [x] **SES Production Pipeline** — IAM user `alphabreak-ses-sender` (least-privilege), k8s secret `ses-credentials`, boto3 in requirements, `SES_SANDBOX_MODE=false` in pod env. Production access request filed 2026-04-15.
- [x] **Email Templates** — 10 branded HTML templates (dark theme, mobile-responsive) + email service with SES sending
- [x] **Bounce Handling** — SNS topic `ses-bounces-complaints` → HTTPS `/api/ses/webhook` (auto-confirmed), attached to SES identity for bounces + complaints
- [x] **Password Reset** — Self-service forgot/reset password flow with 1-hour hashed token, branded HTML email, atomic token consumption, all-device logout on reset

#### Multi-Region (Future)
- [ ] Primary: us-east-2 (Ohio)
- [ ] Secondary: us-west-2 (Oregon)
- [ ] Database replication across regions
- [ ] Health checks and automated failover
- [ ] Disaster recovery procedures tested

#### Mobile
- [ ] **React Native MVP** — Login, watchlist, portfolio summary, push notifications
- [ ] **iOS TestFlight** — Beta distribution
- [ ] **Google Play Beta** — Android distribution
- [ ] **Push Notifications** — Firebase Cloud Messaging for mobile alerts

---

## Recently Completed

### v4.6 (April 15, 2026) — Smart Alerts + Password Reset + SES Pipeline + Infra Fixes
- ✅ **Smart Alerts** — Rule-based price/indicator alert engine. Users define up to 10 rules with 3 AND-chained conditions across 12 indicator fields (price, volume, RSI, SMA, EMA, MACD, Stochastic, CCI, ADX). Airflow DAG evaluates every 10 min during US market hours. Per-rule cooldown (1h/4h/1d/until-reset). Delivery via in-app bell + SES email. Backend: `alert_service.py` (CRUD + indicator snapshot reusing `dashboard_service`), `/api/alerts` REST blueprint, `smart_alerts_evaluator_dag.py`. Frontend: `alerts.js` module, Account > Smart Alerts sub-tab, "+ Alert" button on Security Analysis chart toolbar with ticker prefill.
- ✅ **Self-service password reset** — `/api/auth/forgot-password` (5/hr, generic 200 to prevent email enumeration) + `/api/auth/reset-password` (10/hr, atomic token consumption). 1-hour hashed tokens in `password_reset_tokens` table. Branded HTML email via SES. Revokes all refresh tokens on reset (forces re-login everywhere). Frontend: forgot-password link on login form, dedicated reset form, `#reset-password?token=` hash handler.
- ✅ **SES production pipeline** — Domain `alphabreak.vip` DKIM-verified in us-east-1. IAM user `alphabreak-ses-sender` (least-privilege SES send). k8s secret `ses-credentials` mounted into trading-api. SNS topic `ses-bounces-complaints` with HTTPS subscription to `/api/ses/webhook` (auto-confirmed). `SES_SANDBOX_MODE=false` in pod env. Production access request filed. `boto3` added to requirements.txt (was missing — all SES sends were silently failing).
- ✅ **Airflow recovery** — `airflow-trading:latest` had been pruned from k0s containerd by `docker system prune -af` during a prior backend deploy. All scheduler/webserver pods stuck on `ErrImageNeverPull` for ~4 days. Rebuilt image, imported, cleaned 12 zombie pods. `smart_alerts_evaluator` DAG registered and unpaused.
- ✅ **`scripts/deploy-backend.sh`** — Single deploy script that rebuilds BOTH `trading-api` + `airflow-trading`, imports in one tarball, prunes only dangling layers (never `-af`). Flags: `--api-only`, `--airflow-only`, `--no-pull`. README updated. Prevents the image-GC bug.
- ✅ **ProductionConfig fix** — `validate_env()` required `POSTGRES_PASSWORD` but deployment uses `TIMESERIES_DB_PASSWORD`. Latent since v4.5 code hygiene; surfaced on first image rebuild.
- ✅ **Stale us-east-2 SES cleanup** — Deleted PENDING `alphabreak.vip` identity in us-east-2 (superseded by verified us-east-1 identity).

### v4.5 (April 13-14, 2026) — Charting Phase 2/3 + Code Hygiene
- ✅ **Charting Phase 2 complete** — 5 new drawing tools (parallel channel, measure, text annotation, clone-last, shift-snap-to-OHLC); 4 → 7 total tools. Multi-chart crosshair sync bug fixed (was silently broken in v4.1 — now passes real price values + handles cross-timeframe time normalization).
- ✅ **Charting Phase 3 core complete** — 8 new research-prioritized indicators (ATR, Supertrend, Keltner Channels, ADX+DI±, OBV, Ichimoku Cloud, Volume Profile/VPVR with POC+Value Area, Squeeze Momentum). 4 → 17 total indicators, all client-side.
- ✅ **Differentiated presets** — 4 one-click stacks (Trend Break / Volume Flow / Regime-Aware / AI Confluence) bundling standard indicators with proprietary AlphaBreak signals.
- ✅ **Per-ticker saved chart layouts** — auto-persist toolbar state to localStorage, 200ms debounced, restore on ticker change.
- ✅ **Rich indicator tooltips** — 17 curated hover cards ("what is it + when to use") suppressing native titles.
- ✅ **Chart export as PNG** — stitches main pane + volume + sub-panes, alphabreak.vip watermark, auto-downloads as {ticker}_{date}.png.
- ✅ **Charting research pass** — external usage data gathered from TradingView, QuantifiedStrategies, Dhan, Trader-Dale, Schwab (12 sources); build path validated against what retail traders actually use. Documented in CHARTING_UPGRADE_PLAN.md.
- ✅ **Drawing-tools library spike (negative result)** — evaluated deepentropy/lightweight-charts-drawing, rejected because it requires lightweight-charts v5 (we're on v4.1.3) and is at v0.1.1 alpha. Hand-coded fallback shipped instead.
- ✅ **Code hygiene sweep** — 11 easy-lift cleanups: docs/DEPLOYMENT.md URLs corrected to alphabreak.vip + Arkanisbot/AlphaBreak clone path; ROADMAP.old.md archived; Slack TODO stub removed; requirements.txt optional-deps documented; ProductionConfig.validate_env() fails fast on missing secrets; hardcoded 'trading123' defaults stripped from 10 src/ modules; ~47 print() calls → logger.info/error in 5 Airflow DAGs; 8 frontend console.logs gated behind window.DEBUG; .empty-state--fill CSS extracted; _fetchJson helper collapses repeated fetch/error plumbing in analyze.js.

### v4.4 (April 9-10, 2026) — Chart Migration + Auth Stability
- ✅ **Chart.js → Lightweight Charts migration** — All 14 Chart.js instances across 7 files (dashboard, earnings, forex, portfolio, account, longterm, watchlist) converted to Lightweight Charts. Only portfolio allocation doughnut remains as Chart.js.
- ✅ **Stable JWT authentication** — Fixed random JWT secret regenerating on every pod restart (all tokens invalidated). Stable key now set via k8s env var, shared across all replicas.
- ✅ **Extended token lifetime** — Access token 15min → 24hrs, refresh token 7 days → 30 days
- ✅ **Auth resilience** — Network errors / 502s during token validation no longer clear session. Only explicit 401/403 from server triggers logout.
- ✅ **NaN JSON fix** — Custom SafeJSONProvider converts Python NaN/Infinity to null, preventing invalid JSON responses
- ✅ **Hidden chart rendering fix** — Sentiment chart defers rendering when container is hidden (landing page), re-renders on login
- ✅ **Deployment path fix** — Corrected frontend deploy target from ~/frontend/ to ~/AlphaBreak/frontend/ (nginx root)
- ✅ **Cache busting** — Version-bumped all JS/CSS script tags to force browser cache refresh

### v4.3 (April 8, 2026) — Pro Features + New Analytics + Launch Prep
- ✅ **Landing page** — Marketing page for unauthenticated visitors (hero, social proof, problem/solution, feature grid, CTAs)
- ✅ **Contact page** — Form with subject dropdown, info card, FAQ, mailto fallback
- ✅ **Onboarding flow** — 6-step tooltip tour, 5-item checklist banner with progress tracking, empty state prompts
- ✅ **SES domain verification** — Domain identity + DKIM tokens generated, DNS records ready
- ✅ **Database backup procedure** — pg_dump/pg_restore documented in PROJECT_CONTEXT, first 643MB backup taken
- ✅ **Charting upgrade** — Drawing tools (trendline/hline/Fibonacci/rectangle), RSI/MACD/Stochastic sub-panes, VWAP overlay, clickable AI trendline popovers with confidence breakdown
- ✅ **Premium gate: Trendlines + Seasonality** — Pro badge on toggles, locked overlay with upgrade CTA, 1 free trial each
- ✅ **Short Interest section** — Short % float, days to cover, MoM change, squeeze risk score
- ✅ **Dividend Analysis section** — Yield, rate, payout ratio, safety grade, 5-yr avg, ex-date
- ✅ **Market Maker Expected Move** — ATM straddle-based implied ±% move with dollar range in Options widget
- ✅ **Security bug fixes** — SQL parameterization, error detail suppression in production, auth recursion guard

### v4.2 (April 4, 2026) — AI Dashboard + Quant Grades
- ✅ **AI Dashboard tab** — dedicated market-wide AI view (regime, signals, sectors, history, screener)
- ✅ **Quant Letter Grades (A-F)** — 6-factor scoring vs sector peers, including AI Score (exclusive)
- ✅ **Ticker news feed** — yfinance stock.news with thumbnails, publisher, time ago
- ✅ **Grade/trend-break divergence notes** — contextual warnings in AI Brief
- ✅ **Chart clutter reduction** — simplified trendline labels, fewer S/R lines
- ✅ **Nginx caching fix** — no-cache for HTML/JS/CSS, proper sites-enabled symlink
- ✅ **Git-based deployment** — server now serves from repo clone, no more SCP drift

### v4.1 (April 3-4, 2026) — Security Analysis + Charting Overhaul
- ✅ **Security Analysis page** — full single-ticker deep dive (landing page)
- ✅ **TradingView Lightweight Charts** — replaced Chart.js across 4 tabs (later expanded to all charts in v4.4)
- ✅ **Auto-detected trendlines** — pivot detection, confidence scoring, analog matching
- ✅ **Candlestick pattern recognition** — 8 patterns with probability scoring
- ✅ **Seasonality heatmap** — 5yr monthly returns
- ✅ **Symbol comparison** — overlay SPY, VIX, sector ETF
- ✅ **AI Analysis Brief** — plain-English synthesis on Security Analysis page
- ✅ **Educational tooltips + guide panels** — across Security Analysis, Reports, Earnings, Options
- ✅ **Market regime classification** — BULL/BEAR/RANGE/HIGH_VOL with confidence
- ✅ **Widget-card conversion** — all 11 tabs now collapsible
- ✅ **Comparison chart upgrade** — base=100, area fill, legend toggle, range selector
- ✅ **Hedge fund holdings fix** — tuple→dict mapping, real 13F data now populated
- ✅ **Report detail AI badge** — trend break probability, direction, confidence
- ✅ **Competitive analysis** — 10-competitor feature matrix + 3 Excel files
- ✅ **Pricing tiers defined** — Free / Pro $99 / Elite $299 / API $499-999
- ✅ **Roadmap v4 restructure** — Features by tier, Customer Acquisition, Infrastructure

### v3.0 (Q1-Q2 2026)
- ✅ Kubernetes migration (k0s, all services containerized)
- ✅ Portfolio logic overhaul (50/30/20 allocation, options trading, multi-TF exits)
- ✅ 40-year historical backtest (854K trades, 98.5% win rate)
- ✅ Push notifications (AWS SES + in-app, 9 event types)
- ✅ User profile / account page (Sharpe ratio, drawdown, equity curve)
- ✅ Trade journal (free + premium tiers, AI scoring, 16 endpoints)
- ✅ Redis caching layer
- ✅ API rate limiting
- ✅ EBS 50GB → 100GB expansion
- ✅ Dark pool data pipeline (621K rows, 101 MB)
- ✅ CBOE options statistics tracking

### v2.0 (Q1 2026)
- ✅ Forex correlation analysis (21 pairs, 123K rows)
- ✅ Portfolio automation (Airflow, 12 DAGs)
- ✅ SSL/HTTPS via Let's Encrypt
- ✅ Documentation overhaul (6 docs)
- ✅ 9-tab web dashboard

### v1.0 (Q4 2025)
- ✅ Market sentiment analysis
- ✅ Options pricing (Black-Scholes, Binomial Tree)
- ✅ Trend break detection (78% accuracy)
- ✅ 13F institutional holdings (20 funds)
- ✅ JWT authentication
- ✅ Initial web dashboard (3 tabs)

---

## Related Documentation

- **[COMPETITIVE_ANALYSIS.md](COMPETITIVE_ANALYSIS.md)** — Feature matrix vs 10 competitors
- **[PRICING_TIERS.md](PRICING_TIERS.md)** — Detailed tier breakdown with revenue projections
- **[ARCHITECTURE.md](ARCHITECTURE.md)** — Technical architecture and design
- **[DEPLOYMENT.md](DEPLOYMENT.md)** — Production deployment procedures
- **[COMPLETED_FEATURES.md](COMPLETED_FEATURES.md)** — Detailed production feature list
- **[CHANGELOG.md](../CHANGELOG.md)** — Version history

---

**Last Updated**: April 15, 2026
