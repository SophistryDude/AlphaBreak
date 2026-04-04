"""
Analyze Service
===============
Single-ticker deep-dive data for the Analyze tab.

Aggregates:
- Company info + key stats (from yfinance .info)
- Price + daily change
- Trend break probability
- Technical indicators with buy/sell signals
- Options summary
- Analyst consensus + price targets
- Earnings (last 4 quarters)
- 13F institutional ownership
- Sector sentiment
- Enhanced chart data (multiple timeframes)

Used by:
- flask_app/app/routes/analyze.py
"""

import logging
import time
from datetime import datetime
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────

def fetch_analyze_data(ticker: str, db_manager=None) -> Dict:
    """
    Fetch all analyze-tab data for a single ticker.

    Returns dict with: header, stats, trend_break, indicators, options,
    analyst, earnings, institutional, sector.
    """
    import yfinance as yf
    from app.services.watchlist_service import (
        _get_trend_break_data, _get_options_summary, _safe_float,
    )
    from app.services.dashboard_service import (
        _calculate_cci, _calculate_stochastic, _calculate_rsi,
        _calculate_sma, _calculate_adx,
    )
    from app.services.report_service import TICKER_SECTOR_MAP, SECTOR_ETFS
    from app.services.watchlist_service import _compute_sector_sentiment_cached

    stock = yf.Ticker(ticker)

    # Fetch price history (3 months daily for indicators)
    df = stock.history(period='3mo', interval='1d')
    if df.empty or len(df) < 5:
        raise ValueError(f"Insufficient price data for {ticker}")

    df = df.reset_index()
    if 'Date' in df.columns:
        df = df.rename(columns={'Date': 'date'})

    current_price = float(df['Close'].iloc[-1])
    prev_close = float(df['Close'].iloc[-2]) if len(df) > 1 else current_price

    # Fetch .info (cached by yfinance internally)
    try:
        info = stock.info or {}
    except Exception:
        info = {}

    result = {
        'ticker': ticker,
        'fetched_at': datetime.utcnow().isoformat(),
    }

    # ── Header ────────────────────────────────────────────────────────────
    price_change = current_price - prev_close
    price_change_pct = (price_change / prev_close * 100) if prev_close else 0.0

    result['header'] = {
        'name': info.get('longName') or info.get('shortName') or ticker,
        'sector': info.get('sector'),
        'industry': info.get('industry'),
        'exchange': info.get('exchange'),
        'currency': info.get('currency', 'USD'),
        'price': round(current_price, 2),
        'previous_close': round(prev_close, 2),
        'change': round(price_change, 2),
        'change_pct': round(price_change_pct, 2),
        'fifty_two_week_high': _safe_val(info.get('fiftyTwoWeekHigh')),
        'fifty_two_week_low': _safe_val(info.get('fiftyTwoWeekLow')),
        'day_high': _safe_val(info.get('dayHigh')),
        'day_low': _safe_val(info.get('dayLow')),
        'open': _safe_val(info.get('open')),
        'volume': info.get('volume'),
        'avg_volume': info.get('averageVolume'),
    }

    # ── Key Stats ─────────────────────────────────────────────────────────
    result['stats'] = {
        'market_cap': info.get('marketCap'),
        'pe_ratio': _safe_val(info.get('trailingPE')),
        'forward_pe': _safe_val(info.get('forwardPE')),
        'peg_ratio': _safe_val(info.get('pegRatio')),
        'ps_ratio': _safe_val(info.get('priceToSalesTrailing12Months')),
        'pb_ratio': _safe_val(info.get('priceToBook')),
        'ev_ebitda': _safe_val(info.get('enterpriseToEbitda')),
        'eps': _safe_val(info.get('trailingEps')),
        'forward_eps': _safe_val(info.get('forwardEps')),
        'dividend_yield': _safe_val(info.get('dividendYield')),
        'dividend_rate': _safe_val(info.get('dividendRate')),
        'beta': _safe_val(info.get('beta')),
        'shares_outstanding': info.get('sharesOutstanding'),
        'float_shares': info.get('floatShares'),
        'short_ratio': _safe_val(info.get('shortRatio')),
        'short_pct_float': _safe_val(info.get('shortPercentOfFloat')),
        'insider_pct': _safe_val(info.get('heldPercentInsiders')),
        'institution_pct': _safe_val(info.get('heldPercentInstitutions')),
        'roe': _safe_val(info.get('returnOnEquity')),
        'profit_margin': _safe_val(info.get('profitMargins')),
        'revenue_growth': _safe_val(info.get('revenueGrowth')),
        'earnings_growth': _safe_val(info.get('earningsGrowth')),
        'operating_margin': _safe_val(info.get('operatingMargins')),
        'gross_margin': _safe_val(info.get('grossMargins')),
        'debt_to_equity': _safe_val(info.get('debtToEquity')),
        'current_ratio': _safe_val(info.get('currentRatio')),
        'revenue': info.get('totalRevenue'),
        'ebitda': info.get('ebitda'),
        'free_cash_flow': info.get('freeCashflow'),
    }

    # ── Trend Break ───────────────────────────────────────────────────────
    result['trend_break'] = _get_trend_break_data(ticker, df, db_manager)

    # ── Indicators + Signals ──────────────────────────────────────────────
    indicators = {}
    signals = {}
    if len(df) >= 20:
        try:
            cci_series = _calculate_cci(df)
            cci = _safe_float(cci_series.iloc[-1], 2)
            indicators['cci'] = cci
            signals['cci'] = _signal_from_cci(cci)

            stoch_k, stoch_d = _calculate_stochastic(df)
            k_val = _safe_float(stoch_k.iloc[-1], 2)
            d_val = _safe_float(stoch_d.iloc[-1], 2)
            indicators['stochastic_k'] = k_val
            indicators['stochastic_d'] = d_val
            signals['stochastic'] = _signal_from_stochastic(k_val)

            rsi_series = _calculate_rsi(df)
            rsi = _safe_float(rsi_series.iloc[-1], 2)
            indicators['rsi'] = rsi
            signals['rsi'] = _signal_from_rsi(rsi)

            sma_20 = _safe_float(_calculate_sma(df['Close'], 20).iloc[-1], 4)
            indicators['sma_20'] = sma_20

            sma_50 = None
            if len(df) >= 50:
                sma_50 = _safe_float(_calculate_sma(df['Close'], 50).iloc[-1], 4)
                indicators['sma_50'] = sma_50

            if sma_20 is not None and sma_50 is not None:
                signals['sma_cross'] = 'BULLISH' if sma_20 > sma_50 else 'BEARISH'

            adx_series, _, _ = _calculate_adx(df)
            adx = _safe_float(adx_series.iloc[-1], 2)
            indicators['adx'] = adx
            signals['adx'] = 'STRONG TREND' if adx and adx > 25 else 'WEAK TREND'

        except Exception as e:
            logger.warning(f"Indicator calc failed for {ticker}: {e}")

    # Composite signal: majority vote of directional signals
    signals['composite'] = _compute_composite_signal(signals)

    result['indicators'] = indicators
    result['signals'] = signals

    # ── Analyst Consensus ─────────────────────────────────────────────────
    result['analyst'] = {
        'recommendation': info.get('recommendationKey'),
        'recommendation_mean': _safe_val(info.get('recommendationMean')),
        'num_analysts': info.get('numberOfAnalystOpinions'),
        'target_high': _safe_val(info.get('targetHighPrice')),
        'target_low': _safe_val(info.get('targetLowPrice')),
        'target_mean': _safe_val(info.get('targetMeanPrice')),
        'target_median': _safe_val(info.get('targetMedianPrice')),
    }

    # ── Options Summary ───────────────────────────────────────────────────
    result['options'] = _get_options_summary(stock, current_price)

    # ── Earnings (last 4 quarters from yfinance) ──────────────────────────
    result['earnings'] = _get_earnings_data(stock, info)

    # ── Institutional / 13F ───────────────────────────────────────────────
    result['institutional'] = _get_institutional_data(ticker, info, db_manager)

    # ── Sector Sentiment ──────────────────────────────────────────────────
    sector_name = TICKER_SECTOR_MAP.get(ticker) or info.get('sector')
    sector_etf = SECTOR_ETFS.get(sector_name) if sector_name else None
    sector_sentiment = {'sentiment': 'NEUTRAL', 'confidence': 0}
    if sector_name and sector_etf:
        sector_sentiment = _compute_sector_sentiment_cached(sector_name, sector_etf)

    result['sector'] = {
        'name': sector_name,
        'etf': sector_etf,
        'sentiment': sector_sentiment.get('sentiment', 'NEUTRAL'),
        'confidence': sector_sentiment.get('confidence', 0),
    }

    return result


