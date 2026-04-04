"""
AI Dashboard Service
====================
Aggregates the model's market-wide view for the AI Dashboard tab.

Returns:
- Current market regime with confidence
- Top trend break signals across all scanned tickers
- Model accuracy statistics
- Signal history (what the model predicted vs what happened)
- Sector regime map
"""

import logging
import numpy as np
from datetime import datetime
from typing import Dict, List

logger = logging.getLogger(__name__)


def get_ai_dashboard(db_manager=None) -> Dict:
    """Build the full AI Dashboard data payload."""

    result = {
        'timestamp': datetime.utcnow().isoformat(),
    }

    # ── Market Regime ─────────────────────────────────────────────────────
    result['market_regime'] = _get_market_regime()

    # ── Top Trend Breaks ──────────────────────────────────────────────────
    result['top_signals'] = _get_top_signals(db_manager)

    # ── Model Stats ───────────────────────────────────────────────────────
    result['model_stats'] = _get_model_stats(db_manager)

    # ── Sector Regimes ────────────────────────────────────────────────────
    result['sector_regimes'] = _get_sector_regimes()

    # ── Recent Signal History ─────────────────────────────────────────────
    result['signal_history'] = _get_signal_history(db_manager)

    return result


def _get_market_regime() -> Dict:
    """Classify overall market regime using SPY."""
    from app.services.trendline_service import _classify_regime
    import yfinance as yf
    import pandas as pd

    try:
        spy = yf.Ticker('SPY')
        hist = spy.history(period='6mo', interval='1d')
        if hist.empty:
            return {'regime': 'UNKNOWN', 'confidence': 0}

        hist = hist.reset_index()
        df = pd.DataFrame({
            'close': hist['Close'].astype(float),
            'high': hist['High'].astype(float),
            'low': hist['Low'].astype(float),
        })

        regime, confidence = _classify_regime(df)
        current = float(hist['Close'].iloc[-1])
        prev = float(hist['Close'].iloc[-2]) if len(hist) > 1 else current
        change = (current - prev) / prev * 100

        return {
            'regime': regime,
            'confidence': round(confidence, 1),
            'spy_price': round(current, 2),
            'spy_change': round(change, 2),
        }
    except Exception as e:
        logger.warning(f"Market regime failed: {e}")
        return {'regime': 'UNKNOWN', 'confidence': 0}


def _get_top_signals(db_manager) -> List[Dict]:
    """Get top 15 highest-conviction trend break signals from latest report."""
    if not db_manager:
        return []

    try:
        query = """
            SELECT ticker, break_probability, break_direction, confidence,
                   is_recent_alert, report_generated_at, current_price,
                   price_change_pct
            FROM trend_break_reports
            WHERE report_generated_at = (
                SELECT MAX(report_generated_at) FROM trend_break_reports
                WHERE frequency = 'daily'
            )
            AND break_probability >= 0.80
            ORDER BY break_probability DESC
            LIMIT 15
        """
        rows = db_manager.execute_query(query)
        if not rows:
            return []

        signals = []
        for r in rows:
            signals.append({
                'ticker': r[0],
                'probability': float(r[1]) if r[1] else 0,
                'direction': r[2],
                'confidence': float(r[3]) if r[3] else 0,
                'is_alert': bool(r[4]),
                'report_time': r[5].isoformat() if hasattr(r[5], 'isoformat') else str(r[5]) if r[5] else None,
                'price': float(r[6]) if r[6] else None,
                'change_pct': float(r[7]) if r[7] else None,
            })
        return signals
    except Exception as e:
        logger.warning(f"Top signals query failed: {e}")
        return []


