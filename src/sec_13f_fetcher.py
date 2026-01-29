"""
SEC EDGAR 13F Filing Fetcher

Fetches 13F-HR filings from SEC EDGAR to track institutional ownership.
13F filings are required quarterly for institutional investment managers
with >$100M in qualifying assets.

Key features:
- Fetch filings for specific funds or all tracked funds
- Parse XML/HTML filing content
- Map CUSIPs to tickers
- Calculate position changes quarter-over-quarter
- Aggregate statistics across all funds

SEC EDGAR API Documentation:
https://www.sec.gov/os/webmaster-faq#developers
"""

import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import xml.etree.ElementTree as ET
import re
import time
import psycopg2
from psycopg2.extras import execute_values
import os
import json

# Database connection parameters
DB_CONFIG = {
    'host': os.environ.get('POSTGRES_HOST', 'localhost'),
    'port': int(os.environ.get('POSTGRES_PORT', 5433)),
    'database': os.environ.get('POSTGRES_DB', 'trading_data'),
    'user': os.environ.get('POSTGRES_USER', 'trading'),
    'password': os.environ.get('POSTGRES_PASSWORD', 'trading123'),
    'sslmode': os.environ.get('POSTGRES_SSLMODE', 'prefer')
}

# SEC EDGAR API settings
SEC_BASE_URL = "https://data.sec.gov"
SEC_FULL_INDEX_URL = "https://www.sec.gov/cgi-bin/browse-edgar"
SEC_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) TradingPredictionModel contact@example.com',
    'Accept-Encoding': 'gzip, deflate',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
}

# Major hedge funds to track (CIK numbers)
MAJOR_HEDGE_FUNDS = {
    '0001067983': 'Berkshire Hathaway Inc',
    '0001336528': 'Bridgewater Associates LP',
    '0001350694': 'Renaissance Technologies LLC',
    '0001649339': 'Citadel Advisors LLC',
    '0001037389': 'DE Shaw & Co Inc',
    '0001061768': 'Two Sigma Investments LP',
    '0001079114': 'Millennium Management LLC',
    '0001103804': 'AQR Capital Management LLC',
    '0001484148': 'Tiger Global Management LLC',
    '0001167483': 'Viking Global Investors LP',
    '0001061165': 'Point72 Asset Management',
    '0000921669': 'Soros Fund Management LLC',
    '0001568820': 'Coatue Management LLC',
    '0000860580': 'Elliott Investment Management',
    '0001040273': 'Third Point LLC',
    '0001359154': 'Pershing Square Capital Management',
    '0001510470': 'Baupost Group LLC',
    '0000102909': 'Appaloosa Management LP',
    '0001279708': 'Greenlight Capital Inc',
    '0001535392': 'Lone Pine Capital LLC',
}


def get_db_connection():
    """Create database connection."""
    return psycopg2.connect(**DB_CONFIG)


def get_current_quarter() -> Tuple[int, int]:
    """Return (year, quarter_number) for the most recent completed quarter."""
    now = datetime.now()
    # Current quarter
    current_q = (now.month - 1) // 3 + 1
    # Go back to most recent completed quarter
    if current_q == 1:
        return now.year - 1, 4
    return now.year, current_q - 1


def sec_request(url: str, params: dict = None, max_retries: int = 3) -> requests.Response:
    """
    Make a request to SEC EDGAR with rate limiting and retries.
    SEC recommends max 10 requests per second.
    """
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=SEC_HEADERS, params=params, timeout=30)
            response.raise_for_status()
            time.sleep(0.15)  # Rate limit: ~6 requests per second
            return response
        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
            else:
                raise e


def get_company_filings(cik: str, form_type: str = '13F-HR', count: int = 40) -> List[Dict]:
    """
    Get list of filings for a company from SEC EDGAR.

    Args:
        cik: SEC Central Index Key (with or without leading zeros)
        form_type: Form type to filter (13F-HR, 13F-HR/A)
        count: Maximum number of filings to return

    Returns:
        List of filing dictionaries
    """
    # Pad CIK to 10 digits
    cik = cik.lstrip('0').zfill(10)

    url = f"{SEC_BASE_URL}/submissions/CIK{cik}.json"

    try:
        response = sec_request(url)
        data = response.json()

        filings = []
        recent = data.get('filings', {}).get('recent', {})

        if not recent:
            return []

        forms = recent.get('form', [])
        accessions = recent.get('accessionNumber', [])
        filing_dates = recent.get('filingDate', [])
        primary_docs = recent.get('primaryDocument', [])

        for i, form in enumerate(forms):
            if form in [form_type, f'{form_type}/A']:
                filing = {
                    'cik': cik,
                    'form_type': form,
                    'accession_number': accessions[i] if i < len(accessions) else None,
                    'filing_date': filing_dates[i] if i < len(filing_dates) else None,
                    'primary_document': primary_docs[i] if i < len(primary_docs) else None,
                    'is_amendment': '/A' in form
                }
                filings.append(filing)

                if len(filings) >= count:
                    break

        return filings

    except Exception as e:
        print(f"Error fetching filings for CIK {cik}: {e}")
        return []


