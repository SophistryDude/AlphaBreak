"""
Airflow DAG: Portfolio Update
=============================
Runs at 9:00 AM EST (14:00 UTC) on weekdays.
Processes trend break signals and executes theoretical trades.

Portfolio Allocation:
- 75% Long-term investing (hold > 1 month)
- 25% Intra-day swing trading (hold 1-5 days)

Signal Sources:
- Trend break reports (daily/hourly) for swing trading
- 13F institutional sentiment for long-term positions
"""

from airflow import DAG
from airflow.operators.python import PythonOperator, ShortCircuitOperator
from airflow.utils.dates import days_ago
from datetime import datetime, timedelta
import sys
import os
import logging
import json

sys.path.insert(0, '/app')

logger = logging.getLogger(__name__)

default_args = {
    'owner': 'trading-system',
    'depends_on_past': False,
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
    'execution_timeout': timedelta(hours=1),
}

dag = DAG(
    'portfolio_update',
    default_args=default_args,
    description='Daily portfolio update at 9AM EST - processes signals and executes trades',
    schedule_interval='0 14 * * 1-5',  # 9 AM EST = 14:00 UTC, Mon-Fri
    start_date=days_ago(1),
    catchup=False,
    max_active_runs=1,
    tags=['portfolio', 'daily', 'trading'],
)

# Database connection
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'postgres-timeseries-service'),
    'port': int(os.getenv('DB_PORT', 5432)),
    'database': os.getenv('DB_NAME', 'trading_data'),
    'user': os.getenv('DB_USER', 'trading'),
    'password': os.getenv('DB_PASSWORD', 'change_me'),
}

# Portfolio configuration
PORTFOLIO_CONFIG = {
    'long_term_allocation': 0.75,
    'swing_allocation': 0.25,
    'max_position_pct': 0.05,
    'min_cash_reserve_pct': 0.20,
    'trend_break_threshold': 0.80,  # 80% probability threshold
    'max_trades_per_day': 10,
}


def get_db_connection():
    """Create database connection."""
    import psycopg2
    return psycopg2.connect(**DB_CONFIG)


def check_market_day(**context):
    """Skip on weekends and US market holidays."""
    today = datetime.utcnow().date()
    weekday = today.weekday()
    if weekday >= 5:
        logger.info(f"Skipping: {today} is a weekend day")
        return False
    return True


