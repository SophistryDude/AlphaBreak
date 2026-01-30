"""
Earnings Service
================
Provides earnings calendar data for top stocks by volume,
plus detailed per-ticker data (CBOE activity, daily OHLC chart, news).
"""

import logging
import time
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

# Top 100 tickers by volume/market cap — used as the default earnings universe
TOP_100_TICKERS = [
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'BRK-B',
    'UNH', 'JNJ', 'XOM', 'JPM', 'V', 'PG', 'MA', 'HD', 'CVX', 'MRK',
    'ABBV', 'PEP', 'COST', 'AVGO', 'KO', 'WMT', 'MCD', 'CSCO', 'TMO',
    'ACN', 'ABT', 'DHR', 'LIN', 'VZ', 'ADBE', 'NKE', 'CRM', 'PM',
    'TXN', 'NFLX', 'DIS', 'CMCSA', 'WFC', 'NEE', 'BMY', 'UPS', 'RTX',
    'HON', 'QCOM', 'LOW', 'SPGI', 'INTU', 'BA', 'GE', 'CAT', 'ISRG',
    'AMAT', 'AMD', 'BKNG', 'GS', 'BLK', 'MDLZ', 'ADP', 'SYK', 'GILD',
    'VRTX', 'MMC', 'ADI', 'TJX', 'LRCX', 'DE', 'SBUX', 'AMT', 'REGN',
    'PLD', 'CI', 'CB', 'ETN', 'SCHW', 'MO', 'ZTS', 'CME', 'PNC',
    'SO', 'KLAC', 'DUK', 'SLB', 'EOG', 'ITW', 'BDX', 'CL', 'SNPS',
    'MCK', 'FDX', 'HUM', 'MPC', 'PSX', 'ORLY', 'APD', 'MSI', 'PYPL',
    'GM', 'F', 'INTC', 'SQ', 'PLTR', 'RIVN', 'UBER', 'ABNB', 'COIN',
    'SNAP', 'ROKU', 'DASH', 'DKNG',
]


# ──────────────────────────────────────────────────────────────────────────────
# Main entry points
# ──────────────────────────────────────────────────────────────────────────────

