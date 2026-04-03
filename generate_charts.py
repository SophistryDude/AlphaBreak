"""
Generate presentation charts for AlphaBreak portfolio findings.
Outputs PNG files suitable for PowerPoint.
"""

import os
import sys
import subprocess
import psycopg2
from psycopg2.extras import RealDictCursor
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches
import matplotlib.ticker as mticker
from datetime import datetime
import numpy as np

# DB connection
def _get_pod_ip():
    try:
        result = subprocess.run(
            ['sudo', 'k0s', 'kubectl', 'get', 'pod', '-n', 'trading-system',
             '-l', 'app=timeseries-postgres', '-o', 'jsonpath={.items[0].status.podIP}'],
            capture_output=True, text=True, timeout=10
        )
        if result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass
    return '127.0.0.1'

DB_CONFIG = {
    'host': _get_pod_ip(),
    'port': 5432,
    'database': 'trading_data',
    'user': 'trading',
    'password': 'trading_password',
}

OUT_DIR = '/tmp/charts'
os.makedirs(OUT_DIR, exist_ok=True)

# Style
DARK_BG = '#1a1a2e'
CARD_BG = '#16213e'
TEXT_COLOR = '#e0e0e0'
ACCENT_GREEN = '#00d4aa'
ACCENT_BLUE = '#4fc3f7'
ACCENT_RED = '#ff6b6b'
ACCENT_YELLOW = '#ffd93d'
ACCENT_PURPLE = '#bb86fc'
GRID_COLOR = '#2a2a4a'


def setup_dark_style():
    plt.rcParams.update({
        'figure.facecolor': DARK_BG,
        'axes.facecolor': CARD_BG,
        'axes.edgecolor': GRID_COLOR,
        'axes.labelcolor': TEXT_COLOR,
        'text.color': TEXT_COLOR,
        'xtick.color': TEXT_COLOR,
        'ytick.color': TEXT_COLOR,
        'grid.color': GRID_COLOR,
        'grid.alpha': 0.3,
        'font.family': 'sans-serif',
        'font.size': 12,
    })


