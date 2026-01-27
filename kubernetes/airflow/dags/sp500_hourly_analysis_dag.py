"""
Airflow DAG for Hourly S&P 500 Analysis

Runs every hour to analyze all S&P 500 stocks and update predictions.
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
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
    'execution_timeout': timedelta(hours=1),
}

dag = DAG(
    'sp500_hourly_analysis',
    default_args=default_args,
    description='Hourly analysis of S&P 500 stocks',
    schedule_interval='0 * * * *',  # Every hour
    start_date=days_ago(1),
    catchup=False,
    max_active_runs=1,
    tags=['sp500', 'hourly', 'analysis'],
)

# Database connection
DB_CONFIG = {
    'host': 'postgres-timeseries-service',
    'port': 5432,
    'database': 'trading_data',
    'user': 'trading',
    'password': 'change_me'  # Use secret in production
}


def get_sp500_tickers():
    """Get list of S&P 500 tickers."""
    # In production, fetch from a maintained list or API
    # This is a subset for demonstration
    return [
        'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'BRK.B',
        'UNH', 'JNJ', 'XOM', 'JPM', 'V', 'PG', 'MA', 'HD', 'CVX', 'MRK',
        'ABBV', 'PEP', 'COST', 'AVGO', 'KO', 'WMT', 'MCD', 'CSCO', 'TMO',
        'ACN', 'ABT', 'DHR', 'LIN', 'VZ', 'ADBE', 'NKE', 'CRM', 'PM',
        'TXN', 'NFLX', 'DIS', 'CMCSA', 'WFC', 'NEE', 'BMY', 'UPS', 'RTX',
        'HON', 'ORCL', 'QCOM', 'INTC', 'IBM'  # Top 50
    ]


def fetch_latest_prices(**context):
    """Fetch latest prices for S&P 500 stocks and store in database."""
    import yfinance as yf

    tickers = get_sp500_tickers()
    timestamp = datetime.now()

    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    prices_data = []
    failed_tickers = []

    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period='1d', interval='1h')

            if not hist.empty:
                latest = hist.iloc[-1]
                prices_data.append((
                    ticker,
                    timestamp,
                    float(latest['Open']),
                    float(latest['High']),
                    float(latest['Low']),
                    float(latest['Close']),
                    int(latest['Volume']),
                    float(latest['Close'])  # adjusted_close
                ))
        except Exception as e:
            print(f"Error fetching {ticker}: {e}")
            failed_tickers.append(ticker)

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

    context['ti'].xcom_push(key='successful_tickers', value=len(prices_data))
    context['ti'].xcom_push(key='failed_tickers', value=failed_tickers)

    print(f"Fetched prices for {len(prices_data)} tickers")
    if failed_tickers:
        print(f"Failed tickers: {', '.join(failed_tickers)}")

    return {'success': len(prices_data), 'failed': len(failed_tickers)}


def calculate_indicators(**context):
    """Calculate technical indicators for all S&P 500 stocks."""
    import pandas as pd
    import pandas_ta as ta

    tickers = get_sp500_tickers()
    timestamp = datetime.now()

    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    indicators_data = []

    for ticker in tickers[:10]:  # Process in batches for efficiency
        try:
            # Fetch last 50 hours of data
            query = """
                SELECT timestamp, open, high, low, close, volume
                FROM stock_prices
                WHERE ticker = %s
                ORDER BY timestamp DESC
                LIMIT 50
            """
            cursor.execute(query, (ticker,))
            rows = cursor.fetchall()

            if len(rows) < 20:  # Need enough data
                continue

            df = pd.DataFrame(rows, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df = df.sort_values('timestamp')

            # Calculate indicators
            df['RSI'] = ta.rsi(df['close'], length=14)
            df['SMA_20'] = ta.sma(df['close'], length=20)
            df['EMA_12'] = ta.ema(df['close'], length=12)

            macd = ta.macd(df['close'])
            if macd is not None:
                df['MACD'] = macd['MACD_12_26_9']

            bbands = ta.bbands(df['close'], length=20)
            if bbands is not None:
                df['BB_UPPER'] = bbands['BBU_20_2.0']
                df['BB_LOWER'] = bbands['BBL_20_2.0']

            # Store latest values
            latest = df.iloc[-1]
            for indicator in ['RSI', 'SMA_20', 'EMA_12', 'MACD', 'BB_UPPER', 'BB_LOWER']:
                if indicator in latest and pd.notna(latest[indicator]):
                    indicators_data.append((
                        ticker,
                        timestamp,
                        indicator,
                        float(latest[indicator])
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

    print(f"Calculated {len(indicators_data)} indicator values")
    return {'indicators_calculated': len(indicators_data)}


def predict_trend_breaks(**context):
    """Predict trend breaks for S&P 500 stocks using trained model."""
    from trend_break_prediction import predict_trend_break
    import joblib

    tickers = get_sp500_tickers()[:20]  # Top 20 for hourly analysis
    timestamp = datetime.now()

    # Load model
    model = joblib.load('/app/models/trend_break_model.pkl')

    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    predictions_data = []

    for ticker in tickers:
        try:
            # Get recent data and predict
            prediction = predict_trend_break(
                ticker=ticker,
                model=model,
                lookback_days=30
            )

            if prediction:
                predictions_data.append((
                    ticker,
                    timestamp,
                    'trend_break',
                    float(prediction['probability']),
                    float(prediction['confidence']),
                    None,  # actual_value (filled later)
                    None,  # actual_timestamp
                    prediction.get('model_version', 'v1.0'),
                    psycopg2.extras.Json(prediction.get('features', {})),
                    psycopg2.extras.Json(prediction.get('metadata', {}))
                ))

        except Exception as e:
            print(f"Error predicting {ticker}: {e}")

    # Store predictions
    if predictions_data:
        insert_query = """
            INSERT INTO predictions_log
            (ticker, prediction_timestamp, prediction_type, predicted_value,
             confidence, actual_value, actual_timestamp, model_version,
             features_used, metadata)
            VALUES %s
        """
        execute_values(cursor, insert_query, predictions_data)
        conn.commit()

    cursor.close()
    conn.close()

    context['ti'].xcom_push(key='predictions_count', value=len(predictions_data))

    print(f"Generated {len(predictions_data)} predictions")
    return {'predictions': len(predictions_data)}


def update_alerts(**context):
    """Update alerts for significant trend break predictions."""
    ti = context['ti']
    predictions_count = ti.xcom_pull(key='predictions_count', task_ids='predict_trends')

    # Query high-confidence predictions
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    query = """
        SELECT ticker, predicted_value, confidence
        FROM predictions_log
        WHERE prediction_timestamp > NOW() - INTERVAL '1 hour'
          AND confidence > 0.75
          AND prediction_type = 'trend_break'
        ORDER BY confidence DESC
        LIMIT 10
    """
    cursor.execute(query)
    alerts = cursor.fetchall()

    cursor.close()
    conn.close()

    if alerts:
        print("HIGH CONFIDENCE ALERTS:")
        for ticker, pred_value, confidence in alerts:
            print(f"  {ticker}: {pred_value:.2f} (confidence: {confidence:.2%})")

    # Could send to Slack, email, etc.
    return {'alert_count': len(alerts)}


# Define tasks
fetch_prices_task = PythonOperator(
    task_id='fetch_prices',
    python_callable=fetch_latest_prices,
    provide_context=True,
    dag=dag,
)

calculate_indicators_task = PythonOperator(
    task_id='calculate_indicators',
    python_callable=calculate_indicators,
    provide_context=True,
    dag=dag,
)

predict_trends_task = PythonOperator(
    task_id='predict_trends',
    python_callable=predict_trend_breaks,
    provide_context=True,
    dag=dag,
)

alerts_task = PythonOperator(
    task_id='update_alerts',
    python_callable=update_alerts,
    provide_context=True,
    dag=dag,
)

# Task dependencies
fetch_prices_task >> calculate_indicators_task >> predict_trends_task >> alerts_task
