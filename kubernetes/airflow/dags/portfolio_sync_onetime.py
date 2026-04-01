"""
Airflow DAG: One-Time Portfolio Seed & Sync
============================================
Manually triggered DAG that:
1. Updates portfolio_account allocation to 65/35 (long-term/swing)
2. Fetches 13F institutional signals for long-term trades
3. Fetches trend break signals for swing trades
4. Gets current prices for all signal tickers via yfinance
5. Executes initial trades (long-term first, then swing)
6. Updates all holdings with fresh prices and recalculates P&L
7. Creates a daily performance snapshot
8. Logs a full summary

This seeds the portfolio with both long-term and swing positions,
then ensures the Flask portfolio tracker API serves current data.
Manual trigger only (schedule_interval=None). Safe to re-run.
"""

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago
from datetime import datetime, timedelta
import sys
import os
import logging
import json

sys.path.insert(0, '/app/flask_app')
sys.path.insert(0, '/app/src')

logger = logging.getLogger(__name__)

default_args = {
    'owner': 'trading-system',
    'depends_on_past': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=2),
    'execution_timeout': timedelta(minutes=30),
}

dag = DAG(
    'portfolio_sync_onetime',
    default_args=default_args,
    description='One-time portfolio seed: place initial trades, update prices, snapshot',
    schedule_interval=None,  # Manual trigger only
    start_date=days_ago(1),
    catchup=False,
    max_active_runs=1,
    tags=['portfolio', 'one-time', 'sync'],
)

# Database connection
DB_CONFIG = {
    'host': os.getenv('DB_HOST', '127.0.0.1'),
    'port': int(os.getenv('DB_PORT', '5432')),
    'database': os.getenv('DB_NAME', 'trading_data'),
    'user': os.getenv('DB_USER', 'trading'),
    'password': os.getenv('DB_PASSWORD', 'trading_password'),
}

# Portfolio configuration for initial seeding
PORTFOLIO_CONFIG = {
    'long_term_allocation': 0.65,
    'swing_allocation': 0.35,
    'max_position_pct': 0.07,
    'min_cash_reserve_pct': 0.20,
    'max_long_term_trades_per_day': 8,  # Higher for initial seeding
    'max_swing_trades_per_day': 5,
}


def get_db_connection():
    """Create database connection."""
    import psycopg2
    return psycopg2.connect(**DB_CONFIG)


