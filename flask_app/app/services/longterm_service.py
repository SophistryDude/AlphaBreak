"""
Long Term Trading Service
=========================
Provides data for the Long Term Trading tab:
- Institutional holdings from 13F filings (aggregated across hedge funds)
- Weekly performance comparison vs SPY, Gold, BTC
- Daily OHLC candlestick data
- Dividend / sector metadata

Used by: flask_app/app/routes/longterm.py
"""

import logging
import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import yfinance as yf

logger = logging.getLogger(__name__)

# Fallback institutional holdings when DB is unavailable
# These are commonly held by major hedge funds (approximate)
_FALLBACK_HOLDINGS = [
    {'ticker': 'AAPL', 'sector': 'Technology', 'has_dividend': True},
    {'ticker': 'MSFT', 'sector': 'Technology', 'has_dividend': True},
    {'ticker': 'NVDA', 'sector': 'Technology', 'has_dividend': True},
    {'ticker': 'AMZN', 'sector': 'Consumer Discretionary', 'has_dividend': False},
    {'ticker': 'META', 'sector': 'Communication Services', 'has_dividend': True},
    {'ticker': 'GOOGL', 'sector': 'Communication Services', 'has_dividend': False},
    {'ticker': 'BRK-B', 'sector': 'Financials', 'has_dividend': False},
    {'ticker': 'UNH', 'sector': 'Health Care', 'has_dividend': True},
    {'ticker': 'JPM', 'sector': 'Financials', 'has_dividend': True},
    {'ticker': 'V', 'sector': 'Financials', 'has_dividend': True},
    {'ticker': 'XOM', 'sector': 'Energy', 'has_dividend': True},
    {'ticker': 'JNJ', 'sector': 'Health Care', 'has_dividend': True},
    {'ticker': 'PG', 'sector': 'Consumer Staples', 'has_dividend': True},
    {'ticker': 'MA', 'sector': 'Financials', 'has_dividend': True},
    {'ticker': 'HD', 'sector': 'Consumer Discretionary', 'has_dividend': True},
    {'ticker': 'CVX', 'sector': 'Energy', 'has_dividend': True},
    {'ticker': 'MRK', 'sector': 'Health Care', 'has_dividend': True},
    {'ticker': 'ABBV', 'sector': 'Health Care', 'has_dividend': True},
    {'ticker': 'PEP', 'sector': 'Consumer Staples', 'has_dividend': True},
    {'ticker': 'COST', 'sector': 'Consumer Staples', 'has_dividend': True},
    {'ticker': 'AVGO', 'sector': 'Technology', 'has_dividend': True},
    {'ticker': 'KO', 'sector': 'Consumer Staples', 'has_dividend': True},
    {'ticker': 'WMT', 'sector': 'Consumer Staples', 'has_dividend': True},
    {'ticker': 'TSLA', 'sector': 'Consumer Discretionary', 'has_dividend': False},
    {'ticker': 'NFLX', 'sector': 'Communication Services', 'has_dividend': False},
    {'ticker': 'CRM', 'sector': 'Technology', 'has_dividend': False},
    {'ticker': 'AMD', 'sector': 'Technology', 'has_dividend': False},
    {'ticker': 'ADBE', 'sector': 'Technology', 'has_dividend': False},
    {'ticker': 'GS', 'sector': 'Financials', 'has_dividend': True},
    {'ticker': 'BA', 'sector': 'Industrials', 'has_dividend': True},
    {'ticker': 'CAT', 'sector': 'Industrials', 'has_dividend': True},
    {'ticker': 'GE', 'sector': 'Industrials', 'has_dividend': True},
    {'ticker': 'NEE', 'sector': 'Utilities', 'has_dividend': True},
    {'ticker': 'AMT', 'sector': 'Real Estate', 'has_dividend': True},
    {'ticker': 'LIN', 'sector': 'Materials', 'has_dividend': True},
]


# ──────────────────────────────────────────────────────────────────────────────
# 1. Institutional Holdings (13F)
# ──────────────────────────────────────────────────────────────────────────────

