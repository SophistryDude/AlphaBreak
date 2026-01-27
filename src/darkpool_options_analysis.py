"""
DARK POOL & OPTIONS VOLUME ANALYSIS vs TREND BREAKS

Tests whether dark pool activity and market-wide options sentiment
correlate with or predict trend breaks in individual stocks.

Dark Pool Analysis (FINRA ATS data, Jan 2025 - Jan 2026):
- Does elevated dark pool volume precede trend breaks?
- Does ATS concentration (fragmentation vs concentration) relate to break type?
- Do dark pool volume changes predict direction after break?

CBOE Options Analysis (market-wide put/call ratios, Nov 2006 - Oct 2019):
- Does the equity/index put-call ratio predict trend breaks?
- Do extreme P/C ratios correlate with peak vs trough breaks?
- Does options sentiment diverge from price action before reversals?

Also tests correlation with market indices (S&P 500, VIX, RUT, QQQ, etc.)
"""

import pandas as pd
import numpy as np
import psycopg2
from psycopg2.extras import RealDictCursor
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from scipy import stats

DB_CONFIG = {
    'host': os.environ.get('POSTGRES_HOST', 'localhost'),
    'port': int(os.environ.get('POSTGRES_PORT', 5433)),
    'database': os.environ.get('POSTGRES_DB', 'trading_data'),
    'user': os.environ.get('POSTGRES_USER', 'trading'),
    'password': os.environ.get('POSTGRES_PASSWORD', 'trading123')
}


def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)


# ════════════════════════════════════════════════════════════════════════════
# DATA LOADING
# ════════════════════════════════════════════════════════════════════════════

def load_trend_breaks(conn, start_date: str, end_date: str,
                      tickers: List[str] = None) -> pd.DataFrame:
    """Load daily trend breaks in a date range."""
    query = """
        SELECT ticker, timestamp, break_type, direction_before, direction_after,
               price_at_break, magnitude, price_change_pct, volume_ratio
        FROM trend_breaks
        WHERE timeframe = 'daily'
          AND timestamp >= %s AND timestamp <= %s
    """
    params = [start_date, end_date]
    if tickers:
        query += " AND ticker = ANY(%s)"
        params.append(tickers)
    query += " ORDER BY timestamp"

    return pd.read_sql(query, conn, params=params)


def load_darkpool_aggregates(conn) -> pd.DataFrame:
    """Load all dark pool ticker aggregates."""
    query = """
        SELECT ticker, week_start_date, total_darkpool_shares,
               total_darkpool_trades, num_ats_venues, top_ats_mpid,
               top_ats_shares, concentration_ratio
        FROM darkpool_ticker_aggregates
        ORDER BY ticker, week_start_date
    """
    return pd.read_sql(query, conn)


def load_cboe_market_stats(conn) -> pd.DataFrame:
    """Load CBOE market-wide options stats."""
    query = """
        SELECT trade_date, total_call_volume, total_put_volume, total_volume,
               equity_call_volume, equity_put_volume, equity_put_call_ratio,
               index_call_volume, index_put_volume, index_put_call_ratio
        FROM cboe_market_options_stats
        ORDER BY trade_date
    """
    return pd.read_sql(query, conn)