def update_account_allocations(**context):
    """Update portfolio_account to 65/35 allocation split."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE portfolio_account
                SET long_term_allocation = 0.65,
                    swing_allocation = 0.35,
                    updated_at = NOW()
            """)
            conn.commit()
            logger.info("Updated portfolio_account: long_term=65%, swing=35%")
    except Exception as e:
        logger.error(f"Error updating allocations: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


def fetch_13f_signals(**context):
    """
    Fetch 13F institutional sentiment for long-term positions.
    Derives BUY/STRONG_BUY from institutional_sentiment score.
    """
    import psycopg2
    from psycopg2.extras import RealDictCursor

    conn = get_db_connection()
    signals = []

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    ticker,
                    institutional_sentiment,
                    total_shares_held,
                    total_market_value,
                    total_funds_holding,
                    funds_initiated + funds_increased AS funds_buying,
                    funds_decreased + funds_sold AS funds_selling,
                    net_shares_change,
                    report_quarter,
                    created_at
                FROM f13_stock_aggregates
                WHERE report_quarter = (SELECT MAX(report_quarter) FROM f13_stock_aggregates)
                  AND institutional_sentiment > 0.5
                  AND total_market_value > 1000000
                ORDER BY total_market_value DESC
                LIMIT 20
            """)

            for row in cur.fetchall():
                sentiment = float(row['institutional_sentiment'])
                if sentiment > 1.0:
                    signal_label = 'strong_buy'
                    signal_strength = 0.9
                else:
                    signal_label = 'buy'
                    signal_strength = 0.75

                signals.append({
                    'ticker': row['ticker'],
                    'signal_type': f"13f_{signal_label}",
                    'suggested_action': 'buy',
                    'holding_type': 'long_term',
                    'signal_strength': signal_strength,
                    'signal_price': None,
                    'source_data': {
                        'institutional_value': float(row['total_market_value']),
                        'institutional_sentiment': sentiment,
                        'funds_buying': row['funds_buying'],
                        'funds_selling': row['funds_selling'],
                        'net_shares_change': int(row['net_shares_change']) if row['net_shares_change'] else 0,
                        'report_quarter': row['report_quarter'],
                    }
                })

        logger.info(f"Found {len(signals)} 13F institutional signals")
        context['ti'].xcom_push(key='13f_signals', value=signals)

    except Exception as e:
        logger.error(f"Error fetching 13F signals: {e}")
        context['ti'].xcom_push(key='13f_signals', value=[])
    finally:
        conn.close()

    return signals


def fetch_trend_break_signals(**context):
    """
    Fetch recent trend break signals from the trend_breaks table.
    Creates portfolio signals for stocks with recent daily breaks.
    """
    import psycopg2
    from psycopg2.extras import RealDictCursor

    conn = get_db_connection()
    signals = []

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT DISTINCT ON (ticker)
                    id,
                    ticker,
                    break_type,
                    direction_after,
                    price_at_break,
                    magnitude,
                    volume_ratio,
                    trend_strength,
                    timestamp
                FROM trend_breaks
                WHERE timeframe = 'daily'
                  AND timestamp >= NOW() - INTERVAL '30 days'
                ORDER BY ticker, timestamp DESC
            """)

            for row in cur.fetchall():
                direction = 'bullish' if row['direction_after'] == 'increasing' else 'bearish'
                signal_type = f"trend_break_{direction}"
                action = 'buy' if direction == 'bullish' else 'sell'

                mag = float(row['magnitude']) if row['magnitude'] else 0.5
                signal_strength = min(1.0, max(0.8, 0.8 + mag * 0.02))

                signals.append({
                    'ticker': row['ticker'],
                    'signal_type': signal_type,
                    'suggested_action': action,
                    'holding_type': 'swing',
                    'signal_strength': signal_strength,
                    'signal_price': float(row['price_at_break']) if row['price_at_break'] else None,
                    'source_data': {
                        'break_id': row['id'],
                        'break_type': row['break_type'],
                        'magnitude': float(row['magnitude']) if row['magnitude'] else None,
                        'volume_ratio': float(row['volume_ratio']) if row['volume_ratio'] else None,
                    }
                })

        logger.info(f"Found {len(signals)} trend break signals")
        context['ti'].xcom_push(key='trend_signals', value=signals)

    except Exception as e:
        logger.error(f"Error fetching trend break signals: {e}")
        context['ti'].xcom_push(key='trend_signals', value=[])
    finally:
        conn.close()

    return signals


def fetch_signal_prices(**context):
    """Fetch current prices for all signal tickers using yfinance."""
    import yfinance as yf

    ti = context['ti']
    trend_signals = ti.xcom_pull(key='trend_signals', task_ids='fetch_trend_break_signals') or []
    f13_signals = ti.xcom_pull(key='13f_signals', task_ids='fetch_13f_signals') or []

    all_signals = trend_signals + f13_signals
    tickers = list(set(s['ticker'] for s in all_signals if s.get('suggested_action') == 'buy'))

    if not tickers:
        logger.info("No signal tickers to fetch prices for")
        ti.xcom_push(key='signal_prices', value={})
        return {}

    logger.info(f"Fetching prices for {len(tickers)} signal tickers")
    prices = {}
    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            data = stock.history(period='1d')
            if not data.empty:
                prices[ticker] = float(data['Close'].iloc[-1])
                logger.info(f"  {ticker}: ${prices[ticker]:.2f}")
        except Exception as e:
            logger.warning(f"  Failed to fetch price for {ticker}: {e}")

    logger.info(f"Fetched prices for {len(prices)}/{len(tickers)} tickers")
    ti.xcom_push(key='signal_prices', value=prices)
    return prices