def fetch_top_institutional_holdings(db_manager=None, min_funds: int = 3,
                                     limit: int = 50) -> Dict:
    """
    Return top stocks held by the most hedge funds in the latest 13F quarter.
    Falls back to a curated list if DB is unavailable.
    """
    holdings = []
    report_quarter = None
    source = 'fallback'
    total_tracked_funds = 0

    if db_manager:
        try:
            holdings, report_quarter, total_tracked_funds = \
                _fetch_holdings_from_db(db_manager, min_funds, limit)
            if holdings:
                source = 'database'
        except Exception as e:
            logger.warning(f"DB holdings fetch failed, using fallback: {e}")

    if not holdings:
        holdings = _build_fallback_holdings()
        report_quarter = _estimate_current_quarter()
        source = 'fallback'

    return {
        'holdings': holdings[:limit],
        'report_quarter': report_quarter,
        'total_tracked_funds': total_tracked_funds,
        'source': source,
        'timestamp': datetime.utcnow().isoformat(),
    }


def _fetch_holdings_from_db(db_manager, min_funds, limit):
    """Query f13_stock_aggregates for latest quarter holdings."""
    query = """
        SELECT
            a.ticker,
            a.total_funds_holding,
            a.total_market_value,
            a.institutional_sentiment,
            a.pct_funds_holding,
            a.funds_initiated,
            a.funds_increased,
            a.funds_decreased,
            a.funds_sold,
            a.net_shares_change_pct,
            a.report_quarter,
            tm.sector,
            tm.industry,
            CASE WHEN EXISTS (
                SELECT 1 FROM corporate_actions ca
                WHERE ca.ticker = a.ticker
                AND ca.action_type = 'dividend'
                AND ca.ex_date > NOW() - INTERVAL '12 months'
            ) THEN TRUE ELSE FALSE END AS has_dividend
        FROM f13_stock_aggregates a
        LEFT JOIN ticker_metadata tm ON a.ticker = tm.ticker
        WHERE a.report_quarter = (
            SELECT report_quarter FROM f13_stock_aggregates
            ORDER BY report_quarter DESC LIMIT 1
        )
        AND a.total_funds_holding >= %s
        ORDER BY a.total_funds_holding DESC, a.institutional_sentiment DESC
        LIMIT %s
    """
    rows = db_manager.execute_query(query, (min_funds, limit))
    if not rows:
        return [], None, 0

    report_quarter = rows[0].get('report_quarter')

    # Get total tracked funds count
    count_query = """
        SELECT COUNT(DISTINCT cik) as cnt FROM hedge_fund_managers
    """
    count_rows = db_manager.execute_query(count_query)
    total_funds = count_rows[0]['cnt'] if count_rows else 0

    holdings = []
    for r in rows:
        holdings.append({
            'ticker': r['ticker'],
            'total_funds_holding': r.get('total_funds_holding', 0),
            'total_market_value': float(r.get('total_market_value') or 0),
            'institutional_sentiment': float(r.get('institutional_sentiment') or 0),
            'pct_funds_holding': float(r.get('pct_funds_holding') or 0),
            'funds_initiated': r.get('funds_initiated', 0),
            'funds_increased': r.get('funds_increased', 0),
            'funds_decreased': r.get('funds_decreased', 0),
            'funds_sold': r.get('funds_sold', 0),
            'net_shares_change_pct': float(r.get('net_shares_change_pct') or 0),
            'sector': r.get('sector') or 'Unknown',
            'industry': r.get('industry') or '',
            'has_dividend': bool(r.get('has_dividend')),
            'report_quarter': report_quarter,
        })

    return holdings, report_quarter, total_funds


def _build_fallback_holdings():
    """Build holdings from fallback list, enriched with live yfinance data."""
    holdings = []
    for item in _FALLBACK_HOLDINGS:
        try:
            t = yf.Ticker(item['ticker'])
            info = t.info or {}
            sector = info.get('sector', item.get('sector', 'Unknown'))
            industry = info.get('industry', '')
            has_dividend = info.get('dividendYield') is not None and info.get('dividendYield', 0) > 0
            if item.get('has_dividend'):
                has_dividend = True

            holdings.append({
                'ticker': item['ticker'],
                'total_funds_holding': None,
                'total_market_value': None,
                'institutional_sentiment': None,
                'pct_funds_holding': None,
                'funds_initiated': None,
                'funds_increased': None,
                'funds_decreased': None,
                'funds_sold': None,
                'net_shares_change_pct': None,
                'sector': sector,
                'industry': industry,
                'has_dividend': has_dividend,
                'report_quarter': _estimate_current_quarter(),
            })
        except Exception as e:
            logger.debug(f"Fallback ticker {item['ticker']} info failed: {e}")
            holdings.append({
                'ticker': item['ticker'],
                'total_funds_holding': None,
                'total_market_value': None,
                'institutional_sentiment': None,
                'pct_funds_holding': None,
                'funds_initiated': None,
                'funds_increased': None,
                'funds_decreased': None,
                'funds_sold': None,
                'net_shares_change_pct': None,
                'sector': item.get('sector', 'Unknown'),
                'industry': '',
                'has_dividend': item.get('has_dividend', False),
                'report_quarter': _estimate_current_quarter(),
            })
    return holdings


