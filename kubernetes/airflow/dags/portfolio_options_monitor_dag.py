"""
Airflow DAG: Portfolio Options Monitor
=======================================
Lightweight DAG that runs every 2 hours during market hours.
Only checks swing options positions for exit signals — no new signal generation.

Schedule: Every 2 hours during market hours (9:30 AM - 4 PM ET)
  UTC equivalent: 14:30, 16:00, 18:00, 20:00 (roughly)
  Cron: 0 15,17,19,21 * * 1-5

Tasks:
1. Check market day
2. Fetch current prices for option holdings
3. Evaluate smart exits (volume decline, reversal, stop-loss)
4. Check all stop losses
"""

from airflow import DAG
from airflow.operators.python import PythonOperator, ShortCircuitOperator
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
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=2),
    'execution_timeout': timedelta(minutes=15),
}

dag = DAG(
    'portfolio_options_monitor',
    default_args=default_args,
    description='Monitor swing options positions every 2h during market hours',
    schedule_interval='0 15,17,19,21 * * 1-5',  # Every 2h during US market hours (UTC)
    start_date=days_ago(1),
    catchup=False,
    max_active_runs=1,
    tags=['portfolio', 'options', 'monitor'],
)

DB_CONFIG = {
    'host': os.getenv('DB_HOST', '127.0.0.1'),
    'port': int(os.getenv('DB_PORT', 5432)),
    'database': os.getenv('DB_NAME', 'trading_data'),
    'user': os.getenv('DB_USER', 'trading'),
    'password': os.getenv('DB_PASSWORD', 'trading_password'),
}


def get_db_connection():
    import psycopg2
    return psycopg2.connect(**DB_CONFIG)


def check_market_hours(**context):
    """Only run during US market hours (9:30 AM - 4:00 PM ET)."""
    from datetime import timezone
    now_utc = datetime.now(timezone.utc)
    # ET is UTC-4 (EDT) or UTC-5 (EST)
    # Approximate: market open 13:30 UTC, close 20:00 UTC (EDT)
    hour_utc = now_utc.hour
    weekday = now_utc.weekday()

    if weekday >= 5:
        logger.info("Weekend — skipping")
        return False

    if hour_utc < 13 or hour_utc >= 21:
        logger.info(f"Outside market hours (UTC {hour_utc}) — skipping")
        return False

    return True


