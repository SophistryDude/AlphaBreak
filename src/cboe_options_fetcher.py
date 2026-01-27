"""
CBOE Options Volume & Put/Call Ratio Fetcher

Downloads free options volume data from CBOE:
1. Archive CSVs from cdn.cboe.com (2006-2019): total, equity, index, ETP, VIX
   put/call ratios and volume data
2. CBOE daily market statistics page for recent data

This data provides market-wide sentiment indicators:
- Put/call ratios (contrarian indicator - high = bearish sentiment = potential bottom)
- Volume breakdowns by category (equity, index, ETP, VIX)

CBOE Data Sources:
https://www.cboe.com/us/options/market_statistics/historical_data/
https://www.cboe.com/us/options/market_statistics/daily/
"""

import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
from typing import List, Dict, Optional
import time
import psycopg2
from psycopg2.extras import execute_values, RealDictCursor
import os
import sys
import io
import argparse

# Database connection parameters
DB_CONFIG = {
    'host': os.environ.get('POSTGRES_HOST', 'localhost'),
    'port': int(os.environ.get('POSTGRES_PORT', 5433)),
    'database': os.environ.get('POSTGRES_DB', 'trading_data'),
    'user': os.environ.get('POSTGRES_USER', 'trading'),
    'password': os.environ.get('POSTGRES_PASSWORD', 'trading123')
}

# CBOE CDN archive URLs (free, no auth needed)
CBOE_CDN_BASE = "https://cdn.cboe.com/resources/options/volume_and_call_put_ratios"

CBOE_ARCHIVE_URLS = {
    'total': f"{CBOE_CDN_BASE}/totalpc.csv",
    'equity': f"{CBOE_CDN_BASE}/equitypc.csv",
    'index': f"{CBOE_CDN_BASE}/indexpcarchive.csv",
    'pcratio': f"{CBOE_CDN_BASE}/pcratioarchive.csv",
}

# Headers to mimic a browser
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}


def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)


