# Securities Prediction Model

A comprehensive trading prediction system that identifies high-probability short-term trading opportunities using technical indicators, machine learning, and options pricing analysis.

## Overview

This application analyzes securities to predict trend breaks and identify mispriced options, enabling informed swing trading decisions. The system uses a multi-stage approach:

1. **Meta-Learning Stage** - Determines which technical indicators are most reliable under current market conditions
2. **Prediction Stage** - Uses XGBoost/LightGBM to predict when trend breaks will occur
3. **Options Analysis Stage** - Identifies mispriced options aligned with predicted trends

## Architecture

```
src/
├── data_fetcher.py           # Stock data retrieval (yfinance)
├── technical_indicators.py   # 25+ indicators using pandas_ta
├── trend_analysis.py         # Trend break detection & accuracy analysis
├── meta_learning_model.py    # Indicator reliability prediction (multi-timeframe)
├── models.py                 # XGBoost, LightGBM, LSTM, Dense NN
├── options_pricing.py        # Black-Scholes & Binomial Tree pricing
├── populate_market_indices.py # Market indices & ETF data population
├── sec_13f_fetcher.py        # SEC EDGAR 13F institutional holdings tracker
└── scheduled_runner.py       # Automated daily analysis
```

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
- CUSIP-to-ticker mapping via SEC company data

### Options Pricing
- **Binomial Tree** (American options) - Recommended for US stocks
- **Black-Scholes** (European options) - For indices, some ETFs
- Dynamic risk-free rate from Treasury yields
- Greeks calculation (Delta, Gamma, Theta, Vega, Rho)
- Trend-aligned option filtering for swing trading

## Installation

```bash
pip install -r requirements.txt
```

Required packages:
- pandas, numpy, scipy
- pandas_ta (technical indicators)
- yfinance (market data)
- xgboost, lightgbm (gradient boosting)
- tensorflow/keras (neural networks)
- scikit-learn (utilities)

## Quick Start

```python
from src import (
    get_stock_data,
    calculate_rsi, calculate_macd,
    trend_break, feature_engineering,
    train_xgboost_model,
    analyze_option_pricing
)

# 1. Fetch data and calculate indicators
data = get_stock_data('AAPL', '2023-01-01', '2024-01-01')

# 2. Detect trend breaks
breaks = trend_break(data, 'Close', 'direction')

# 3. Train prediction model
model, metrics = train_xgboost_model(X_train, y_train, X_test, y_test)

# 4. Analyze options (American pricing by default)
results = analyze_option_pricing(
    'AAPL', '2023-01-01', '2024-01-15',
    pricing_model='american',
    trend_direction='bullish'
)
underpriced = results[results['recommendation'] == 'UNDERPRICED']
```

## Project Structure

```
Securities_prediction_model/
├── src/                    # Production modules
├── docs/
│   └── code_snippets/     # Reference implementations & development history
├── flask_app/             # Web API (in development)
├── frontend/              # UI (in development)
├── kubernetes/            # Deployment configs (PostgreSQL/TimescaleDB)
└── requirements.txt
```

### Database Schema (PostgreSQL/TimescaleDB)

| Table | Description |
|-------|-------------|
| `stock_data` | Daily/intraday OHLCV for individual stocks |
| `market_indices` | Daily data for S&P 500, DJI, VIX, futures, inverse ETFs |
| `market_indices_intraday` | 5min/1hr data for market ETFs |
| `hedge_fund_managers` | 20 tracked institutional investors |
| `f13_filings` | Quarterly 13F filing metadata |
| `f13_holdings` | Individual holdings per filing with Q/Q changes |
| `f13_stock_aggregates` | Per-stock aggregate institutional sentiment |
| `cusip_ticker_map` | CUSIP to ticker symbol mappings |

## Usage Notes

### American vs European Options
Most US stock options are **American** (exercise anytime). Use `binomial_tree_american()` for accurate pricing. Black-Scholes underprices American options, especially:
- Puts when stock price drops significantly
- Calls on dividend-paying stocks

### Model Selection
- **XGBoost/LightGBM**: Best for indicator-based tabular data
- **LSTM**: Best for pure time-series with temporal dependencies
- **Dense NN**: Good for meta-learning (predicting indicator accuracy)

### Dynamic Risk-Free Rate
The system automatically fetches current Treasury yields:
- <3 months to expiry: 13-week T-bill (^IRX)
- 3-6 months: 5-year Treasury (^FVX)
- >6 months: 10-year Treasury (^TNX)

## Roadmap

- [x] Database integration for historical data storage (PostgreSQL/TimescaleDB)
- [x] Multi-timeframe models (5min, 1hr, daily)
- [x] 13F report analysis (SEC hedge fund holdings)
- [x] Market indices & ETF tracking
- [ ] Airflow service for scheduled analysis
- [ ] Push notifications for high-probability trades
- [ ] Visualizations dashboard

## License

MIT