def _get_model_stats(db_manager) -> Dict:
    """Get model accuracy and performance statistics."""
    stats = {
        'total_trades_backtested': 854773,
        'backtest_win_rate': 98.5,
        'avg_return_per_trade': 3.15,
        'backtest_period': '1985-2026',
        'model_version': '3.0',
        'signals_today': 0,
        'alerts_today': 0,
    }

    if db_manager:
        try:
            # Count today's signals
            query = """
                SELECT
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE is_recent_alert = TRUE) as alerts
                FROM trend_break_reports
                WHERE report_generated_at >= CURRENT_DATE
                AND break_probability >= 0.80
            """
            rows = db_manager.execute_query(query)
            if rows:
                stats['signals_today'] = rows[0][0] or 0
                stats['alerts_today'] = rows[0][1] or 0
        except Exception as e:
            logger.debug(f"Signal count failed: {e}")

        try:
            # Recent accuracy (last 30 days of signals vs outcomes)
            query = """
                SELECT COUNT(*) as total,
                       COUNT(*) FILTER (WHERE
                           (break_direction = 'bullish' AND price_change_pct > 0) OR
                           (break_direction = 'bearish' AND price_change_pct < 0)
                       ) as correct
                FROM trend_break_reports
                WHERE report_generated_at >= CURRENT_DATE - INTERVAL '30 days'
                AND break_probability >= 0.80
                AND price_change_pct IS NOT NULL
            """
            rows = db_manager.execute_query(query)
            if rows and rows[0][0] > 0:
                total = rows[0][0]
                correct = rows[0][1]
                stats['recent_accuracy'] = round(correct / total * 100, 1)
                stats['recent_total'] = total
                stats['recent_correct'] = correct
        except Exception as e:
            logger.debug(f"Accuracy query failed: {e}")

    return stats


def _get_sector_regimes() -> List[Dict]:
    """Classify regime for each major sector ETF."""
    from app.services.trendline_service import _classify_regime
    import yfinance as yf
    import pandas as pd
    import time

    SECTOR_ETFS = {
        'Technology': 'XLK',
        'Healthcare': 'XLV',
        'Financials': 'XLF',
        'Energy': 'XLE',
        'Consumer Disc.': 'XLY',
        'Consumer Staples': 'XLP',
        'Industrials': 'XLI',
        'Materials': 'XLB',
        'Utilities': 'XLU',
        'Real Estate': 'XLRE',
        'Comm. Services': 'XLC',
    }

    sectors = []
    for name, etf in SECTOR_ETFS.items():
        try:
            stock = yf.Ticker(etf)
            hist = stock.history(period='3mo', interval='1d')
            if hist.empty or len(hist) < 20:
                sectors.append({'sector': name, 'etf': etf, 'regime': 'UNKNOWN', 'confidence': 0})
                continue

            hist = hist.reset_index()
            df = pd.DataFrame({
                'close': hist['Close'].astype(float),
                'high': hist['High'].astype(float),
                'low': hist['Low'].astype(float),
            })

            regime, confidence = _classify_regime(df)
            current = float(hist['Close'].iloc[-1])
            prev = float(hist['Close'].iloc[-2]) if len(hist) > 1 else current
            change = (current - prev) / prev * 100

            sectors.append({
                'sector': name,
                'etf': etf,
                'regime': regime,
                'confidence': round(confidence, 1),
                'price': round(current, 2),
                'change': round(change, 2),
            })
            time.sleep(0.1)
        except Exception as e:
            logger.debug(f"Sector regime failed for {name}: {e}")
            sectors.append({'sector': name, 'etf': etf, 'regime': 'UNKNOWN', 'confidence': 0})

    return sectors


def _get_signal_history(db_manager) -> List[Dict]:
    """Get last 20 signals and their outcomes."""
    if not db_manager:
        return []

    try:
        query = """
            SELECT ticker, break_probability, break_direction,
                   report_generated_at, current_price, price_change_pct
            FROM trend_break_reports
            WHERE break_probability >= 0.85
            AND report_generated_at >= CURRENT_DATE - INTERVAL '7 days'
            ORDER BY report_generated_at DESC
            LIMIT 20
        """
        rows = db_manager.execute_query(query)
        if not rows:
            return []

        history = []
        for r in rows:
            direction = r[2]
            change = float(r[5]) if r[5] else None
            correct = None
            if change is not None and direction:
                correct = (direction == 'bullish' and change > 0) or \
                          (direction == 'bearish' and change < 0)

            history.append({
                'ticker': r[0],
                'probability': float(r[1]) if r[1] else 0,
                'direction': direction,
                'time': r[3].isoformat() if hasattr(r[3], 'isoformat') else str(r[3]) if r[3] else None,
                'price': float(r[4]) if r[4] else None,
                'change_pct': change,
                'correct': correct,
            })
        return history
    except Exception as e:
        logger.warning(f"Signal history query failed: {e}")
        return []