def fetch_earnings_calendar(custom_tickers=None, db_manager=None):
    """
    Fetch upcoming earnings calendar for top 100 stocks + custom tickers.
    Uses DB cache when available — only fetches from yfinance for stale/missing tickers.

    Args:
        custom_tickers: Optional list of additional tickers to include
        db_manager: Optional database manager for caching

    Returns:
        dict with earnings array, futures_context, and timestamp
    """
    # Build full ticker universe
    tickers = list(TOP_100_TICKERS)
    if custom_tickers:
        for t in custom_tickers:
            t_upper = t.strip().upper()
            if t_upper and t_upper not in tickers:
                tickers.append(t_upper)

    logger.info(f"Fetching earnings calendar for {len(tickers)} tickers")

    now = datetime.now()
    cutoff_past = now - timedelta(days=30)
    cutoff_future = now + timedelta(days=60)

    # Try to load from DB cache first
    cached_by_ticker = {}
    tickers_to_fetch = list(tickers)
    if db_manager:
        try:
            _ensure_earnings_tables(db_manager)
            from app.utils.database import get_all_cached_earnings
            cached_by_ticker = get_all_cached_earnings(stale_hours=6)
            # Only fetch tickers not in cache
            tickers_to_fetch = [t for t in tickers if t not in cached_by_ticker]
            if cached_by_ticker:
                logger.info(f"Loaded {len(cached_by_ticker)} tickers from earnings cache, "
                            f"{len(tickers_to_fetch)} need refresh")
        except Exception as e:
            logger.warning(f"DB cache read failed, fetching all from yfinance: {e}")
            tickers_to_fetch = list(tickers)

    # Fetch missing/stale tickers from yfinance
    fetched_by_ticker = {}
    for ticker in tickers_to_fetch:
        try:
            entries = _fetch_ticker_earnings(ticker)
            # Cache to DB if available
            if db_manager and entries:
                try:
                    from app.utils.database import store_ticker_earnings
                    store_ticker_earnings(ticker, [
                        {
                            'date': e['date'],
                            'eps_estimate': e.get('eps_estimate'),
                            'eps_actual': e.get('eps_actual'),
                            'surprise_pct': e.get('surprise_pct'),
                            'is_upcoming': e.get('is_upcoming', True),
                        } for e in entries
                    ])
                except Exception as db_err:
                    logger.debug(f"DB cache write failed for {ticker}: {db_err}")

            fetched_by_ticker[ticker] = entries
            time.sleep(0.15)  # Rate limit
        except Exception as e:
            logger.debug(f"Skipping {ticker} earnings: {e}")
            continue

    # Merge cached + freshly fetched earnings into final list
    earnings = []
    for ticker in tickers:
        entries = None
        if ticker in fetched_by_ticker:
            entries = fetched_by_ticker[ticker]
        elif ticker in cached_by_ticker:
            # Convert cached entries to the expected format
            entries = []
            for ce in cached_by_ticker[ticker]:
                try:
                    dt = datetime.strptime(ce['date'], '%Y-%m-%d')
                except (ValueError, TypeError):
                    continue
                entries.append({
                    'date': ce['date'],
                    'date_dt': dt,
                    'eps_estimate': ce.get('eps_estimate'),
                    'eps_actual': ce.get('eps_actual'),
                    'surprise_pct': ce.get('surprise_pct'),
                    'is_upcoming': ce.get('is_upcoming', dt > now),
                })

        if entries:
            for entry in entries:
                entry_date = entry.get('date_dt')
                if entry_date is None:
                    try:
                        entry_date = datetime.strptime(entry['date'], '%Y-%m-%d')
                    except (ValueError, TypeError):
                        continue
                if cutoff_past <= entry_date <= cutoff_future:
                    entry['ticker'] = ticker
                    entry['is_custom'] = ticker not in TOP_100_TICKERS
                    earnings.append(entry)

    # Sort by date ascending
    earnings.sort(key=lambda x: x.get('date', ''))

    # Remove internal date_dt field
    for entry in earnings:
        entry.pop('date_dt', None)

    # Fetch futures context
    futures_context = _fetch_futures_context()

    return {
        'earnings': earnings,
        'futures_context': futures_context,
        'total_tickers_scanned': len(tickers),
        'from_cache': len(cached_by_ticker),
        'freshly_fetched': len(fetched_by_ticker),
        'timestamp': datetime.now().isoformat(),
    }


def _ensure_earnings_tables(db_manager):
    """Create earnings cache tables if they don't exist (idempotent)."""
    try:
        from app.utils.database import ensure_earnings_tables
        ensure_earnings_tables()
    except Exception as e:
        logger.debug(f"Earnings table creation skipped: {e}")


def fetch_ticker_detail(ticker):
    """
    Fetch detailed data for a single ticker — CBOE activity, daily chart, news.

    Args:
        ticker: Stock ticker symbol

    Returns:
        dict with earnings_dates, cboe_activity, daily_chart, news, timestamp
    """
    ticker = ticker.strip().upper()
    logger.info(f"Fetching earnings detail for {ticker}")

    earnings_dates = []
    cboe_activity = None
    daily_chart = None
    news = []

    try:
        earnings_dates = _fetch_ticker_earnings(ticker)
        for entry in earnings_dates:
            entry.pop('date_dt', None)
    except Exception as e:
        logger.warning(f"Earnings dates failed for {ticker}: {e}")

    try:
        cboe_activity = _fetch_cboe_activity(ticker)
    except Exception as e:
        logger.warning(f"CBOE activity failed for {ticker}: {e}")

    try:
        daily_chart = _fetch_daily_chart(ticker)
    except Exception as e:
        logger.warning(f"Daily chart failed for {ticker}: {e}")

    try:
        news = _fetch_news(ticker)
    except Exception as e:
        logger.warning(f"News failed for {ticker}: {e}")

    return {
        'ticker': ticker,
        'earnings_dates': earnings_dates,
        'cboe_activity': cboe_activity,
        'daily_chart': daily_chart,
        'news': news,
        'timestamp': datetime.now().isoformat(),
    }


