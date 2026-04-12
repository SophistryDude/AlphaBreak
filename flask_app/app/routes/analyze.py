"""
Analyze Routes
==============
Single-ticker deep-dive endpoints for the Analyze tab:

1. GET  /api/analyze/<ticker>           -- Full analyze data
2. GET  /api/analyze/<ticker>/chart     -- Enhanced chart data
3. GET  /api/analyze/search             -- Ticker autocomplete
"""

import re
from app.utils import error_details
import time
import logging
from flask import Blueprint, jsonify, request, current_app
from app import limiter
from app.utils.auth import log_request, require_api_key

logger = logging.getLogger(__name__)

analyze_bp = Blueprint('analyze', __name__)

# ──────────────────────────────────────────────────────────────────────────────
# Cache
# ──────────────────────────────────────────────────────────────────────────────

CACHE_TTL = 300  # 5 minutes

TICKER_PATTERN = re.compile(r'^[A-Z]{1,5}(-[A-Z])?$')
VALID_INTERVALS = ('1m', '5m', '15m', '1h', '1d', '1wk', '1mo')
VALID_PERIODS = ('1d', '5d', '1mo', '3mo', '6mo', '1y', '2y', '5y', 'max')


def _get_cached(key, compute_fn, ttl=CACHE_TTL):
    from app import cache
    data = cache.get(key)
    if data is not None:
        return data
    data = compute_fn()
    cache.set(key, data, timeout=ttl)
    return data


def _get_db_manager():
    try:
        from app.utils.database import db_manager
        return db_manager
    except Exception:
        return None


def _validate_ticker(ticker: str) -> str:
    ticker = ticker.strip().upper()
    if not ticker or len(ticker) > 10:
        raise ValueError(f"Invalid ticker: {ticker}")
    if not TICKER_PATTERN.match(ticker):
        raise ValueError(f"Invalid ticker format: {ticker}")
    return ticker


# ──────────────────────────────────────────────────────────────────────────────
# GET /api/analyze/search?q=APP
# ──────────────────────────────────────────────────────────────────────────────

@analyze_bp.route('/analyze/search', methods=['GET'])
@log_request
@require_api_key
def analyze_search():
    """
    Ticker autocomplete search.

    Query params:
        q: Search query (min 1 char)

    Returns array of {ticker, name, sector}.
    """
    query = request.args.get('q', '').strip()
    if len(query) < 1:
        return jsonify([])

    try:
        from app.services.analyze_service import search_tickers
        results = search_tickers(query)
        return jsonify(results)
    except Exception as e:
        current_app.logger.error(f"Analyze search error: {e}")
        return jsonify([])


# ──────────────────────────────────────────────────────────────────────────────
# GET /api/analyze/<ticker>
# ──────────────────────────────────────────────────────────────────────────────

@analyze_bp.route('/analyze/<ticker>', methods=['GET'])
@limiter.limit("60/minute")
@log_request
@require_api_key
def analyze_ticker(ticker):
    """
    Fetch full analyze data for a single ticker.

    Returns: header, stats, trend_break, indicators, signals,
    options, analyst, earnings, institutional, sector.
    """
    try:
        ticker = _validate_ticker(ticker)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

    try:
        db = _get_db_manager()
        cache_key = f'analyze_{ticker}'

        result = _get_cached(
            cache_key,
            lambda: _fetch_analyze(ticker, db),
            ttl=CACHE_TTL,
        )

        return jsonify(result)

    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        current_app.logger.error(f"Analyze error for {ticker}: {e}")
        return jsonify({
            'error': f'Failed to fetch analyze data for {ticker}',
            'details': error_details(e),
        }), 500


# ──────────────────────────────────────────────────────────────────────────────
# GET /api/analyze/<ticker>/chart?interval=1d&period=3mo
# ──────────────────────────────────────────────────────────────────────────────

