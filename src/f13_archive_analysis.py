"""
13F Archive Data Import and Trend Break Correlation Analysis

Imports historical 13F institutional holdings data (Kaggle archive, Q1 2015 - Q3 2017)
into dedicated training tables and analyzes correlations between institutional holding
changes and trend breaks on daily price charts.

Key questions:
- Do institutional buying/selling patterns precede trend breaks?
- Which holding change patterns best predict peak vs trough breaks?
- Does institutional sentiment align with or diverge from technical indicators?
"""

import pandas as pd
import numpy as np
import psycopg2
from psycopg2.extras import execute_values, RealDictCursor
import os
import sys
import zipfile
import io
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Callable

DB_CONFIG = {
    'host': os.environ.get('POSTGRES_HOST', 'localhost'),
    'port': int(os.environ.get('POSTGRES_PORT', 5433)),
    'database': os.environ.get('POSTGRES_DB', 'trading_data'),
    'user': os.environ.get('POSTGRES_USER', 'trading'),
    'password': os.environ.get('POSTGRES_PASSWORD', 'trading123'),
    'sslmode': os.environ.get('POSTGRES_SSLMODE', 'prefer')
}


def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)


# ════════════════════════════════════════════════════════════════════════════
# IMPORT FUNCTIONS
# ════════════════════════════════════════════════════════════════════════════

