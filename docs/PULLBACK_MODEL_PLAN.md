# Pullback/Continuation Model — Plan of Action

## Goal

After a trend break is detected, predict:
1. Whether price action represents a **pullback** (temporary retracement before continuation) or a **full reversal**
2. The **candlestick count** (duration) of the pullback
3. The **depth** of the pullback (% retracement of prior move)

---

## Phase 1 — Database Schema

Create `kubernetes/schema_pullback_outcomes.sql` with:

### New Table: `trend_break_outcomes`

| Column | Type | Purpose |
|--------|------|---------|
| `ticker` | VARCHAR(10) | Stock symbol |
| `break_timestamp` | TIMESTAMPTZ | When the break occurred |
| `timeframe` | VARCHAR(10) | daily, 1hour, 5min, 1min |
| `break_type` | VARCHAR(10) | peak or trough |
| `pullback_confirmed` | BOOLEAN | Did a pullback occur? |
| `pullback_depth_pct` | DECIMAL(8,4) | % of prior trend retraced |
| `pullback_duration_candlesticks` | INTEGER | Number of candles in pullback |
| `pullback_low_price` | DECIMAL(12,4) | Extreme point of pullback |
| `time_to_pullback_end` | INTEGER | Periods until pullback ended |
| `retracement_ratio` | DECIMAL(8,4) | Pullback size / prior trend size |
| `touched_fib_382` | BOOLEAN | Hit 38.2% Fibonacci level |
| `touched_fib_500` | BOOLEAN | Hit 50% Fibonacci level |
| `touched_fib_618` | BOOLEAN | Hit 61.8% Fibonacci level |
| `touched_prior_support` | BOOLEAN | Pulled back to prior swing low/high |
| `is_continuation` | BOOLEAN | Price resumed original trend direction |
| `is_full_reversal` | BOOLEAN | Broke prior swing (full reversal) |
| `recovery_strength` | DECIMAL(8,4) | Momentum after pullback ended |
| `volume_ratio_initial_vs_pullback` | DECIMAL(8,4) | Volume comparison |
| `outcome_type` | VARCHAR(20) | pullback_continuation, reversal, consolidation |

**Primary Key**: `(ticker, break_timestamp, timeframe)`

---

## Phase 2 — Historical Backfill Script

Create `src/pullback_feature_engineering.py`:

1. Query every record in `trend_breaks` table
2. For each break, look forward in `stock_prices` / `stock_prices_intraday`:
   - Identify the pullback low/high (first significant retracement)
   - Measure depth as % of prior `trend_ranges` move
   - Count candlesticks until pullback ends
   - Compute Fibonacci retracement levels from prior trend range
   - Check if price touched 38.2%, 50%, 61.8% levels
3. Classify outcome:
   - **pullback_continuation**: Retraced < 61.8% and resumed original direction
   - **reversal**: Broke prior swing high/low (100%+ retracement)
   - **consolidation**: Sideways action, no clear pullback or break within N periods
4. Populate `trend_break_outcomes` for all historical data

### Classification Thresholds

| Outcome | Definition |
|---------|------------|
| Pullback continuation | Retracement 10-61.8% of prior move, then resumes |
| Full reversal | Retracement > 100% (breaks prior swing) |
| Consolidation | < 10% retracement or no directional move within 2x avg trend duration |

---

## Phase 3 — Feature Engineering

### Pre-Break Context Features (from existing data)

| Feature | Source | Description |
|---------|--------|-------------|
| `prior_trend_strength` | `trend_ranges` | ADX value, MA slope during prior trend |
| `prior_trend_duration` | `trend_ranges.range_periods` | How long the prior trend lasted |
| `prior_trend_pct_change` | `trend_ranges.price_change_pct` | Total % move of prior trend |
| `break_magnitude` | `trend_breaks.magnitude` | Sharpness of the reversal |
| `break_volume_ratio` | `trend_breaks.volume_ratio` | Volume spike at break |
| `periods_since_last_break` | `trend_breaks` | Trend age at time of break |
| `trend_age_ratio` | `trend_break_features` | periods / typical_trend_length (13-18) |

### New Features to Compute

| Feature | Description |
|---------|-------------|
| `fib_level_nearest` | Nearest Fibonacci retracement level (0.236, 0.382, 0.5, 0.618) |
| `distance_to_support` | Price distance to nearest prior swing low |
| `distance_to_resistance` | Price distance to nearest prior swing high |
| `ma_distance_20` | Distance from 20-period MA at break point |
| `ma_distance_50` | Distance from 50-period MA at break point |
| `bollinger_pct_b` | Bollinger Band %B at break |
| `bollinger_width` | Bollinger Band width (volatility) |
| `momentum_consensus` | Avg of RSI, MACD, Stochastic continuous values (from meta_learning_model) |
| `trend_consensus` | Avg of SMA distance, EMA spread, Aroon (from meta_learning_model) |
| `volatility_regime` | Current vol percentile vs historical |
| `market_regime` | Bull/bear/neutral from market indices |
| `volume_trend_prior` | Volume increasing/decreasing during prior trend |
| `gap_at_break` | Whether break occurred on a gap |