def fetch_enhanced_chart(ticker: str, interval: str = '1d', period: str = '3mo') -> Dict:
    """
    Fetch OHLCV chart data with support/resistance for extended timeframes.

    Supported periods: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, max
    Supported intervals: 1m, 5m, 15m, 1h, 1d, 1wk, 1mo
    """
    import yfinance as yf
    from app.services.watchlist_service import _detect_peaks, _detect_troughs

    # Validate and map combinations
    VALID_COMBOS = {
        # period -> allowed intervals
        '1d': ['1m', '5m', '15m'],
        '5d': ['5m', '15m', '1h'],
        '1mo': ['1h', '1d'],
        '3mo': ['1d'],
        '6mo': ['1d', '1wk'],
        '1y': ['1d', '1wk'],
        '2y': ['1wk'],
        '5y': ['1wk', '1mo'],
        'max': ['1mo'],
    }

    if period not in VALID_COMBOS:
        period = '3mo'
    if interval not in VALID_COMBOS.get(period, ['1d']):
        interval = VALID_COMBOS[period][0]

    stock = yf.Ticker(ticker)
    hist = stock.history(period=period, interval=interval)

    if hist.empty:
        return {'data': [], 'peaks': [], 'troughs': [], 'period': period, 'interval': interval}

    hist = hist.reset_index()
    ts_col = 'Date' if 'Date' in hist.columns else 'Datetime' if 'Datetime' in hist.columns else hist.columns[0]

    chart_data = []
    for _, row in hist.iterrows():
        ts = row[ts_col]
        chart_data.append({
            'timestamp': ts.isoformat() if hasattr(ts, 'isoformat') else str(ts),
            'open': round(float(row['Open']), 4),
            'high': round(float(row['High']), 4),
            'low': round(float(row['Low']), 4),
            'close': round(float(row['Close']), 4),
            'volume': int(row['Volume']),
        })

    closes = [d['close'] for d in chart_data]
    peaks = _detect_peaks(closes, chart_data)
    troughs = _detect_troughs(closes, chart_data)

    return {
        'data': chart_data,
        'peaks': peaks,
        'troughs': troughs,
        'period': period,
        'interval': interval,
    }


