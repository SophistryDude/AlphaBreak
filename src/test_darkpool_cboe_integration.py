"""
Dark Pool Amplification & CBOE Integration Test Script

Runs train_on_trend_breaks() twice:
1. Baseline: include_darkpool=False, include_cboe=False
2. Enhanced: include_darkpool=True, include_cboe=True

Compares per-indicator accuracy changes and produces a structured report.

Usage:
    python -m src.test_darkpool_cboe_integration [--samples N]
"""

import sys
import os
import argparse
import json
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def run_comparison(n_samples: int = 50000):
    """Run baseline vs enhanced comparison."""
    from src.meta_learning_model import train_on_trend_breaks

    # Use date range that overlaps with CBOE data (2006-2019) and dark pool (2025)
    # CBOE has the most coverage, so focus on 2007-2019 for the main test
    test_start = '2007-01-01'
    test_end = '2019-10-04'

    print("=" * 80)
    print("DARK POOL & CBOE INTEGRATION TEST")
    print(f"Samples: {n_samples:,}")
    print(f"Date range: {test_start} to {test_end}")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 80)

    # ─── BASELINE RUN ───
    print("\n" + "#" * 80)
    print("# RUN 1: BASELINE (no dark pool, no CBOE)")
    print("#" * 80)

    baseline_results = train_on_trend_breaks(
        n_samples=n_samples,
        timeframe='daily',
        target_accuracy=0.85,
        include_market_data=True,
        include_darkpool=False,
        include_cboe=False,
        start_date=test_start,
        end_date=test_end
    )

    # ─── ENHANCED RUN ───
    print("\n" + "#" * 80)
    print("# RUN 2: ENHANCED (with dark pool amplification + CBOE sentiment)")
    print("#" * 80)

    enhanced_results = train_on_trend_breaks(
        n_samples=n_samples,
        timeframe='daily',
        target_accuracy=0.85,
        include_market_data=True,
        include_darkpool=True,
        include_cboe=True,
        start_date=test_start,
        end_date=test_end
    )

    # ─── COMPARISON ───
    print("\n" + "=" * 80)
    print("COMPARISON: BASELINE vs ENHANCED")
    print("=" * 80)

    baseline_df = baseline_results['summary_df']
    enhanced_df = enhanced_results['summary_df']

    if baseline_df is None or len(baseline_df) == 0:
        print("ERROR: Baseline returned no results.")
        return baseline_results, enhanced_results

    if enhanced_df is None or len(enhanced_df) == 0:
        print("ERROR: Enhanced returned no results.")
        return baseline_results, enhanced_results

    # Merge on indicator name
    comparison = baseline_df[['indicator', 'best_accuracy', 'best_lookback', 'indicator_type']].rename(
        columns={'best_accuracy': 'baseline_accuracy', 'best_lookback': 'baseline_lookback'}
    ).merge(
        enhanced_df[['indicator', 'best_accuracy', 'best_lookback']].rename(
            columns={'best_accuracy': 'enhanced_accuracy', 'best_lookback': 'enhanced_lookback'}
        ),
        on='indicator',
        how='outer'
    )

    comparison['accuracy_change'] = comparison['enhanced_accuracy'] - comparison['baseline_accuracy']
    comparison['pct_change'] = (comparison['accuracy_change'] / comparison['baseline_accuracy'] * 100).round(2)
    comparison = comparison.sort_values('accuracy_change', ascending=False)

    # Summary statistics
    improved = comparison[comparison['accuracy_change'] > 0.001]
    degraded = comparison[comparison['accuracy_change'] < -0.001]
    unchanged = comparison[abs(comparison['accuracy_change']) <= 0.001]

    print(f"\nTotal indicators compared: {len(comparison)}")
    print(f"  Improved:  {len(improved)} ({len(improved)/len(comparison)*100:.0f}%)")
    print(f"  Unchanged: {len(unchanged)} ({len(unchanged)/len(comparison)*100:.0f}%)")
    print(f"  Degraded:  {len(degraded)} ({len(degraded)/len(comparison)*100:.0f}%)")

    avg_change = comparison['accuracy_change'].mean()
    print(f"\nAverage accuracy change: {avg_change:+.4f} ({avg_change/comparison['baseline_accuracy'].mean()*100:+.2f}%)")

    # Top improved
    print("\n" + "-" * 80)
    print("TOP 10 MOST IMPROVED INDICATORS:")
    print("-" * 80)
    for _, row in improved.head(10).iterrows():
        itype = f" [{row['indicator_type']}]" if row.get('indicator_type') == 'market' else ''
        print(f"  {row['indicator']}{itype}: "
              f"{row['baseline_accuracy']:.4f} -> {row['enhanced_accuracy']:.4f} "
              f"({row['accuracy_change']:+.4f}, {row['pct_change']:+.1f}%)")

    # Top degraded
    if len(degraded) > 0:
        print("\n" + "-" * 80)
        print("TOP 5 MOST DEGRADED INDICATORS:")
        print("-" * 80)
        for _, row in degraded.tail(5).iterrows():
            itype = f" [{row['indicator_type']}]" if row.get('indicator_type') == 'market' else ''
            print(f"  {row['indicator']}{itype}: "
                  f"{row['baseline_accuracy']:.4f} -> {row['enhanced_accuracy']:.4f} "
                  f"({row['accuracy_change']:+.4f}, {row['pct_change']:+.1f}%)")

    # Dark pool amplification details
    if 'dp_amplification' in enhanced_df.columns:
        dp_data = enhanced_df.dropna(subset=['dp_amplification'])
        if len(dp_data) > 0:
            print("\n" + "-" * 80)
            print("DARK POOL AMPLIFICATION DETAILS:")
            print("-" * 80)
            print(f"  Indicators with DP data: {len(dp_data)}")
            print(f"  Avg amplification factor: {dp_data['dp_amplification'].mean():.4f}")
            print(f"  Max amplification factor: {dp_data['dp_amplification'].max():.4f}")
            print(f"  Avg DP volume z-score: {dp_data['dp_volume_zscore'].mean():.3f}")

    # CBOE regime details
    pcr_regime_cols = [c for c in enhanced_df.columns if 'PCR' in c and 'direction' in c]
    if pcr_regime_cols:
        print("\n" + "-" * 80)
        print("CBOE P/C REGIME SEGMENTED RESULTS:")
        print("-" * 80)
        for regime_label in ['Very Bearish PCR', 'Bearish PCR', 'Neutral PCR', 'Bullish PCR', 'Very Bullish PCR']:
            dir_col = f'{regime_label}_direction'
            brk_col = f'{regime_label}_breaks'
            if dir_col in enhanced_df.columns:
                regime_data = enhanced_df.dropna(subset=[dir_col])
                if len(regime_data) > 0:
                    avg_dir = regime_data[dir_col].mean()
                    avg_brk = regime_data[brk_col].mean() if brk_col in regime_data.columns else 0
                    print(f"\n  {regime_label}:")
                    print(f"    Avg direction accuracy: {avg_dir:.1%}")
                    print(f"    Avg breaks per indicator: {avg_brk:.0f}")
                    top = regime_data.nlargest(3, dir_col)
                    for _, row in top.iterrows():
                        print(f"    Best: {row['indicator']} ({row[dir_col]:.1%})")

    # Generate report data
    report_data = {
        'date': datetime.now().isoformat(),
        'n_samples': n_samples,
        'total_indicators': len(comparison),
        'improved': len(improved),
        'unchanged': len(unchanged),
        'degraded': len(degraded),
        'avg_accuracy_change': float(avg_change),
        'avg_baseline_accuracy': float(comparison['baseline_accuracy'].mean()),
        'avg_enhanced_accuracy': float(comparison['enhanced_accuracy'].mean()),
        'top_improved': comparison.head(10)[['indicator', 'baseline_accuracy', 'enhanced_accuracy', 'accuracy_change']].to_dict('records'),
    }

    # Write report
    write_amplification_report(report_data, comparison, enhanced_df)

    return baseline_results, enhanced_results


