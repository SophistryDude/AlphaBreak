# Options Pricing: What You're Actually Buying

*Reading time: 22 minutes*

---

## The Problem with How Options Are Taught

Most options education begins with definitions: "A call option gives you the right to buy 100 shares at the strike price before expiration." This is correct but nearly useless. It's like explaining a car by saying "a vehicle that converts gasoline into forward motion."

The definitions don't help you understand what determines whether an option is cheap or expensive, why the same option can lose value even when you're right about direction, or why professional traders obsess over implied volatility rather than price.

To actually understand options, we need to work through three layers:

1. **What you're buying** (the structural reality)
2. **What determines its price** (the constraint system)
3. **What creates opportunity** (the information asymmetry)

---

## Layer 1: What an Option Actually Is

Forget "the right to buy." Here's what you're buying when you purchase a call option:

**You are buying a probability-weighted exposure to upside movement, with a defined maximum loss.**

This is a fundamentally different thing than buying stock. When you buy 100 shares of AAPL at $190, you own a linear instrument — every $1 move in AAPL changes your P&L by exactly $100, regardless of direction.

When you buy a call option, you own a non-linear instrument — your P&L is asymmetric. You can lose at most what you paid (the premium), but you can gain much more. This asymmetry is the product you're purchasing.

### The Insurance Analogy (Taken Seriously)

Options are often compared to insurance. This analogy is more precise than most people realize:

| Insurance | Options |
|-----------|---------|
| Premium paid upfront | Option premium paid upfront |
| Pays out only if event occurs | Pays out only if price moves beyond strike |
| Premium reflects probability of event | Premium reflects probability of exercise |
| Insurance company takes the other side | Option seller takes the other side |
| Higher-risk policies cost more | Higher-volatility options cost more |

The insurance company doesn't know whether *your* house will burn down. But they know the probability across thousands of houses, and they price premiums to profit statistically. Option sellers do the same thing.

This means: **the price of an option is a market-consensus estimate of the probability distribution of future price movements.**

This is not metaphor. It is mathematically literal. You can extract the implied probability distribution from option prices (this is called "risk-neutral density"). The market is constantly voting on what it thinks will happen, and option prices are the ballot.

---

## Layer 2: The Five Forces That Price Options

Options prices are determined by five inputs, each serving a distinct informational function:

### 1. Current Price Relative to Strike (Intrinsic Value)

This is the simplest: how far is the current price from the strike?