def parse_13f_xml(xml_content: str) -> Tuple[Dict, List[Dict]]:
    """
    Parse 13F-HR XML filing content.

    Args:
        xml_content: Raw XML content of the filing

    Returns:
        Tuple of (filing_info dict, list of holdings dicts)
    """
    holdings = []
    filing_info = {}

    try:
        # Handle namespace issues by removing all namespace-related content
        # 1. Remove all xmlns declarations (including default namespace)
        xml_content = re.sub(r'\sxmlns(?::[^=]*)?\s*=\s*"[^"]*"', '', xml_content)
        # 2. Remove xsi:schemaLocation and similar prefixed attributes
        xml_content = re.sub(r'\s[a-zA-Z]\w*:[a-zA-Z]\w*\s*=\s*"[^"]*"', '', xml_content)
        # 3. Remove namespace prefixes from opening tags (e.g., <ns1:tag -> <tag)
        xml_content = re.sub(r'<([a-zA-Z]\w*):', r'<', xml_content)
        # 4. Remove namespace prefixes from closing tags (e.g., </ns1:tag -> </tag)
        xml_content = re.sub(r'</([a-zA-Z]\w*):', r'</', xml_content)

        root = ET.fromstring(xml_content)

        # Parse info table entries - look for infoTable tags
        for info_table in root.iter():
            tag_name = info_table.tag.lower()
            # Match infoTable but not informationTable (the parent container)
            if tag_name == 'infotable':
                holding = {}

                for child in info_table:
                    tag = child.tag.lower()
                    text = child.text.strip() if child.text else ''

                    if 'nameofissuer' in tag:
                        holding['issuer_name'] = text
                    elif 'titleofclass' in tag:
                        holding['security_class'] = text
                    elif 'cusip' in tag:
                        holding['cusip'] = text.upper()
                    elif tag == 'value':
                        try:
                            holding['market_value'] = int(text)  # Value in dollars (not thousands for some filers)
                        except:
                            holding['market_value'] = 0
                    elif 'shrsorprnamt' in tag:
                        for sub in child:
                            subtag = sub.tag.lower()
                            if 'sshprnamt' in subtag and 'type' not in subtag:
                                try:
                                    holding['shares_held'] = int(sub.text.strip())
                                except:
                                    holding['shares_held'] = 0
                            elif 'sshprnamttype' in subtag or 'type' in subtag:
                                holding['sh_prn_type'] = sub.text.strip() if sub.text else ''
                    elif 'investmentdiscretion' in tag:
                        holding['investment_discretion'] = text
                    elif 'votingauthority' in tag:
                        for sub in child:
                            subtag = sub.tag.lower()
                            subtext = sub.text.strip() if sub.text else '0'
                            try:
                                if subtag == 'sole':
                                    holding['sole_voting_authority'] = int(subtext)
                                elif subtag == 'shared':
                                    holding['shared_voting_authority'] = int(subtext)
                                elif subtag == 'none':
                                    holding['no_voting_authority'] = int(subtext)
                            except:
                                pass

                if holding.get('cusip') and (holding.get('shares_held') or holding.get('market_value')):
                    # Set shares_held to 0 if not present (some filings omit for options)
                    if 'shares_held' not in holding:
                        holding['shares_held'] = 0
                    holdings.append(holding)

    except ET.ParseError as e:
        print(f"XML parse error: {e}")

    return filing_info, holdings


def fetch_filing_content(cik: str, accession_number: str, primary_doc: str = None) -> str:
    """
    Fetch the actual 13F filing content from SEC EDGAR.

    Args:
        cik: SEC CIK number
        accession_number: Filing accession number
        primary_doc: Primary document path from filing metadata

    Returns:
        XML content of the information table
    """
    # CIK should NOT have leading zeros for the URL path
    cik_int = str(int(cik.lstrip('0')))
    accession_clean = accession_number.replace('-', '')

    base_url = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_clean}"

    try:
        # Method 1: Get directory listing and find XML files with info table
        dir_response = sec_request(f"{base_url}/")
        if dir_response.status_code == 200:
            # Find all XML files in the listing
            xml_files = re.findall(r'href="([^"]+\.xml)"', dir_response.text)

            # Try each XML file to find the info table
            for xml_file in xml_files:
                # Skip primary_doc.xml as it's usually just the form cover
                if 'primary_doc' in xml_file.lower():
                    continue

                if xml_file.startswith('/'):
                    file_url = f"https://www.sec.gov{xml_file}"
                elif xml_file.startswith('http'):
                    file_url = xml_file
                else:
                    file_url = f"{base_url}/{xml_file}"

                try:
                    content_response = sec_request(file_url)
                    if content_response.status_code == 200:
                        content = content_response.text
                        # Check if this is the info table (contains holding data)
                        # Match <infoTable>, <infoTable , <ns1:infoTable, <informationTable
                        if re.search(r'<(ns\d+:)?info(rmation)?Table', content, re.IGNORECASE):
                            return content
                except:
                    continue

        # Method 2: Try common info table naming patterns
        common_patterns = [
            f"{base_url}/infotable.xml",
            f"{base_url}/form13fInfoTable.xml",
        ]

        for url in common_patterns:
            try:
                response = sec_request(url)
                if response.status_code == 200 and '<infoTable' in response.text.lower():
                    return response.text
            except:
                continue

    except Exception as e:
        print(f"Error fetching filing content: {e}")

    return ""


def get_quarter_from_date(date_str: str) -> str:
    """Convert date to quarter string (e.g., 'Q4 2024')."""
    date = datetime.strptime(date_str, '%Y-%m-%d') if isinstance(date_str, str) else date_str
    quarter = (date.month - 1) // 3 + 1
    return f"Q{quarter} {date.year}"


