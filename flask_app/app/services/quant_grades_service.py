"""
Quant Grades Service
====================
Assigns A+ through F letter grades across 6 factors for any stock,
compared against sector medians.

Factors:
1. Value     — P/E, Forward P/E, P/S, P/B, EV/EBITDA, PEG
2. Growth    — Revenue growth, earnings growth, forward EPS growth
3. Profitability — ROE, profit margin, operating margin, gross margin
4. Momentum  — Price performance vs 52-week range, recent trend
5. Revisions — Forward EPS vs trailing EPS (proxy for estimate direction)
6. AI Score  — Trend break probability + regime alignment (AlphaBreak exclusive)

Grading scale: A+, A, A-, B+, B, B-, C+, C, C-, D+, D, D-, F
Mapped from percentile rank within sector.
"""

import logging
import numpy as np
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Sector peer tickers for comparison (top 5-8 per sector)
SECTOR_PEERS = {
    'Technology': ['AAPL', 'MSFT', 'NVDA', 'GOOGL', 'META', 'AVGO', 'ADBE', 'CRM'],
    'Healthcare': ['UNH', 'JNJ', 'LLY', 'ABBV', 'MRK', 'PFE', 'TMO', 'ABT'],
    'Financial Services': ['JPM', 'V', 'MA', 'BAC', 'GS', 'MS', 'BLK', 'SCHW'],
    'Consumer Cyclical': ['AMZN', 'TSLA', 'HD', 'MCD', 'NKE', 'SBUX', 'TJX', 'LOW'],
    'Consumer Defensive': ['PG', 'PEP', 'KO', 'COST', 'WMT', 'PM', 'CL', 'MDLZ'],
    'Energy': ['XOM', 'CVX', 'COP', 'SLB', 'EOG', 'MPC', 'PSX', 'VLO'],
    'Industrials': ['CAT', 'BA', 'HON', 'UNP', 'RTX', 'GE', 'DE', 'LMT'],
    'Communication Services': ['GOOGL', 'META', 'DIS', 'NFLX', 'CMCSA', 'T', 'VZ', 'TMUS'],
    'Utilities': ['NEE', 'SO', 'DUK', 'D', 'AEP', 'SRE', 'EXC', 'XEL'],
    'Materials': ['LIN', 'APD', 'SHW', 'ECL', 'FCX', 'NEM', 'NUE', 'DOW'],
    'Real Estate': ['PLD', 'AMT', 'EQIX', 'SPG', 'PSA', 'O', 'DLR', 'WELL'],
}

GRADE_LABELS = ['A+', 'A', 'A-', 'B+', 'B', 'B-', 'C+', 'C', 'C-', 'D+', 'D', 'D-', 'F']


def compute_quant_grades(ticker: str, db_manager=None) -> Dict:
    """
    Compute quant letter grades for a stock.

    Returns:
        {
            ticker, sector, overall_grade, overall_score,
            factors: {
                value: {grade, score, metrics: [...]},
                growth: {...},
                profitability: {...},
                momentum: {...},
                revisions: {...},
                ai_score: {...},
            },
            peer_rank: {rank, total, percentile},
        }
    """
    import yfinance as yf

    stock = yf.Ticker(ticker)
    try:
        info = stock.info or {}
    except Exception:
        info = {}

    if not info.get('sector'):
        return {'ticker': ticker, 'error': 'No sector data available', 'factors': {}}

    sector = info.get('sector', 'Unknown')

    # Get peer data for comparison
    peers = SECTOR_PEERS.get(sector, [])
    if ticker not in peers:
        peers = [ticker] + peers[:7]
    else:
        peers = peers[:8]

    peer_data = _fetch_peer_data(peers)
    ticker_data = peer_data.get(ticker)

    if not ticker_data:
        return {'ticker': ticker, 'sector': sector, 'error': 'Could not fetch data', 'factors': {}}

    # Score each factor
    factors = {}

    # 1. Value — lower is better for P/E, P/S, P/B, EV/EBITDA; lower PEG is better
    factors['value'] = _grade_factor(ticker, peer_data, [
        ('pe_ratio', 'lower'),
        ('forward_pe', 'lower'),
        ('ps_ratio', 'lower'),
        ('pb_ratio', 'lower'),
        ('ev_ebitda', 'lower'),
        ('peg_ratio', 'lower'),
    ], 'Value')

    # 2. Growth — higher is better
    factors['growth'] = _grade_factor(ticker, peer_data, [
        ('revenue_growth', 'higher'),
        ('earnings_growth', 'higher'),
        ('forward_eps_growth', 'higher'),
    ], 'Growth')

    # 3. Profitability — higher is better
    factors['profitability'] = _grade_factor(ticker, peer_data, [
        ('roe', 'higher'),
        ('profit_margin', 'higher'),
        ('operating_margin', 'higher'),
        ('gross_margin', 'higher'),
    ], 'Profitability')

    # 4. Momentum — higher is better
    factors['momentum'] = _grade_factor(ticker, peer_data, [
        ('price_vs_52wk', 'higher'),
        ('change_3m', 'higher'),
    ], 'Momentum')

    # 5. Revisions — positive revision direction is better
    factors['revisions'] = _grade_factor(ticker, peer_data, [
        ('eps_revision', 'higher'),
    ], 'Revisions')

    # 6. AI Score — AlphaBreak exclusive
    factors['ai_score'] = _compute_ai_grade(ticker, info, db_manager)

    # Overall score: weighted average
    weights = {
        'value': 0.20,
        'growth': 0.20,
        'profitability': 0.20,
        'momentum': 0.15,
        'revisions': 0.10,
        'ai_score': 0.15,
    }

    total_score = 0
    total_weight = 0
    for key, weight in weights.items():
        if factors[key].get('score') is not None:
            total_score += factors[key]['score'] * weight
            total_weight += weight

    overall_score = total_score / total_weight if total_weight > 0 else 50
    overall_grade = _score_to_grade(overall_score)

    # Peer ranking
    peer_scores = []
    for p_ticker in peers:
        p_data = peer_data.get(p_ticker)
        if p_data:
            p_score = _quick_overall_score(p_ticker, peer_data)
            peer_scores.append((p_ticker, p_score))

    peer_scores.sort(key=lambda x: x[1], reverse=True)
    rank = next((i + 1 for i, (t, _) in enumerate(peer_scores) if t == ticker), len(peer_scores))

    return {
        'ticker': ticker,
        'sector': sector,
        'overall_grade': overall_grade,
        'overall_score': round(overall_score, 1),
        'factors': factors,
        'peer_rank': {
            'rank': rank,
            'total': len(peer_scores),
            'percentile': round((1 - rank / max(len(peer_scores), 1)) * 100, 0),
            'peers': [{'ticker': t, 'score': round(s, 1)} for t, s in peer_scores],
        },
    }


