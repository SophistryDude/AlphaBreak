# Why Most Backtests Lie (And How to Spot Fake Results)

*Reading time: 16 minutes*

---

## The Backtest Promise

A backtest is an attempt to simulate what a trading strategy would have done if you had applied it to historical market data. The appeal is obvious: if you can prove a strategy worked in the past, you have evidence that it might work in the future.

You've seen the advertisements. "This strategy returned 347% over 5 years!" "Our system has an 87% win rate!" "Generate $100,000 per year with our proven method!" These claims are almost always supported by backtested results.

Most of these backtests are misleading. Not because the authors are lying — though some are — but because backtesting contains systematic biases that inflate historical performance and understate future risk. Even well-intentioned backtests fail to predict live trading results most of the time.

Understanding why backtests lie is essential for two reasons:
1. You won't be fooled by marketing claims based on inflated historical results
2. You can build honest backtests of your own strategies that actually give you useful information

---

## The Fundamental Problem

Here's the honest truth about backtesting that most educators don't tell you:

**A backtest tells you how a strategy would have performed if you had known in advance which strategy to pick.**

This is circular reasoning. You developed the strategy by looking at historical data. You picked parameters that worked on that data. Then you ran the backtest on the same data and found — surprise — it worked.

This is not evidence of predictive power. It's evidence that you can find patterns in historical data if you look hard enough. The question is whether those patterns are real and persistent, or whether they're artifacts of your search process.

Distinguishing signal from noise in backtesting is hard. Most published results are noise masquerading as signal.

---

## The Five Sins of Backtesting

Let me walk through the five most common ways backtests produce misleading results.

### Sin 1: Overfitting

**What it is**: Adjusting strategy parameters until they perfectly match historical data.

**How it works**: You notice that a 14-period RSI gave 60% win rate. You try 13, 15, 10, 20 — and discover that 16-period RSI produces 75% win rate over your test period. You've "optimized" the strategy.

But the 16-period RSI wasn't inherently better. It just happened to coincide with the specific price patterns in your test data. Apply it to a different period and it probably performs worse than the 14-period version.

**The mechanism**: historical data contains noise. With enough parameter adjustments, you can always find a combination that fits the noise perfectly. But the noise doesn't repeat — only the signal does. An overfit strategy is one that has absorbed too much noise, making it fragile to new data.

**How to spot it**:
- Strategies with many parameters (more knobs = more overfitting potential)
- Strategies optimized for a specific historical period
- Dramatic performance improvements from small parameter changes (sign that the strategy is fitting noise)
- Performance that's unusually smooth (no drawdowns, consistent gains — real strategies have more variance)

**The defense**: use simple strategies with few parameters. Test on multiple independent time periods. If changing a parameter by 10% dramatically changes results, the strategy is fitting noise, not signal.

### Sin 2: Survivorship Bias

**What it is**: Testing strategies only on stocks that still exist, ignoring stocks that were delisted, went bankrupt, or merged away.

**How it works**: Suppose you backtest a strategy on the current S&P 500 constituents going back 20 years. The results look great. But the current S&P 500 constituents are survivors — the stocks that didn't fail. 20 years ago, the S&P 500 included many companies that subsequently declined dramatically or went bankrupt. Those companies aren't in your backtest.

You're effectively running your strategy only on winners, which produces artificially good results.

**Real-world impact**: A strategy that appears to return 15% annually on current S&P 500 constituents might return 8-10% on the actual S&P 500 constituents from each historical period. Survivorship bias can inflate returns by 5-7% per year.

**How to spot it**:
- Backtests run on current index constituents rather than point-in-time constituents
- Datasets that don't include delisted stocks
- Performance that's too good to be true (often driven by hindsight selection of the universe)

**The defense**: use point-in-time data that includes all stocks that existed at each historical date, including ones that later failed. This data is expensive but more honest.

### Sin 3: Look-Ahead Bias

**What it is**: Using information in the strategy that wasn't actually available at the time of the simulated trade.

**How it works**: Your backtest says "buy when earnings per share exceed analyst expectations by 10%." But EPS and analyst expectations are often restated or revised after the fact. The current "historical" EPS number might be different from the EPS that was known at the time.

Similarly, "adjusted close" prices incorporate future dividend payments and splits. If your backtest uses adjusted close prices for entry and exit decisions, you're implicitly using information that wasn't available at the time.

**Subtle examples**:
- Using end-of-day data to make "intraday" decisions
- Using revised economic data (often different from initial release)
- Using company fundamentals that were announced 45 days after the period end but are stamped with the period-end date
- Using survivorship-adjusted indices

**How to spot it**:
- Backtests that don't specify their data source and timing conventions
- Unusually high win rates on event-driven strategies (often indicates look-ahead into the event result)
- Results that deteriorate when tested with strict point-in-time data

**The defense**: explicitly think about what information was available at each point in history. Use data sources that preserve original values (not subsequent revisions). For earnings or macro data, use the first released value, not the current revised value.

### Sin 4: Selection Bias (Multiple Comparison Problem)

**What it is**: Testing many strategies and reporting only the ones that worked.

