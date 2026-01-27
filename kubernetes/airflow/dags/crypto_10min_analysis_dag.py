"""
Airflow DAG for 10-Minute Crypto Analysis

Runs every 10 minutes to analyze Bitcoin and Ethereum.
High-frequency analysis for volatile crypto markets.
"""

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago
from datetime import datetime, timedelta
import sys
import psycopg2
from psycopg2.extras import execute_values

sys.path.insert(0, '/app')

default_args = {
    'owner': 'trading-system',
    'depends_on_past': False,
    'email_on_failure': False,  # Too frequent for email alerts
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=2),
    'execution_timeout': timedelta(minutes=8),
}

dag = DAG(
    'crypto_10min_analysis',
    default_args=default_args,
    description='10-minute analysis of Bitcoin and Ethereum',
    schedule_interval='*/10 * * * *',  # Every 10 minutes
    start_date=days_ago(1),
    catchup=False,
    max_active_runs=1,
    tags=['crypto', 'bitcoin', 'ethereum', 'high-frequency'],
)

CRYPTO_TICKERS = ['BTC-USD', 'ETH-USD']

DB_CONFIG = {
    'host': 'postgres-timeseries-service',
    'port': 5432,
    'database': 'trading_data',
    'user': 'trading',
    'password': 'change_me'
}


def fetch_crypto_prices(**context):
    """Fetch latest crypto prices at 1-minute granularity."""
    import yfinance as yf

    timestamp = datetime.now()

    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    prices_data = []

    for ticker in CRYPTO_TICKERS:
        try:
            crypto = yf.Ticker(ticker)
            # Get last 10 minutes of 1-minute data
            hist = crypto.history(period='1d', interval='1m')

            if not hist.empty:
                # Store all recent 1-minute candles
                for idx, row in hist.tail(10).iterrows():
                    prices_data.append((
                        ticker,
                        idx.to_pydatetime(),
                        float(row['Open']),
                        float(row['High']),
                        float(row['Low']),
                        float(row['Close']),
                        int(row['Volume']),
                        float(row['Close'])
                    ))
        except Exception as e:
            print(f"Error fetching {ticker}: {e}")

    # Bulk insert
    if prices_data:
        insert_query = """
            INSERT INTO stock_prices
            (ticker, timestamp, open, high, low, close, volume, adjusted_close)
            VALUES %s
            ON CONFLICT (ticker, timestamp) DO UPDATE SET
                open = EXCLUDED.open,
                high = EXCLUDED.high,
                low = EXCLUDED.low,
                close = EXCLUDED.close,
                volume = EXCLUDED.volume,
                adjusted_close = EXCLUDED.adjusted_close
        """
        execute_values(cursor, insert_query, prices_data)
        conn.commit()

    cursor.close()
    conn.close()

    context['ti'].xcom_push(key='price_updates', value=len(prices_data))

    print(f"Stored {len(prices_data)} crypto price updates")
    return {'updates': len(prices_data)}