def search_tickers(query: str) -> List[Dict]:
    """
    Search for tickers by symbol or company name prefix.
    Returns top 10 matches.
    """
    if not query or len(query) < 1:
        return []

    query = query.upper().strip()
    matches = []

    for symbol, name, sector in _get_ticker_list():
        if symbol.startswith(query) or query in name.upper():
            matches.append({
                'ticker': symbol,
                'name': name,
                'sector': sector,
            })
            if len(matches) >= 10:
                break

    return matches


# ──────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────────────────────────────────────

def _safe_val(val):
    """Convert to Python float/int safely, None for NaN/None."""
    if val is None:
        return None
    try:
        f = float(val)
        if np.isnan(f) or np.isinf(f):
            return None
        return round(f, 4) if f != int(f) else int(f)
    except (TypeError, ValueError):
        return None


def _signal_from_rsi(rsi):
    if rsi is None:
        return 'NEUTRAL'
    if rsi < 30:
        return 'BUY'
    if rsi > 70:
        return 'SELL'
    return 'NEUTRAL'


def _signal_from_cci(cci):
    if cci is None:
        return 'NEUTRAL'
    if cci < -100:
        return 'BUY'
    if cci > 100:
        return 'SELL'
    return 'NEUTRAL'


def _signal_from_stochastic(k):
    if k is None:
        return 'NEUTRAL'
    if k < 20:
        return 'BUY'
    if k > 80:
        return 'SELL'
    return 'NEUTRAL'


