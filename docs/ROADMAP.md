# Product Roadmap

**Version**: 4.0
**Last Updated**: April 3, 2026
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

### Analyze Tab (Single-Ticker Deep Dive) — 🚧 In Progress
*Rename "Intra-Day Trading Watchlist" → "Analyze". This is the core product differentiator.*

- [ ] Ticker search bar with auto-complete
- [ ] Company overview (market cap, P/E, EPS, 52-week range, sector)
- [ ] Analyst consensus & price targets (buy/hold/sell distribution, mean/high/low)
- [ ] Ticker news feed (real-time headlines filtered to security)
- [ ] Earnings calendar (dates, estimates, surprise history)
- [ ] Wire existing endpoints (`/api/predict/indicators/<ticker>`, `/api/analyze`) to new UI
- [ ] Basic price charts with common indicators (RSI, MACD, MA, Bollinger)

### Options Analysis — ✅ Complete
- [x] Options chain with bid/ask, volume, OI, IV
- [x] Fair value calculation (Black-Scholes, Binomial Tree)
- [x] Option chain by expiration

### AI & Scoring — 🚧 Partially Built
- [x] AI trade scoring (entry/exit/timing grades) — built in journal
- [x] Composite tech + fundamental score — built in journal scoring
- [x] Regime-aware analysis — trend break + indicator context in scoring
- [ ] Expose scoring as standalone Analyze tab widget (not just journal)
- [ ] Signal accuracy tracking dashboard — backtest data exists (854K trades, 98.5% win), needs frontend

### Portfolio & Journal — ✅ Complete
- [x] Portfolio tracker (paper trading, $100K)
- [x] Trade journal (full CRUD, notes, P&L tracking)
- [x] AI trade scoring on journal entries
- [x] Auto-import trades from portfolio
- [x] Community / shared journal (public/private toggle)
- [x] Watchlist management (server-synced, batch fetch up to 50 tickers)

### Notifications — ✅ Complete
- [x] Email alerts via AWS SES (sandbox mode)
- [x] In-app bell icon with unread count
- [x] 9 event types (trade signal, stop-loss, take-profit, earnings, etc.)
- [x] Per-event notification preferences
- [x] Unsubscribe-all endpoint

### Data — ✅ Complete
- [x] Delayed data (15-min via yfinance)
- [x] Institutional ownership / 13F (20 funds, 8.4M-row archive)
- [x] Forex correlations (21 pairs, 54 years, 123K rows)
- [x] Earnings calendar with surprise history

### Authentication — ✅ Complete
- [x] JWT + refresh tokens (bcrypt password hashing)
- [x] Registration, login, logout
- [x] User profiles (display name, email, is_premium flag)
- [x] 1 free trial per premium feature

---

## Features — Pro Tier ($99/mo)

Pro is the revenue engine. These features justify the price by replacing 2-3 separate subscriptions (TradingView + Seeking Alpha + Barchart = $75-135/mo).

### Analyze Tab — Advanced Analytics
- [ ] **Quant Letter Grades (A-F)** — Composite scores for value, growth, profitability, momentum, revisions (Seeking Alpha-style, compared vs sector median)
- [ ] **Peer Comparison Table** — Side-by-side P/E, EV/EBITDA, ROE, revenue growth vs sector peers (Bloomberg COMP-style)
- [ ] **Short Interest Data** — Short float %, days to cover, short squeeze risk score
- [ ] **Dividend Analysis** — Yield, payout ratio, growth rate, ex-dates, safety grade
- [ ] **Insider Trading Signals** — SEC Form 4 filings, insider buy/sell activity with timeline
- [ ] **Seasonality Patterns** — Monthly/weekly historical return heatmap (TrendSpider-style)
- [ ] **Auto-Detected Trendlines** — Algorithmic support/resistance drawn automatically
- [ ] **News NLP Sentiment Scoring** — FinBERT-scored headlines with sentiment trends per ticker