# ──────────────────────────────────────────────────────────────────────────────
# Data Fetching
# ──────────────────────────────────────────────────────────────────────────────

def _fetch_peer_data(tickers: List[str]) -> Dict:
    """Fetch key metrics for all peer tickers."""
    import yfinance as yf
    import time

    data = {}
    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            info = stock.info or {}
            hist = stock.history(period='1y', interval='1d')

            # Price momentum
            price_vs_52wk = 0
            change_3m = 0
            if not hist.empty and len(hist) > 5:
                closes = hist['Close'].values
                current = closes[-1]
                high52 = np.max(closes)
                low52 = np.min(closes)
                if high52 > low52:
                    price_vs_52wk = (current - low52) / (high52 - low52) * 100

                if len(closes) > 63:  # ~3 months
                    change_3m = (closes[-1] / closes[-63] - 1) * 100

            # EPS revision proxy
            trailing = info.get('trailingEps')
            forward = info.get('forwardEps')
            eps_revision = 0
            if trailing and forward and trailing != 0:
                eps_revision = (forward - trailing) / abs(trailing) * 100

            # Forward EPS growth proxy
            forward_eps_growth = 0
            if trailing and forward:
                forward_eps_growth = (forward / trailing - 1) * 100 if trailing > 0 else 0

            data[ticker] = {
                'pe_ratio': _safe(info.get('trailingPE')),
                'forward_pe': _safe(info.get('forwardPE')),
                'ps_ratio': _safe(info.get('priceToSalesTrailing12Months')),
                'pb_ratio': _safe(info.get('priceToBook')),
                'ev_ebitda': _safe(info.get('enterpriseToEbitda')),
                'peg_ratio': _safe(info.get('pegRatio')),
                'revenue_growth': _safe(info.get('revenueGrowth'), mult=100),
                'earnings_growth': _safe(info.get('earningsGrowth'), mult=100),
                'forward_eps_growth': forward_eps_growth,
                'roe': _safe(info.get('returnOnEquity'), mult=100),
                'profit_margin': _safe(info.get('profitMargins'), mult=100),
                'operating_margin': _safe(info.get('operatingMargins'), mult=100),
                'gross_margin': _safe(info.get('grossMargins'), mult=100),
                'price_vs_52wk': price_vs_52wk,
                'change_3m': change_3m,
                'eps_revision': eps_revision,
            }

            time.sleep(0.1)  # Rate limit yfinance

        except Exception as e:
            logger.debug(f"Failed to fetch peer data for {ticker}: {e}")

    return data


# ──────────────────────────────────────────────────────────────────────────────
# Grading Logic
# ──────────────────────────────────────────────────────────────────────────────

