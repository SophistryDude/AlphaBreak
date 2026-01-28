"""
Airflow DAG: Daily Trend Break Report
======================================
Runs at 9:00 AM EST (14:00 UTC) on weekdays.
Scans S&P 500 top 50 for trend break probability >= 80%.
Includes full indicators + options pricing.
"""

from airflow import DAG
from airflow.operators.python import PythonOperator, ShortCircuitOperator
from airflow.utils.dates import days_ago
from datetime import datetime, timedelta
import sys
import logging

sys.path.insert(0, '/app')

logger = logging.getLogger(__name__)

default_args = {
    'owner': 'trading-system',
    'depends_on_past': False,
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=10),
    'execution_timeout': timedelta(hours=2),
}

dag = DAG(
    'trend_break_daily_report',
    default_args=default_args,
    description='Daily trend break report at 9AM EST (weekdays)',
    schedule_interval='0 14 * * 1-5',  # 9 AM EST = 14:00 UTC, Mon-Fri
    start_date=days_ago(1),
    catchup=False,
    max_active_runs=1,
    tags=['reports', 'daily', 'trend-break'],
)

# Database connection
DB_CONFIG = {
    'host': 'postgres-timeseries-service',
    'port': 5432,
    'database': 'trading_data',
    'user': 'trading',
    'password': 'change_me',  # Use K8s secret in production
}

FREQUENCY = 'daily'


def check_market_day(**context):
    """Skip on weekends and US market holidays."""
    today = datetime.utcnow().date()
    weekday = today.weekday()
    if weekday >= 5:  # Saturday or Sunday
        logger.info(f"Skipping: {today} is a weekend day")
        return False
    # Basic holiday check (can expand with trading_calendars package)
    return True


def generate_report(**context):
    """Generate daily trend break report."""
    from app.services.report_service import generate_report

    logger.info("Starting daily trend break report generation")
    report = generate_report(
        frequency=FREQUENCY,
        include_options=True,
    )

    context['ti'].xcom_push(key='report_id', value=report['report_id'])
    context['ti'].xcom_push(key='securities_count', value=report['securities_count'])
    context['ti'].xcom_push(key='alerts_count', value=report['alerts_count'])
    context['ti'].xcom_push(key='report', value=report)

    logger.info(
        f"Daily report generated: {report['securities_count']} securities, "
        f"{report['alerts_count']} alerts (report_id={report['report_id'][:8]})"
    )
    return report


def store_report(**context):
    """Store the report in the database."""
    import psycopg2
    from app.services.report_service import store_report

    report = context['ti'].xcom_pull(key='report', task_ids='generate_report')
    if not report or not report.get('securities'):
        logger.info("No securities to store")
        return

    # Create a simple DB manager wrapper for store_report
    class SimpleDBManager:
        def __init__(self, config):
            self.config = config

        def get_cursor(self, commit=False):
            return _DBCursorContext(self.config, commit)

        def execute_query(self, query, params=None):
            conn = psycopg2.connect(**self.config)
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            cursor.close()
            conn.close()
            return rows

    class _DBCursorContext:
        def __init__(self, config, commit):
            self.config = config
            self.commit = commit
            self.conn = None
            self.cursor = None

        def __enter__(self):
            self.conn = psycopg2.connect(**self.config)
            self.cursor = self.conn.cursor()
            return self.cursor

        def __exit__(self, exc_type, exc_val, exc_tb):
            if exc_type is None and self.commit:
                self.conn.commit()
            elif exc_type:
                self.conn.rollback()
            self.cursor.close()
            self.conn.close()

    db = SimpleDBManager(DB_CONFIG)
    success = store_report(report, db)
    logger.info(f"Report storage {'succeeded' if success else 'failed'}")


def log_summary(**context):
    """Log a summary of the report run."""
    ti = context['ti']
    report_id = ti.xcom_pull(key='report_id', task_ids='generate_report')
    securities = ti.xcom_pull(key='securities_count', task_ids='generate_report')
    alerts = ti.xcom_pull(key='alerts_count', task_ids='generate_report')

    logger.info(
        f"=== DAILY REPORT SUMMARY ===\n"
        f"Report ID: {report_id}\n"
        f"Securities flagged: {securities}\n"
        f"Recent alerts: {alerts}\n"
        f"Frequency: {FREQUENCY}\n"
        f"Generated at: {datetime.utcnow().isoformat()}\n"
        f"============================"
    )


# Define tasks
check_market = ShortCircuitOperator(
    task_id='check_market_day',
    python_callable=check_market_day,
    provide_context=True,
    dag=dag,
)

generate = PythonOperator(
    task_id='generate_report',
    python_callable=generate_report,
    provide_context=True,
    dag=dag,
)

store = PythonOperator(
    task_id='store_report',
    python_callable=store_report,
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
check_market >> generate >> store >> summary
