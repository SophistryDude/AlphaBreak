"""
Backtest: Improved Long-Term Entry Logic (Feb 1 - Apr 3, 2026)

Technical confirmations required:
1. 14-day EMA above 50-day EMA (bullish trend)
2. RSI(14) < 70 (not overbought)
3. No bearish daily trend break in last 7 days

Pullback entry mode:
- If 13F signal strong but EMA/RSI not favorable, add to watchlist
- Enter on 3-5% pullback to 20-day SMA

Compares: old rules (buy everything) vs new rules (technical confirmation)
"""

import os
import sys
import subprocess
import json
import logging
from datetime import datetime, date, timedelta

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
logger = logging.getLogger(__name__)


def _get_pod_ip():
    try:
        result = subprocess.run(
            ['sudo', 'k0s', 'kubectl', 'get', 'pod', '-n', 'trading-system',
             '-l', 'app=timeseries-postgres', '-o', 'jsonpath={.items[0].status.podIP}'],
            capture_output=True, text=True, timeout=10
        )
        return result.stdout.strip()
    except Exception:
        return '127.0.0.1'


def run():
    import psycopg2
    from psycopg2.extras import RealDictCursor
    import yfinance as yf
    import pandas as pd
    import numpy as np

    conn = psycopg2.connect(
        host=_get_pod_ip(), port=5432,
        database='trading_data', user='trading', password='trading_password'
    )

    # Get all 13F signal tickers from the past 2 months
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT DISTINCT ticker, institutional_sentiment, total_market_value,
                   funds_initiated + funds_increased as funds_buying,
                   net_shares_change
            FROM f13_stock_aggregates
            WHERE report_quarter = (SELECT MAX(report_quarter) FROM f13_stock_aggregates)
              AND institutional_sentiment > 0.5
              AND total_market_value > 1000000
            ORDER BY total_market_value DESC
            LIMIT 20
        """)
        f13_signals = cur.fetchall()

    tickers = [s['ticker'] for s in f13_signals]
    logger.info(f"13F signals: {len(tickers)} tickers: {', '.join(tickers[:10])}...")

    # Fetch 6 months of daily data for each ticker
    results_old = []
    results_new = []
    watchlist = []

    for sig in f13_signals:
        ticker = sig['ticker']
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(start='2025-10-01', end='2026-04-03', auto_adjust=True)
            if len(hist) < 60:
                continue
        except Exception as e:
            logger.warning(f"Failed to fetch {ticker}: {e}")
            continue

        close = hist['Close']

        # Compute EMAs (smoothing=2 means standard EMA)
        ema14 = close.ewm(span=14, adjust=False).mean()
        ema50 = close.ewm(span=50, adjust=False).mean()
        sma20 = close.rolling(20).mean()

        # RSI(14)
        delta = close.diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))

        # Check bearish trend breaks from DB
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT timestamp::date as break_date, direction_after
                FROM trend_breaks
                WHERE ticker = %s AND timeframe = 'daily'
                  AND timestamp >= '2026-01-01'
                ORDER BY timestamp
            """, (ticker,))
            breaks = {r['break_date']: r['direction_after'] for r in cur.fetchall()}

        # Simulate: check each trading day in Feb-Mar 2026
        feb1 = date(2026, 2, 1)
        apr3 = date(2026, 4, 3)

        entry_date_old = date(2026, 2, 12)  # Original: all bought Feb 12
        entry_price_old = None
        current_price = float(close.iloc[-1])

        # Old rules: bought on Feb 12 regardless
        for d, row in hist.iterrows():
            if d.date() == entry_date_old:
                entry_price_old = float(row['Close'])
                break

        if entry_price_old:
            old_pnl_pct = (current_price - entry_price_old) / entry_price_old
            results_old.append({
                'ticker': ticker,
                'entry_date': entry_date_old.isoformat(),
                'entry_price': entry_price_old,
                'current_price': current_price,
                'pnl_pct': old_pnl_pct,
                'status': 'WIN' if old_pnl_pct > 0 else 'LOSS',
            })

        # New rules: check technical confirmations each day
        entry_date_new = None
        entry_price_new = None
        entry_method = None
        pullback_target = None

        for d, row in hist.iterrows():
            td = d.date()
            if td < feb1 or td > apr3:
                continue
            if entry_date_new:
                break  # Already entered

            idx = hist.index.get_loc(d)
            if idx < 50:
                continue  # Need 50 days for EMA

            e14 = float(ema14.iloc[idx])
            e50 = float(ema50.iloc[idx])
            r = float(rsi.iloc[idx]) if not pd.isna(rsi.iloc[idx]) else 50
            s20 = float(sma20.iloc[idx]) if not pd.isna(sma20.iloc[idx]) else float(row['Close'])
            price = float(row['Close'])

            # Check for recent bearish break
            recent_bearish = False
            for i in range(7):
                check_date = td - timedelta(days=i)
                if breaks.get(check_date) == 'decreasing':
                    recent_bearish = True
                    break

            # Technical confirmations
            ema_bullish = e14 > e50
            rsi_ok = r < 70
            no_bearish = not recent_bearish

            if ema_bullish and rsi_ok and no_bearish:
                # All 3 confirmations met — enter
                entry_date_new = td
                entry_price_new = price
                entry_method = 'confirmed_entry'
            elif pullback_target is None and not ema_bullish:
                # EMA not bullish — set pullback target at 20-day SMA
                pullback_target = s20
            elif pullback_target and price <= pullback_target * 1.02 and rsi_ok and no_bearish:
                # Pullback entry: price returned to 20-day SMA
                entry_date_new = td
                entry_price_new = price
                entry_method = 'pullback_entry'

        if entry_date_new:
            new_pnl_pct = (current_price - entry_price_new) / entry_price_new
            results_new.append({
                'ticker': ticker,
                'entry_date': entry_date_new.isoformat(),
                'entry_price': round(entry_price_new, 2),
                'current_price': round(current_price, 2),
                'pnl_pct': round(new_pnl_pct, 4),
                'method': entry_method,
                'status': 'WIN' if new_pnl_pct > 0 else 'LOSS',
            })
        else:
            # Check last EMA state
            last_e14 = float(ema14.iloc[-1])
            last_e50 = float(ema50.iloc[-1])
            last_rsi = float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50
            watchlist.append({
                'ticker': ticker,
                'reason': f"EMA14={'above' if last_e14 > last_e50 else 'BELOW'} EMA50, RSI={last_rsi:.0f}",
                'sentiment': float(sig['institutional_sentiment']),
            })

    conn.close()

    # Print results
    print("\n" + "=" * 80)
    print("LONG-TERM ENTRY BACKTEST: Feb 1 - Apr 3, 2026")
    print("=" * 80)

    print(f"\n--- OLD RULES (buy all on Feb 12, no technical check) ---")
    old_wins = sum(1 for r in results_old if r['status'] == 'WIN')
    for r in sorted(results_old, key=lambda x: x['pnl_pct'], reverse=True):
        print(f"  {r['status']:4s} {r['ticker']:5s}  entry ${r['entry_price']:>8.2f}  now ${r['current_price']:>8.2f}  {r['pnl_pct']:+.2%}")
    print(f"  Total: {old_wins}/{len(results_old)} profitable  Avg: {sum(r['pnl_pct'] for r in results_old)/len(results_old) if results_old else 0:+.2%}")

    print(f"\n--- NEW RULES (EMA14>EMA50 + RSI<70 + no bearish break + pullback) ---")
    new_wins = sum(1 for r in results_new if r['status'] == 'WIN')
    for r in sorted(results_new, key=lambda x: x['pnl_pct'], reverse=True):
        print(f"  {r['status']:4s} {r['ticker']:5s}  entry ${r['entry_price']:>8.2f}  now ${r['current_price']:>8.2f}  {r['pnl_pct']:+.2%}  [{r['method']}]")
    print(f"  Total: {new_wins}/{len(results_new)} profitable  Avg: {sum(r['pnl_pct'] for r in results_new)/len(results_new) if results_new else 0:+.2%}")

    if watchlist:
        print(f"\n--- WATCHLIST (signals rejected, waiting for confirmation) ---")
        for w in watchlist[:10]:
            print(f"  {w['ticker']:5s}  {w['reason']}  (sentiment: {w['sentiment']:.2f})")

    print(f"\n--- COMPARISON ---")
    old_avg = sum(r['pnl_pct'] for r in results_old) / len(results_old) if results_old else 0
    new_avg = sum(r['pnl_pct'] for r in results_new) / len(results_new) if results_new else 0
    print(f"  Old: {old_wins}/{len(results_old)} wins, avg {old_avg:+.2%}")
    print(f"  New: {new_wins}/{len(results_new)} wins, avg {new_avg:+.2%}")
    print(f"  Skipped: {len(watchlist)} tickers (no technical confirmation)")
    diff = new_avg - old_avg
    print(f"  Improvement: {diff:+.2%} avg return")
    print("=" * 80)


if __name__ == '__main__':
    run()