def load_stock_prices(conn, ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
    """Load daily stock prices for a ticker."""
    query = """
        SELECT timestamp, open, high, low, close, volume
        FROM stock_prices
        WHERE ticker = %s AND timestamp >= %s AND timestamp <= %s
        ORDER BY timestamp
    """
    df = pd.read_sql(query, conn, params=(ticker, start_date, end_date))
    if not df.empty:
        df['timestamp'] = pd.to_datetime(df['timestamp']).dt.tz_localize(None)
        df = df.set_index('timestamp')
    return df


def load_market_indices(conn, start_date: str, end_date: str) -> Dict[str, pd.DataFrame]:
    """Load market index data for all symbols."""
    query = """
        SELECT symbol, timestamp, open, high, low, close, volume
        FROM market_indices
        WHERE timestamp >= %s AND timestamp <= %s
        ORDER BY symbol, timestamp
    """
    df = pd.read_sql(query, conn, params=(start_date, end_date))
    if df.empty:
        return {}

    df['timestamp'] = pd.to_datetime(df['timestamp']).dt.tz_localize(None)

    result = {}
    for sym, group in df.groupby('symbol'):
        mdf = group.set_index('timestamp').sort_index()
        result[sym] = mdf
    return result


# ════════════════════════════════════════════════════════════════════════════
# BATCH CONTEXT LOADERS (for meta-learning model integration)
# ════════════════════════════════════════════════════════════════════════════

def batch_load_darkpool_context(
    conn=None,
    start_date: str = None,
    end_date: str = None,
    tickers: List[str] = None
) -> Optional[pd.DataFrame]:
    """Load dark pool ticker aggregates with computed z-scores and changes.

    Returns a DataFrame with per-ticker, per-week dark pool context:
        ticker, week_start_date, total_darkpool_shares, total_darkpool_trades,
        num_ats_venues, concentration_ratio, dp_volume_zscore, dp_shares_change

    Args:
        conn: Database connection (created internally if None)
        start_date: Optional start date filter (YYYY-MM-DD)
        end_date: Optional end date filter (YYYY-MM-DD)
        tickers: Optional list of tickers to filter

    Returns:
        DataFrame with dark pool context, or None if no data available
    """
    close_conn = False
    if conn is None:
        try:
            conn = get_db_connection()
            close_conn = True
        except Exception as e:
            print(f"  [darkpool context] DB connection failed: {e}")
            return None

    try:
        # Build query with optional filters
        query = """
            SELECT ticker, week_start_date, total_darkpool_shares,
                   total_darkpool_trades, num_ats_venues, concentration_ratio
            FROM darkpool_ticker_aggregates
            WHERE 1=1
        """
        params = []
        if start_date:
            query += " AND week_start_date >= %s"
            params.append(start_date)
        if end_date:
            query += " AND week_start_date <= %s"
            params.append(end_date)
        if tickers:
            query += " AND ticker = ANY(%s)"
            params.append(tickers)
        query += " ORDER BY ticker, week_start_date"

        dp = pd.read_sql(query, conn, params=params if params else None)

        if dp.empty:
            print("  [darkpool context] No dark pool data found")
            return None

        dp['week_start_date'] = pd.to_datetime(dp['week_start_date'])

        # Week-over-week change in shares
        dp = dp.sort_values(['ticker', 'week_start_date'])
        dp_prev = dp.groupby('ticker')['total_darkpool_shares'].shift(1)
        dp['dp_shares_change'] = np.where(
            dp_prev > 0,
            (dp['total_darkpool_shares'] - dp_prev) / dp_prev,
            np.nan
        )

        # Per-ticker rolling z-score (8-week window, min 3 periods)
        dp['dp_shares_mean'] = dp.groupby('ticker')['total_darkpool_shares'].transform(
            lambda x: x.rolling(window=8, min_periods=3).mean()
        )
        dp['dp_shares_std'] = dp.groupby('ticker')['total_darkpool_shares'].transform(
            lambda x: x.rolling(window=8, min_periods=3).std()
        )
        dp['dp_volume_zscore'] = np.where(
            dp['dp_shares_std'] > 0,
            (dp['total_darkpool_shares'] - dp['dp_shares_mean']) / dp['dp_shares_std'],
            0.0
        )

        # Drop intermediate columns
        dp = dp.drop(columns=['dp_shares_mean', 'dp_shares_std'])

        print(f"  [darkpool context] Loaded {len(dp):,} rows for {dp['ticker'].nunique()} tickers")
        return dp

    except Exception as e:
        print(f"  [darkpool context] Error loading: {e}")
        return None
    finally:
        if close_conn and conn:
            conn.close()


def batch_load_cboe_context(
    conn=None,
    start_date: str = None,
    end_date: str = None
) -> Optional[pd.DataFrame]:
    """Load CBOE market options stats with computed P/C ratios, z-scores, and regime.

    Returns a DataFrame indexed by trade_date with columns:
        total_pcr, pcr_5d, pcr_20d, pcr_zscore, pcr_change_5d,
        equity_pcr, index_pcr, pcr_spread, total_options_volume,
        volume_zscore, pcr_regime

    pcr_regime values:
        -2 = Very Bullish (P/C z-score <= -1.5)
        -1 = Bullish (-1.5 < z <= -0.5)
         0 = Neutral (-0.5 < z < 0.5)
        +1 = Bearish (0.5 <= z < 1.5)
        +2 = Very Bearish (z >= 1.5)

    Args:
        conn: Database connection (created internally if None)
        start_date: Optional start date filter (YYYY-MM-DD)
        end_date: Optional end date filter (YYYY-MM-DD)

    Returns:
        DataFrame with CBOE context indexed by trade_date, or None if no data
    """
    close_conn = False
    if conn is None:
        try:
            conn = get_db_connection()
            close_conn = True
        except Exception as e:
            print(f"  [cboe context] DB connection failed: {e}")
            return None

    try:
        query = """
            SELECT trade_date, total_call_volume, total_put_volume,
                   equity_call_volume, equity_put_volume, equity_put_call_ratio,
                   index_call_volume, index_put_volume, index_put_call_ratio
            FROM cboe_market_options_stats
            WHERE 1=1
        """
        params = []
        if start_date:
            query += " AND trade_date >= %s"
            params.append(start_date)
        if end_date:
            query += " AND trade_date <= %s"
            params.append(end_date)
        query += " ORDER BY trade_date"

        cboe = pd.read_sql(query, conn, params=params if params else None)

        if cboe.empty:
            print("  [cboe context] No CBOE data found")
            return None

        cboe['trade_date'] = pd.to_datetime(cboe['trade_date'])

        # Total put/call ratio
        cboe['total_pcr'] = np.where(
            cboe['total_call_volume'] > 0,
            cboe['total_put_volume'] / cboe['total_call_volume'],
            np.nan
        )

        # Rolling averages
        cboe['pcr_5d'] = cboe['total_pcr'].rolling(5, min_periods=3).mean()
        cboe['pcr_20d'] = cboe['total_pcr'].rolling(20, min_periods=10).mean()
        cboe['pcr_change_5d'] = cboe['total_pcr'] - cboe['pcr_5d'].shift(5)

        # Z-score of P/C ratio (60-day rolling)
        pcr_mean = cboe['total_pcr'].rolling(60, min_periods=30).mean()
        pcr_std = cboe['total_pcr'].rolling(60, min_periods=30).std()
        cboe['pcr_zscore'] = np.where(
            pcr_std > 0,
            (cboe['total_pcr'] - pcr_mean) / pcr_std,
            0.0
        )

        # Equity vs Index spread
        cboe['equity_pcr'] = cboe['equity_put_call_ratio']
        cboe['index_pcr'] = cboe['index_put_call_ratio']
        cboe['pcr_spread'] = cboe['equity_pcr'] - cboe['index_pcr']

        # Volume features
        cboe['total_options_volume'] = (
            cboe['total_call_volume'].fillna(0) + cboe['total_put_volume'].fillna(0)
        )
        vol_20d_avg = cboe['total_options_volume'].rolling(20, min_periods=10).mean()
        cboe['volume_zscore'] = np.where(
            vol_20d_avg > 0,
            (cboe['total_options_volume'] - vol_20d_avg) / vol_20d_avg,
            0.0
        )

        # P/C ratio regime classification
        cboe['pcr_regime'] = pd.cut(
            cboe['pcr_zscore'],
            bins=[-np.inf, -1.5, -0.5, 0.5, 1.5, np.inf],
            labels=[-2, -1, 0, 1, 2]
        ).astype(float).fillna(0).astype(int)

        # Select final columns and index by trade_date
        output_cols = [
            'trade_date', 'total_pcr', 'pcr_5d', 'pcr_20d', 'pcr_zscore',
            'pcr_change_5d', 'equity_pcr', 'index_pcr', 'pcr_spread',
            'total_options_volume', 'volume_zscore', 'pcr_regime'
        ]
        result = cboe[output_cols].set_index('trade_date')

        regime_counts = result['pcr_regime'].value_counts().sort_index()
        regime_labels = {-2: 'Very Bullish', -1: 'Bullish', 0: 'Neutral', 1: 'Bearish', 2: 'Very Bearish'}
        print(f"  [cboe context] Loaded {len(result):,} trading days "
              f"({result.index.min().date()} to {result.index.max().date()})")
        print(f"  [cboe context] Regime distribution: " +
              ", ".join(f"{regime_labels.get(int(r), r)}={c}" for r, c in regime_counts.items()))

        return result

    except Exception as e:
        print(f"  [cboe context] Error loading: {e}")
        return None
    finally:
        if close_conn and conn:
            conn.close()


# ════════════════════════════════════════════════════════════════════════════
# DARK POOL ANALYSIS
# ════════════════════════════════════════════════════════════════════════════

def analyze_darkpool_vs_breaks(conn) -> Dict[str, pd.DataFrame]:
    """
    Main dark pool analysis: correlate dark pool activity with trend breaks.

    Tests:
    1. Dark pool volume levels at trend breaks vs normal periods
    2. Volume changes (week-over-week) before breaks
    3. ATS concentration at breaks
    4. Dark pool volume vs break direction and magnitude
    5. Predictive power: does dark pool activity predict post-break returns?
    """
    sys.stdout.reconfigure(line_buffering=True)

    print("=" * 70)
    print("DARK POOL ANALYSIS vs TREND BREAKS")
    print("=" * 70)

    # Load data
    print("\nLoading data...")
    dp_agg = load_darkpool_aggregates(conn)
    if dp_agg.empty:
        print("ERROR: No dark pool data found.")
        return {}

    dp_min = dp_agg['week_start_date'].min()
    dp_max = dp_agg['week_start_date'].max()
    print(f"  Dark pool data: {dp_min} to {dp_max}, {len(dp_agg):,} records, "
          f"{dp_agg['ticker'].nunique()} tickers")

    breaks = load_trend_breaks(conn, str(dp_min), str(dp_max + timedelta(days=7)))
    print(f"  Trend breaks in range: {len(breaks):,}")

    if breaks.empty:
        print("ERROR: No trend breaks found in dark pool date range.")
        return {}

    # Normalize timestamps
    breaks['timestamp'] = pd.to_datetime(breaks['timestamp']).dt.tz_localize(None)
    dp_agg['week_start_date'] = pd.to_datetime(dp_agg['week_start_date'])

    # Calculate week-over-week dark pool changes per ticker
    dp_agg = dp_agg.sort_values(['ticker', 'week_start_date'])
    dp_agg['dp_shares_prev'] = dp_agg.groupby('ticker')['total_darkpool_shares'].shift(1)
    dp_agg['dp_shares_change'] = (
        (dp_agg['total_darkpool_shares'] - dp_agg['dp_shares_prev']) / dp_agg['dp_shares_prev']
    )
    dp_agg['dp_trades_prev'] = dp_agg.groupby('ticker')['total_darkpool_trades'].shift(1)
    dp_agg['dp_trades_change'] = (
        (dp_agg['total_darkpool_trades'] - dp_agg['dp_trades_prev']) / dp_agg['dp_trades_prev']
    )

    # Calculate per-ticker rolling stats for z-score normalization
    dp_agg['dp_shares_mean'] = dp_agg.groupby('ticker')['total_darkpool_shares'].transform(
        lambda x: x.rolling(window=8, min_periods=3).mean()
    )
    dp_agg['dp_shares_std'] = dp_agg.groupby('ticker')['total_darkpool_shares'].transform(
        lambda x: x.rolling(window=8, min_periods=3).std()
    )
    dp_agg['dp_volume_zscore'] = np.where(
        dp_agg['dp_shares_std'] > 0,
        (dp_agg['total_darkpool_shares'] - dp_agg['dp_shares_mean']) / dp_agg['dp_shares_std'],
        0
    )

    # Match breaks to dark pool data using merge_asof
    # For each break, find the most recent dark pool week
    breaks_sorted = breaks.sort_values('timestamp')
    analysis_rows = []

    tickers_with_dp = set(dp_agg['ticker'].unique())
    matched = 0

    for ticker in breaks_sorted['ticker'].unique():
        if ticker not in tickers_with_dp:
            continue

        ticker_breaks = breaks_sorted[breaks_sorted['ticker'] == ticker].copy()
        ticker_dp = dp_agg[dp_agg['ticker'] == ticker].sort_values('week_start_date')

        if ticker_dp.empty:
            continue

        merged = pd.merge_asof(
            ticker_breaks[['timestamp', 'break_type', 'direction_before', 'direction_after',
                           'price_at_break', 'magnitude', 'price_change_pct', 'volume_ratio']],
            ticker_dp[['week_start_date', 'total_darkpool_shares', 'total_darkpool_trades',
                        'num_ats_venues', 'concentration_ratio', 'dp_shares_change',
                        'dp_trades_change', 'dp_volume_zscore']],
            left_on='timestamp',
            right_on='week_start_date',
            direction='backward',
            tolerance=pd.Timedelta('14 days')
        )

        merged['ticker'] = ticker
        analysis_rows.append(merged)
        matched += 1

    if not analysis_rows:
        print("ERROR: No breaks could be matched with dark pool data.")
        return {}

    df = pd.concat(analysis_rows, ignore_index=True)
    df = df.dropna(subset=['total_darkpool_shares'])
    print(f"\n  Matched {len(df):,} breaks with dark pool data across {matched} tickers")

    results = {}

    # ── Analysis 1: Overall Dark Pool Stats at Breaks ──────────────────────
    print("\n" + "-" * 60)
    print("ANALYSIS 1: DARK POOL VOLUME AT TREND BREAKS")
    print("-" * 60)

    summary = pd.DataFrame({
        'metric': [
            'Total breaks with DP data',
            'Peak breaks',
            'Trough breaks',
            'Avg dark pool shares (at break)',
            'Avg dark pool trades (at break)',
            'Avg ATS venues',
            'Avg concentration ratio',
            'Avg DP volume z-score at break',
        ],
        'value': [
            f"{len(df):,}",
            f"{len(df[df['break_type']=='peak']):,}",
            f"{len(df[df['break_type']=='trough']):,}",
            f"{df['total_darkpool_shares'].mean():,.0f}",
            f"{df['total_darkpool_trades'].mean():,.0f}",
            f"{df['num_ats_venues'].mean():.1f}",
            f"{df['concentration_ratio'].mean():.4f}",
            f"{df['dp_volume_zscore'].mean():+.4f}",
        ]
    })
    print(summary.to_string(index=False))
    results['summary'] = summary

    # ── Analysis 2: Dark Pool by Break Type ────────────────────────────────
    print("\n" + "-" * 60)
    print("ANALYSIS 2: DARK POOL METRICS BY BREAK TYPE")
    print("-" * 60)

    by_type = df.groupby('break_type').agg({
        'total_darkpool_shares': ['mean', 'median'],
        'total_darkpool_trades': ['mean', 'median'],
        'num_ats_venues': 'mean',
        'concentration_ratio': ['mean', 'median'],
        'dp_shares_change': ['mean', 'median'],
        'dp_volume_zscore': ['mean', 'median'],
        'magnitude': 'count'
    }).round(4)
    by_type.columns = ['_'.join(col).strip('_') for col in by_type.columns]
    print(by_type.to_string())
    results['by_break_type'] = by_type

    # Statistical test: is dark pool volume different at peaks vs troughs?
    peak_dp = df[df['break_type'] == 'peak']['dp_volume_zscore'].dropna()
    trough_dp = df[df['break_type'] == 'trough']['dp_volume_zscore'].dropna()
    if len(peak_dp) > 30 and len(trough_dp) > 30:
        t_stat, p_val = stats.ttest_ind(peak_dp, trough_dp)
        print(f"\n  T-test (DP volume z-score: peak vs trough): t={t_stat:.4f}, p={p_val:.6f}")
        if p_val < 0.05:
            print(f"  -> SIGNIFICANT: Dark pool volume differs between peaks and troughs")
        else:
            print(f"  -> Not significant at p<0.05")

    # ── Analysis 3: Dark Pool Volume Change Before Breaks ──────────────────
    print("\n" + "-" * 60)
    print("ANALYSIS 3: DARK POOL VOLUME CHANGE BEFORE BREAKS")
    print("-" * 60)

    change_df = df.dropna(subset=['dp_shares_change'])
    if not change_df.empty:
        # Bucket changes
        change_df = change_df.copy()
        change_df['dp_change_bucket'] = pd.cut(
            change_df['dp_shares_change'].clip(-1, 2),
            bins=[-1, -0.2, -0.05, 0.05, 0.2, 2],
            labels=['Big Drop (>20%)', 'Moderate Drop', 'Flat', 'Moderate Rise', 'Big Rise (>20%)']
        )

        change_vs_type = pd.crosstab(
            change_df['dp_change_bucket'],
            change_df['break_type'],
            normalize='index'
        ).round(4) * 100
        print("Break type distribution by dark pool volume change (%):")
        print(change_vs_type.to_string())
        results['dp_change_vs_break'] = change_vs_type

        # Correlation
        for bt in ['peak', 'trough']:
            subset = change_df[change_df['break_type'] == bt]
            if len(subset) > 30:
                corr = subset['dp_shares_change'].corr(subset['magnitude'])
                print(f"\n  Correlation (DP change vs magnitude) for {bt}: r={corr:+.4f} (n={len(subset)})")

    # ── Analysis 4: ATS Concentration at Breaks ────────────────────────────
    print("\n" + "-" * 60)
    print("ANALYSIS 4: ATS VENUE CONCENTRATION AT BREAKS")
    print("-" * 60)

    conc_df = df.dropna(subset=['concentration_ratio']).copy()
    if not conc_df.empty:
        conc_df['concentration_bucket'] = pd.cut(
            conc_df['concentration_ratio'],
            bins=[0, 0.15, 0.25, 0.40, 1.0],
            labels=['Dispersed (<15%)', 'Moderate (15-25%)', 'Concentrated (25-40%)', 'Highly Conc (>40%)']
        )

        conc_breaks = pd.crosstab(
            conc_df['concentration_bucket'],
            conc_df['break_type'],
            normalize='index'
        ).round(4) * 100
        print("Break type distribution by ATS concentration (%):")
        print(conc_breaks.to_string())
        results['concentration_vs_break'] = conc_breaks

        # Average magnitude by concentration
        mag_by_conc = conc_df.groupby('concentration_bucket').agg({
            'magnitude': ['mean', 'median', 'count'],
            'dp_volume_zscore': 'mean'
        }).round(4)
        mag_by_conc.columns = ['_'.join(col) for col in mag_by_conc.columns]
        print("\nBreak magnitude by ATS concentration:")
        print(mag_by_conc.to_string())

    # ── Analysis 5: Predictive Power - Post-Break Returns ──────────────────
    print("\n" + "-" * 60)
    print("ANALYSIS 5: DARK POOL PREDICTIVE POWER (POST-BREAK RETURNS)")
    print("-" * 60)

    timing_results = []
    unique_tickers = df['ticker'].unique()
    print(f"  Computing post-break returns for {len(unique_tickers)} tickers...")

    for i, ticker in enumerate(unique_tickers):
        if (i + 1) % 50 == 0:
            print(f"    {i+1}/{len(unique_tickers)} tickers...")

        ticker_data = df[df['ticker'] == ticker]
        if ticker_data.empty:
            continue

        min_date = ticker_data['timestamp'].min() - timedelta(days=5)
        max_date = ticker_data['timestamp'].max() + timedelta(days=45)
        prices = load_stock_prices(conn, ticker, str(min_date.date()), str(max_date.date()))

        if len(prices) < 10:
            continue

        for _, row in ticker_data.iterrows():
            break_time = row['timestamp']
            price_at = row['price_at_break']
            if price_at is None or price_at == 0:
                continue

            post = prices[prices.index >= break_time]
            if len(post) < 5:
                continue

            ret_5d = (float(post['close'].iloc[min(4, len(post)-1)]) / float(price_at) - 1)
            ret_20d = (float(post['close'].iloc[min(19, len(post)-1)]) / float(price_at) - 1) if len(post) > 19 else None

            timing_results.append({
                'ticker': ticker,
                'break_type': row['break_type'],
                'magnitude': row['magnitude'],
                'dp_volume_zscore': row['dp_volume_zscore'],
                'dp_shares_change': row['dp_shares_change'],
                'concentration_ratio': row['concentration_ratio'],
                'num_ats_venues': row['num_ats_venues'],
                'return_5d': ret_5d,
                'return_20d': ret_20d,
            })

    if timing_results:
        timing_df = pd.DataFrame(timing_results)
        print(f"\n  {len(timing_df):,} break-return pairs computed")

        # Correlations
        print("\nCorrelation: Dark Pool Metrics vs Post-Break Returns")
        print("-" * 55)
        dp_cols = ['dp_volume_zscore', 'dp_shares_change', 'concentration_ratio', 'num_ats_venues']
        ret_cols = ['return_5d', 'return_20d']
        for dc in dp_cols:
            for rc in ret_cols:
                valid = timing_df[[dc, rc]].dropna()
                if len(valid) > 30:
                    corr = valid[dc].corr(valid[rc])
                    print(f"  {dc:25s} vs {rc:12s}: r = {corr:+.4f} (n={len(valid)})")

        # Split by high/low dark pool volume
        print("\nPost-Break Returns by Dark Pool Volume Regime")
        print("-" * 55)
        timing_df['dp_regime'] = np.where(
            timing_df['dp_volume_zscore'] > 1, 'High DP (z>1)',
            np.where(timing_df['dp_volume_zscore'] < -1, 'Low DP (z<-1)', 'Normal DP')
        )

        for regime in ['High DP (z>1)', 'Normal DP', 'Low DP (z<-1)']:
            subset = timing_df[timing_df['dp_regime'] == regime]
            if len(subset) > 10:
                r5 = subset['return_5d'].dropna()
                r20 = subset['return_20d'].dropna()
                print(f"\n  {regime} (n={len(subset)}):")
                if len(r5) > 0:
                    print(f"    5d return:  mean={r5.mean():+.4f}, median={r5.median():+.4f}")
                if len(r20) > 0:
                    print(f"    20d return: mean={r20.mean():+.4f}, median={r20.median():+.4f}")

        # Split by break type AND dark pool regime
        print("\nPost-Break Returns by Break Type + Dark Pool Regime")
        print("-" * 55)
        for bt in ['peak', 'trough']:
            for regime in ['High DP (z>1)', 'Normal DP', 'Low DP (z<-1)']:
                subset = timing_df[(timing_df['break_type'] == bt) & (timing_df['dp_regime'] == regime)]
                if len(subset) > 10:
                    r20 = subset['return_20d'].dropna()
                    if len(r20) > 0:
                        print(f"  {bt:6s} + {regime:15s}: 20d mean={r20.mean():+.4f}, "
                              f"median={r20.median():+.4f} (n={len(r20)})")

        results['timing'] = timing_df
    else:
        print("  Insufficient data for return analysis")

    # ── Analysis 6: Summary ────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("DARK POOL ANALYSIS SUMMARY")
    print("=" * 70)
    print(f"  Total breaks analyzed: {len(df):,}")
    print(f"  Tickers with dark pool + break data: {df['ticker'].nunique()}")
    print(f"  Date range: {df['timestamp'].min().date()} to {df['timestamp'].max().date()}")

    return results


# ════════════════════════════════════════════════════════════════════════════
# CBOE OPTIONS ANALYSIS
# ════════════════════════════════════════════════════════════════════════════

def analyze_cboe_options_vs_breaks(conn) -> Dict[str, pd.DataFrame]:
    """
    Analyze CBOE market-wide options sentiment vs individual stock trend breaks.

    Tests:
    1. Put/call ratio levels at trend breaks
    2. P/C ratio trends (rising/falling) before breaks
    3. Extreme P/C ratios and break type distribution
    4. Options sentiment vs market indices at breaks
    5. Predictive power for post-break direction
    """
    sys.stdout.reconfigure(line_buffering=True)

    print("\n" + "=" * 70)
    print("CBOE OPTIONS ANALYSIS vs TREND BREAKS")
    print("=" * 70)

    # Load data
    print("\nLoading data...")
    cboe = load_cboe_market_stats(conn)
    if cboe.empty:
        print("ERROR: No CBOE options data found.")
        return {}

    cboe['trade_date'] = pd.to_datetime(cboe['trade_date'])
    cboe_min = cboe['trade_date'].min()
    cboe_max = cboe['trade_date'].max()
    print(f"  CBOE data: {cboe_min.date()} to {cboe_max.date()}, {len(cboe):,} trading days")

    breaks = load_trend_breaks(conn, str(cboe_min.date()), str(cboe_max.date()))
    print(f"  Trend breaks in range: {len(breaks):,}")

    if breaks.empty:
        print("ERROR: No trend breaks found in CBOE date range.")
        return {}

    breaks['timestamp'] = pd.to_datetime(breaks['timestamp']).dt.tz_localize(None)

    # Calculate CBOE features
    # Total put/call ratio
    cboe['total_pcr'] = np.where(
        cboe['total_call_volume'] > 0,
        cboe['total_put_volume'] / cboe['total_call_volume'],
        np.nan
    )
    # Rolling averages for context
    cboe['pcr_5d'] = cboe['total_pcr'].rolling(5, min_periods=3).mean()
    cboe['pcr_20d'] = cboe['total_pcr'].rolling(20, min_periods=10).mean()
    cboe['pcr_change_5d'] = cboe['total_pcr'] - cboe['pcr_5d'].shift(5)

    # Z-score of P/C ratio
    cboe['pcr_mean_60d'] = cboe['total_pcr'].rolling(60, min_periods=30).mean()
    cboe['pcr_std_60d'] = cboe['total_pcr'].rolling(60, min_periods=30).std()
    cboe['pcr_zscore'] = np.where(
        cboe['pcr_std_60d'] > 0,
        (cboe['total_pcr'] - cboe['pcr_mean_60d']) / cboe['pcr_std_60d'],
        0
    )

    # Equity vs Index ratio spread
    cboe['equity_pcr'] = cboe['equity_put_call_ratio']
    cboe['index_pcr'] = cboe['index_put_call_ratio']
    cboe['pcr_spread'] = cboe['equity_pcr'] - cboe['index_pcr']

    # Volume features
    cboe['total_options_volume'] = cboe['total_call_volume'].fillna(0) + cboe['total_put_volume'].fillna(0)
    cboe['volume_20d_avg'] = cboe['total_options_volume'].rolling(20, min_periods=10).mean()
    cboe['volume_zscore'] = np.where(
        cboe['volume_20d_avg'] > 0,
        (cboe['total_options_volume'] - cboe['volume_20d_avg']) / cboe['volume_20d_avg'],
        0
    )

    # Match breaks to CBOE data using merge_asof
    breaks_sorted = breaks.sort_values('timestamp')
    cboe_sorted = cboe.sort_values('trade_date')

    merged = pd.merge_asof(
        breaks_sorted,
        cboe_sorted[['trade_date', 'total_pcr', 'pcr_5d', 'pcr_20d', 'pcr_change_5d',
                      'pcr_zscore', 'equity_pcr', 'index_pcr', 'pcr_spread',
                      'total_options_volume', 'volume_zscore']],
        left_on='timestamp',
        right_on='trade_date',
        direction='backward',
        tolerance=pd.Timedelta('5 days')
    )

    df = merged.dropna(subset=['total_pcr'])
    print(f"\n  Matched {len(df):,} breaks with CBOE data")

    if df.empty:
        print("ERROR: No breaks could be matched with CBOE data.")
        return {}

    results = {}

    # ── Analysis 1: Put/Call Ratio at Breaks ───────────────────────────────
    print("\n" + "-" * 60)
    print("ANALYSIS 1: PUT/CALL RATIO AT TREND BREAKS")
    print("-" * 60)

    summary = pd.DataFrame({
        'metric': [
            'Total breaks with CBOE data',
            'Peak breaks', 'Trough breaks',
            'Avg total P/C ratio at breaks',
            'Avg equity P/C ratio at breaks',
            'Avg index P/C ratio at breaks',
            'Avg P/C ratio z-score at breaks',
            'Avg P/C ratio 5d change at breaks',
        ],
        'value': [
            f"{len(df):,}",
            f"{len(df[df['break_type']=='peak']):,}",
            f"{len(df[df['break_type']=='trough']):,}",
            f"{df['total_pcr'].mean():.4f}",
            f"{df['equity_pcr'].dropna().mean():.4f}" if df['equity_pcr'].notna().any() else "N/A",
            f"{df['index_pcr'].dropna().mean():.4f}" if df['index_pcr'].notna().any() else "N/A",
            f"{df['pcr_zscore'].mean():+.4f}",
            f"{df['pcr_change_5d'].dropna().mean():+.4f}",
        ]
    })
    print(summary.to_string(index=False))
    results['summary'] = summary

    # ── Analysis 2: P/C Ratio by Break Type ────────────────────────────────
    print("\n" + "-" * 60)
    print("ANALYSIS 2: PUT/CALL RATIO BY BREAK TYPE")
    print("-" * 60)

    by_type = df.groupby('break_type').agg({
        'total_pcr': ['mean', 'median', 'std'],
        'pcr_zscore': ['mean', 'median'],
        'pcr_change_5d': ['mean', 'median'],
        'equity_pcr': 'mean',
        'index_pcr': 'mean',
        'pcr_spread': ['mean', 'median'],
        'volume_zscore': 'mean',
        'magnitude': 'count'
    }).round(4)
    by_type.columns = ['_'.join(col).strip('_') for col in by_type.columns]
    print(by_type.to_string())
    results['by_break_type'] = by_type

    # Statistical test
    peak_pcr = df[df['break_type'] == 'peak']['total_pcr'].dropna()
    trough_pcr = df[df['break_type'] == 'trough']['total_pcr'].dropna()
    if len(peak_pcr) > 30 and len(trough_pcr) > 30:
        t_stat, p_val = stats.ttest_ind(peak_pcr, trough_pcr)
        print(f"\n  T-test (P/C ratio: peak vs trough): t={t_stat:.4f}, p={p_val:.6f}")
        if p_val < 0.05:
            print(f"  -> SIGNIFICANT: P/C ratio differs between peaks and troughs")
            if peak_pcr.mean() > trough_pcr.mean():
                print(f"  -> Higher P/C (more bearish sentiment) at peaks: {peak_pcr.mean():.4f} vs {trough_pcr.mean():.4f}")
            else:
                print(f"  -> Higher P/C (more bearish sentiment) at troughs: {trough_pcr.mean():.4f} vs {peak_pcr.mean():.4f}")
        else:
            print(f"  -> Not significant at p<0.05")

    # ── Analysis 3: Extreme P/C Ratios ─────────────────────────────────────
    print("\n" + "-" * 60)
    print("ANALYSIS 3: EXTREME PUT/CALL RATIO REGIMES")
    print("-" * 60)

    df_copy = df.copy()
    df_copy['pcr_regime'] = pd.cut(
        df_copy['pcr_zscore'].clip(-3, 3),
        bins=[-3, -1.5, -0.5, 0.5, 1.5, 3],
        labels=['Very Bullish (z<-1.5)', 'Bullish (-1.5 to -0.5)',
                'Neutral', 'Bearish (0.5 to 1.5)', 'Very Bearish (z>1.5)']
    )

    pcr_breaks = pd.crosstab(
        df_copy['pcr_regime'],
        df_copy['break_type'],
        normalize='index'
    ).round(4) * 100
    print("Break type distribution by P/C ratio regime (%):")
    print(pcr_breaks.to_string())
    results['pcr_regime_breaks'] = pcr_breaks

    # Average magnitude by P/C regime
    mag_by_pcr = df_copy.groupby('pcr_regime').agg({
        'magnitude': ['mean', 'median', 'count'],
        'volume_ratio': 'mean'
    }).round(4)
    mag_by_pcr.columns = ['_'.join(col) for col in mag_by_pcr.columns]
    print("\nBreak magnitude by P/C ratio regime:")
    print(mag_by_pcr.to_string())

    # ── Analysis 4: Equity vs Index P/C Spread ─────────────────────────────
    print("\n" + "-" * 60)
    print("ANALYSIS 4: EQUITY vs INDEX PUT/CALL SPREAD")
    print("-" * 60)

    spread_df = df.dropna(subset=['pcr_spread']).copy()
    if len(spread_df) > 100:
        spread_df['spread_bucket'] = pd.cut(
            spread_df['pcr_spread'],
            bins=[-np.inf, -0.3, -0.1, 0.1, 0.3, np.inf],
            labels=['Index >> Equity', 'Index > Equity', 'Balanced',
                    'Equity > Index', 'Equity >> Index']
        )

        spread_breaks = pd.crosstab(
            spread_df['spread_bucket'],
            spread_df['break_type'],
            normalize='index'
        ).round(4) * 100
        print("Break type distribution by equity-index P/C spread (%):")
        print(spread_breaks.to_string())
        results['spread_vs_break'] = spread_breaks

    # ── Analysis 5: P/C Ratio Trend Before Breaks ──────────────────────────
    print("\n" + "-" * 60)
    print("ANALYSIS 5: P/C RATIO TREND BEFORE BREAKS")
    print("-" * 60)

    trend_df = df.dropna(subset=['pcr_change_5d']).copy()
    if len(trend_df) > 100:
        trend_df['pcr_trend'] = np.where(
            trend_df['pcr_change_5d'] > 0.03, 'Rising (more bearish)',
            np.where(trend_df['pcr_change_5d'] < -0.03, 'Falling (more bullish)', 'Flat')
        )

        trend_breaks = pd.crosstab(
            trend_df['pcr_trend'],
            trend_df['break_type'],
            normalize='index'
        ).round(4) * 100
        print("Break type distribution by P/C ratio trend (%):")
        print(trend_breaks.to_string())
        results['pcr_trend_vs_break'] = trend_breaks

    # ── Analysis 6: Predictive Power ───────────────────────────────────────
    print("\n" + "-" * 60)
    print("ANALYSIS 6: OPTIONS SENTIMENT PREDICTIVE POWER")
    print("-" * 60)

    # Test: do extreme P/C ratios predict break direction?
    # Direction after: 'up' = price went up after break, 'down' = went down
    direction_df = df[df['direction_after'].isin(['up', 'down'])].copy()
    if len(direction_df) > 100:
        direction_df['went_up'] = (direction_df['direction_after'] == 'up').astype(int)

        # Correlation
        for col in ['total_pcr', 'pcr_zscore', 'pcr_change_5d', 'pcr_spread', 'volume_zscore']:
            valid = direction_df[[col, 'went_up']].dropna()
            if len(valid) > 30:
                corr, pval = stats.pointbiserialr(valid['went_up'], valid[col])
                sig = " ***" if pval < 0.01 else " **" if pval < 0.05 else " *" if pval < 0.1 else ""
                print(f"  {col:20s} vs direction_after=up: r={corr:+.4f}, p={pval:.6f}{sig}")

    # ── Analysis 7: Options Volume at Breaks ───────────────────────────────
    print("\n" + "-" * 60)
    print("ANALYSIS 7: OPTIONS VOLUME AT TREND BREAKS")
    print("-" * 60)

    vol_df = df.dropna(subset=['volume_zscore']).copy()
    if len(vol_df) > 100:
        vol_df['options_vol_regime'] = np.where(
            vol_df['volume_zscore'] > 0.5, 'High Options Vol',
            np.where(vol_df['volume_zscore'] < -0.3, 'Low Options Vol', 'Normal Options Vol')
        )

        vol_breaks = pd.crosstab(
            vol_df['options_vol_regime'],
            vol_df['break_type'],
            normalize='index'
        ).round(4) * 100
        print("Break type distribution by options volume regime (%):")
        print(vol_breaks.to_string())

        # Magnitude by options volume
        mag_by_vol = vol_df.groupby('options_vol_regime').agg({
            'magnitude': ['mean', 'median', 'count']
        }).round(4)
        mag_by_vol.columns = ['_'.join(col) for col in mag_by_vol.columns]
        print("\nBreak magnitude by options volume regime:")
        print(mag_by_vol.to_string())
        results['options_vol_regime'] = vol_breaks

    # ── Summary ────────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("CBOE OPTIONS ANALYSIS SUMMARY")
    print("=" * 70)
    print(f"  Total breaks analyzed: {len(df):,}")
    print(f"  Tickers: {df['ticker'].nunique()}")
    print(f"  Date range: {df['timestamp'].min().date()} to {df['timestamp'].max().date()}")

    return results


# ════════════════════════════════════════════════════════════════════════════
# MARKET INDEX CORRELATION ANALYSIS
# ════════════════════════════════════════════════════════════════════════════

def analyze_market_context_at_breaks(conn) -> Dict[str, pd.DataFrame]:
    """
    Test whether market context (S&P, VIX, RUT, QQQ) provides signal at trend breaks.

    Uses the dark pool date range (most recent data with all indices populated).
    """
    sys.stdout.reconfigure(line_buffering=True)

    print("\n" + "=" * 70)
    print("MARKET INDEX CONTEXT AT TREND BREAKS")
    print("=" * 70)

    # Use the market indices date range (2020+)
    start_date = '2020-01-01'
    end_date = datetime.now().strftime('%Y-%m-%d')

    print("\nLoading data...")
    market = load_market_indices(conn, start_date, end_date)
    print(f"  Market indices loaded: {list(market.keys())}")

    breaks = load_trend_breaks(conn, start_date, end_date)
    print(f"  Trend breaks: {len(breaks):,}")

    if breaks.empty or not market:
        print("ERROR: Missing data.")
        return {}

    breaks['timestamp'] = pd.to_datetime(breaks['timestamp']).dt.tz_localize(None)

    # Build market features for each trading day
    features = {}

    # S&P 500 features
    if '^GSPC' in market:
        sp = market['^GSPC'][['close']].copy()
        sp['sp500_return_1d'] = sp['close'].pct_change(1)
        sp['sp500_return_5d'] = sp['close'].pct_change(5)
        sp['sp500_return_20d'] = sp['close'].pct_change(20)
        sp['sp500_trend'] = np.where(sp['sp500_return_20d'] > 0, 'up', 'down')
        sp['sp500_vol_20d'] = sp['sp500_return_1d'].rolling(20).std()
        features['sp500'] = sp

    # VIX features
    if '^VIX' in market:
        vix = market['^VIX'][['close']].copy()
        vix['vix_level'] = vix['close']
        vix['vix_change_1d'] = vix['close'].pct_change(1)
        vix['vix_change_5d'] = vix['close'].pct_change(5)
        vix['vix_regime'] = np.where(
            vix['close'] > 25, 'High (>25)',
            np.where(vix['close'] < 15, 'Low (<15)', 'Normal (15-25)')
        )
        features['vix'] = vix

    # Russell 2000 features
    if '^RUT' in market:
        rut = market['^RUT'][['close']].copy()
        rut['rut_return_1d'] = rut['close'].pct_change(1)
        rut['rut_return_5d'] = rut['close'].pct_change(5)
        rut['rut_return_20d'] = rut['close'].pct_change(20)
        rut['rut_trend'] = np.where(rut['rut_return_20d'] > 0, 'up', 'down')
        features['rut'] = rut

    # QQQ features
    if 'QQQ' in market:
        qqq = market['QQQ'][['close']].copy()
        qqq['qqq_return_1d'] = qqq['close'].pct_change(1)
        qqq['qqq_return_5d'] = qqq['close'].pct_change(5)
        qqq['qqq_return_20d'] = qqq['close'].pct_change(20)
        qqq['qqq_trend'] = np.where(qqq['qqq_return_20d'] > 0, 'up', 'down')
        features['qqq'] = qqq

    # Futures premium
    if 'ES=F' in market and '^GSPC' in market:
        es = market['ES=F'][['close']].rename(columns={'close': 'es_close'})
        sp_close = market['^GSPC'][['close']].rename(columns={'close': 'sp_close'})
        combined = es.join(sp_close, how='inner')
        combined['futures_premium'] = (combined['es_close'] - combined['sp_close']) / combined['sp_close']
        features['futures'] = combined

    # RUT vs S&P (small cap vs large cap) spread
    if '^RUT' in market and '^GSPC' in market:
        rut_ret = market['^RUT'][['close']].pct_change(20).rename(columns={'close': 'rut_20d'})
        sp_ret = market['^GSPC'][['close']].pct_change(20).rename(columns={'close': 'sp500_20d'})
        spread = rut_ret.join(sp_ret, how='inner')
        spread['small_cap_spread'] = spread['rut_20d'] - spread['sp500_20d']
        features['small_cap_spread'] = spread

    # Merge all features onto breaks via merge_asof
    breaks_sorted = breaks.sort_values('timestamp')

    # Build one big features DataFrame
    feature_cols = {}
    for name, fdf in features.items():
        fdf_reset = fdf.reset_index()
        fdf_reset = fdf_reset.rename(columns={'index': 'timestamp'}) if 'timestamp' not in fdf_reset.columns else fdf_reset

        m = pd.merge_asof(
            breaks_sorted[['timestamp']].drop_duplicates(),
            fdf_reset,
            on='timestamp',
            direction='backward',
            tolerance=pd.Timedelta('5 days')
        )
        m = m.set_index('timestamp')
        for col in m.columns:
            if col not in ['close', 'sp_close', 'es_close']:
                feature_cols[col] = m[col]

    feature_df = pd.DataFrame(feature_cols)
    df = pd.merge_asof(
        breaks_sorted,
        feature_df.reset_index(),
        on='timestamp',
        direction='backward'
    )

    print(f"\n  Matched {len(df):,} breaks with market context")

    results = {}

    # ── VIX Regime Analysis ────────────────────────────────────────────────
    if 'vix_regime' in df.columns:
        print("\n" + "-" * 60)
        print("VIX REGIME vs TREND BREAKS")
        print("-" * 60)

        vix_breaks = pd.crosstab(
            df['vix_regime'],
            df['break_type'],
            normalize='index'
        ).round(4) * 100
        print("Break type distribution by VIX regime (%):")
        print(vix_breaks.to_string())

        vix_mag = df.groupby('vix_regime').agg({
            'magnitude': ['mean', 'median', 'count'],
            'volume_ratio': 'mean'
        }).round(4)
        vix_mag.columns = ['_'.join(col) for col in vix_mag.columns]
        print("\nBreak magnitude by VIX regime:")
        print(vix_mag.to_string())
        results['vix_regime'] = vix_breaks

    # ── S&P 500 Trend Analysis ─────────────────────────────────────────────
    if 'sp500_trend' in df.columns:
        print("\n" + "-" * 60)
        print("S&P 500 TREND vs TREND BREAKS")
        print("-" * 60)

        sp_breaks = pd.crosstab(
            df['sp500_trend'],
            df['break_type'],
            normalize='index'
        ).round(4) * 100
        print("Break type distribution by S&P 500 trend (%):")
        print(sp_breaks.to_string())
        results['sp500_trend'] = sp_breaks

    # ── Russell 2000 vs S&P Spread ─────────────────────────────────────────
    if 'small_cap_spread' in df.columns:
        print("\n" + "-" * 60)
        print("SMALL CAP SPREAD (RUT - S&P500) vs TREND BREAKS")
        print("-" * 60)

        spread_df = df.dropna(subset=['small_cap_spread']).copy()
        if len(spread_df) > 100:
            spread_df['spread_regime'] = np.where(
                spread_df['small_cap_spread'] > 0.02, 'Small Cap Leading',
                np.where(spread_df['small_cap_spread'] < -0.02, 'Large Cap Leading', 'Balanced')
            )

            spread_breaks = pd.crosstab(
                spread_df['spread_regime'],
                spread_df['break_type'],
                normalize='index'
            ).round(4) * 100
            print("Break type distribution by small cap spread (%):")
            print(spread_breaks.to_string())

            spread_mag = spread_df.groupby('spread_regime').agg({
                'magnitude': ['mean', 'median', 'count']
            }).round(4)
            spread_mag.columns = ['_'.join(col) for col in spread_mag.columns]
            print("\nBreak magnitude by small cap spread:")
            print(spread_mag.to_string())
            results['small_cap_spread'] = spread_breaks

    # ── QQQ Trend Analysis ─────────────────────────────────────────────────
    if 'qqq_trend' in df.columns:
        print("\n" + "-" * 60)
        print("QQQ (NASDAQ-100) TREND vs TREND BREAKS")
        print("-" * 60)

        qqq_breaks = pd.crosstab(
            df['qqq_trend'],
            df['break_type'],
            normalize='index'
        ).round(4) * 100
        print("Break type distribution by QQQ trend (%):")
        print(qqq_breaks.to_string())
        results['qqq_trend'] = qqq_breaks

    # ── Cross-Index Correlation ────────────────────────────────────────────
    print("\n" + "-" * 60)
    print("MARKET METRICS CORRELATION WITH BREAK MAGNITUDE")
    print("-" * 60)

    numeric_cols = ['sp500_return_1d', 'sp500_return_5d', 'sp500_return_20d', 'sp500_vol_20d',
                    'vix_level', 'vix_change_1d', 'vix_change_5d',
                    'rut_return_1d', 'rut_return_5d', 'rut_return_20d',
                    'qqq_return_1d', 'qqq_return_5d', 'qqq_return_20d',
                    'futures_premium', 'small_cap_spread']

    for col in numeric_cols:
        if col in df.columns:
            valid = df[['magnitude', col]].dropna()
            if len(valid) > 100:
                corr = valid['magnitude'].corr(valid[col])
                sig = " **" if abs(corr) > 0.05 else ""
                print(f"  {col:25s} vs magnitude: r = {corr:+.4f} (n={len(valid)}){sig}")

    # ── Direction Prediction ───────────────────────────────────────────────
    print("\n" + "-" * 60)
    print("MARKET CONTEXT PREDICTIVE POWER (DIRECTION AFTER BREAK)")
    print("-" * 60)

    dir_df = df[df['direction_after'].isin(['up', 'down'])].copy()
    if len(dir_df) > 100:
        dir_df['went_up'] = (dir_df['direction_after'] == 'up').astype(int)

        for col in numeric_cols:
            if col in dir_df.columns:
                valid = dir_df[[col, 'went_up']].dropna()
                if len(valid) > 100:
                    corr, pval = stats.pointbiserialr(valid['went_up'], valid[col])
                    sig = " ***" if pval < 0.01 else " **" if pval < 0.05 else " *" if pval < 0.1 else ""
                    print(f"  {col:25s} vs went_up: r={corr:+.4f}, p={pval:.6f}{sig}")

    # ── Summary ────────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("MARKET CONTEXT ANALYSIS SUMMARY")
    print("=" * 70)
    print(f"  Total breaks analyzed: {len(df):,}")
    print(f"  Date range: {df['timestamp'].min().date()} to {df['timestamp'].max().date()}")
    print(f"  Market indices used: {list(market.keys())}")

    return results


# ════════════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════════════

def run_all_analyses():
    """Run all dark pool, CBOE, and market context analyses."""
    sys.stdout.reconfigure(line_buffering=True)

    conn = get_db_connection()
    all_results = {}

    try:
        # 1. Dark pool analysis
        print("\n" + "#" * 70)
        print("# SECTION 1: DARK POOL ANALYSIS")
        print("#" * 70)
        dp_results = analyze_darkpool_vs_breaks(conn)
        all_results['darkpool'] = dp_results

        # 2. CBOE options analysis
        print("\n" + "#" * 70)
        print("# SECTION 2: CBOE OPTIONS ANALYSIS")
        print("#" * 70)
        cboe_results = analyze_cboe_options_vs_breaks(conn)
        all_results['cboe'] = cboe_results

        # 3. Market context analysis
        print("\n" + "#" * 70)
        print("# SECTION 3: MARKET INDEX CONTEXT")
        print("#" * 70)
        market_results = analyze_market_context_at_breaks(conn)
        all_results['market'] = market_results

    finally:
        conn.close()

    # Final summary
    print("\n" + "=" * 70)
    print("FINAL SUMMARY - ALL ANALYSES")
    print("=" * 70)
    for section, results in all_results.items():
        if results:
            print(f"  {section}: {len(results)} result tables generated")
        else:
            print(f"  {section}: No results (check data availability)")

    return all_results


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Dark Pool & Options Analysis')
    parser.add_argument('--darkpool', action='store_true', help='Run dark pool analysis only')
    parser.add_argument('--cboe', action='store_true', help='Run CBOE options analysis only')
    parser.add_argument('--market', action='store_true', help='Run market context analysis only')
    parser.add_argument('--all', action='store_true', default=True, help='Run all analyses')

    args = parser.parse_args()

    conn = get_db_connection()

    try:
        if args.darkpool and not args.cboe and not args.market:
            analyze_darkpool_vs_breaks(conn)
        elif args.cboe and not args.darkpool and not args.market:
            analyze_cboe_options_vs_breaks(conn)
        elif args.market and not args.darkpool and not args.cboe:
            analyze_market_context_at_breaks(conn)
        else:
            run_all_analyses()
    finally:
        conn.close()