def _estimate_current_quarter():
    """Estimate the most recent 13F quarter label."""
    now = datetime.utcnow()
    month = now.month
    year = now.year
    if month <= 3:
        return f"Q4 {year - 1}"
    elif month <= 6:
        return f"Q1 {year}"
    elif month <= 9:
        return f"Q2 {year}"
    else:
        return f"Q3 {year}"


# ──────────────────────────────────────────────────────────────────────────────
# 2. Per-Ticker Fund Holdings
# ──────────────────────────────────────────────────────────────────────────────

def fetch_fund_holdings_for_ticker(ticker: str, db_manager=None) -> Dict:
    """Return which specific hedge funds hold a ticker and their position changes."""
    funds = []

    if db_manager:
        try:
            funds = _fetch_fund_detail_from_db(ticker, db_manager)
        except Exception as e:
            logger.warning(f"DB fund detail failed for {ticker}: {e}")

    if not funds:
        try:
            funds = _fetch_fund_detail_from_yfinance(ticker)
        except Exception as e:
            logger.warning(f"yfinance institutional holders failed for {ticker}: {e}")

    return {
        'ticker': ticker,
        'funds': funds,
        'total_funds': len(funds),
        'timestamp': datetime.utcnow().isoformat(),
    }


def _fetch_fund_detail_from_db(ticker, db_manager):
    """Query per-fund holdings from DB."""
    query = """
        SELECT
            hfm.name AS fund_name,
            h.shares_held,
            h.market_value,
            h.position_type,
            h.shares_change_pct,
            f.report_quarter
        FROM f13_holdings h
        JOIN f13_filings f ON h.filing_id = f.id
        JOIN hedge_fund_managers hfm ON h.cik = hfm.cik
        WHERE h.ticker = %s
        AND f.report_quarter = (
            SELECT report_quarter FROM f13_filings
            ORDER BY report_date DESC LIMIT 1
        )
        ORDER BY h.market_value DESC
    """
    rows = db_manager.execute_query(query, (ticker,))
    return [
        {
            'fund_name': r['fund_name'],
            'shares_held': int(r.get('shares_held') or 0),
            'market_value': float(r.get('market_value') or 0),
            'position_type': r.get('position_type', 'UNCHANGED'),
            'shares_change_pct': float(r.get('shares_change_pct') or 0),
            'report_quarter': r.get('report_quarter', ''),
        }
        for r in rows
    ]


def _fetch_fund_detail_from_yfinance(ticker):
    """Fallback: use yfinance institutional_holders."""
    t = yf.Ticker(ticker)
    holders = t.institutional_holders
    if holders is None or holders.empty:
        return []

    funds = []
    for _, row in holders.head(15).iterrows():
        funds.append({
            'fund_name': str(row.get('Holder', 'Unknown')),
            'shares_held': int(row.get('Shares', 0)),
            'market_value': float(row.get('Value', 0)),
            'position_type': 'UNKNOWN',
            'shares_change_pct': float(row.get('% Change', 0) or 0),
            'report_quarter': _estimate_current_quarter(),
        })
    return funds


# ──────────────────────────────────────────────────────────────────────────────
# 3. Weekly Comparison (Stock vs SPY vs Gold vs BTC)
# ──────────────────────────────────────────────────────────────────────────────