def _compute_composite_signal(signals: Dict) -> str:
    """Majority vote across directional signals."""
    buy = 0
    sell = 0
    for key in ('rsi', 'cci', 'stochastic'):
        sig = signals.get(key)
        if sig == 'BUY':
            buy += 1
        elif sig == 'SELL':
            sell += 1

    sma = signals.get('sma_cross')
    if sma == 'BULLISH':
        buy += 1
    elif sma == 'BEARISH':
        sell += 1

    if buy > sell:
        return 'BULLISH'
    if sell > buy:
        return 'BEARISH'
    return 'NEUTRAL'


def _get_earnings_data(stock, info: Dict) -> Dict:
    """Get last 4 quarters earnings + next earnings date."""
    result = {
        'next_date': None,
        'quarters': [],
    }

    # Next earnings date
    try:
        import datetime as dt
        cal = stock.calendar
        if cal is not None:
            if isinstance(cal, dict):
                ed = cal.get('Earnings Date')
                if ed and isinstance(ed, list) and len(ed) > 0:
                    result['next_date'] = ed[0].isoformat() if hasattr(ed[0], 'isoformat') else str(ed[0])
                elif ed and hasattr(ed, 'isoformat'):
                    result['next_date'] = ed.isoformat()
            elif isinstance(cal, pd.DataFrame) and not cal.empty:
                if 'Earnings Date' in cal.columns:
                    val = cal['Earnings Date'].iloc[0]
                    result['next_date'] = val.isoformat() if hasattr(val, 'isoformat') else str(val)
    except Exception as e:
        logger.debug(f"Earnings calendar fetch failed: {e}")

    # Last 4 quarters
    try:
        earnings = stock.earnings_history
        if earnings is not None and not earnings.empty:
            recent = earnings.tail(4).iloc[::-1]  # most recent first
            for _, row in recent.iterrows():
                q = {}
                for col in recent.columns:
                    val = row[col]
                    if hasattr(val, 'isoformat'):
                        q[col] = val.isoformat()
                    elif isinstance(val, (int, float)):
                        q[col] = None if (isinstance(val, float) and np.isnan(val)) else val
                    else:
                        q[col] = str(val) if val is not None else None
                result['quarters'].append(q)
    except Exception as e:
        logger.debug(f"Earnings history fetch failed: {e}")

    return result


def _get_institutional_data(ticker: str, info: Dict, db_manager) -> Dict:
    """Get institutional ownership data from 13F + yfinance."""
    result = {
        'pct_held': _safe_val(info.get('heldPercentInstitutions')),
        'top_holders': [],
    }

    # Try getting top holders from yfinance
    try:
        import yfinance as yf
        stock = yf.Ticker(ticker)
        holders = stock.institutional_holders
        if holders is not None and not holders.empty:
            for _, row in holders.head(10).iterrows():
                holder = {}
                for col in holders.columns:
                    val = row[col]
                    if hasattr(val, 'isoformat'):
                        holder[col] = val.isoformat()
                    elif isinstance(val, (int, float)):
                        holder[col] = None if (isinstance(val, float) and np.isnan(val)) else val
                    else:
                        holder[col] = str(val) if val is not None else None
                result['top_holders'].append(holder)
    except Exception as e:
        logger.debug(f"Institutional holders fetch failed: {e}")

    # 13F data from our DB
    if db_manager:
        try:
            query = """
                SELECT fund_name, shares, value, report_date
                FROM thirteen_f_holdings
                WHERE ticker = %s
                ORDER BY report_date DESC
                LIMIT 10
            """
            rows = db_manager.execute_query(query, (ticker,))
            if rows:
                result['thirteen_f'] = [
                    {
                        'fund': row[0],
                        'shares': row[1],
                        'value': row[2],
                        'report_date': row[3].isoformat() if hasattr(row[3], 'isoformat') else str(row[3]),
                    }
                    for row in rows
                ]
        except Exception as e:
            logger.debug(f"13F query failed for {ticker}: {e}")

    return result