def fetch_option_prices(**context):
    """Fetch current prices for all tickers with swing option holdings."""
    import psycopg2
    from psycopg2.extras import RealDictCursor
    import yfinance as yf

    conn = get_db_connection()
    prices = {}

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT DISTINCT ticker FROM portfolio_holdings
                WHERE holding_type = 'swing' AND asset_type = 'option'
            """)
            tickers = [row['ticker'] for row in cur.fetchall()]

        if not tickers:
            logger.info("No swing option positions to monitor")
            context['ti'].xcom_push(key='prices', value={})
            return {}

        logger.info(f"Fetching prices for {len(tickers)} option underliers")
        for ticker in tickers:
            try:
                stock = yf.Ticker(ticker)
                data = stock.history(period='1d')
                if not data.empty:
                    prices[ticker] = float(data['Close'].iloc[-1])
            except Exception as e:
                logger.warning(f"Failed to fetch {ticker}: {e}")

    except Exception as e:
        logger.error(f"Error fetching option prices: {e}")
    finally:
        conn.close()

    context['ti'].xcom_push(key='prices', value=prices)
    return prices


def evaluate_options(**context):
    """Evaluate all swing option positions for exit signals."""
    import psycopg2

    ti = context['ti']
    prices = ti.xcom_pull(key='prices', task_ids='fetch_option_prices') or {}

    if not prices:
        logger.info("No prices — nothing to evaluate")
        return {}

    conn = get_db_connection()
    actions = {'take_profit': [], 'reversal_exit': [], 'stop_loss': [], 'holds': []}

    try:
        sys.path.insert(0, '/app/src')
        from portfolio_manager import PortfolioManager

        pm = PortfolioManager(conn=conn)

        all_holdings = pm.get_holdings(holding_type='swing')
        option_holdings = [h for h in all_holdings if h.get('asset_type') == 'option']

        for holding in option_holdings:
            ticker = holding['ticker']
            current_price = float(holding.get('current_price', 0)) or float(holding['avg_cost_basis'])

            evaluation = pm.evaluate_option_exit(holding, current_price)
            action = evaluation['action']

            if action in ('take_profit', 'reversal_exit', 'stop_loss'):
                result = pm.execute_trade(
                    action='sell_to_close',
                    ticker=ticker,
                    quantity=float(holding['quantity']),
                    price=current_price,
                    holding_type='swing',
                    asset_type='option',
                    signal_source=f'monitor_{action}',
                    signal_details={'reason': evaluation['reason']},
                )
                if result.get('success'):
                    actions[action].append({
                        'ticker': ticker,
                        'reason': evaluation['reason'],
                        'pnl_pct': evaluation.get('pnl_pct', 0),
                    })
                    logger.info(f"[MONITOR] {action}: {ticker} — {evaluation['reason']}")
            else:
                actions['holds'].append({'ticker': ticker})

        # Also update prices for all holdings
        if prices:
            pm.update_prices(prices)

    except Exception as e:
        logger.error(f"Error evaluating options: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

    ti.xcom_push(key='options_actions', value=actions)
    return actions


def check_all_stop_losses(**context):
    """Check stop-losses for all holdings (not just options)."""
    import psycopg2

    ti = context['ti']
    prices = ti.xcom_pull(key='prices', task_ids='fetch_option_prices') or {}

    conn = get_db_connection()
    stop_loss_sales = []

    try:
        sys.path.insert(0, '/app/src')
        from portfolio_manager import PortfolioManager

        pm = PortfolioManager(conn=conn)
        if prices:
            pm.update_prices(prices)

        triggered = pm.check_stop_losses()
        for position in triggered:
            ticker = position['ticker']
            holding = pm.get_holding(ticker, position['holding_type'])
            if holding:
                action = 'sell' if holding['asset_type'] == 'stock' else 'sell_to_close'
                result = pm.execute_trade(
                    action=action,
                    ticker=ticker,
                    quantity=float(holding['quantity']),
                    price=position['current_price'],
                    holding_type=position['holding_type'],
                    asset_type=holding['asset_type'],
                    signal_source='monitor_stop_loss',
                )
                if result.get('success'):
                    stop_loss_sales.append({
                        'ticker': ticker,
                        'price': position['current_price'],
                        'loss_pct': position['unrealized_pnl_pct'],
                    })
                    logger.info(f"[MONITOR] Stop-loss: {ticker} at {position['unrealized_pnl_pct']:.2%}")

    except Exception as e:
        logger.error(f"Error checking stop losses: {e}")
    finally:
        conn.close()

    return stop_loss_sales


def send_monitor_notifications(**context):
    """Send notifications for options exits detected by monitor."""
    import psycopg2

    ti = context['ti']
    options_actions = ti.xcom_pull(key='options_actions', task_ids='evaluate_options') or {}

    conn = get_db_connection()
    total_sent = 0

    try:
        sys.path.insert(0, '/app/flask_app/app/services')
        from notification_service import send_portfolio_event_notification

        for tp in options_actions.get('take_profit', []):
            send_portfolio_event_notification(conn, 'take_profit', tp)
            total_sent += 1
        for rev in options_actions.get('reversal_exit', []):
            send_portfolio_event_notification(conn, 'reversal_exit', rev)
            total_sent += 1
        for sl in options_actions.get('stop_loss', []):
            send_portfolio_event_notification(conn, 'stop_loss', sl)
            total_sent += 1

        if total_sent:
            logger.info(f"[MONITOR] Sent {total_sent} notifications")
    except Exception as e:
        logger.error(f"Monitor notification error: {e}")
    finally:
        conn.close()

    return total_sent


def log_monitor_summary(**context):
    """Log a brief summary of the monitoring run."""
    ti = context['ti']
    options_actions = ti.xcom_pull(key='options_actions', task_ids='evaluate_options') or {}

    tp = len(options_actions.get('take_profit', []))
    re = len(options_actions.get('reversal_exit', []))
    sl = len(options_actions.get('stop_loss', []))
    holds = len(options_actions.get('holds', []))

    logger.info(
        f"[OPTIONS MONITOR] take_profit={tp}, reversal_exit={re}, stop_loss={sl}, holds={holds}"
    )


# Tasks
check_hours = ShortCircuitOperator(
    task_id='check_market_hours',
    python_callable=check_market_hours,
    provide_context=True,
    dag=dag,
)

fetch_prices = PythonOperator(
    task_id='fetch_option_prices',
    python_callable=fetch_option_prices,
    provide_context=True,
    dag=dag,
)

evaluate = PythonOperator(
    task_id='evaluate_options',
    python_callable=evaluate_options,
    provide_context=True,
    dag=dag,
)

stop_losses = PythonOperator(
    task_id='check_stop_losses',
    python_callable=check_all_stop_losses,
    provide_context=True,
    dag=dag,
)

notify = PythonOperator(
    task_id='send_monitor_notifications',
    python_callable=send_monitor_notifications,
    provide_context=True,
    dag=dag,
)

monitor_summary = PythonOperator(
    task_id='log_monitor_summary',
    python_callable=log_monitor_summary,
    provide_context=True,
    dag=dag,
)

# Flow: check_hours -> fetch_prices -> evaluate -> stop_losses -> notify -> summary
check_hours >> fetch_prices >> evaluate >> stop_losses >> notify >> monitor_summary
