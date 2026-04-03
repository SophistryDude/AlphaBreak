"""
Backtest: New portfolio rules vs actual results.
Period: Feb 9, 2026 - Apr 2, 2026

Models options as: Premium = ~3% of stock price for ATM 30-DTE calls,
options move with delta ~0.50 on the underlying.
"""

# === CURRENT PORTFOLIO (ACTUAL) ===
ACTUAL_VALUE = 96242.82
ACTUAL_PNL = -3757.18
ACTUAL_PNL_PCT = -0.0376
ACTUAL_REALIZED = -3487.29

STARTING = 100000.0
OPT_PREMIUM_PCT = 0.03
OPT_DELTA = 0.50

# Long-term buys (same signals, same dates)
lt_buys = [
    ("2026-02-12", "NVDA",  190.05, 173.86),
    ("2026-02-12", "AVGO",  342.76, 306.88),
    ("2026-02-12", "GOOGL", 310.96, 293.87),
    ("2026-02-12", "LLY",  1015.21, 953.23),
    ("2026-02-12", "ORCL",  157.16, 142.65),
    ("2026-02-12", "AAPL",  275.50, 228.70),
]

# Under old rules these were stop-lossed and some re-bought.
# Under new multi-TF rules: trim 25% instead of full exit.
trim_events = [
    ("AAPL", 275.50, 255.78, 228.70),
    ("ORCL",  157.16, 141.31, 142.65),
    ("AVGO", 342.76, 313.84, 306.88),
    ("LLY", 1015.21, 911.48, 953.23),
    ("NVDA", 190.05, 173.86, 173.86),
]

# Swing signals (bullish trend breaks) -> now options
swing_buys = [
    # (date, ticker, entry_price, peak_in_period, current_apr2, hit_5pct_target)
    ("2026-02-09", "AMP",   542.99, 542.99, 468.78, False),
    ("2026-02-09", "BLK",  1056.38, 1087.78, 1072.67, False),
    ("2026-02-09", "CAT",   726.20,  775.00, 764.76, True),
    ("2026-02-09", "CMI",   577.73,  601.38, 595.66, True),
    ("2026-02-09", "DPZ",   394.88,  394.88, 373.50, False),
    ("2026-02-09", "FICO", 1391.00, 1391.00, 1351.60, False),
    ("2026-02-11", "KLAC", 1430.84, 1480.30, 1469.90, True),
    ("2026-02-13", "AMP",   467.30,  505.64, 468.78, True),
]

print("=" * 70)
print("PORTFOLIO BACKTEST: NEW RULES vs OLD RULES")
print("Period: Feb 9, 2026 - Apr 2, 2026")
print("=" * 70)

# --- LONG-TERM LEG (50% = $50,000) ---
lt_cash = STARTING * 0.50
lt_holdings = {}
lt_trades = []
lt_realized = 0.0

for date, ticker, entry, current in lt_buys:
    pos_size = min(STARTING * 0.07, lt_cash)
    shares = int(pos_size / entry)
    if shares < 1 or shares * entry > lt_cash:
        continue
    cost = shares * entry
    lt_cash -= cost
    lt_holdings[ticker] = {"shares": shares, "entry": entry, "cost": cost}
    lt_trades.append(f"  BUY {shares:3d} {ticker:5s} @ ${entry:>8.2f} = ${cost:>9.2f}")

# Apply trims (25%) instead of full stop-loss exits
for ticker, entry, trim_price, current in trim_events:
    if ticker not in lt_holdings:
        continue
    h = lt_holdings[ticker]
    trim_qty = max(1, int(h["shares"] * 0.25))
    trim_value = trim_qty * trim_price
    realized = (trim_price - h["entry"]) * trim_qty
    lt_realized += realized
    lt_cash += trim_value
    h["shares"] -= trim_qty
    lt_trades.append(f"  TRIM {trim_qty:3d} {ticker:5s} @ ${trim_price:>8.2f} (realized ${realized:>+9.2f})")

# Calculate LT current value
lt_holdings_value = 0
for date, ticker, entry, current in lt_buys:
    if ticker in lt_holdings and lt_holdings[ticker]["shares"] > 0:
        mkt_val = lt_holdings[ticker]["shares"] * current
        lt_holdings_value += mkt_val

lt_value = lt_cash + lt_holdings_value

print(f"\n--- LONG-TERM LEG (50% = $50,000) ---")
for t in lt_trades:
    print(t)
print(f"  LT cash remaining:   ${lt_cash:>10,.2f}")
print(f"  LT holdings value:   ${lt_holdings_value:>10,.2f}")
print(f"  LT total value:      ${lt_value:>10,.2f}")
print(f"  LT realized P&L:     ${lt_realized:>+10,.2f}")
print(f"  LT total return:     {(lt_value - 50000) / 50000:>+10.2%}")

# --- SWING OPTIONS LEG (30% + 20% float = $50,000) ---
swing_cash = STARTING * 0.50  # 30% + 20% float
swing_trades_log = []
swing_realized = 0.0
positions_open = 0

