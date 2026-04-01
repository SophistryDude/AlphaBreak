# AlphaBreak

**Live Demo:** [https://alphabreak.vip](https://alphabreak.vip)

A comprehensive AI-powered trading prediction system that identifies high-probability short-term trading opportunities using technical indicators, machine learning, and options pricing analysis.

## Overview

This application analyzes securities to predict trend breaks and identify mispriced options, enabling informed swing trading decisions. The system uses a multi-stage approach:

1. **Meta-Learning Stage** - Determines which technical indicators are most reliable under current market conditions
2. **Prediction Stage** - Uses XGBoost/LightGBM to predict when trend breaks will occur
3. **Options Analysis Stage** - Identifies mispriced options aligned with predicted trends

## Recent Updates

### February 9, 2026 - Portfolio DAG & API Fixes
- Fixed DAG database connection (was using Kubernetes DNS hostname instead of localhost)
- Fixed DAG SQL queries to match actual database schema (`trend_breaks` table, `f13_stock_aggregates` columns)
- Fixed Python import paths for EC2 deployment (was using Docker `/app/src` paths)
- Fixed Flask portfolio service DB password default
- Installed missing `yfinance` dependency in Airflow venv
- Portfolio now actively holding 6 swing positions from bullish trend break signals

### February 2, 2026 - Initial Deployment
- Deployed Apache Airflow 2.8.1 for automated portfolio management
- Extended options analysis to show all options expiring within 90 days
- Fixed DXY inline chart data parsing with dual Y-axis visualization
- Added real-time ticker validation and snackbar notifications for watchlist
- Deployed SSL via Let's Encrypt on alphabreak.vip

## Live Features

### Web Dashboard
- **Dashboard** - Real-time market overview with commodities, crypto, sector sentiment
- **Reports** - Comprehensive trend break analysis with probability scores
- **Watchlist** - Personal security watchlist with server sync (requires login)
- **Earnings** - Upcoming earnings calendar with historical surprise data
- **Long Term Trading** - Multi-week position analysis
- **Forex** - Currency pair correlation analysis with DXY tracking
- **Portfolio** - Automated portfolio with swing and long-term positions

### User Authentication
- JWT-based authentication with bcrypt password hashing
- Secure token refresh mechanism (15-min access / 7-day refresh)
- Server-side watchlist persistence
- localStorage migration on login

## Architecture

```
Securities_prediction_model/
├── src/                          # Python analysis modules
│   ├── data_fetcher.py           # Stock data retrieval (yfinance)
│   ├── technical_indicators.py   # 25+ indicators using pandas_ta
│   ├── trend_analysis.py         # Trend break detection
│   ├── meta_learning_model.py    # Indicator reliability prediction
│   ├── options_pricing.py        # Black-Scholes & Binomial Tree
│   ├── forex_data_fetcher.py     # FRED + Yahoo forex data
│   ├── forex_correlation_model.py # Currency correlation analysis
│   ├── sec_13f_fetcher.py        # SEC EDGAR 13F tracker
│   └── portfolio_manager.py      # Portfolio tracking
│
├── flask_app/                    # REST API Backend
│   ├── app/
│   │   ├── routes/
│   │   │   ├── auth.py           # Authentication endpoints
│   │   │   ├── user.py           # User-specific endpoints
│   │   │   ├── dashboard.py      # Dashboard data
│   │   │   ├── reports.py        # Analysis reports
│   │   │   ├── watchlist.py      # Watchlist data
│   │   │   ├── earnings.py       # Earnings calendar
│   │   │   ├── forex.py          # Forex endpoints
│   │   │   ├── options.py        # Options analysis
│   │   │   └── portfolio.py      # Portfolio management
│   │   ├── services/
│   │   │   └── portfolio_service.py # Portfolio DB access
│   │   └── utils/
│   │       ├── database.py       # PostgreSQL connection
│   │       └── jwt_auth.py       # JWT token management
│   └── requirements.txt
│
├── frontend/                     # Vanilla JS Dashboard
│   ├── index.html                # Main HTML with auth modal
│   ├── app.js                    # Core app + API request handler
│   ├── auth.js                   # Authentication state management
│   ├── dashboard.js              # Dashboard widgets (sentiment, sector analysis)
│   ├── trading.js                # Trend break predictions
│   ├── reports.js                # Historical analysis reports
│   ├── watchlist.js              # Watchlist with server sync
│   ├── earnings.js               # Earnings calendar
│   ├── longterm.js               # Long-term position analysis
│   ├── indicators.js             # Technical indicators tab
│   ├── forex.js                  # Forex correlation charts
│   ├── portfolio.js              # Portfolio tracker tab
│   ├── descriptions.js           # Shared UI descriptions
│   └── styles.css                # Dark theme styling (~5000 lines)
│
├── kubernetes/                   # Database schemas & Airflow
│   ├── schema_auth.sql           # Users, tokens, watchlists
│   ├── schema_forex.sql          # Forex data tables
│   └── airflow/dags/
│       └── portfolio_update_dag.py # Automated portfolio DAG
│
└── docs/                         # Documentation
    ├── ARCHITECTURE.md
    ├── DATA_ARCHITECTURE.md
    ├── DEPLOYMENT.md
    ├── COMPLETED_FEATURES.md
    ├── COMPREHENSIVE_FEATURE_DOCUMENTATION.md
    ├── other/security/
    │   └── trading-db-key.pem    # EC2 SSH key
    └── setup guide/
        └── SETUP_GUIDE.md        # Complete setup & deployment guide
```

## API Endpoints

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/register` | Create new account |
| POST | `/api/auth/login` | Login, returns JWT tokens |
| POST | `/api/auth/refresh` | Refresh access token |
| POST | `/api/auth/logout` | Revoke refresh token |
| GET | `/api/auth/me` | Get current user profile |

### User Data
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/user/watchlist` | Get user's watchlist |
| POST | `/api/user/watchlist` | Add tickers to watchlist |
| DELETE | `/api/user/watchlist/<ticker>` | Remove ticker |
| POST | `/api/user/watchlist/migrate` | Migrate localStorage to server |

### Market Data
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/dashboard/summary` | Market overview |
| GET | `/api/reports/trend-breaks` | Trend break analysis |
| GET | `/api/watchlist/data` | Watchlist security data |
| GET | `/api/earnings/calendar` | Earnings calendar |
| GET | `/api/forex/usd-chart` | USD pairs chart data |
| GET | `/api/forex/correlations` | Currency correlations |
| GET | `/api/sentiment` | Market sentiment indicators |

### Portfolio
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/portfolio/summary` | Portfolio overview |
| GET | `/api/portfolio/holdings` | Current positions |
| GET | `/api/portfolio/trades` | Trade history |
| GET | `/api/portfolio/snapshots` | Historical snapshots |

## Key Features

### Technical Indicators
- RSI, MACD, ADX, Stochastic Oscillator
- Bollinger Bands, SuperTrend
- Volume indicators (OBV, VPT, CMF, MFI, VWAP)
- Moving averages and trend lines

### Machine Learning Models

| Prediction Goal | Recommended Model | Why |
|----------------|-------------------|-----|
| Price direction (up/down) | XGBoost or LightGBM | Handles tabular data, feature importance |
| Trend break probability | XGBoost or LightGBM | Classification, good with indicators |
| Future price value | LSTM/GRU | Time series regression |
| Indicator reliability | Dense NN (Keras) | Multi-output regression |

### Market Indices & ETFs
- S&P 500 (^GSPC), Dow Jones (^DJI), VIX (^VIX)
- E-mini S&P 500 Futures (ES=F)
- Inverse ETFs: SH, PSQ, DOG (sentiment indicators)
- Volatility ETF: VXX
- Calculated features: S&P trend, VIX regime, futures premium, inverse ETF flows

### 13F Institutional Holdings Analysis
- Tracks 20 major hedge funds (Berkshire, Bridgewater, Renaissance, Citadel, DE Shaw, etc.)
- Fetches quarterly 13F filings from SEC EDGAR
- Calculates quarter-over-quarter position changes
- Aggregate institutional sentiment per stock
- Signals: STRONG_BUY, BUY, HOLD, SELL, STRONG_SELL based on fund activity

### Options Pricing
- **Binomial Tree** (American options) - Recommended for US stocks
- **Black-Scholes** (European options) - For indices, some ETFs
- Dynamic risk-free rate from Treasury yields
- Greeks calculation (Delta, Gamma, Theta, Vega, Rho)
- Trend-aligned option filtering for swing trading

### Forex Correlation Model
Analyzes correlations between currency pairs to identify patterns that may inform equity positioning.

**Data Sources:**
- **FRED (Federal Reserve)** - Historical exchange rates back to 1971 (54 years for major pairs)
- **Yahoo Finance** - Recent OHLCV data for supplementation

**Currency Pairs Tracked:**
| Pair | Data Start | History |
|------|------------|---------|
| USD/JPY, GBP/USD, USD/CAD, USD/CHF, AUD/USD | 1971 | ~54 years |
| USD/CNY | 1981 | ~44 years |
| EUR/USD | 1999 | ~26 years (Euro introduction) |
| USD/MXN, USD/BRL, USD/INR, USD/KRW, etc. | Various | 20-30 years |

### Portfolio Management (Airflow DAG)
- Runs at **9:00 AM EST** on weekdays (Mon-Fri)
- Trend break signals (80%+ probability) for swing trades
- 13F institutional sentiment for long-term positions
- 75% long-term / 25% swing allocation strategy
- Automated stop-loss monitoring and daily snapshots

## Installation

### Backend (Flask API)
```bash
cd flask_app
pip install -r requirements.txt
python wsgi.py
```

### Frontend
```bash
cd frontend
python -m http.server 8000
```

### Database
```bash
# PostgreSQL with TimescaleDB
psql -U postgres -d trading_data -f kubernetes/schema_auth.sql
psql -U postgres -d trading_data -f kubernetes/schema_forex.sql
```

## Environment Variables

```bash
# Flask
FLASK_ENV=development
SECRET_KEY=your-secret-key

# Database
TIMESERIES_DB_HOST=localhost
TIMESERIES_DB_PORT=5432
TIMESERIES_DB_NAME=trading_data
TIMESERIES_DB_USER=trading
TIMESERIES_DB_PASSWORD=your-password

# JWT (optional - has dev defaults)
JWT_SECRET_KEY=your-jwt-secret
```

## Database Schema

| Table | Description |
|-------|-------------|
| `users` | User accounts with bcrypt password hashes |
| `refresh_tokens` | JWT refresh token tracking |
| `user_watchlists` | Per-user watchlist persistence |
| `stock_data` | Daily/intraday OHLCV for individual stocks |
| `market_indices` | Daily data for S&P 500, DJI, VIX, futures |
| `hedge_fund_managers` | 20 tracked institutional investors |
| `f13_filings` | Quarterly 13F filing metadata |
| `f13_holdings` | Individual holdings per filing |
| `forex_daily_data` | Historical forex OHLCV |
| `forex_correlations` | Pair-to-pair correlation matrix |
| `portfolio_signals` | Trading signals from DAG |
| `portfolio_holdings` | Current portfolio positions |
| `portfolio_trades` | Trade execution history |
| `portfolio_snapshots` | Daily portfolio value snapshots |

## Deployment

Currently deployed on AWS EC2 with:
- **Frontend**: Nginx with SSL (Let's Encrypt) on port 443
- **Backend**: Gunicorn + Flask on port 5000 (proxied via Nginx at `/api/`)
- **Database**: PostgreSQL 15 with TimescaleDB
- **Scheduler**: Apache Airflow 2.8.1 (port 8080)
- **Domain**: alphabreak.vip

```bash
# Connect to EC2
ssh -i "Securities_prediction_model/docs/other/security/trading-db-key.pem" ubuntu@3.140.78.15

# Restart Flask API
pkill -f 'gunicorn.*5000'
cd /home/ubuntu/flask_app && nohup bash start_gunicorn.sh > /home/ubuntu/gunicorn.log 2>&1 &

# Restart Airflow (if needed)
sudo systemctl restart airflow-scheduler
sudo systemctl restart airflow-webserver
```

See [docs/setup guide/SETUP_GUIDE.md](docs/setup%20guide/SETUP_GUIDE.md) for comprehensive setup and deployment guide (EC2, K8s, Docker).

## Roadmap

- [x] Database integration (PostgreSQL/TimescaleDB)
- [x] Multi-timeframe models (5min, 1hr, daily)
- [x] 13F report analysis (SEC hedge fund holdings, 8.4M archive rows)
- [x] Market indices & ETF tracking
- [x] Forex correlation model with 54 years of data (21 pairs)
- [x] User authentication (JWT + bcrypt)
- [x] Server-side watchlist sync
- [x] Live web dashboard (9 tabs)
- [x] SSL/HTTPS (Let's Encrypt, auto-renewing)
- [x] Airflow automation (LocalExecutor, portfolio DAG, daily updates)
- [x] Dark pool data pipeline
- [x] Portfolio tracker (paper trading, $100K)
- [ ] Kubernetes containerization
- [ ] Push notifications for high-probability trades
- [ ] Trading platform integration (Schwab/Robinhood)
- [ ] Premium subscription tier with real-time data
- [ ] Mobile app (React Native)

## Data Sources

| Tier | Sources | Limitations |
|------|---------|-------------|
| **Current (Free)** | Yahoo Finance, FRED, SEC EDGAR | 15-min delay, rate limits |
| **Planned (Mid-tier)** | Polygon.io, Unusual Whales | Real-time, $400-800/mo |
| **Enterprise** | Bloomberg, Refinitiv | Tick data, $10k+/mo |

See [docs/DATA_SOURCES_COMPARISON.md](docs/DATA_SOURCES_COMPARISON.md) for detailed comparison.

## Documentation

### Core Documentation

- **[ARCHITECTURE.md](docs/ARCHITECTURE.md)** - System architecture, component breakdown, technology stack, deployment architecture
- **[DATA_ARCHITECTURE.md](docs/DATA_ARCHITECTURE.md)** - Database schema, TimescaleDB optimization, query patterns, storage estimates
- **[DEPLOYMENT.md](docs/DEPLOYMENT.md)** - Production deployment guide, infrastructure provisioning, service configuration, backup/recovery
- **[API_DOCUMENTATION.md](docs/api/API_DOCUMENTATION.md)** - Complete API reference, request/response formats, authentication
- **[SETUP_GUIDE.md](docs/setup/SETUP_GUIDE.md)** - Local development, Docker, K8s, EC2 quick start

### Feature Documentation

- **[COMPLETED_FEATURES.md](docs/COMPLETED_FEATURES.md)** - Production-ready features, deployment status, recent updates
- **[COMPREHENSIVE_FEATURE_DOCUMENTATION.md](docs/COMPREHENSIVE_FEATURE_DOCUMENTATION.md)** - ML feature engineering (59 features), production metrics

### Project Management

- **[CHANGELOG.md](CHANGELOG.md)** - Version history, all changes by release
- **[CONTRIBUTING.md](CONTRIBUTING.md)** - Contribution guidelines and development workflow
- **[ROADMAP.md](docs/ROADMAP.md)** - Future development plans and priorities

### Specialized Guides

- **[RELEASE_NOTES.md](docs/RELEASE_NOTES.md)** - Release process, templates, checklists
- **[MODEL_TRAINING_GUIDE.md](docs/setup/MODEL_TRAINING_GUIDE.md)** - Training ML models
- **[KUBERNETES_MIGRATION_PLAN.md](docs/setup/KUBERNETES_MIGRATION_PLAN.md)** - K8s migration strategy
- **[DATA_SOURCES_COMPARISON.md](docs/DATA_SOURCES_COMPARISON.md)** - Data provider comparison
- **[PULLBACK_MODEL_PLAN.md](docs/PULLBACK_MODEL_PLAN.md)** - Future model development

## License

MIT

---

**Last Updated**: February 9, 2026
**Version**: 1.0.0
**Status**: Production