- A $190 call on AAPL trading at $195 has $5 of intrinsic value (it's "in the money" by $5)
- A $200 call on AAPL trading at $195 has $0 intrinsic value (it's "out of the money")

Intrinsic value is the floor. An option is always worth at least its intrinsic value. Everything above that is "time value" — and time value is where all the interesting dynamics live.

### 2. Time to Expiration (Theta)

More time = more opportunity for price to move = more valuable option. But this relationship is non-linear:

```
Value decay is proportional to √time, not time.

An option with 64 days remaining is worth roughly 2x
an option with 16 days remaining (because √64/√16 = 8/4 = 2).

NOT 4x, as linear thinking would suggest.
```

**The critical implication**: Time decay accelerates as expiration approaches. An option loses more value in its last week than in its first month. This is why selling options near expiration is profitable on average — you collect accelerating decay.

This isn't a market inefficiency. It's compensation for the seller's risk of being wrong in a compressed timeframe where gamma (directional sensitivity) is highest.

### 3. Implied Volatility (The Price of Uncertainty)

This is the most important and least understood input. Implied volatility (IV) is not a prediction of how much the stock will move. It is:

**The market's current pricing of uncertainty, expressed as an annualized standard deviation.**

An IV of 30% on AAPL means: the market is pricing options as if AAPL will move within a ±30% range over the next year, with 68% probability (one standard deviation).

But here's the key distinction: **IV is a price, not a forecast.**

Just as a house can be overpriced or underpriced relative to its fundamental value, IV can be overpriced or underpriced relative to how much the stock actually moves (realized volatility).

When IV > realized volatility: options are expensive. Sellers profit.
When IV < realized volatility: options are cheap. Buyers profit.

This gap — between what the market charges for uncertainty and what actually materializes — is the primary edge in options trading.

### 4. Interest Rates (Cost of Carry)

Higher interest rates make calls slightly more expensive and puts slightly cheaper. The intuition: buying a call instead of stock lets you invest the remainder at the risk-free rate. Higher rates make this "free lunch" more valuable.

In practice, this effect is small relative to IV. It matters primarily for long-dated options (LEAPS) and professional market-makers managing large portfolios.

### 5. Dividends (Cash Flow)

Expected dividends reduce call values and increase put values. The stock price drops by approximately the dividend amount on the ex-date. Options markets price in known dividends; unexpected dividend changes create edge.

---

## The Black-Scholes Equation: What It Does and Doesn't Do

Black-Scholes is the foundational options pricing model. It is simultaneously:
- The most important formula in options trading
- Known to be technically wrong by everyone who uses it

This isn't contradictory. Here's why:

**What Black-Scholes assumes:**
1. Stock prices follow geometric Brownian motion (log-normal distribution)
2. Volatility is constant over the option's life
3. No transaction costs or taxes
4. Continuous trading is possible
5. No arbitrage opportunities exist

**What reality shows:**
1. Stock prices have fat tails (large moves happen more often than log-normal predicts)
2. Volatility changes constantly (and clusters in time)
3. Transaction costs exist
4. Markets close overnight and on weekends
5. Arbitrage opportunities exist briefly

So why use it? Because **Black-Scholes is the coordinate system**, not the territory. It provides a common language (delta, gamma, theta, vega) for discussing and managing risk. Just as Newtonian mechanics is "wrong" (relativity supersedes it) but perfectly useful for engineering bridges, Black-Scholes is wrong but perfectly useful for managing options positions.

The deviations from Black-Scholes — particularly the "volatility smile" and "volatility skew" — are themselves tradeable information. They tell you where the market disagrees with the model, and those disagreements often have structural explanations (crash risk, earnings events, supply/demand imbalances in specific strikes).

---

## Layer 3: Where Opportunity Exists

Given this framework, where does edge actually come from in options trading?

### 1. Volatility Mispricing

The single largest source of alpha in options is the persistent overpricing of implied volatility relative to realized volatility. On average, IV exceeds RV by 2-4 percentage points across most underlyings, most of the time.

This is not a market inefficiency. It's a risk premium — option buyers pay extra because they're buying insurance, and insurance is worth paying a premium for. But this premium is not constant:

- Before earnings: IV spikes (the market prices in uncertainty about the announcement)
- After earnings: IV collapses ("IV crush") — regardless of direction
- During low-volatility regimes: IV is often too high (the market remembers recent volatility)
- During high-volatility regimes: IV is sometimes too low (the market underestimates tail risk)

### 2. Structural Supply/Demand Imbalances

Certain options are systematically overpriced or underpriced because of non-economic participants:

- **Put protection buying**: Portfolio managers buy index puts for protection, creating structural demand that pushes prices above fair value
- **Covered call selling**: Yield-seeking investors sell calls against holdings, creating structural supply that keeps prices lower
- **Tail hedging**: Some options far out-of-the-money trade at a premium because institutions must hedge catastrophic risk regardless of price

### 3. Event-Driven Dislocations

Around known events (earnings, FDA decisions, FOMC meetings), the market must price binary outcomes. This creates specific, identifiable opportunities:

- **Pre-event**: You can calculate the implied move (from ATM straddle price) and compare it to historical actual moves
- **Post-event**: IV crush creates opportunity in selling strategies if the event is smaller than expected
- **Skew shifts**: The market's fear/greed ratio (put skew vs. call skew) changes around events and sometimes overshoots

---

## Probability of Profit: The Only Metric That Matters

Every options position has a calculable probability of profit. This isn't speculation — it's derived directly from the option's price and the implied volatility:

For a long call: PoP = 1 - N(d2)
For a long put: PoP = N(-d2)

Where d2 is derived from Black-Scholes inputs.

**What this means practically:**

- An ATM call typically has ~45-48% PoP (less than 50% because you must overcome the premium paid)
- An OTM call at 1 standard deviation has ~16% PoP (the stock must move significantly)
- A short ATM put (selling a put) has ~52-55% PoP
- A credit spread has PoP directly related to the width and strikes chosen

**The fundamental trade-off**: Higher PoP strategies have lower maximum profit. Lower PoP strategies have higher maximum profit. There is no free lunch — but there are intelligent selections based on your thesis about volatility, direction, and timing.

---

## The Practitioner's Decision Framework

Given everything above, here's how to think about options decisions:

### Before any trade, answer:

1. **What is my thesis?** (Direction? Volatility? Time decay? Event?)
2. **Is IV relatively high or low?** (Compared to historical, compared to recent realized vol)
3. **What is the market pricing vs. what do I believe?** (Implied move vs. my expected move)
4. **What is my probability of profit?** (Not "can I make money" but "what's the mathematical probability")
5. **What is the maximum I can lose, and am I comfortable with that?** (Define risk before reward)

### Strategy selection based on thesis:

| Your belief | IV is high | IV is low |
|-------------|-----------|----------|
| Bullish + confident | Sell put spread | Buy call or call spread |
| Bullish + uncertain | Sell put | Buy call spread (limited risk) |
| Bearish + confident | Sell call spread | Buy put or put spread |
| Neutral + high IV | Iron condor, short straddle | Avoid (no edge) |
| Don't know | Don't trade options | Don't trade options |

The last row is the most important. Options magnify both edge and ignorance. Trading options without a specific thesis about volatility is guaranteed to lose money over time, because you're paying for time decay without a compensating informational advantage.

---

## Conclusion: Options as Probability Instruments

Options aren't gambling instruments. They aren't lottery tickets. They're precision tools for expressing probabilistic beliefs about future uncertainty.

The professionals who consistently profit from options aren't smarter about predicting direction. They're more disciplined about:
- Identifying when the market's probability estimate (implied vol) diverges from reality
- Structuring positions that profit from specific scenarios while defining worst-case losses
- Managing positions actively as new information arrives
- Sizing positions so that the inevitable losses don't destroy the statistical edge

If you can't articulate why an option is mispriced — what specific probability the market is getting wrong — you don't have a trade. You have a bet.

---

*AlphaBreak calculates Probability of Profit, IV percentile, and fair value for every option in real-time, so you can focus on thesis construction rather than math. Our AI scoring system identifies when implied volatility diverges from historical norms — the primary source of options edge.*

*Try AlphaBreak free →*