def chart1_40yr_growth():
    """Chart 1: Strategy vs NASDAQ vs TQQQ - 40 Year Growth (log scale)"""
    conn = psycopg2.connect(**DB_CONFIG)
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT backtest_date, strategy_value, nasdaq_value, tqqq_value
            FROM backtest_comparison
            ORDER BY backtest_date
        """)
        rows = cur.fetchall()
    conn.close()

    dates = [r['backtest_date'] for r in rows]
    strategy = [float(r['strategy_value']) for r in rows]
    nasdaq = [float(r['nasdaq_value']) for r in rows]
    tqqq = [float(r['tqqq_value']) for r in rows]

    fig, ax = plt.subplots(figsize=(16, 9))
    ax.semilogy(dates, strategy, color=ACCENT_GREEN, linewidth=2.5, label='AlphaBreak Strategy')
    ax.semilogy(dates, nasdaq, color=ACCENT_BLUE, linewidth=2, label='NASDAQ Buy & Hold')
    ax.semilogy(dates, tqqq, color=ACCENT_PURPLE, linewidth=2, alpha=0.8, label='TQQQ (3x Leveraged)')
    ax.axhline(y=100000, color=TEXT_COLOR, linewidth=0.5, linestyle='--', alpha=0.3)

    ax.set_title('Portfolio Growth: 1985 - 2026 (Log Scale)', fontsize=22, fontweight='bold', pad=20)
    ax.set_ylabel('Portfolio Value ($)', fontsize=14)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, p: f'${x:,.0f}' if x < 1e6 else f'${x/1e6:,.0f}M'))
    ax.legend(fontsize=14, loc='upper left', facecolor=CARD_BG, edgecolor=GRID_COLOR)
    ax.grid(True, alpha=0.2)

    # Annotations
    ax.annotate(f'${strategy[-1]/1e6:,.0f}M', xy=(dates[-1], strategy[-1]),
                fontsize=14, fontweight='bold', color=ACCENT_GREEN,
                xytext=(-80, 10), textcoords='offset points')
    ax.annotate(f'${nasdaq[-1]/1e6:,.1f}M', xy=(dates[-1], nasdaq[-1]),
                fontsize=12, color=ACCENT_BLUE,
                xytext=(-80, -20), textcoords='offset points')
    ax.annotate(f'${tqqq[-1]/1e6:,.0f}M', xy=(dates[-1], tqqq[-1]),
                fontsize=12, color=ACCENT_PURPLE,
                xytext=(-80, 10), textcoords='offset points')

    plt.tight_layout()
    path = os.path.join(OUT_DIR, '01_40yr_growth_log.png')
    plt.savefig(path, dpi=200, bbox_inches='tight')
    plt.close()
    print(f"Saved: {path}")


def chart2_yearly_returns():
    """Chart 2: Year-by-year comparison bar chart"""
    conn = psycopg2.connect(**DB_CONFIG)
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            WITH yearly AS (
                SELECT EXTRACT(year FROM backtest_date)::int as year,
                       FIRST_VALUE(strategy_value) OVER (PARTITION BY EXTRACT(year FROM backtest_date) ORDER BY backtest_date) as strat_start,
                       LAST_VALUE(strategy_value) OVER (PARTITION BY EXTRACT(year FROM backtest_date) ORDER BY backtest_date ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) as strat_end,
                       FIRST_VALUE(nasdaq_value) OVER (PARTITION BY EXTRACT(year FROM backtest_date) ORDER BY backtest_date) as nas_start,
                       LAST_VALUE(nasdaq_value) OVER (PARTITION BY EXTRACT(year FROM backtest_date) ORDER BY backtest_date ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) as nas_end
                FROM backtest_comparison
            )
            SELECT DISTINCT year,
                   (strat_end - strat_start) / strat_start as strat_return,
                   (nas_end - nas_start) / nas_start as nas_return
            FROM yearly
            WHERE year >= 1986
            ORDER BY year
        """)
        rows = cur.fetchall()
    conn.close()

    years = [r['year'] for r in rows]
    strat_ret = [float(r['strat_return']) * 100 for r in rows]
    nas_ret = [float(r['nas_return']) * 100 for r in rows]

    fig, ax = plt.subplots(figsize=(18, 8))
    x = np.arange(len(years))
    w = 0.35
    bars1 = ax.bar(x - w/2, strat_ret, w, color=ACCENT_GREEN, alpha=0.85, label='AlphaBreak')
    bars2 = ax.bar(x + w/2, nas_ret, w, color=ACCENT_BLUE, alpha=0.85, label='NASDAQ')
    ax.axhline(y=0, color=TEXT_COLOR, linewidth=0.8, alpha=0.5)

    ax.set_title('Annual Returns: AlphaBreak vs NASDAQ', fontsize=20, fontweight='bold', pad=20)
    ax.set_ylabel('Annual Return (%)', fontsize=14)
    ax.set_xticks(x[::2])
    ax.set_xticklabels([str(y) for y in years[::2]], rotation=45, ha='right', fontsize=10)
    ax.legend(fontsize=13, facecolor=CARD_BG, edgecolor=GRID_COLOR)
    ax.grid(True, axis='y', alpha=0.2)

    plt.tight_layout()
    path = os.path.join(OUT_DIR, '02_annual_returns.png')
    plt.savefig(path, dpi=200, bbox_inches='tight')
    plt.close()
    print(f"Saved: {path}")


