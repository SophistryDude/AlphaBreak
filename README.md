# AlphaBreak

**Live Demo:** [https://alphabreak.vip](https://alphabreak.vip)

A comprehensive AI-powered trading prediction system that identifies high-probability short-term trading opportunities using technical indicators, machine learning, and options pricing analysis.

## Overview

This application analyzes securities to predict trend breaks and identify mispriced options, enabling informed swing trading decisions. The system uses a multi-stage approach:

1. **Meta-Learning Stage** - Determines which technical indicators are most reliable under current market conditions
2. **Prediction Stage** - Uses XGBoost/LightGBM to predict when trend breaks will occur
3. **Options Analysis Stage** - Identifies mispriced options aligned with predicted trends

## Recent Updates

### April 2, 2026 - Kubernetes Migration Complete
- Fully containerized on k0s (single-node Kubernetes) on EC2
- Migrated 106 tables (~8GB) from bare-metal PostgreSQL into containerized TimescaleDB
- All 10 Airflow DAGs running via KubernetesExecutor (crypto 10min, S&P 500 hourly, trend breaks, model retraining, backtesting, portfolio)
- Flask API running in k0s with auto-scaling (HPA), health/readiness probes
- Redis caching in-cluster
- Nginx reverse-proxies to k0s NodePort (30427)
- Fixed earnings calendar (added `lxml` dependency for yfinance)
- Fixed `ProductionConfig` to respect `API_KEY_REQUIRED` env var
- Cleaned up disk pressure issues with relaxed kubelet eviction thresholds

### February 9, 2026 - Portfolio DAG & API Fixes
- Fixed DAG database connection (was using Kubernetes DNS hostname instead of localhost)
- Fixed DAG SQL queries to match actual database schema
- Fixed Python import paths for EC2 deployment
- Portfolio now actively holding 6 swing positions from bullish trend break signals

### February 2, 2026 - Initial Deployment
- Deployed Apache Airflow 2.8.1 for automated portfolio management
- Extended options analysis to show all options expiring within 90 days
- Deployed SSL via Let's Encrypt on alphabreak.vip

## Live Features

### Web Dashboard (9 Tabs)
- **Dashboard** - Real-time market overview with commodities, crypto, sector sentiment
- **Reports** - Comprehensive trend break analysis with probability scores
- **Watchlist** - Personal security watchlist with server sync (requires login)
- **Earnings** - Upcoming earnings calendar with EPS estimates and historical surprises
- **Long Term Trading** - Multi-week position analysis
- **Forex** - Currency pair correlation analysis with DXY tracking
- **Portfolio** - Automated portfolio with swing and long-term positions
- **Indicators** - Technical indicator analysis
- **Options** - Options pricing and Greeks analysis

### User Authentication
- JWT-based authentication with bcrypt password hashing
- Secure token refresh mechanism (15-min access / 7-day refresh)
- Server-side watchlist persistence

## Architecture

```
Securities_prediction_model/
├── src/                          # Python analysis modules
│   ├── data_fetcher.py           # Stock data retrieval (yfinance)
│   ├── technical_indicators.py   # 25+ indicators
│   ├── trend_analysis.py         # Trend break detection
│   ├── meta_learning_model.py    # Indicator reliability prediction
│   ├── options_pricing.py        # Black-Scholes & Binomial Tree
│   ├── forex_data_fetcher.py     # FRED + Yahoo forex data
│   ├── forex_correlation_model.py # Currency correlation analysis
│   ├── sec_13f_fetcher.py        # SEC EDGAR 13F tracker
│   └── portfolio_manager.py      # Portfolio tracking
│
├── flask_app/                    # REST API Backend
│   ├── Dockerfile                # trading-api:latest image
│   ├── app/
│   │   ├── routes/               # 13 route blueprints
│   │   ├── services/             # Business logic
│   │   └── utils/                # Database, auth, helpers
│   └── requirements.txt
│
├── Dockerfile.airflow            # airflow-trading:latest image
│
├── frontend/                     # Vanilla JS Dashboard
│   ├── index.html
│   ├── app.js, auth.js, dashboard.js, trading.js,
│   │   reports.js, watchlist.js, earnings.js, longterm.js,
│   │   indicators.js, forex.js, portfolio.js
│   └── styles.css                # Dark theme (~5000 lines)
│
├── kubernetes/                   # K8s Manifests & Schemas
│   ├── scripts/                  # Deployment phase scripts
│   │   ├── phase0-setup-k0s.sh
│   │   ├── phase1-deploy-flask.sh
│   │   ├── phase2-deploy-airflow.sh
│   │   └── phase3-migrate-postgres.sh
│   ├── api-deployment.yaml       # Flask API (1-3 replicas, HPA)
│   ├── api-service.yaml          # NodePort 30427
│   ├── airflow/                  # Scheduler, webserver, postgres
│   │   └── dags/                 # 10 Airflow DAGs
│   ├── redis-deployment.yaml
│   ├── postgres-timeseries-deployment.yaml  # TimescaleDB
│   ├── persistent-volume.yaml    # hostPath PVs
│   ├── secrets.yaml
│   ├── configmap.yaml
│   └── schema_*.sql              # 7 schema files (106 tables)
│
└── docs/                         # Documentation
    ├── ARCHITECTURE.md
    ├── DATA_ARCHITECTURE.md
    ├── DEPLOYMENT.md
    └── other/security/
        └── trading-db-key.pem    # EC2 SSH key
```

## Deployment

Fully containerized on **k0s** (lightweight Kubernetes) running on a single EC2 instance.

### Infrastructure
| Component | Details |
|-----------|---------|
| **Cluster** | k0s v1.34.3, single-node (controller + worker) |
| **Node** | EC2 (2 CPU, 8GB RAM, 49GB disk) at 3.140.78.15 |
| **Domain** | alphabreak.vip with SSL (Let's Encrypt + Nginx) |
| **Namespace** | `trading-system` |

### Running Pods
| Pod | Purpose |
|-----|---------|
| `trading-api` | Flask API (NodePort 30427, HPA 1-3 replicas) |
| `timeseries-postgres` | TimescaleDB with 106 tables, 5 hypertables, ~8GB |
| `airflow-scheduler` | Airflow scheduler (KubernetesExecutor) |
| `airflow-webserver` | Airflow UI (NodePort 30880) |
| `airflow-postgres` | Airflow metadata DB |
| `redis` | Caching and rate limiting |

### Airflow DAGs (10 Active)
| DAG | Schedule | Purpose |
|-----|----------|---------|
| `crypto_10min_analysis` | Every 10 min | BTC/ETH trading signals |
| `trend_break_10min_report` | Every 10 min | High-frequency trend breaks |
| `sp500_hourly_analysis` | Hourly | S&P 500 predictions |
| `trend_break_hourly_report` | Hourly | Hourly trend break report |
| `trend_break_daily_report` | Daily | Daily trend break summary |
| `indicator_analysis_dag` | Daily 2 AM | Indicator accuracy tracking |
| `portfolio_update` | Daily | Portfolio signal generation |
| `model_retraining_pipeline` | Weekly Sun 3 AM | ML model retraining |
| `backtest_dag` | Monthly 1st, 4 AM | Strategy backtesting |
| `portfolio_sync_onetime` | One-time | Portfolio data sync |

### Docker Images
```bash
# Build and import images (run on EC2)
cd ~/Securities_prediction_model

# Flask API
sudo docker build -f flask_app/Dockerfile -t trading-api:latest .
sudo docker save trading-api:latest | sudo k0s ctr images import -

# Airflow
sudo docker build -f Dockerfile.airflow -t airflow-trading:latest .
sudo docker save airflow-trading:latest | sudo k0s ctr images import -

# Always clean up after builds (disk is tight)
sudo docker system prune -af
```

### Connecting
```bash
# SSH to EC2
ssh -i "docs/other/security/trading-db-key.pem" ubuntu@3.140.78.15

# Check pods
sudo k0s kubectl get pods -n trading-system

# API logs
sudo k0s kubectl logs -n trading-system deployment/trading-api --tail=50

# Airflow UI (port-forward or use NodePort 30880)
sudo k0s kubectl port-forward svc/airflow-webserver 8080:8080 -n trading-system
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

### Market Data
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | API health check |
| GET | `/api/dashboard/market-sentiment` | Market sentiment overview |
| GET | `/api/dashboard/sector-sentiment` | Sector analysis |
| GET | `/api/reports/latest` | Latest trend break reports |
| GET | `/api/earnings/calendar` | Earnings calendar (top 100 tickers) |
| GET | `/api/earnings/ticker/<ticker>` | Detailed earnings + CBOE data |
| GET | `/api/forex/correlations` | Currency pair correlations |
| GET | `/api/forex/trend-breaks` | Forex trend break signals |
| GET | `/api/forex/usd-chart` | USD pairs chart data |
| GET | `/api/longterm/holdings` | Long-term position analysis |

### Portfolio
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/portfolio/summary` | Portfolio overview |
| GET | `/api/portfolio/holdings` | Current positions |
| GET | `/api/portfolio/trades` | Trade history |
| GET | `/api/portfolio/snapshots` | Historical snapshots |

## Database

**106 tables** in TimescaleDB (PostgreSQL 15 + TimescaleDB 2.24.0), including:

### Hypertables (Time-Series)
| Table | Rows | Chunks | Description |
|-------|------|--------|-------------|
| `stock_prices_intraday` | 5.6M | 730 | Intraday OHLCV |
| `stock_prices` | 4.1M | 3,344 | Daily OHLCV |
| `trend_breaks` | 4.0M | 781 | Detected trend breaks |
| `trend_ranges` | 4.0M | 261 | Trend range data |
| `market_indices` | 15K | 317 | S&P 500, DJI, VIX |

### Key Regular Tables
| Table | Description |
|-------|-------------|
| `f13_archive_holdings` | 8.4M rows of 13F institutional holdings |
| `darkpool_weekly_volume` | 621K rows of dark pool data |
| `forex_daily_data` | 123K rows of forex OHLCV (21 pairs, 54 years) |
| `forex_correlations` | Currency pair correlation matrix |
| `forex_trend_breaks` | Forex trend break signals |
| `earnings_calendar` | Earnings dates and EPS data |
| `users` / `refresh_tokens` | JWT auth tables |

## Environment Variables

```bash
# Flask
FLASK_ENV=production
SECRET_KEY=<secret>
API_KEY_REQUIRED=false    # Set to 'true' to require X-API-Key header

# Database (TimescaleDB in k0s)
TIMESERIES_DB_HOST=postgres-timeseries-service
TIMESERIES_DB_PORT=5432
TIMESERIES_DB_NAME=trading_data
TIMESERIES_DB_USER=trading
TIMESERIES_DB_PASSWORD=<password>

# Redis
REDIS_URL=redis://redis-service:6379/0

# JWT (optional - has dev defaults)
JWT_SECRET_KEY=<jwt-secret>
```

## Key Technical Features

### Machine Learning Models
| Model | Purpose | Algorithm |
|-------|---------|-----------|
| Indicator Reliability | Predict which indicators work in current regime | Dense NN (Keras) |
| Trend Break Detection | Predict when trend breaks will occur | XGBoost / LightGBM |
| Options Pricing | Black-Scholes & Binomial Tree | Analytical |

### Technical Indicators (25+)
RSI, MACD, ADX, Stochastic, Bollinger Bands, SuperTrend, OBV, VPT, CMF, MFI, VWAP, ATR, CCI, EMA, SMA, and more.

### 13F Institutional Holdings
Tracks 20 major hedge funds (Berkshire, Bridgewater, Renaissance, Citadel, etc.) via SEC EDGAR quarterly filings.

### Forex Correlation Model
21 currency pairs with up to 54 years of historical data from FRED. Tracks USD correlations, equity cross-correlations, and trend break signals.

## Roadmap

- [x] Database integration (PostgreSQL/TimescaleDB)
- [x] Multi-timeframe models (5min, 1hr, daily)
- [x] 13F report analysis (8.4M archive rows)
- [x] Forex correlation model (21 pairs, 54 years)
- [x] User authentication (JWT + bcrypt)
- [x] Live web dashboard (9 tabs)
- [x] SSL/HTTPS (Let's Encrypt)
- [x] Airflow automation (10 DAGs, KubernetesExecutor)
- [x] Dark pool data pipeline
- [x] Portfolio tracker (paper trading)
- [x] Kubernetes containerization (k0s, full migration)
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

## License

MIT

---

**Last Updated**: April 2, 2026
**Version**: 2.0.0
**Status**: Production (Kubernetes)