**How it works**: Suppose you test 100 different strategies on historical data. Even if all 100 strategies are worthless (pure noise), approximately 5 will show "statistically significant" results at the 5% significance level — by chance alone.

If you cherry-pick those 5 "successful" strategies and publish them, you're reporting results that look good but won't persist. The "winners" are just the lucky tests.

**Real-world prevalence**: This is rampant in strategy marketing. A trading service tests hundreds of strategies and reports the ones that worked, leaving out the ones that didn't. The reported results look impressive but represent selection from a larger sample.

**How to spot it**:
- Strategies presented in isolation without mention of how they were developed
- "Discovered" patterns that lack theoretical justification
- Results that are dramatically better than similar published strategies
- Strategies that require very specific parameter combinations

**The defense**: apply multiple comparison corrections. If you tested 100 strategies, the significance threshold should be higher (typically divided by the number of tests). Alternatively, test fewer strategies that are motivated by clear theoretical reasoning rather than data mining.

### Sin 5: Transaction Cost Blindness

**What it is**: Ignoring or underestimating the costs of actually executing the strategy.

**How it works**: A backtest shows 20% annual return before costs. In reality:
- Bid-ask spreads cost 0.05-0.20% per trade
- Commissions (even "zero") have effective costs via order routing
- Slippage between signal and fill can be 0.10-0.30% per trade
- Market impact on larger orders adds more cost

For a strategy making 200 trades per year, total costs might be 1-4% of account value annually. A "20% annual return before costs" strategy might be a "16-19% net return" strategy — or worse.

For a strategy making 1000 trades per year (higher frequency), costs can reach 5-15% annually, potentially eliminating any edge.

**How to spot it**:
- Backtests that don't mention transaction costs
- Strategies with very high trade frequency and modest per-trade edge
- "Net" returns that seem too close to "gross" returns
- Strategies applied to illiquid instruments where slippage is severe

**The defense**: always include realistic transaction costs in backtests. For retail traders, 0.10-0.20% per round trip is a reasonable estimate for liquid stocks. For less liquid instruments, costs are higher. If your strategy doesn't survive realistic costs, it's not a real strategy.

---

## How to Evaluate a Backtest Honestly

When you see a backtest result — whether from a service, a book, or your own testing — apply these checks.

### Check 1: Sample Size

How many trades does the backtest include? A backtest based on 20 trades is meaningless. The minimum for any confidence is 100 trades. For statistical significance, you want 200-500+.

**If sample size is small**: treat results as preliminary indication, not as evidence.

### Check 2: Time Period Diversity

Does the backtest include multiple market regimes (bull markets, bear markets, ranging markets, high-volatility periods, low-volatility periods)?

A strategy tested only during a bull market won't tell you how it performs during downturns. A strategy tested only in 2020-2022 is tested on an unusual period and may not generalize.

**Minimum diversity**: 5-10 years of data, including at least one significant drawdown period.

### Check 3: Out-of-Sample Testing

Was the strategy developed on one period and tested on another unseen period?

This is the gold standard for honest backtesting. You can't overfit to data you haven't looked at. If the strategy works on unseen data, you have stronger evidence that the edge is real.

**If no out-of-sample test**: treat the backtest with high skepticism.

### Check 4: Parameter Sensitivity

Does the strategy's performance change dramatically with small parameter changes?

A strategy that returns 20% with a 14-period RSI but only 5% with a 13-period RSI is fitting noise. A robust strategy should show similar performance across reasonable parameter ranges.

**The test**: ask for results with parameters ±10% from the chosen values. If performance varies wildly, the strategy is overfit.

### Check 5: Transaction Costs Included

Does the reported return include realistic transaction costs?

If the backtest says "before costs," mentally subtract 1-3% per year (depending on trade frequency). If it doesn't specify, assume no costs were included and treat the results as optimistic.

### Check 6: Maximum Drawdown

What was the worst peak-to-trough decline during the test period?

A strategy with great average returns but a 50% maximum drawdown is practically unusable. You wouldn't be able to hold through the drawdown mentally, and even if you could, the drawdown math means you need a 100% return to recover.

**Rule of thumb**: maximum drawdown should be less than 2x the strategy's average annual return. A 15% annual return strategy with a 30% max drawdown is borderline. A 15% return strategy with a 50% max drawdown is unacceptable.

### Check 7: Trade Distribution

Are the returns dominated by a few outlier trades, or spread across many trades?

If 80% of the backtest's profit came from 3 trades, the strategy isn't really profitable — it's a few lucky calls with a lot of noise. A robust strategy produces profit across many trades without excessive dependence on outliers.

---

## The Walk-Forward Approach: The Gold Standard

The most honest form of backtesting is walk-forward testing. Here's how it works:

**Step 1**: Divide historical data into multiple non-overlapping periods.
- Period A: 2015-2018 (training)
- Period B: 2019-2020 (validation)
- Period C: 2021-2022 (test)
- Period D: 2023-present (live)

**Step 2**: Develop the strategy using only Period A data. Optimize parameters, test ideas, iterate.

**Step 3**: Test the finalized strategy (no further changes) on Period B. Does it still work? If yes, proceed. If no, the strategy was overfit to Period A.