def fetch_trend_break_signals(**context):
    """
    Fetch recent trend break signals from the reports table.
    Creates portfolio signals for stocks with high probability breaks.
    """
    import psycopg2
    from psycopg2.extras import RealDictCursor

    conn = get_db_connection()
    signals = []

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get latest daily trend break reports from last 24 hours
            cur.execute("""
                SELECT DISTINCT ON (ticker)
                    ticker,
                    break_probability,
                    break_direction,
                    current_price,
                    cci_value,
                    rsi_value,
                    adx_value,
                    report_generated_at,
                    report_id
                FROM trend_break_reports
                WHERE report_frequency = 'daily'
                  AND report_generated_at >= NOW() - INTERVAL '24 hours'
                  AND break_probability >= %s
                ORDER BY ticker, report_generated_at DESC
            """, (PORTFOLIO_CONFIG['trend_break_threshold'],))

            for row in cur.fetchall():
                signal_type = f"trend_break_{row['break_direction']}"
                action = 'buy' if row['break_direction'] == 'bullish' else 'sell'

                signals.append({
                    'ticker': row['ticker'],
                    'signal_type': signal_type,
                    'suggested_action': action,
                    'holding_type': 'swing',  # Trend breaks are for swing trading
                    'signal_strength': float(row['break_probability']),
                    'signal_price': float(row['current_price']) if row['current_price'] else None,
                    'source_data': {
                        'report_id': str(row['report_id']),
                        'cci': float(row['cci_value']) if row['cci_value'] else None,
                        'rsi': float(row['rsi_value']) if row['rsi_value'] else None,
                        'adx': float(row['adx_value']) if row['adx_value'] else None,
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


def fetch_13f_signals(**context):
    """
    Fetch 13F institutional sentiment for long-term positions.
    Looks for stocks with STRONG_BUY or BUY signals from institutional holdings.
    """
    import psycopg2
    from psycopg2.extras import RealDictCursor

    conn = get_db_connection()
    signals = []

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get stocks with positive institutional sentiment
            cur.execute("""
                SELECT
                    ticker,
                    signal,
                    total_shares,
                    total_value_usd,
                    funds_buying,
                    funds_selling,
                    net_change_shares,
                    updated_at
                FROM f13_stock_aggregates
                WHERE signal IN ('STRONG_BUY', 'BUY')
                  AND updated_at >= NOW() - INTERVAL '7 days'
                  AND total_value_usd > 1000000  -- Min $1M institutional interest
                ORDER BY total_value_usd DESC
                LIMIT 20
            """)

            for row in cur.fetchall():
                signal_strength = 0.9 if row['signal'] == 'STRONG_BUY' else 0.75

                signals.append({
                    'ticker': row['ticker'],
                    'signal_type': f"13f_{row['signal'].lower()}",
                    'suggested_action': 'buy',
                    'holding_type': 'long_term',  # 13F signals are for long-term
                    'signal_strength': signal_strength,
                    'signal_price': None,  # Will fetch current price later
                    'source_data': {
                        'institutional_value': float(row['total_value_usd']),
                        'funds_buying': row['funds_buying'],
                        'funds_selling': row['funds_selling'],
                        'net_shares_change': float(row['net_change_shares']) if row['net_change_shares'] else 0,
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


def fetch_current_prices(**context):
    """Fetch current prices for all signal tickers using yfinance."""
    import yfinance as yf

    ti = context['ti']
    trend_signals = ti.xcom_pull(key='trend_signals', task_ids='fetch_trend_break_signals') or []
    f13_signals = ti.xcom_pull(key='13f_signals', task_ids='fetch_13f_signals') or []

    all_signals = trend_signals + f13_signals
    tickers = list(set(s['ticker'] for s in all_signals))

    if not tickers:
        logger.info("No tickers to fetch prices for")
        ti.xcom_push(key='prices', value={})
        return {}

    logger.info(f"Fetching prices for {len(tickers)} tickers")

    prices = {}
    try:
        for ticker in tickers:
            try:
                stock = yf.Ticker(ticker)
                data = stock.history(period='1d')
                if not data.empty:
                    prices[ticker] = float(data['Close'].iloc[-1])
            except Exception as e:
                logger.warning(f"Failed to fetch price for {ticker}: {e}")

        logger.info(f"Fetched prices for {len(prices)} tickers")

    except Exception as e:
        logger.error(f"Error fetching prices: {e}")

    ti.xcom_push(key='prices', value=prices)
    return prices


def create_portfolio_signals(**context):
    """Create portfolio signals from trend break and 13F data."""
    import psycopg2
    import uuid

    ti = context['ti']
    trend_signals = ti.xcom_pull(key='trend_signals', task_ids='fetch_trend_break_signals') or []
    f13_signals = ti.xcom_pull(key='13f_signals', task_ids='fetch_13f_signals') or []
    prices = ti.xcom_pull(key='prices', task_ids='fetch_current_prices') or {}

    conn = get_db_connection()
    created_count = 0

    try:
        with conn.cursor() as cur:
            all_signals = trend_signals + f13_signals

            # Sort by signal strength (strongest first)
            all_signals.sort(key=lambda x: x.get('signal_strength', 0), reverse=True)

            # Limit to max trades per day
            all_signals = all_signals[:PORTFOLIO_CONFIG['max_trades_per_day']]

            for signal in all_signals:
                ticker = signal['ticker']
                price = prices.get(ticker) or signal.get('signal_price')

                if not price:
                    logger.warning(f"No price available for {ticker}, skipping")
                    continue

                signal_id = uuid.uuid4()
                expires_at = datetime.utcnow() + timedelta(hours=24)

                cur.execute("""
                    INSERT INTO portfolio_signals
                    (signal_id, ticker, signal_type, suggested_action, holding_type,
                     signal_strength, signal_price, source_data, expires_at, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending')
                    ON CONFLICT DO NOTHING
                """, (
                    signal_id,
                    ticker,
                    signal['signal_type'],
                    signal['suggested_action'],
                    signal['holding_type'],
                    signal.get('signal_strength'),
                    price,
                    json.dumps(signal.get('source_data')),
                    expires_at,
                ))
                created_count += 1

            conn.commit()

        logger.info(f"Created {created_count} portfolio signals")
        ti.xcom_push(key='signals_created', value=created_count)

    except Exception as e:
        logger.error(f"Error creating portfolio signals: {e}")
        conn.rollback()
    finally:
        conn.close()

    return created_count


def process_signals(**context):
    """Process pending signals and execute trades."""
    import psycopg2
    from psycopg2.extras import RealDictCursor

    ti = context['ti']
    prices = ti.xcom_pull(key='prices', task_ids='fetch_current_prices') or {}

    conn = get_db_connection()
    executed_trades = []

    try:
        # Import portfolio manager
        sys.path.insert(0, '/app/src')
        from portfolio_manager import PortfolioManager

        pm = PortfolioManager(conn=conn)

        # Get pending signals
        signals = pm.get_pending_signals()
        logger.info(f"Processing {len(signals)} pending signals")

        for signal in signals:
            ticker = signal['ticker']
            current_price = prices.get(ticker, signal.get('signal_price'))

            if not current_price:
                logger.warning(f"No price for {ticker}, skipping signal")
                continue

            # Skip sells for now (only process buys for new positions)
            if signal['suggested_action'] != 'buy':
                continue

            # Process the signal
            result = pm.process_signal(str(signal['signal_id']), current_price)

            if result.get('success'):
                executed_trades.append({
                    'ticker': ticker,
                    'action': signal['suggested_action'],
                    'quantity': result.get('quantity'),
                    'price': current_price,
                    'holding_type': signal['holding_type'],
                })
                logger.info(f"Executed trade: {signal['suggested_action']} {ticker}")
            else:
                logger.warning(f"Trade failed for {ticker}: {result.get('error')}")

        ti.xcom_push(key='executed_trades', value=executed_trades)

    except Exception as e:
        logger.error(f"Error processing signals: {e}")
    finally:
        conn.close()

    return executed_trades


def manage_long_term_positions(**context):
    """
    Manage long-term positions:
    1. Check for bearish trend breaks in existing holdings
    2. Evaluate covered call vs exit
    3. Execute exits with sector rotation or add to watchlist
    4. Check for re-entry opportunities
    """
    import psycopg2
    from psycopg2.extras import RealDictCursor

    ti = context['ti']
    trend_signals = ti.xcom_pull(key='trend_signals', task_ids='fetch_trend_break_signals') or []
    prices = ti.xcom_pull(key='prices', task_ids='fetch_current_prices') or {}

    conn = get_db_connection()
    actions_taken = {
        'exits': [],
        'covered_calls': [],
        'reentries': [],
        'holds': [],
    }

    try:
        sys.path.insert(0, '/app/src')
        from portfolio_manager import PortfolioManager

        pm = PortfolioManager(conn=conn)

        # Get current long-term holdings
        long_term_holdings = pm.get_holdings(holding_type='long_term')
        logger.info(f"Checking {len(long_term_holdings)} long-term positions for bearish signals")

        # Build lookup of bearish signals by ticker
        bearish_signals = {}
        bullish_signals = []
        for signal in trend_signals:
            if 'bearish' in signal.get('signal_type', '').lower():
                bearish_signals[signal['ticker']] = signal
            elif 'bullish' in signal.get('signal_type', '').lower():
                bullish_signals.append(signal)

        # Check each long-term holding for bearish signals
        for holding in long_term_holdings:
            ticker = holding['ticker']
            current_price = prices.get(ticker) or float(holding.get('current_price', 0))

            if not current_price:
                continue

            # Check if we have a bearish signal for this holding
            if ticker in bearish_signals:
                bearish_signal = bearish_signals[ticker]
                bearish_prob = bearish_signal.get('signal_strength', 0)

                logger.info(f"Bearish signal for {ticker}: {bearish_prob:.0%} probability")

                # Evaluate covered call vs exit
                evaluation = pm.evaluate_covered_call_vs_exit(
                    ticker=ticker,
                    current_price=current_price,
                    bearish_probability=bearish_prob,
                )

                if evaluation['action'] == 'exit':
                    # Exit with potential sector rotation
                    result = pm.exit_with_sector_rotation(
                        ticker=ticker,
                        current_price=current_price,
                        exit_reason=f"trend_break_bearish_{bearish_prob:.0%}",
                        signals=bullish_signals,
                    )

                    if result.get('success'):
                        actions_taken['exits'].append({
                            'ticker': ticker,
                            'price': current_price,
                            'reason': evaluation['reason'],
                            'rotated_to': result.get('rotated_to'),
                        })
                        logger.info(f"Exited {ticker}: {evaluation['reason']}")

                elif evaluation['action'] == 'covered_call':
                    # Write covered call instead of exiting
                    from datetime import date, timedelta as td

                    # Calculate expiration ~30 days out, on a Friday
                    exp_date = date.today() + td(days=30)
                    while exp_date.weekday() != 4:  # Find next Friday
                        exp_date += td(days=1)

                    # Estimate premium (3% of stock price for monthly ATM)
                    estimated_premium = current_price * 0.03

                    result = pm.write_covered_call(
                        ticker=ticker,
                        strike_price=evaluation['strike_price'],
                        expiration_date=exp_date,
                        premium_per_share=estimated_premium,
                        contracts=evaluation['contracts'],
                    )

                    if result.get('success'):
                        actions_taken['covered_calls'].append({
                            'ticker': ticker,
                            'strike': evaluation['strike_price'],
                            'contracts': evaluation['contracts'],
                            'premium': result['total_premium'],
                            'expiration': exp_date.isoformat(),
                        })
                        logger.info(f"Wrote covered call on {ticker}: {evaluation['contracts']} contracts @ ${evaluation['strike_price']}")

                else:  # hold
                    actions_taken['holds'].append({
                        'ticker': ticker,
                        'reason': evaluation['reason'],
                    })

        # Check for re-entry opportunities from watchlist
        reentry_opportunities = pm.check_reentry_opportunities(bullish_signals)
        logger.info(f"Found {len(reentry_opportunities)} potential re-entry opportunities")

        for opportunity in reentry_opportunities:
            item = opportunity['watchlist_item']
            current_price = opportunity.get('current_price')

            if current_price:
                result = pm.execute_reentry(
                    watchlist_id=item['id'],
                    current_price=current_price,
                )

                if result.get('success'):
                    actions_taken['reentries'].append({
                        'ticker': item['ticker'],
                        'price': current_price,
                        'signal_strength': opportunity['signal_strength'],
                    })
                    logger.info(f"Re-entered {item['ticker']} from watchlist at ${current_price:.2f}")

        # Check for expiring covered calls
        expiring_calls = pm.check_expiring_calls(days_ahead=1)
        for call in expiring_calls:
            ticker = call['ticker']
            current_price = prices.get(ticker)

            if current_price and current_price < float(call['strike_price']):
                # Call will expire worthless - close it
                pm.close_covered_call(str(call['call_id']), close_reason='expired_worthless')
                logger.info(f"Covered call on {ticker} expired worthless (premium kept)")

        ti.xcom_push(key='long_term_actions', value=actions_taken)

    except Exception as e:
        logger.error(f"Error managing long-term positions: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

    return actions_taken


def check_stop_losses(**context):
    """Check for holdings that have hit stop-loss and sell them."""
    import psycopg2

    ti = context['ti']
    prices = ti.xcom_pull(key='prices', task_ids='fetch_current_prices') or {}

    conn = get_db_connection()
    stop_loss_sales = []

    try:
        sys.path.insert(0, '/app/src')
        from portfolio_manager import PortfolioManager

        pm = PortfolioManager(conn=conn)

        # Update prices first
        if prices:
            pm.update_prices(prices)

        # Check stop losses
        triggered = pm.check_stop_losses()
        logger.info(f"Found {len(triggered)} positions at stop-loss")

        for position in triggered:
            ticker = position['ticker']
            current_price = position['current_price']

            # Get the holding to know quantity
            holding = pm.get_holding(ticker, position['holding_type'])
            if holding:
                result = pm.execute_trade(
                    action='sell',
                    ticker=ticker,
                    quantity=float(holding['quantity']),
                    price=current_price,
                    holding_type=position['holding_type'],
                    signal_source='stop_loss',
                )

                if result.get('success'):
                    stop_loss_sales.append({
                        'ticker': ticker,
                        'quantity': float(holding['quantity']),
                        'price': current_price,
                        'loss_pct': position['unrealized_pnl_pct'],
                    })
                    logger.info(f"Stop-loss sell: {ticker} at {position['unrealized_pnl_pct']:.2%}")

        ti.xcom_push(key='stop_loss_sales', value=stop_loss_sales)

    except Exception as e:
        logger.error(f"Error checking stop losses: {e}")
    finally:
        conn.close()

    return stop_loss_sales


def create_daily_snapshot(**context):
    """Create end-of-day portfolio snapshot."""
    import psycopg2

    conn = get_db_connection()

    try:
        sys.path.insert(0, '/app/src')
        from portfolio_manager import PortfolioManager

        pm = PortfolioManager(conn=conn)
        snapshot = pm.create_daily_snapshot()

        logger.info(f"Created daily snapshot: ${snapshot['total_value']:.2f}")
        context['ti'].xcom_push(key='snapshot', value=snapshot)

    except Exception as e:
        logger.error(f"Error creating daily snapshot: {e}")
    finally:
        conn.close()


def log_summary(**context):
    """Log a summary of the portfolio update run."""
    ti = context['ti']

    signals_created = ti.xcom_pull(key='signals_created', task_ids='create_portfolio_signals') or 0
    executed_trades = ti.xcom_pull(key='executed_trades', task_ids='process_signals') or []
    stop_loss_sales = ti.xcom_pull(key='stop_loss_sales', task_ids='check_stop_losses') or []
    long_term_actions = ti.xcom_pull(key='long_term_actions', task_ids='manage_long_term_positions') or {}
    snapshot = ti.xcom_pull(key='snapshot', task_ids='create_daily_snapshot') or {}

    summary = f"""
=== PORTFOLIO UPDATE SUMMARY ===
Date: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}

Signals:
  - Created: {signals_created}
  - Executed new trades: {len(executed_trades)}
  - Stop-loss sales: {len(stop_loss_sales)}

Long-Term Position Management:
  - Exits (bearish trend break): {len(long_term_actions.get('exits', []))}
  - Covered calls written: {len(long_term_actions.get('covered_calls', []))}
  - Re-entries from watchlist: {len(long_term_actions.get('reentries', []))}
  - Positions held: {len(long_term_actions.get('holds', []))}

New Trades Executed:
"""
    for trade in executed_trades:
        summary += f"  - {trade['action'].upper()} {trade['ticker']}: {trade['quantity']} @ ${trade['price']:.2f}\n"

    if long_term_actions.get('exits'):
        summary += "\nLong-Term Exits (Bearish Signals):\n"
        for exit in long_term_actions['exits']:
            rotation = f" -> Rotated to {exit['rotated_to']}" if exit.get('rotated_to') else " (added to watchlist)"
            summary += f"  - SELL {exit['ticker']} @ ${exit['price']:.2f}{rotation}\n"

    if long_term_actions.get('covered_calls'):
        summary += "\nCovered Calls Written:\n"
        for cc in long_term_actions['covered_calls']:
            summary += f"  - {cc['ticker']}: {cc['contracts']} contracts @ ${cc['strike']:.2f} exp {cc['expiration']} (${cc['premium']:.2f} premium)\n"

    if long_term_actions.get('reentries'):
        summary += "\nWatchlist Re-Entries:\n"
        for re in long_term_actions['reentries']:
            summary += f"  - BUY {re['ticker']} @ ${re['price']:.2f} (signal strength: {re['signal_strength']:.0%})\n"

    if stop_loss_sales:
        summary += "\nStop-Loss Sales:\n"
        for sale in stop_loss_sales:
            summary += f"  - SELL {sale['ticker']}: {sale['quantity']} @ ${sale['price']:.2f} ({sale['loss_pct']:.2%})\n"

    if snapshot:
        summary += f"""
Portfolio Status:
  - Total Value: ${snapshot.get('total_value', 0):.2f}
  - Daily P&L: ${snapshot.get('daily_pnl', 0):.2f} ({snapshot.get('daily_pnl_pct', 0):.2%})
  - Total P&L: ${snapshot.get('total_pnl', 0):.2f} ({snapshot.get('total_pnl_pct', 0):.2%})
  - Open Positions: {snapshot.get('positions', 0)}
  - Win Rate: {snapshot.get('win_rate', 0):.1%}
"""

    summary += "================================"

    logger.info(summary)


# Define tasks
check_market = ShortCircuitOperator(
    task_id='check_market_day',
    python_callable=check_market_day,
    provide_context=True,
    dag=dag,
)

fetch_trend_signals = PythonOperator(
    task_id='fetch_trend_break_signals',
    python_callable=fetch_trend_break_signals,
    provide_context=True,
    dag=dag,
)

fetch_13f = PythonOperator(
    task_id='fetch_13f_signals',
    python_callable=fetch_13f_signals,
    provide_context=True,
    dag=dag,
)

fetch_prices = PythonOperator(
    task_id='fetch_current_prices',
    python_callable=fetch_current_prices,
    provide_context=True,
    dag=dag,
)

create_signals = PythonOperator(
    task_id='create_portfolio_signals',
    python_callable=create_portfolio_signals,
    provide_context=True,
    dag=dag,
)

process = PythonOperator(
    task_id='process_signals',
    python_callable=process_signals,
    provide_context=True,
    dag=dag,
)

manage_long_term = PythonOperator(
    task_id='manage_long_term_positions',
    python_callable=manage_long_term_positions,
    provide_context=True,
    dag=dag,
)

stop_losses = PythonOperator(
    task_id='check_stop_losses',
    python_callable=check_stop_losses,
    provide_context=True,
    dag=dag,
)

snapshot = PythonOperator(
    task_id='create_daily_snapshot',
    python_callable=create_daily_snapshot,
    provide_context=True,
    dag=dag,
)

summary = PythonOperator(
    task_id='log_summary',
    python_callable=log_summary,
    provide_context=True,
    dag=dag,
)

# Task flow
#                         /-> fetch_trend_signals -\                                          /-> process (new swing positions)
# check_market -> fork ->                           -> fetch_prices -> create_signals -> fork ->  manage_long_term -> stop_losses -> snapshot -> summary
#                         \-> fetch_13f -----------/                                          \                    /
#
# Long-term position management:
# - Checks existing holdings for bearish trend breaks
# - Evaluates covered call vs exit strategy
# - Executes sector rotation or adds to watchlist
# - Checks watchlist for bullish re-entry signals

check_market >> [fetch_trend_signals, fetch_13f]
[fetch_trend_signals, fetch_13f] >> fetch_prices
fetch_prices >> create_signals >> [process, manage_long_term]
[process, manage_long_term] >> stop_losses >> snapshot >> summary
