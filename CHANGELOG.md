# Changelog

All notable changes to the Securities Prediction Model project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [4.6.0] - 2026-04-15

### Added

#### Smart Alerts
- Rule-based price/indicator alert engine with 12 supported fields (price, volume, RSI, SMA 20/50/200, EMA 20/50, MACD histogram, Stochastic %K, CCI, ADX)
- Up to 10 rules per user, 3 AND-chained conditions per rule
- Per-rule cooldown: 1 hour, 4 hours, 1 day, or manual reset
- Airflow DAG `smart_alerts_evaluator` runs every 10 minutes during US market hours
- Delivery via existing in-app notification bell + SES email
- Database: `user_alert_rules`, `alert_rule_firings` tables
- Backend: `alert_service.py` (CRUD + indicator snapshot engine), `/api/alerts` REST blueprint (6 endpoints)
- Frontend: `alerts.js` module, Account > Smart Alerts sub-tab, "+ Alert" button on Security Analysis chart toolbar
- `smart_alert` event type added to notification preferences

#### Self-Service Password Reset
- `POST /api/auth/forgot-password` — rate-limited (5/hr), generic 200 response (no email enumeration)
- `POST /api/auth/reset-password` — atomic token consumption, revokes all refresh tokens
- `password_reset_tokens` table with SHA-256 hashed tokens, 1-hour TTL
- Branded HTML email via SES with reset link
- Frontend: "Forgot password?" link on login form, forgot-password form, reset-password form
- Handles `#reset-password?token=` URL hash for email link landing

#### SES Production Pipeline
- IAM user `alphabreak-ses-sender` with least-privilege SES send-only policy (us-east-1)
- k8s secret `ses-credentials` mounted as env vars into trading-api pods
- SNS topic `ses-bounces-complaints` with HTTPS subscription to `/api/ses/webhook` (auto-confirmed)
- Bounce + complaint notifications attached to SES domain identity
- `boto3>=1.34.0` added to requirements.txt (was missing — all SES sends silently failed)
- `SES_SANDBOX_MODE=false`, `SES_REGION=us-east-1`, `SES_FROM_EMAIL=noreply@alphabreak.vip` set in pod env
- Production access request filed; sandbox still allows sends to verified addresses

#### Deploy Script
- `scripts/deploy-backend.sh` — rebuilds BOTH `trading-api` and `airflow-trading` images
- Imports both in a single tarball via `k0s ctr images import`
- Prunes only dangling Docker layers (`docker image prune -f`, never `-af`)
- Flags: `--api-only`, `--airflow-only`, `--no-pull`

### Fixed
- **Airflow recovery** — `airflow-trading:latest` was pruned from k0s containerd by `docker system prune -af` during a prior deploy. Scheduler + webserver pods stuck on `ErrImageNeverPull` for ~4 days. Rebuilt image, imported, cleaned 12 zombie pods.
- **ProductionConfig.validate_env()** — Required `POSTGRES_PASSWORD` but k8s deployment uses `TIMESERIES_DB_PASSWORD`. Latent since v4.5; crashed pods on first image rebuild.
- **Stale SES identity** — Deleted PENDING `alphabreak.vip` domain identity in us-east-2 (superseded by verified us-east-1 identity)

---

## [3.0.0] - 2026-04-03

### Added

#### Kubernetes Migration
- Full containerization on k0s (single-node Kubernetes)
- Migrated 106 tables (~8GB) from bare-metal to containerized TimescaleDB
- 11 Airflow DAGs running via KubernetesExecutor
- Docker images: `trading-api:latest`, `airflow-trading:latest`
- HPA auto-scaling, health/readiness probes, persistent volumes

#### Portfolio Logic Overhaul
- New allocation: 50% long-term stock / 30% swing options / 20% cash float
- Swing trades execute via ATM options (auto-selected 30 DTE contracts)
- Multi-timeframe exit confirmation (daily+hourly must agree for full exit)
- Smart options exits: volume-based profit-taking, reversal-based loss-cutting
- Position trim (25%) on hourly-only bearish signals
- Max $10K per options trade, 5 concurrent positions
- `portfolio_options_monitor` DAG runs every 2h during market hours