def fetch_weekly_comparison(ticker: str, period_weeks: int = 52) -> Dict:
    """
    Generate normalized weekly % return data for ticker vs SPY, GC=F, BTC-USD.
    Uses a single batch download for efficiency.
    """
    symbols = [ticker, '^GSPC', 'GC=F', 'BTC-USD']
    label_map = {ticker: ticker, '^GSPC': 'SPY', 'GC=F': 'GLD', 'BTC-USD': 'BTC'}

    period_str = f'{period_weeks}wk'
    if period_weeks > 200:
        period_str = 'max'

    try:
        data = yf.download(
            symbols,
            period=period_str,
            interval='1wk',
            group_by='ticker',
            auto_adjust=True,
            progress=False,
        )
    except Exception as e:
        logger.error(f"Weekly comparison download failed: {e}")
        return {
            'ticker': ticker,
            'period_weeks': period_weeks,
            'series': {},
            'summary': {},
            'timestamp': datetime.utcnow().isoformat(),
        }

    series = {}
    summary = {}

    for sym in symbols:
        label = label_map.get(sym, sym)
        try:
            if len(symbols) > 1:
                close = data[sym]['Close'].dropna()
            else:
                close = data['Close'].dropna()

            if close.empty:
                continue

            base = float(close.iloc[0])
            if base == 0:
                continue

            points = []
            for dt, val in close.items():
                pct = ((float(val) / base) - 1.0) * 100.0
                date_str = dt.strftime('%Y-%m-%d')
                points.append({'date': date_str, 'pct_return': round(pct, 2)})

            series[label] = points

            # Summary stats
            returns = close.pct_change().dropna()
            total_return = ((float(close.iloc[-1]) / base) - 1.0) * 100.0
            volatility = float(returns.std()) * 100.0
            sharpe = (total_return / volatility) if volatility > 0 else 0.0

            summary[label] = {
                'total_return': round(total_return, 2),
                'volatility': round(volatility, 2),
                'sharpe_approx': round(sharpe, 2),
            }
        except Exception as e:
            logger.warning(f"Weekly comparison series failed for {sym}: {e}")
            continue

    return {
        'ticker': ticker,
        'period_weeks': period_weeks,
        'series': series,
        'summary': summary,
        'timestamp': datetime.utcnow().isoformat(),
    }


# ──────────────────────────────────────────────────────────────────────────────
# 4. Daily OHLC (Candlestick)
# ──────────────────────────────────────────────────────────────────────────────

def fetch_daily_ohlc(ticker: str, months: int = 6) -> Dict:
    """Fetch daily OHLC data for candlestick chart with peak/trough detection."""
    period = f'{months}mo'

    try:
        hist = yf.Ticker(ticker).history(period=period, interval='1d')
    except Exception as e:
        logger.error(f"Daily OHLC fetch failed for {ticker}: {e}")
        return {'data': [], 'peaks': [], 'troughs': []}

    if hist.empty:
        return {'data': [], 'peaks': [], 'troughs': []}

    chart_data = []
    closes = []
    for dt, row in hist.iterrows():
        try:
            date_str = dt.strftime('%Y-%m-%d') if hasattr(dt, 'strftime') else str(dt)[:10]
            chart_data.append({
                'date': date_str,
                'open': round(float(row['Open']), 2),
                'high': round(float(row['High']), 2),
                'low': round(float(row['Low']), 2),
                'close': round(float(row['Close']), 2),
                'volume': int(row.get('Volume', 0)),
            })
            closes.append(float(row['Close']))
        except Exception:
            continue

    peaks = _detect_peaks(closes, chart_data)
    troughs = _detect_troughs(closes, chart_data)

    return {
        'data': chart_data,
        'peaks': peaks,
        'troughs': troughs,
    }


def _detect_peaks(closes, chart_data, window=5):
    """Detect local peaks in close prices."""
    peaks = []
    for i in range(window, len(closes) - window):
        is_peak = all(closes[i] >= closes[i - j] for j in range(1, window + 1)) and \
                  all(closes[i] >= closes[i + j] for j in range(1, window + 1))
        if is_peak:
            peaks.append({
                'index': i,
                'date': chart_data[i]['date'],
                'price': closes[i],
            })
    return peaks


def _detect_troughs(closes, chart_data, window=5):
    """Detect local troughs in close prices."""
    troughs = []
    for i in range(window, len(closes) - window):
        is_trough = all(closes[i] <= closes[i - j] for j in range(1, window + 1)) and \
                    all(closes[i] <= closes[i + j] for j in range(1, window + 1))
        if is_trough:
            troughs.append({
                'index': i,
                'date': chart_data[i]['date'],
                'price': closes[i],
            })
    return troughs


# ──────────────────────────────────────────────────────────────────────────────
# 5. Full Ticker Detail (orchestrator)
# ──────────────────────────────────────────────────────────────────────────────

