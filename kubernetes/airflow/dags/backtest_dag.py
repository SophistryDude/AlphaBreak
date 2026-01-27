"""
Airflow DAG for Monthly Backtesting

Runs monthly on the 1st at 4 AM to backtest the trading strategy.
"""

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago
from datetime import datetime, timedelta
import sys

sys.path.insert(0, '/app')

default_args = {
    'owner': 'trading-system',
    'depends_on_past': False,
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=10),
    'execution_timeout': timedelta(hours=4),
}

dag = DAG(
    'backtest_dag',
    default_args=default_args,
    description='Monthly backtesting of trading strategy',
    schedule_interval='0 4 1 * *',  # Monthly on 1st at 4 AM
    start_date=days_ago(1),
    catchup=False,
    tags=['backtest', 'strategy', 'monthly'],
)


def prepare_backtest_config(**context):
    """Prepare backtest configuration."""
    from datetime import datetime, timedelta

    # Backtest last 2 years
    end_date = datetime.now()
    start_date = end_date - timedelta(days=730)

    tickers = [
        'AAPL', 'GOOGL', 'MSFT', 'TSLA', 'AMZN', 'NVDA', 'META',
        'JPM', 'BAC', 'WMT', 'XOM', 'SPY', 'QQQ'
    ]

    config = {
        'start_date': start_date.strftime('%Y-%m-%d'),
        'end_date': end_date.strftime('%Y-%m-%d'),
        'tickers': tickers,
        'initial_capital': 100000,
        'position_size': 0.1,  # 10% per trade
        'stop_loss': 0.05,  # 5% stop loss
        'take_profit': 0.15,  # 15% take profit
    }

    context['ti'].xcom_push(key='backtest_config', value=config)
    print(f"Backtest config prepared: {len(tickers)} tickers from {config['start_date']} to {config['end_date']}")
    return config


def run_trend_break_backtest(**context):
    """Run trend break prediction backtest."""
    from trend_break_prediction import backtest_trend_break_strategy
    import pandas as pd

    ti = context['ti']
    config = ti.xcom_pull(key='backtest_config', task_ids='prepare_config')

    results = []
    for ticker in config['tickers']:
        try:
            print(f"Backtesting {ticker}...")
            result = backtest_trend_break_strategy(
                ticker=ticker,
                start_date=config['start_date'],
                end_date=config['end_date'],
                initial_capital=config['initial_capital']
            )

            if result is not None:
                results.append({
                    'ticker': ticker,
                    'total_return': result.get('total_return', 0),
                    'sharpe_ratio': result.get('sharpe_ratio', 0),
                    'max_drawdown': result.get('max_drawdown', 0),
                    'win_rate': result.get('win_rate', 0),
                    'total_trades': result.get('total_trades', 0),
                })
        except Exception as e:
            print(f"Error backtesting {ticker}: {e}")
            results.append({
                'ticker': ticker,
                'error': str(e)
            })

    # Save results
    results_df = pd.DataFrame(results)
    output_path = f"/app/logs/backtest_{config['end_date']}.csv"
    results_df.to_csv(output_path, index=False)

    context['ti'].xcom_push(key='results_path', value=output_path)
    context['ti'].xcom_push(key='results', value=results)

    return {'total_tickers': len(results)}


def run_options_backtest(**context):
    """Run options strategy backtest."""
    from options_analysis import backtest_options_strategy
    import pandas as pd

    ti = context['ti']
    config = ti.xcom_pull(key='backtest_config', task_ids='prepare_config')

    # Focus on liquid options
    liquid_tickers = ['AAPL', 'GOOGL', 'MSFT', 'TSLA', 'AMZN', 'SPY', 'QQQ']

    results = []
    for ticker in liquid_tickers:
        try:
            print(f"Backtesting options for {ticker}...")
            result = backtest_options_strategy(
                ticker=ticker,
                start_date=config['start_date'],
                end_date=config['end_date']
            )

            if result is not None:
                results.append({
                    'ticker': ticker,
                    'total_return': result.get('total_return', 0),
                    'best_trade': result.get('best_trade', 0),
                    'worst_trade': result.get('worst_trade', 0),
                    'avg_profit': result.get('avg_profit', 0),
                })
        except Exception as e:
            print(f"Error backtesting options for {ticker}: {e}")

    # Save results
    results_df = pd.DataFrame(results)
    output_path = f"/app/logs/options_backtest_{config['end_date']}.csv"
    results_df.to_csv(output_path, index=False)

    context['ti'].xcom_push(key='options_results_path', value=output_path)

    return {'total_tickers': len(results)}


def generate_backtest_report(**context):
    """Generate comprehensive backtest report."""
    import pandas as pd

    ti = context['ti']
    trend_results_path = ti.xcom_pull(key='results_path', task_ids='backtest_trend_breaks')
    options_results_path = ti.xcom_pull(key='options_results_path', task_ids='backtest_options')

    # Load results
    trend_df = pd.read_csv(trend_results_path)
    options_df = pd.read_csv(options_results_path)

    # Calculate aggregate statistics
    trend_stats = {
        'avg_return': trend_df['total_return'].mean(),
        'avg_sharpe': trend_df['sharpe_ratio'].mean(),
        'avg_win_rate': trend_df['win_rate'].mean(),
        'total_trades': trend_df['total_trades'].sum(),
    }

    options_stats = {
        'avg_return': options_df['total_return'].mean(),
        'best_performer': options_df.loc[options_df['total_return'].idxmax(), 'ticker'],
        'avg_profit': options_df['avg_profit'].mean(),
    }

    # Generate report
    report = f"""
    ===== MONTHLY BACKTEST REPORT =====
    Date: {datetime.now().strftime('%Y-%m-%d')}

    TREND BREAK STRATEGY:
    - Average Return: {trend_stats['avg_return']:.2%}
    - Average Sharpe Ratio: {trend_stats['avg_sharpe']:.2f}
    - Average Win Rate: {trend_stats['avg_win_rate']:.2%}
    - Total Trades: {trend_stats['total_trades']}

    OPTIONS STRATEGY:
    - Average Return: {options_stats['avg_return']:.2%}
    - Best Performer: {options_stats['best_performer']}
    - Average Profit per Trade: ${options_stats['avg_profit']:.2f}

    Full results saved to:
    - {trend_results_path}
    - {options_results_path}
    ===================================
    """

    print(report)

    # Save report
    report_path = f"/app/logs/backtest_report_{datetime.now().strftime('%Y-%m-%d')}.txt"
    with open(report_path, 'w') as f:
        f.write(report)

    return {'status': 'report_generated', 'path': report_path}


# Define tasks
prepare_config_task = PythonOperator(
    task_id='prepare_config',
    python_callable=prepare_backtest_config,
    provide_context=True,
    dag=dag,
)

backtest_trend_task = PythonOperator(
    task_id='backtest_trend_breaks',
    python_callable=run_trend_break_backtest,
    provide_context=True,
    dag=dag,
)

backtest_options_task = PythonOperator(
    task_id='backtest_options',
    python_callable=run_options_backtest,
    provide_context=True,
    dag=dag,
)

report_task = PythonOperator(
    task_id='generate_report',
    python_callable=generate_backtest_report,
    provide_context=True,
    dag=dag,
)

# Define task dependencies
prepare_config_task >> [backtest_trend_task, backtest_options_task] >> report_task