#### Historical Backtesting
- 40-year backtest: Strategy vs NASDAQ vs TQQQ (1985-2026)
- 854,773 trend break trades analyzed: 98.5% win rate, +3.15% avg return
- `backtest_comparison` table with 10,393 daily rows
- 7 presentation charts generated (PNG, dark theme, 200 DPI)

#### Push Notifications
- Email notifications via AWS SES (sandbox mode)
- In-app notification bell with unread badge (60s polling)
- 9 event types: trade signals, stop-loss, take-profit, earnings, daily summary
- Per-event-type email preferences with toggles
- Unsubscribe-all endpoint
- Notification tables: `notifications`, `notification_preferences`, `notification_email_log`

#### User Profile / Account Page
- Profile settings: edit display name, change password
- Performance analytics: Sharpe ratio, max drawdown, equity curve chart, P&L calendar heatmap
- Best/worst trades tables
- Linked Accounts section (Schwab placeholder)
- Username in header links to Account page (no sidebar entry)
- `user_preferences` table for extensible settings
- `analytics.py` computation module

#### Trade Journal (Free + Paid Tiers)
- **Free**: Manual notes, P&L tracking, AI trade scoring, shared/public journal, auto-import, chart snapshots
- **Paid**: Tags + filters, pre-trade plans, post-trade reviews, pattern detection, performance by tag
- 1 free trial per premium feature (pre-trade plan, post-trade review, pattern recognition)
- AI scoring: entry/exit grades (0-100), timing grade (A-F), improvement suggestions
- Pattern detection: momentum_breakout, trend_continuation, mean_reversion, volume_climax
- 16 API endpoints with premium gating
- `trade_journal` table with JSONB fields for structured data

### Changed
- Portfolio allocation: 65/35 → 50/30/20 (long-term/swing options/cash float)
- Cash reserve: 20% minimum floor → 20% maximum ceiling (deploy capital)
- `ProductionConfig.API_KEY_REQUIRED`: now respects env var instead of hardcoding True
- Earnings calendar: capped at 20 yfinance fetches per request (was 112, caused timeouts)
- Added `lxml` dependency for yfinance earnings parsing
- k0s eviction thresholds relaxed to 5% in `/etc/k0s/k0s.yaml`
- Default notification preferences seeded on user registration

---

## [2.0.0] - 2026-02-02

### Added

#### Forex Correlation Analysis
- **New Tab**: Added Forex Analysis tab to frontend (4 tabs total)
- **Currency Pair Tracking**: 12+ major USD pairs with historical data back to 1971
- **DXY Backdrop Visualization**: Dual Y-axis charts showing pair movement against US Dollar Index
- **Correlation Matrix**: 30/60/90-day rolling correlations between currency pairs
- **Data Sources**: FRED (Federal Reserve) for historical data, Yahoo Finance for recent OHLCV
- **Database Tables**:
  - `forex_pairs` - Pair metadata and thresholds
  - `forex_daily_data` - Historical OHLCV data
  - `forex_correlations` - Correlation matrix storage
  - `forex_correlation_thresholds` - Alert thresholds
  - `forex_trend_breaks` - Forex trend break signals
- **API Endpoints**:
  - `GET /api/forex/usd-chart` - USD pairs chart data
  - `GET /api/forex/pairs` - List all tracked pairs
  - `GET /api/forex/data/:pair` - OHLCV data for specific pair
  - `GET /api/forex/correlations` - Correlation matrix
  - `GET /api/forex/trend-breaks` - Forex trend break signals

#### Portfolio Automation & Management
- **Apache Airflow 2.8.1**: Deployed for workflow orchestration
  - LocalExecutor for task execution (no Celery/Redis required)
  - PostgreSQL backend for metadata storage
  - Systemd services: `airflow-scheduler.service`, `airflow-webserver.service`
  - Web UI: http://3.140.78.15:8080 (admin/admin123)