### Options — Enhanced
- [ ] **Unusual Options Activity** — Volume vs 5-day average, large block trades, sweep detection
- [ ] **Fair Value (Black-Scholes, Binomial)** — Move from free to Pro with expanded models *(currently free — gate at Pro)*
- [ ] **Probability of Profit** — IV-based probability calculations for any position
- [ ] **Market Maker Move** — Implied earnings move from ATM straddle pricing

### Charting — Enhanced
- [ ] **Drawing Tools** — Fibonacci retracements, trendlines, channels, annotations
- [ ] **Multi-Timeframe Analysis** — Overlay indicators from daily + hourly + 15min on single view

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
- [ ] **Dark Pool Data** — Expose existing 621K-row dataset (backend exists, needs API routes + UI)

### Trade Thesis Builder
- [x] Pre-trade plans (premium-gated)
- [ ] Structured thesis template: entry criteria, target, stop-loss, time horizon, catalysts, risks

---

## Features — Elite Tier ($299/mo)

Elite delivers institutional-grade tools for serious traders and small funds.

### Analyze Tab — Institutional
- [ ] **Revenue by Segment & Geography** — Business unit and regional revenue breakdowns
- [ ] **3-Statement Financials with Trends** — Income, balance sheet, cash flow with historical time-series charts
- [ ] **DuPont Decomposition** — ROE breakdown into margin × turnover × leverage
- [ ] **Supply Chain Mapping** — Revenue exposure by customer/supplier (Bloomberg SPLC-style)
- [ ] **IV History & Volatility Surface** — Historical IV, term structure, skew visualization
- [ ] **Greeks (Full Suite)** — Delta, Gamma, Theta, Vega with real-time updates *(chain is free; full Greeks at Elite)*

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
- [ ] Candlestick pattern recognition (auto-detect and label)
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
- [ ] **Landing Page** — Value proposition, feature screenshots, email capture for waitlist
- [ ] **SEO Content** — Blog posts targeting: "best stock analysis tools", "Bloomberg alternative", "free options analysis", "AI trade scoring"
- [ ] **Social Proof** — Backtest results (854K trades, 98.5% win rate) as marketing content
- [ ] **Competitive Positioning** — "Bloomberg depth at 1/80th the cost" messaging
- [ ] **Free Tool Hooks** — Offer free AI trade scoring, trend break alerts, and portfolio tracker as acquisition magnets

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
- [ ] **Onboarding Flow** — Guided tour for new users: add watchlist → analyze first ticker → create first journal entry
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
*These are prerequisites for handling real user traffic.*

#### Database
- [ ] **Connection Pooling** — PgBouncer or increase pool size for concurrent connections
- [ ] **Query Optimization** — Add indexes on hot paths, analyze query plans, eliminate N+1 queries
- [ ] **Read Replicas** — Postgres streaming replication for read-heavy endpoints (analyze, reports)
- [ ] **Database Backups** — Automated daily to S3, 30-day retention, tested restore procedure
- [ ] **Query Caching** — In-memory caching (Redis) with 1-5 min TTL for expensive queries

#### Compute
- [ ] **Horizontal Scaling** — Move from single-node k0s to multi-node cluster (EKS or multi-node k0s)
- [ ] **API Response Time** — Target <200ms p95 (currently 200-500ms)
- [ ] **CDN** — CloudFront for static assets (JS, CSS, images)
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
- [ ] **Rate Limiting** — Per-user, per-endpoint limits (Flask-Limiter configured but needs tuning)
- [ ] **Input Validation** — Sanitize all user inputs across all endpoints
- [ ] **CORS Configuration** — Lock down to alphabreak.vip origins only
- [ ] **Secrets Management** — Rotate API keys, DB passwords; move to AWS Secrets Manager
- [ ] **DDoS Protection** — CloudFront + WAF for edge protection
- [ ] **Penetration Testing** — Before public launch

#### Email & Notifications
- [ ] **SES Domain Verification** — Verify alphabreak.vip, move out of sandbox mode
- [ ] **Email Templates** — Branded HTML templates for all notification types
- [ ] **Bounce Handling** — SES bounce/complaint processing to maintain sender reputation

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

**Last Updated**: April 3, 2026