def execute_initial_trades(**context):
    """Execute initial portfolio trades from 13F and trend break signals."""
    ti = context['ti']
    trend_signals = ti.xcom_pull(key='trend_signals', task_ids='fetch_trend_break_signals') or []
    f13_signals = ti.xcom_pull(key='13f_signals', task_ids='fetch_13f_signals') or []
    prices = ti.xcom_pull(key='signal_prices', task_ids='fetch_signal_prices') or {}

    conn = get_db_connection()
    executed_trades = []

    try:
        sys.path.insert(0, '/app/src')
        from portfolio_manager import PortfolioManager

        pm = PortfolioManager(conn=conn)

        # Get current holdings to avoid duplicate buys
        current_holdings = {h['ticker']: h for h in pm.get_holdings()}
        logger.info(f"Current holdings: {list(current_holdings.keys())}")

        # --- Process long-term signals first (13F) ---
        long_term = [s for s in f13_signals if s.get('suggested_action') == 'buy']
        long_term.sort(key=lambda x: x.get('signal_strength', 0), reverse=True)
        long_term = long_term[:PORTFOLIO_CONFIG['max_long_term_trades_per_day']]

        logger.info(f"Processing {len(long_term)} long-term signals")

        for signal in long_term:
            ticker = signal['ticker']
            price = prices.get(ticker)

            if not price:
                logger.warning(f"No price for {ticker}, skipping")
                continue

            if ticker in current_holdings:
                logger.info(f"Already holding {ticker}, skipping")
                continue

            # Recalculate portfolio value for accurate position sizing
            portfolio = pm.get_portfolio_value()
            max_position_value = portfolio['total_value'] * PORTFOLIO_CONFIG['max_position_pct']
            quantity = int(max_position_value / price)

            if quantity < 1:
                logger.warning(f"{ticker} too expensive at ${price:.2f}, skipping")
                continue

            result = pm.execute_trade(
                action='buy',
                ticker=ticker,
                quantity=quantity,
                price=price,
                holding_type='long_term',
                signal_source=signal['signal_type'],
                signal_details=signal.get('source_data'),
            )

            if result.get('success'):
                executed_trades.append({
                    'ticker': ticker,
                    'action': 'buy',
                    'quantity': quantity,
                    'price': price,
                    'holding_type': 'long_term',
                    'total_value': quantity * price,
                })
                current_holdings[ticker] = True
                logger.info(f"BUY {quantity} {ticker} @ ${price:.2f} (long_term) = ${quantity * price:,.2f}")
            else:
                logger.warning(f"Trade failed for {ticker}: {result.get('error')}")

        # --- Process swing signals (trend breaks) ---
        swing = [s for s in trend_signals if s.get('suggested_action') == 'buy']
        swing.sort(key=lambda x: x.get('signal_strength', 0), reverse=True)
        swing = swing[:PORTFOLIO_CONFIG['max_swing_trades_per_day']]

        logger.info(f"Processing {len(swing)} swing signals")

        for signal in swing:
            ticker = signal['ticker']
            price = prices.get(ticker) or signal.get('signal_price')

            if not price:
                logger.warning(f"No price for {ticker}, skipping")
                continue

            if ticker in current_holdings:
                logger.info(f"Already holding {ticker}, skipping")
                continue

            portfolio = pm.get_portfolio_value()
            max_position_value = portfolio['total_value'] * PORTFOLIO_CONFIG['max_position_pct']
            quantity = int(max_position_value / price)

            if quantity < 1:
                logger.warning(f"{ticker} too expensive at ${price:.2f}, skipping")
                continue

            result = pm.execute_trade(
                action='buy',
                ticker=ticker,
                quantity=quantity,
                price=price,
                holding_type='swing',
                signal_source=signal['signal_type'],
                signal_details=signal.get('source_data'),
            )

            if result.get('success'):
                executed_trades.append({
                    'ticker': ticker,
                    'action': 'buy',
                    'quantity': quantity,
                    'price': price,
                    'holding_type': 'swing',
                    'total_value': quantity * price,
                })
                current_holdings[ticker] = True
                logger.info(f"BUY {quantity} {ticker} @ ${price:.2f} (swing) = ${quantity * price:,.2f}")
            else:
                logger.warning(f"Trade failed for {ticker}: {result.get('error')}")

        lt_count = sum(1 for t in executed_trades if t['holding_type'] == 'long_term')
        sw_count = sum(1 for t in executed_trades if t['holding_type'] == 'swing')
        logger.info(f"Executed {len(executed_trades)} initial trades ({lt_count} long-term, {sw_count} swing)")
        ti.xcom_push(key='executed_trades', value=executed_trades)

    except Exception as e:
        logger.error(f"Error executing initial trades: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

    return executed_trades


def fetch_and_update_prices(**context):
    """Fetch current prices for all holdings and update the database."""
    import psycopg2
    from psycopg2.extras import RealDictCursor

    conn = get_db_connection()
    prices = {}

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT ticker FROM portfolio_holdings")
            tickers = [row['ticker'] for row in cur.fetchall()]

        if not tickers:
            logger.info("No holdings to update prices for")
            context['ti'].xcom_push(key='prices', value={})
            return {}

        logger.info(f"Fetching prices for {len(tickers)} holdings: {tickers}")

        import yfinance as yf
        for ticker in tickers:
            try:
                stock = yf.Ticker(ticker)
                data = stock.history(period='1d')
                if not data.empty:
                    prices[ticker] = float(data['Close'].iloc[-1])
                    logger.info(f"  {ticker}: ${prices[ticker]:.2f}")
            except Exception as e:
                logger.warning(f"  Failed to fetch price for {ticker}: {e}")

        if prices:
            sys.path.insert(0, '/app/src')
            from portfolio_manager import PortfolioManager

            pm = PortfolioManager(conn=conn)
            updated = pm.update_prices(prices)
            logger.info(f"Updated prices for {updated} holdings")

        context['ti'].xcom_push(key='prices', value=prices)

    except Exception as e:
        logger.error(f"Error fetching/updating prices: {e}")
        raise
    finally:
        conn.close()

    return prices


def create_snapshot(**context):
    """Create a daily portfolio snapshot."""
    conn = get_db_connection()
    try:
        sys.path.insert(0, '/app/src')
        from portfolio_manager import PortfolioManager

        pm = PortfolioManager(conn=conn)
        snapshot = pm.create_daily_snapshot()

        logger.info(f"Created snapshot: total_value=${snapshot.get('total_value', 0):.2f}")
        context['ti'].xcom_push(key='snapshot', value=snapshot)

    except Exception as e:
        logger.error(f"Error creating snapshot: {e}")
        raise
    finally:
        conn.close()


def log_sync_summary(**context):
    """Log a summary of the sync operation."""
    import psycopg2
    from psycopg2.extras import RealDictCursor

    ti = context['ti']
    prices = ti.xcom_pull(key='prices', task_ids='fetch_and_update_prices') or {}
    snapshot = ti.xcom_pull(key='snapshot', task_ids='create_snapshot') or {}
    executed_trades = ti.xcom_pull(key='executed_trades', task_ids='execute_initial_trades') or []

    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT cash_balance, long_term_allocation, swing_allocation FROM portfolio_account LIMIT 1")
            account = cur.fetchone()

            cur.execute("""
                SELECT ticker, quantity, avg_cost_basis, current_price, market_value,
                       unrealized_pnl, unrealized_pnl_pct, holding_type
                FROM portfolio_holdings
                ORDER BY holding_type, market_value DESC
            """)
            holdings = cur.fetchall()

        lt_trades = [t for t in executed_trades if t['holding_type'] == 'long_term']
        sw_trades = [t for t in executed_trades if t['holding_type'] == 'swing']

        summary = f"""
=== ONE-TIME PORTFOLIO SEED & SYNC COMPLETE ===

Account:
  - Cash Balance: ${float(account['cash_balance']):,.2f}
  - Long-Term Allocation: {float(account['long_term_allocation']):.0%}
  - Swing Allocation: {float(account['swing_allocation']):.0%}

Initial Trades Executed: {len(executed_trades)} ({len(lt_trades)} long-term, {len(sw_trades)} swing)
"""
        for t in executed_trades:
            summary += f"  - BUY {t['ticker']:5s} ({t['holding_type']:9s}): {t['quantity']} @ ${t['price']:,.2f} = ${t['total_value']:,.2f}\n"

        summary += f"\nHoldings ({len(holdings)} positions):\n"

        total_invested = 0
        total_market_value = 0
        lt_value = 0
        sw_value = 0
        for h in holdings:
            qty = float(h['quantity'])
            avg = float(h['avg_cost_basis'])
            curr = float(h['current_price']) if h['current_price'] else 0
            mv = float(h['market_value']) if h['market_value'] else qty * curr
            pnl = float(h['unrealized_pnl']) if h['unrealized_pnl'] else 0
            pnl_pct = float(h['unrealized_pnl_pct']) if h['unrealized_pnl_pct'] else 0
            total_invested += qty * avg
            total_market_value += mv
            if h['holding_type'] == 'long_term':
                lt_value += mv
            else:
                sw_value += mv
            summary += f"  - {h['ticker']:5s} ({h['holding_type']:9s}): {qty:.0f} shares @ ${avg:,.2f} -> ${curr:,.2f}  MV: ${mv:,.2f}  P&L: ${pnl:,.2f} ({pnl_pct:.2%})\n"

        cash = float(account['cash_balance'])
        total_value = cash + total_market_value
        total_pnl = total_value - 100000.0

        summary += f"""
Portfolio Summary:
  - Total Invested: ${total_invested:,.2f}
  - Market Value: ${total_market_value:,.2f}
  - Cash: ${cash:,.2f} ({cash/total_value:.1%})
  - Total Portfolio Value: ${total_value:,.2f}
  - Total P&L: ${total_pnl:,.2f} ({total_pnl/100000.0:.2%})

Allocation:
  - Long-Term: ${lt_value:,.2f} ({lt_value/total_value:.1%} of portfolio, target 65%)
  - Swing: ${sw_value:,.2f} ({sw_value/total_value:.1%} of portfolio, target 35%)
  - Cash: ${cash:,.2f} ({cash/total_value:.1%} of portfolio, min 20%)

Prices Updated: {len(prices)} tickers
Snapshot Created: {'Yes' if snapshot else 'No'}
================================================
"""
        logger.info(summary)

    except Exception as e:
        logger.error(f"Error logging summary: {e}")
    finally:
        conn.close()


# Define tasks
update_alloc = PythonOperator(
    task_id='update_account_allocations',
    python_callable=update_account_allocations,
    provide_context=True,
    dag=dag,
)

fetch_13f = PythonOperator(
    task_id='fetch_13f_signals',
    python_callable=fetch_13f_signals,
    provide_context=True,
    dag=dag,
)

fetch_trend = PythonOperator(
    task_id='fetch_trend_break_signals',
    python_callable=fetch_trend_break_signals,
    provide_context=True,
    dag=dag,
)

fetch_sig_prices = PythonOperator(
    task_id='fetch_signal_prices',
    python_callable=fetch_signal_prices,
    provide_context=True,
    dag=dag,
)

execute_trades = PythonOperator(
    task_id='execute_initial_trades',
    python_callable=execute_initial_trades,
    provide_context=True,
    dag=dag,
)

fetch_prices = PythonOperator(
    task_id='fetch_and_update_prices',
    python_callable=fetch_and_update_prices,
    provide_context=True,
    dag=dag,
)

snapshot = PythonOperator(
    task_id='create_snapshot',
    python_callable=create_snapshot,
    provide_context=True,
    dag=dag,
)

log_summary = PythonOperator(
    task_id='log_sync_summary',
    python_callable=log_sync_summary,
    provide_context=True,
    dag=dag,
)

# Task flow:
# update_alloc → [fetch_13f, fetch_trend] → fetch_signal_prices → execute_initial_trades
#   → fetch_and_update_prices → create_snapshot → log_sync_summary
update_alloc >> [fetch_13f, fetch_trend]
[fetch_13f, fetch_trend] >> fetch_sig_prices
fetch_sig_prices >> execute_trades
execute_trades >> fetch_prices
fetch_prices >> snapshot
snapshot >> log_summary