# ── Ticker list for autocomplete ──────────────────────────────────────────────

_ticker_list_cache = None

def _get_ticker_list() -> List[tuple]:
    """
    Return list of (symbol, name, sector) tuples for autocomplete.
    Cached in memory after first load.
    """
    global _ticker_list_cache
    if _ticker_list_cache is not None:
        return _ticker_list_cache

    # Build from well-known tickers. In production this would come from DB.
    tickers = _build_default_ticker_list()
    _ticker_list_cache = tickers
    return tickers


def _build_default_ticker_list() -> List[tuple]:
    """Build a default ticker list from S&P 500 + popular tickers."""
    # Top ~100 most commonly searched tickers with names
    return [
        ('AAPL', 'Apple Inc', 'Technology'),
        ('MSFT', 'Microsoft Corp', 'Technology'),
        ('AMZN', 'Amazon.com Inc', 'Consumer Cyclical'),
        ('NVDA', 'NVIDIA Corp', 'Technology'),
        ('GOOGL', 'Alphabet Inc Class A', 'Technology'),
        ('GOOG', 'Alphabet Inc Class C', 'Technology'),
        ('META', 'Meta Platforms Inc', 'Technology'),
        ('TSLA', 'Tesla Inc', 'Consumer Cyclical'),
        ('BRK-B', 'Berkshire Hathaway B', 'Financial Services'),
        ('UNH', 'UnitedHealth Group', 'Healthcare'),
        ('JNJ', 'Johnson & Johnson', 'Healthcare'),
        ('JPM', 'JPMorgan Chase', 'Financial Services'),
        ('V', 'Visa Inc', 'Financial Services'),
        ('XOM', 'Exxon Mobil Corp', 'Energy'),
        ('PG', 'Procter & Gamble', 'Consumer Defensive'),
        ('MA', 'Mastercard Inc', 'Financial Services'),
        ('HD', 'Home Depot Inc', 'Consumer Cyclical'),
        ('CVX', 'Chevron Corp', 'Energy'),
        ('MRK', 'Merck & Co', 'Healthcare'),
        ('ABBV', 'AbbVie Inc', 'Healthcare'),
        ('LLY', 'Eli Lilly & Co', 'Healthcare'),
        ('PEP', 'PepsiCo Inc', 'Consumer Defensive'),
        ('KO', 'Coca-Cola Co', 'Consumer Defensive'),
        ('AVGO', 'Broadcom Inc', 'Technology'),
        ('COST', 'Costco Wholesale', 'Consumer Defensive'),
        ('WMT', 'Walmart Inc', 'Consumer Defensive'),
        ('MCD', 'McDonald\'s Corp', 'Consumer Cyclical'),
        ('CSCO', 'Cisco Systems', 'Technology'),
        ('TMO', 'Thermo Fisher Scientific', 'Healthcare'),
        ('ACN', 'Accenture plc', 'Technology'),
        ('ABT', 'Abbott Laboratories', 'Healthcare'),
        ('DHR', 'Danaher Corp', 'Healthcare'),
        ('NEE', 'NextEra Energy', 'Utilities'),
        ('DIS', 'Walt Disney Co', 'Communication Services'),
        ('VZ', 'Verizon Communications', 'Communication Services'),
        ('ADBE', 'Adobe Inc', 'Technology'),
        ('NFLX', 'Netflix Inc', 'Communication Services'),
        ('CRM', 'Salesforce Inc', 'Technology'),
        ('INTC', 'Intel Corp', 'Technology'),
        ('AMD', 'Advanced Micro Devices', 'Technology'),
        ('QCOM', 'Qualcomm Inc', 'Technology'),
        ('TXN', 'Texas Instruments', 'Technology'),
        ('INTU', 'Intuit Inc', 'Technology'),
        ('IBM', 'International Business Machines', 'Technology'),
        ('ORCL', 'Oracle Corp', 'Technology'),
        ('NOW', 'ServiceNow Inc', 'Technology'),
        ('AMAT', 'Applied Materials', 'Technology'),
        ('LRCX', 'Lam Research', 'Technology'),
        ('MU', 'Micron Technology', 'Technology'),
        ('BA', 'Boeing Co', 'Industrials'),
        ('CAT', 'Caterpillar Inc', 'Industrials'),
        ('GE', 'GE Aerospace', 'Industrials'),
        ('RTX', 'RTX Corp', 'Industrials'),
        ('HON', 'Honeywell International', 'Industrials'),
        ('UNP', 'Union Pacific Corp', 'Industrials'),
        ('GS', 'Goldman Sachs', 'Financial Services'),
        ('MS', 'Morgan Stanley', 'Financial Services'),
        ('BLK', 'BlackRock Inc', 'Financial Services'),
        ('C', 'Citigroup Inc', 'Financial Services'),
        ('BAC', 'Bank of America', 'Financial Services'),
        ('WFC', 'Wells Fargo', 'Financial Services'),
        ('SCHW', 'Charles Schwab', 'Financial Services'),
        ('AXP', 'American Express', 'Financial Services'),
        ('SPGI', 'S&P Global', 'Financial Services'),
        ('PFE', 'Pfizer Inc', 'Healthcare'),
        ('BMY', 'Bristol-Myers Squibb', 'Healthcare'),
        ('AMGN', 'Amgen Inc', 'Healthcare'),
        ('GILD', 'Gilead Sciences', 'Healthcare'),
        ('SYK', 'Stryker Corp', 'Healthcare'),
        ('MDT', 'Medtronic plc', 'Healthcare'),
        ('T', 'AT&T Inc', 'Communication Services'),
        ('CMCSA', 'Comcast Corp', 'Communication Services'),
        ('TMUS', 'T-Mobile US', 'Communication Services'),
        ('COP', 'ConocoPhillips', 'Energy'),
        ('SLB', 'Schlumberger NV', 'Energy'),
        ('EOG', 'EOG Resources', 'Energy'),
        ('SO', 'Southern Company', 'Utilities'),
        ('DUK', 'Duke Energy', 'Utilities'),
        ('D', 'Dominion Energy', 'Utilities'),
        ('SPY', 'SPDR S&P 500 ETF', 'ETF'),
        ('QQQ', 'Invesco QQQ Trust', 'ETF'),
        ('IWM', 'iShares Russell 2000', 'ETF'),
        ('DIA', 'SPDR Dow Jones ETF', 'ETF'),
        ('TQQQ', 'ProShares UltraPro QQQ', 'ETF'),
        ('SQQQ', 'ProShares UltraPro Short QQQ', 'ETF'),
        ('VTI', 'Vanguard Total Stock', 'ETF'),
        ('ARKK', 'ARK Innovation ETF', 'ETF'),
        ('XLF', 'Financial Select Sector', 'ETF'),
        ('XLE', 'Energy Select Sector', 'ETF'),
        ('XLK', 'Technology Select Sector', 'ETF'),
        ('XLV', 'Health Care Select Sector', 'ETF'),
        ('GLD', 'SPDR Gold Shares', 'ETF'),
        ('SLV', 'iShares Silver Trust', 'ETF'),
        ('TSLY', 'YieldMax TSLA Option Income', 'ETF'),
        ('PLTR', 'Palantir Technologies', 'Technology'),
        ('SOFI', 'SoFi Technologies', 'Financial Services'),
        ('RIVN', 'Rivian Automotive', 'Consumer Cyclical'),
        ('LCID', 'Lucid Group', 'Consumer Cyclical'),
        ('NIO', 'NIO Inc', 'Consumer Cyclical'),
        ('COIN', 'Coinbase Global', 'Financial Services'),
        ('MARA', 'Marathon Digital', 'Financial Services'),
        ('ARM', 'Arm Holdings', 'Technology'),
        ('SMCI', 'Super Micro Computer', 'Technology'),
    ]