def get_report_date_from_filing(filing_date: str) -> str:
    """
    Estimate the report quarter end date from filing date.
    13F filings are due 45 days after quarter end.
    """
    date = datetime.strptime(filing_date, '%Y-%m-%d')

    # Filing is typically 30-45 days after quarter end
    estimated_quarter_end = date - timedelta(days=45)

    # Snap to quarter end
    quarter = (estimated_quarter_end.month - 1) // 3
    quarter_end_month = (quarter + 1) * 3
    if quarter_end_month > 12:
        quarter_end_month = 12

    quarter_end = datetime(estimated_quarter_end.year, quarter_end_month, 1)
    # Get last day of month
    if quarter_end_month == 12:
        quarter_end = datetime(estimated_quarter_end.year, 12, 31)
    else:
        quarter_end = datetime(estimated_quarter_end.year, quarter_end_month + 1, 1) - timedelta(days=1)

    return quarter_end.strftime('%Y-%m-%d')


def cusip_to_ticker(cusip: str, conn=None) -> Optional[str]:
    """
    Look up ticker symbol from CUSIP.
    First checks local cache, then tries external services.
    """
    if conn is None:
        conn = get_db_connection()
        should_close = True
    else:
        should_close = False

    cursor = conn.cursor()

    # Check local cache
    cursor.execute(
        "SELECT ticker FROM cusip_ticker_map WHERE cusip = %s AND is_active = TRUE",
        (cusip,)
    )
    result = cursor.fetchone()

    if result:
        cursor.close()
        if should_close:
            conn.close()
        return result[0]

    cursor.close()
    if should_close:
        conn.close()

    return None


def save_cusip_mapping(cusip: str, ticker: str, company_name: str, conn=None):
    """Save CUSIP to ticker mapping."""
    if conn is None:
        conn = get_db_connection()
        should_close = True
    else:
        should_close = False

    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO cusip_ticker_map (cusip, ticker, company_name, last_verified)
        VALUES (%s, %s, %s, NOW())
        ON CONFLICT (cusip) DO UPDATE SET
            ticker = EXCLUDED.ticker,
            company_name = EXCLUDED.company_name,
            last_verified = NOW()
    """, (cusip, ticker, company_name))
    conn.commit()
    cursor.close()

    if should_close:
        conn.close()


def batch_map_cusips_to_tickers():
    """
    Batch map CUSIPs to tickers using SEC company data.
    Downloads SEC's company_tickers_exchange.json and matches by company name.
    """
    try:
        response = sec_request("https://www.sec.gov/files/company_tickers_exchange.json")
        sec_data = response.json()
    except Exception as e:
        print(f"Error fetching SEC ticker data: {e}")
        return 0

    # Build name-to-ticker lookup with normalized names
    name_to_ticker = {}
    for entry in sec_data.get('data', []):
        cik, name, ticker, exchange = entry
        name_upper = name.upper().strip()
        name_to_ticker[name_upper] = ticker

        # Normalize: remove common suffixes
        for suffix in [' INC', ' CORP', ' CO', ' LTD', ' LP', ' LLC', ' PLC',
                       ' NV', ' SA', ' AG', ' SE', ' GROUP', ' HLDG', ' HLDGS',
                       ' HOLDINGS', ' DEL', ' NEW']:
            if name_upper.endswith(suffix):
                name_to_ticker[name_upper[:len(name_upper)-len(suffix)].strip()] = ticker

        name_to_ticker[name_upper.replace('.', '')] = ticker

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT DISTINCT cusip, issuer_name
        FROM f13_holdings
        WHERE ticker IS NULL
    ''')
    unmapped = cursor.fetchall()

    mapped = 0
    for cusip, name in unmapped:
        name_upper = name.upper().strip()
        ticker = name_to_ticker.get(name_upper)

        if not ticker:
            for suffix in [' INC DEL', ' INC NEW', ' INC', ' CORP', ' CO', ' LTD',
                           ' LP', ' LLC', ' PLC', ' CLASS A', ' CLASS B', ' CLASS C',
                           ' CL A', ' CL B', ' CL C', ' SHS', ' COM', ' DEL', ' NEW',
                           ' CAP STK', ' COM STK']:
                clean = name_upper
                if clean.endswith(suffix):
                    clean = clean[:len(clean)-len(suffix)].strip()
                ticker = name_to_ticker.get(clean)
                if ticker:
                    break

        if ticker:
            cursor.execute('UPDATE f13_holdings SET ticker = %s WHERE cusip = %s AND ticker IS NULL',
                           (ticker, cusip))
            cursor.execute('''
                INSERT INTO cusip_ticker_map (cusip, ticker, company_name, last_verified)
                VALUES (%s, %s, %s, NOW())
                ON CONFLICT (cusip) DO UPDATE SET ticker = EXCLUDED.ticker, last_verified = NOW()
            ''', (cusip, ticker, name))
            mapped += 1

    conn.commit()
    cursor.close()
    conn.close()

    print(f"Mapped {mapped} CUSIPs to tickers ({len(unmapped) - mapped} still unmapped)")
    return mapped


def initialize_hedge_funds(funds: Dict[str, str] = None):
    """
    Initialize the hedge fund managers table with known funds.

    Args:
        funds: Dictionary mapping CIK to fund name
    """
    if funds is None:
        funds = MAJOR_HEDGE_FUNDS

    conn = get_db_connection()
    cursor = conn.cursor()

    for cik, name in funds.items():
        cursor.execute("""
            INSERT INTO hedge_fund_managers (cik, name)
            VALUES (%s, %s)
            ON CONFLICT (cik) DO UPDATE SET
                name = EXCLUDED.name,
                last_updated = NOW()
        """, (cik, name))

    conn.commit()
    cursor.close()
    conn.close()

    print(f"Initialized {len(funds)} hedge fund managers")


def fetch_and_store_13f(cik: str, max_quarters: int = 8) -> int:
    """
    Fetch and store 13F filings for a specific fund.

    Args:
        cik: SEC CIK number
        max_quarters: Maximum number of quarterly filings to fetch

    Returns:
        Number of filings processed
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Get existing filings to avoid duplicates
    cursor.execute(
        "SELECT accession_number FROM f13_filings WHERE cik = %s",
        (cik.lstrip('0').zfill(10),)
    )
    existing = {row[0] for row in cursor.fetchall()}

    # Fetch filing list from SEC
    filings = get_company_filings(cik, '13F-HR', count=max_quarters * 2)

    processed = 0
    for filing in filings:
        accession = filing['accession_number']
        if accession in existing:
            continue

        print(f"  Processing {filing['filing_date']} ({accession})...")

        # Fetch and parse filing content
        content = fetch_filing_content(cik, accession)
        if not content:
            continue

        _, holdings = parse_13f_xml(content)
        if not holdings:
            print(f"    No holdings found")
            continue

        # Calculate report date and quarter
        report_date = get_report_date_from_filing(filing['filing_date'])
        report_quarter = get_quarter_from_date(report_date)

        # Insert filing record (value in XML is already in dollars for newer filings)
        total_value = sum(h.get('market_value', 0) for h in holdings)
        cursor.execute("""
            INSERT INTO f13_filings
            (cik, accession_number, filing_date, report_date, report_quarter,
             total_value, total_holdings, form_type, is_amendment)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            cik.lstrip('0').zfill(10),
            accession,
            filing['filing_date'],
            report_date,
            report_quarter,
            total_value,
            len(holdings),
            filing['form_type'],
            filing['is_amendment']
        ))

        filing_id = cursor.fetchone()[0]

        # Insert holdings
        for holding in holdings:
            ticker = cusip_to_ticker(holding['cusip'], conn)

            cursor.execute("""
                INSERT INTO f13_holdings
                (filing_id, cik, report_date, cusip, ticker, issuer_name,
                 security_class, shares_held, market_value,
                 sole_voting_authority, shared_voting_authority, no_voting_authority,
                 investment_discretion)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                filing_id,
                cik.lstrip('0').zfill(10),
                report_date,
                holding['cusip'],
                ticker,
                holding['issuer_name'],
                holding.get('security_class', ''),
                holding['shares_held'],
                holding['market_value'],  # Value already in dollars
                holding.get('sole_voting_authority'),
                holding.get('shared_voting_authority'),
                holding.get('no_voting_authority'),
                holding.get('investment_discretion')
            ))

        conn.commit()
        processed += 1
        print(f"    Stored {len(holdings)} holdings")

        if processed >= max_quarters:
            break

    cursor.close()
    conn.close()

    return processed


