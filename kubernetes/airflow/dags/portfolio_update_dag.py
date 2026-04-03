"""
Airflow DAG: Portfolio Update
=============================
Runs at 9:00 AM EST (14:00 UTC) on weekdays.
Processes trend break signals and executes theoretical trades.

Portfolio Allocation:
- 50% Long-term stock positions (hold > 1 month)
- 30% Swing options trading ($10K max per trade, 5 concurrent max)
- 20% Cash float for new options opportunities

Signal Sources:
- Trend break reports (daily/hourly) for swing options trading
- 13F institutional sentiment for long-term stock positions

Exit Strategy:
- Long-term: Multi-timeframe confirmation (daily+hourly must agree for full exit)
- Swing options: Volume-based profit-taking, reversal-based loss-cutting
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
    'host': os.getenv('DB_HOST', '127.0.0.1'),
    'port': int(os.getenv('DB_PORT', 5432)),
    'database': os.getenv('DB_NAME', 'trading_data'),
    'user': os.getenv('DB_USER', 'trading'),
    'password': os.getenv('DB_PASSWORD', 'trading_password'),
}

# Portfolio configuration
PORTFOLIO_CONFIG = {
    # Allocation: $50K long-term, $30K swing options, $20K options float
    'long_term_allocation': 0.50,
    'swing_allocation': 0.30,
    'cash_float_pct': 0.20,            # Cash float for new options trades
    'max_position_pct': 0.07,          # 7% per long-term stock
    'max_options_pct': 0.10,           # 10% ($10K) per options trade
    'max_concurrent_options': 5,       # Max 5 options at once
    # Signal thresholds
    'trend_break_threshold': 0.80,     # Default signal strength
    'capital_deployment_threshold': 0.70,  # Relaxed threshold when cash > 20%
    # Swing options
    'swing_option_target_dte': 30,
    'swing_option_max_dte': 45,
    # Long-term exit (multi-timeframe)
    'long_term_exit_threshold': 0.92,
    'long_term_trim_pct': 0.25,
    # Smart options exit
    'options_profit_volume_decline_ratio': 0.7,
    # Daily limits
    'max_swing_trades_per_day': 5,
    'max_long_term_trades_per_day': 5,
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
    Fetch recent trend break signals from the trend_breaks table.
    Creates portfolio signals for stocks with recent daily breaks.
    """
    import psycopg2
    from psycopg2.extras import RealDictCursor

    conn = get_db_connection()
    signals = []

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get latest daily trend breaks from last 30 days
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

                # Use magnitude as signal strength proxy (normalize to 0.8-1.0)
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
            # Get stocks with positive institutional sentiment from most recent quarter
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
                    'signal_price': None,  # Will fetch current price later
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
        # Check cash level for capital deployment mode
        from psycopg2.extras import RealDictCursor
        with conn.cursor(cursor_factory=RealDictCursor) as check_cur:
            check_cur.execute("SELECT cash_balance FROM portfolio_account LIMIT 1")
            account = check_cur.fetchone()
            cash_balance = float(account['cash_balance']) if account else 0
            # Rough total value estimate
            check_cur.execute("SELECT COALESCE(SUM(market_value), 0) as holdings FROM portfolio_holdings")
            holdings_val = float(check_cur.fetchone()['holdings'])
            total_value = cash_balance + holdings_val
            cash_pct = cash_balance / total_value if total_value > 0 else 1.0

        # If cash exceeds the 20% float target, accept weaker signals to deploy capital
        signal_threshold = PORTFOLIO_CONFIG['trend_break_threshold']
        if cash_pct > PORTFOLIO_CONFIG.get('cash_float_pct', 0.20):
            signal_threshold = PORTFOLIO_CONFIG.get('capital_deployment_threshold', 0.70)
            logger.info(f"Capital deployment mode: cash at {cash_pct:.1%}, relaxing threshold to {signal_threshold}")

        with conn.cursor() as cur:
            # Separate signals by holding type and apply per-type limits
            # Filter swing signals by threshold (may be relaxed in deployment mode)
            swing_signals = [s for s in trend_signals
                            if s.get('holding_type') == 'swing'
                            and s.get('signal_strength', 0) >= signal_threshold]
            long_term_signals = [s for s in f13_signals if s.get('holding_type') == 'long_term']

            swing_signals.sort(key=lambda x: x.get('signal_strength', 0), reverse=True)
            long_term_signals.sort(key=lambda x: x.get('signal_strength', 0), reverse=True)

            swing_signals = swing_signals[:PORTFOLIO_CONFIG['max_swing_trades_per_day']]
            long_term_signals = long_term_signals[:PORTFOLIO_CONFIG['max_long_term_trades_per_day']]

            all_signals = swing_signals + long_term_signals

            logger.info(
                f"Processing {len(swing_signals)} swing + {len(long_term_signals)} long-term signals "
                f"(from {len(trend_signals)} trend + {len(f13_signals)} 13F raw signals)"
            )

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

        logger.info(f"Created {created_count} portfolio signals ({len(swing_signals)} swing, {len(long_term_signals)} long-term)")
        ti.xcom_push(key='signals_created', value=created_count)
        ti.xcom_push(key='swing_signals_created', value=len(swing_signals))
        ti.xcom_push(key='long_term_signals_created', value=len(long_term_signals))

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

        # Get current holdings to avoid duplicate buys and validate sells
        current_holdings = {h['ticker']: h for h in pm.get_holdings()}

        for signal in signals:
            ticker = signal['ticker']
            current_price = prices.get(ticker, signal.get('signal_price'))

            if not current_price:
                logger.warning(f"No price for {ticker}, skipping signal")
                continue

            # For sell signals, only process if we hold the position
            if signal['suggested_action'] == 'sell':
                holding = current_holdings.get(ticker)
                if not holding:
                    logger.info(f"No position in {ticker} to sell, skipping bearish signal")
                    # Mark as rejected so it doesn't stay pending forever
                    with conn.cursor() as cur:
                        cur.execute("""
                            UPDATE portfolio_signals
                            SET status = 'rejected', rejection_reason = 'No position held to sell',
                                processed_at = NOW()
                            WHERE signal_id = %s
                        """, (str(signal['signal_id']),))
                        conn.commit()
                    continue

            # For buy signals, skip if we already hold the stock
            if signal['suggested_action'] == 'buy' and ticker in current_holdings:
                logger.info(f"Already holding {ticker}, skipping duplicate buy signal")
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE portfolio_signals
                        SET status = 'rejected', rejection_reason = 'Already holding position',
                            processed_at = NOW()
                        WHERE signal_id = %s
                    """, (str(signal['signal_id']),))
                    conn.commit()
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
        'trims': [],
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

            # Check multi-timeframe bearish status for this holding
            tf_check = pm.check_multi_timeframe_bearish(ticker)
            has_bearish = tf_check['daily_bearish'] or tf_check['hourly_bearish']

            # Also check if we have a bearish signal from trend_breaks
            if ticker in bearish_signals or has_bearish:
                bearish_signal = bearish_signals.get(ticker, {})
                bearish_prob = bearish_signal.get('signal_strength', 0)

                logger.info(
                    f"Bearish check for {ticker}: prob={bearish_prob:.0%}, "
                    f"daily={'YES' if tf_check['daily_bearish'] else 'no'}, "
                    f"hourly={'YES' if tf_check['hourly_bearish'] else 'no'}"
                )

                # Evaluate with multi-timeframe confirmation
                evaluation = pm.evaluate_covered_call_vs_exit(
                    ticker=ticker,
                    current_price=current_price,
                    bearish_probability=bearish_prob,
                    daily_bearish=tf_check['daily_bearish'],
                    hourly_bearish=tf_check['hourly_bearish'],
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

                elif evaluation['action'] == 'trim':
                    # Trim position (hourly bearish but daily not confirmed)
                    trim_pct = evaluation.get('trim_pct', 0.25)
                    result = pm.trim_position(ticker, trim_pct, current_price)

                    if result.get('success'):
                        actions_taken['trims'].append({
                            'ticker': ticker,
                            'price': current_price,
                            'trim_pct': trim_pct,
                            'reason': evaluation['reason'],
                        })
                        logger.info(f"Trimmed {ticker} by {trim_pct:.0%}: {evaluation['reason']}")
                    else:
                        logger.warning(f"Failed to trim {ticker}: {result.get('error')}")

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


def manage_swing_positions(**context):
    """
    Actively rotate swing positions:
    - Sell swing holdings that have bearish trend break signals
    - Free up cash for new options opportunities
    """
    import psycopg2
    from psycopg2.extras import RealDictCursor

    ti = context['ti']
    trend_signals = ti.xcom_pull(key='trend_signals', task_ids='fetch_trend_break_signals') or []
    prices = ti.xcom_pull(key='prices', task_ids='fetch_current_prices') or {}

    conn = get_db_connection()
    swing_actions = {'sells': [], 'holds': []}

    try:
        sys.path.insert(0, '/app/src')
        from portfolio_manager import PortfolioManager

        pm = PortfolioManager(conn=conn)

        # Find swing holdings with bearish signals
        holdings_to_sell = pm.get_swing_holdings_with_sell_signals(trend_signals)
        logger.info(f"Found {len(holdings_to_sell)} swing positions with bearish signals")

        for item in holdings_to_sell:
            holding = item['holding']
            ticker = holding['ticker']
            current_price = prices.get(ticker, float(holding.get('current_price', 0)))

            if not current_price:
                continue

            # Execute sell
            result = pm.execute_trade(
                action='sell' if holding['asset_type'] == 'stock' else 'sell_to_close',
                ticker=ticker,
                quantity=float(holding['quantity']),
                price=current_price,
                holding_type='swing',
                asset_type=holding['asset_type'],
                signal_source='swing_rotation_bearish',
                signal_details=item['signal'].get('source_data'),
            )

            if result.get('success'):
                swing_actions['sells'].append({
                    'ticker': ticker,
                    'price': current_price,
                    'reason': item['reason'],
                    'asset_type': holding['asset_type'],
                })
                logger.info(f"Swing rotation: sold {ticker} ({item['reason']})")
            else:
                logger.warning(f"Failed to sell swing {ticker}: {result.get('error')}")

        ti.xcom_push(key='swing_actions', value=swing_actions)

    except Exception as e:
        logger.error(f"Error managing swing positions: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

    return swing_actions


def manage_swing_options(**context):
    """
    Smart exit management for swing options positions:
    - Take profit when volume declines (leave near the top)
    - Exit on reversal signal (accept ~50% loss)
    - Hard stop at 50% loss
    """
    import psycopg2
    from psycopg2.extras import RealDictCursor
    import yfinance as yf

    ti = context['ti']
    prices = ti.xcom_pull(key='prices', task_ids='fetch_current_prices') or {}

    conn = get_db_connection()
    options_actions = {'take_profit': [], 'reversal_exit': [], 'stop_loss': [], 'holds': []}

    try:
        sys.path.insert(0, '/app/src')
        from portfolio_manager import PortfolioManager

        pm = PortfolioManager(conn=conn)

        # Get all swing options holdings
        all_holdings = pm.get_holdings(holding_type='swing')
        option_holdings = [h for h in all_holdings if h.get('asset_type') == 'option']
        logger.info(f"Evaluating {len(option_holdings)} swing options for exit signals")

        for holding in option_holdings:
            ticker = holding['ticker']

            # Get current option price (use stored price or fetch)
            current_price = float(holding.get('current_price', 0))
            if not current_price:
                # Try to estimate from underlying price movement
                underlying_price = prices.get(ticker)
                if underlying_price:
                    current_price = float(holding['avg_cost_basis'])  # Fallback to cost basis
                else:
                    continue

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
                    signal_source=f'smart_exit_{action}',
                    signal_details={'reason': evaluation['reason'], 'pnl_pct': evaluation.get('pnl_pct')},
                )

                if result.get('success'):
                    options_actions[action].append({
                        'ticker': ticker,
                        'price': current_price,
                        'reason': evaluation['reason'],
                        'pnl_pct': evaluation.get('pnl_pct', 0),
                    })
                    logger.info(f"Options {action}: {ticker} — {evaluation['reason']}")
                else:
                    logger.warning(f"Failed options exit for {ticker}: {result.get('error')}")
            else:
                options_actions['holds'].append({'ticker': ticker, 'reason': evaluation['reason']})

        ti.xcom_push(key='options_actions', value=options_actions)

    except Exception as e:
        logger.error(f"Error managing swing options: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

    return options_actions


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
    swing_created = ti.xcom_pull(key='swing_signals_created', task_ids='create_portfolio_signals') or 0
    lt_created = ti.xcom_pull(key='long_term_signals_created', task_ids='create_portfolio_signals') or 0
    executed_trades = ti.xcom_pull(key='executed_trades', task_ids='process_signals') or []
    stop_loss_sales = ti.xcom_pull(key='stop_loss_sales', task_ids='check_stop_losses') or []
    long_term_actions = ti.xcom_pull(key='long_term_actions', task_ids='manage_long_term_positions') or {}
    swing_actions = ti.xcom_pull(key='swing_actions', task_ids='manage_swing_positions') or {}
    snapshot = ti.xcom_pull(key='snapshot', task_ids='create_daily_snapshot') or {}

    swing_sells = swing_actions.get('sells', [])

    summary = f"""