@analyze_bp.route('/analyze/<ticker>/chart', methods=['GET'])
@limiter.limit("60/minute")
@log_request
@require_api_key
def analyze_chart(ticker):
    """
    Fetch enhanced OHLCV chart data.

    Query params:
        interval: 1m, 5m, 15m, 1h, 1d, 1wk, 1mo (default 1d)
        period: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, max (default 3mo)
    """
    try:
        ticker = _validate_ticker(ticker)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

    interval = request.args.get('interval', '1d')
    if interval not in VALID_INTERVALS:
        return jsonify({'error': 'Invalid interval'}), 400
    period = request.args.get('period', '3mo')
    if period not in VALID_PERIODS:
        return jsonify({'error': 'Invalid period'}), 400

    try:
        cache_key = f'analyze_chart_{ticker}_{period}_{interval}'

        result = _get_cached(
            cache_key,
            lambda: _fetch_chart(ticker, interval, period),
            ttl=CACHE_TTL,
        )

        return jsonify(result)

    except Exception as e:
        current_app.logger.error(f"Analyze chart error for {ticker}: {e}")
        return jsonify({
            'error': f'Failed to fetch chart data for {ticker}',
            'details': error_details(e),
        }), 500


# ──────────────────────────────────────────────────────────────────────────────
# GET /api/analyze/<ticker>/trendlines
# ──────────────────────────────────────────────────────────────────────────────

@analyze_bp.route('/analyze/<ticker>/trendlines', methods=['GET'])
@log_request
@require_api_key
def analyze_trendlines(ticker):
    """
    Auto-detect trendlines with regime-aware confidence scoring.

    Query params:
        period: 1mo, 3mo, 6mo, 1y (default 6mo)
        interval: 1d (default 1d)
    """
    try:
        ticker = _validate_ticker(ticker)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

    period = request.args.get('period', '6mo')
    if period not in VALID_PERIODS:
        return jsonify({'error': 'Invalid period'}), 400
    interval = request.args.get('interval', '1d')
    if interval not in VALID_INTERVALS:
        return jsonify({'error': 'Invalid interval'}), 400

    try:
        db = _get_db_manager()
        cache_key = f'analyze_trendlines_{ticker}_{period}_{interval}'

        result = _get_cached(
            cache_key,
            lambda: _fetch_trendlines(ticker, period, interval, db),
            ttl=CACHE_TTL,
        )

        return jsonify(result)

    except Exception as e:
        current_app.logger.error(f"Trendline error for {ticker}: {e}")
        return jsonify({
            'error': f'Failed to detect trendlines for {ticker}',
            'details': error_details(e),
        }), 500


# ──────────────────────────────────────────────────────────────────────────────
# GET /api/analyze/<ticker>/patterns
# ──────────────────────────────────────────────────────────────────────────────

@analyze_bp.route('/analyze/<ticker>/patterns', methods=['GET'])
@log_request
@require_api_key
def analyze_patterns(ticker):
    """Detect candlestick patterns + seasonality heatmap."""
    try:
        ticker = _validate_ticker(ticker)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

    period = request.args.get('period', '6mo')

    try:
        cache_key = f'analyze_patterns_{ticker}_{period}'
        result = _get_cached(
            cache_key,
            lambda: _fetch_patterns(ticker, period),
            ttl=CACHE_TTL,
        )
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Pattern error for {ticker}: {e}")
        return jsonify({'error': str(e)}), 500


# ──────────────────────────────────────────────────────────────────────────────
# GET /api/analyze/<ticker>/compare
# ──────────────────────────────────────────────────────────────────────────────

@analyze_bp.route('/analyze/<ticker>/compare', methods=['GET'])
@log_request
@require_api_key
def analyze_compare(ticker):
    """
    Get comparison data: ticker vs SPY, VIX, sector ETF.
    Returns normalized % change series for overlay.
    """
    try:
        ticker = _validate_ticker(ticker)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

    period = request.args.get('period', '6mo')

    try:
        cache_key = f'analyze_compare_{ticker}_{period}'
        result = _get_cached(
            cache_key,
            lambda: _fetch_compare(ticker, period),
            ttl=CACHE_TTL,
        )
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Compare error for {ticker}: {e}")
        return jsonify({'error': str(e)}), 500


# ──────────────────────────────────────────────────────────────────────────────
# GET /api/analyze/<ticker>/peers
# ──────────────────────────────────────────────────────────────────────────────