def calculate_position_changes():
    """
    Calculate quarter-over-quarter position changes for all holdings.
    Updates the change tracking columns in f13_holdings.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Update position changes for each fund/stock combination
    cursor.execute("""
        WITH prev_holdings AS (
            SELECT
                h.id,
                h.cik,
                h.cusip,
                h.report_date,
                h.shares_held,
                h.market_value,
                LAG(h.shares_held) OVER (
                    PARTITION BY h.cik, h.cusip
                    ORDER BY h.report_date
                ) as prev_shares,
                LAG(h.market_value) OVER (
                    PARTITION BY h.cik, h.cusip
                    ORDER BY h.report_date
                ) as prev_value
            FROM f13_holdings h
        )
        UPDATE f13_holdings h
        SET
            prev_shares = p.prev_shares,
            shares_change = h.shares_held - COALESCE(p.prev_shares, 0),
            shares_change_pct = CASE
                WHEN p.prev_shares > 0 THEN
                    LEAST(GREATEST(
                        (h.shares_held - p.prev_shares)::NUMERIC / p.prev_shares,
                        -999999.9999
                    ), 999999.9999)
                ELSE NULL
            END,
            prev_value = p.prev_value,
            value_change = h.market_value - COALESCE(p.prev_value, 0),
            value_change_pct = CASE
                WHEN p.prev_value > 0 THEN
                    LEAST(GREATEST(
                        (h.market_value - p.prev_value) / p.prev_value,
                        -999999.9999
                    ), 999999.9999)
                ELSE NULL
            END,
            position_type = CASE
                WHEN p.prev_shares IS NULL THEN 'NEW'
                WHEN h.shares_held > p.prev_shares * 1.01 THEN 'INCREASED'
                WHEN h.shares_held < p.prev_shares * 0.99 THEN 'DECREASED'
                ELSE 'UNCHANGED'
            END
        FROM prev_holdings p
        WHERE h.id = p.id
    """)

    conn.commit()

    # Mark sold positions: if a holding has no next quarter entry, and it's not
    # the most recent filing for that fund, it was likely sold
    cursor.execute("""
        WITH holding_sequence AS (
            SELECT
                id, cik, cusip, report_date,
                LEAD(report_date) OVER (
                    PARTITION BY cik, cusip
                    ORDER BY report_date
                ) as next_report_date,
                MAX(report_date) OVER (PARTITION BY cik) as max_report_date
            FROM f13_holdings
        )
        UPDATE f13_holdings h
        SET position_type = 'SOLD'
        FROM holding_sequence s
        WHERE h.id = s.id
        AND s.next_report_date IS NULL
        AND s.report_date < s.max_report_date
        AND h.position_type != 'SOLD'
    """)

    conn.commit()
    cursor.close()
    conn.close()

    print("Position changes calculated")


def calculate_stock_aggregates(report_quarter: str = None):
    """
    Calculate aggregate statistics for each stock across all funds.

    Args:
        report_quarter: Specific quarter to calculate (e.g., 'Q4 2024')
                       If None, calculates for all quarters
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    quarter_filter = ""
    params = []
    if report_quarter:
        quarter_filter = "WHERE f.report_quarter = %s"
        params.append(report_quarter)

    # Clear existing aggregates for recalculation
    if report_quarter:
        cursor.execute("DELETE FROM f13_stock_aggregates WHERE report_quarter = %s", (report_quarter,))
    else:
        cursor.execute("DELETE FROM f13_stock_aggregates")
    conn.commit()

    # Calculate aggregates - group by ticker (combining different CUSIPs for same ticker)
    cursor.execute(f"""
        INSERT INTO f13_stock_aggregates (
            report_quarter, ticker, cusip,
            total_funds_holding, total_shares_held, total_market_value,
            avg_position_size, funds_initiated, funds_increased,
            funds_decreased, funds_sold, net_shares_change,
            institutional_sentiment
        )
        SELECT
            f.report_quarter,
            COALESCE(h.ticker, h.cusip) as ticker,
            MIN(h.cusip) as cusip,
            COUNT(DISTINCT h.cik) as total_funds_holding,
            SUM(h.shares_held) as total_shares_held,
            SUM(h.market_value) as total_market_value,
            AVG(h.market_value) as avg_position_size,
            COUNT(*) FILTER (WHERE h.position_type = 'NEW') as funds_initiated,
            COUNT(*) FILTER (WHERE h.position_type = 'INCREASED') as funds_increased,
            COUNT(*) FILTER (WHERE h.position_type = 'DECREASED') as funds_decreased,
            COUNT(*) FILTER (WHERE h.position_type = 'SOLD') as funds_sold,
            SUM(COALESCE(h.shares_change, 0)) as net_shares_change,
            CASE
                WHEN COUNT(DISTINCT h.cik) > 0 THEN
                    (COUNT(*) FILTER (WHERE h.position_type IN ('NEW', 'INCREASED'))
                     - COUNT(*) FILTER (WHERE h.position_type IN ('DECREASED', 'SOLD')))::NUMERIC
                    / COUNT(DISTINCT h.cik)
                ELSE 0
            END as institutional_sentiment
        FROM f13_holdings h
        JOIN f13_filings f ON h.filing_id = f.id
        {quarter_filter}
        GROUP BY f.report_quarter, COALESCE(h.ticker, h.cusip)
    """, params)

    conn.commit()

    # Calculate quarter-over-quarter changes
    cursor.execute("""
        WITH prev_quarter AS (
            SELECT
                a.ticker,
                a.report_quarter,
                a.total_funds_holding,
                LAG(a.total_funds_holding) OVER (
                    PARTITION BY a.ticker ORDER BY a.report_quarter
                ) as prev_funds_holding,
                a.net_shares_change,
                LAG(a.total_shares_held) OVER (
                    PARTITION BY a.ticker ORDER BY a.report_quarter
                ) as prev_total_shares
            FROM f13_stock_aggregates a
        )
        UPDATE f13_stock_aggregates s
        SET
            prev_funds_holding = p.prev_funds_holding,
            net_shares_change_pct = CASE
                WHEN p.prev_total_shares > 0 THEN
                    s.net_shares_change::NUMERIC / p.prev_total_shares
                ELSE NULL
            END
        FROM prev_quarter p
        WHERE s.ticker = p.ticker
        AND s.report_quarter = p.report_quarter
    """)

    conn.commit()

    # Calculate percentage of tracked funds holding
    cursor.execute("""
        WITH total_funds AS (
            SELECT COUNT(*) as fund_count
            FROM hedge_fund_managers
            WHERE is_tracked = TRUE
        )
        UPDATE f13_stock_aggregates
        SET pct_funds_holding = total_funds_holding::NUMERIC / NULLIF((SELECT fund_count FROM total_funds), 0)
    """)

    conn.commit()
    cursor.close()
    conn.close()

    print(f"Stock aggregates calculated for {report_quarter or 'all quarters'}")