=== PORTFOLIO UPDATE SUMMARY ===
Date: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}

Signals:
  - Created: {signals_created} ({swing_created} swing, {lt_created} long-term)
  - Executed new trades: {len(executed_trades)}
  - Swing rotations (bearish exits): {len(swing_sells)}
  - Stop-loss sales: {len(stop_loss_sales)}

Long-Term Position Management:
  - Exits (bearish trend break): {len(long_term_actions.get('exits', []))}
  - Covered calls written: {len(long_term_actions.get('covered_calls', []))}
  - Trims (hourly-only bearish): {len(long_term_actions.get('trims', []))}
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

    if long_term_actions.get('trims'):
        summary += "\nLong-Term Trims (Hourly-Only Bearish):\n"
        for trim in long_term_actions['trims']:
            summary += f"  - TRIM {trim['ticker']}: {trim.get('trim_pct', 25)}% @ ${trim['price']:.2f}\n"

    if long_term_actions.get('reentries'):
        summary += "\nWatchlist Re-Entries:\n"
        for re in long_term_actions['reentries']:
            summary += f"  - BUY {re['ticker']} @ ${re['price']:.2f} (signal strength: {re['signal_strength']:.0%})\n"

    if swing_sells:
        summary += "\nSwing Rotations (Bearish Exits):\n"
        for sell in swing_sells:
            summary += f"  - SELL {sell['ticker']} ({sell.get('asset_type', 'option')}) @ ${sell['price']:.2f} ({sell['reason']})\n"

    if stop_loss_sales:
        summary += "\nStop-Loss Sales:\n"
        for sale in stop_loss_sales:
            summary += f"  - SELL {sale['ticker']}: {sale['quantity']} @ ${sale['price']:.2f} ({sale['loss_pct']:.2%})\n"

    if snapshot:
        total_val = snapshot.get('total_value') or 0
        daily_pnl = snapshot.get('daily_pnl') or 0
        daily_pnl_pct = snapshot.get('daily_pnl_pct') or 0
        total_pnl = snapshot.get('total_pnl') or 0
        total_pnl_pct = snapshot.get('total_pnl_pct') or 0
        positions = snapshot.get('positions') or 0
        win_rate = snapshot.get('win_rate') or 0
        summary += f"""
Portfolio Status:
  - Total Value: ${total_val:.2f}
  - Daily P&L: ${daily_pnl:.2f} ({daily_pnl_pct:.2%})
  - Total P&L: ${total_pnl:.2f} ({total_pnl_pct:.2%})
  - Open Positions: {positions}
  - Win Rate: {win_rate:.1%}
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

manage_swing = PythonOperator(
    task_id='manage_swing_positions',
    python_callable=manage_swing_positions,
    provide_context=True,
    dag=dag,
)

manage_options = PythonOperator(
    task_id='manage_swing_options',
    python_callable=manage_swing_options,
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
#                         /-> fetch_trend_signals -\                                          /-> process (new swing options)
# check_market -> fork ->                           -> fetch_prices -> create_signals -> fork -> manage_long_term (multi-TF)
#                         \-> fetch_13f -----------/                                          \-> manage_swing (active rotation)
#                                                                                                      |
#                                                                          [all three] -> stop_losses -> snapshot -> summary

check_market >> [fetch_trend_signals, fetch_13f]
[fetch_trend_signals, fetch_13f] >> fetch_prices
fetch_prices >> create_signals >> [process, manage_long_term, manage_swing, manage_options]
[process, manage_long_term, manage_swing, manage_options] >> stop_losses >> snapshot >> summary