def chart3_signal_accuracy():
    """Chart 3: Trend Break Signal Accuracy (854K trades)"""
    categories = ['All Signals\n(854K trades)', 'Weak\n(<0.5 mag)', 'Medium\n(0.5-1.0)', 'Strong\n(>=1.0)', 'High Volume\n(>=1.5x)']
    win_rates = [98.5, 98.1, 99.7, 99.9, 99.5]
    avg_returns = [3.15, 2.89, 3.60, 4.36, 3.76]
    trade_counts = [853773, 648229, 105380, 100164, 199225]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 8))

    # Win Rate bars
    colors = [ACCENT_BLUE, '#66bb6a', ACCENT_YELLOW, ACCENT_GREEN, ACCENT_PURPLE]
    bars = ax1.bar(categories, win_rates, color=colors, alpha=0.9, edgecolor='white', linewidth=0.5)
    ax1.set_ylim(96, 100.5)
    ax1.set_title('Win Rate by Signal Strength', fontsize=16, fontweight='bold', pad=15)
    ax1.set_ylabel('Win Rate (%)', fontsize=13)
    for bar, val in zip(bars, win_rates):
        ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1,
                f'{val:.1f}%', ha='center', fontsize=12, fontweight='bold', color=TEXT_COLOR)

    # Avg Return bars
    bars2 = ax2.bar(categories, avg_returns, color=colors, alpha=0.9, edgecolor='white', linewidth=0.5)
    ax2.set_title('Avg Return per Trade', fontsize=16, fontweight='bold', pad=15)
    ax2.set_ylabel('Average Return (%)', fontsize=13)
    for bar, val in zip(bars2, avg_returns):
        ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.05,
                f'+{val:.2f}%', ha='center', fontsize=12, fontweight='bold', color=TEXT_COLOR)

    # Add trade counts as subtitle
    for ax in [ax1, ax2]:
        ax.grid(True, axis='y', alpha=0.2)

    fig.suptitle('Trend Break Signal Analysis: 854,773 Historical Trades (1985-2026)',
                 fontsize=18, fontweight='bold', y=1.02, color=ACCENT_GREEN)
    plt.tight_layout()
    path = os.path.join(OUT_DIR, '03_signal_accuracy.png')
    plt.savefig(path, dpi=200, bbox_inches='tight')
    plt.close()
    print(f"Saved: {path}")


def chart4_old_vs_new():
    """Chart 4: Old Rules vs New Rules (Feb-Apr 2026)"""
    labels = ['Starting\nBalance', 'LT Realized\nP&L', 'Swing\nRealized P&L', 'Ending\nValue']
    old_values = [100000, -3487, 0, 96243]
    new_values = [100000, -687, 13996, 110281]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 8))

    # Bar comparison
    x = np.arange(len(labels))
    w = 0.35
    ax1.bar(x - w/2, old_values, w, color=ACCENT_RED, alpha=0.85, label='Old Rules (Stock Only)')
    ax1.bar(x + w/2, new_values, w, color=ACCENT_GREEN, alpha=0.85, label='New Rules (Stock + Options)')

    ax1.set_title('Portfolio Comparison: Feb 9 - Apr 2, 2026', fontsize=16, fontweight='bold', pad=15)
    ax1.set_ylabel('Value ($)', fontsize=13)
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, fontsize=11)
    ax1.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, p: f'${x:,.0f}'))
    ax1.legend(fontsize=12, facecolor=CARD_BG, edgecolor=GRID_COLOR)
    ax1.grid(True, axis='y', alpha=0.2)

    # Summary metrics
    ax2.axis('off')
    metrics = [
        ('', 'OLD RULES', 'NEW RULES'),
        ('Total Return', '-3.76%', '+10.28%'),
        ('LT Strategy', '7% stop-loss', '25% trim (multi-TF)'),
        ('Swing Instrument', 'Stock', 'ATM Options'),
        ('Swing Win Rate', '0/6 (0%)', '4/8 (50%)'),
        ('Cash Rule', '20% min floor', '20% float ceiling'),
        ('Allocation', '65/35', '50/30/20'),
        ('Difference', '', '+$14,038'),
    ]

    table = ax2.table(cellText=metrics, loc='center', cellLoc='center',
                      colWidths=[0.35, 0.3, 0.3])
    table.auto_set_font_size(False)
    table.set_fontsize(12)
    table.scale(1, 2)

    for (row, col), cell in table.get_celld().items():
        cell.set_edgecolor(GRID_COLOR)
        if row == 0:
            cell.set_facecolor(ACCENT_BLUE)
            cell.set_text_props(fontweight='bold', color='white')
        elif row == len(metrics) - 1:
            cell.set_facecolor(ACCENT_GREEN)
            cell.set_text_props(fontweight='bold', color='black')
        else:
            cell.set_facecolor(CARD_BG)
            cell.set_text_props(color=TEXT_COLOR)
            if col == 2 and row > 0:
                cell.set_text_props(color=ACCENT_GREEN, fontweight='bold')

    ax2.set_title('Key Metrics', fontsize=16, fontweight='bold', pad=15)

    plt.tight_layout()
    path = os.path.join(OUT_DIR, '04_old_vs_new_rules.png')
    plt.savefig(path, dpi=200, bbox_inches='tight')
    plt.close()
    print(f"Saved: {path}")


