"""
FINRA Dark Pool (ATS) Data Fetcher

Fetches weekly OTC transparency data from FINRA's API to track dark pool
trading activity per ticker. This data provides:
- Weekly aggregate dark pool volume per ticker per ATS
- Total shares traded and trade count off-exchange
- 2-week delay for S&P 500/Russell 1000 stocks, 4-week for others

Dark pool volume ratios and unusual activity can signal institutional
accumulation/distribution not visible in lit exchange data.

FINRA API Documentation:
https://developer.finra.org/docs
"""

import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
from typing import List, Dict, Optional, Tuple
import time
import psycopg2
from psycopg2.extras import execute_values, RealDictCursor
import os
import sys
import json
import base64
import argparse

# Database connection parameters
DB_CONFIG = {
    'host': os.environ.get('POSTGRES_HOST', 'localhost'),
    'port': int(os.environ.get('POSTGRES_PORT', 5433)),
    'database': os.environ.get('POSTGRES_DB', 'trading_data'),
    'user': os.environ.get('POSTGRES_USER', 'trading'),
    'password': os.environ.get('POSTGRES_PASSWORD', 'trading123'),
    'sslmode': os.environ.get('POSTGRES_SSLMODE', 'prefer')
}

# FINRA API settings
FINRA_TOKEN_URL = "https://ews.fip.finra.org/fip/rest/ews/oauth2/access_token?grant_type=client_credentials"
FINRA_API_BASE = "https://api.finra.org/data/group/otcMarket/name"

# Credentials from environment or defaults
FINRA_CLIENT_ID = os.environ.get('FINRA_CLIENT_ID', 'efb640a8695c43589222')
FINRA_CLIENT_SECRET = os.environ.get('FINRA_CLIENT_SECRET', 'ZZ&1@b%^QvbuaBWPD^#5')

# NMS Tier identifiers
TIER_1 = "T1"  # S&P 500, Russell 1000, select ETPs (2-week delay)
TIER_2 = "T2"  # All other NMS stocks (4-week delay)
TIER_OTC = "T3"  # OTC equity securities


def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)


