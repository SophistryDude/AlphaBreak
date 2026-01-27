# Dark Pool Amplification & CBOE Integration Report

**Generated**: 2026-01-27 04:06
**Samples**: 10,000 trend breaks

---

## Executive Summary

Tested the effect of integrating FINRA dark pool volume amplification and CBOE
put/call ratio sentiment into the meta-learning model's indicator accuracy scoring.

- **Total indicators compared**: 24
- **Improved**: 0 (0%)
- **Unchanged**: 24 (100%)
- **Degraded**: 0 (0%)
- **Average accuracy change**: +0.0000 (+0.00%)

---

## Methodology

### Dark Pool Amplification

Dark pool volume z-scores (8-week rolling, per-ticker) amplify composite accuracy:

```
amplification = 1.0 + max(0, dp_volume_zscore) * 0.15
```

| Z-Score | Amplification |
|--------:|--------------:|
| 0.0 | 1.00x |
| 1.0 | 1.15x |
| 2.0 | 1.30x |

**Rationale**: Analysis showed dark pool high volume (z>1) amplifies post-break
returns by +1.29pp (3.22% vs 1.93% for troughs). The amplification is multiplicative
on the composite accuracy score.

### CBOE P/C Ratio Sentiment

CBOE put/call ratio z-scores classify market sentiment into regimes:

| Regime | Z-Score Range | Contrarian Signal |
|--------|:--------------|:------------------|
| Very Bullish | z <= -1.5 | Bearish (complacency) |
| Bullish | -1.5 < z <= -0.5 | Bearish |
| Neutral | -0.5 < z < 0.5 | None |
| Bearish | 0.5 <= z < 1.5 | Bullish |
| Very Bearish | z >= 1.5 | Bullish (fear) |

CBOE context is stored on each indicator for regime-segmented analysis,
not used as an accuracy amplifier (P/C is directional/contrarian, not magnitude).

---

## Results: Accuracy Comparison

### Top 10 Most Improved Indicators

| Indicator | Baseline | Enhanced | Change | % Change |
|-----------|--------:|---------:|-------:|---------:|

### Overall Distribution

---

## CBOE P/C Regime-Segmented Results

### Very Bearish PCR

Average direction accuracy: 7.0%

| Indicator | Direction Accuracy |
|-----------|-------------------:|
| RSI | 69.0% |
| MACD | 55.7% |
| BB | 42.9% |

### Bearish PCR

Average direction accuracy: 7.6%

| Indicator | Direction Accuracy |
|-----------|-------------------:|
| RSI | 71.7% |
| MACD | 68.1% |
| BB | 41.7% |

### Neutral PCR

Average direction accuracy: 6.8%

| Indicator | Direction Accuracy |
|-----------|-------------------:|
| RSI | 65.2% |
| MACD | 59.3% |
| BB | 39.1% |

### Bullish PCR

Average direction accuracy: 8.0%

| Indicator | Direction Accuracy |
|-----------|-------------------:|
| RSI | 80.0% |
| MACD | 72.0% |
| BB | 40.0% |

---

## Data Coverage Limitations

- **Dark pool data**: Jan 2025 - Jan 2026 (~52 weeks, 459 tickers)
  - Only recent breaks can be amplified
  - Historical breaks outside this window get no amplification (factor = 1.0)

- **CBOE data**: Nov 2006 - Oct 2019 (~3,253 trading days)
  - No overlap with dark pool data date range
  - Regime segmentation covers most of the historical break data

## Recommendations

1. **Continue collecting dark pool data** weekly to expand coverage
2. **Update CBOE archive** with recent data (2020-present) for full coverage
3. **Use regime segmentation** to select different indicator weights per market condition
4. **Monitor amplification** as more dark pool data accumulates