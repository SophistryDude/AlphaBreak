"""
Airflow DAG: Model Retraining Pipeline

This DAG orchestrates the complete model retraining workflow:
1. Fetch latest market data
2. Analyze indicator accuracy
3. Train meta-learning model
4. Train trend break model
5. Validate models
6. Deploy new models
7. Send notifications

Schedule: Weekly on Sunday at 3 AM
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.utils.dates import days_ago
import sys
sys.path.append('/app')


default_args = {
    'owner': 'trading-system',
    'depends_on_past': False,
    'email': ['alerts@yourcompany.com'],
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'model_retraining_pipeline',
    default_args=default_args,
    description='Weekly model retraining and deployment',
    schedule_interval='0 3 * * 0',  # Sunday at 3 AM
    start_date=days_ago(1),
    catchup=False,
    tags=['ml', 'retraining', 'weekly'],
)


def fetch_latest_data(**context):
    """Task 1: Fetch latest market data for multiple tickers."""
    import pandas as pd
    import yfinance as yf
    from datetime import datetime, timedelta

    tickers = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA']
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=365*5)).strftime('%Y-%m-%d')  # 5 years

    print(f"Fetching data for {len(tickers)} tickers from {start_date} to {end_date}")

    data_status = {}
    for ticker in tickers:
        try:
            data = yf.download(ticker, start=start_date, end=end_date, progress=False)
            data_status[ticker] = {
                'success': True,
                'rows': len(data),
                'start_date': data.index[0].strftime('%Y-%m-%d'),
                'end_date': data.index[-1].strftime('%Y-%m-%d')
            }
            print(f"✓ {ticker}: {len(data)} rows")
        except Exception as e:
            data_status[ticker] = {'success': False, 'error': str(e)}
            print(f"✗ {ticker}: {e}")

    # Push results to XCom
    context['task_instance'].xcom_push(key='data_status', value=data_status)
    context['task_instance'].xcom_push(key='tickers', value=tickers)

    return data_status


def analyze_indicators(**context):
    """Task 2: Analyze indicator accuracy for each ticker."""
    from docs.code_snippets.SP_historical_data import analyze_indicator_accuracy, filter_best_indicators

    tickers = context['task_instance'].xcom_pull(key='tickers', task_ids='fetch_data')
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=365*3)).strftime('%Y-%m-%d')

    results = {}
    for ticker in tickers:
        try:
            print(f"Analyzing indicators for {ticker}...")
            analysis = analyze_indicator_accuracy(ticker, start_date, end_date)
            best = filter_best_indicators(analysis, 0.80, 0.90)

            results[ticker] = {
                'success': True,
                'best_indicators': best['indicator_names'],
                'mean_accuracy': float(best['mean_accuracy'])
            }
            print(f"✓ {ticker}: {len(best['indicator_names'])} indicators selected")
        except Exception as e:
            results[ticker] = {'success': False, 'error': str(e)}
            print(f"✗ {ticker}: {e}")

    context['task_instance'].xcom_push(key='indicator_analysis', value=results)
    return results


def train_meta_learning_model(**context):
    """Task 3: Train meta-learning model."""
    from meta_learning_model import (
        create_accuracy_features_dataset,
        train_indicator_reliability_model,
        save_model_artifacts
    )

    tickers = context['task_instance'].xcom_pull(key='tickers', task_ids='fetch_data')
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=365*5)).strftime('%Y-%m-%d')

    print("Creating accuracy features dataset...")
    dataset = create_accuracy_features_dataset(
        ticker=tickers[0],  # Use primary ticker
        start_date=start_date,
        end_date=end_date,
        lookback_window=30,
        lookahead_window=30,
        step_size=7
    )

    dataset.to_csv('/app/models/accuracy_features_latest.csv', index=False)
    print(f"✓ Dataset created: {len(dataset)} samples")

    print("Training meta-learning model...")
    results = train_indicator_reliability_model(
        dataset_path='/app/models/accuracy_features_latest.csv',
        epochs=50,
        batch_size=32
    )

    print("Saving model...")
    save_model_artifacts(results, output_dir='/app/models')

    context['task_instance'].xcom_push(key='meta_model_metrics', value={
        'test_loss': float(results['test_loss']),
        'test_mae': float(results['test_mae'])
    })

    print(f"✓ Meta-learning model trained (MAE: {results['test_mae']:.4f})")
    return results['test_mae']


def train_trend_break_model(**context):
    """Task 4: Train trend break prediction model."""
    from trend_break_prediction import train_trend_break_model, save_trend_break_model

    indicator_analysis = context['task_instance'].xcom_pull(
        key='indicator_analysis',
        task_ids='analyze_indicators'
    )

    tickers = context['task_instance'].xcom_pull(key='tickers', task_ids='fetch_data')
    ticker = tickers[0]  # Use primary ticker

    # Get best indicators
    best_indicators = indicator_analysis[ticker]['best_indicators']

    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=365*5)).strftime('%Y-%m-%d')
    test_split_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')

    print(f"Training trend break model with {len(best_indicators)} indicators...")
    results = train_trend_break_model(
        ticker=ticker,
        start_date=start_date,
        end_date=end_date,
        indicator_names=best_indicators,
        lookahead_days=10,
        engineer_features_flag=True,
        test_split_date=test_split_date
    )

    print("Saving model...")
    save_trend_break_model(results, output_dir='/app/models')

    context['task_instance'].xcom_push(key='trend_model_metrics', value={
        'auc_score': float(results['auc_score'])
    })

    print(f"✓ Trend break model trained (AUC: {results['auc_score']:.4f})")
    return results['auc_score']


def validate_models(**context):
    """Task 5: Validate trained models meet quality thresholds."""
    meta_metrics = context['task_instance'].xcom_pull(
        key='meta_model_metrics',
        task_ids='train_meta_model'
    )
    trend_metrics = context['task_instance'].xcom_pull(
        key='trend_model_metrics',
        task_ids='train_trend_model'
    )

    # Quality thresholds
    META_MAE_THRESHOLD = 0.15
    TREND_AUC_THRESHOLD = 0.65

    validation_passed = True
    issues = []

    if meta_metrics['test_mae'] > META_MAE_THRESHOLD:
        validation_passed = False
        issues.append(f"Meta-learning MAE ({meta_metrics['test_mae']:.4f}) exceeds threshold ({META_MAE_THRESHOLD})")

    if trend_metrics['auc_score'] < TREND_AUC_THRESHOLD:
        validation_passed = False
        issues.append(f"Trend model AUC ({trend_metrics['auc_score']:.4f}) below threshold ({TREND_AUC_THRESHOLD})")

    if not validation_passed:
        error_msg = "Model validation FAILED:\n" + "\n".join(f"  - {issue}" for issue in issues)
        raise ValueError(error_msg)

    print("✓ Model validation PASSED")
    print(f"  Meta-learning MAE: {meta_metrics['test_mae']:.4f}")
    print(f"  Trend model AUC: {trend_metrics['auc_score']:.4f}")

    return validation_passed


def deploy_models(**context):
    """Task 6: Deploy models (copy to production location)."""
    import shutil
    import os
    from datetime import datetime

    # Backup existing models
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_dir = f'/app/models/backups/{timestamp}'
    os.makedirs(backup_dir, exist_ok=True)

    models_to_backup = [
        '/app/models/indicator_reliability_model.h5',
        '/app/models/trend_break_model.json',
        '/app/models/model_metadata.pkl'
    ]

    for model_path in models_to_backup:
        if os.path.exists(model_path):
            shutil.copy(model_path, backup_dir)
            print(f"✓ Backed up {os.path.basename(model_path)}")

    print(f"✓ Models deployed and old models backed up to {backup_dir}")

    context['task_instance'].xcom_push(key='deployment_time', value=timestamp)
    return timestamp


def send_notification(**context):
    """Task 7: Send success notification."""
    import json

    meta_metrics = context['task_instance'].xcom_pull(
        key='meta_model_metrics',
        task_ids='train_meta_model'
    )
    trend_metrics = context['task_instance'].xcom_pull(
        key='trend_model_metrics',
        task_ids='train_trend_model'
    )
    deployment_time = context['task_instance'].xcom_pull(
        key='deployment_time',
        task_ids='deploy_models'
    )

    message = f"""
    🎉 Model Retraining Completed Successfully

    Deployment Time: {deployment_time}

    Model Performance:
    - Meta-Learning MAE: {meta_metrics['test_mae']:.4f}
    - Trend Break AUC: {trend_metrics['auc_score']:.4f}

    Next scheduled run: Sunday 3 AM
    """

    print(message)

    # TODO: Implement actual notification (Slack, email, etc.)
    # import requests
    # requests.post(SLACK_WEBHOOK_URL, json={'text': message})

    return message


# Define task dependencies
task_fetch_data = PythonOperator(
    task_id='fetch_data',
    python_callable=fetch_latest_data,
    dag=dag,
)

task_analyze_indicators = PythonOperator(
    task_id='analyze_indicators',
    python_callable=analyze_indicators,
    dag=dag,
)

task_train_meta_model = PythonOperator(
    task_id='train_meta_model',
    python_callable=train_meta_learning_model,
    dag=dag,
)

task_train_trend_model = PythonOperator(
    task_id='train_trend_model',
    python_callable=train_trend_break_model,
    dag=dag,
)

task_validate_models = PythonOperator(
    task_id='validate_models',
    python_callable=validate_models,
    dag=dag,
)

task_deploy_models = PythonOperator(
    task_id='deploy_models',
    python_callable=deploy_models,
    dag=dag,
)

task_notify = PythonOperator(
    task_id='send_notification',
    python_callable=send_notification,
    dag=dag,
)

# Set up task dependencies (DAG structure)
task_fetch_data >> task_analyze_indicators >> [task_train_meta_model, task_train_trend_model]
[task_train_meta_model, task_train_trend_model] >> task_validate_models
task_validate_models >> task_deploy_models >> task_notify