def _grade_factor(ticker: str, peer_data: Dict, metrics: List[Tuple],
                  factor_name: str) -> Dict:
    """
    Grade a factor by computing percentile rank across peers for each metric.
    Returns {grade, score, metrics: [{name, value, percentile, direction}]}.
    """
    ticker_data = peer_data.get(ticker, {})
    metric_results = []
    scores = []

    for metric_name, direction in metrics:
        ticker_val = ticker_data.get(metric_name)
        if ticker_val is None:
            metric_results.append({
                'name': metric_name,
                'value': None,
                'percentile': None,
                'direction': direction,
            })
            continue

        # Collect all peer values for this metric
        peer_vals = []
        for p, d in peer_data.items():
            v = d.get(metric_name)
            if v is not None and not np.isnan(v) and not np.isinf(v):
                peer_vals.append(v)

        if len(peer_vals) < 2:
            metric_results.append({
                'name': metric_name,
                'value': round(ticker_val, 2),
                'percentile': 50,
                'direction': direction,
            })
            scores.append(50)
            continue

        # Compute percentile rank
        if direction == 'lower':
            # For value metrics, lower is better → invert percentile
            rank = sum(1 for v in peer_vals if v > ticker_val)
        else:
            # For growth/profitability, higher is better
            rank = sum(1 for v in peer_vals if v < ticker_val)

        percentile = (rank / len(peer_vals)) * 100
        scores.append(percentile)

        metric_results.append({
            'name': _format_metric_name(metric_name),
            'value': round(ticker_val, 2),
            'percentile': round(percentile, 0),
            'direction': direction,
        })

    avg_score = np.mean(scores) if scores else 50
    grade = _score_to_grade(avg_score)

    return {
        'grade': grade,
        'score': round(avg_score, 1),
        'factor': factor_name,
        'metrics': metric_results,
    }


def _compute_ai_grade(ticker: str, info: Dict, db_manager=None) -> Dict:
    """Compute AI Score grade using trend break probability + regime alignment."""
    from app.services.watchlist_service import _get_trend_break_data, _safe_float
    import pandas as pd
    import yfinance as yf

    score = 50.0  # Default neutral
    metrics = []

    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period='3mo', interval='1d')
        if not df.empty and len(df) > 5:
            df = df.reset_index()
            if 'Date' in df.columns:
                df = df.rename(columns={'Date': 'date'})

            tb = _get_trend_break_data(ticker, df, db_manager)
            prob = tb.get('probability')
            direction = tb.get('direction', 'NEUTRAL')

            if prob is not None:
                # Higher probability = stronger signal = better score
                tb_score = prob * 100
                metrics.append({
                    'name': 'Trend Break Probability',
                    'value': round(tb_score, 1),
                    'percentile': round(tb_score, 0),
                    'direction': 'higher',
                })

                # Direction alignment bonus
                closes = df['Close'].values
                recent_trend = (closes[-1] / closes[-10] - 1) * 100 if len(closes) > 10 else 0

                aligned = (direction == 'BULLISH' and recent_trend > 0) or \
                          (direction == 'BEARISH' and recent_trend < 0)
                alignment_score = 80 if aligned else 40
                metrics.append({
                    'name': 'Regime Alignment',
                    'value': 'Aligned' if aligned else 'Divergent',
                    'percentile': alignment_score,
                    'direction': 'higher',
                })

                score = (tb_score * 0.6 + alignment_score * 0.4)

    except Exception as e:
        logger.debug(f"AI grade calc failed for {ticker}: {e}")

    return {
        'grade': _score_to_grade(score),
        'score': round(score, 1),
        'factor': 'AI Score',
        'metrics': metrics,
        'exclusive': True,  # Flag as AlphaBreak exclusive
    }


def _quick_overall_score(ticker: str, peer_data: Dict) -> float:
    """Quick overall score for ranking peers (no AI component)."""
    d = peer_data.get(ticker, {})
    scores = []

    # Value: lower P/E is better (invert)
    pe = d.get('pe_ratio')
    if pe and pe > 0:
        scores.append(max(0, min(100, 100 - pe)))  # Rough inverse

    # Growth
    rg = d.get('revenue_growth')
    if rg is not None:
        scores.append(max(0, min(100, 50 + rg)))

    # Profitability
    pm = d.get('profit_margin')
    if pm is not None:
        scores.append(max(0, min(100, 50 + pm)))

    # Momentum
    m = d.get('price_vs_52wk')
    if m is not None:
        scores.append(m)

    return np.mean(scores) if scores else 50


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _score_to_grade(score: float) -> str:
    """Convert 0-100 score to letter grade."""
    if score >= 95: return 'A+'
    if score >= 90: return 'A'
    if score >= 85: return 'A-'
    if score >= 80: return 'B+'
    if score >= 75: return 'B'
    if score >= 70: return 'B-'
    if score >= 65: return 'C+'
    if score >= 60: return 'C'
    if score >= 55: return 'C-'
    if score >= 50: return 'D+'
    if score >= 40: return 'D'
    if score >= 30: return 'D-'
    return 'F'


def _safe(val, mult=1):
    """Safely convert to float, multiply if needed."""
    if val is None:
        return None
    try:
        f = float(val)
        if np.isnan(f) or np.isinf(f):
            return None
        return f * mult
    except (TypeError, ValueError):
        return None


def _format_metric_name(name: str) -> str:
    """Convert snake_case to readable name."""
    return name.replace('_', ' ').replace('pe ratio', 'P/E').replace('forward pe', 'Fwd P/E') \
               .replace('ps ratio', 'P/S').replace('pb ratio', 'P/B') \
               .replace('ev ebitda', 'EV/EBITDA').replace('peg ratio', 'PEG') \
               .replace('roe', 'ROE').replace('eps', 'EPS') \
               .title()
