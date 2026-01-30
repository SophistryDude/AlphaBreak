# AlphaBreak API Documentation

Complete API reference for front-end developers.

## Base URL

**Development**: `http://localhost:5000`
**Production**: `https://trading-api.yourdomain.com`

## Authentication

All API requests require an API key in the header:

```http
X-API-Key: your-api-key-here
```

## Rate Limits

- **200 requests per day**
- **50 requests per hour**

Rate limit headers are returned in responses:
```http
X-RateLimit-Limit: 50
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1640995200
```

## Endpoints

### 1. Health Check

Check API status and availability.

**Endpoint**: `GET /api/health`

**Authentication**: Not required

**Response**: `200 OK`
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z",
  "version": "1.0.0"
}
```

---

### 2. Predict Trend Break

Predict trend breaks for a given stock ticker.

**Endpoint**: `POST /api/predict/trend-break`

**Authentication**: Required

**Request Body**:
```json
{
  "ticker": "AAPL",
  "start_date": "2023-01-01",
  "end_date": "2024-01-15"
}
```

**Parameters**:
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| ticker | string | Yes | Stock ticker symbol (e.g., "AAPL", "GOOGL") |
| start_date | string | Yes | Start date in YYYY-MM-DD format |
| end_date | string | Yes | End date in YYYY-MM-DD format |

**Response**: `200 OK`
```json
{
  "ticker": "AAPL",
  "prediction": {
    "trend_break_probability": 0.85,
    "predicted_direction": "up",
    "confidence": 0.78,
    "break_date": "2024-01-20",
    "current_price": 185.50,
    "target_price": 195.00
  },
  "indicators_used": [
    {
      "name": "RSI_14",
      "value": 65.4,
      "weight": 0.25
    },
    {
      "name": "MACD",
      "value": 1.23,
      "weight": 0.30
    },
    {
      "name": "BB_UPPER",
      "value": 190.50,
      "weight": 0.20
    }
  ],
  "model_version": "v2.1",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

**Error Responses**:

`400 Bad Request` - Invalid input
```json
{
  "error": "Invalid ticker symbol",
  "message": "Ticker must be a valid stock symbol"
}
```

`401 Unauthorized` - Missing or invalid API key
```json
{
  "error": "Unauthorized",
  "message": "Invalid or missing API key"
}
```

`429 Too Many Requests` - Rate limit exceeded
```json
{
  "error": "Rate limit exceeded",
  "message": "Too many requests. Please try again later.",
  "retry_after": 3600
}
```

`500 Internal Server Error` - Server error
```json
{
  "error": "Internal server error",
  "message": "An unexpected error occurred"
}
```

---

### 3. Analyze Options

Analyze options trading opportunities for a stock.

**Endpoint**: `POST /api/predict/options`

**Authentication**: Required

**Request Body**:
```json
{
  "ticker": "AAPL",
  "start_date": "2023-01-01",
  "end_date": "2024-01-15",
  "option_type": "call",
  "trend_direction": "bullish"
}
```

**Parameters**:
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| ticker | string | Yes | Stock ticker symbol |
| start_date | string | Yes | Start date (YYYY-MM-DD) |
| end_date | string | Yes | End date (YYYY-MM-DD) |
| option_type | string | No | "call" or "put" (default: both) |
| trend_direction | string | No | "bullish", "bearish", or "neutral" |

**Response**: `200 OK`
```json
{
  "ticker": "AAPL",
  "current_price": 185.50,
  "analysis": {
    "recommended_strategy": "bull_call_spread",
    "confidence": 0.82,
    "expected_return": 0.15,
    "risk_level": "medium"
  },
  "options": [
    {
      "type": "call",
      "strike": 190.00,
      "expiration": "2024-02-16",
      "bid": 5.20,
      "ask": 5.40,
      "last_price": 5.30,
      "implied_volatility": 0.28,
      "delta": 0.45,
      "gamma": 0.02,
      "theta": -0.05,
      "vega": 0.12,
      "rho": 0.08,
      "fair_value": 5.35,
      "recommendation": "buy",
      "profit_potential": 0.18
    }
  ],
  "greeks_summary": {
    "portfolio_delta": 0.45,
    "portfolio_gamma": 0.02,
    "portfolio_theta": -0.05,
    "portfolio_vega": 0.12
  },
  "model_version": "v1.5",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

---

### 4. Get Historical Accuracy

Get historical accuracy of predictions for a model.

**Endpoint**: `GET /api/stats/accuracy`

**Authentication**: Required

**Query Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| model_version | string | No | Specific model version (default: latest) |
| days | integer | No | Number of days to look back (default: 30) |

**Example**: `GET /api/stats/accuracy?model_version=v2.1&days=90`

**Response**: `200 OK`
```json
{
  "model_version": "v2.1",
  "period_days": 90,
  "metrics": {
    "accuracy": 0.78,
    "precision": 0.82,
    "recall": 0.75,
    "f1_score": 0.78,
    "auc_roc": 0.85
  },
  "predictions": {
    "total": 450,
    "correct": 351,
    "incorrect": 99
  },
  "trading_performance": {
    "total_return": 0.18,
    "sharpe_ratio": 1.45,
    "max_drawdown": -0.08,
    "win_rate": 0.68
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

---

### 5. Get Top Indicators

Get top-performing indicators for a ticker.

**Endpoint**: `GET /api/stats/indicators/{ticker}`

**Authentication**: Required

**Path Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| ticker | string | Yes | Stock ticker symbol |

**Query Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| min_accuracy | float | No | Minimum accuracy threshold (default: 0.7) |
| days | integer | No | Number of days to look back (default: 30) |

**Example**: `GET /api/stats/indicators/AAPL?min_accuracy=0.75&days=60`

**Response**: `200 OK`
```json
{
  "ticker": "AAPL",
  "period_days": 60,
  "top_indicators": [
    {
      "name": "RSI_14",
      "avg_accuracy": 0.85,
      "avg_f1": 0.83,
      "evaluations": 120,
      "recommended": true
    },
    {
      "name": "MACD",
      "avg_accuracy": 0.82,
      "avg_f1": 0.80,
      "evaluations": 120,
      "recommended": true
    },
    {
      "name": "BB_UPPER",
      "avg_accuracy": 0.78,
      "avg_f1": 0.76,
      "evaluations": 120,
      "recommended": true
    }
  ],
  "timestamp": "2024-01-15T10:30:00Z"
}
```

---

## WebSocket Support (Future)

Real-time updates for crypto prices and signals.

**Endpoint**: `ws://trading-api.yourdomain.com/ws/crypto`

**Message Format**:
```json
{
  "type": "price_update",
  "ticker": "BTC-USD",
  "price": 45000.50,
  "volume": 1234567890,
  "timestamp": "2024-01-15T10:30:15Z"
}
```

```json
{
  "type": "signal",
  "ticker": "ETH-USD",
  "signal": "RSI_OVERSOLD",
  "confidence": 0.85,
  "timestamp": "2024-01-15T10:30:15Z"
}
```

---

## Error Handling

All error responses follow this format:

```json
{
  "error": "Error type",
  "message": "Human-readable error message",
  "details": {
    "field": "ticker",
    "issue": "Invalid format"
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

**Common HTTP Status Codes**:
- `200 OK` - Success
- `400 Bad Request` - Invalid input
- `401 Unauthorized` - Authentication failed
- `403 Forbidden` - Insufficient permissions
- `404 Not Found` - Endpoint not found
- `429 Too Many Requests` - Rate limit exceeded
- `500 Internal Server Error` - Server error
- `503 Service Unavailable` - Service temporarily unavailable

---

## CORS

The API supports CORS for web applications. Allowed origins are configured in the server.

**Allowed Methods**: `GET`, `POST`, `OPTIONS`
**Allowed Headers**: `Content-Type`, `X-API-Key`

---

## Example: Complete Request Flow

```javascript
// 1. Check API health
const healthResponse = await fetch('http://localhost:5000/api/health');
const health = await healthResponse.json();
console.log('API Status:', health.status);

// 2. Make prediction request
const predictionResponse = await fetch('http://localhost:5000/api/predict/trend-break', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-API-Key': 'your-api-key-here'
  },
  body: JSON.stringify({
    ticker: 'AAPL',
    start_date: '2023-01-01',
    end_date: '2024-01-15'
  })
});

if (!predictionResponse.ok) {
  const error = await predictionResponse.json();
  console.error('Error:', error.message);
} else {
  const prediction = await predictionResponse.json();
  console.log('Trend Break Probability:', prediction.prediction.trend_break_probability);
  console.log('Predicted Direction:', prediction.prediction.predicted_direction);
}
```

---

## Testing

Use these test credentials for development:

**API Key**: `test-api-key-12345`
**Base URL**: `http://localhost:5000`

**Test Tickers**: AAPL, GOOGL, MSFT, TSLA
**Test Date Range**: 2023-01-01 to 2024-01-15

---

## Support

For API issues or questions:
- Check API status: `/api/health`
- Review error messages in response body
- Check rate limit headers
- Contact: api-support@yourcompany.com