def fetch_all_tracked_funds(max_quarters: int = 8):
    """Fetch 13F filings for all tracked hedge funds."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT cik, name FROM hedge_fund_managers WHERE is_tracked = TRUE
    """)
    funds = cursor.fetchall()
    cursor.close()
    conn.close()

    print(f"\n{'='*60}")
    print(f"FETCHING 13F FILINGS FOR {len(funds)} FUNDS")
    print(f"{'='*60}\n")

    total_filings = 0
    for cik, name in funds:
        print(f"\n{name} (CIK: {cik})")
        filings = fetch_and_store_13f(cik, max_quarters)
        total_filings += filings
        print(f"  Processed {filings} filings")

    print(f"\n{'='*60}")
    print(f"Total filings processed: {total_filings}")

    # Calculate changes and aggregates
    print("\nCalculating position changes...")
    calculate_position_changes()

    print("Calculating stock aggregates...")
    calculate_stock_aggregates()


# Query functions for analysis

def get_stock_institutional_ownership(ticker: str, quarters: int = 8) -> pd.DataFrame:
    """
    Get institutional ownership history for a stock.

    Args:
        ticker: Stock ticker symbol
        quarters: Number of quarters of history

    Returns:
        DataFrame with quarterly institutional ownership data
    """
    conn = get_db_connection()

    query = """
        SELECT
            report_quarter,
            total_funds_holding,
            total_shares_held,
            total_market_value,
            funds_initiated,
            funds_increased,
            funds_decreased,
            funds_sold,
            net_shares_change,
            net_shares_change_pct,
            institutional_sentiment,
            pct_funds_holding
        FROM f13_stock_aggregates
        WHERE ticker = %s
        ORDER BY report_quarter DESC
        LIMIT %s
    """

    df = pd.read_sql(query, conn, params=(ticker, quarters))
    conn.close()

    return df


