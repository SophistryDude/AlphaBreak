"""
Airflow DAG: 10-Minute Trend Break Report
==========================================
Runs every 10 minutes during market hours.
Scans S&P 500 top 20 for trend break probability >= 80%.
Skips options pricing (too slow at this frequency).
Uses CCI + TLEV indicators only.
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
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=2),
    'execution_timeout': timedelta(minutes=8),  # Tight budget for 10-min cadence
}

dag = DAG(
    'trend_break_10min_report',
    default_args=default_args,
    description='10-minute trend break report during market hours',
    schedule_interval='*/10 * * * *',  # Every 10 minutes
    start_date=days_ago(1),
    catchup=False,
    max_active_runs=1,
    tags=['reports', '10min', 'trend-break'],
)

DB_CONFIG = {
    'host': 'postgres-timeseries-service',
    'port': 5432,
    'database': 'trading_data',
    'user': 'trading',
    'password': 'change_me',
}

FREQUENCY = '10min'


def check_market_hours(**context):
    """Only run during US market hours: 9:30 AM - 4:00 PM ET, weekdays."""
    now_utc = datetime.utcnow()
    et_hour = (now_utc.hour - 5) % 24
    weekday = now_utc.weekday()

    if weekday >= 5:
        logger.info(f"Skipping: weekend")
        return False

    if et_hour < 9 or et_hour >= 16:
        logger.info(f"Skipping: outside market hours (ET hour={et_hour})")
        return False

    if et_hour == 9 and now_utc.minute < 30:
        logger.info("Skipping: before 9:30 AM ET")
        return False

    return True


def generate_report(**context):
    """Generate 10-minute trend break report (no options, limited indicators)."""
    from app.services.report_service import generate_report

    logger.info("Starting 10-min trend break report generation")
    report = generate_report(
        frequency=FREQUENCY,
        include_options=False,  # Too slow at 10-min cadence
    )

    context['ti'].xcom_push(key='report_id', value=report['report_id'])
    context['ti'].xcom_push(key='securities_count', value=report['securities_count'])
    context['ti'].xcom_push(key='alerts_count', value=report['alerts_count'])
    context['ti'].xcom_push(key='report', value=report)

    logger.info(
        f"10-min report: {report['securities_count']} securities, "
        f"{report['alerts_count']} alerts"
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
    """Log summary."""
    ti = context['ti']
    securities = ti.xcom_pull(key='securities_count', task_ids='generate_report')
    alerts = ti.xcom_pull(key='alerts_count', task_ids='generate_report')
    logger.info(f"10-MIN REPORT: {securities} securities, {alerts} alerts")


# Tasks
check_market = ShortCircuitOperator(
    task_id='check_market_hours',
    python_callable=check_market_hours,
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

check_market >> generate >> store >> summary
