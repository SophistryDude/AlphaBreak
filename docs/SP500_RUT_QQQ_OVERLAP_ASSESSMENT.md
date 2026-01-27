# S&P 500, Russell 2000, and QQQ (Nasdaq-100) Overlap Assessment

## Purpose

Assess index composition overlap and feature independence to determine whether using
all three indices (S&P 500, RUT, QQQ) as prediction model features introduces
redundancy or provides complementary information.

---

## 1. Index Composition

| Index | Constituents | Market Cap Coverage | Segment |
|-------|-------------|--------------------:|---------|
| S&P 500 (^GSPC) | ~500 stocks | ~80% of US equity market | Large-cap |
| Russell 2000 (^RUT) | ~2,000 stocks | ~7% of US equity market | Small-cap |
| Nasdaq-100 / QQQ | ~100 stocks | ~40% of Nasdaq composite | Large-cap tech/growth |

### Overlap Matrix

| Pair | Overlap |
|------|---------|
| S&P 500 vs RUT | **Zero** -- Russell 2000 is explicitly the small-cap complement to the Russell 1000 (large-cap). No S&P 500 stock appears in RUT. |
| S&P 500 vs QQQ | **~85-90%** -- Nearly all QQQ constituents are also S&P 500 members. QQQ excludes financials and includes only Nasdaq-listed companies. |
| RUT vs QQQ | **Negligible** -- Different market cap segments (small-cap vs mega-cap tech). |

---

## 2. Why All Three Provide Value

Despite the high constituent overlap between S&P 500 and QQQ, their **return patterns
diverge** during regime changes. Each index captures different market dynamics:

### S&P 500 (Broad Market Benchmark)
- Represents the overall large-cap US equity market
- Balanced across all sectors (tech, healthcare, financials, energy, etc.)
- Most liquid benchmark; institutional positioning reference
- Use case: Baseline market trend and risk appetite

### Russell 2000 (Small-Cap Risk Appetite)
- **Zero overlap** with S&P 500 -- fully independent constituent set
- Small-cap stocks are more sensitive to:
  - Credit conditions (higher leverage, less cash reserves)
  - Domestic economic outlook (less international revenue)
  - Risk-on/risk-off shifts (first to sell in risk-off, first to rally in risk-on)
- The **RUT-to-S&P spread** is a well-known regime shift indicator:
  - RUT outperforming S&P = risk-on (bullish breadth)
  - RUT underperforming S&P = risk-off (flight to quality)
- Use case: Risk appetite gauge, credit stress detection, breadth confirmation

### QQQ / Nasdaq-100 (Tech/Growth Momentum)
- Concentrated in technology, communication, and consumer discretionary
- Excludes financials entirely
- More rate-sensitive than S&P 500 (growth stocks discount future earnings)
- Captures **sector rotation** dynamics:
  - QQQ outperforming S&P = growth momentum / tech leadership
  - QQQ underperforming S&P = value rotation / defensive positioning
- Use case: Sector momentum, rate sensitivity proxy, growth vs value gauge

---

## 3. Feature Independence Analysis

### Correlation with Trend Break Metrics

From our market context analysis (darkpool_options_analysis.py):

| Feature | Correlation with Break Magnitude | p-value |
|---------|--------------------------------:|---------|
| VIX (current) | r = +0.124 | < 0.001 |
| S&P 500 20d return | r = -0.104 | < 0.001 |
| RUT 20d return | r = -0.091 | < 0.001 |
| QQQ 20d return | r = -0.094 | < 0.001 |

Key observations:
- All three indices have **statistically significant** but **moderate** correlations
- S&P 500 has the strongest negative correlation (larger market decline -> larger break magnitude)
- RUT and QQQ provide **incremental information** despite being correlated with S&P
- The **differences** between index correlations reveal regime-specific patterns

### Cross-Index Correlation

Under normal conditions, S&P 500 and QQQ have a daily return correlation of ~0.90-0.95.
However, during regime transitions this drops significantly:

| Regime | S&P-QQQ Correlation | S&P-RUT Correlation |
|--------|--------------------:|--------------------:|
| Normal volatility | ~0.93 | ~0.85 |
| Volatility expansion | ~0.80-0.85 | ~0.65-0.75 |
| Sector rotation | ~0.70-0.80 | ~0.60-0.70 |
| Credit stress | ~0.85 | ~0.50-0.60 |

**It is precisely during regime changes -- when correlations break down -- that having
all three indices provides the most value for trend break prediction.**

---

## 4. Our System's Tracked Universe

Our database tracks ~461 individual stocks, primarily:
- S&P 500 constituents (fetched from Wikipedia)
- DJIA components
- Additional large-cap stocks

Implications:
- **S&P 500**: Directly represents ~80% of our tracked universe by market cap
- **RUT**: None of our tracked stocks are RUT constituents, but RUT serves as an
  external risk gauge (small-cap risk appetite affects large-cap trend breaks)
- **QQQ**: High overlap with our tracked universe, but QQQ-as-a-feature captures
  the **tech concentration** effect that individual stock indicators miss

---

## 5. Implementation in Our Model

### Market Indices Configuration (populate_market_indices.py)

```python
MARKET_SYMBOLS = [
    '^GSPC',   # S&P 500 Index
    '^DJI',    # Dow Jones Industrial Average
    '^VIX',    # CBOE Volatility Index
    '^RUT',    # Russell 2000 Index  (added)
    'QQQ',     # Invesco QQQ Trust   (added)
    'ES=F',    # E-mini S&P 500 Futures
    'SH',      # ProShares Short S&P 500
    'PSQ',     # ProShares Short QQQ
    'DOG',     # ProShares Short Dow 30
    'VXX',     # iPath S&P 500 VIX Short-Term Futures ETN
]
```

### Features Derived from Each Index

For each market instrument, the system calculates technical indicators
(RSI, MACD, Stochastic, CCI, Bollinger Bands, etc.) and tests them
against individual stock trend breaks. Additionally, market regime features
are computed:

- **VIX regime**: High (>25), Normal (15-25), Low (<15)
- **S&P 500 trend**: Uptrend/Downtrend (20d return sign)
- **Futures premium**: Contango/backwardation (ES=F vs ^GSPC)
- **RUT-S&P spread**: Small-cap relative strength (risk-on/off gauge)
- **QQQ-S&P spread**: Tech momentum relative to broad market

---

## 6. Recommendation

**Use all three indices as features.** While S&P 500 and QQQ have high constituent
overlap, they capture different market dynamics:

1. **S&P 500**: Broad market direction and overall risk level
2. **Russell 2000**: Small-cap risk appetite (zero constituent overlap, independent signal)
3. **QQQ**: Tech/growth momentum and sector rotation dynamics

The moderate inter-index correlations (~0.85-0.93 in normal times) confirm they are
**related but not redundant**. The correlations break down during exactly the market
conditions that produce the largest trend breaks -- which is when feature diversity
matters most.

For the prediction model, recommended derived features:
- Individual index returns (1d, 5d, 20d)
- Index technical indicators (RSI, MACD, BB on each)
- **Cross-index spreads**: RUT-S&P (risk appetite), QQQ-S&P (sector momentum)
- **Correlation breakdowns**: Rolling 20d correlation between index pairs