@analyze_bp.route('/analyze/<ticker>/peers', methods=['GET'])
@limiter.limit("30/minute")
@log_request
@require_api_key
def analyze_peers(ticker):
    """
    Fetch peer comparison table for a ticker.

    Returns comparison metrics (P/E, EV/EBITDA, ROE, Revenue Growth,
    Profit Margin, Market Cap) for the ticker and 5-8 sector peers.
    """
    try:
        ticker = _validate_ticker(ticker)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

    try:
        cache_key = f'analyze_peers_{ticker}'
        result = _get_cached(
            cache_key,
            lambda: _fetch_peers(ticker),
            ttl=CACHE_TTL,
        )
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Peers error for {ticker}: {e}")
        return jsonify({'error': str(e)}), 500


# ──────────────────────────────────────────────────────────────────────────────
# GET /api/analyze/<ticker>/insiders
# ──────────────────────────────────────────────────────────────────────────────

@analyze_bp.route('/analyze/<ticker>/insiders', methods=['GET'])
@log_request
@require_api_key
def analyze_insiders(ticker):
    """
    Fetch recent insider trading (SEC Form 4) for a ticker.

    Returns last 90 days of insider buy/sell transactions parsed from
    SEC EDGAR, with a summary of net insider sentiment.
    """
    try:
        ticker = _validate_ticker(ticker)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

    try:
        cache_key = f'analyze_insiders_{ticker}'
        result = _get_cached(
            cache_key,
            lambda: _fetch_insider_trading(ticker),
            ttl=3600,  # 1 hour — insider data changes infrequently
        )
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Insider trading error for {ticker}: {e}")
        return jsonify({
            'error': f'Failed to fetch insider trading data for {ticker}',
            'details': error_details(e),
        }), 500


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _fetch_analyze(ticker, db_manager):
    from app.services.analyze_service import fetch_analyze_data
    return fetch_analyze_data(ticker, db_manager)


def _fetch_chart(ticker, interval, period):
    from app.services.analyze_service import fetch_enhanced_chart
    return fetch_enhanced_chart(ticker, interval, period)


def _fetch_trendlines(ticker, period, interval, db_manager):
    from app.services.trendline_service import detect_trendlines
    return detect_trendlines(ticker, period, interval, db_manager)


# ──────────────────────────────────────────────────────────────────────────────
# GET /api/analyze/<ticker>/grades
# ──────────────────────────────────────────────────────────────────────────────

@analyze_bp.route('/analyze/<ticker>/grades', methods=['GET'])
@log_request
@require_api_key
def analyze_grades(ticker):
    """Compute quant letter grades (A+ through F) across 6 factors."""
    try:
        ticker = _validate_ticker(ticker)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

    try:
        db = _get_db_manager()
        cache_key = f'analyze_grades_{ticker}'
        result = _get_cached(
            cache_key,
            lambda: _fetch_grades(ticker, db),
            ttl=CACHE_TTL,
        )
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Grades error for {ticker}: {e}")
        return jsonify({'error': str(e)}), 500


# ──────────────────────────────────────────────────────────────────────────────
# GET /api/analyze/ai-dashboard
# ──────────────────────────────────────────────────────────────────────────────

@analyze_bp.route('/analyze/ai-dashboard', methods=['GET'])
@log_request
@require_api_key
def ai_dashboard():
    """Get full AI Dashboard data: market regime, top signals, model stats, sector regimes."""
    try:
        db = _get_db_manager()
        cache_key = 'ai_dashboard'
        result = _get_cached(
            cache_key,
            lambda: _fetch_ai_dashboard(db),
            ttl=120,  # 2 min cache (more dynamic than ticker data)
        )
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"AI Dashboard error: {e}")
        return jsonify({'error': str(e)}), 500


def _fetch_ai_dashboard(db_manager):
    from app.services.ai_dashboard_service import get_ai_dashboard
    return get_ai_dashboard(db_manager)


def _fetch_grades(ticker, db_manager):
    from app.services.quant_grades_service import compute_quant_grades
    return compute_quant_grades(ticker, db_manager)


# ──────────────────────────────────────────────────────────────────────────────
# GET /api/analyze/<ticker>/pop
# ──────────────────────────────────────────────────────────────────────────────

