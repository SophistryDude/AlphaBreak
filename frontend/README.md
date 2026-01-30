# AlphaBreak Frontend

Production-ready frontend interface for the AlphaBreak AI-powered securities trading prediction system.

## Features

✅ **Trend Break Prediction** - Predict potential trend breaks with confidence scores
✅ **Options Analysis** - Analyze options with fair value pricing and Greeks
✅ **Performance Statistics** - View model accuracy and trading performance
✅ **Real-time API Status** - Monitor API health
✅ **Responsive Design** - Works on desktop, tablet, and mobile
✅ **Error Handling** - Comprehensive error messages and validation
✅ **Professional UI** - Modern, clean design with smooth animations

## Files

```
frontend/
├── index.html              # Main HTML structure
├── styles.css              # Complete styling
├── app.js                  # JavaScript application logic
├── API_DOCUMENTATION.md    # Complete API reference
└── README.md               # This file
```

## Quick Start

### 1. Update API Configuration

Edit `app.js` and update the configuration:

```javascript
const CONFIG = {
    API_BASE_URL: 'http://localhost:5000',  // Update for production
    API_KEY: 'your-api-key-here',           // Replace with actual API key
};
```

### 2. Serve the Files

**Option A: Simple HTTP Server (Python)**
```bash
cd frontend
python -m http.server 8000
```
Then open: http://localhost:8000

**Option B: Node.js HTTP Server**
```bash
npm install -g http-server
cd frontend
http-server -p 8000
```

**Option C: VS Code Live Server**
- Install "Live Server" extension
- Right-click `index.html` → "Open with Live Server"

### 3. Test the Application

1. **Check API Status** - Should show "API Online" if backend is running
2. **Test Trend Prediction**:
   - Enter ticker: `AAPL`
   - Select date range
   - Click "Analyze Trend"
3. **Test Options Analysis**:
   - Enter ticker: `AAPL`
   - Select parameters
   - Click "Analyze Options"

## API Configuration

### Development
```javascript
API_BASE_URL: 'http://localhost:5000'
```

### Production (Docker)
```javascript
API_BASE_URL: 'http://trading-api:5000'
```

### Production (Kubernetes)
```javascript
API_BASE_URL: 'https://trading-api.yourdomain.com'
```

### Getting API Key

Request an API key from your backend administrator or generate one:

```bash
# Generate random API key
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Add it to Kubernetes secrets:
```bash
kubectl edit secret trading-secrets -n trading-system
```

## Features Overview

### 1. Trend Break Prediction

Predicts potential trend breaks with:
- Probability score (0-100%)
- Predicted direction (UP/DOWN/SIDEWAYS)
- Confidence level
- Current and target prices
- Key indicators used (RSI, MACD, Bollinger Bands, etc.)

**Example Result**:
- Trend Break Probability: 85%
- Direction: UP
- Confidence: 78%
- Current Price: $185.50
- Target Price: $195.00

### 2. Options Analysis

Analyzes options trading opportunities:
- Recommended strategy (e.g., bull call spread)
- Expected return and risk level
- Options chain with fair values
- Greeks (Delta, Gamma, Theta, Vega, Rho)
- Buy/Sell/Hold recommendations

**Filters**:
- Option type (Call/Put/Both)
- Trend direction (Bullish/Bearish/Neutral)

### 3. Performance Statistics

View model performance metrics:
- **Accuracy Metrics**: Accuracy, Precision, Recall, F1 Score
- **Trading Performance**: Total Return, Sharpe Ratio, Win Rate, Max Drawdown
- Historical lookback: 7/30/60/90 days

## Form Validation

All forms include client-side validation:

**Ticker Input**:
- Required
- 1-5 uppercase letters only
- Auto-converts to uppercase

**Date Inputs**:
- Required
- Start date must be before end date
- Defaults to last year → today

**Options Parameters**:
- Optional filters
- Validates dropdown selections

## Error Handling

The application handles:

1. **Network Errors** - API unavailable
2. **Authentication Errors** - Invalid API key
3. **Validation Errors** - Invalid input
4. **Rate Limiting** - Too many requests
5. **Server Errors** - Internal server errors

**Error Display**:
- Red notification banner (top-right)
- Auto-dismisses after 5 seconds
- Can be manually closed

## Styling Customization

### Colors

Edit CSS variables in `styles.css`:

```css
:root {
    --primary-color: #2563eb;      /* Main brand color */
    --success-color: #10b981;      /* Positive values */
    --danger-color: #ef4444;       /* Negative values */
    --warning-color: #f59e0b;      /* Warnings */
    --bg-color: #f9fafb;           /* Background */
    --card-bg: #ffffff;            /* Card background */
}
```

### Fonts

Change font family:
```css
body {
    font-family: 'Your Font', sans-serif;
}
```

### Layout

Adjust container width:
```css
.container {
    max-width: 1400px;  /* Default: 1200px */
}
```

## Browser Support

- ✅ Chrome 90+
- ✅ Firefox 88+
- ✅ Safari 14+
- ✅ Edge 90+

**Required Features**:
- ES6+ JavaScript (async/await, arrow functions)
- CSS Grid & Flexbox
- Fetch API

## Mobile Responsive

Breakpoints:
- **Desktop**: > 768px
- **Tablet**: 481px - 768px
- **Mobile**: < 480px

Features:
- Stacked form layouts on mobile
- Collapsible tables
- Touch-friendly buttons
- Optimized spacing

## Security Considerations

1. **API Key Security**:
   - Never commit API keys to version control
   - Use environment variables in production
   - Rotate keys regularly

2. **CORS**:
   - Backend must allow frontend origin
   - Configured in Flask API settings

3. **HTTPS**:
   - Use HTTPS in production
   - Update `API_BASE_URL` to `https://`