def calculate_crypto_indicators(**context):
    """Calculate high-frequency technical indicators."""
    import pandas as pd
    import pandas_ta as ta

    timestamp = datetime.now()

    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    indicators_data = []

    for ticker in CRYPTO_TICKERS:
        try:
            # Fetch last 200 minutes of data for indicator calculation
            query = """
                SELECT timestamp, open, high, low, close, volume
                FROM stock_prices
                WHERE ticker = %s
                  AND timestamp > NOW() - INTERVAL '4 hours'
                ORDER BY timestamp DESC
                LIMIT 200
            """
            cursor.execute(query, (ticker,))
            rows = cursor.fetchall()

            if len(rows) < 50:
                continue

            df = pd.DataFrame(rows, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df = df.sort_values('timestamp')

            # Fast-moving indicators for crypto
            df['RSI_14'] = ta.rsi(df['close'], length=14)
            df['RSI_7'] = ta.rsi(df['close'], length=7)  # Faster RSI
            df['EMA_9'] = ta.ema(df['close'], length=9)
            df['EMA_21'] = ta.ema(df['close'], length=21)

            # MACD for momentum
            macd = ta.macd(df['close'], fast=12, slow=26, signal=9)
            if macd is not None:
                df['MACD'] = macd['MACD_12_26_9']
                df['MACD_SIGNAL'] = macd['MACDs_12_26_9']
                df['MACD_HIST'] = macd['MACDh_12_26_9']

            # Bollinger Bands
            bbands = ta.bbands(df['close'], length=20, std=2)
            if bbands is not None:
                df['BB_UPPER'] = bbands['BBU_20_2.0']
                df['BB_LOWER'] = bbands['BBL_20_2.0']
                df['BB_MID'] = bbands['BBM_20_2.0']

            # ATR for volatility
            atr = ta.atr(df['high'], df['low'], df['close'], length=14)
            if atr is not None:
                df['ATR'] = atr

            # Volume indicators
            df['VOLUME_SMA_20'] = ta.sma(df['volume'], length=20)

            # Store latest values
            latest = df.iloc[-1]
            for indicator in ['RSI_14', 'RSI_7', 'EMA_9', 'EMA_21', 'MACD',
                            'MACD_SIGNAL', 'MACD_HIST', 'BB_UPPER', 'BB_LOWER',
                            'BB_MID', 'ATR', 'VOLUME_SMA_20']:
                if indicator in latest and pd.notna(latest[indicator]):
                    indicators_data.append((
                        ticker,
                        timestamp,
                        indicator,
                        float(latest[indicator])
                    ))

            # Calculate price momentum (% change over last 10 minutes)
            if len(df) >= 10:
                price_change_10m = ((df.iloc[-1]['close'] - df.iloc[-10]['close']) /
                                   df.iloc[-10]['close'] * 100)
                indicators_data.append((
                    ticker,
                    timestamp,
                    'MOMENTUM_10M',
                    float(price_change_10m)
                ))

        except Exception as e:
            print(f"Error calculating indicators for {ticker}: {e}")

    # Bulk insert
    if indicators_data:
        insert_query = """
            INSERT INTO technical_indicators
            (ticker, timestamp, indicator_name, indicator_value)
            VALUES %s
            ON CONFLICT (ticker, timestamp, indicator_name) DO UPDATE SET
                indicator_value = EXCLUDED.indicator_value
        """
        execute_values(cursor, insert_query, indicators_data)
        conn.commit()

    cursor.close()
    conn.close()

    context['ti'].xcom_push(key='indicators_calculated', value=len(indicators_data))

    print(f"Calculated {len(indicators_data)} crypto indicator values")
    return {'indicators': len(indicators_data)}


def detect_crypto_signals(**context):
    """Detect trading signals for crypto."""
    import pandas as pd

    timestamp = datetime.now()

    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    signals = []

    for ticker in CRYPTO_TICKERS:
        try:
            # Get latest indicators
            query = """
                SELECT indicator_name, indicator_value
                FROM technical_indicators
                WHERE ticker = %s
                  AND timestamp > NOW() - INTERVAL '15 minutes'
                ORDER BY timestamp DESC
                LIMIT 50
            """
            cursor.execute(query, (ticker,))
            rows = cursor.fetchall()

            indicators = {name: value for name, value in rows}

            # Get current price
            price_query = """
                SELECT close FROM stock_prices
                WHERE ticker = %s
                ORDER BY timestamp DESC
                LIMIT 1
            """
            cursor.execute(price_query, (ticker,))
            current_price = cursor.fetchone()[0]

            # Trading signals
            signal_list = []

            # RSI oversold/overbought
            if 'RSI_14' in indicators:
                rsi = indicators['RSI_14']
                if rsi < 30:
                    signal_list.append('RSI_OVERSOLD')
                elif rsi > 70:
                    signal_list.append('RSI_OVERBOUGHT')

            # MACD crossover
            if 'MACD' in indicators and 'MACD_SIGNAL' in indicators:
                if indicators['MACD'] > indicators['MACD_SIGNAL']:
                    signal_list.append('MACD_BULLISH')
                else:
                    signal_list.append('MACD_BEARISH')

            # Bollinger Band breakout
            if all(k in indicators for k in ['BB_UPPER', 'BB_LOWER']):
                if current_price > indicators['BB_UPPER']:
                    signal_list.append('BB_BREAKOUT_UP')
                elif current_price < indicators['BB_LOWER']:
                    signal_list.append('BB_BREAKOUT_DOWN')

            # Strong momentum
            if 'MOMENTUM_10M' in indicators:
                momentum = indicators['MOMENTUM_10M']
                if abs(momentum) > 2.0:  # 2% move in 10 minutes
                    signal_list.append(f'STRONG_MOMENTUM_{"UP" if momentum > 0 else "DOWN"}')

            # Store signals
            if signal_list:
                signal_metadata = {
                    'price': float(current_price),
                    'indicators': {k: float(v) for k, v in indicators.items()},
                    'signals': signal_list
                }

                signals.append((
                    ticker,
                    timestamp,
                    ', '.join(signal_list),
                    psycopg2.extras.Json(signal_metadata)
                ))

        except Exception as e:
            print(f"Error detecting signals for {ticker}: {e}")

    # Store signals in engineered_features table
    if signals:
        insert_query = """
            INSERT INTO engineered_features
            (ticker, timestamp, feature_name, feature_value, feature_metadata)
            VALUES %s
            ON CONFLICT (ticker, timestamp, feature_name) DO UPDATE SET
                feature_value = EXCLUDED.feature_value,
                feature_metadata = EXCLUDED.feature_metadata
        """
        # Add feature_value as 1.0 for signal presence
        signals_with_value = [(t, ts, 'TRADING_SIGNAL', 1.0, meta)
                             for t, ts, _, meta in signals]
        execute_values(cursor, insert_query, signals_with_value)
        conn.commit()

    cursor.close()
    conn.close()

    # Print alerts for monitoring
    if signals:
        print("CRYPTO SIGNALS DETECTED:")
        for ticker, _, signal_str, _ in signals:
            print(f"  {ticker}: {signal_str}")

    context['ti'].xcom_push(key='signals_count', value=len(signals))

    return {'signals': len(signals)}


def update_crypto_metrics(**context):
    """Update aggregated crypto metrics."""
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    metrics = {}

    for ticker in CRYPTO_TICKERS:
        try:
            # Calculate volatility (standard deviation of returns)
            query = """
                SELECT
                    STDDEV(close) as price_stddev,
                    AVG(volume) as avg_volume,
                    COUNT(*) as data_points
                FROM stock_prices
                WHERE ticker = %s
                  AND timestamp > NOW() - INTERVAL '1 hour'
            """
            cursor.execute(query, (ticker,))
            row = cursor.fetchone()

            if row:
                metrics[ticker] = {
                    'volatility': float(row[0]) if row[0] else 0,
                    'avg_volume': float(row[1]) if row[1] else 0,
                    'data_points': int(row[2])
                }

        except Exception as e:
            print(f"Error calculating metrics for {ticker}: {e}")

    cursor.close()
    conn.close()

    print(f"Crypto metrics: {metrics}")
    return metrics


# Define tasks
fetch_prices_task = PythonOperator(
    task_id='fetch_crypto_prices',
    python_callable=fetch_crypto_prices,
    provide_context=True,
    dag=dag,
)

calculate_indicators_task = PythonOperator(
    task_id='calculate_indicators',
    python_callable=calculate_crypto_indicators,
    provide_context=True,
    dag=dag,
)

detect_signals_task = PythonOperator(
    task_id='detect_signals',
    python_callable=detect_crypto_signals,
    provide_context=True,
    dag=dag,
)

update_metrics_task = PythonOperator(
    task_id='update_metrics',
    python_callable=update_crypto_metrics,
    provide_context=True,
    dag=dag,
)

# Task dependencies
fetch_prices_task >> calculate_indicators_task >> [detect_signals_task, update_metrics_task]