# ──────────────────────────────────────────────────────────────────────────────
# Sub-functions
# ──────────────────────────────────────────────────────────────────────────────

def _fetch_ticker_earnings(ticker):
    """Fetch earnings dates for a single ticker using yfinance."""
    t = yf.Ticker(ticker)
    try:
        ed = t.earnings_dates
    except Exception:
        return []

    if ed is None or ed.empty:
        return []

    results = []
    now = datetime.now()

    for date_idx, row in ed.iterrows():
        try:
            if hasattr(date_idx, 'to_pydatetime'):
                dt = date_idx.to_pydatetime()
                if dt.tzinfo:
                    dt = dt.replace(tzinfo=None)
            else:
                dt = pd.to_datetime(date_idx).to_pydatetime()
                if dt.tzinfo:
                    dt = dt.replace(tzinfo=None)

            eps_estimate = None
            eps_actual = None
            surprise_pct = None

            if 'EPS Estimate' in row.index and pd.notna(row['EPS Estimate']):
                eps_estimate = round(float(row['EPS Estimate']), 2)
            if 'Reported EPS' in row.index and pd.notna(row['Reported EPS']):
                eps_actual = round(float(row['Reported EPS']), 2)
            if 'Surprise(%)' in row.index and pd.notna(row['Surprise(%)']):
                surprise_pct = round(float(row['Surprise(%)']), 2)

            results.append({
                'date': dt.strftime('%Y-%m-%d'),
                'date_dt': dt,
                'eps_estimate': eps_estimate,
                'eps_actual': eps_actual,
                'surprise_pct': surprise_pct,
                'is_upcoming': dt > now,
            })
        except Exception:
            continue

    return results


def _fetch_futures_context():
    """Fetch E-mini S&P 500 futures (ES=F) for market context."""
    try:
        es = yf.Ticker('ES=F')
        hist = es.history(period='5d', interval='1d')
        if hist.empty:
            return None

        last_price = round(float(hist['Close'].iloc[-1]), 2)
        if len(hist) >= 2:
            prev_close = float(hist['Close'].iloc[-2])
            change = round(last_price - prev_close, 2)
            change_pct = round((change / prev_close) * 100, 2) if prev_close != 0 else 0
        else:
            change = 0
            change_pct = 0

        return {
            'symbol': 'ES=F',
            'name': 'E-mini S&P 500 Futures',
            'last_price': last_price,
            'change': change,
            'change_pct': change_pct,
        }
    except Exception as e:
        logger.warning(f"Futures context fetch failed: {e}")
        return None


def _fetch_cboe_activity(ticker):
    """Fetch CBOE options activity for a ticker using yfinance option chains."""
    t = yf.Ticker(ticker)
    try:
        expirations = t.options
    except Exception:
        return None

    if not expirations:
        return None

    # Use nearest expiration
    nearest_exp = expirations[0]
    try:
        chain = t.option_chain(nearest_exp)
    except Exception:
        return None

    calls = chain.calls
    puts = chain.puts

    call_volume = int(calls['volume'].sum()) if 'volume' in calls.columns and not calls['volume'].isna().all() else 0
    put_volume = int(puts['volume'].sum()) if 'volume' in puts.columns and not puts['volume'].isna().all() else 0
    call_oi = int(calls['openInterest'].sum()) if 'openInterest' in calls.columns and not calls['openInterest'].isna().all() else 0
    put_oi = int(puts['openInterest'].sum()) if 'openInterest' in puts.columns and not puts['openInterest'].isna().all() else 0

    total_volume = call_volume + put_volume
    pc_ratio = round(put_volume / call_volume, 2) if call_volume > 0 else None

    return {
        'expiration': nearest_exp,
        'call_volume': call_volume,
        'put_volume': put_volume,
        'total_volume': total_volume,
        'pc_ratio': pc_ratio,
        'call_oi': call_oi,
        'put_oi': put_oi,
        'total_oi': call_oi + put_oi,
    }