**Step 4**: If Period B confirms, test on Period C (never previously seen). Does it still work? If yes, proceed. If no, you have two failure modes out of three tests — the strategy is likely not robust.

**Step 5**: If Periods B and C both confirm, run the strategy live on Period D with small position sizes for additional validation.

This process is rigorous because you never "see" the validation/test data when developing the strategy. Any performance on those periods is honest out-of-sample performance, not overfit backtest performance.

**The reality**: most strategies that survive walk-forward testing have real edge. Most strategies that look great in simple backtests but fail walk-forward testing are overfit noise.

**The cost**: walk-forward testing requires more data and more discipline. Most retail traders don't do it because it's tedious and often shows their "winning" strategies are actually mediocre. But it's the only honest way to test whether you have real edge.

---

## The Honest Conclusion About Backtesting

Backtesting is useful for one purpose and misused for another.

### The Useful Purpose

Backtesting is useful for **disproving strategies**. If a strategy doesn't work in backtest, it probably won't work live. You can eliminate bad ideas quickly and cheaply through testing.

### The Misused Purpose

Backtesting is commonly used (incorrectly) to **prove strategies work**. But backtesting cannot prove future performance. A working backtest is necessary but not sufficient evidence of real edge.

### The Practical Use

For retail traders, backtesting should serve two functions:

1. **Sanity check**: If a strategy idea doesn't work on historical data, don't bother trading it live. Most strategies fail this test and can be discarded quickly.

2. **Parameter calibration**: Among strategies that do work, backtesting helps choose reasonable parameters (without over-optimizing). Use simple parameters that are robust across different time periods.

But for confidence that a strategy will work live, backtesting is inadequate. You need:
- Walk-forward testing
- Out-of-sample validation
- Live paper trading to verify execution
- Gradual transition to live trading with small positions
- Ongoing monitoring to detect degradation

---

## The Marketing Red Flags

Here's a checklist for evaluating claims about trading strategies:

**Red flag 1**: "Win rate of 90%+"
Very high win rates are almost always misleading. Either the strategy has tiny wins and catastrophic losses, or the backtest is flawed. Real profitable strategies typically have 40-60% win rates.

**Red flag 2**: "Returns of 200% per year"
Triple-digit returns are not sustainable at any scale. Even the best hedge funds average 15-25% annually. A service promising 200% returns is either fraudulent or would have to close to new clients immediately (which they don't — because the returns don't exist).

**Red flag 3**: No drawdown information
Real strategies have drawdowns. If a service shows only cumulative returns without drawdown periods, they're hiding the bad parts. Always ask for max drawdown and recovery time.

**Red flag 4**: Guaranteed results
No strategy guarantees results. The use of words like "guaranteed," "proven," or "foolproof" is a marketing red flag, not a legal commitment.

**Red flag 5**: No mention of live trading results
Backtested results should be accompanied by live trading results if the strategy has been tested. If the service only shows backtests, they either haven't traded it live or the live results were worse than the backtest.

**Red flag 6**: Sold as a "system" without strategic detail
Strategies that are sold without explaining the logic or rationale are typically black boxes. You can't evaluate what you can't see. Be especially skeptical of "proprietary" systems with no disclosure.

---

## The Realistic Expectation

Here's what realistic trading performance looks like:

- **Annual return**: 10-25% for good strategies after costs
- **Win rate**: 40-60% (depends on strategy type)
- **Maximum drawdown**: 15-30%
- **Number of losing months**: 3-5 per year is normal
- **Consecutive losing trades**: 5-10 in a row is normal
- **Recovery time from drawdowns**: weeks to months

Anything dramatically better than this should trigger skepticism. Either the sample size is too small to conclude, the backtest has issues, or the strategy hasn't been tested on enough different market conditions.

Real profitable trading is modestly profitable, not spectacularly so. The compounding effect over years is what generates wealth — not individual trades or months of astronomical returns. The traders and strategies promising otherwise are almost always selling something other than honest performance.

---

## The Meta-Lesson

Backtesting reflects the broader epistemic challenge in trading: it's easy to find patterns in past data, hard to know which patterns will continue. Most patterns don't continue. A few do.

The discipline to distinguish real patterns from noise requires:
- Skepticism about your own findings
- Willingness to test on unseen data
- Acceptance that most strategy ideas don't work
- Realistic expectations for even good strategies
- Honesty about the limits of what historical data can tell you

Traders who approach backtesting with this epistemic discipline produce better strategies and avoid expensive failures. Traders who treat backtests as proof of future performance are perpetually disappointed when live trading reveals the gap between historical fit and forward prediction.

Backtesting isn't useless. It's just not what most people think it is. Used correctly, it's a tool for disproving ideas and calibrating approaches. Used incorrectly, it's a mechanism for self-deception and marketing fraud.

Know the difference.

---

*AlphaBreak's backtesting engine uses walk-forward validation with out-of-sample testing, and our 854,000+ trade historical database includes point-in-time data that eliminates survivorship bias. We report results with realistic transaction costs and full drawdown analysis — so you see honest performance rather than optimized fantasy.*

*Try AlphaBreak free →*
