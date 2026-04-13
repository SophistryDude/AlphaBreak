# How to Build Your First Trading Plan (Template Included)

*Reading time: 18 minutes*

---

## What a Trading Plan Actually Is

Most beginners think a trading plan is a prediction document — a forecast of what the market will do. It isn't.

A trading plan is a constraint document. It specifies what you will and will not do, under what conditions, with what sized positions, and what triggers exit. It is not a prediction of the future. It is a pre-commitment to a process.

This distinction matters because it changes what the plan is for. A prediction document is evaluated by whether it was "right" about the market. A constraint document is evaluated by whether it was followed consistently. The plan cannot be wrong about the future. The plan can only be followed or violated.

This reframe is critical for beginners. You will not know whether your plan is profitable until you've executed it consistently for 50-100 trades. Before then, the measure of success is adherence, not P&L. Did you follow the plan? Yes or no. That's the only question that matters for the first 3-6 months.

---

## Why Plans Fail

Before building a plan, let's understand why most plans don't work. This will inform how we build one that does.

### Failure Mode 1: Vagueness

"Buy when the trend is up and the setup looks good."

This plan cannot be followed because it doesn't define:
- What constitutes an uptrend (higher highs and lows? Above the 200 SMA? Confirmed by which indicator?)
- What makes a setup "look good" (what specific criteria?)
- What constitutes "buying" (at market? Limit order? Stop-buy?)

A plan that relies on subjective judgment in the moment is not a plan. It's a set of suggestions. When emotional pressure arrives, you'll make different judgments than you intended.

**The test**: could another trader execute your plan without asking you questions? If not, it's too vague.

### Failure Mode 2: Rigidity

"Always buy when RSI crosses below 30, always sell when it crosses above 70."

This plan is specific but ignores context. RSI < 30 in a strong downtrend is not a buy signal — it's a warning that downtrends can maintain oversold conditions for weeks. Blindly buying every RSI dip in any regime leads to catastrophic losses.

**The test**: does your plan account for market regime? If it's a single set of rules applied to all conditions, it will fail when the market enters an unfavorable regime.

### Failure Mode 3: Wishful Assumptions

"Enter long, hold for a 10% gain, stop loss at 5% below entry."