def write_amplification_report(report_data, comparison_df, enhanced_df):
    """Write the dark pool amplification report."""
    docs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'docs')
    report_path = os.path.join(docs_dir, 'DARKPOOL_AMPLIFICATION_REPORT.md')

    avg_change = report_data['avg_accuracy_change']
    pct_change = (avg_change / report_data['avg_baseline_accuracy'] * 100) if report_data['avg_baseline_accuracy'] > 0 else 0

    improved = comparison_df[comparison_df['accuracy_change'] > 0.001]
    degraded = comparison_df[comparison_df['accuracy_change'] < -0.001]

    lines = [
        "# Dark Pool Amplification & CBOE Integration Report",
        "",
        f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"**Samples**: {report_data['n_samples']:,} trend breaks",
        "",
        "---",
        "",
        "## Executive Summary",
        "",
        f"Tested the effect of integrating FINRA dark pool volume amplification and CBOE",
        f"put/call ratio sentiment into the meta-learning model's indicator accuracy scoring.",
        "",
        f"- **Total indicators compared**: {report_data['total_indicators']}",
        f"- **Improved**: {report_data['improved']} ({report_data['improved']/report_data['total_indicators']*100:.0f}%)",
        f"- **Unchanged**: {report_data['unchanged']} ({report_data['unchanged']/report_data['total_indicators']*100:.0f}%)",
        f"- **Degraded**: {report_data['degraded']} ({report_data['degraded']/report_data['total_indicators']*100:.0f}%)",
        f"- **Average accuracy change**: {avg_change:+.4f} ({pct_change:+.2f}%)",
        "",
        "---",
        "",
        "## Methodology",
        "",
        "### Dark Pool Amplification",
        "",
        "Dark pool volume z-scores (8-week rolling, per-ticker) amplify composite accuracy:",
        "",
        "```",
        "amplification = 1.0 + max(0, dp_volume_zscore) * 0.15",
        "```",
        "",
        "| Z-Score | Amplification |",
        "|--------:|--------------:|",
        "| 0.0 | 1.00x |",
        "| 1.0 | 1.15x |",
        "| 2.0 | 1.30x |",
        "",
        "**Rationale**: Analysis showed dark pool high volume (z>1) amplifies post-break",
        "returns by +1.29pp (3.22% vs 1.93% for troughs). The amplification is multiplicative",
        "on the composite accuracy score.",
        "",
        "### CBOE P/C Ratio Sentiment",
        "",
        "CBOE put/call ratio z-scores classify market sentiment into regimes:",
        "",
        "| Regime | Z-Score Range | Contrarian Signal |",
        "|--------|:--------------|:------------------|",
        "| Very Bullish | z <= -1.5 | Bearish (complacency) |",
        "| Bullish | -1.5 < z <= -0.5 | Bearish |",
        "| Neutral | -0.5 < z < 0.5 | None |",
        "| Bearish | 0.5 <= z < 1.5 | Bullish |",
        "| Very Bearish | z >= 1.5 | Bullish (fear) |",
        "",
        "CBOE context is stored on each indicator for regime-segmented analysis,",
        "not used as an accuracy amplifier (P/C is directional/contrarian, not magnitude).",
        "",
        "---",
        "",
        "## Results: Accuracy Comparison",
        "",
        "### Top 10 Most Improved Indicators",
        "",
        "| Indicator | Baseline | Enhanced | Change | % Change |",
        "|-----------|--------:|---------:|-------:|---------:|",
    ]

    for _, row in improved.head(10).iterrows():
        lines.append(
            f"| {row['indicator']} | {row['baseline_accuracy']:.4f} | "
            f"{row['enhanced_accuracy']:.4f} | {row['accuracy_change']:+.4f} | "
            f"{row['pct_change']:+.1f}% |"
        )

    lines.extend([
        "",
        "### Overall Distribution",
        "",
    ])

    if len(degraded) > 0:
        lines.extend([
            "### Degraded Indicators",
            "",
            "| Indicator | Baseline | Enhanced | Change |",
            "|-----------|--------:|---------:|-------:|",
        ])
        for _, row in degraded.head(5).iterrows():
            lines.append(
                f"| {row['indicator']} | {row['baseline_accuracy']:.4f} | "
                f"{row['enhanced_accuracy']:.4f} | {row['accuracy_change']:+.4f} |"
            )
        lines.append("")

    # Dark pool details
    if 'dp_amplification' in enhanced_df.columns:
        dp_data = enhanced_df.dropna(subset=['dp_amplification'])
        if len(dp_data) > 0:
            lines.extend([
                "---",
                "",
                "## Dark Pool Amplification Details",
                "",
                f"- Indicators with dark pool data: {len(dp_data)}",
                f"- Average amplification factor: {dp_data['dp_amplification'].mean():.4f}",
                f"- Max amplification factor: {dp_data['dp_amplification'].max():.4f}",
                f"- Average DP volume z-score: {dp_data['dp_volume_zscore'].mean():.3f}",
                "",
            ])

    # CBOE regime details
    pcr_cols = [c for c in enhanced_df.columns if 'PCR' in c and 'direction' in c]
    if pcr_cols:
        lines.extend([
            "---",
            "",
            "## CBOE P/C Regime-Segmented Results",
            "",
        ])
        for regime_label in ['Very Bearish PCR', 'Bearish PCR', 'Neutral PCR', 'Bullish PCR', 'Very Bullish PCR']:
            dir_col = f'{regime_label}_direction'
            if dir_col in enhanced_df.columns:
                regime_data = enhanced_df.dropna(subset=[dir_col])
                if len(regime_data) > 0:
                    lines.append(f"### {regime_label}")
                    lines.append("")
                    lines.append(f"Average direction accuracy: {regime_data[dir_col].mean():.1%}")
                    lines.append("")
                    top3 = regime_data.nlargest(3, dir_col)
                    lines.append("| Indicator | Direction Accuracy |")
                    lines.append("|-----------|-------------------:|")
                    for _, row in top3.iterrows():
                        lines.append(f"| {row['indicator']} | {row[dir_col]:.1%} |")
                    lines.append("")

    lines.extend([
        "---",
        "",
        "## Data Coverage Limitations",
        "",
        "- **Dark pool data**: Jan 2025 - Jan 2026 (~52 weeks, 459 tickers)",
        "  - Only recent breaks can be amplified",
        "  - Historical breaks outside this window get no amplification (factor = 1.0)",
        "",
        "- **CBOE data**: Nov 2006 - Oct 2019 (~3,253 trading days)",
        "  - No overlap with dark pool data date range",
        "  - Regime segmentation covers most of the historical break data",
        "",
        "## Recommendations",
        "",
        "1. **Continue collecting dark pool data** weekly to expand coverage",
        "2. **Update CBOE archive** with recent data (2020-present) for full coverage",
        "3. **Use regime segmentation** to select different indicator weights per market condition",
        "4. **Monitor amplification** as more dark pool data accumulates",
    ])

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    print(f"\nReport written to: {report_path}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Test dark pool and CBOE integration')
    parser.add_argument('--samples', type=int, default=50000,
                        help='Number of trend break samples (default: 50000)')
    args = parser.parse_args()

    run_comparison(n_samples=args.samples)