@analyze_bp.route('/analyze/<ticker>/pop', methods=['GET'])
@log_request
@require_api_key
def analyze_pop(ticker):
    """
    Calculate Probability of Profit for the nearest expiry option chain.

    Returns ATM call/put PoP and full chain with per-strike PoP values.
    """
    try:
        ticker = _validate_ticker(ticker)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

    try:
        cache_key = f'analyze_pop_{ticker}'
        result = _get_cached(
            cache_key,
            lambda: _fetch_pop(ticker),
            ttl=CACHE_TTL,
        )
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"PoP error for {ticker}: {e}")
        return jsonify({
            'error': f'Failed to calculate probability of profit for {ticker}',
            'details': error_details(e),
        }), 500


def _fetch_pop(ticker):
    """Fetch option chain and compute Probability of Profit for each strike."""
    import yfinance as yf
    import math
    from datetime import datetime
    from app.utils.options_math import calculate_probability_of_profit

    stock = yf.Ticker(ticker)
    current_price = float(stock.history(period='1d')['Close'].iloc[-1])

    expirations = stock.options
    if not expirations:
        return {'available': False, 'error': 'No options available'}

    nearest_exp = expirations[0]
    chain = stock.option_chain(nearest_exp)

    # Calculate days to expiry
    exp_date = datetime.strptime(nearest_exp, '%Y-%m-%d')
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    days_to_expiry = max((exp_date - today).days, 1)

    result = {
        'available': True,
        'ticker': ticker,
        'current_price': round(current_price, 2),
        'nearest_expiry': nearest_exp,
        'days_to_expiry': days_to_expiry,
        'chain': [],
    }

    # Build per-strike PoP data from calls and puts
    call_map = {}
    put_map = {}

    if not chain.calls.empty:
        for _, row in chain.calls.iterrows():
            strike = float(row['strike'])
            iv = float(row['impliedVolatility']) if not (
                row.get('impliedVolatility') is None or
                (isinstance(row.get('impliedVolatility'), float) and math.isnan(row['impliedVolatility']))
            ) else 0.0
            if iv > 0:
                pop = calculate_probability_of_profit(
                    current_price, strike, iv, days_to_expiry, 'call'
                )
                call_map[strike] = round(pop, 4)

    if not chain.puts.empty:
        for _, row in chain.puts.iterrows():
            strike = float(row['strike'])
            iv = float(row['impliedVolatility']) if not (
                row.get('impliedVolatility') is None or
                (isinstance(row.get('impliedVolatility'), float) and math.isnan(row['impliedVolatility']))
            ) else 0.0
            if iv > 0:
                pop = calculate_probability_of_profit(
                    current_price, strike, iv, days_to_expiry, 'put'
                )
                put_map[strike] = round(pop, 4)

    # Merge strikes
    all_strikes = sorted(set(list(call_map.keys()) + list(put_map.keys())))
    for strike in all_strikes:
        result['chain'].append({
            'strike': strike,
            'call_pop': call_map.get(strike),
            'put_pop': put_map.get(strike),
        })

    # ATM call/put PoP (nearest strike to current price)
    if all_strikes:
        atm_strike = min(all_strikes, key=lambda s: abs(s - current_price))
        result['atm_strike'] = atm_strike
        result['atm_call_pop'] = call_map.get(atm_strike)
        result['atm_put_pop'] = put_map.get(atm_strike)

    return result


def _fetch_patterns(ticker, period):
    from app.services.pattern_service import detect_patterns
    return detect_patterns(ticker, period)


def _fetch_peers(ticker):
    from app.services.analyze_service import fetch_peer_comparison
    return fetch_peer_comparison(ticker)


def _fetch_compare(ticker, period):
    """Fetch normalized % change series for ticker vs SPY, VIX, sector ETF."""
    import yfinance as yf
    import numpy as np

    symbols = [ticker, 'SPY', '^VIX']

    # Try to get sector ETF
    try:
        from app.services.report_service import TICKER_SECTOR_MAP, SECTOR_ETFS
        sector = TICKER_SECTOR_MAP.get(ticker)
        if sector:
            etf = SECTOR_ETFS.get(sector)
            if etf and etf not in symbols:
                symbols.append(etf)
    except Exception:
        pass

    result = {'symbols': []}

    for sym in symbols:
        try:
            stock = yf.Ticker(sym)
            hist = stock.history(period=period, interval='1d')
            if hist.empty or len(hist) < 5:
                continue

            hist = hist.reset_index()
            ts_col = 'Date' if 'Date' in hist.columns else 'Datetime'
            closes = hist['Close'].values
            base = closes[0]
            if base == 0:
                continue

            pct_changes = ((closes - base) / base * 100).tolist()
            timestamps = [
                t.isoformat() if hasattr(t, 'isoformat') else str(t)
                for t in hist[ts_col]
            ]

            label = sym
            if sym == '^VIX':
                label = 'VIX'
            elif sym == ticker:
                label = ticker

            result['symbols'].append({
                'symbol': sym,
                'label': label,
                'data': [
                    {'timestamp': ts, 'value': round(float(v), 2)}
                    for ts, v in zip(timestamps, pct_changes)
                    if not np.isnan(v)
                ],
            })
        except Exception as e:
            logger.debug(f"Compare fetch failed for {sym}: {e}")

    return result