for date, ticker, entry, peak, current, hit_target in swing_buys:
    if positions_open >= 5:
        swing_trades_log.append(f"  SKIP {ticker:5s} (max 5 concurrent)")
        continue

    premium = entry * OPT_PREMIUM_PCT
    budget = min(STARTING * 0.10, swing_cash)
    contracts = int(budget / (premium * 100))

    if contracts < 1:
        swing_trades_log.append(f"  SKIP {ticker:5s} (too expensive)")
        continue

    cost = contracts * premium * 100
    if cost > swing_cash:
        continue

    swing_cash -= cost
    positions_open += 1

    stock_change_pct = (current - entry) / entry

    if hit_target:
        # Stock moved 5%+ -> option gains ~(0.05 * entry * 0.50) / premium per share
        gain_per_share = 0.05 * entry * OPT_DELTA
        exit_premium = premium + gain_per_share
        exit_value = contracts * exit_premium * 100
        pnl = exit_value - cost
        swing_realized += pnl
        swing_cash += exit_value
        positions_open -= 1
        pnl_pct = pnl / cost
        swing_trades_log.append(
            f"  {ticker:5s} {contracts}x ${entry:.0f}C @ ${premium:.2f} "
            f"-> PROFIT @ ${exit_premium:.2f}  P&L: ${pnl:>+8,.2f} ({pnl_pct:>+6.0%})"
        )
    elif stock_change_pct < -0.07:
        # Big drop -> reversal exit
        loss_per_share = abs(stock_change_pct) * entry * OPT_DELTA
        exit_premium = max(premium * 0.50, premium - loss_per_share)
        exit_value = contracts * exit_premium * 100
        pnl = exit_value - cost
        swing_realized += pnl
        swing_cash += exit_value
        positions_open -= 1
        pnl_pct = pnl / cost
        swing_trades_log.append(
            f"  {ticker:5s} {contracts}x ${entry:.0f}C @ ${premium:.2f} "
            f"-> REVERSAL @ ${exit_premium:.2f}  P&L: ${pnl:>+8,.2f} ({pnl_pct:>+6.0%})"
        )
    else:
        # Sideways -> theta decay ~40% over 30 days
        exit_premium = premium * 0.60
        exit_value = contracts * exit_premium * 100
        pnl = exit_value - cost
        swing_realized += pnl
        swing_cash += exit_value
        positions_open -= 1
        pnl_pct = pnl / cost
        swing_trades_log.append(
            f"  {ticker:5s} {contracts}x ${entry:.0f}C @ ${premium:.2f} "
            f"-> DECAY   @ ${exit_premium:.2f}  P&L: ${pnl:>+8,.2f} ({pnl_pct:>+6.0%})"
        )

print(f"\n--- SWING OPTIONS LEG (30%+20% float = $50,000) ---")
for t in swing_trades_log:
    print(t)
print(f"  Swing cash remaining: ${swing_cash:>10,.2f}")
print(f"  Swing realized P&L:   ${swing_realized:>+10,.2f}")
print(f"  Swing total return:   {swing_realized / (STARTING * 0.50):>+10.2%}")

# === FINAL COMPARISON ===
new_total = lt_value + swing_cash
new_pnl = new_total - STARTING
new_pnl_pct = new_pnl / STARTING

wins = sum(1 for d, t, e, p, c, h in swing_buys if h)
losses = len(swing_buys) - wins

print(f"\n{'=' * 70}")
print(f"{'SIDE-BY-SIDE COMPARISON':^70s}")
print(f"{'=' * 70}")
print(f"")
print(f"{'':35s} {'OLD RULES':>15s} {'NEW RULES':>15s}")
print(f"{'-' * 65}")
print(f"{'Starting Balance':35s} {'$100,000':>15s} {'$100,000':>15s}")
print(f"{'Ending Value':35s} ${ACTUAL_VALUE:>14,.2f} ${new_total:>14,.2f}")
print(f"{'Total P&L':35s} ${ACTUAL_PNL:>+14,.2f} ${new_pnl:>+14,.2f}")
print(f"{'Total Return':35s} {ACTUAL_PNL_PCT:>+14.2%} {new_pnl_pct:>+14.2%}")
print(f"{'':35s} {'':>15s} {'':>15s}")
print(f"{'LT Allocation':35s} {'65%':>15s} {'50%':>15s}")
print(f"{'Swing Allocation':35s} {'35% (stock)':>15s} {'30% (options)':>15s}")
print(f"{'Cash Rule':35s} {'20% min floor':>15s} {'20% float':>15s}")
print(f"{'LT Exit Rule':35s} {'7% stop-loss':>15s} {'25% trim (MT)':>15s}")
print(f"{'LT Realized P&L':35s} ${ACTUAL_REALIZED:>+14,.2f} ${lt_realized:>+14,.2f}")
print(f"{'Swing Realized P&L':35s} {'$0.00':>15s} ${swing_realized:>+14,.2f}")
print(f"{'Swing Win Rate':35s} {'N/A (no sells)':>15s} {f'{wins}/{wins+losses}':>15s}")
print(f"{'Swing Instrument':35s} {'Stock':>15s} {'ATM Calls 30D':>15s}")
print(f"{'Max Risk per Swing Trade':35s} {'$4-7K stock':>15s} {'$10K premium':>15s}")
print(f"{'=' * 65}")
print(f"")
diff = new_pnl - ACTUAL_PNL
print(f"Difference: ${diff:+,.2f} ({diff/STARTING:+.2%}) in favor of {'NEW' if diff > 0 else 'OLD'} rules")
