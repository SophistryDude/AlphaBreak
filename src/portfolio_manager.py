"""
Portfolio Manager Module
========================
Manages the theoretical paper trading portfolio for validating prediction model effectiveness.

Starting balance: $100,000 USD
Allocation: 75% long-term investing, 25% intra-day swing trading

Position Sizing Rules:
- Max 5% of portfolio per individual stock position
- Max 2% per options contract
- Maintain 20% cash reserve minimum
- Stop-loss: 7% below entry for stocks, 50% for options

Usage:
    # Get current portfolio state
    python -m src.portfolio_manager --status

    # Execute a buy signal
    python -m src.portfolio_manager --buy AAPL --quantity 10 --price 185.50 --type long_term

    # Process pending signals from DAG
    python -m src.portfolio_manager --process-signals

    # Calculate daily P&L and create snapshot
    python -m src.portfolio_manager --daily-snapshot
"""

import argparse
import os
import sys
import logging
import json
from datetime import datetime, date, timedelta
from typing import List, Dict, Tuple, Optional, Any
from decimal import Decimal
import psycopg2
from psycopg2.extras import RealDictCursor, execute_values
import uuid

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database connection configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', '5433')),
    'database': os.getenv('DB_NAME', 'trading_data'),
    'user': os.getenv('DB_USER', 'trading'),
    'password': os.getenv('DB_PASSWORD', 'trading123'),
    'sslmode': os.getenv('DB_SSLMODE', 'prefer')
}

# Portfolio configuration
PORTFOLIO_CONFIG = {
    'starting_balance': 100000.00,
    'long_term_allocation': 0.75,      # 75%
    'swing_allocation': 0.25,          # 25%
    'max_position_pct': 0.05,          # 5% max per stock position
    'max_options_pct': 0.02,           # 2% max per options contract
    'min_cash_reserve_pct': 0.20,      # 20% minimum cash reserve
    'stock_stop_loss_pct': 0.07,       # 7% stop-loss for stocks
    'options_stop_loss_pct': 0.50,     # 50% stop-loss for options
}


def get_db_connection():
    """Create database connection."""
    return psycopg2.connect(**DB_CONFIG)