- **Portfolio DAG**: Automated daily updates at 9 AM EST (Mon-Fri)
  - Schedule: `0 14 * * 1-5` (cron format)
  - 8-step workflow: Fetch signals → Fetch prices → Create signals → Process signals → Manage long-term → Stop losses → Daily snapshot
  - 75/25 allocation (long-term/swing)
  - 80%+ probability threshold for trend breaks
  - Integration with 13F institutional sentiment (STRONG_BUY/BUY signals)
- **Database Tables**:
  - `portfolio_signals` - Buy/sell signals with probability scores
  - `portfolio_holdings` - Current positions
  - `portfolio_trades` - Trade history
  - `portfolio_snapshots` - End-of-day portfolio state
  - `portfolio_performance` - Performance metrics

#### Documentation
- **ARCHITECTURE.md**: Comprehensive system architecture documentation
  - High-level architecture diagrams
  - Component breakdown (Frontend, Backend, Business Logic, Data layers)
  - Technology stack details
  - Deployment architecture
  - Security architecture
  - Scalability strategies
- **DEPLOYMENT.md**: Production deployment guide
  - Infrastructure provisioning (AWS EC2)
  - Initial server setup
  - Service configuration (Flask, Nginx, Airflow)
  - Database management (PostgreSQL + TimescaleDB)
  - Backup & disaster recovery procedures
  - Update & rollback procedures
  - Comprehensive troubleshooting
- **Consolidated SETUP_GUIDE.md**: Merged GETTING_STARTED.md into SETUP_GUIDE.md
  - Quick Start section for EC2 production deployment
  - Complete local development setup
  - Docker and Kubernetes deployment instructions
  - EC2 Production Guide section with detailed commands
- **CHANGELOG.md**: Version history and release notes (this file)
- **ROADMAP.md**: Future development plans and priorities

### Changed

#### Options Analysis Improvements
- **Extended Options Window**: Now shows all options expiring within 90 days (previously only nearest expiry)
  - Modified: `src/options_pricing.py`
  - Added: `get_options_within_days()` function
  - Each option displays specific expiry date and days until expiration
- **Fair Value Calculations**: Added parameter validation with sensible defaults
  - Volatility: defaults to 30% if invalid
  - Time to expiry: minimum 1 day
  - Risk-free rate: defaults to 4.5%
  - Better error handling for edge cases

#### Watchlist Features
- **Ticker Validation**: Added real-time validation before adding securities
  - Modified: `frontend/watchlist.js`
  - API check ensures ticker exists before adding
  - Reduces user errors and invalid tickers
- **Snackbar Notifications**: Implemented global notification system
  - Added to: `frontend/app.js`, `frontend/watchlist.js`
  - Styled in: `frontend/styles.css`
  - Success, error, info, and warning message types
  - Non-intrusive, auto-dismissing notifications
- **"+ Watch" Button**: Quick-add functionality on options analysis page
  - Modified: `frontend/index.html`, `frontend/app.js`
  - Adds analyzed ticker directly to intra-day trading watchlist
  - Streamlines workflow for options traders

#### UI/UX Improvements
- **Market Sentiment Visibility**: Hidden market sentiment widget on portfolio page for cleaner UI
  - Modified: `frontend/app.js` tab switching logic
  - Reduces visual clutter on portfolio tab
  - Still accessible on Dashboard tab

#### Feature Engineering
- **12 New Forex Features**: Added currency-specific features for ML models
  - Pair correlations (30/60/90-day)
  - DXY correlation & divergence
  - Multi-pair context features (USD strength indicator, carry trade sentiment)
  - Lead/lag analysis between pairs
  - Database: `forex_correlations`, `forex_correlation_thresholds`
- **Updated Documentation**: COMPREHENSIVE_FEATURE_DOCUMENTATION.md v2.0
  - 47 standard features + 12 forex features = 59 total
  - Production implementation notes
  - Performance metrics: <2s calculation time, 78% model accuracy

### Fixed

#### Forex Chart Issues
- **DXY Inline Charts**: Corrected data parsing for currency pair charts
  - Modified: `frontend/forex.js` (lines 623-643, 948-968)
  - Charts now properly calculate DXY index from chart_data array
  - Added dual Y-axis visualization for currency pairs with DXY backdrop