4. **Input Sanitization**:
   - All inputs validated client-side
   - Backend performs additional validation

## Production Deployment

### Option 1: Static Hosting (Recommended)

**Netlify**:
```bash
# Install Netlify CLI
npm install -g netlify-cli

# Deploy
cd frontend
netlify deploy --prod
```

**Vercel**:
```bash
npm install -g vercel
cd frontend
vercel --prod
```

**AWS S3 + CloudFront**:
```bash
aws s3 sync frontend/ s3://your-bucket-name/
aws cloudfront create-invalidation --distribution-id YOUR_DIST_ID --paths "/*"
```

### Option 2: Docker

Create `Dockerfile`:
```dockerfile
FROM nginx:alpine
COPY frontend/ /usr/share/nginx/html/
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

Build and run:
```bash
docker build -t trading-frontend .
docker run -p 8080:80 trading-frontend
```

### Option 3: Kubernetes

Create `frontend-deployment.yaml`:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: trading-frontend
spec:
  replicas: 2
  selector:
    matchLabels:
      app: trading-frontend
  template:
    metadata:
      labels:
        app: trading-frontend
    spec:
      containers:
      - name: nginx
        image: nginx:alpine
        ports:
        - containerPort: 80
        volumeMounts:
        - name: frontend-files
          mountPath: /usr/share/nginx/html
      volumes:
      - name: frontend-files
        configMap:
          name: frontend-config
```

Deploy:
```bash
kubectl apply -f frontend-deployment.yaml
```

## Testing

### Manual Testing Checklist

- [ ] API status indicator shows "Online"
- [ ] Trend prediction returns results
- [ ] Options analysis displays table
- [ ] Stats load correctly
- [ ] Error messages appear for invalid input
- [ ] Forms validate required fields
- [ ] Ticker auto-converts to uppercase
- [ ] Date pickers work
- [ ] Results display properly
- [ ] Mobile responsive layout works
- [ ] All tabs switch correctly

### Automated Testing

Add E2E tests with Playwright:

```bash
npm install -g playwright
```

Create `tests/e2e.spec.js`:
```javascript
const { test, expect } = require('@playwright/test');

test('trend prediction flow', async ({ page }) => {
  await page.goto('http://localhost:8000');

  await page.fill('#trendTicker', 'AAPL');
  await page.fill('#trendStartDate', '2023-01-01');
  await page.fill('#trendEndDate', '2024-01-15');

  await page.click('button[type="submit"]');

  await expect(page.locator('#trendResults')).toBeVisible();
});
```

## Troubleshooting

### API Status shows "Offline"

**Check**:
1. Backend is running: `curl http://localhost:5000/api/health`
2. CORS is enabled in Flask app
3. Correct `API_BASE_URL` in `app.js`

### CORS Errors

Add to Flask app:
```python
from flask_cors import CORS
CORS(app, resources={r"/api/*": {"origins": "*"}})
```

### 401 Unauthorized

**Check**:
1. API key is correct in `app.js`
2. API key exists in backend secrets
3. Headers are being sent: Check Network tab in DevTools

### Results Not Displaying

**Check**:
1. Browser console for JavaScript errors (F12)
2. Network tab for failed requests
3. Response JSON structure matches expected format

## Performance Optimization

1. **Minify Assets**:
```bash
# Install terser for JS minification
npm install -g terser
terser app.js -o app.min.js -c -m

# Install clean-css for CSS minification
npm install -g clean-css-cli
cleancss -o styles.min.css styles.css
```

2. **Enable Caching**:
Add to nginx config:
```nginx
location ~* \.(js|css|png|jpg|jpeg|gif|ico)$ {
    expires 1y;
    add_header Cache-Control "public, immutable";
}
```

3. **Use CDN**:
- Host on CloudFlare, AWS CloudFront, or similar
- Reduces latency for global users

## Future Enhancements

- [ ] Real-time WebSocket updates for crypto
- [ ] Chart visualizations (TradingView, Chart.js)
- [ ] Export results to CSV/PDF
- [ ] User authentication and saved preferences
- [ ] Watchlist functionality
- [ ] Email/SMS alerts for high-confidence predictions
- [ ] Dark mode toggle
- [ ] Multi-language support

## Support

For issues or questions:
- Check [API_DOCUMENTATION.md](API_DOCUMENTATION.md)
- Review browser console for errors
- Check Network tab in DevTools
- Ensure backend API is running

## License

Proprietary - For internal use only