### Post-Break Immediate Context (first 1-3 candles)

| Feature | Description |
|---------|-------------|
| `first_candle_direction` | Direction of first candle after break |
| `first_candle_body_pct` | Body size as % of range (conviction) |
| `first_3_candle_volume_avg` | Average volume in first 3 candles after break |
| `initial_move_pct` | % move in first 3 candles |

---

## Phase 4 — Model Training

Create `src/pullback_continuation_model.py`:

### Model A: Classification (3-class)

- **Target**: `outcome_type` — pullback_continuation, reversal, consolidation
- **Algorithm**: XGBoost (consistent with existing models in `models.py`)
- **Input**: All Phase 3 features
- **Output**: Probability distribution over 3 classes
- **Train per timeframe**: Separate models for daily, 1hr, 5min

### Model B: Regression (multi-output)

- **Targets**:
  - `pullback_depth_pct` — How deep (0-100%+)
  - `pullback_duration_candlesticks` — How many candles
  - `time_to_resumption` — Periods until trend resumes
- **Algorithm**: XGBoost regressor or LightGBM
- **Only trained on confirmed pullbacks** (not consolidation/reversal samples)

### Training Strategy

1. Split by time: train on pre-2024, validate on 2024, test on 2025+
2. Use all timeframes (daily has most history, intraday has most samples)
3. Feature importance analysis to prune weak features
4. Cross-validate with walk-forward validation (no future leakage)

### Expected Data Volume

| Timeframe | Estimated Breaks | Training Samples |
|-----------|-----------------|------------------|
| Daily | ~50k+ (64 years x ~500 tickers x ~2 breaks/year) | Large |
| 1 Hour | ~100k+ (30 days x 500 tickers x ~6 breaks/day) | Medium |
| 5 Min | ~500k+ (30 days x 500 tickers x ~30 breaks/day) | Large |

---

## Phase 5 — API & Frontend Integration

### Flask Endpoint

```
GET /api/pullback-prediction/<ticker>/<timeframe>
```

**Response**:
```json
{
  "ticker": "AAPL",
  "timeframe": "daily",
  "last_break": {
    "timestamp": "2025-01-15T00:00:00Z",
    "type": "peak",
    "price": 245.50
  },
  "prediction": {
    "outcome_probabilities": {
      "pullback_continuation": 0.65,
      "reversal": 0.20,
      "consolidation": 0.15
    },
    "expected_pullback_depth_pct": 38.2,
    "expected_pullback_duration_candles": 5,
    "nearest_fib_support": 238.70,
    "confidence": 0.72
  }
}
```

### Frontend Display

- After a detected trend break, show a card/widget with:
  - Probability bar: continuation vs. reversal vs. consolidation
  - Expected pullback depth with Fibonacci levels marked
  - Expected duration in candlesticks
  - Confidence score

---

## Dependencies

| Dependency | Status | Notes |
|------------|--------|-------|
| `trend_breaks` table | Populated | All historical breaks detected |
| `trend_ranges` table | Populated | Trend segments between breaks |
| `trend_break_features` table | Populated | Pre-computed ML features |
| `stock_prices` table | Populated | Daily OHLCV history |
| `stock_prices_intraday` table | Populated | Intraday bars (30-day retention) |
| `meta_learning_model.py` indicators | Exists | Reuse market regime + consensus features |
| `models.py` training patterns | Exists | Reuse XGBoost/LightGBM training |

---

## Files to Create

| # | File | Purpose |
|---|------|---------|
| 1 | `kubernetes/schema_pullback_outcomes.sql` | New table schema |
| 2 | `src/pullback_feature_engineering.py` | Backfill script + feature computation |
| 3 | `src/pullback_continuation_model.py` | Model training + prediction |
| 4 | `flask_app/app/routes/pullback.py` | API endpoint |
| 5 | `frontend/pullback.js` | Frontend display widget |

## Files to Modify

| # | File | Change |
|---|------|--------|
| 1 | `flask_app/app/__init__.py` | Register pullback blueprint |
| 2 | `frontend/index.html` | Add pullback widget section |
| 3 | `src/detect_trend_breaks.py` | Optional: trigger backfill after new break detection |