def get_top_institutional_holdings(report_quarter: str, min_funds: int = 5) -> pd.DataFrame:
    """
    Get stocks with the most institutional support in a quarter.

    Args:
        report_quarter: Quarter to analyze (e.g., 'Q4 2024')
        min_funds: Minimum number of funds holding

    Returns:
        DataFrame of top holdings
    """
    conn = get_db_connection()

    query = """
        SELECT
            ticker,
            total_funds_holding,
            total_market_value,
            institutional_sentiment,
            pct_funds_holding,
            net_shares_change_pct
        FROM f13_stock_aggregates
        WHERE report_quarter = %s
        AND total_funds_holding >= %s
        ORDER BY total_funds_holding DESC, institutional_sentiment DESC
        LIMIT 100
    """

    df = pd.read_sql(query, conn, params=(report_quarter, min_funds))
    conn.close()

    return df


def get_institutional_sentiment_changes(
    from_quarter: str,
    to_quarter: str,
    min_change: float = 0.1
) -> pd.DataFrame:
    """
    Get stocks with significant institutional sentiment changes.

    Args:
        from_quarter: Starting quarter
        to_quarter: Ending quarter
        min_change: Minimum sentiment change threshold

    Returns:
        DataFrame of stocks with sentiment changes
    """
    conn = get_db_connection()

    query = """
        WITH sentiment_change AS (
            SELECT
                a1.ticker,
                a1.total_funds_holding as current_funds,
                a2.total_funds_holding as prev_funds,
                a1.institutional_sentiment as current_sentiment,
                a2.institutional_sentiment as prev_sentiment,
                a1.institutional_sentiment - a2.institutional_sentiment as sentiment_change,
                a1.net_shares_change_pct
            FROM f13_stock_aggregates a1
            JOIN f13_stock_aggregates a2 ON
                a1.ticker = a2.ticker AND
                a2.report_quarter = %s
            WHERE a1.report_quarter = %s
        )
        SELECT *
        FROM sentiment_change
        WHERE ABS(sentiment_change) >= %s
        ORDER BY sentiment_change DESC
    """

    df = pd.read_sql(query, conn, params=(from_quarter, to_quarter, min_change))
    conn.close()

    return df


def get_fund_activity(cik: str, quarters: int = 4) -> pd.DataFrame:
    """
    Get a fund's trading activity across recent quarters.

    Args:
        cik: Fund CIK number
        quarters: Number of quarters

    Returns:
        DataFrame of fund's positions and changes
    """
    conn = get_db_connection()

    query = """
        SELECT
            f.report_quarter,
            COALESCE(h.ticker, h.issuer_name) as security,
            h.shares_held,
            h.market_value,
            h.position_type,
            h.shares_change,
            h.shares_change_pct
        FROM f13_holdings h
        JOIN f13_filings f ON h.filing_id = f.id
        WHERE h.cik = %s
        ORDER BY f.report_quarter DESC, h.market_value DESC
    """

    df = pd.read_sql(query, conn, params=(cik.lstrip('0').zfill(10),))
    conn.close()

    return df