def _fetch_insider_trading(ticker):
    """
    Fetch recent Form 4 insider transactions from SEC EDGAR.

    Uses the EDGAR company submissions endpoint to find Form 4 filings,
    then parses the XML ownership documents for transaction details.
    """
    import requests
    import xml.etree.ElementTree as ET
    from datetime import datetime, timedelta

    SEC_HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) TradingPredictionModel contact@example.com',
        'Accept-Encoding': 'gzip, deflate',
        'Accept': 'application/json,text/html,application/xhtml+xml,*/*;q=0.8',
    }

    end_date = datetime.now()
    start_date = end_date - timedelta(days=90)
    start_str = start_date.strftime('%Y-%m-%d')

    transactions = []

    # ── Step 1: Map ticker to CIK via SEC company tickers ────────────────
    cik = None
    try:
        tickers_url = 'https://www.sec.gov/files/company_tickers.json'
        resp = requests.get(tickers_url, headers=SEC_HEADERS, timeout=10)
        resp.raise_for_status()
        tickers_data = resp.json()
        for entry in tickers_data.values():
            if entry.get('ticker', '').upper() == ticker.upper():
                cik = str(entry['cik_str']).zfill(10)
                break
    except Exception as e:
        logger.debug(f"Failed to fetch company tickers: {e}")

    if not cik:
        return {
            'ticker': ticker,
            'transactions': [],
            'summary': {
                'total_buys': 0, 'total_sells': 0,
                'buy_value': 0, 'sell_value': 0,
                'net_sentiment': 'N/A', 'period_days': 90,
            },
            'error': 'Could not resolve ticker to CIK',
        }

    # ── Step 2: Fetch company submissions to find Form 4 filings ────────
    try:
        time.sleep(0.15)  # SEC rate limit: 10 req/sec
        submissions_url = f'https://data.sec.gov/submissions/CIK{cik}.json'
        resp = requests.get(submissions_url, headers=SEC_HEADERS, timeout=15)
        resp.raise_for_status()
        sub_data = resp.json()

        recent = sub_data.get('filings', {}).get('recent', {})
        forms = recent.get('form', [])
        dates = recent.get('filingDate', [])
        accessions = recent.get('accessionNumber', [])
        primary_docs = recent.get('primaryDocument', [])

        form4_filings = []
        for i, form in enumerate(forms):
            if form == '4' and i < len(dates):
                filing_date = dates[i]
                if filing_date >= start_str:
                    form4_filings.append({
                        'date': filing_date,
                        'accession': accessions[i] if i < len(accessions) else None,
                        'doc': primary_docs[i] if i < len(primary_docs) else None,
                    })

        # Parse up to 20 Form 4 XML documents
        for filing in form4_filings[:20]:
            acc = filing['accession']
            doc = filing['doc']
            if not acc or not doc:
                continue

            acc_nodash = acc.replace('-', '')
            xml_url = (
                f'https://www.sec.gov/Archives/edgar/data/'
                f'{cik.lstrip("0")}/{acc_nodash}/{doc}'
            )

            try:
                time.sleep(0.12)  # SEC rate limit
                xml_resp = requests.get(xml_url, headers=SEC_HEADERS, timeout=10)
                if xml_resp.status_code != 200:
                    continue

                parsed = _parse_form4_xml(xml_resp.text, filing['date'])
                transactions.extend(parsed)
            except Exception as e:
                logger.debug(f"Failed to parse Form 4 {acc}: {e}")
                continue

    except Exception as e:
        logger.debug(f"Failed to fetch submissions for CIK {cik}: {e}")

    # ── Step 3: Deduplicate and sort ─────────────────────────────────────
    seen = set()
    unique_txns = []
    for txn in transactions:
        key = (txn['date'], txn['insider'], txn['type'], txn.get('shares', 0))
        if key not in seen:
            seen.add(key)
            unique_txns.append(txn)

    unique_txns.sort(key=lambda x: x['date'], reverse=True)

    # ── Step 4: Compute summary ──────────────────────────────────────────
    buys = [t for t in unique_txns if t['type'] == 'Buy']
    sells = [t for t in unique_txns if t['type'] == 'Sell']
    buy_value = sum(t.get('value', 0) or 0 for t in buys)
    sell_value = sum(t.get('value', 0) or 0 for t in sells)

    if len(buys) > len(sells):
        sentiment = 'Bullish'
    elif len(sells) > len(buys):
        sentiment = 'Bearish'
    else:
        sentiment = 'Neutral'

    return {
        'ticker': ticker,
        'transactions': unique_txns[:50],  # Cap at 50 most recent
        'summary': {
            'total_buys': len(buys),
            'total_sells': len(sells),
            'buy_value': round(buy_value, 2),
            'sell_value': round(sell_value, 2),
            'net_sentiment': sentiment,
            'period_days': 90,
        },
    }