def chart5_allocation():
    """Chart 5: Portfolio Allocation Strategy"""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 7))

    # Old allocation
    old_sizes = [65, 35]
    old_labels = ['Long-Term Stock\n65%', 'Swing Stock\n35%']
    old_colors = [ACCENT_BLUE, ACCENT_YELLOW]
    ax1.pie(old_sizes, labels=old_labels, colors=old_colors, autopct='', startangle=90,
            textprops={'color': TEXT_COLOR, 'fontsize': 14, 'fontweight': 'bold'},
            wedgeprops={'edgecolor': DARK_BG, 'linewidth': 2})
    ax1.set_title('Old Allocation', fontsize=18, fontweight='bold', pad=20)
    ax1.text(0, -1.3, '20% cash minimum (floor)', ha='center', fontsize=12,
             color=ACCENT_RED, style='italic')

    # New allocation
    new_sizes = [50, 30, 20]
    new_labels = ['Long-Term Stock\n50%', 'Swing Options\n30%', 'Cash Float\n20%']
    new_colors = [ACCENT_BLUE, ACCENT_GREEN, ACCENT_YELLOW]
    ax2.pie(new_sizes, labels=new_labels, colors=new_colors, autopct='', startangle=90,
            textprops={'color': TEXT_COLOR, 'fontsize': 14, 'fontweight': 'bold'},
            wedgeprops={'edgecolor': DARK_BG, 'linewidth': 2})
    ax2.set_title('New Allocation', fontsize=18, fontweight='bold', pad=20)
    ax2.text(0, -1.3, '$10K max per options trade, 5 concurrent max', ha='center', fontsize=12,
             color=ACCENT_GREEN, style='italic')

    fig.suptitle('Portfolio Allocation: Before & After', fontsize=22, fontweight='bold', y=1.02)
    plt.tight_layout()
    path = os.path.join(OUT_DIR, '05_allocation.png')
    plt.savefig(path, dpi=200, bbox_inches='tight')
    plt.close()
    print(f"Saved: {path}")


def chart6_options_strategy():
    """Chart 6: Options Exit Strategy"""
    fig, ax = plt.subplots(figsize=(14, 9))
    ax.axis('off')
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)

    ax.text(5, 9.5, 'Smart Options Exit Strategy', ha='center', fontsize=24,
            fontweight='bold', color=ACCENT_GREEN)

    # Entry
    bbox_style = dict(boxstyle='round,pad=0.5', facecolor=ACCENT_BLUE, alpha=0.3, edgecolor=ACCENT_BLUE, linewidth=2)
    ax.text(5, 8.5, 'ENTRY: Buy ATM Call on Bullish Trend Break\n30 DTE | $10K max | 5 concurrent positions',
            ha='center', fontsize=13, fontweight='bold', bbox=bbox_style)

    ax.annotate('', xy=(5, 7.3), xytext=(5, 7.8), arrowprops=dict(arrowstyle='->', color=TEXT_COLOR, lw=2))

    # Decision
    bbox_q = dict(boxstyle='round,pad=0.4', facecolor=CARD_BG, edgecolor=ACCENT_YELLOW, linewidth=2)
    ax.text(5, 7.0, 'Monitor Position', ha='center', fontsize=14, fontweight='bold', bbox=bbox_q)

    # YES - profit
    ax.annotate('PROFITABLE', xy=(2.5, 5.8), xytext=(3.5, 6.5),
                arrowprops=dict(arrowstyle='->', color=ACCENT_GREEN, lw=2),
                fontsize=12, fontweight='bold', color=ACCENT_GREEN, ha='center')

    bbox_win = dict(boxstyle='round,pad=0.5', facecolor=ACCENT_GREEN, alpha=0.15, edgecolor=ACCENT_GREEN, linewidth=2)
    ax.text(2.5, 5.2, 'TAKE PROFIT\n\nVolume declines to 70% of entry\nOR +100% gain auto-exit\n\nAvg gain: +60% on premium',
            ha='center', fontsize=12, fontweight='bold', bbox=bbox_win, color=ACCENT_GREEN)

    # NO - losing
    ax.annotate('LOSING', xy=(7.5, 5.8), xytext=(6.5, 6.5),
                arrowprops=dict(arrowstyle='->', color=ACCENT_RED, lw=2),
                fontsize=12, fontweight='bold', color=ACCENT_RED, ha='center')

    bbox_loss = dict(boxstyle='round,pad=0.5', facecolor=ACCENT_RED, alpha=0.15, edgecolor=ACCENT_RED, linewidth=2)
    ax.text(7.5, 5.2, 'REVERSAL EXIT\n\nTrend direction flips (bull->bear)\nOR hard stop: -50% of premium\n\nGoal: contain losses to 50%',
            ha='center', fontsize=12, fontweight='bold', bbox=bbox_loss, color=ACCENT_RED)

    # Goal
    bbox_goal = dict(boxstyle='round,pad=0.5', facecolor=ACCENT_PURPLE, alpha=0.2, edgecolor=ACCENT_PURPLE, linewidth=2)
    ax.text(5, 2.8, 'GOAL: Leave the top when right, accept 50% loss when wrong\n\n'
            'Empirical: 99.8% win rate on strong signals | +60% avg option gain | 3-day avg hold\n'
            '854,773 historical trades analyzed across 40 years',
            ha='center', fontsize=13, fontweight='bold', bbox=bbox_goal, color=ACCENT_PURPLE)

    plt.tight_layout()
    path = os.path.join(OUT_DIR, '06_options_strategy.png')
    plt.savefig(path, dpi=200, bbox_inches='tight')
    plt.close()
    print(f"Saved: {path}")