def discover_13f_filers(year: int = None, quarter: int = None) -> List[Dict]:
    """
    Discover all 13F-HR filers from SEC EDGAR's full-index for a given quarter.

    Downloads the quarterly master.idx file (pipe-delimited) and extracts
    all unique 13F-HR filers.

    Args:
        year: Year to search (default: most recent completed quarter)
        quarter: Quarter number 1-4 (default: most recent completed quarter)

    Returns:
        List of dicts with 'cik', 'name', 'filing_date', 'accession_path' keys
    """
    if year is None or quarter is None:
        year, quarter = get_current_quarter()

    def fetch_index(y, q):
        idx_url = f"https://www.sec.gov/Archives/edgar/full-index/{y}/QTR{q}/master.idx"
        print(f"Fetching 13F filer index from {idx_url}...")
        response = sec_request(idx_url)
        return response.text

    try:
        content = fetch_index(year, quarter)
    except Exception as e:
        print(f"Error fetching full-index for {year} QTR{quarter}: {e}")
        # Try previous quarter
        if quarter == 1:
            prev_year, prev_q = year - 1, 4
        else:
            prev_year, prev_q = year, quarter - 1
        print(f"Trying previous quarter: {prev_year} QTR{prev_q}")
        try:
            content = fetch_index(prev_year, prev_q)
        except Exception as e2:
            print(f"Error fetching previous quarter index: {e2}")
            return []

    # Parse the pipe-delimited master.idx file
    # Format: CIK|Company Name|Form Type|Date Filed|Filename
    # First ~10 lines are headers (title, column names, dashes)
    filers = []
    seen_ciks = set()
    in_data = False

    for line in content.split('\n'):
        line = line.strip()
        if not line:
            continue

        # Detect end of header (dashed separator line)
        if line.startswith('---'):
            in_data = True
            continue
        if not in_data:
            continue

        # Parse pipe-delimited fields
        parts = line.split('|')
        if len(parts) < 5:
            continue

        try:
            cik = parts[0].strip()
            company_name = parts[1].strip()
            form_type = parts[2].strip()
            date_filed = parts[3].strip()
            filename = parts[4].strip()

            # Only keep 13F-HR filings (not amendments)
            if form_type != '13F-HR':
                continue

            # Deduplicate by CIK (a fund may file multiple times in a quarter)
            if cik in seen_ciks:
                continue
            seen_ciks.add(cik)

            filers.append({
                'cik': cik.zfill(10),
                'name': company_name,
                'filing_date': date_filed,
                'accession_path': filename
            })

        except (IndexError, ValueError):
            continue

    print(f"Found {len(filers)} unique 13F-HR filers in {year} QTR{quarter}")
    return filers


def get_filer_portfolio_value(cik: str) -> Optional[int]:
    """
    Get the total portfolio value from a filer's most recent 13F filing.

    Uses the SEC submissions API to check the filing metadata, then
    fetches the cover page to extract the total value.

    Args:
        cik: SEC CIK number (padded to 10 digits)

    Returns:
        Total portfolio value in dollars, or None if unavailable
    """
    try:
        # Use submissions API to get filing details
        url = f"{SEC_BASE_URL}/submissions/CIK{cik.zfill(10)}.json"
        response = sec_request(url)
        data = response.json()

        recent = data.get('filings', {}).get('recent', {})
        if not recent:
            return None

        forms = recent.get('form', [])
        accessions = recent.get('accessionNumber', [])

        # Find most recent 13F-HR filing
        accession = None
        for i, form in enumerate(forms):
            if form == '13F-HR':
                accession = accessions[i]
                break

        if not accession:
            return None

        # Fetch the filing content and sum up holdings values
        content = fetch_filing_content(cik, accession)
        if not content:
            return None

        _, holdings = parse_13f_xml(content)
        if not holdings:
            return None

        total_value = sum(h.get('market_value', 0) for h in holdings)
        return total_value

    except Exception as e:
        return None


def discover_top_filers(n: int = 200, year: int = None, quarter: int = None) -> List[Dict]:
    """
    Discover the top N 13F filers ranked by total portfolio value.

    Two-pass approach:
    1. Get all 13F filers from the quarterly index
    2. For each filer, get their total portfolio value from the most recent filing
    3. Rank by value and return top N

    Args:
        n: Number of top filers to return (default: 200)
        year: Year for the quarterly index
        quarter: Quarter number for the index

    Returns:
        List of dicts with 'cik', 'name', 'total_value' sorted descending by value
    """
    # Step 1: Discover all filers
    filers = discover_13f_filers(year, quarter)
    if not filers:
        print("No filers found")
        return []

    print(f"\nFetching portfolio values for {len(filers)} filers...")
    print("This will take a while due to SEC rate limiting (~6 req/sec)...")
    print(f"Estimated time: ~{len(filers) * 2 // 60} minutes\n")

    # Step 2: Get portfolio value for each filer
    # We batch this with progress reporting
    valued_filers = []
    errors = 0

    for i, filer in enumerate(filers):
        if (i + 1) % 50 == 0:
            print(f"  Progress: {i+1}/{len(filers)} filers checked "
                  f"({len(valued_filers)} with values, {errors} errors)")

        try:
            # Quick check: use submissions API to get the most recent 13F
            url = f"{SEC_BASE_URL}/submissions/CIK{filer['cik']}.json"
            response = sec_request(url)
            data = response.json()

            recent = data.get('filings', {}).get('recent', {})
            forms = recent.get('form', [])
            accessions = recent.get('accessionNumber', [])
            primary_docs = recent.get('primaryDocument', [])

            # Find most recent 13F-HR
            accession = None
            primary_doc = None
            for j, form in enumerate(forms):
                if form == '13F-HR':
                    accession = accessions[j]
                    primary_doc = primary_docs[j] if j < len(primary_docs) else None
                    break

            if not accession:
                continue

            # Try to get total value from the primary document (cover page)
            # The cover page XML contains <tableValueTotal> with the total value
            cik_int = str(int(filer['cik'].lstrip('0')))
            accession_clean = accession.replace('-', '')
            cover_url = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_clean}/{primary_doc}"

            try:
                cover_response = sec_request(cover_url)
                cover_text = cover_response.text

                # Extract total value from cover page XML/HTML
                # Look for <tableValueTotal> or similar patterns
                value_match = re.search(
                    r'<(?:ns\d+:)?tableValueTotal[^>]*>\s*(\d+)\s*</(?:ns\d+:)?tableValueTotal>',
                    cover_text, re.IGNORECASE
                )
                if value_match:
                    # Value in thousands in the cover page
                    total_value = int(value_match.group(1)) * 1000
                else:
                    # Try alternate patterns
                    value_match = re.search(
                        r'table\s*value\s*total[^<]*<[^>]*>[\s$]*([0-9,]+)',
                        cover_text, re.IGNORECASE
                    )
                    if value_match:
                        total_value = int(value_match.group(1).replace(',', '')) * 1000
                    else:
                        # Last resort: sum up the info table holdings
                        content = fetch_filing_content(filer['cik'], accession)
                        if content:
                            _, holdings = parse_13f_xml(content)
                            total_value = sum(h.get('market_value', 0) for h in holdings)
                        else:
                            continue

                if total_value > 0:
                    # Update name from submissions data if available
                    entity_name = data.get('name', filer['name'])
                    valued_filers.append({
                        'cik': filer['cik'],
                        'name': entity_name,
                        'total_value': total_value
                    })

            except Exception:
                # If cover page fails, skip - we'll catch the biggest ones anyway
                errors += 1
                continue

        except Exception as e:
            errors += 1
            continue

    print(f"\nCompleted: {len(valued_filers)} filers with portfolio values, {errors} errors")

    # Step 3: Sort by total value and take top N
    valued_filers.sort(key=lambda x: x['total_value'], reverse=True)
    top_filers = valued_filers[:n]

    if top_filers:
        print(f"\nTop {min(n, len(top_filers))} 13F filers by portfolio value:")
        print(f"{'Rank':<5} {'Name':<45} {'Portfolio Value':>20}")
        print("-" * 72)
        for i, f in enumerate(top_filers[:20], 1):
            value_str = f"${f['total_value']:,.0f}"
            print(f"{i:<5} {f['name'][:44]:<45} {value_str:>20}")
        if len(top_filers) > 20:
            print(f"  ... and {len(top_filers) - 20} more")

    return top_filers