This plan has a 2:1 risk/reward ratio, which sounds fine. But it doesn't specify:
- When to enter (what signal triggers the entry)
- Whether the 10% target is likely given recent volatility
- What happens if the price moves 4% down and then 8% up (you'd stop out before the target)
- How volatility affects the probability of reaching either level

A plan based on hope about what "should" happen rather than analysis of what is likely will produce disappointment.

### Failure Mode 4: No Review Process

Even a good plan degrades without review. Markets change. Your understanding improves. Edges erode. A plan that you wrote 12 months ago and never revised is probably less effective now than it was then.

**The test**: do you have a scheduled review process to evaluate and update the plan?

---

## The Seven Components of a Complete Trading Plan

A complete trading plan has seven components. Each one answers a specific question about how you'll trade.

### Component 1: Market and Instrument Selection

**Question**: What will I trade, and why?

You can't trade everything. Narrowing your focus is the first constraint. Considerations:
- **Asset class**: Stocks, options, futures, forex, crypto? Pick one to start.
- **Market capitalization**: Large-cap (lower volatility, more liquid) vs. small-cap (higher volatility, less liquid)?
- **Sectors**: All sectors or specific ones? Tech and biotech move differently than utilities and consumer staples.
- **Liquidity requirements**: Minimum volume, minimum price. You need enough liquidity to enter and exit without slippage.

**Example specification**:
- US stocks only
- Market cap > $1 billion
- Average daily volume > 500,000 shares
- Price > $10 (avoid penny stocks)
- Focus on technology and consumer discretionary sectors

### Component 2: Setup Definition

**Question**: What specifically constitutes a trade opportunity?

This is the most important component and the one beginners struggle with most. The setup must be defined precisely enough that you can objectively determine whether it exists.

**Bad example**: "Buy on pullbacks in uptrending stocks."

**Good example**: "Buy when ALL of the following are true:
- Stock is above its 200-day SMA (trend filter)
- Stock has pulled back to its 50-day SMA (entry level)
- RSI(14) is between 40 and 55 (not overbought or exhausted)
- Daily volume on the pullback is declining (not a breakdown)
- Stock is in the top 30% of its sector's performance over the past 3 months (relative strength filter)"

The second version is executable without interpretation. The first version requires judgment about what "pullback" and "uptrending" mean.

### Component 3: Entry Rules

**Question**: Exactly when and how do I enter the trade?

Once the setup is identified, how do you actually execute the entry?
- **Order type**: Market order, limit order, stop order?
- **Price**: At market, at a specific limit price, or triggered by a breakout level?
- **Time**: At market open, during the first hour, after 10 AM, anytime during session?
- **Confirmation**: Do you need to see additional confirmation before entering, or is the setup itself sufficient?

**Example specification**: "Place a limit buy order at or slightly above the previous day's close. Cancel the order if not filled within the first 90 minutes of trading. If filled, immediately place stop loss order."

### Component 4: Position Sizing

**Question**: How much capital do I allocate to each trade?

Position sizing translates risk management rules into specific share or contract numbers.

**The formula**:
- Max risk per trade (1-2% of account) = X dollars
- Stop loss distance = Y dollars per share
- Position size = X / Y shares

**Example specification**: "Risk 1% of total account per trade. Calculate position size using: (Account value × 0.01) / (Entry price − Stop price). Round down to the nearest whole share."

For a $25,000 account buying a $50 stock with a $47 stop:
- Max risk: $250
- Stop distance: $3
- Position size: 250 / 3 = 83 shares
- Position value: 83 × $50 = $4,150 (16.6% of account)

### Component 5: Stop Loss Rules

**Question**: Where and how do I exit losing trades?

Stop loss must be:
- **Specific**: A defined price, not "wherever feels right"
- **Based on technical structure**: Below a support level, below a previous pivot low, or based on ATR
- **Placed before entry**: As a hard order with the broker, not a mental stop
- **Non-negotiable**: Do not move the stop further from entry under any circumstances

**Example specification**: "Place stop loss order below the most recent swing low, with a minimum distance of 1.5x ATR(14) from entry price. Stop is a hard order placed immediately after entry fill. Stop will not be moved further from entry under any circumstances. May be moved closer to entry (trailing) as trade progresses."

### Component 6: Profit Target Rules

**Question**: Where and how do I exit winning trades?

Targets can be:
- **Fixed**: A specific price level (e.g., previous resistance)
- **Ratio-based**: A multiple of risk (e.g., 2x the stop distance)
- **Trailing**: A stop that moves up as price rises, capturing profits while allowing further upside
- **Indicator-based**: Exit when a specific indicator signals reversal

**Example specification**: "Initial target at 2x risk (e.g., if risking $3 per share, target is $6 of profit per share). Upon reaching target, sell 50% of position and move stop to breakeven on remaining 50%. Trail remaining position with a stop below each new swing low."

### Component 7: Review Process

**Question**: How often do I evaluate and update the plan?

Regular review is what keeps the plan useful over time.

**Daily review**: End-of-day check. Did I follow the plan today? Any rule violations? Any observations to note?

**Weekly review**: Calculate the week's results. Review individual trades. Update the journal with patterns observed.

**Monthly review**: Full metrics calculation (win rate, profit factor, R-multiples). Compare to previous months. Identify trends.

**Quarterly review**: Reassess the entire plan. Is the strategy still working? Has the market regime changed? Should any components be adjusted?

**Example specification**: "Daily: 10-minute end-of-day review. Weekly: 30-minute Sunday review of the week's trades. Monthly: full metrics calculation and comparison. Quarterly: comprehensive plan review with possible adjustments."

---

## The Template

Here's a complete template you can copy and fill in for your own plan:

```
====================================
TRADING PLAN
Version: 1.0
Date: [DATE]
====================================

1. MARKET AND INSTRUMENT SELECTION
- Asset class:
- Market cap range:
- Sector focus:
- Minimum liquidity:
- Price range:

2. SETUP DEFINITION
Entry criteria (ALL must be true):
- Criterion 1:
- Criterion 2:
- Criterion 3:
- Criterion 4:
- (add more as needed)

3. ENTRY RULES
- Order type:
- Price:
- Time restrictions:
- Confirmation required:

4. POSITION SIZING
- Max risk per trade: X% of account
- Formula: (Account × X%) / (Entry − Stop)
- Maximum concurrent positions:
- Maximum total portfolio risk:

5. STOP LOSS RULES
- Placement method:
- Minimum distance from entry:
- Type: hard order / trailing
- Non-negotiable: yes/no

6. PROFIT TARGET RULES
- Initial target:
- Scale-out rules:
- Trailing stop method:

7. REVIEW PROCESS
- Daily review time:
- Weekly review time:
- Monthly review:
- Quarterly review:

====================================
```

### Example Filled-In Plan: Swing Trading Uptrending Stocks

```
====================================
TRADING PLAN
Version: 1.0
Date: April 12, 2026
====================================

1. MARKET AND INSTRUMENT SELECTION
- Asset class: US stocks (long only)
- Market cap range: $1B and above
- Sector focus: Technology, Consumer Discretionary, Healthcare
- Minimum liquidity: Average daily volume > 500K shares
- Price range: $15 - $500 per share

2. SETUP DEFINITION
Entry criteria (ALL must be true):
- Stock is above 200-day SMA (trend filter)
- Stock has pulled back to or near 50-day SMA (entry level)
- RSI(14) is between 40 and 55
- Volume on pullback is declining (not increasing)
- Stock is in top 30% of sector's 3-month performance
- No earnings report within the next 7 days

3. ENTRY RULES
- Order type: Limit buy order
- Price: Previous day's close (limit)
- Time restrictions: Order placed before market open, cancelled if not filled by noon
- Confirmation required: None beyond entry criteria

4. POSITION SIZING
- Max risk per trade: 1% of account
- Formula: (Account × 0.01) / (Entry − Stop)
- Maximum concurrent positions: 5
- Maximum total portfolio risk: 5%

5. STOP LOSS RULES
- Placement method: Below most recent swing low, or 1.5x ATR(14) below entry — whichever is wider
- Type: Hard stop-loss order
- Non-negotiable: Yes. Stop will not be moved further from entry.

6. PROFIT TARGET RULES
- Initial target: 2x risk (2R)
- Scale-out: Sell 50% at 2R, move stop to breakeven on remaining 50%
- Trailing: Remaining 50% trailed below each new swing low

7. REVIEW PROCESS
- Daily review: 10 min at end of session
- Weekly review: 30 min every Sunday evening
- Monthly review: Full metrics + pattern analysis on last day of month
- Quarterly review: Complete plan reassessment

====================================
```

---

## Common Plan Mistakes

### Mistake 1: Over-optimization

Creating a plan with 15 specific criteria that perfectly matches past winning trades. The result: a plan so narrow that almost no trades qualify, or one that works on historical data but fails on new data (overfitting).

**The fix**: start with 4-6 core criteria. Add more only if you can articulate why they're needed. If a criterion doesn't meaningfully improve outcomes, remove it.

### Mistake 2: Plans That Aren't Followed

Writing a plan and then ignoring it when "this time is different." Every deviation undermines the value of the plan. If you're not going to follow it, don't write it.

**The fix**: score yourself on plan adherence, not just P&L. Target 90%+ adherence. Any deviation is tracked as a rule violation in the journal.

### Mistake 3: Plans That Never Adapt

Writing a plan and treating it as permanent law. Markets change. Your understanding improves. A plan from 18 months ago may not be appropriate for the current market.

**The fix**: quarterly reviews with explicit consideration of whether the plan needs updating. Versioned plans (1.0, 1.1, 2.0) so you can track changes over time.

### Mistake 4: Plans With No Measurement

Having a plan but not tracking whether it's working. Without data, you can't distinguish a good plan from a bad one, or identify which components are contributing to success.

**The fix**: journal every trade with the fields needed for later analysis. At minimum: date, ticker, setup, entry, stop, target, exit, outcome, rules followed.

### Mistake 5: Copying Someone Else's Plan

Finding a profitable trader's strategy and adopting it as your own. This rarely works because:
- Their plan was built for their personality, capital, and time availability
- You don't understand why each component is there, so you can't maintain it when conditions change
- Publicly shared strategies often lose their edge as they become crowded

**The fix**: build your own plan, even if it starts simpler than what others are using. A plan you understand is more valuable than a "better" plan you can't maintain.

---

## The Plan Evolution Path

Your first plan will be simple, probably crude, and definitely imperfect. That's expected. The plan is supposed to evolve over time as you gain experience.

### Version 1.0: Your First Plan

Simple. Focused on one setup type. Emphasis on risk management and rule following. Goal: 50-100 trades with high adherence.

Measure: Did you follow the plan?

### Version 2.0: Refinement

After 100 trades, you'll see what's working and what isn't. Maybe the target is too ambitious. Maybe the stop is too tight. Maybe one criterion isn't meaningful.

Refine based on data, not feelings. Remove criteria that don't improve outcomes. Add criteria that address specific failure patterns you've observed.

### Version 3.0: Second Setup

Once you've mastered one setup, consider adding a second — but only after proving consistent execution on the first. The second setup should address different market conditions than the first (e.g., if your first setup works in ranging markets, your second might work in trending markets).

### Beyond: Specialization

Most successful traders eventually specialize. They have 2-4 setups that they execute expertly, rather than 10 setups they execute mediocrely. Depth beats breadth.

---

## The Psychological Function of Plans

Beyond the tactical value, a trading plan serves a crucial psychological function: it removes the burden of in-the-moment decision-making.

Without a plan, every market move requires a decision. Every setup requires an evaluation. Every exit requires a judgment call. This constant decision-making is exhausting, and exhaustion leads to worse decisions as the day progresses.

With a plan, most decisions are pre-made. When a setup appears, you check the criteria. If they match, you execute. If they don't, you wait. No agonizing, no second-guessing, no improvisation.

This doesn't mean you become a robot. It means you save your mental energy for the decisions that actually require judgment (rare) rather than burning it on decisions that should be automatic (common).

---

## The First 30 Days With Your Plan

Here's how to use a new plan in its first month:

**Days 1-7**: Paper trade only. Practice executing the plan without real money. Make sure you can identify setups, calculate position sizes, and execute orders correctly.

**Days 8-14**: Continue paper trading. Journal every trade. Note any ambiguities in the plan — places where you had to guess. Refine the plan to eliminate those ambiguities.

**Days 15-21**: Begin live trading with 25% of planned position size. Focus entirely on execution quality. Do not change the plan based on 2-3 trade outcomes.

**Days 22-30**: If execution is good, increase to 50% size. Continue journaling. Note whether the plan is producing the expected number of trade setups.

**End of month 1**: Review. Did you follow the plan consistently? What was your adherence rate (trades that fully followed rules / total trades)? What rules were difficult to follow and why?

After month 1, you'll know whether your plan is executable by you, not just whether it's theoretically profitable. This is the first milestone. Profitability comes later — usually months 3-6 once enough trades have accumulated for meaningful statistics.

---

## The Commitment

Writing a plan is easy. Following it is hard. Here's the commitment that makes the difference:

**"I will follow this plan on every trade for the next 30 days, regardless of outcome."**

Not "if it's working." Not "if I feel like it." Not "unless I see a great opportunity." For 30 days, the plan is the law.

At the end of 30 days, you can evaluate whether the plan needs revisions. Until then, you evaluate only whether you followed it. This separation — adherence first, outcome later — is the discipline that turns a plan from a document into a system.

The trader who follows a mediocre plan consistently will outperform the trader who bounces between "better" plans. Consistency compounds. Improvisation accumulates errors.

---

*AlphaBreak includes a trade thesis builder that structures your pre-trade plans with entry criteria, targets, stops, and conviction levels. The journal system tracks plan adherence automatically, showing you your rule-following rate alongside your P&L. And our AI scoring provides an objective second opinion on whether a setup matches your defined criteria — helping you stay disciplined when emotion pushes you to deviate.*

*Try AlphaBreak free →*