def create_tables(conn):
    """Create dark pool tables if they don't exist."""
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS darkpool_weekly_volume (
            id SERIAL PRIMARY KEY,
            ticker VARCHAR(20),
            week_start_date DATE NOT NULL,
            ats_name VARCHAR(255),
            ats_mpid VARCHAR(10),
            total_shares BIGINT,
            total_trades INTEGER,
            tier VARCHAR(5),
            created_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(ticker, week_start_date, ats_mpid)
        );

        CREATE INDEX IF NOT EXISTS idx_darkpool_ticker_date
            ON darkpool_weekly_volume(ticker, week_start_date DESC);
        CREATE INDEX IF NOT EXISTS idx_darkpool_date
            ON darkpool_weekly_volume(week_start_date DESC);
        CREATE INDEX IF NOT EXISTS idx_darkpool_ats
            ON darkpool_weekly_volume(ats_mpid, week_start_date DESC);

        CREATE TABLE IF NOT EXISTS darkpool_ticker_aggregates (
            id SERIAL PRIMARY KEY,
            ticker VARCHAR(20) NOT NULL,
            week_start_date DATE NOT NULL,
            total_darkpool_shares BIGINT,
            total_darkpool_trades INTEGER,
            num_ats_venues INTEGER,
            top_ats_mpid VARCHAR(10),
            top_ats_shares BIGINT,
            concentration_ratio NUMERIC(8, 6),
            created_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(ticker, week_start_date)
        );

        CREATE INDEX IF NOT EXISTS idx_darkpool_agg_ticker
            ON darkpool_ticker_aggregates(ticker, week_start_date DESC);
        CREATE INDEX IF NOT EXISTS idx_darkpool_agg_date
            ON darkpool_ticker_aggregates(week_start_date DESC);
    """)
    conn.commit()
    cur.close()
    print("Dark pool tables created/verified.")


class FINRAClient:
    """Client for FINRA OTC Transparency API."""

    def __init__(self, client_id: str = None, client_secret: str = None):
        self.client_id = client_id or FINRA_CLIENT_ID
        self.client_secret = client_secret or FINRA_CLIENT_SECRET
        self.access_token = None
        self.token_expiry = None

    def authenticate(self) -> bool:
        """Get OAuth2 access token from FINRA."""
        credentials = f"{self.client_id}:{self.client_secret}"
        encoded = base64.b64encode(credentials.encode()).decode()

        headers = {
            "Authorization": f"Basic {encoded}",
            "Content-Type": "application/x-www-form-urlencoded"
        }

        try:
            resp = requests.post(FINRA_TOKEN_URL, headers=headers, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                self.access_token = data.get("access_token")
                expires_in = data.get("expires_in", 1800)
                self.token_expiry = datetime.now() + timedelta(seconds=int(expires_in) - 60)
                print(f"Authenticated with FINRA API (token expires in {expires_in}s)")
                return True
            else:
                print(f"FINRA auth failed: {resp.status_code} - {resp.text}")
                return False
        except Exception as e:
            print(f"FINRA auth error: {e}")
            return False

    def _ensure_token(self):
        """Re-authenticate if token expired."""
        if self.access_token is None or (self.token_expiry and datetime.now() >= self.token_expiry):
            if not self.authenticate():
                raise RuntimeError("Failed to authenticate with FINRA API")

    def _api_headers(self) -> dict:
        self._ensure_token()
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    def fetch_weekly_summary(self, week_start: str, tier: str = None,
                              limit: int = 5000, offset: int = 0) -> List[dict]:
        """
        Fetch weekly ATS summary data for a specific week.

        Args:
            week_start: Date string YYYY-MM-DD (Monday of the week)
            tier: T1 (S&P 500/Russell 1000), T2 (other NMS), or None for all
            limit: Max records per request (max 5000 sync, 100000 async)
            offset: Pagination offset
        """
        url = f"{FINRA_API_BASE}/weeklySummary"

        filters = [
            {
                "fieldName": "weekStartDate",
                "fieldValue": week_start,
                "compareType": "EQUAL"
            }
        ]

        if tier:
            filters.append({
                "fieldName": "tierIdentifier",
                "fieldValue": tier,
                "compareType": "EQUAL"
            })

        payload = {
            "compareFilters": filters,
            "limit": limit,
            "offset": offset
        }

        try:
            resp = requests.post(url, headers=self._api_headers(),
                               json=payload, timeout=60)
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 401:
                # Token expired, re-auth and retry
                self.access_token = None
                resp = requests.post(url, headers=self._api_headers(),
                                   json=payload, timeout=60)
                if resp.status_code == 200:
                    return resp.json()
            print(f"FINRA API error ({resp.status_code}): {resp.text[:200]}")
            return []
        except Exception as e:
            print(f"FINRA API request error: {e}")
            return []

    def fetch_weekly_summary_historic(self, week_start: str, tier: str = None,
                                       limit: int = 5000, offset: int = 0) -> List[dict]:
        """
        Fetch from the historic dataset (data older than 12 months, up to 4 years).
        Same schema as weeklySummary but uses async endpoint for large requests.
        """
        url = f"{FINRA_API_BASE}/weeklySummaryHistoric"

        filters = [
            {
                "fieldName": "weekStartDate",
                "fieldValue": week_start,
                "compareType": "EQUAL"
            }
        ]

        if tier:
            filters.append({
                "fieldName": "tierIdentifier",
                "fieldValue": tier,
                "compareType": "EQUAL"
            })

        payload = {
            "compareFilters": filters,
            "limit": limit,
            "offset": offset
        }

        try:
            resp = requests.post(url, headers=self._api_headers(),
                               json=payload, timeout=120)
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 401:
                self.access_token = None
                resp = requests.post(url, headers=self._api_headers(),
                                   json=payload, timeout=120)
                if resp.status_code == 200:
                    return resp.json()
            print(f"FINRA historic API error ({resp.status_code}): {resp.text[:200]}")
            return []
        except Exception as e:
            print(f"FINRA historic API request error: {e}")
            return []

    def fetch_all_for_week(self, week_start: str, use_historic: bool = False) -> List[dict]:
        """
        Fetch ALL records for a given week, paginating through all results.
        """
        all_records = []
        offset = 0
        limit = 5000

        fetch_fn = self.fetch_weekly_summary_historic if use_historic else self.fetch_weekly_summary

        while True:
            batch = fetch_fn(week_start, limit=limit, offset=offset)
            if not batch:
                break
            all_records.extend(batch)
            if len(batch) < limit:
                break
            offset += limit
            time.sleep(0.5)  # Rate limiting

        return all_records

    def discover_available_weeks(self, use_historic: bool = False) -> List[str]:
        """
        Discover which weeks have data by testing recent Mondays.
        Returns list of week_start dates with available data.
        """
        available = []
        # Start from 3 weeks ago (accounting for delay) and go back
        check_date = datetime.now().date() - timedelta(weeks=3)

        # Check up to 52 weeks back (or 208 for historic)
        max_weeks = 208 if use_historic else 52

        for i in range(max_weeks):
            # Find the Monday of this week
            monday = check_date - timedelta(days=check_date.weekday())
            week_str = monday.strftime("%Y-%m-%d")

            fetch_fn = self.fetch_weekly_summary_historic if use_historic else self.fetch_weekly_summary
            test = fetch_fn(week_str, tier=TIER_1, limit=1)
            if test:
                available.append(week_str)
                if len(available) == 1:
                    print(f"  Most recent available week: {week_str}")

            check_date -= timedelta(weeks=1)
            time.sleep(0.3)

            if i % 10 == 9:
                print(f"  Checked {i+1} weeks, found {len(available)} with data...")

        return sorted(available)


def get_tracked_tickers(conn) -> List[str]:
    """Get list of tickers we track in our database."""
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT ticker FROM stock_prices ORDER BY ticker")
    tickers = [row[0] for row in cur.fetchall()]
    cur.close()
    return tickers


def get_latest_darkpool_date(conn) -> Optional[date]:
    """Get the most recent week_start_date in our dark pool table."""
    cur = conn.cursor()
    cur.execute("SELECT MAX(week_start_date) FROM darkpool_weekly_volume")
    result = cur.fetchone()
    cur.close()
    return result[0] if result and result[0] else None


def parse_finra_records(records: List[dict], tracked_tickers: set) -> List[tuple]:
    """
    Parse FINRA API response records into DB-ready tuples.
    Only keeps records for tickers we track.

    FINRA fields (from API response):
    - issueSymbolIdentifier: ticker symbol
    - weekStartDate: YYYY-MM-DD
    - totalWeeklyShareQuantity: total shares
    - totalWeeklyTradeCount: total trades
    - lastUpdateDate: when record was last updated
    - tierIdentifier: T1, T2, etc.
    - MPID: Market Participant ID (the ATS venue identifier)
    - marketParticipantName: Human-readable name of the ATS venue
    """
    parsed = []
    for rec in records:
        raw_ticker = rec.get("issueSymbolIdentifier")
        if not raw_ticker:
            continue
        ticker = str(raw_ticker).strip().upper()
        if not ticker or ticker not in tracked_tickers:
            continue

        week_start = rec.get("weekStartDate")
        ats_mpid = rec.get("MPID", rec.get("atsFirmId", rec.get("marketParticipantId", "")))
        ats_name = rec.get("marketParticipantName", rec.get("atsName", rec.get("otcDescription", "")))
        total_shares = rec.get("totalWeeklyShareQuantity", 0)
        total_trades = rec.get("totalWeeklyTradeCount", 0)
        tier = rec.get("tierIdentifier", "")

        if not week_start or not ats_mpid:
            continue

        # Convert types safely
        try:
            total_shares = int(total_shares) if total_shares else 0
            total_trades = int(total_trades) if total_trades else 0
        except (ValueError, TypeError):
            total_shares = 0
            total_trades = 0

        parsed.append((
            ticker, week_start, ats_name[:255] if ats_name else None,
            ats_mpid[:10] if ats_mpid else None,
            total_shares, total_trades, tier[:5] if tier else None
        ))

    return parsed


def insert_weekly_volume(conn, records: List[tuple]) -> int:
    """Insert parsed dark pool records into darkpool_weekly_volume."""
    if not records:
        return 0

    cur = conn.cursor()
    execute_values(
        cur,
        """INSERT INTO darkpool_weekly_volume
           (ticker, week_start_date, ats_name, ats_mpid, total_shares, total_trades, tier)
           VALUES %s
           ON CONFLICT (ticker, week_start_date, ats_mpid) DO UPDATE SET
             total_shares = EXCLUDED.total_shares,
             total_trades = EXCLUDED.total_trades,
             ats_name = EXCLUDED.ats_name""",
        records
    )
    conn.commit()
    cur.close()
    return len(records)


def build_ticker_aggregates(conn, week_start: str = None):
    """
    Build per-ticker aggregates from raw weekly volume data.
    Aggregates across all ATS venues for each ticker/week.
    """
    cur = conn.cursor()

    where_clause = ""
    params = []
    if week_start:
        where_clause = "WHERE week_start_date = %s"
        params = [week_start]

    cur.execute(f"""
        INSERT INTO darkpool_ticker_aggregates
            (ticker, week_start_date, total_darkpool_shares, total_darkpool_trades,
             num_ats_venues, top_ats_mpid, top_ats_shares, concentration_ratio)
        SELECT
            ticker,
            week_start_date,
            SUM(total_shares) as total_darkpool_shares,
            SUM(total_trades) as total_darkpool_trades,
            COUNT(DISTINCT ats_mpid) as num_ats_venues,
            (SELECT ats_mpid FROM darkpool_weekly_volume dv2
             WHERE dv2.ticker = dv.ticker AND dv2.week_start_date = dv.week_start_date
             ORDER BY total_shares DESC LIMIT 1) as top_ats_mpid,
            MAX(total_shares) as top_ats_shares,
            CASE WHEN SUM(total_shares) > 0
                 THEN MAX(total_shares)::numeric / SUM(total_shares)
                 ELSE 0 END as concentration_ratio
        FROM darkpool_weekly_volume dv
        {where_clause}
        GROUP BY ticker, week_start_date
        ON CONFLICT (ticker, week_start_date) DO UPDATE SET
            total_darkpool_shares = EXCLUDED.total_darkpool_shares,
            total_darkpool_trades = EXCLUDED.total_darkpool_trades,
            num_ats_venues = EXCLUDED.num_ats_venues,
            top_ats_mpid = EXCLUDED.top_ats_mpid,
            top_ats_shares = EXCLUDED.top_ats_shares,
            concentration_ratio = EXCLUDED.concentration_ratio
    """, params if params else None)

    count = cur.rowcount
    conn.commit()
    cur.close()
    return count


def fetch_and_store(client: FINRAClient, conn, weeks: List[str] = None,
                    use_historic: bool = False):
    """
    Main fetch pipeline: get dark pool data for specified weeks and store it.

    Args:
        client: Authenticated FINRA API client
        conn: Database connection
        weeks: List of week_start dates (YYYY-MM-DD, Mondays). If None, auto-detect.
        use_historic: Use historic endpoint for data > 12 months old
    """
    sys.stdout.reconfigure(line_buffering=True)

    # Get our tracked tickers
    tracked = set(get_tracked_tickers(conn))
    print(f"Tracking {len(tracked)} tickers in our database")

    if not weeks:
        # Auto-detect: fetch from last stored date forward, or last 4 weeks
        latest = get_latest_darkpool_date(conn)
        if latest:
            print(f"Last stored dark pool data: {latest}")
            # Generate Mondays from latest+7 days to now-14 days (accounting for delay)
            start = latest + timedelta(days=7)
            end = datetime.now().date() - timedelta(days=14)
            weeks = []
            current = start
            while current <= end:
                monday = current - timedelta(days=current.weekday())
                if monday.strftime("%Y-%m-%d") not in weeks:
                    weeks.append(monday.strftime("%Y-%m-%d"))
                current += timedelta(weeks=1)
        else:
            # First run: fetch last 4 weeks
            weeks = []
            for i in range(3, 7):  # 3-6 weeks ago
                d = datetime.now().date() - timedelta(weeks=i)
                monday = d - timedelta(days=d.weekday())
                weeks.append(monday.strftime("%Y-%m-%d"))
            weeks.sort()

    if not weeks:
        print("No new weeks to fetch.")
        return

    print(f"\nFetching dark pool data for {len(weeks)} weeks: {weeks[0]} to {weeks[-1]}")
    print("=" * 60)

    total_inserted = 0
    for i, week in enumerate(weeks):
        print(f"\n[{i+1}/{len(weeks)}] Week of {week}...")
        records = client.fetch_all_for_week(week, use_historic=use_historic)
        print(f"  Raw records from FINRA: {len(records):,}")

        if not records:
            print("  No data returned (may not be available yet)")
            continue

        parsed = parse_finra_records(records, tracked)
        print(f"  Matched to tracked tickers: {len(parsed):,}")

        if parsed:
            inserted = insert_weekly_volume(conn, parsed)
            total_inserted += inserted
            print(f"  Inserted/updated: {inserted:,}")

            # Build aggregates for this week
            agg_count = build_ticker_aggregates(conn, week)
            print(f"  Aggregated: {agg_count:,} ticker summaries")

        # Rate limiting between weeks
        if i < len(weeks) - 1:
            time.sleep(1.0)

    print(f"\nDone! Total records inserted/updated: {total_inserted:,}")


def fetch_historic_backfill(client: FINRAClient, conn, weeks_back: int = 52):
    """
    Backfill historical dark pool data.
    Uses WeeklySummaryHistoric for data > 12 months old,
    and WeeklySummary for data within the last 12 months.
    """
    sys.stdout.reconfigure(line_buffering=True)

    weeks = []
    for i in range(weeks_back):
        d = datetime.now().date() - timedelta(weeks=i + 3)  # start 3 weeks ago
        monday = d - timedelta(days=d.weekday())
        week_str = monday.strftime("%Y-%m-%d")
        if week_str not in weeks:
            weeks.append(week_str)

    weeks.sort()

    # Split into historic (>12 months) and recent (<=12 months)
    cutoff = datetime.now().date() - timedelta(days=365)
    historic_weeks = [w for w in weeks if datetime.strptime(w, "%Y-%m-%d").date() < cutoff]
    recent_weeks = [w for w in weeks if datetime.strptime(w, "%Y-%m-%d").date() >= cutoff]

    print(f"Backfilling {len(weeks)} weeks of dark pool data")
    print(f"  Historic (>12mo, weeklySummaryHistoric): {len(historic_weeks)} weeks")
    print(f"  Recent (<=12mo, weeklySummary): {len(recent_weeks)} weeks")
    print(f"  Date range: {weeks[0]} to {weeks[-1]}")

    if historic_weeks:
        print(f"\n--- Fetching {len(historic_weeks)} historic weeks ---")
        fetch_and_store(client, conn, weeks=historic_weeks, use_historic=True)

    if recent_weeks:
        print(f"\n--- Fetching {len(recent_weeks)} recent weeks ---")
        fetch_and_store(client, conn, weeks=recent_weeks, use_historic=False)


def print_summary(conn):
    """Print summary of stored dark pool data."""
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT
            COUNT(*) as total_records,
            COUNT(DISTINCT ticker) as unique_tickers,
            COUNT(DISTINCT ats_mpid) as unique_ats,
            COUNT(DISTINCT week_start_date) as unique_weeks,
            MIN(week_start_date) as earliest_week,
            MAX(week_start_date) as latest_week,
            SUM(total_shares) as total_shares_traded
        FROM darkpool_weekly_volume
    """)
    summary = cur.fetchone()

    print("\n" + "=" * 60)
    print("DARK POOL DATA SUMMARY")
    print("=" * 60)

    if summary['total_records'] == 0:
        print("  No dark pool data stored yet.")
        cur.close()
        return

    print(f"  Total records:        {summary['total_records']:,}")
    print(f"  Unique tickers:       {summary['unique_tickers']:,}")
    print(f"  Unique ATS venues:    {summary['unique_ats']:,}")
    print(f"  Weeks of data:        {summary['unique_weeks']:,}")
    print(f"  Date range:           {summary['earliest_week']} to {summary['latest_week']}")
    print(f"  Total shares traded:  {summary['total_shares_traded']:,}")

    # Top 10 tickers by dark pool volume
    cur.execute("""
        SELECT ticker, SUM(total_shares) as total_vol,
               SUM(total_trades) as total_trades,
               COUNT(DISTINCT week_start_date) as weeks
        FROM darkpool_weekly_volume
        GROUP BY ticker
        ORDER BY total_vol DESC
        LIMIT 10
    """)
    top = cur.fetchall()
    if top:
        print(f"\n  Top 10 tickers by dark pool volume:")
        print(f"  {'Ticker':<10} {'Total Shares':>15} {'Total Trades':>13} {'Weeks':>6}")
        print(f"  {'-'*10} {'-'*15} {'-'*13} {'-'*6}")
        for row in top:
            print(f"  {row['ticker']:<10} {row['total_vol']:>15,} {row['total_trades']:>13,} {row['weeks']:>6}")

    # Top ATS venues
    cur.execute("""
        SELECT ats_mpid, ats_name, SUM(total_shares) as total_vol,
               COUNT(DISTINCT ticker) as tickers
        FROM darkpool_weekly_volume
        WHERE ats_mpid IS NOT NULL
        GROUP BY ats_mpid, ats_name
        ORDER BY total_vol DESC
        LIMIT 10
    """)
    venues = cur.fetchall()
    if venues:
        print(f"\n  Top 10 ATS venues by volume:")
        print(f"  {'MPID':<10} {'Name':<30} {'Total Shares':>15} {'Tickers':>8}")
        print(f"  {'-'*10} {'-'*30} {'-'*15} {'-'*8}")
        for row in venues:
            name = (row['ats_name'] or 'Unknown')[:30]
            print(f"  {row['ats_mpid']:<10} {name:<30} {row['total_vol']:>15,} {row['tickers']:>8}")

    cur.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FINRA Dark Pool Data Fetcher")
    parser.add_argument("--fetch", action="store_true",
                       help="Fetch latest dark pool data (incremental)")
    parser.add_argument("--backfill", type=int, metavar="WEEKS",
                       help="Backfill N weeks of historical data (max 208)")
    parser.add_argument("--summary", action="store_true",
                       help="Print summary of stored dark pool data")
    parser.add_argument("--create-tables", action="store_true",
                       help="Create dark pool database tables")
    parser.add_argument("--test-auth", action="store_true",
                       help="Test FINRA API authentication only")
    parser.add_argument("--test-fetch", action="store_true",
                       help="Test fetch a single week of data (dry run)")

    args = parser.parse_args()

    if not any([args.fetch, args.backfill, args.summary, args.create_tables,
                args.test_auth, args.test_fetch]):
        parser.print_help()
        sys.exit(1)

    if args.test_auth:
        print("Testing FINRA API authentication...")
        client = FINRAClient()
        if client.authenticate():
            print("SUCCESS: Authentication works.")
        else:
            print("FAILED: Could not authenticate. Check credentials.")
        sys.exit(0)

    if args.test_fetch:
        print("Testing FINRA API fetch (single week, dry run)...")
        client = FINRAClient()
        if not client.authenticate():
            print("FAILED: Could not authenticate.")
            sys.exit(1)

        # Try 3 weeks ago
        test_date = datetime.now().date() - timedelta(weeks=3)
        monday = test_date - timedelta(days=test_date.weekday())
        week_str = monday.strftime("%Y-%m-%d")
        print(f"Fetching week of {week_str} (Tier 1 only, limit 10)...")

        records = client.fetch_weekly_summary(week_str, tier=TIER_1, limit=10)
        if records:
            print(f"SUCCESS: Got {len(records)} records")
            print(f"Sample record keys: {list(records[0].keys())}")
            print(f"Sample: {json.dumps(records[0], indent=2)}")
        else:
            print("No records returned. The week may not have data yet.")
        sys.exit(0)

    # For DB operations, connect
    conn = get_db_connection()

    if args.create_tables:
        create_tables(conn)

    if args.summary:
        print_summary(conn)

    if args.fetch:
        client = FINRAClient()
        if not client.authenticate():
            print("FAILED: Could not authenticate with FINRA.")
            sys.exit(1)
        create_tables(conn)  # Ensure tables exist
        fetch_and_store(client, conn)
        print_summary(conn)

    if args.backfill:
        weeks = min(args.backfill, 208)
        client = FINRAClient()
        if not client.authenticate():
            print("FAILED: Could not authenticate with FINRA.")
            sys.exit(1)
        create_tables(conn)
        fetch_historic_backfill(client, conn, weeks_back=weeks)
        print_summary(conn)

    conn.close()