def populate_top_filers(n: int = 200, year: int = None, quarter: int = None):
    """
    Discover top N 13F filers and populate the hedge_fund_managers table.

    This replaces the static MAJOR_HEDGE_FUNDS approach with dynamic discovery.
    Existing tracked funds are preserved; new ones are added with is_tracked=TRUE.

    Args:
        n: Number of top filers to track (default: 200)
        year: Year for quarterly index
        quarter: Quarter number for index
    """
    top_filers = discover_top_filers(n, year, quarter)
    if not top_filers:
        print("No filers discovered. Check network connectivity and SEC EDGAR availability.")
        return

    conn = get_db_connection()
    cursor = conn.cursor()

    added = 0
    updated = 0

    for filer in top_filers:
        cursor.execute("""
            INSERT INTO hedge_fund_managers (cik, name, is_tracked)
            VALUES (%s, %s, TRUE)
            ON CONFLICT (cik) DO UPDATE SET
                name = EXCLUDED.name,
                is_tracked = TRUE,
                last_updated = NOW()
            RETURNING (xmax = 0) as is_new
        """, (filer['cik'], filer['name']))

        result = cursor.fetchone()
        if result and result[0]:
            added += 1
        else:
            updated += 1

    # Untrack funds that fell out of the top N
    # (but don't delete them - keep historical data)
    top_ciks = [f['cik'] for f in top_filers]
    if top_ciks:
        cursor.execute("""
            UPDATE hedge_fund_managers
            SET is_tracked = FALSE
            WHERE cik NOT IN %s
            AND is_tracked = TRUE
        """, (tuple(top_ciks),))
        untracked = cursor.rowcount
    else:
        untracked = 0

    conn.commit()
    cursor.close()
    conn.close()

    print(f"\nPopulated hedge_fund_managers: {added} added, {updated} updated, {untracked} untracked")
    print(f"Total tracked funds: {len(top_filers)}")


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Fetch SEC 13F filings')
    parser.add_argument('--init', action='store_true', help='Initialize hedge fund managers from hardcoded list')
    parser.add_argument('--discover', type=int, nargs='?', const=200, metavar='N',
                        help='Discover and track top N 13F filers by portfolio value (default: 200)')
    parser.add_argument('--fetch', action='store_true', help='Fetch 13F filings for all tracked funds')
    parser.add_argument('--cik', help='Specific CIK to fetch')
    parser.add_argument('--quarters', type=int, default=8, help='Number of quarters to fetch')
    parser.add_argument('--aggregate', action='store_true', help='Calculate aggregates only')
    parser.add_argument('--map-cusips', action='store_true', help='Map CUSIPs to tickers')
    parser.add_argument('--stock', help='Get institutional data for specific stock')

    args = parser.parse_args()

    if args.init:
        initialize_hedge_funds()

    if args.discover is not None:
        populate_top_filers(n=args.discover)

    if args.fetch:
        if args.cik:
            print(f"Fetching filings for CIK {args.cik}")
            fetch_and_store_13f(args.cik, args.quarters)
        else:
            fetch_all_tracked_funds(args.quarters)

    if args.map_cusips:
        batch_map_cusips_to_tickers()

    if args.aggregate:
        calculate_position_changes()
        calculate_stock_aggregates()

    if args.stock:
        df = get_stock_institutional_ownership(args.stock)
        print(f"\nInstitutional ownership for {args.stock}:")
        print(df.to_string())