def load_archive_zip(zip_path: str) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Load and parse the three CSVs from the archive.zip file.

    Returns:
        (holdings_wide, institutions, stock_names) DataFrames
    """
    print(f"Loading archive from {zip_path}...")

    with zipfile.ZipFile(zip_path, 'r') as zf:
        file_list = zf.namelist()
        print(f"  Files in archive: {file_list}")

        # Find the right files
        data_file = [f for f in file_list if '13F' in f.upper() or 'data' in f.lower()][0]
        inst_file = [f for f in file_list if 'institution' in f.lower()][0]
        stock_file = [f for f in file_list if 'stock' in f.lower()][0]

        print(f"  Loading {data_file}...")
        with zf.open(data_file) as f:
            holdings_wide = pd.read_csv(f, dtype={'cusip': str}, low_memory=False)
        print(f"    {len(holdings_wide):,} rows x {len(holdings_wide.columns)} columns")

        print(f"  Loading {inst_file}...")
        with zf.open(inst_file) as f:
            institutions = pd.read_csv(f)
        print(f"    {len(institutions):,} institutions")

        print(f"  Loading {stock_file}...")
        with zf.open(stock_file) as f:
            stock_names = pd.read_csv(f, dtype=str)
        print(f"    {len(stock_names):,} stock names")

    return holdings_wide, institutions, stock_names


def unpivot_holdings(holdings_wide: pd.DataFrame) -> pd.DataFrame:
    """
    Convert wide-format holdings (columns = dates, values = shares)
    into long-format: one row per (cusip, cik, report_date).
    """
    # Identify date columns (format: YYYY-MM-DD or similar)
    id_cols = ['cusip', 'stock', 'cik', 'institution']
    # Any column not in id_cols is a date column
    possible_id = [c for c in holdings_wide.columns if c.lower() in ['cusip', 'stock', 'cik', 'institution', 'stock_name']]
    date_cols = [c for c in holdings_wide.columns if c not in possible_id]

    print(f"  ID columns: {possible_id}")
    print(f"  Date columns ({len(date_cols)}): {date_cols[:5]}...{date_cols[-3:]}")

    # Melt wide to long
    melted = holdings_wide.melt(
        id_vars=possible_id,
        value_vars=date_cols,
        var_name='report_date_str',
        value_name='shares_held'
    )

    # Drop NaN shares (no holding that quarter) and zero shares (empty filing months)
    melted = melted.dropna(subset=['shares_held'])
    melted['shares_held'] = melted['shares_held'].astype(np.int64)
    melted = melted[melted['shares_held'] > 0]

    # Parse dates - the date columns are like "2015-02" or "2015-02-28"
    melted['report_date'] = pd.to_datetime(melted['report_date_str'], errors='coerce')
    melted = melted.dropna(subset=['report_date'])
    melted['report_date'] = melted['report_date'].dt.date

    print(f"  Unpivoted to {len(melted):,} rows")
    print(f"  Date range: {melted['report_date'].min()} to {melted['report_date'].max()}")

    return melted


def build_cusip_ticker_map(conn) -> Dict[str, str]:
    """
    Build CUSIP -> ticker mapping from existing cusip_ticker_map table.
    Archive CUSIPs are variable-length (6-9 chars, often missing leading zeros).
    Build mappings using multiple strategies:
    1. Zero-pad archive CUSIP to 9 digits -> exact match
    2. Match first 6 digits of DB CUSIP -> archive CUSIP (zero-padded to 6)
    """
    cur = conn.cursor()
    cur.execute("SELECT cusip, ticker FROM cusip_ticker_map WHERE ticker IS NOT NULL")
    rows = cur.fetchall()
    cur.close()

    # Strategy 1: full 9-digit mapping (for archive cusips that are 7+ chars)
    full_9_map = {}
    for cusip9, ticker in rows:
        full_9_map[cusip9] = ticker

    # Strategy 2: first 6 digits of DB CUSIP -> ticker
    prefix_6_map = {}
    prefix_7_map = {}
    for cusip9, ticker in rows:
        prefix_6_map[cusip9[:6]] = ticker
        prefix_7_map[cusip9[:7]] = ticker

    print(f"  Loaded {len(full_9_map)} 9-digit, {len(prefix_6_map)} 6-prefix, {len(prefix_7_map)} 7-prefix CUSIP mappings")

    def lookup(archive_cusip: str) -> Optional[str]:
        """Try multiple matching strategies for an archive CUSIP."""
        c = str(archive_cusip).strip()
        # Skip non-numeric/special CUSIPs (options, cash, etc.)
        if len(c) < 4:
            return None

        # Strategy 1: zero-pad to 9 and exact match
        padded9 = c.zfill(9)
        if padded9 in full_9_map:
            return full_9_map[padded9]

        # Strategy 2: zero-pad to 6 and match first 6 of DB CUSIP
        padded6 = c[:6].zfill(6) if len(c) >= 6 else c.zfill(6)
        if padded6 in prefix_6_map:
            return prefix_6_map[padded6]

        # Strategy 3: for 7+ digit CUSIPs, try matching as first N digits of 9-digit CUSIP
        if len(c) >= 7:
            padded7 = c[:7].zfill(7)
            if padded7 in prefix_7_map:
                return prefix_7_map[padded7]

        return None

    return lookup


def import_institutions(institutions: pd.DataFrame, conn):
    """Import institutions.csv into f13_archive_institutions."""
    cur = conn.cursor()

    # Detect column names
    cols = institutions.columns.tolist()
    cik_col = [c for c in cols if 'cik' in c.lower()][0]
    name_col = [c for c in cols if c.lower() != cik_col.lower()][0]

    records = []
    for _, row in institutions.iterrows():
        cik = int(row[cik_col])
        name = str(row[name_col])[:255]
        records.append((cik, name))

    execute_values(
        cur,
        "INSERT INTO f13_archive_institutions (cik, institution_name) VALUES %s ON CONFLICT (cik) DO NOTHING",
        records
    )
    conn.commit()
    cur.close()
    print(f"  Imported {len(records)} institutions")


def import_stock_names(stock_names: pd.DataFrame, cusip_lookup, conn):
    """Import stock_names.csv into f13_archive_stocks with ticker mapping."""
    cur = conn.cursor()

    cols = stock_names.columns.tolist()
    # Handle typo in source data: "cuisp" instead of "cusip"
    cusip_col = [c for c in cols if 'cusip' in c.lower() or 'cuisp' in c.lower()][0]
    name_col = [c for c in cols if c.lower() != cusip_col.lower()][0]

    records = []
    mapped = 0
    for _, row in stock_names.iterrows():
        cusip = str(row[cusip_col]).strip()
        name = str(row[name_col])[:255]
        ticker = cusip_lookup(cusip)
        if ticker:
            mapped += 1
        records.append((cusip, name, ticker))

    execute_values(
        cur,
        "INSERT INTO f13_archive_stocks (cusip, stock_name, ticker) VALUES %s ON CONFLICT (cusip) DO NOTHING",
        records
    )
    conn.commit()
    cur.close()
    print(f"  Imported {len(records)} stock names ({mapped} mapped to tickers)")


def import_holdings(melted: pd.DataFrame, cusip_lookup, conn):
    """
    Import unpivoted holdings into f13_archive_holdings.
    Calculates quarter-over-quarter changes during import.
    """
    cur = conn.cursor()

    # Clear existing data for idempotent re-import
    cur.execute("TRUNCATE f13_archive_holdings RESTART IDENTITY")
    conn.commit()

    # Ensure cusip is string
    melted['cusip'] = melted['cusip'].astype(str)

    # Sort by cusip, cik, date to calculate changes
    melted = melted.sort_values(['cusip', 'cik', 'report_date']).reset_index(drop=True)

    # Calculate changes within each cusip/cik group
    melted['prev_shares'] = melted.groupby(['cusip', 'cik'])['shares_held'].shift(1)
    melted['shares_change'] = melted['shares_held'] - melted['prev_shares'].fillna(0)
    melted['shares_change_pct'] = np.where(
        melted['prev_shares'] > 0,
        (melted['shares_held'] - melted['prev_shares']) / melted['prev_shares'],
        np.nan
    )
    # Clamp extreme values
    melted['shares_change_pct'] = melted['shares_change_pct'].clip(-9999.9999, 9999.9999)

    # Classify position action
    conditions = [
        melted['prev_shares'].isna(),
        melted['shares_held'] > melted['prev_shares'] * 1.01,
        melted['shares_held'] < melted['prev_shares'] * 0.99,
    ]
    choices = ['NEW', 'INCREASED', 'DECREASED']
    melted['position_action'] = np.select(conditions, choices, default='UNCHANGED')

    # Map CUSIPs to tickers using multi-strategy lookup
    print("    Mapping CUSIPs to tickers...")
    unique_cusips = melted['cusip'].unique()
    cusip_to_ticker = {c: cusip_lookup(c) for c in unique_cusips}
    mapped_count = sum(1 for v in cusip_to_ticker.values() if v is not None)
    print(f"    Mapped {mapped_count}/{len(unique_cusips)} unique CUSIPs to tickers")
    melted['ticker'] = melted['cusip'].map(cusip_to_ticker)

    # Prepare columns for insertion - convert to Python native types
    insert_cols = ['cusip', 'cik', 'ticker', 'report_date', 'shares_held',
                   'prev_shares', 'shares_change', 'shares_change_pct', 'position_action']

    # Batch insert using execute_values for speed
    BIGINT_MAX = 9223372036854775807
    batch_size = 50000
    total = len(melted)
    inserted = 0

    for start in range(0, total, batch_size):
        batch = melted.iloc[start:start + batch_size]
        records = []
        for _, row in batch.iterrows():
            cusip_val = str(row['cusip'])
            cik_val = int(row['cik'])
            ticker_val = row['ticker'] if pd.notna(row['ticker']) else None
            report_date_val = row['report_date']
            shares_val = int(row['shares_held'])
            prev_val = int(row['prev_shares']) if pd.notna(row['prev_shares']) else None
            change_val = int(row['shares_change']) if pd.notna(row['shares_change']) else None
            pct_val = float(row['shares_change_pct']) if pd.notna(row['shares_change_pct']) else None

            # Clamp to bigint range
            if change_val is not None and abs(change_val) > BIGINT_MAX:
                change_val = BIGINT_MAX if change_val > 0 else -BIGINT_MAX
            if shares_val > BIGINT_MAX:
                shares_val = BIGINT_MAX

            records.append((
                cusip_val, cik_val, ticker_val, report_date_val, shares_val,
                prev_val, change_val, pct_val, row['position_action']
            ))

        execute_values(
            cur,
            """INSERT INTO f13_archive_holdings
               (cusip, cik, ticker, report_date, shares_held, prev_shares,
                shares_change, shares_change_pct, position_action)
               VALUES %s""",
            records
        )
        conn.commit()
        inserted += len(records)
        if inserted % 100000 == 0 or start + batch_size >= total:
            print(f"    Inserted {inserted:,}/{total:,} holdings")

    cur.close()
    print(f"  Total holdings imported: {inserted:,}")
    ticker_count = int(melted['ticker'].notna().sum())
    print(f"  Holdings with ticker mapping: {ticker_count:,} ({ticker_count/total*100:.1f}%)")


def build_archive_aggregates(conn):
    """
    Build per-ticker per-quarter aggregates from f13_archive_holdings.
    These pre-computed aggregates enable fast joins with trend_breaks.
    """
    cur = conn.cursor()

    cur.execute("TRUNCATE f13_archive_aggregates RESTART IDENTITY")

    cur.execute("""
        INSERT INTO f13_archive_aggregates
            (ticker, report_date, total_institutions, total_shares_held,
             institutions_increased, institutions_decreased, institutions_new,
             institutions_sold, institutions_unchanged,
             net_shares_change, net_shares_change_pct,
             institutional_sentiment, avg_position_change_pct)
        SELECT
            ticker,
            report_date,
            COUNT(DISTINCT cik) AS total_institutions,
            SUM(shares_held) AS total_shares_held,
            COUNT(*) FILTER (WHERE position_action = 'INCREASED') AS institutions_increased,
            COUNT(*) FILTER (WHERE position_action = 'DECREASED') AS institutions_decreased,
            COUNT(*) FILTER (WHERE position_action = 'NEW') AS institutions_new,
            0 AS institutions_sold,
            COUNT(*) FILTER (WHERE position_action = 'UNCHANGED') AS institutions_unchanged,
            SUM(COALESCE(shares_change, 0)) AS net_shares_change,
            CASE WHEN SUM(COALESCE(prev_shares, 0)) > 0
                 THEN SUM(COALESCE(shares_change, 0))::NUMERIC / SUM(COALESCE(prev_shares, 0))
                 ELSE NULL END AS net_shares_change_pct,
            -- Sentiment: (increased + new - decreased) / total
            CASE WHEN COUNT(DISTINCT cik) > 0
                 THEN (COUNT(*) FILTER (WHERE position_action IN ('INCREASED', 'NEW'))
                       - COUNT(*) FILTER (WHERE position_action = 'DECREASED'))::NUMERIC
                       / COUNT(DISTINCT cik)
                 ELSE 0 END AS institutional_sentiment,
            AVG(shares_change_pct) FILTER (WHERE shares_change_pct IS NOT NULL) AS avg_position_change_pct
        FROM f13_archive_holdings
        WHERE ticker IS NOT NULL
        GROUP BY ticker, report_date
        ON CONFLICT (ticker, report_date) DO UPDATE SET
            total_institutions = EXCLUDED.total_institutions,
            total_shares_held = EXCLUDED.total_shares_held,
            institutions_increased = EXCLUDED.institutions_increased,
            institutions_decreased = EXCLUDED.institutions_decreased,
            institutions_new = EXCLUDED.institutions_new,
            institutions_sold = EXCLUDED.institutions_sold,
            institutions_unchanged = EXCLUDED.institutions_unchanged,
            net_shares_change = EXCLUDED.net_shares_change,
            net_shares_change_pct = EXCLUDED.net_shares_change_pct,
            institutional_sentiment = EXCLUDED.institutional_sentiment,
            avg_position_change_pct = EXCLUDED.avg_position_change_pct
    """)

    conn.commit()

    cur.execute("SELECT COUNT(*), COUNT(DISTINCT ticker) FROM f13_archive_aggregates")
    count, tickers = cur.fetchone()
    cur.close()
    print(f"  Built {count:,} aggregate records across {tickers} tickers")


def import_archive(zip_path: str):
    """
    Full import pipeline: load archive.zip -> parse -> import to DB -> build aggregates.
    """
    # Force unbuffered output for progress tracking
    sys.stdout.reconfigure(line_buffering=True)

    print("=" * 70)
    print("13F ARCHIVE IMPORT")
    print("=" * 70)

    # Load CSVs
    holdings_wide, institutions, stock_names = load_archive_zip(zip_path)

    # Unpivot holdings
    print("\nUnpivoting holdings from wide to long format...")
    melted = unpivot_holdings(holdings_wide)

    # Connect and import
    conn = get_db_connection()
    cusip_map = build_cusip_ticker_map(conn)

    print("\nImporting institutions...")
    import_institutions(institutions, conn)

    print("\nImporting stock names...")
    import_stock_names(stock_names, cusip_map, conn)

    print("\nImporting holdings (with change calculations)...")
    import_holdings(melted, cusip_map, conn)

    print("\nBuilding per-ticker aggregates...")
    build_archive_aggregates(conn)

    conn.close()
    print("\nImport complete!")


# ════════════════════════════════════════════════════════════════════════════
# ANALYSIS FUNCTIONS
# ════════════════════════════════════════════════════════════════════════════

def get_archive_aggregates(conn, ticker: str = None) -> pd.DataFrame:
    """Fetch archive aggregates, optionally filtered by ticker."""
    query = """
        SELECT ticker, report_date, total_institutions, total_shares_held,
               institutions_increased, institutions_decreased, institutions_new,
               institutions_sold, institutions_unchanged,
               net_shares_change, net_shares_change_pct,
               institutional_sentiment, avg_position_change_pct
        FROM f13_archive_aggregates
    """
    params = []
    if ticker:
        query += " WHERE ticker = %s"
        params.append(ticker)
    query += " ORDER BY ticker, report_date"

    df = pd.read_sql(query, conn, params=params if params else None)
    df['report_date'] = pd.to_datetime(df['report_date'])
    return df


def get_trend_breaks_in_range(conn, start_date: str, end_date: str,
                               tickers: List[str] = None) -> pd.DataFrame:
    """Fetch trend breaks within a date range, optionally filtered by tickers."""
    query = """
        SELECT ticker, timestamp, break_type, direction_before, direction_after,
               price_at_break, magnitude, price_change_pct, volume_ratio,
               periods_since_last_break, trend_strength
        FROM trend_breaks
        WHERE timeframe = 'daily'
        AND timestamp >= %s AND timestamp <= %s
    """
    params = [start_date, end_date]

    if tickers:
        query += " AND ticker = ANY(%s)"
        params.append(tickers)

    query += " ORDER BY ticker, timestamp"
    df = pd.read_sql(query, conn, params=params)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    return df


def get_stock_prices_in_range(conn, ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
    """Fetch daily stock prices for a ticker within date range."""
    query = """
        SELECT timestamp, open, high, low, close, volume
        FROM stock_prices
        WHERE ticker = %s AND timestamp >= %s AND timestamp <= %s
        ORDER BY timestamp
    """
    df = pd.read_sql(query, conn, params=(ticker, start_date, end_date))
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)
    return df


def assign_holding_context_to_breaks(
    breaks_df: pd.DataFrame,
    agg_df: pd.DataFrame
) -> pd.DataFrame:
    """
    For each trend break, find the most recent institutional holding data
    and attach it as context features.

    Since 13F data is quarterly (reported monthly as per archive format),
    we use merge_asof to find the nearest prior holding report for each break.
    """
    if breaks_df.empty or agg_df.empty:
        return breaks_df

    # Prepare for merge_asof - both must be sorted by time
    breaks_sorted = breaks_df.sort_values('timestamp').copy()

    results = []
    for ticker in breaks_sorted['ticker'].unique():
        ticker_breaks = breaks_sorted[breaks_sorted['ticker'] == ticker].copy()
        ticker_agg = agg_df[agg_df['ticker'] == ticker].copy()

        if ticker_agg.empty:
            continue

        # merge_asof: for each break, find the most recent holding report
        # Normalize timezone - strip tz from breaks to match naive report_date
        ticker_agg = ticker_agg.sort_values('report_date')
        ticker_agg['report_date'] = pd.to_datetime(ticker_agg['report_date']).dt.tz_localize(None)
        ticker_breaks = ticker_breaks.sort_values('timestamp')
        ticker_breaks['timestamp'] = pd.to_datetime(ticker_breaks['timestamp']).dt.tz_localize(None)

        merged = pd.merge_asof(
            ticker_breaks,
            ticker_agg,
            left_on='timestamp',
            right_on='report_date',
            by='ticker',
            direction='backward',
            tolerance=pd.Timedelta('120 days')  # max 4 months lookback
        )
        results.append(merged)

    if not results:
        return pd.DataFrame()

    return pd.concat(results, ignore_index=True)


def analyze_holding_patterns_vs_breaks(conn) -> Dict[str, pd.DataFrame]:
    """
    Core analysis: correlate institutional holding changes with trend breaks.

    Returns dict of analysis DataFrames:
    - 'summary': Overall pattern summary
    - 'by_break_type': Patterns segmented by peak vs trough
    - 'by_sentiment': Breaks segmented by institutional sentiment
    - 'predictive_power': Statistical measures of institutional data's predictive value
    - 'timing_analysis': Whether institutions lead or lag trend breaks
    """
    print("=" * 70)
    print("13F ARCHIVE vs TREND BREAK ANALYSIS")
    print("=" * 70)

    # Load all archive aggregates
    print("\nLoading archive aggregates...")
    agg_df = get_archive_aggregates(conn)
    if agg_df.empty:
        print("ERROR: No archive aggregates found. Run --import-archive first.")
        return {}

    date_range = (agg_df['report_date'].min(), agg_df['report_date'].max())
    tickers_with_data = agg_df['ticker'].unique().tolist()
    print(f"  {len(agg_df):,} aggregate records, {len(tickers_with_data)} tickers")
    print(f"  Date range: {date_range[0].date()} to {date_range[1].date()}")

    # Load trend breaks overlapping the archive period
    print("\nLoading trend breaks in archive date range...")
    breaks_df = get_trend_breaks_in_range(
        conn,
        str(date_range[0].date()),
        str(date_range[1].date()),
        tickers_with_data
    )
    print(f"  {len(breaks_df):,} trend breaks for {breaks_df['ticker'].nunique()} tickers")

    if breaks_df.empty:
        print("ERROR: No trend breaks found in the archive date range.")
        return {}

    # Assign holding context to each break
    print("\nJoining institutional data to trend breaks...")
    merged = assign_holding_context_to_breaks(breaks_df, agg_df)
    has_inst_data = merged['institutional_sentiment'].notna().sum()
    print(f"  {has_inst_data:,}/{len(merged):,} breaks matched with institutional data")

    # Filter to only breaks with institutional data
    analysis_df = merged[merged['institutional_sentiment'].notna()].copy()

    if analysis_df.empty:
        print("ERROR: No breaks could be matched with institutional data.")
        return {}

    results = {}

    # ── Analysis 1: Overall Pattern Summary ──────────────────────────────
    print("\n" + "-" * 60)
    print("ANALYSIS 1: OVERALL HOLDING PATTERNS AT TREND BREAKS")
    print("-" * 60)

    summary = pd.DataFrame({
        'metric': [
            'Total breaks analyzed',
            'Breaks with inst. data',
            'Unique tickers',
            'Avg institutional sentiment',
            'Avg net shares change %',
            'Avg institutions holding',
            'Avg institutions increased',
            'Avg institutions decreased',
        ],
        'value': [
            len(breaks_df),
            len(analysis_df),
            analysis_df['ticker'].nunique(),
            f"{analysis_df['institutional_sentiment'].mean():.4f}",
            f"{analysis_df['net_shares_change_pct'].mean():.4f}" if analysis_df['net_shares_change_pct'].notna().any() else 'N/A',
            f"{analysis_df['total_institutions'].mean():.1f}",
            f"{analysis_df['institutions_increased'].mean():.1f}",
            f"{analysis_df['institutions_decreased'].mean():.1f}",
        ]
    })
    print(summary.to_string(index=False))
    results['summary'] = summary

    # ── Analysis 2: By Break Type (Peak vs Trough) ──────────────────────
    print("\n" + "-" * 60)
    print("ANALYSIS 2: INSTITUTIONAL PATTERNS BY BREAK TYPE")
    print("-" * 60)

    by_break = analysis_df.groupby('break_type').agg({
        'institutional_sentiment': ['mean', 'median', 'std', 'count'],
        'net_shares_change_pct': ['mean', 'median'],
        'institutions_increased': 'mean',
        'institutions_decreased': 'mean',
        'total_institutions': 'mean',
        'avg_position_change_pct': ['mean', 'median'],
    }).round(4)
    by_break.columns = ['_'.join(col).strip() for col in by_break.columns]
    print(by_break.to_string())
    results['by_break_type'] = by_break

    # Key insight: Is sentiment higher before peaks or troughs?
    if 'peak' in analysis_df['break_type'].values and 'trough' in analysis_df['break_type'].values:
        peak_sent = analysis_df[analysis_df['break_type'] == 'peak']['institutional_sentiment'].mean()
        trough_sent = analysis_df[analysis_df['break_type'] == 'trough']['institutional_sentiment'].mean()
        print(f"\n  KEY INSIGHT: Avg sentiment before peaks: {peak_sent:.4f}, before troughs: {trough_sent:.4f}")
        if peak_sent > trough_sent:
            print("  ->Institutions tend to be NET BUYERS before price peaks (potential contrarian signal)")
        else:
            print("  ->Institutions tend to be NET SELLERS before price peaks (aligned with market)")

    # ── Analysis 3: Sentiment Buckets ────────────────────────────────────
    print("\n" + "-" * 60)
    print("ANALYSIS 3: BREAK TYPE DISTRIBUTION BY SENTIMENT REGIME")
    print("-" * 60)

    # Bucket sentiment into categories
    analysis_df['sentiment_bucket'] = pd.cut(
        analysis_df['institutional_sentiment'],
        bins=[-np.inf, -0.3, -0.1, 0.1, 0.3, np.inf],
        labels=['Strong Sell', 'Mild Sell', 'Neutral', 'Mild Buy', 'Strong Buy']
    )

    sentiment_breaks = pd.crosstab(
        analysis_df['sentiment_bucket'],
        analysis_df['break_type'],
        normalize='index'
    ).round(4) * 100
    sentiment_breaks['total_count'] = pd.crosstab(
        analysis_df['sentiment_bucket'],
        analysis_df['break_type']
    ).sum(axis=1)
    print(sentiment_breaks.to_string())
    results['by_sentiment'] = sentiment_breaks

    # ── Analysis 4: Magnitude Analysis ───────────────────────────────────
    print("\n" + "-" * 60)
    print("ANALYSIS 4: BREAK MAGNITUDE vs INSTITUTIONAL ACTIVITY")
    print("-" * 60)

    # Bucket magnitude into quartiles
    analysis_df['magnitude_q'] = pd.qcut(
        analysis_df['magnitude'],
        q=4,
        labels=['Small', 'Medium', 'Large', 'Very Large'],
        duplicates='drop'
    )

    mag_inst = analysis_df.groupby('magnitude_q', observed=True).agg({
        'institutional_sentiment': ['mean', 'std'],
        'net_shares_change_pct': 'mean',
        'total_institutions': 'mean',
        'magnitude': 'count'
    }).round(4)
    mag_inst.columns = ['_'.join(col).strip() for col in mag_inst.columns]
    print(mag_inst.to_string())
    results['magnitude_analysis'] = mag_inst

    # ── Analysis 5: Timing / Lead-Lag Analysis ───────────────────────────
    print("\n" + "-" * 60)
    print("ANALYSIS 5: TIMING ANALYSIS - DO INSTITUTIONS LEAD OR LAG?")
    print("-" * 60)

    # For each ticker, load prices once and compute returns for all breaks
    timing_results = []
    unique_tickers = analysis_df['ticker'].unique()
    print(f"  Processing {len(unique_tickers)} tickers for timing analysis...")
    for i, ticker in enumerate(unique_tickers):
        if (i + 1) % 50 == 0:
            print(f"    {i+1}/{len(unique_tickers)} tickers processed...")

        ticker_data = analysis_df[analysis_df['ticker'] == ticker].sort_values('timestamp')
        ticker_data = ticker_data[ticker_data['institutional_sentiment'].notna()]
        if ticker_data.empty:
            continue

        # Load full price range for this ticker (with buffer)
        try:
            min_date = ticker_data['timestamp'].min() - timedelta(days=10)
            max_date = ticker_data['timestamp'].max() + timedelta(days=60)
            prices = get_stock_prices_in_range(
                conn, ticker, str(min_date.date()), str(max_date.date())
            )
        except Exception:
            continue

        if len(prices) < 20:
            continue

        # Normalize timezone on prices index
        if prices.index.tz is not None:
            prices.index = prices.index.tz_localize(None)

        for _, row in ticker_data.iterrows():
            break_time = row['timestamp']
            price_at_break = row['price_at_break']
            if price_at_break is None or price_at_break == 0:
                continue

            # Calculate returns after break
            post_break = prices[prices.index >= break_time]
            if len(post_break) < 5:
                continue

            # 5-day, 20-day, 40-day returns after break
            ret_5d = (float(post_break['close'].iloc[min(4, len(post_break)-1)]) / float(price_at_break) - 1) if len(post_break) > 4 else None
            ret_20d = (float(post_break['close'].iloc[min(19, len(post_break)-1)]) / float(price_at_break) - 1) if len(post_break) > 19 else None
            ret_40d = (float(post_break['close'].iloc[min(39, len(post_break)-1)]) / float(price_at_break) - 1) if len(post_break) > 39 else None

            timing_results.append({
                'ticker': ticker,
                'break_type': row['break_type'],
                'break_date': break_time,
                'sentiment': row['institutional_sentiment'],
                'net_change_pct': row['net_shares_change_pct'],
                'magnitude': row['magnitude'],
                'return_5d': ret_5d,
                'return_20d': ret_20d,
                'return_40d': ret_40d,
            })

    print(f"  Completed timing analysis: {len(timing_results)} break-return pairs")

    if timing_results:
        timing_df = pd.DataFrame(timing_results)

        # Correlation between institutional data and subsequent returns
        print("\nCorrelation: Institutional Metrics vs Post-Break Returns")
        print("-" * 50)
        corr_cols = ['sentiment', 'net_change_pct']
        ret_cols = ['return_5d', 'return_20d', 'return_40d']
        for cc in corr_cols:
            for rc in ret_cols:
                valid = timing_df[[cc, rc]].dropna()
                if len(valid) > 30:
                    corr = valid[cc].corr(valid[rc])
                    print(f"  {cc:20s} vs {rc:12s}: r = {corr:+.4f} (n={len(valid)})")

        # Split by sentiment direction
        print("\nAvg Post-Break Returns by Sentiment Direction")
        print("-" * 50)
        timing_df['sent_dir'] = np.where(timing_df['sentiment'] > 0.1, 'Buying',
                                  np.where(timing_df['sentiment'] < -0.1, 'Selling', 'Neutral'))

        for sent_dir in ['Buying', 'Neutral', 'Selling']:
            subset = timing_df[timing_df['sent_dir'] == sent_dir]
            if len(subset) > 10:
                print(f"\n  When institutions are {sent_dir} (n={len(subset)}):")
                for rc in ret_cols:
                    valid = subset[rc].dropna()
                    if len(valid) > 0:
                        print(f"    {rc}: mean={valid.mean():.4f}, median={valid.median():.4f}")

        # Split by break type AND sentiment
        print("\nPost-Break Returns by Break Type + Sentiment")
        print("-" * 50)
        for bt in ['peak', 'trough']:
            for sd in ['Buying', 'Neutral', 'Selling']:
                subset = timing_df[(timing_df['break_type'] == bt) & (timing_df['sent_dir'] == sd)]
                if len(subset) > 10:
                    r20 = subset['return_20d'].dropna()
                    if len(r20) > 0:
                        print(f"  {bt:6s} + {sd:8s}: 20d_return mean={r20.mean():+.4f}, median={r20.median():+.4f} (n={len(r20)})")

        results['timing_analysis'] = timing_df
    else:
        print("  Insufficient data for timing analysis")

    # ── Analysis 6: Predictive Power Summary ─────────────────────────────
    print("\n" + "-" * 60)
    print("ANALYSIS 6: PREDICTIVE POWER SUMMARY")
    print("-" * 60)

    # Simple binary test: does positive sentiment predict direction?
    if 'timing_analysis' in results and not results['timing_analysis'].empty:
        td = results['timing_analysis'].dropna(subset=['sentiment', 'return_20d'])
        if len(td) > 30:
            # Test 1: Positive sentiment -> positive 20d return?
            pos_sent = td[td['sentiment'] > 0]
            neg_sent = td[td['sentiment'] < 0]

            if len(pos_sent) > 10 and len(neg_sent) > 10:
                pos_accuracy = (pos_sent['return_20d'] > 0).mean()
                neg_accuracy = (neg_sent['return_20d'] < 0).mean()
                print(f"  When sentiment > 0: {pos_accuracy:.1%} of 20d returns are positive (n={len(pos_sent)})")
                print(f"  When sentiment < 0: {neg_accuracy:.1%} of 20d returns are negative (n={len(neg_sent)})")

            # Test 2: At peaks, does high sentiment predict reversal?
            peak_data = td[td['break_type'] == 'peak']
            trough_data = td[td['break_type'] == 'trough']

            if len(peak_data) > 20:
                high_sent_peaks = peak_data[peak_data['sentiment'] > 0.1]
                low_sent_peaks = peak_data[peak_data['sentiment'] <= 0.1]
                if len(high_sent_peaks) > 5 and len(low_sent_peaks) > 5:
                    print(f"\n  At PEAKS:")
                    print(f"    High sentiment (institutions buying): avg 20d return = {high_sent_peaks['return_20d'].mean():+.4f} (n={len(high_sent_peaks)})")
                    print(f"    Low sentiment (not buying):           avg 20d return = {low_sent_peaks['return_20d'].mean():+.4f} (n={len(low_sent_peaks)})")

            if len(trough_data) > 20:
                high_sent_troughs = trough_data[trough_data['sentiment'] > 0.1]
                low_sent_troughs = trough_data[trough_data['sentiment'] <= 0.1]
                if len(high_sent_troughs) > 5 and len(low_sent_troughs) > 5:
                    print(f"\n  At TROUGHS:")
                    print(f"    High sentiment (institutions buying): avg 20d return = {high_sent_troughs['return_20d'].mean():+.4f} (n={len(high_sent_troughs)})")
                    print(f"    Low sentiment (not buying):           avg 20d return = {low_sent_troughs['return_20d'].mean():+.4f} (n={len(low_sent_troughs)})")

            # Test 3: Is institutional change a useful feature for the model?
            from scipy import stats
            # Point-biserial correlation: sentiment vs direction after break
            analysis_df['went_up'] = (analysis_df['direction_after'] == 'up').astype(int)
            valid_for_corr = analysis_df[['institutional_sentiment', 'went_up']].dropna()
            if len(valid_for_corr) > 30:
                corr, pval = stats.pointbiserialr(valid_for_corr['went_up'], valid_for_corr['institutional_sentiment'])
                print(f"\n  Point-biserial correlation (sentiment vs direction_after=up):")
                print(f"    r = {corr:.4f}, p-value = {pval:.6f}")
                if pval < 0.05:
                    print(f"    ->STATISTICALLY SIGNIFICANT at p<0.05")
                else:
                    print(f"    ->Not significant at p<0.05")

    # Final Summary
    print("\n" + "=" * 70)
    print("SUMMARY OF FINDINGS")
    print("=" * 70)
    print(f"  Total trend breaks analyzed with institutional data: {len(analysis_df):,}")
    print(f"  Tickers with both institutional and trend break data: {analysis_df['ticker'].nunique()}")
    print(f"  Date range covered: {analysis_df['timestamp'].min().date()} to {analysis_df['timestamp'].max().date()}")

    return results


def run_full_analysis(zip_path: str = None, skip_import: bool = False):
    """
    Run the complete pipeline: import (optional) + analysis.
    """
    if not skip_import:
        if zip_path is None:
            zip_path = os.path.join(os.path.dirname(__file__), '..', 'docs', 'csv', 'archive.zip')
        import_archive(zip_path)

    print("\n")
    conn = get_db_connection()
    results = analyze_holding_patterns_vs_breaks(conn)
    conn.close()
    return results


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='13F Archive Import and Analysis')
    parser.add_argument('--import-archive', metavar='ZIP_PATH', nargs='?',
                        const=os.path.join(os.path.dirname(__file__), '..', 'docs', 'csv', 'archive.zip'),
                        help='Import archive.zip into training tables (default: docs/csv/archive.zip)')
    parser.add_argument('--analyze', action='store_true',
                        help='Run trend break correlation analysis on imported data')
    parser.add_argument('--full', action='store_true',
                        help='Import + analyze in one step')

    args = parser.parse_args()

    if args.full:
        run_full_analysis(args.import_archive)
    elif args.import_archive is not None:
        import_archive(args.import_archive)
    elif args.analyze:
        conn = get_db_connection()
        analyze_holding_patterns_vs_breaks(conn)
        conn.close()
    else:
        parser.print_help()