def decimal_to_float(obj):
    """Convert Decimal objects to float for JSON serialization."""
    if isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, date):
        return obj.isoformat()
    elif isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, uuid.UUID):
        return str(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


class PortfolioManager:
    """Manages the theoretical portfolio state and operations."""

    def __init__(self, conn=None):
        self.conn = conn or get_db_connection()
        self.config = PORTFOLIO_CONFIG

    def get_account(self) -> Dict[str, Any]:
        """Get current account state."""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM portfolio_account LIMIT 1")
            account = cur.fetchone()
            if account:
                return dict(account)
            return None

    def get_cash_balance(self) -> float:
        """Get current cash balance."""
        account = self.get_account()
        return float(account['cash_balance']) if account else 0.0

    def get_holdings(self, holding_type: str = None) -> List[Dict]:
        """Get current holdings, optionally filtered by type."""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            if holding_type:
                cur.execute(
                    "SELECT * FROM portfolio_holdings WHERE holding_type = %s ORDER BY market_value DESC",
                    (holding_type,)
                )
            else:
                cur.execute("SELECT * FROM portfolio_holdings ORDER BY holding_type, market_value DESC")
            return [dict(row) for row in cur.fetchall()]

    def get_holding(self, ticker: str, holding_type: str, asset_type: str = 'stock') -> Optional[Dict]:
        """Get a specific holding."""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM portfolio_holdings
                WHERE ticker = %s AND holding_type = %s AND asset_type = %s
            """, (ticker, holding_type, asset_type))
            row = cur.fetchone()
            return dict(row) if row else None

    def get_portfolio_value(self) -> Dict[str, float]:
        """Calculate total portfolio value breakdown."""
        cash = self.get_cash_balance()
        holdings = self.get_holdings()

        long_term_value = sum(
            float(h['market_value'] or 0)
            for h in holdings if h['holding_type'] == 'long_term'
        )
        swing_value = sum(
            float(h['market_value'] or 0)
            for h in holdings if h['holding_type'] == 'swing'
        )

        total_holdings = long_term_value + swing_value
        total_value = cash + total_holdings

        return {
            'total_value': total_value,
            'cash_balance': cash,
            'holdings_value': total_holdings,
            'long_term_value': long_term_value,
            'swing_value': swing_value,
            'long_term_pct': long_term_value / total_value if total_value > 0 else 0,
            'swing_pct': swing_value / total_value if total_value > 0 else 0,
            'cash_pct': cash / total_value if total_value > 0 else 0,
        }

    def validate_trade(self, action: str, ticker: str, quantity: float, price: float,
                       holding_type: str, asset_type: str = 'stock') -> Tuple[bool, str]:
        """
        Validate if a trade can be executed based on portfolio rules.
        Returns (is_valid, reason).
        """
        portfolio = self.get_portfolio_value()
        total_value = portfolio['total_value']
        cash = portfolio['cash_balance']
        trade_value = quantity * price

        # Check if selling
        if action in ['sell', 'sell_to_close']:
            holding = self.get_holding(ticker, holding_type, asset_type)
            if not holding:
                return False, f"No {holding_type} position in {ticker} to sell"
            if float(holding['quantity']) < quantity:
                return False, f"Insufficient shares: have {holding['quantity']}, trying to sell {quantity}"
            return True, "Valid sell order"

        # Buying checks
        # 1. Check cash availability
        min_cash_reserve = total_value * self.config['min_cash_reserve_pct']
        available_cash = cash - min_cash_reserve

        if trade_value > available_cash:
            return False, f"Insufficient cash: need ${trade_value:.2f}, have ${available_cash:.2f} available (maintaining 20% reserve)"

        # 2. Check position size limit
        max_position = self.config['max_options_pct'] if asset_type == 'option' else self.config['max_position_pct']
        max_position_value = total_value * max_position

        # Get existing position value
        existing_holding = self.get_holding(ticker, holding_type, asset_type)
        existing_value = float(existing_holding['market_value'] or 0) if existing_holding else 0

        if existing_value + trade_value > max_position_value:
            return False, f"Position too large: max {max_position * 100}% = ${max_position_value:.2f}, would be ${existing_value + trade_value:.2f}"

        # 3. Check allocation limits
        if holding_type == 'long_term':
            current_allocation = portfolio['long_term_value']
            max_allocation = total_value * self.config['long_term_allocation']
        else:  # swing
            current_allocation = portfolio['swing_value']
            max_allocation = total_value * self.config['swing_allocation']

        if current_allocation + trade_value > max_allocation * 1.1:  # 10% buffer
            return False, f"Would exceed {holding_type} allocation limit"

        return True, "Valid buy order"

    def execute_trade(self, action: str, ticker: str, quantity: float, price: float,
                      holding_type: str, asset_type: str = 'stock',
                      signal_source: str = None, signal_details: dict = None,
                      option_type: str = None, strike_price: float = None,
                      expiration_date: date = None) -> Dict[str, Any]:
        """
        Execute a trade and update portfolio state.
        Returns transaction details.
        """
        # Validate first
        is_valid, reason = self.validate_trade(action, ticker, quantity, price, holding_type, asset_type)
        if not is_valid:
            return {'success': False, 'error': reason}

        trade_value = quantity * price
        transaction_id = uuid.uuid4()

        with self.conn.cursor() as cur:
            if action in ['buy', 'buy_to_open']:
                # Deduct cash
                cur.execute(
                    "UPDATE portfolio_account SET cash_balance = cash_balance - %s, updated_at = NOW()",
                    (trade_value,)
                )

                # Update or create holding
                existing = self.get_holding(ticker, holding_type, asset_type)

                if existing:
                    # Average down/up
                    new_quantity = float(existing['quantity']) + quantity
                    new_cost_basis = (
                        (float(existing['avg_cost_basis']) * float(existing['quantity'])) +
                        (price * quantity)
                    ) / new_quantity

                    cur.execute("""
                        UPDATE portfolio_holdings
                        SET quantity = %s, avg_cost_basis = %s, current_price = %s,
                            market_value = %s * %s, updated_at = NOW()
                        WHERE ticker = %s AND holding_type = %s AND asset_type = %s
                    """, (new_quantity, new_cost_basis, price, new_quantity, price,
                          ticker, holding_type, asset_type))
                else:
                    # New position
                    stop_loss = price * (1 - (self.config['options_stop_loss_pct'] if asset_type == 'option' else self.config['stock_stop_loss_pct']))

                    cur.execute("""
                        INSERT INTO portfolio_holdings
                        (ticker, holding_type, asset_type, quantity, avg_cost_basis, current_price,
                         market_value, entry_date, entry_signal, stop_loss_price, option_type,
                         strike_price, expiration_date)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), %s, %s, %s, %s, %s)
                    """, (ticker, holding_type, asset_type, quantity, price, price,
                          trade_value, signal_source, stop_loss, option_type, strike_price, expiration_date))

            else:  # sell, sell_to_close
                existing = self.get_holding(ticker, holding_type, asset_type)
                cost_basis = float(existing['avg_cost_basis'])
                realized_pnl = (price - cost_basis) * quantity
                realized_pnl_pct = (price - cost_basis) / cost_basis if cost_basis > 0 else 0

                # Add cash
                cur.execute(
                    "UPDATE portfolio_account SET cash_balance = cash_balance + %s, updated_at = NOW()",
                    (trade_value,)
                )

                new_quantity = float(existing['quantity']) - quantity

                if new_quantity <= 0.0001:  # Close position
                    cur.execute(
                        "DELETE FROM portfolio_holdings WHERE ticker = %s AND holding_type = %s AND asset_type = %s",
                        (ticker, holding_type, asset_type)
                    )
                else:
                    cur.execute("""
                        UPDATE portfolio_holdings
                        SET quantity = %s, market_value = %s * %s, updated_at = NOW()
                        WHERE ticker = %s AND holding_type = %s AND asset_type = %s
                    """, (new_quantity, new_quantity, price, ticker, holding_type, asset_type))

            # Record transaction
            cur.execute("""
                INSERT INTO portfolio_transactions
                (transaction_id, ticker, action, holding_type, asset_type, quantity, price,
                 total_value, signal_source, signal_details, option_type, strike_price,
                 expiration_date, realized_pnl, realized_pnl_pct)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                transaction_id, ticker, action, holding_type, asset_type, quantity, price,
                trade_value, signal_source, json.dumps(signal_details) if signal_details else None,
                option_type, strike_price, expiration_date,
                realized_pnl if action in ['sell', 'sell_to_close'] else None,
                realized_pnl_pct if action in ['sell', 'sell_to_close'] else None
            ))

            self.conn.commit()

        return {
            'success': True,
            'transaction_id': str(transaction_id),
            'ticker': ticker,
            'action': action,
            'quantity': quantity,
            'price': price,
            'total_value': trade_value,
            'holding_type': holding_type,
        }

    def update_prices(self, price_updates: Dict[str, float]) -> int:
        """
        Update current prices for holdings and recalculate P&L.
        price_updates: {ticker: current_price}
        Returns count of updated holdings.
        """
        updated = 0
        with self.conn.cursor() as cur:
            for ticker, price in price_updates.items():
                cur.execute("""
                    UPDATE portfolio_holdings
                    SET current_price = %s,
                        market_value = quantity * %s,
                        unrealized_pnl = (quantity * %s) - (quantity * avg_cost_basis),
                        unrealized_pnl_pct = (%s - avg_cost_basis) / avg_cost_basis,
                        updated_at = NOW()
                    WHERE ticker = %s
                """, (price, price, price, price, ticker))
                updated += cur.rowcount
            self.conn.commit()
        return updated

    def check_stop_losses(self) -> List[Dict]:
        """Check if any holdings have hit their stop-loss."""
        triggered = []
        holdings = self.get_holdings()

        for holding in holdings:
            if holding['current_price'] and holding['stop_loss_price']:
                if float(holding['current_price']) <= float(holding['stop_loss_price']):
                    triggered.append({
                        'ticker': holding['ticker'],
                        'holding_type': holding['holding_type'],
                        'current_price': float(holding['current_price']),
                        'stop_loss_price': float(holding['stop_loss_price']),
                        'unrealized_pnl_pct': float(holding['unrealized_pnl_pct'] or 0),
                    })

        return triggered

    def create_daily_snapshot(self) -> Dict:
        """Create a daily performance snapshot."""
        portfolio = self.get_portfolio_value()
        account = self.get_account()
        holdings = self.get_holdings()

        # Get previous snapshot for comparison
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM portfolio_performance
                ORDER BY snapshot_date DESC LIMIT 1
            """)
            prev_snapshot = cur.fetchone()

        prev_value = float(prev_snapshot['total_value']) if prev_snapshot else float(account['starting_balance'])
        daily_pnl = portfolio['total_value'] - prev_value
        daily_pnl_pct = daily_pnl / prev_value if prev_value > 0 else 0

        total_pnl = portfolio['total_value'] - float(account['starting_balance'])
        total_pnl_pct = total_pnl / float(account['starting_balance'])

        # Count positions
        long_term_count = sum(1 for h in holdings if h['holding_type'] == 'long_term')
        swing_count = sum(1 for h in holdings if h['holding_type'] == 'swing')

        # Calculate win rate from transactions
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT
                    COUNT(*) FILTER (WHERE realized_pnl > 0) as wins,
                    COUNT(*) FILTER (WHERE realized_pnl <= 0) as losses
                FROM portfolio_transactions
                WHERE action IN ('sell', 'sell_to_close')
            """)
            result = cur.fetchone()
            wins, losses = result[0] or 0, result[1] or 0
            win_rate = wins / (wins + losses) if (wins + losses) > 0 else None

            # Insert snapshot
            cur.execute("""
                INSERT INTO portfolio_performance
                (snapshot_date, total_value, cash_balance, holdings_value,
                 long_term_value, swing_value, daily_pnl, daily_pnl_pct,
                 total_pnl, total_pnl_pct, win_rate, open_positions,
                 long_term_positions, swing_positions)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (snapshot_date) DO UPDATE SET
                    total_value = EXCLUDED.total_value,
                    cash_balance = EXCLUDED.cash_balance,
                    holdings_value = EXCLUDED.holdings_value,
                    long_term_value = EXCLUDED.long_term_value,
                    swing_value = EXCLUDED.swing_value,
                    daily_pnl = EXCLUDED.daily_pnl,
                    daily_pnl_pct = EXCLUDED.daily_pnl_pct,
                    total_pnl = EXCLUDED.total_pnl,
                    total_pnl_pct = EXCLUDED.total_pnl_pct,
                    win_rate = EXCLUDED.win_rate,
                    open_positions = EXCLUDED.open_positions,
                    long_term_positions = EXCLUDED.long_term_positions,
                    swing_positions = EXCLUDED.swing_positions
            """, (
                date.today(), portfolio['total_value'], portfolio['cash_balance'],
                portfolio['holdings_value'], portfolio['long_term_value'],
                portfolio['swing_value'], daily_pnl, daily_pnl_pct,
                total_pnl, total_pnl_pct, win_rate, len(holdings),
                long_term_count, swing_count
            ))
            self.conn.commit()

        return {
            'snapshot_date': date.today().isoformat(),
            'total_value': portfolio['total_value'],
            'daily_pnl': daily_pnl,
            'daily_pnl_pct': daily_pnl_pct,
            'total_pnl': total_pnl,
            'total_pnl_pct': total_pnl_pct,
            'win_rate': win_rate,
            'positions': len(holdings),
        }

    def get_performance_history(self, days: int = 30) -> List[Dict]:
        """Get performance history for the last N days."""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM portfolio_performance
                WHERE snapshot_date >= CURRENT_DATE - INTERVAL '%s days'
                ORDER BY snapshot_date ASC
            """, (days,))
            return [dict(row) for row in cur.fetchall()]

    def get_transactions(self, limit: int = 50, ticker: str = None) -> List[Dict]:
        """Get recent transactions."""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            if ticker:
                cur.execute("""
                    SELECT * FROM portfolio_transactions
                    WHERE ticker = %s
                    ORDER BY executed_at DESC LIMIT %s
                """, (ticker, limit))
            else:
                cur.execute("""
                    SELECT * FROM portfolio_transactions
                    ORDER BY executed_at DESC LIMIT %s
                """, (limit,))
            return [dict(row) for row in cur.fetchall()]

    def add_signal(self, ticker: str, signal_type: str, suggested_action: str,
                   holding_type: str, signal_strength: float = None,
                   signal_price: float = None, source_data: dict = None,
                   expires_hours: int = 24) -> str:
        """Add a signal to the queue for processing."""
        signal_id = uuid.uuid4()
        expires_at = datetime.now() + timedelta(hours=expires_hours)

        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO portfolio_signals
                (signal_id, ticker, signal_type, suggested_action, holding_type,
                 signal_strength, signal_price, source_data, expires_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                signal_id, ticker, signal_type, suggested_action, holding_type,
                signal_strength, signal_price,
                json.dumps(source_data) if source_data else None, expires_at
            ))
            self.conn.commit()

        return str(signal_id)

    def get_pending_signals(self) -> List[Dict]:
        """Get all pending signals that haven't expired."""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM portfolio_signals
                WHERE status = 'pending' AND expires_at > NOW()
                ORDER BY signal_strength DESC NULLS LAST, generated_at ASC
            """)
            return [dict(row) for row in cur.fetchall()]

    def process_signal(self, signal_id: str, current_price: float) -> Dict:
        """Process a signal and execute the trade if valid."""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM portfolio_signals WHERE signal_id = %s", (signal_id,))
            signal = cur.fetchone()

            if not signal:
                return {'success': False, 'error': 'Signal not found'}

            if signal['status'] != 'pending':
                return {'success': False, 'error': f"Signal already {signal['status']}"}

            # Calculate position size
            portfolio = self.get_portfolio_value()
            total_value = portfolio['total_value']

            # Determine quantity based on position sizing rules
            max_position_value = total_value * self.config['max_position_pct']
            quantity = int(max_position_value / current_price)

            if quantity < 1:
                cur.execute("""
                    UPDATE portfolio_signals
                    SET status = 'rejected', rejection_reason = 'Position too expensive', processed_at = NOW()
                    WHERE signal_id = %s
                """, (signal_id,))
                self.conn.commit()
                return {'success': False, 'error': 'Position too expensive for current portfolio size'}

            # Execute the trade
            result = self.execute_trade(
                action=signal['suggested_action'],
                ticker=signal['ticker'],
                quantity=quantity,
                price=current_price,
                holding_type=signal['holding_type'],
                asset_type=signal['asset_type'] or 'stock',
                signal_source=signal['signal_type'],
                signal_details=signal['source_data']
            )

            if result['success']:
                cur.execute("""
                    UPDATE portfolio_signals
                    SET status = 'processed', processed_at = NOW()
                    WHERE signal_id = %s
                """, (signal_id,))
            else:
                cur.execute("""
                    UPDATE portfolio_signals
                    SET status = 'rejected', rejection_reason = %s, processed_at = NOW()
                    WHERE signal_id = %s
                """, (result.get('error'), signal_id))

            self.conn.commit()
            return result

    def get_portfolio_summary(self) -> Dict:
        """Get complete portfolio summary for API/frontend."""
        account = self.get_account()
        portfolio = self.get_portfolio_value()
        holdings = self.get_holdings()
        recent_transactions = self.get_transactions(limit=10)
        watchlist = self.get_watchlist()
        covered_calls = self.get_open_covered_calls()

        return {
            'account': account,
            'portfolio_value': portfolio,
            'holdings': {
                'long_term': [h for h in holdings if h['holding_type'] == 'long_term'],
                'swing': [h for h in holdings if h['holding_type'] == 'swing'],
            },
            'recent_transactions': recent_transactions,
            'watchlist': watchlist,
            'covered_calls': covered_calls,
            'config': self.config,
        }

    # =========================================================================
    # Long-Term Position Management
    # =========================================================================

    def get_watchlist(self, status: str = 'watching') -> List[Dict]:
        """Get tickers on the re-entry watchlist."""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM portfolio_watchlist
                WHERE status = %s
                ORDER BY exit_date DESC
            """, (status,))
            return [dict(row) for row in cur.fetchall()]

    def add_to_watchlist(self, ticker: str, exit_price: float, exit_reason: str,
                         realized_pnl: float, holding: Dict, sector: str = None) -> str:
        """
        Add an exited position to the watchlist for potential re-entry.
        Called when exiting a long-term position due to bearish trend break.
        """
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO portfolio_watchlist
                (ticker, sector, exit_date, exit_price, exit_reason, realized_pnl,
                 target_reentry_price, reentry_signal_type, original_quantity,
                 original_cost_basis, holding_type)
                VALUES (%s, %s, NOW(), %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (ticker, exit_date) DO NOTHING
                RETURNING id
            """, (
                ticker,
                sector,
                exit_price,
                exit_reason,
                realized_pnl,
                exit_price * 0.95,  # Target 5% below exit for re-entry
                'trend_break_bullish',  # Re-enter on bullish trend break
                float(holding.get('quantity', 0)),
                float(holding.get('avg_cost_basis', 0)),
                holding.get('holding_type', 'long_term'),
            ))
            self.conn.commit()
            result = cur.fetchone()
            return result[0] if result else None

    def check_reentry_opportunities(self, trend_signals: List[Dict]) -> List[Dict]:
        """
        Check watchlist against current bullish trend break signals.
        Returns list of re-entry opportunities.
        """
        watchlist = self.get_watchlist(status='watching')
        opportunities = []

        for item in watchlist:
            ticker = item['ticker']
            # Find matching bullish signal
            for signal in trend_signals:
                if (signal['ticker'] == ticker and
                    'bullish' in signal.get('signal_type', '').lower() and
                    signal.get('signal_strength', 0) >= float(item.get('min_signal_strength', 0.80))):

                    opportunities.append({
                        'watchlist_item': item,
                        'signal': signal,
                        'ticker': ticker,
                        'last_exit_price': float(item['exit_price']),
                        'current_price': signal.get('signal_price'),
                        'signal_strength': signal.get('signal_strength'),
                    })
                    break

        return opportunities

    def execute_reentry(self, watchlist_id: int, current_price: float,
                        quantity: int = None) -> Dict:
        """
        Execute a re-entry trade from the watchlist.
        """
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM portfolio_watchlist WHERE id = %s", (watchlist_id,))
            item = cur.fetchone()

            if not item or item['status'] != 'watching':
                return {'success': False, 'error': 'Watchlist item not found or not watching'}

            # Calculate quantity if not provided
            if quantity is None:
                portfolio = self.get_portfolio_value()
                max_position = portfolio['total_value'] * self.config['max_position_pct']
                quantity = int(max_position / current_price)

            if quantity < 1:
                return {'success': False, 'error': 'Position too expensive'}

            # Execute the buy
            result = self.execute_trade(
                action='buy',
                ticker=item['ticker'],
                quantity=quantity,
                price=current_price,
                holding_type=item['holding_type'],
                signal_source='watchlist_reentry',
                signal_details={'watchlist_id': watchlist_id, 'exit_price': float(item['exit_price'])}
            )

            if result['success']:
                # Update watchlist status
                cur.execute("""
                    UPDATE portfolio_watchlist
                    SET status = 'reentry_triggered', reentry_date = NOW(), reentry_price = %s
                    WHERE id = %s
                """, (current_price, watchlist_id))
                self.conn.commit()

            return result

    def close_watchlist_item(self, watchlist_id: int, reason: str = 'closed') -> bool:
        """Close a watchlist item without re-entry."""
        with self.conn.cursor() as cur:
            cur.execute("""
                UPDATE portfolio_watchlist
                SET status = %s, updated_at = NOW()
                WHERE id = %s
            """, (reason, watchlist_id))
            self.conn.commit()
            return cur.rowcount > 0

    # =========================================================================
    # Covered Call Management
    # =========================================================================

    def get_open_covered_calls(self, ticker: str = None) -> List[Dict]:
        """Get open covered call positions."""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            if ticker:
                cur.execute("""
                    SELECT * FROM portfolio_covered_calls
                    WHERE status = 'open' AND ticker = %s
                    ORDER BY expiration_date ASC
                """, (ticker,))
            else:
                cur.execute("""
                    SELECT * FROM portfolio_covered_calls
                    WHERE status = 'open'
                    ORDER BY expiration_date ASC
                """)
            return [dict(row) for row in cur.fetchall()]

    def evaluate_covered_call_vs_exit(self, ticker: str, current_price: float,
                                       bearish_probability: float,
                                       options_data: Dict = None) -> Dict:
        """
        Evaluate whether selling a covered call is more profitable than exiting.

        Returns recommendation:
        - 'exit': Sell the position
        - 'covered_call': Write covered call
        - 'hold': Neither (not enough signal strength)

        Logic:
        - If bearish probability > 90%: Exit (too risky to hold)
        - If 80-90%: Compare covered call premium vs expected loss
        - If < 80%: Hold (not enough conviction)
        """
        holding = self.get_holding(ticker, 'long_term')
        if not holding:
            return {'action': 'none', 'reason': 'No long-term position found'}

        shares = float(holding['quantity'])
        cost_basis = float(holding['avg_cost_basis'])
        current_value = shares * current_price
        unrealized_pnl = current_value - (shares * cost_basis)

        # Strong bearish signal - exit
        if bearish_probability >= 0.90:
            return {
                'action': 'exit',
                'reason': f'High bearish probability ({bearish_probability:.0%})',
                'expected_loss_avoided': unrealized_pnl * 0.10,  # Estimate 10% further drop
            }

        # Moderate bearish signal - evaluate covered call
        if bearish_probability >= 0.80:
            # Calculate covered call potential
            # Use ATM or slightly OTM call (~5% above current price)
            strike_price = round(current_price * 1.05, 2)
            contracts = int(shares / 100)

            if contracts < 1:
                return {
                    'action': 'exit',
                    'reason': 'Position too small for covered calls (< 100 shares)',
                }

            # Estimate premium (simplified - would use real options pricing in production)
            # Typical ATM call premium is 2-5% of stock price for monthly expiration
            estimated_premium_pct = 0.03  # 3% assumption
            estimated_premium = current_price * estimated_premium_pct * contracts * 100

            # Estimate potential loss if we hold (based on bearish probability)
            expected_decline = (bearish_probability - 0.50) * 0.20  # Scale probability to expected move
            expected_loss = current_value * expected_decline

            if estimated_premium > expected_loss * 0.5:  # Premium covers >50% of expected loss
                return {
                    'action': 'covered_call',
                    'reason': 'Covered call premium exceeds expected downside',
                    'strike_price': strike_price,
                    'contracts': contracts,
                    'estimated_premium': estimated_premium,
                    'expected_loss': expected_loss,
                }
            else:
                return {
                    'action': 'exit',
                    'reason': 'Expected loss exceeds covered call benefit',
                    'expected_loss': expected_loss,
                    'estimated_premium': estimated_premium,
                }

        # Low bearish signal - hold
        return {
            'action': 'hold',
            'reason': f'Bearish probability ({bearish_probability:.0%}) below threshold',
        }

    def write_covered_call(self, ticker: str, strike_price: float, expiration_date: date,
                           premium_per_share: float, contracts: int = None) -> Dict:
        """
        Write a covered call against an existing long position.
        """
        holding = self.get_holding(ticker, 'long_term')
        if not holding:
            return {'success': False, 'error': 'No long-term position found'}

        shares = float(holding['quantity'])
        max_contracts = int(shares / 100)

        if max_contracts < 1:
            return {'success': False, 'error': 'Position too small (< 100 shares)'}

        if contracts is None:
            contracts = max_contracts
        elif contracts > max_contracts:
            return {'success': False, 'error': f'Cannot write {contracts} contracts, max is {max_contracts}'}

        shares_covered = contracts * 100
        total_premium = premium_per_share * shares_covered
        call_id = uuid.uuid4()

        with self.conn.cursor() as cur:
            # Record the covered call
            cur.execute("""
                INSERT INTO portfolio_covered_calls
                (call_id, ticker, underlying_quantity, contracts, strike_price,
                 expiration_date, premium_received, total_premium, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'open')
            """, (
                call_id, ticker, shares_covered, contracts, strike_price,
                expiration_date, premium_per_share, total_premium
            ))

            # Add premium to cash balance
            cur.execute("""
                UPDATE portfolio_account
                SET cash_balance = cash_balance + %s, updated_at = NOW()
            """, (total_premium,))

            # Record as transaction
            cur.execute("""
                INSERT INTO portfolio_transactions
                (transaction_id, ticker, action, holding_type, asset_type, quantity,
                 price, total_value, option_type, strike_price, expiration_date, signal_source)
                VALUES (%s, %s, 'sell_to_open', 'long_term', 'option', %s, %s, %s, 'call', %s, %s, 'covered_call')
            """, (
                call_id, ticker, contracts, premium_per_share, total_premium,
                strike_price, expiration_date
            ))

            self.conn.commit()

        return {
            'success': True,
            'call_id': str(call_id),
            'ticker': ticker,
            'contracts': contracts,
            'strike_price': strike_price,
            'expiration_date': expiration_date.isoformat(),
            'total_premium': total_premium,
        }

    def close_covered_call(self, call_id: str, close_price: float = None,
                           close_reason: str = 'expired_worthless') -> Dict:
        """
        Close a covered call position.
        Reasons: 'expired_worthless', 'assigned', 'bought_back'
        """
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM portfolio_covered_calls WHERE call_id = %s", (call_id,))
            call = cur.fetchone()

            if not call or call['status'] != 'open':
                return {'success': False, 'error': 'Covered call not found or not open'}

            realized_pnl = float(call['total_premium'])

            if close_reason == 'bought_back' and close_price:
                # Deduct buyback cost
                buyback_cost = close_price * call['contracts'] * 100
                realized_pnl -= buyback_cost

                # Deduct from cash
                cur.execute("""
                    UPDATE portfolio_account
                    SET cash_balance = cash_balance - %s, updated_at = NOW()
                """, (buyback_cost,))

            elif close_reason == 'assigned':
                # Shares get called away at strike price
                holding = self.get_holding(call['ticker'], 'long_term')
                if holding:
                    shares_to_sell = call['contracts'] * 100
                    # Execute sale at strike price
                    self.execute_trade(
                        action='sell',
                        ticker=call['ticker'],
                        quantity=shares_to_sell,
                        price=float(call['strike_price']),
                        holding_type='long_term',
                        signal_source='call_assigned',
                    )

            # Update covered call record
            cur.execute("""
                UPDATE portfolio_covered_calls
                SET status = %s, close_date = NOW(), close_price = %s,
                    close_reason = %s, realized_pnl = %s, updated_at = NOW()
                WHERE call_id = %s
            """, (close_reason, close_price, close_reason, realized_pnl, call_id))

            self.conn.commit()

        return {
            'success': True,
            'call_id': call_id,
            'close_reason': close_reason,
            'realized_pnl': realized_pnl,
        }

    def check_expiring_calls(self, days_ahead: int = 3) -> List[Dict]:
        """Check for covered calls expiring soon."""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM portfolio_covered_calls
                WHERE status = 'open'
                  AND expiration_date <= CURRENT_DATE + INTERVAL '%s days'
                ORDER BY expiration_date ASC
            """, (days_ahead,))
            return [dict(row) for row in cur.fetchall()]

    # =========================================================================
    # Sector Rotation
    # =========================================================================

    def get_sector_for_ticker(self, ticker: str) -> Optional[str]:
        """Get sector for a ticker from database or yfinance."""
        # First try database
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT sector FROM stock_data
                WHERE ticker = %s
                LIMIT 1
            """, (ticker,))
            result = cur.fetchone()
            if result and result[0]:
                return result[0]

        # Fallback to yfinance
        try:
            import yfinance as yf
            stock = yf.Ticker(ticker)
            info = stock.info
            return info.get('sector')
        except Exception:
            return None

    def find_sector_alternatives(self, sector: str, exclude_tickers: List[str] = None,
                                  signals: List[Dict] = None) -> List[Dict]:
        """
        Find alternative stocks in the same sector with bullish signals.
        Used for sector rotation when exiting a position.
        """
        if not signals:
            return []

        exclude_tickers = exclude_tickers or []
        alternatives = []

        for signal in signals:
            ticker = signal['ticker']
            if ticker in exclude_tickers:
                continue
            if 'bullish' not in signal.get('signal_type', '').lower():
                continue

            ticker_sector = self.get_sector_for_ticker(ticker)
            if ticker_sector == sector:
                alternatives.append({
                    'ticker': ticker,
                    'sector': sector,
                    'signal': signal,
                    'signal_strength': signal.get('signal_strength', 0),
                })

        # Sort by signal strength
        alternatives.sort(key=lambda x: x['signal_strength'], reverse=True)
        return alternatives

    def exit_with_sector_rotation(self, ticker: str, current_price: float,
                                   exit_reason: str, signals: List[Dict] = None) -> Dict:
        """
        Exit a long-term position and optionally rotate into same-sector alternative.

        Returns:
        - exit_result: Result of selling current position
        - rotation_result: Result of buying alternative (if available)
        - watchlist_added: Whether position was added to watchlist
        """
        holding = self.get_holding(ticker, 'long_term')
        if not holding:
            return {'success': False, 'error': 'No position found'}

        sector = self.get_sector_for_ticker(ticker)
        quantity = float(holding['quantity'])
        cost_basis = float(holding['avg_cost_basis'])

        # Execute the exit
        exit_result = self.execute_trade(
            action='sell',
            ticker=ticker,
            quantity=quantity,
            price=current_price,
            holding_type='long_term',
            signal_source=exit_reason,
        )

        if not exit_result['success']:
            return exit_result

        realized_pnl = (current_price - cost_basis) * quantity

        # Add to watchlist for potential re-entry
        self.add_to_watchlist(
            ticker=ticker,
            exit_price=current_price,
            exit_reason=exit_reason,
            realized_pnl=realized_pnl,
            holding=holding,
            sector=sector,
        )

        result = {
            'success': True,
            'exit_result': exit_result,
            'realized_pnl': realized_pnl,
            'watchlist_added': True,
            'sector': sector,
        }

        # Look for sector rotation opportunity
        if signals and sector:
            alternatives = self.find_sector_alternatives(
                sector=sector,
                exclude_tickers=[ticker],
                signals=signals,
            )

            if alternatives:
                best_alt = alternatives[0]
                alt_price = best_alt['signal'].get('signal_price')

                if alt_price:
                    # Calculate position size for rotation
                    portfolio = self.get_portfolio_value()
                    max_position = portfolio['total_value'] * self.config['max_position_pct']
                    alt_quantity = int(max_position / alt_price)

                    if alt_quantity >= 1:
                        rotation_result = self.execute_trade(
                            action='buy',
                            ticker=best_alt['ticker'],
                            quantity=alt_quantity,
                            price=alt_price,
                            holding_type='long_term',
                            signal_source='sector_rotation',
                            signal_details={'rotated_from': ticker, 'sector': sector},
                        )
                        result['rotation_result'] = rotation_result
                        result['rotated_to'] = best_alt['ticker']

        return result


def main():
    parser = argparse.ArgumentParser(description='Portfolio Manager')
    parser.add_argument('--status', action='store_true', help='Show portfolio status')
    parser.add_argument('--buy', type=str, help='Buy ticker symbol')
    parser.add_argument('--sell', type=str, help='Sell ticker symbol')
    parser.add_argument('--quantity', type=float, help='Quantity to trade')
    parser.add_argument('--price', type=float, help='Price per share')
    parser.add_argument('--type', choices=['long_term', 'swing'], default='swing', help='Holding type')
    parser.add_argument('--process-signals', action='store_true', help='Process pending signals')
    parser.add_argument('--daily-snapshot', action='store_true', help='Create daily snapshot')

    args = parser.parse_args()

    pm = PortfolioManager()

    if args.status:
        summary = pm.get_portfolio_summary()
        print(json.dumps(summary, indent=2, default=decimal_to_float))

    elif args.buy and args.quantity and args.price:
        result = pm.execute_trade('buy', args.buy, args.quantity, args.price, args.type)
        print(json.dumps(result, indent=2, default=decimal_to_float))

    elif args.sell and args.quantity and args.price:
        result = pm.execute_trade('sell', args.sell, args.quantity, args.price, args.type)
        print(json.dumps(result, indent=2, default=decimal_to_float))

    elif args.process_signals:
        signals = pm.get_pending_signals()
        print(f"Found {len(signals)} pending signals")
        for signal in signals:
            print(f"  - {signal['ticker']}: {signal['signal_type']} ({signal['suggested_action']})")

    elif args.daily_snapshot:
        snapshot = pm.create_daily_snapshot()
        print(json.dumps(snapshot, indent=2, default=decimal_to_float))

    else:
        parser.print_help()


if __name__ == '__main__':
    main()