- **Nginx URL Encoding**: Fixed inline charts not populating due to encoded slashes
  - Issue: `/api/forex/data/EUR%2FUSD` blocked by nginx (encoded slash %2F)
  - Fix: Changed frontend to send `/api/forex/data/EUR_USD` instead (underscores)
  - Backend already handles both formats (converts underscores back to slashes)
  - Modified: `frontend/forex.js` in `loadPairInlineChart()` and `loadPairChart()` functions

#### API Authentication
- **Frontend Endpoint Access**: Removed `@require_api_key` decorator
  - Modified: `flask_app/app/routes/frontend_compat.py`
  - Endpoints now accessible without API keys for development
  - Simplifies frontend integration during development phase
  - **Note**: Consider re-enabling for production with proper key management

### Security

- **JWT Authentication**: Access tokens (15 min) + refresh tokens (7 days)
- **Password Hashing**: bcrypt with 12 rounds
- **SSH Access**: Key-based authentication only (password auth disabled)
- **Database**: Localhost access only (not exposed to public internet)
- **Known Gaps** (to be addressed):
  - No HTTPS/SSL (Let's Encrypt planned for Q2 2026)
  - No API rate limiting (Flask-Limiter + Redis planned)
  - Hardcoded secrets in .env (AWS Secrets Manager planned)

### Performance

- **API Response Time**: 200-500ms (target: <200ms)
- **Frontend Load Time**: <2s (target: <1s)
- **Database Query Time**: 50-100ms (target: <50ms)
- **Airflow DAG Runtime**: 2-5 minutes per run
- **Uptime**: 99.5% (target: 99.9%)
- **Feature Calculation**: <2s for 59 features
- **Model Accuracy**: 78% with all features, 76% with top 25, 68% with minimal 10

---

## [1.0.0] - 2025-11-27

### Initial Release

#### Core Features
- **Market Sentiment Analysis**: Real-time sentiment tracking using 8 technical indicators
  - CCI, RSI, SMA Crossover, Stochastic, ADX, TLEV, VIX, PCR
  - Dashboard widget with color-coded sentiment (bullish/bearish/neutral)
- **Options Pricing**: Fair value calculations using Black-Scholes and Binomial Tree models
  - American options support (Binomial Tree)
  - European options support (Black-Scholes)
  - Greeks calculation (Delta, Gamma, Theta, Vega, Rho)
- **Trend Break Detection**: ML-based prediction of trend reversals
  - 47 technical indicators as features
  - XGBoost/LightGBM models
  - Probability scores for trade signals
- **13F Institutional Holdings**: Track 20 major hedge funds
  - Quarterly 13F filings from SEC EDGAR
  - Quarter-over-quarter position changes
  - Aggregate sentiment signals (STRONG_BUY to STRONG_SELL)
- **Watchlist Management**: Personal security tracking
  - localStorage persistence
  - Server sync (requires login)
  - Real-time price updates

#### Frontend
- **Web Dashboard**: Single-page application with 3 tabs
  - Dashboard: Market overview, sentiment, commodities
  - Reports: Trend break analysis with filtering
  - Watchlist: Personal security tracker
  - Earnings: Upcoming earnings calendar
- **Technology**: Vanilla JavaScript, Chart.js, HTML5/CSS3
- **Dark Theme**: Modern, responsive UI
- **Authentication**: JWT-based login system

#### Backend
- **Flask API**: RESTful API with 20+ endpoints
  - Trend break predictions
  - Options analysis
  - Market sentiment
  - User authentication
  - Watchlist CRUD
- **Database**: PostgreSQL 15 + TimescaleDB
  - Time-series optimization for OHLCV data
  - Hypertables with automatic partitioning
  - Continuous aggregates for 10-min and hourly rollups
- **Data Sources**: Yahoo Finance, FRED, SEC EDGAR
  - Free tier data (15-min delay acceptable)
  - Historical data back to 1962 for major stocks

#### Infrastructure
- **Deployment**: AWS EC2 (Ubuntu 22.04)
  - Frontend: Nginx on port 8000
  - Backend: Gunicorn (3 workers) on port 5000
  - Database: PostgreSQL on port 5432
- **Services**: Systemd service management
- **Security**: SSH key-based authentication only

#### Documentation
- **README.md**: Project overview and quick start
- **DATA_ARCHITECTURE.md**: Database schema and data pipeline
- **COMPLETED_FEATURES.md**: Production-ready feature list
- **COMPREHENSIVE_FEATURE_DOCUMENTATION.md**: ML feature engineering specs
- **API_DOCUMENTATION.md**: API endpoints and request/response formats
- **SETUP_GUIDE.md**: Local development setup

---

## [Unreleased]

### Planned Features (Q1-Q2 2026)

#### Infrastructure
- [ ] Let's Encrypt SSL certificates (HTTPS)
- [ ] CloudFront CDN for static assets
- [ ] Redis caching layer
- [ ] API rate limiting (Flask-Limiter)
- [ ] Prometheus + Grafana monitoring
- [ ] AWS Secrets Manager for credentials
- [ ] Automated database backups to S3

#### Features
- [ ] Real-time WebSocket price updates
- [ ] Push notifications for high-probability trades
- [ ] Advanced charting with TradingView integration
- [ ] Sector rotation analysis
- [ ] Earnings surprise predictions
- [ ] News sentiment analysis integration
- [ ] Backtesting framework
- [ ] Paper trading mode

#### ML/Data
- [ ] LSTM/GRU models for price prediction
- [ ] Reinforcement learning for position sizing
- [ ] Alternative data integration (social sentiment, satellite imagery)
- [ ] Options historical data (ORATS or OptionMetrics)
- [ ] Real-time data feed (Polygon.io upgrade)
- [ ] Crypto market integration

#### Platform
- [ ] Mobile app (React Native)
- [ ] Premium subscription tier
- [ ] Trading platform integration (Schwab/Robinhood APIs)
- [ ] Multi-user support with role-based access
- [ ] Portfolio sharing and social features

### Planned Infrastructure Changes (Q3-Q4 2026)

#### Phase 2: Containerization
- [ ] Docker containers for all services
- [ ] Docker Compose for local development
- [ ] Nginx load balancer
- [ ] Redis cache cluster

#### Phase 3: Kubernetes Migration
- [ ] EKS cluster setup
- [ ] Helm charts for deployment
- [ ] Horizontal pod autoscaling
- [ ] Service mesh (Istio)
- [ ] CI/CD pipeline (GitHub Actions)

#### Phase 4: Multi-Region
- [ ] Multi-region deployment (us-east-1, us-west-2)
- [ ] CloudFront global CDN
- [ ] Database replication
- [ ] Disaster recovery automation

---

## Version History Summary

| Version | Date | Description |
|---------|------|-------------|
| 2.0.0 | 2026-02-02 | Forex analysis, portfolio automation, Airflow deployment |
| 1.0.0 | 2025-11-27 | Initial release with core trading features |

---

## How to Read This Changelog

- **Added**: New features
- **Changed**: Changes to existing functionality
- **Deprecated**: Soon-to-be-removed features
- **Removed**: Removed features
- **Fixed**: Bug fixes
- **Security**: Security improvements

## How to Contribute to This Changelog

When making changes to the codebase:

1. **Update CHANGELOG.md** in the same PR as your changes
2. Add entries under the `[Unreleased]` section at the top
3. Use the appropriate category (Added, Changed, Fixed, etc.)
4. Include:
   - Brief description of the change
   - Files modified (if significant)
   - Any breaking changes or migration steps
5. On release, move `[Unreleased]` entries to a new version section

**Example**:

```markdown
## [Unreleased]

### Added
- Real-time WebSocket price updates
  - Modified: `frontend/app.js`, `flask_app/app/routes/websocket.py`
  - New dependency: `flask-socketio`
  - Breaking change: Requires Redis for Pub/Sub
```

---

## Release Process

See [RELEASE_NOTES.md](docs/RELEASE_NOTES.md) for the release process and how to create release notes.

---

**Maintained By**: Development Team
**Review Cycle**: Updated with every PR, tagged on releases
**Format**: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
**Versioning**: [Semantic Versioning](https://semver.org/spec/v2.0.0.html)

---

**Last Updated**: February 2, 2026
