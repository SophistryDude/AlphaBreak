"""
Airflow DAG for Daily Indicator Analysis

Runs daily at 2 AM to analyze indicator accuracy across multiple stocks.
"""

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.utils.dates import days_ago
from datetime import datetime, timedelta
import sys
import os

# Add project root to path
sys.path.insert(0, '/app')

default_args = {
    'owner': 'trading-system',
    'depends_on_past': False,
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
    'execution_timeout': timedelta(hours=2),
}

dag = DAG(
    'indicator_analysis_dag',
    default_args=default_args,
    description='Daily indicator accuracy analysis',
    schedule_interval='0 2 * * *',  # Daily at 2 AM
    start_date=days_ago(1),
    catchup=False,
    tags=['analysis', 'indicators', 'daily'],
)


def fetch_latest_market_data(**context):
    """Fetch latest market data for analysis."""
    from meta_learning_model import analyze_indicator_accuracy
    import pandas as pd
    from datetime import datetime, timedelta

    tickers = ['AAPL', 'GOOGL', 'MSFT', 'TSLA', 'AMZN', 'NVDA', 'META', 'SPY']
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')

    context['ti'].xcom_push(key='tickers', value=tickers)
    context['ti'].xcom_push(key='start_date', value=start_date)
    context['ti'].xcom_push(key='end_date', value=end_date)

    print(f"Prepared analysis for {len(tickers)} tickers from {start_date} to {end_date}")
    return {'status': 'success', 'tickers': len(tickers)}


def analyze_indicators(**context):
    """Run indicator accuracy analysis."""
    from meta_learning_model import analyze_indicator_accuracy
    import pandas as pd

    ti = context['ti']
    tickers = ti.xcom_pull(key='tickers', task_ids='fetch_data')
    start_date = ti.xcom_pull(key='start_date', task_ids='fetch_data')
    end_date = ti.xcom_pull(key='end_date', task_ids='fetch_data')

    results = []
    for ticker in tickers:
        try:
            print(f"Analyzing {ticker}...")
            result = analyze_indicator_accuracy(
                ticker=ticker,
                start_date=start_date,
                end_date=end_date,
                lookback_window=30,
                lookahead_window=30
            )
            results.append({
                'ticker': ticker,
                'status': 'success',
                'indicators_analyzed': len(result) if result is not None else 0
            })
        except Exception as e:
            print(f"Error analyzing {ticker}: {e}")
            results.append({
                'ticker': ticker,
                'status': 'error',
                'error': str(e)
            })

    # Save results
    results_df = pd.DataFrame(results)
    output_path = f"/app/logs/indicator_analysis_{end_date}.csv"
    results_df.to_csv(output_path, index=False)

    context['ti'].xcom_push(key='results_path', value=output_path)
    context['ti'].xcom_push(key='success_count', value=len([r for r in results if r['status'] == 'success']))

    return {'total': len(results), 'success': len([r for r in results if r['status'] == 'success'])}


def generate_report(**context):
    """Generate analysis report."""
    ti = context['ti']
    results_path = ti.xcom_pull(key='results_path', task_ids='analyze')
    success_count = ti.xcom_pull(key='success_count', task_ids='analyze')

    print(f"Analysis completed: {success_count} successful analyses")
    print(f"Results saved to: {results_path}")

    # Could send email, Slack notification, etc.
    return {'status': 'report_generated', 'success_count': success_count}


# Define tasks
fetch_data_task = PythonOperator(
    task_id='fetch_data',
    python_callable=fetch_latest_market_data,
    provide_context=True,
    dag=dag,
)

analyze_task = PythonOperator(
    task_id='analyze',
    python_callable=analyze_indicators,
    provide_context=True,
    dag=dag,
)

report_task = PythonOperator(
    task_id='generate_report',
    python_callable=generate_report,
    provide_context=True,
    dag=dag,
)

cleanup_task = BashOperator(
    task_id='cleanup',
    bash_command='find /app/logs -name "indicator_analysis_*.csv" -mtime +30 -delete',
    dag=dag,
)

# Define task dependencies
fetch_data_task >> analyze_task >> report_task >> cleanup_task
