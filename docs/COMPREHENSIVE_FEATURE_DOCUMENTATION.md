# COMPREHENSIVE FEATURE ENGINEERING DOCUMENTATION
## Securities Prediction Model - Technical Indicator Features

**Date:** 2026-01-16
**Purpose:** Complete reference for all engineered features across technical indicators
**Use Case:** Machine Learning model training for securities trend prediction

---

## TABLE OF CONTENTS
1. [Overview](#overview)
2. [Technical Indicators Analyzed](#technical-indicators-analyzed)
3. [Feature Categories](#feature-categories)
4. [Feature Definitions](#feature-definitions)
5. [Implementation Guide](#implementation-guide)
6. [Feature Applicability Matrix](#feature-applicability-matrix)

---

## OVERVIEW

This document catalogs all engineered features that can be extracted from technical indicator analysis for machine learning-based securities prediction. Features are organized into 10 categories, each capturing different aspects of trend behavior and indicator performance.

### Feature Engineering Purpose
- **Input:** Trend ranges with indicator values at start/end points
- **Output:** Rich feature set for ML model training
- **Goal:** Predict which indicators accurately forecast trend reversals

---

## TECHNICAL INDICATORS ANALYZED

Based on your codebase, the following 23 technical indicators are included:

### Momentum Indicators
1. **MACD** - Moving Average Convergence Divergence
2. **RSI** - Relative Strength Index
3. **RoC** - Rate of Change
4. **Stoch** - Stochastic Oscillator

### Trend Indicators
5. **ADX** - Average Directional Index
6. **Super** - Supertrend
7. **Para_SAR** - Parabolic SAR
8. **MAL** - Moving Averages (Custom)

### Volume Indicators
9. **OBV** - On Balance Volume
10. **TLEV** - Trader's Lion Enhanced Volume
11. **VPTI** - Volume Price Trend Indicator
12. **MFI** - Money Flow Index
13. **CMFI** - Chaikin Money Flow Indicator
14. **Acc_Dis** - Accumulation/Distribution
15. **EoM** - Ease of Movement
16. **VaP** - Volume at Price
17. **VWAP** - Volume Weighted Average Price

### Volatility Indicators
18. **BBands** - Bollinger Bands
19. **KChan** - Keltner Channel
20. **DonChan** - Donchian Channel
21. **ATR** - Average True Range

### Breadth Indicators (Market-wide)
22. **Rel_Str** - Relative Strength
23. **Custom Breadth** - Percent above MA, Advance/Decline

---

## FEATURE CATEGORIES

### Category 1: Basic Temporal Features (6 features)
Time-based measurements of the trend

### Category 2: Absolute Change Features (3 features)
Raw differences between start and end values

### Category 3: Normalized/Relative Features (5 features)
Percentage-based and scaled measurements

### Category 4: Volatility Features (4 features)
Measures of stability and fluctuation

### Category 5: Volume Features (5 features)
Trading volume analysis and confirmation

### Category 6: Momentum Features (4 features)
Acceleration and rate-of-change metrics

### Category 7: Pattern Features (4 features)
Shape and quality of the trend

### Category 8: Sequential Context Features (5 features)
Historical and positional information

### Category 9: Reversal Characteristics (3 features)
Properties of the trend reversal points

### Category 10: Indicator-Specific Features (8 features)
Features unique to each indicator type

**TOTAL: 47 FEATURES PER INDICATOR**

---

## FEATURE DEFINITIONS

### CATEGORY 1: BASIC TEMPORAL FEATURES

#### 1.1 trend_length
**Definition:** Duration of the trend in calendar days
**Formula:** `(end_date - start_date).days`
**Data Type:** Integer
**Range:** [1, ∞)
**Applicability:** ALL indicators
**Use Case:** Longer trends may be more significant
**Example:** 45 days

#### 1.2 trading_days_count
**Definition:** Number of actual trading days (excludes weekends/holidays)
**Formula:** `count(trading_days between start_date and end_date)`
**Data Type:** Integer
**Range:** [1, ∞)
**Applicability:** ALL indicators
**Use Case:** More accurate than calendar days for market analysis
**Example:** 32 trading days

#### 1.3 trend_start_timestamp
**Definition:** Unix timestamp of trend start
**Formula:** `start_date.timestamp()`
**Data Type:** Float
**Applicability:** ALL indicators
**Use Case:** Time-series analysis, seasonality detection

#### 1.4 day_of_week_start
**Definition:** Day of week when trend started (0=Monday, 6=Sunday)
**Formula:** `start_date.dayofweek`
**Data Type:** Integer
**Range:** [0, 6]
**Applicability:** ALL indicators
**Use Case:** Detect day-of-week effects (e.g., "Monday effect")

#### 1.5 month_of_year_start
**Definition:** Month when trend started (1=January, 12=December)
**Formula:** `start_date.month`
**Data Type:** Integer
**Range:** [1, 12]
**Applicability:** ALL indicators
**Use Case:** Seasonal patterns (January effect, sell in May, etc.)

#### 1.6 crosses_quarter_end
**Definition:** Boolean indicating if trend crosses fiscal quarter boundary
**Formula:** `(start_date.quarter != end_date.quarter)`
**Data Type:** Boolean
**Applicability:** ALL indicators
**Use Case:** Quarterly reporting effects on trading

---

### CATEGORY 2: ABSOLUTE CHANGE FEATURES

#### 2.1 price_distance
**Definition:** Absolute price change from start to end
**Formula:** `end_price - start_price`
**Data Type:** Float
**Range:** (-∞, ∞)
**Applicability:** ALL indicators
**Use Case:** Raw magnitude of price movement
**Example:** $15.50 (stock rose $15.50)
**Note:** Can be positive (upward) or negative (downward)

#### 2.2 signal_difference
**Definition:** Change in indicator's signal line value
**Formula:** `end_signal - start_signal`
**Data Type:** Float
**Range:** Depends on indicator
**Applicability:** Indicators with signal lines (MACD, Stoch, etc.)
**Use Case:** Measure how much indicator changed
**Example:** For MACD: 2.5 (signal line increased by 2.5)

#### 2.3 hist_difference
**Definition:** Change in indicator's histogram value
**Formula:** `end_hist - start_hist`
**Data Type:** Float
**Range:** Depends on indicator
**Applicability:** Indicators with histograms (MACD primarily)
**Use Case:** Measure histogram momentum change

---

### CATEGORY 3: NORMALIZED/RELATIVE FEATURES

#### 3.1 price_distance_percent
**Definition:** Percentage price change
**Formula:** `(end_price - start_price) / start_price * 100`
**Data Type:** Float
**Range:** (-100, ∞)
**Applicability:** ALL indicators
**Use Case:** Scale-independent price change (5% is comparable across all stocks)
**Example:** 12.5% (stock rose 12.5%)
**CRITICAL:** This is essential for cross-stock comparison

#### 3.2 signal_difference_percent
**Definition:** Percentage change in signal line
**Formula:** `signal_difference / abs(start_signal) * 100`
**Data Type:** Float
**Applicability:** Indicators with signal lines
**Use Case:** Relative signal change
**Note:** Handle division by zero when start_signal = 0

#### 3.3 hist_difference_percent
**Definition:** Percentage change in histogram
**Formula:** `hist_difference / abs(start_hist) * 100`
**Data Type:** Float
**Applicability:** Indicators with histograms
**Use Case:** Relative histogram change

#### 3.4 trend_velocity
**Definition:** Price change per day (speed of trend)
**Formula:** `price_distance / trend_length`
**Data Type:** Float
**Range:** (-∞, ∞)
**Applicability:** ALL indicators
**Use Case:** Fast-moving vs slow-moving trends
**Example:** $0.85/day (stock gaining $0.85 per day on average)
**CRITICAL:** Key feature for momentum analysis

#### 3.5 start_end_ratio
**Definition:** Multiplicative price change
**Formula:** `end_price / start_price`
**Data Type:** Float
**Range:** (0, ∞)
**Applicability:** ALL indicators
**Use Case:** Useful for log-space analysis, compounding calculations
**Example:** 1.15 (stock is 115% of starting price = 15% gain)

---

### CATEGORY 4: VOLATILITY FEATURES

#### 4.1 price_volatility
**Definition:** Standard deviation of prices during the trend
**Formula:** `std(prices[start_date:end_date])`
**Data Type:** Float
**Range:** [0, ∞)
**Applicability:** ALL indicators
**Use Case:** Measure trend stability
**Example:** 2.3 (prices fluctuated with std dev of $2.30)
**CRITICAL:** High volatility = risky/choppy trend

#### 4.2 volume_volatility
**Definition:** Standard deviation of volume during the trend
**Formula:** `std(volume[start_date:end_date])`
**Data Type:** Float
**Range:** [0, ∞)
**Applicability:** ALL indicators
**Use Case:** Volume consistency
**Example:** 1,500,000 shares

#### 4.3 signal_volatility
**Definition:** Standard deviation of signal values during trend
**Formula:** `std(signal[start_date:end_date])`
**Data Type:** Float
**Applicability:** Indicators with signal lines
**Use Case:** Indicator stability

#### 4.4 trend_smoothness
**Definition:** Ratio of volatility to total price change
**Formula:** `price_volatility / abs(price_distance)`
**Data Type:** Float
**Range:** [0, ∞)
**Applicability:** ALL indicators
**Use Case:** Low = smooth trend, High = choppy trend
**Example:** 0.15 (very smooth), 2.5 (very choppy)
**CRITICAL:** Smooth trends are more predictable

---

### CATEGORY 5: VOLUME FEATURES

#### 5.1 avg_volume
**Definition:** Average trading volume during the trend
**Formula:** `mean(volume[start_date:end_date])`
**Data Type:** Float
**Range:** [0, ∞)
**Applicability:** ALL indicators
**Use Case:** Volume confirmation of price movement
**Example:** 5,000,000 shares/day
**CRITICAL:** "Volume confirms price" - classic TA principle

#### 5.2 volume_trend
**Definition:** Percentage change in volume from start to end
**Formula:** `(end_volume - start_volume) / start_volume * 100`
**Data Type:** Float
**Applicability:** ALL indicators
**Use Case:** Increasing volume = stronger trend
**Example:** 45% (volume increased 45% during trend)

#### 5.3 volume_price_correlation
**Definition:** Correlation between volume and price during trend
**Formula:** `correlation(volume[start:end], price[start:end])`
**Data Type:** Float
**Range:** [-1, 1]
**Applicability:** ALL indicators
**Use Case:** Positive correlation = volume confirms price
**Example:** 0.75 (strong positive correlation)
**CRITICAL:** Divergence signals potential reversal

#### 5.4 relative_volume
**Definition:** Average volume compared to historical average
**Formula:** `avg_volume / historical_avg_volume`
**Data Type:** Float
**Range:** (0, ∞)
**Applicability:** ALL indicators
**Use Case:** Unusual volume detection
**Example:** 2.5 (volume is 2.5x normal)

#### 5.5 total_volume
**Definition:** Cumulative volume during the trend
**Formula:** `sum(volume[start_date:end_date])`
**Data Type:** Float
**Applicability:** ALL indicators
**Use Case:** Total participation in the trend

---

### CATEGORY 6: MOMENTUM FEATURES

#### 6.1 price_acceleration
**Definition:** Change in rate of price change (2nd derivative)
**Formula:** `(slope_2nd_half - slope_1st_half)`
**Data Type:** Float
**Range:** (-∞, ∞)
**Applicability:** ALL indicators
**Use Case:** Positive = accelerating, Negative = decelerating
**Example:** 0.15 (trend is speeding up)
**CRITICAL:** Accelerating trends have momentum

#### 6.2 signal_acceleration
**Definition:** Change in signal line momentum
**Formula:** `(signal_change_2nd_half - signal_change_1st_half)`
**Data Type:** Float
**Applicability:** Indicators with signal lines
**Use Case:** Indicator momentum analysis

#### 6.3 drawdown_during_trend
**Definition:** Maximum price decline from peak during trend
**Formula:** `max(price[start:end]) - min(price[start:end])`
**Data Type:** Float
**Range:** [0, ∞)
**Applicability:** ALL indicators
**Use Case:** Risk measure - how much retracement occurred
**Example:** $8.50 (price dropped $8.50 at worst point)

#### 6.4 time_to_peak
**Definition:** Days from start to the highest price point
**Formula:** `argmax(price[start:end]) - start_date`
**Data Type:** Integer
**Applicability:** ALL indicators
**Use Case:** Early peak vs late peak tells different stories
**Example:** 12 days (peaked early in the trend)

---

### CATEGORY 7: PATTERN FEATURES

#### 7.1 trend_linearity
**Definition:** R-squared of linear regression on prices
**Formula:** `R²(linear_regression(price ~ time))`
**Data Type:** Float
**Range:** [0, 1]
**Applicability:** ALL indicators
**Use Case:** 1.0 = perfectly linear, 0 = random walk
**Example:** 0.92 (very linear trend)
**CRITICAL:** Linear trends are more predictable

#### 7.2 number_of_reversals_within
**Definition:** Count of minor reversals during the trend
**Formula:** `count(local_extrema(price[start:end]))`
**Data Type:** Integer
**Range:** [0, ∞)
**Applicability:** ALL indicators
**Use Case:** Smooth vs erratic trend
**Example:** 3 (had 3 minor reversals)

#### 7.3 max_consecutive_days_same_direction
**Definition:** Longest streak of consecutive up or down days
**Formula:** `max(consecutive_streaks(daily_returns))`
**Data Type:** Integer
**Applicability:** ALL indicators
**Use Case:** Trend persistence
**Example:** 8 days (8 consecutive up days)

#### 7.4 trend_strength
**Definition:** Combined magnitude measure
**Formula:** `trend_length * abs(price_distance)`
**Data Type:** Float
**Range:** [0, ∞)
**Applicability:** ALL indicators
**Use Case:** Long + large move = strong trend
**Example:** 675 (45 days × $15 move)

---

### CATEGORY 8: SEQUENTIAL CONTEXT FEATURES

#### 8.1 trend_sequence_number
**Definition:** Position in the overall sequence of trends
**Formula:** `index + 1`
**Data Type:** Integer
**Range:** [1, ∞)
**Applicability:** ALL indicators
**Use Case:** Early trends vs late trends in dataset
**Example:** 23 (this is the 23rd trend detected)

#### 8.2 previous_trend_direction
**Definition:** Direction of the previous trend
**Formula:** `df['trend_direction'].shift(1)`
**Data Type:** Categorical ('upward', 'downward', NaN)
**Applicability:** ALL indicators
**Use Case:** Sequential pattern detection
**Example:** 'downward' (previous trend was down)
**CRITICAL:** Trends don't exist in isolation

#### 8.3 time_since_last_reversal
**Definition:** Duration of the previous trend
**Formula:** `df['trend_length'].shift(1)`
**Data Type:** Float
**Range:** [0, ∞) or NaN
**Applicability:** ALL indicators
**Use Case:** Temporal spacing of trends
**Example:** 32 days (previous trend lasted 32 days)

#### 8.4 alternation_pattern
**Definition:** Boolean indicating normal peak-trough-peak pattern
**Formula:** `(current_reversal != previous_reversal)`
**Data Type:** Boolean
**Applicability:** ALL indicators
**Use Case:** Detect unusual patterns (consecutive peaks/troughs)
**Example:** True (normal alternation)

#### 8.5 trend_direction_match
**Definition:** Does current trend match previous direction?
**Formula:** `(trend_direction == previous_trend_direction)`
**Data Type:** Boolean
**Applicability:** ALL indicators
**Use Case:** Continuation vs reversal patterns
**Example:** False (direction reversed)

---

### CATEGORY 9: REVERSAL CHARACTERISTICS

#### 9.1 start_reversal_magnitude
**Definition:** Sharpness of the starting reversal point
**Formula:** `min(|trend[i] - trend[i-1]|, |trend[i] - trend[i+1]|)`
**Data Type:** Float
**Range:** [0, ∞)
**Applicability:** ALL indicators
**Use Case:** Sharp reversals indicate strong momentum change
**Example:** 5.2 (very sharp reversal)

#### 9.2 end_reversal_magnitude
**Definition:** Sharpness of the ending reversal point
**Formula:** Same as start_reversal_magnitude
**Data Type:** Float
**Applicability:** ALL indicators
**Use Case:** How strongly did the trend end?

#### 9.3 reversal_asymmetry
**Definition:** Difference between start and end reversal magnitudes
**Formula:** `abs(start_magnitude - end_magnitude)`
**Data Type:** Float
**Range:** [0, ∞)
**Applicability:** ALL indicators
**Use Case:** Symmetric vs asymmetric reversals
**Example:** 2.1 (reversals differ in sharpness)

---

### CATEGORY 10: INDICATOR-SPECIFIC FEATURES

#### 10.1 signal_histogram_divergence
**Definition:** Do signal and histogram disagree on direction?
**Formula:** `(signal_difference > 0) != (hist_difference > 0)`
**Data Type:** Boolean
**Applicability:** MACD, indicators with signal + histogram
**Use Case:** Divergence often precedes reversals
**Example:** True (divergence detected)
**CRITICAL:** Classic technical analysis signal

#### 10.2 zero_line_crosses
**Definition:** Number of times signal/histogram crossed zero
**Formula:** `count(sign_changes(signal[start:end]))`
**Data Type:** Integer
**Range:** [0, ∞)
**Applicability:** Oscillators (MACD, RSI, Stoch)
**Use Case:** Bullish/bearish transitions

#### 10.3 indicator_extreme_start
**Definition:** Is indicator at extreme level at start?
**Formula:** `(RSI < 30 or RSI > 70) for RSI, similar for others`
**Data Type:** Boolean
**Applicability:** Bounded oscillators (RSI, Stoch, MFI)
**Use Case:** Overbought/oversold conditions
**Example:** True (RSI was at 75 = overbought)

#### 10.4 indicator_extreme_end
**Definition:** Is indicator at extreme level at end?
**Formula:** Same logic as indicator_extreme_start
**Data Type:** Boolean
**Applicability:** Bounded oscillators
**Use Case:** Exit from extreme zones

#### 10.5 signal_histogram_ratio
**Definition:** Relative strength between signal and histogram
**Formula:** `signal_value / histogram_value`
**Data Type:** Float
**Applicability:** MACD
**Use Case:** Component relationship analysis

#### 10.6 directional_indicator_spread
**Definition:** Difference between +DI and -DI
**Formula:** `PDI - NDI`
**Data Type:** Float
**Applicability:** ADX
**Use Case:** Trend direction strength

#### 10.7 band_width
**Definition:** Distance between upper and lower bands
**Formula:** `upper_band - lower_band`
**Data Type:** Float
**Applicability:** BBands, KChan, DonChan
**Use Case:** Volatility measure via bands
**Example:** $12.50 (bands are $12.50 apart)

#### 10.8 price_band_position
**Definition:** Where price is relative to bands (0=lower, 0.5=middle, 1=upper)
**Formula:** `(price - lower_band) / (upper_band - lower_band)`
**Data Type:** Float
**Range:** [0, 1] typically, can exceed for breakouts
**Applicability:** BBands, KChan, DonChan
**Use Case:** Overbought/oversold relative to bands
**Example:** 0.85 (price near upper band)

---

### ACCURACY AND VALIDATION FEATURES (Already in your code)

#### accuracy
**Definition:** Indicator prediction accuracy score
**Formula:** `1.0 if both correct, 0.5 if one correct, 0.0 if both wrong`
**Data Type:** Float
**Range:** [0, 0.5, 1.0]
**Applicability:** ALL indicators

#### accuracy_percentage
**Definition:** Accuracy as percentage
**Formula:** `accuracy * 100`
**Data Type:** Float
**Range:** [0, 50, 100]
**Applicability:** ALL indicators

---

## IMPLEMENTATION GUIDE

### Step 1: Data Requirements

To calculate all features, you need:
- **Price data:** Open, High, Low, Close for each day in the trend range
- **Volume data:** Volume for each day in the trend range
- **Indicator data:** Signal line, histogram, or other indicator-specific values
- **Trend metadata:** start_date, end_date, trend_direction, reversal_types

### Step 2: Feature Calculation Order

1. **Basic features first:** trend_length, price_distance, etc.
2. **Normalized features:** Depend on basic features
3. **Statistical features:** Require full price/volume series
4. **Sequential features:** Require previous rows
5. **Indicator-specific:** Last, as they're conditional

### Step 3: Handling Missing Data

- Use `.fillna()` for sequential features (first row has no previous)
- Use `try/except` for division by zero in percentage calculations
- Use conditional logic for indicator-specific features

### Step 4: Feature Scaling for ML

After engineering, normalize features:
- **StandardScaler:** For normally distributed features
- **MinMaxScaler:** For bounded features
- **RobustScaler:** For features with outliers

---

## FEATURE APPLICABILITY MATRIX

See companion CSV file: `feature_indicator_matrix.csv`

The matrix shows which of the 47 features apply to each of the 23 technical indicators.

**Legend:**
- ✓ = Feature fully applicable
- P = Partially applicable (requires adaptation)
- ✗ = Not applicable
- S = Indicator-specific (unique to this indicator)

---

## SUMMARY STATISTICS

- **Total Features Defined:** 47
- **Universal Features (apply to all indicators):** 28
- **Conditional Features (specific indicators only):** 19
- **Critical Features (highest ML importance):** 12
  - price_distance_percent
  - trend_velocity
  - price_volatility
  - trend_smoothness
  - avg_volume
  - volume_price_correlation
  - price_acceleration
  - trend_linearity
  - previous_trend_direction
  - signal_histogram_divergence
  - start_reversal_magnitude
  - trend_strength

---

## RECOMMENDED FEATURE SETS BY USE CASE

### Minimal (Quick Prototyping) - 10 features
1. trend_length
2. price_distance_percent
3. trend_velocity
4. price_volatility
5. avg_volume
6. signal_difference
7. hist_difference
8. signal_histogram_divergence
9. accuracy
10. trend_direction (label)

### Standard (Production Model) - 25 features
All minimal features plus:
11. trading_days_count
12. trend_smoothness
13. volume_trend
14. volume_price_correlation
15. price_acceleration
16. trend_linearity
17. previous_trend_direction
18. time_since_last_reversal
19. start_reversal_magnitude
20. end_reversal_magnitude
21. drawdown_during_trend
22. relative_volume
23. trend_strength
24. number_of_reversals_within
25. signal_volatility

### Comprehensive (Maximum Performance) - All 47 features
Use all defined features for maximum model performance

---

## NEXT STEPS

1. Review the companion CSV matrix (`feature_indicator_matrix.csv`)
2. Implement feature engineering function based on your use case
3. Test on sample data
4. Perform feature importance analysis
5. Refine feature set based on ML results

---

**End of Documentation**