def _parse_form4_xml(xml_text, filing_date):
    """Parse a Form 4 XML document and extract insider transactions."""
    import xml.etree.ElementTree as ET

    transactions = []

    try:
        # Remove XML namespace prefixes for easier parsing
        xml_text = re.sub(r'xmlns[^"]*"[^"]*"', '', xml_text)
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return transactions

    # Get insider info
    owner_name = ''
    owner_title = ''
    try:
        reporting_owner = root.find('.//reportingOwner')
        if reporting_owner is not None:
            name_el = reporting_owner.find('.//rptOwnerName')
            if name_el is not None and name_el.text:
                owner_name = name_el.text.strip()
            title_el = reporting_owner.find('.//officerTitle')
            if title_el is not None and title_el.text:
                owner_title = title_el.text.strip()
            # Fallback: check isOfficer/isDirector
            if not owner_title:
                is_director = reporting_owner.find('.//isDirector')
                is_officer = reporting_owner.find('.//isOfficer')
                if is_director is not None and is_director.text and is_director.text.strip() in ('1', 'true'):
                    owner_title = 'Director'
                elif is_officer is not None and is_officer.text and is_officer.text.strip() in ('1', 'true'):
                    owner_title = 'Officer'
    except Exception:
        pass

    # Parse non-derivative transactions (actual stock buys/sells)
    for txn_el in root.findall('.//nonDerivativeTransaction'):
        try:
            txn_date_el = txn_el.find('.//transactionDate/value')
            txn_date = txn_date_el.text.strip() if txn_date_el is not None and txn_date_el.text else filing_date

            code_el = txn_el.find('.//transactionCoding/transactionCode')
            code = code_el.text.strip() if code_el is not None and code_el.text else ''

            # P = Open-market Purchase, S = Open-market Sale
            if code == 'P':
                txn_type = 'Buy'
            elif code == 'S':
                txn_type = 'Sell'
            else:
                continue  # Skip grants (A), exercises (M), etc.

            shares_el = txn_el.find('.//transactionAmounts/transactionShares/value')
            shares = float(shares_el.text) if shares_el is not None and shares_el.text else 0

            price_el = txn_el.find('.//transactionAmounts/transactionPricePerShare/value')
            price = float(price_el.text) if price_el is not None and price_el.text else 0

            value = round(shares * price, 2) if shares and price else 0

            transactions.append({
                'date': txn_date,
                'insider': owner_name,
                'title': owner_title,
                'type': txn_type,
                'shares': int(shares),
                'price': round(price, 2),
                'value': value,
            })
        except Exception:
            continue

    return transactions


# ──────────────────────────────────────────────────────────────────────────────
# GET /api/analyze/<ticker>/unusual-options
# ──────────────────────────────────────────────────────────────────────────────