def fetch_ticker_longterm_detail(ticker: str, period_weeks: int = 52,
                                  db_manager=None) -> Dict:
    """
    All-in-one detail fetch for a ticker: comparison, daily chart, funds, metadata.
    Each sub-fetch is independent so partial failures don't break the response.
    """
    result = {
        'ticker': ticker,
        'sector': None,
        'industry': None,
        'has_dividend': False,
        'latest_dividend': None,
        'comparison': None,
        'daily_chart': None,
        'fund_holdings': None,
        'timestamp': datetime.utcnow().isoformat(),
    }

    # Sector / dividend metadata
    try:
        info = yf.Ticker(ticker).info or {}
        result['sector'] = info.get('sector', 'Unknown')
        result['industry'] = info.get('industry', '')
        div_yield = info.get('dividendYield')
        result['has_dividend'] = div_yield is not None and div_yield > 0
        div_rate = info.get('dividendRate')
        if div_rate and div_rate > 0:
            result['latest_dividend'] = {
                'amount': round(div_rate, 4),
                'yield_pct': round((div_yield or 0) * 100, 2),
            }
        result['current_price'] = info.get('currentPrice') or info.get('regularMarketPrice')
        result['change_pct'] = info.get('regularMarketChangePercent')
    except Exception as e:
        logger.warning(f"Metadata fetch failed for {ticker}: {e}")

    # Weekly comparison
    try:
        result['comparison'] = fetch_weekly_comparison(ticker, period_weeks)
    except Exception as e:
        logger.warning(f"Weekly comparison failed for {ticker}: {e}")

    # Daily OHLC
    try:
        result['daily_chart'] = fetch_daily_ohlc(ticker)
    except Exception as e:
        logger.warning(f"Daily OHLC failed for {ticker}: {e}")

    # Fund holdings
    try:
        result['fund_holdings'] = fetch_fund_holdings_for_ticker(ticker, db_manager)
    except Exception as e:
        logger.warning(f"Fund holdings failed for {ticker}: {e}")

    return result


# ──────────────────────────────────────────────────────────────────────────────
# 6. Sector Holdings Summary
# ──────────────────────────────────────────────────────────────────────────────

def fetch_sector_holdings_summary(db_manager=None) -> Dict:
    """Aggregate holdings by sector for overview display."""
    sectors = []

    if db_manager:
        try:
            query = """
                SELECT
                    COALESCE(tm.sector, 'Unknown') AS sector,
                    COUNT(DISTINCT a.ticker) AS ticker_count,
                    SUM(a.total_market_value) AS total_market_value,
                    AVG(a.institutional_sentiment) AS avg_sentiment,
                    COUNT(DISTINCT CASE WHEN EXISTS (
                        SELECT 1 FROM corporate_actions ca
                        WHERE ca.ticker = a.ticker
                        AND ca.action_type = 'dividend'
                        AND ca.ex_date > NOW() - INTERVAL '12 months'
                    ) THEN a.ticker END) AS dividend_ticker_count
                FROM f13_stock_aggregates a
                LEFT JOIN ticker_metadata tm ON a.ticker = tm.ticker
                WHERE a.report_quarter = (
                    SELECT report_quarter FROM f13_stock_aggregates
                    ORDER BY report_quarter DESC LIMIT 1
                )
                GROUP BY COALESCE(tm.sector, 'Unknown')
                ORDER BY ticker_count DESC
            """
            rows = db_manager.execute_query(query)
            for r in rows:
                sectors.append({
                    'sector': r['sector'],
                    'ticker_count': r.get('ticker_count', 0),
                    'total_market_value': float(r.get('total_market_value') or 0),
                    'avg_sentiment': round(float(r.get('avg_sentiment') or 0), 3),
                    'dividend_ticker_count': r.get('dividend_ticker_count', 0),
                })
        except Exception as e:
            logger.warning(f"Sector summary DB query failed: {e}")

    if not sectors:
        # Build from fallback
        sector_map = {}
        for h in _FALLBACK_HOLDINGS:
            s = h.get('sector', 'Unknown')
            if s not in sector_map:
                sector_map[s] = {'count': 0, 'dividend': 0}
            sector_map[s]['count'] += 1
            if h.get('has_dividend'):
                sector_map[s]['dividend'] += 1

        for s, data in sorted(sector_map.items(), key=lambda x: -x[1]['count']):
            sectors.append({
                'sector': s,
                'ticker_count': data['count'],
                'total_market_value': None,
                'avg_sentiment': None,
                'dividend_ticker_count': data['dividend'],
            })

    return {
        'sectors': sectors,
        'timestamp': datetime.utcnow().isoformat(),
    }