def create_tables(conn):
    """Create CBOE options tables if they don't exist."""
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS cboe_options_volume (
            id SERIAL PRIMARY KEY,
            ticker VARCHAR(20) NOT NULL,
            trade_date DATE NOT NULL,
            call_volume BIGINT,
            put_volume BIGINT,
            total_volume BIGINT,
            put_call_ratio NUMERIC(10, 6),
            created_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(ticker, trade_date)
        );

        CREATE INDEX IF NOT EXISTS idx_cboe_options_ticker
            ON cboe_options_volume(ticker, trade_date DESC);
        CREATE INDEX IF NOT EXISTS idx_cboe_options_date
            ON cboe_options_volume(trade_date DESC);

        CREATE TABLE IF NOT EXISTS cboe_market_options_stats (
            id SERIAL PRIMARY KEY,
            trade_date DATE NOT NULL UNIQUE,
            total_call_volume BIGINT,
            total_put_volume BIGINT,
            total_volume BIGINT,
            equity_call_volume BIGINT,
            equity_put_volume BIGINT,
            equity_put_call_ratio NUMERIC(10, 6),
            index_call_volume BIGINT,
            index_put_volume BIGINT,
            index_put_call_ratio NUMERIC(10, 6),
            etp_call_volume BIGINT,
            etp_put_volume BIGINT,
            etp_put_call_ratio NUMERIC(10, 6),
            vix_call_volume BIGINT,
            vix_put_volume BIGINT,
            vix_put_call_ratio NUMERIC(10, 6),
            created_at TIMESTAMPTZ DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS idx_cboe_market_stats_date
            ON cboe_market_options_stats(trade_date DESC);
    """)
    conn.commit()
    cur.close()
    print("CBOE options tables created/verified.")


def download_csv(url: str) -> Optional[pd.DataFrame]:
    """Download a CSV from CBOE CDN. Handles disclaimer header rows."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=60)
        if resp.status_code == 200:
            # CBOE CSVs have a disclaimer as the first line, then a blank line,
            # then the actual header row. Find the real header by looking for
            # a line containing 'DATE' or 'date' or 'Trade_date'.
            lines = resp.text.strip().split('\n')
            header_idx = 0
            for i, line in enumerate(lines):
                line_lower = line.lower().strip()
                if 'date' in line_lower and ('call' in line_lower or 'put' in line_lower
                                              or 'ratio' in line_lower or 'total' in line_lower):
                    header_idx = i
                    break

            # Read CSV starting from the real header
            csv_text = '\n'.join(lines[header_idx:])
            try:
                df = pd.read_csv(io.StringIO(csv_text), on_bad_lines='skip')
            except Exception:
                df = pd.read_csv(io.StringIO(csv_text), encoding='latin1', on_bad_lines='skip')

            # Drop any fully empty rows
            df = df.dropna(how='all')
            return df
        else:
            print(f"  Failed to download {url}: HTTP {resp.status_code}")
            return None
    except Exception as e:
        print(f"  Error downloading {url}: {e}")
        return None


def parse_volume_csv(df: pd.DataFrame, category: str) -> pd.DataFrame:
    """
    Parse a CBOE volume CSV into a standardized format.
    Different CSVs have slightly different column names.
    """
    if df is None or df.empty:
        return pd.DataFrame()

    # Normalize column names
    cols = df.columns.tolist()
    col_map = {}
    for c in cols:
        cl = c.strip().lower()
        if 'date' in cl:
            col_map[c] = 'trade_date'
        elif cl in ('calls', 'call', 'call_volume'):
            col_map[c] = 'call_volume'
        elif cl in ('puts', 'put', 'put_volume'):
            col_map[c] = 'put_volume'
        elif cl == 'total' or cl == 'total_volume':
            col_map[c] = 'total_volume'
        elif 'p/c' in cl or 'ratio' in cl:
            col_map[c] = 'put_call_ratio'

    df = df.rename(columns=col_map)

    # Parse dates
    if 'trade_date' in df.columns:
        df['trade_date'] = pd.to_datetime(df['trade_date'], errors='coerce')
        df = df.dropna(subset=['trade_date'])
        df['trade_date'] = df['trade_date'].dt.date

    # Convert volumes to numeric
    for col in ['call_volume', 'put_volume', 'total_volume']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', ''), errors='coerce')

    if 'put_call_ratio' in df.columns:
        df['put_call_ratio'] = pd.to_numeric(df['put_call_ratio'], errors='coerce')

    df['category'] = category
    return df


def parse_pcratio_archive(df: pd.DataFrame) -> pd.DataFrame:
    """
    Parse the pcratioarchive.csv which has a different format:
    DATE, TOTAL VOLUME P/C RATIO, INDEX P/C RATIO, EQUITY P/C RATIO
    """
    if df is None or df.empty:
        return pd.DataFrame()

    cols = df.columns.tolist()
    col_map = {}
    for c in cols:
        cl = c.strip().lower()
        if 'date' in cl:
            col_map[c] = 'trade_date'
        elif 'total' in cl and 'ratio' in cl:
            col_map[c] = 'total_pcr'
        elif 'index' in cl and 'ratio' in cl:
            col_map[c] = 'index_pcr'
        elif 'equity' in cl and 'ratio' in cl:
            col_map[c] = 'equity_pcr'

    df = df.rename(columns=col_map)

    # Drop any columns we didn't map (e.g. disclaimer column)
    known = {'trade_date', 'total_pcr', 'index_pcr', 'equity_pcr'}
    df = df[[c for c in df.columns if c in known]]

    if 'trade_date' in df.columns:
        df['trade_date'] = pd.to_datetime(df['trade_date'], errors='coerce')
        df = df.dropna(subset=['trade_date'])
        df['trade_date'] = df['trade_date'].dt.date

    for col in ['total_pcr', 'index_pcr', 'equity_pcr']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    return df


def import_market_stats(conn, total_df: pd.DataFrame, equity_df: pd.DataFrame,
                        index_df: pd.DataFrame, pcratio_df: pd.DataFrame) -> int:
    """
    Combine all archive CSVs into cboe_market_options_stats.
    Joins on trade_date to build a single row per day.
    """
    # Start with total volume data
    if total_df.empty:
        print("  No total volume data to import")
        return 0

    # Build combined DataFrame
    combined = total_df[['trade_date', 'call_volume', 'put_volume', 'total_volume', 'put_call_ratio']].copy()
    combined = combined.rename(columns={
        'call_volume': 'total_call_volume',
        'put_volume': 'total_put_volume',
        'total_volume': 'total_volume',
        'put_call_ratio': 'total_pcr_from_vol'
    })

    # Join equity data
    if not equity_df.empty:
        eq = equity_df[['trade_date', 'call_volume', 'put_volume', 'put_call_ratio']].copy()
        eq = eq.rename(columns={
            'call_volume': 'equity_call_volume',
            'put_volume': 'equity_put_volume',
            'put_call_ratio': 'equity_put_call_ratio'
        })
        combined = combined.merge(eq, on='trade_date', how='left')

    # Join index data
    if not index_df.empty:
        ix = index_df[['trade_date', 'call_volume', 'put_volume', 'put_call_ratio']].copy()
        ix = ix.rename(columns={
            'call_volume': 'index_call_volume',
            'put_volume': 'index_put_volume',
            'put_call_ratio': 'index_put_call_ratio'
        })
        combined = combined.merge(ix, on='trade_date', how='left')

    # Join pcratio archive for early dates (before volume data exists)
    if not pcratio_df.empty:
        pcr = pcratio_df[['trade_date', 'equity_pcr', 'index_pcr']].copy()
        combined = combined.merge(pcr, on='trade_date', how='left')
        # Fill equity/index ratios from pcratio archive where missing
        if 'equity_put_call_ratio' in combined.columns:
            combined['equity_put_call_ratio'] = combined['equity_put_call_ratio'].fillna(combined.get('equity_pcr'))
        if 'index_put_call_ratio' in combined.columns:
            combined['index_put_call_ratio'] = combined['index_put_call_ratio'].fillna(combined.get('index_pcr'))
        combined = combined.drop(columns=['equity_pcr', 'index_pcr'], errors='ignore')

    # Sort and deduplicate
    combined = combined.sort_values('trade_date').drop_duplicates(subset='trade_date', keep='last')

    print(f"  Combined dataset: {len(combined):,} trading days")
    print(f"  Date range: {combined['trade_date'].min()} to {combined['trade_date'].max()}")

    # Insert into DB
    cur = conn.cursor()
    records = []
    for _, row in combined.iterrows():
        def safe_int(v):
            if pd.isna(v):
                return None
            return int(v)

        def safe_float(v):
            if pd.isna(v):
                return None
            return float(v)

        records.append((
            row['trade_date'],
            safe_int(row.get('total_call_volume')),
            safe_int(row.get('total_put_volume')),
            safe_int(row.get('total_volume')),
            safe_int(row.get('equity_call_volume')),
            safe_int(row.get('equity_put_volume')),
            safe_float(row.get('equity_put_call_ratio')),
            safe_int(row.get('index_call_volume')),
            safe_int(row.get('index_put_volume')),
            safe_float(row.get('index_put_call_ratio')),
            None,  # etp_call_volume (not in archive)
            None,  # etp_put_volume
            None,  # etp_put_call_ratio
            None,  # vix_call_volume
            None,  # vix_put_volume
            None,  # vix_put_call_ratio
        ))

    # Batch insert
    batch_size = 5000
    total_inserted = 0
    for start in range(0, len(records), batch_size):
        batch = records[start:start + batch_size]
        execute_values(
            cur,
            """INSERT INTO cboe_market_options_stats
               (trade_date, total_call_volume, total_put_volume, total_volume,
                equity_call_volume, equity_put_volume, equity_put_call_ratio,
                index_call_volume, index_put_volume, index_put_call_ratio,
                etp_call_volume, etp_put_volume, etp_put_call_ratio,
                vix_call_volume, vix_put_volume, vix_put_call_ratio)
               VALUES %s
               ON CONFLICT (trade_date) DO UPDATE SET
                 total_call_volume = COALESCE(EXCLUDED.total_call_volume, cboe_market_options_stats.total_call_volume),
                 total_put_volume = COALESCE(EXCLUDED.total_put_volume, cboe_market_options_stats.total_put_volume),
                 total_volume = COALESCE(EXCLUDED.total_volume, cboe_market_options_stats.total_volume),
                 equity_call_volume = COALESCE(EXCLUDED.equity_call_volume, cboe_market_options_stats.equity_call_volume),
                 equity_put_volume = COALESCE(EXCLUDED.equity_put_volume, cboe_market_options_stats.equity_put_volume),
                 equity_put_call_ratio = COALESCE(EXCLUDED.equity_put_call_ratio, cboe_market_options_stats.equity_put_call_ratio),
                 index_call_volume = COALESCE(EXCLUDED.index_call_volume, cboe_market_options_stats.index_call_volume),
                 index_put_volume = COALESCE(EXCLUDED.index_put_volume, cboe_market_options_stats.index_put_volume),
                 index_put_call_ratio = COALESCE(EXCLUDED.index_put_call_ratio, cboe_market_options_stats.index_put_call_ratio)""",
            batch
        )
        conn.commit()
        total_inserted += len(batch)
        if total_inserted % 10000 == 0:
            print(f"    Inserted {total_inserted:,}/{len(records):,}")

    cur.close()
    print(f"  Imported {total_inserted:,} daily market stats records")
    return total_inserted


def download_and_import_archives(conn):
    """Download all CBOE archive CSVs and import into database."""
    sys.stdout.reconfigure(line_buffering=True)

    print("=" * 60)
    print("CBOE OPTIONS DATA - ARCHIVE IMPORT")
    print("=" * 60)

    # Download each archive
    print("\nDownloading Total Exchange Volume & Put/Call Ratios...")
    total_raw = download_csv(CBOE_ARCHIVE_URLS['total'])
    if total_raw is not None:
        print(f"  Downloaded: {len(total_raw):,} rows")
        total_df = parse_volume_csv(total_raw, 'total')
    else:
        total_df = pd.DataFrame()

    print("\nDownloading Equity Volume & Put/Call Ratios...")
    equity_raw = download_csv(CBOE_ARCHIVE_URLS['equity'])
    if equity_raw is not None:
        print(f"  Downloaded: {len(equity_raw):,} rows")
        equity_df = parse_volume_csv(equity_raw, 'equity')
    else:
        equity_df = pd.DataFrame()

    print("\nDownloading Index Volume & Put/Call Ratios...")
    index_raw = download_csv(CBOE_ARCHIVE_URLS['index'])
    if index_raw is not None:
        print(f"  Downloaded: {len(index_raw):,} rows")
        index_df = parse_volume_csv(index_raw, 'index')
    else:
        index_df = pd.DataFrame()

    print("\nDownloading Put/Call Ratio Archive...")
    pcratio_raw = download_csv(CBOE_ARCHIVE_URLS['pcratio'])
    if pcratio_raw is not None:
        print(f"  Downloaded: {len(pcratio_raw):,} rows")
        pcratio_df = parse_pcratio_archive(pcratio_raw)
    else:
        pcratio_df = pd.DataFrame()

    # Import into market stats table
    print("\nImporting combined market options stats...")
    count = import_market_stats(conn, total_df, equity_df, index_df, pcratio_df)

    return count


def print_summary(conn):
    """Print summary of stored CBOE options data."""
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Market stats summary
    cur.execute("""
        SELECT
            COUNT(*) as total_days,
            MIN(trade_date) as earliest,
            MAX(trade_date) as latest,
            AVG(equity_put_call_ratio) as avg_equity_pcr,
            AVG(index_put_call_ratio) as avg_index_pcr,
            COUNT(equity_call_volume) as days_with_equity,
            COUNT(index_call_volume) as days_with_index
        FROM cboe_market_options_stats
    """)
    stats = cur.fetchone()

    print("\n" + "=" * 60)
    print("CBOE OPTIONS DATA SUMMARY")
    print("=" * 60)

    if stats['total_days'] == 0:
        print("  No CBOE options data stored yet.")
        cur.close()
        return

    print(f"\n  Market-Wide Stats:")
    print(f"    Trading days:         {stats['total_days']:,}")
    print(f"    Date range:           {stats['earliest']} to {stats['latest']}")
    print(f"    Days with equity PCR: {stats['days_with_equity']:,}")
    print(f"    Days with index PCR:  {stats['days_with_index']:,}")
    if stats['avg_equity_pcr']:
        print(f"    Avg equity PCR:       {float(stats['avg_equity_pcr']):.3f}")
    if stats['avg_index_pcr']:
        print(f"    Avg index PCR:        {float(stats['avg_index_pcr']):.3f}")

    # Show recent data
    cur.execute("""
        SELECT trade_date, total_volume, equity_put_call_ratio, index_put_call_ratio
        FROM cboe_market_options_stats
        ORDER BY trade_date DESC
        LIMIT 10
    """)
    recent = cur.fetchall()
    if recent:
        print(f"\n  Most Recent 10 Days:")
        print(f"  {'Date':<12} {'Total Vol':>12} {'Eq PCR':>8} {'Ix PCR':>8}")
        print(f"  {'-'*12} {'-'*12} {'-'*8} {'-'*8}")
        for row in recent:
            total = f"{row['total_volume']:,}" if row['total_volume'] else "N/A"
            eq = f"{float(row['equity_put_call_ratio']):.3f}" if row['equity_put_call_ratio'] else "N/A"
            ix = f"{float(row['index_put_call_ratio']):.3f}" if row['index_put_call_ratio'] else "N/A"
            print(f"  {row['trade_date']!s:<12} {total:>12} {eq:>8} {ix:>8}")

    # Per-ticker options data summary
    cur.execute("""
        SELECT
            COUNT(*) as total_records,
            COUNT(DISTINCT ticker) as tickers,
            MIN(trade_date) as earliest,
            MAX(trade_date) as latest
        FROM cboe_options_volume
    """)
    ticker_stats = cur.fetchone()
    if ticker_stats['total_records'] > 0:
        print(f"\n  Per-Ticker Options Volume:")
        print(f"    Total records:  {ticker_stats['total_records']:,}")
        print(f"    Tickers:        {ticker_stats['tickers']:,}")
        print(f"    Date range:     {ticker_stats['earliest']} to {ticker_stats['latest']}")

    # PCR extremes analysis
    cur.execute("""
        SELECT
            trade_date, equity_put_call_ratio
        FROM cboe_market_options_stats
        WHERE equity_put_call_ratio IS NOT NULL
        ORDER BY equity_put_call_ratio DESC
        LIMIT 5
    """)
    high_pcr = cur.fetchall()

    cur.execute("""
        SELECT
            trade_date, equity_put_call_ratio
        FROM cboe_market_options_stats
        WHERE equity_put_call_ratio IS NOT NULL
        ORDER BY equity_put_call_ratio ASC
        LIMIT 5
    """)
    low_pcr = cur.fetchall()

    if high_pcr:
        print(f"\n  Most Bearish Days (Highest Equity PCR):")
        for row in high_pcr:
            print(f"    {row['trade_date']}: PCR = {float(row['equity_put_call_ratio']):.3f}")
        print(f"\n  Most Bullish Days (Lowest Equity PCR):")
        for row in low_pcr:
            print(f"    {row['trade_date']}: PCR = {float(row['equity_put_call_ratio']):.3f}")

    cur.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CBOE Options Volume & Put/Call Ratio Fetcher")
    parser.add_argument("--import-archives", action="store_true",
                       help="Download and import CBOE archive CSVs (2006-2019)")
    parser.add_argument("--summary", action="store_true",
                       help="Print summary of stored CBOE options data")
    parser.add_argument("--create-tables", action="store_true",
                       help="Create CBOE options database tables")

    args = parser.parse_args()

    if not any([args.import_archives, args.summary, args.create_tables]):
        parser.print_help()
        sys.exit(1)

    conn = get_db_connection()

    if args.create_tables:
        create_tables(conn)

    if args.import_archives:
        create_tables(conn)
        download_and_import_archives(conn)
        print_summary(conn)

    if args.summary and not args.import_archives:
        print_summary(conn)

    conn.close()