@analyze_bp.route('/analyze/<ticker>/unusual-options', methods=['GET'])
@log_request
@require_api_key
def analyze_unusual_options(ticker):
    """
    Detect unusual options activity for a ticker.

    Scans the nearest 2-3 expiries for contracts with abnormal
    volume relative to open interest, then classifies sweeps.

    Returns:
        {
            ticker, unusual_contracts: [...], summary: {
                total_unusual, bullish_count, bearish_count, total_premium
            }
        }
    """
    try:
        ticker = _validate_ticker(ticker)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

    try:
        cache_key = f'analyze_unusual_options_{ticker}'
        result = _get_cached(
            cache_key,
            lambda: _fetch_unusual_options(ticker),
            ttl=CACHE_TTL,
        )
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Unusual options error for {ticker}: {e}")
        return jsonify({
            'error': f'Failed to fetch unusual options for {ticker}',
            'details': error_details(e),
        }), 500


def _fetch_unusual_options(ticker):
    """Scan nearest expiries for unusual options activity."""
    import math
    import yfinance as yf
    from datetime import datetime

    stock = yf.Ticker(ticker)
    expirations = stock.options
    if not expirations:
        return {
            'ticker': ticker,
            'unusual_contracts': [],
            'summary': {
                'total_unusual': 0,
                'bullish_count': 0,
                'bearish_count': 0,
                'total_premium': 0,
            },
        }

    # Use nearest 2-3 expiries
    expiries_to_scan = expirations[:3]

    def safe_float(val, default=0.0):
        if val is None or (isinstance(val, float) and math.isnan(val)):
            return default
        try:
            return float(val)
        except (ValueError, TypeError):
            return default

    def safe_int(val, default=0):
        if val is None or (isinstance(val, float) and math.isnan(val)):
            return default
        try:
            return int(val)
        except (ValueError, TypeError):
            return default

    unusual = []

    for expiry in expiries_to_scan:
        try:
            chain = stock.option_chain(expiry)
        except Exception:
            continue

        for opt_type, df in [('call', chain.calls), ('put', chain.puts)]:
            if df is None or df.empty:
                continue
            for _, row in df.iterrows():
                volume = safe_int(row.get('volume'))
                oi = safe_int(row.get('openInterest'))
                bid = safe_float(row.get('bid'))
                ask = safe_float(row.get('ask'))
                last_price = safe_float(row.get('lastPrice'))
                iv = safe_float(row.get('impliedVolatility'))
                strike = safe_float(row.get('strike'))

                if volume == 0:
                    continue

                vol_oi = volume / oi if oi > 0 else float('inf')

                # Flag as unusual:
                #   volume > 5x OI AND volume > 1000
                #   OR vol/OI > 3 AND volume > 500
                is_unusual = (
                    (vol_oi > 5 and volume > 1000)
                    or (vol_oi > 3 and volume > 500)
                )

                if not is_unusual:
                    continue

                # Sweep detection: high volume + tight bid-ask spread
                mid = (bid + ask) / 2 if (bid + ask) > 0 else 0
                spread = ask - bid
                is_sweep = (
                    mid > 0
                    and spread < 0.10 * mid
                    and volume > 500
                )

                sentiment = 'bullish' if opt_type == 'call' else 'bearish'

                unusual.append({
                    'expiry': expiry,
                    'strike': round(strike, 2),
                    'type': opt_type,
                    'volume': volume,
                    'open_interest': oi,
                    'vol_oi_ratio': round(vol_oi, 2) if vol_oi != float('inf') else None,
                    'iv': round(iv, 4) if iv else None,
                    'last_price': round(last_price, 2),
                    'is_sweep': is_sweep,
                    'sentiment': sentiment,
                })

    # Sort by volume descending
    unusual.sort(key=lambda c: c['volume'], reverse=True)

    bullish = sum(1 for c in unusual if c['sentiment'] == 'bullish')
    bearish = sum(1 for c in unusual if c['sentiment'] == 'bearish')
    total_premium = sum(c['volume'] * c['last_price'] * 100 for c in unusual)

    return {
        'ticker': ticker,
        'unusual_contracts': unusual,
        'summary': {
            'total_unusual': len(unusual),
            'bullish_count': bullish,
            'bearish_count': bearish,
            'total_premium': round(total_premium, 2),
        },
    }