def chart7_milestones():
    """Chart 7: Key milestones table"""
    fig, ax = plt.subplots(figsize=(14, 8))
    ax.axis('off')

    data = [
        ['Year', 'AlphaBreak', 'NASDAQ', 'TQQQ', 'Alpha vs NASDAQ'],
        ['1985', '$100K', '$100K', '$100K', '—'],
        ['1990', '$2.4M', '$187K', '$481K', '12.8x'],
        ['1995', '$8.0M', '$302K', '$1.5M', '26.5x'],
        ['2000', '$23.6M', '$1.7M', '$135M', '14.0x'],
        ['2005', '$43.0M', '$875K', '$3.0M', '49.1x'],
        ['2010', '$67.2M', '$939K', '$1.4M', '71.5x'],
        ['2015', '$99.5M', '$1.9M', '$7.4M', '51.8x'],
        ['2020', '$137.5M', '$3.7M', '$35.5M', '37.2x'],
        ['2026', '$200.7M', '$8.9M', '$158.6M', '22.6x'],
    ]

    table = ax.table(cellText=data, loc='center', cellLoc='center',
                     colWidths=[0.12, 0.2, 0.2, 0.2, 0.2])
    table.auto_set_font_size(False)
    table.set_fontsize(14)
    table.scale(1, 2.2)

    for (row, col), cell in table.get_celld().items():
        cell.set_edgecolor(GRID_COLOR)
        if row == 0:
            cell.set_facecolor(ACCENT_BLUE)
            cell.set_text_props(fontweight='bold', color='white', fontsize=14)
        elif row == len(data) - 1:
            cell.set_facecolor(ACCENT_GREEN)
            cell.set_text_props(fontweight='bold', color='black', fontsize=14)
        else:
            cell.set_facecolor(CARD_BG)
            cell.set_text_props(color=TEXT_COLOR, fontsize=13)
            if col == 1:  # AlphaBreak column
                cell.set_text_props(color=ACCENT_GREEN, fontweight='bold', fontsize=13)
            if col == 4:  # Alpha column
                cell.set_text_props(color=ACCENT_YELLOW, fontweight='bold', fontsize=13)

    ax.set_title('$100K Starting Balance: Growth Milestones (1985-2026)',
                 fontsize=20, fontweight='bold', pad=30, color=ACCENT_GREEN)

    plt.tight_layout()
    path = os.path.join(OUT_DIR, '07_milestones.png')
    plt.savefig(path, dpi=200, bbox_inches='tight')
    plt.close()
    print(f"Saved: {path}")


if __name__ == '__main__':
    setup_dark_style()
    print("Generating presentation charts...")
    chart1_40yr_growth()
    chart2_yearly_returns()
    chart3_signal_accuracy()
    chart4_old_vs_new()
    chart5_allocation()
    chart6_options_strategy()
    chart7_milestones()
    print(f"\nAll charts saved to {OUT_DIR}/")
    print("Files:")
    for f in sorted(os.listdir(OUT_DIR)):
        if f.endswith('.png'):
            size = os.path.getsize(os.path.join(OUT_DIR, f))
            print(f"  {f} ({size//1024}KB)")