def _fetch_daily_chart(ticker):
    """Fetch 3-month daily OHLC data for candlestick chart rendering."""
    t = yf.Ticker(ticker)
    hist = t.history(period='3mo', interval='1d')
    if hist.empty:
        return None

    chart_data = []
    for date_idx, row in hist.iterrows():
        try:
            dt = date_idx
            if hasattr(dt, 'strftime'):
                date_str = dt.strftime('%Y-%m-%d')
            else:
                date_str = str(dt)[:10]

            chart_data.append({
                'date': date_str,
                'open': round(float(row['Open']), 2),
                'high': round(float(row['High']), 2),
                'low': round(float(row['Low']), 2),
                'close': round(float(row['Close']), 2),
                'volume': int(row['Volume']) if pd.notna(row['Volume']) else 0,
            })
        except Exception:
            continue

    # Detect peaks and troughs for trend lines
    peaks = []
    troughs = []
    if len(chart_data) >= 3:
        close_vals = [d['close'] for d in chart_data]
        for i in range(1, len(close_vals) - 1):
            if close_vals[i] > close_vals[i - 1] and close_vals[i] > close_vals[i + 1]:
                peaks.append({'date': chart_data[i]['date'], 'price': close_vals[i]})
            elif close_vals[i] < close_vals[i - 1] and close_vals[i] < close_vals[i + 1]:
                troughs.append({'date': chart_data[i]['date'], 'price': close_vals[i]})

    return {
        'data': chart_data,
        'peaks': peaks,
        'troughs': troughs,
    }


def _fetch_news(ticker):
    """Fetch recent news for a ticker using yfinance with RSS fallback."""
    results = []

    # Try yfinance first
    try:
        t = yf.Ticker(ticker)
        news_items = t.news
        if news_items and len(news_items) > 0:
            for item in news_items[:5]:
                try:
                    thumbnail = None
                    # Handle different thumbnail formats
                    if 'thumbnail' in item and item['thumbnail']:
                        resolutions = item['thumbnail'].get('resolutions', [])
                        if resolutions:
                            thumbnail = resolutions[0].get('url')

                    publish_time = None
                    if 'providerPublishTime' in item:
                        publish_time = datetime.fromtimestamp(item['providerPublishTime']).isoformat()

                    results.append({
                        'title': item.get('title', ''),
                        'publisher': item.get('publisher', ''),
                        'link': item.get('link', ''),
                        'publish_time': publish_time,
                        'thumbnail': thumbnail,
                    })
                except Exception:
                    continue
    except Exception as e:
        logger.debug(f"yfinance news failed for {ticker}: {e}")

    # If no results, try Yahoo Finance RSS feed as fallback
    if not results:
        results = _fetch_yahoo_rss_news(ticker)

    return results


def _fetch_yahoo_rss_news(ticker):
    """Fetch news from Yahoo Finance RSS feed (free, no API key needed)."""
    import urllib.request
    import xml.etree.ElementTree as ET

    results = []
    try:
        # Yahoo Finance RSS feed for a ticker
        rss_url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"
        headers = {'User-Agent': 'Mozilla/5.0'}
        req = urllib.request.Request(rss_url, headers=headers)

        with urllib.request.urlopen(req, timeout=5) as response:
            xml_data = response.read()

        root = ET.fromstring(xml_data)
        channel = root.find('channel')
        if channel is None:
            return results

        for item in channel.findall('item')[:5]:
            try:
                title = item.find('title')
                link = item.find('link')
                pub_date = item.find('pubDate')

                if title is None or link is None:
                    continue

                # Parse pub date to ISO format
                publish_time = None
                if pub_date is not None and pub_date.text:
                    try:
                        from email.utils import parsedate_to_datetime
                        dt = parsedate_to_datetime(pub_date.text)
                        publish_time = dt.isoformat()
                    except Exception:
                        pass

                results.append({
                    'title': title.text or '',
                    'publisher': 'Yahoo Finance',
                    'link': link.text or '',
                    'publish_time': publish_time,
                    'thumbnail': None,
                })
            except Exception:
                continue

    except Exception as e:
        logger.debug(f"Yahoo RSS news fetch failed for {ticker}: {e}")

    return results
