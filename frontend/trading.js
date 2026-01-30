// ============================================================================
// Trade Execution — Brokerage Integration Proof of Concept
// ============================================================================
// This module demonstrates how the trading system would integrate with
// brokerage APIs (Schwab, IBKR, Alpaca, etc.) using OAuth 2.0 authentication.
// All data shown is simulated for demonstration purposes.
// ============================================================================

const Trading = {
    // Mock account data
    account: {
        value: 125432.87,
        cash: 34521.50,
        buyingPower: 69043.00,
        dayPnL: 1234.56,
    },

    // Mock positions
    positions: [
        { symbol: 'AAPL', qty: 100, avgCost: 178.50, current: 185.32 },
        { symbol: 'MSFT', qty: 50, avgCost: 378.20, current: 402.15 },
        { symbol: 'GOOGL', qty: 25, avgCost: 141.80, current: 148.92 },
        { symbol: 'NVDA', qty: 30, avgCost: 485.60, current: 512.45 },
        { symbol: 'AMZN', qty: 40, avgCost: 178.25, current: 185.80 },
        { symbol: 'SPY 240215C500', qty: 5, avgCost: 8.50, current: 12.35, isOption: true },
    ],

    // Mock orders
    orders: [
        { time: '10:32:15', symbol: 'AAPL', action: 'Buy', qty: 25, type: 'Limit', price: 184.50, status: 'Filled' },
        { time: '10:15:42', symbol: 'MSFT', action: 'Sell', qty: 10, type: 'Market', price: 401.80, status: 'Filled' },
        { time: '09:45:30', symbol: 'NVDA', action: 'Buy', qty: 10, type: 'Limit', price: 508.00, status: 'Open' },
        { time: '09:31:05', symbol: 'SPY 240215C500', action: 'Buy to Open', qty: 5, type: 'Limit', price: 8.50, status: 'Filled' },
    ],

    // Mock quotes cache
    quotes: {},

    init() {
        this.renderPositions();
        this.renderOrders();
        this.setupEventListeners();
        this.updateAccountDisplay();
    },

    setupEventListeners() {
        // Symbol input - fetch quote on blur or enter
        const symbolInput = document.getElementById('tradeSymbol');
        if (symbolInput) {
            symbolInput.addEventListener('blur', () => this.fetchQuote(symbolInput.value));
            symbolInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    this.fetchQuote(symbolInput.value);
                }
            });
        }

        // Action select - show/hide options fields
        const actionSelect = document.getElementById('tradeAction');
        if (actionSelect) {
            actionSelect.addEventListener('change', () => this.toggleOptionsFields());
        }

        // Order type - show/hide price fields
        const orderTypeSelect = document.getElementById('tradeOrderType');
        if (orderTypeSelect) {
            orderTypeSelect.addEventListener('change', () => this.togglePriceFields());
        }

        // Preview button
        const previewBtn = document.getElementById('previewOrderBtn');
        if (previewBtn) {
            previewBtn.addEventListener('click', () => this.previewOrder());
        }

        // Clear button
        const clearBtn = document.getElementById('clearOrderBtn');
        if (clearBtn) {
            clearBtn.addEventListener('click', () => this.clearOrder());
        }

        // Submit order button
        const submitBtn = document.getElementById('submitOrderBtn');
        if (submitBtn) {
            submitBtn.addEventListener('click', () => this.submitOrder());
        }

        // Cancel preview button
        const cancelPreviewBtn = document.getElementById('cancelPreviewBtn');
        if (cancelPreviewBtn) {
            cancelPreviewBtn.addEventListener('click', () => this.cancelPreview());
        }

        // Disconnect broker button
        const disconnectBtn = document.getElementById('disconnectBrokerBtn');
        if (disconnectBtn) {
            disconnectBtn.addEventListener('click', () => this.showConnectDialog());
        }
    },

    toggleOptionsFields() {
        const action = document.getElementById('tradeAction').value;
        const optionsFields = document.getElementById('tradingOptionsFields');

        if (action.includes('open') || action.includes('close')) {
            optionsFields.style.display = 'block';
        } else {
            optionsFields.style.display = 'none';
        }
    },

    togglePriceFields() {
        const orderType = document.getElementById('tradeOrderType').value;
        const limitPriceRow = document.getElementById('limitPriceRow');
        const stopPriceGroup = document.getElementById('stopPriceGroup');

        if (orderType === 'market') {
            limitPriceRow.style.display = 'none';
        } else {
            limitPriceRow.style.display = 'flex';
        }

        if (orderType === 'stop' || orderType === 'stop_limit') {
            stopPriceGroup.style.display = 'block';
        } else {
            stopPriceGroup.style.display = 'none';
        }
    },

    fetchQuote(symbol) {
        if (!symbol) return;
        symbol = symbol.toUpperCase().trim();

        // Mock quote data
        const mockQuotes = {
            'AAPL': { bid: 185.20, ask: 185.35, last: 185.32, change: 2.45, changePct: 1.34, volume: '45.2M' },
            'MSFT': { bid: 402.00, ask: 402.30, last: 402.15, change: 5.80, changePct: 1.46, volume: '22.1M' },
            'GOOGL': { bid: 148.85, ask: 149.00, last: 148.92, change: -1.23, changePct: -0.82, volume: '18.5M' },
            'NVDA': { bid: 512.30, ask: 512.60, last: 512.45, change: 8.92, changePct: 1.77, volume: '38.7M' },
            'AMZN': { bid: 185.70, ask: 185.90, last: 185.80, change: 3.25, changePct: 1.78, volume: '31.2M' },
            'SPY': { bid: 502.45, ask: 502.55, last: 502.50, change: 4.20, changePct: 0.84, volume: '62.8M' },
            'QQQ': { bid: 432.80, ask: 432.95, last: 432.87, change: 5.60, changePct: 1.31, volume: '28.4M' },
            'TSLA': { bid: 185.40, ask: 185.65, last: 185.52, change: -3.48, changePct: -1.84, volume: '95.3M' },
        };

        const quoteBox = document.getElementById('tradingQuoteBox');

        if (mockQuotes[symbol]) {
            const q = mockQuotes[symbol];
            this.quotes[symbol] = q;

            const changeClass = q.change >= 0 ? 'positive' : 'negative';
            const changeSign = q.change >= 0 ? '+' : '';

            quoteBox.innerHTML = `
                <div class="trading-quote-header">
                    <span class="trading-quote-symbol">${symbol}</span>
                    <span class="trading-quote-price">$${q.last.toFixed(2)}</span>
                </div>
                <div class="trading-quote-change ${changeClass}">
                    ${changeSign}${q.change.toFixed(2)} (${changeSign}${q.changePct.toFixed(2)}%)
                </div>
                <div class="trading-quote-details">
                    <div class="trading-quote-row">
                        <span>Bid:</span><span>$${q.bid.toFixed(2)}</span>
                    </div>
                    <div class="trading-quote-row">
                        <span>Ask:</span><span>$${q.ask.toFixed(2)}</span>
                    </div>
                    <div class="trading-quote-row">
                        <span>Volume:</span><span>${q.volume}</span>
                    </div>
                </div>
            `;
        } else {
            quoteBox.innerHTML = `
                <div class="trading-quote-error">
                    Symbol "${symbol}" not found in mock data.
                    <br><small>Try: AAPL, MSFT, GOOGL, NVDA, AMZN, SPY, QQQ, TSLA</small>
                </div>
            `;
        }
    },

    previewOrder() {
        const symbol = document.getElementById('tradeSymbol').value.toUpperCase().trim();
        const action = document.getElementById('tradeAction').value;
        const qty = parseInt(document.getElementById('tradeQuantity').value) || 0;
        const orderType = document.getElementById('tradeOrderType').value;
        const limitPrice = parseFloat(document.getElementById('tradeLimitPrice').value) || 0;
        const timeInForce = document.getElementById('tradeTimeInForce').value;

        if (!symbol || qty <= 0) {
            alert('Please enter a valid symbol and quantity.');
            return;
        }

        // Get quote for estimated cost
        const quote = this.quotes[symbol];
        const price = orderType === 'market' ? (quote?.ask || 0) : limitPrice;
        const estimatedCost = price * qty * (action.includes('buy') ? 1 : -1);

        const actionLabels = {
            'buy': 'Buy',
            'sell': 'Sell',
            'buy_to_open': 'Buy to Open',
            'sell_to_close': 'Sell to Close',
            'sell_to_open': 'Sell to Open',
            'buy_to_close': 'Buy to Close',
        };

        const orderTypeLabels = {
            'market': 'Market',
            'limit': 'Limit',
            'stop': 'Stop',
            'stop_limit': 'Stop Limit',
        };

        const tifLabels = {
            'day': 'Day',
            'gtc': 'Good Till Canceled',
            'ioc': 'Immediate or Cancel',
            'fok': 'Fill or Kill',
        };

        const previewDetails = document.getElementById('tradingPreviewDetails');
        previewDetails.innerHTML = `
            <div class="preview-row">
                <span>Symbol:</span><span class="preview-value">${symbol}</span>
            </div>
            <div class="preview-row">
                <span>Action:</span><span class="preview-value ${action.includes('buy') ? 'positive' : 'negative'}">${actionLabels[action]}</span>
            </div>
            <div class="preview-row">
                <span>Quantity:</span><span class="preview-value">${qty}</span>
            </div>
            <div class="preview-row">
                <span>Order Type:</span><span class="preview-value">${orderTypeLabels[orderType]}</span>
            </div>
            ${orderType !== 'market' ? `
            <div class="preview-row">
                <span>Limit Price:</span><span class="preview-value">$${limitPrice.toFixed(2)}</span>
            </div>
            ` : ''}
            <div class="preview-row">
                <span>Time in Force:</span><span class="preview-value">${tifLabels[timeInForce]}</span>
            </div>
            <div class="preview-row total">
                <span>Estimated ${action.includes('buy') ? 'Cost' : 'Credit'}:</span>
                <span class="preview-value ${action.includes('buy') ? 'negative' : 'positive'}">
                    ${action.includes('buy') ? '-' : '+'}$${Math.abs(estimatedCost).toFixed(2)}
                </span>
            </div>
        `;

        document.getElementById('tradingOrderPreview').style.display = 'block';
    },

    cancelPreview() {
        document.getElementById('tradingOrderPreview').style.display = 'none';
    },

    submitOrder() {
        const symbol = document.getElementById('tradeSymbol').value.toUpperCase().trim();
        const action = document.getElementById('tradeAction').value;
        const qty = parseInt(document.getElementById('tradeQuantity').value) || 0;
        const orderType = document.getElementById('tradeOrderType').value;
        const limitPrice = parseFloat(document.getElementById('tradeLimitPrice').value) || 0;

        const actionLabels = {
            'buy': 'Buy',
            'sell': 'Sell',
            'buy_to_open': 'Buy to Open',
            'sell_to_close': 'Sell to Close',
            'sell_to_open': 'Sell to Open',
            'buy_to_close': 'Buy to Close',
        };

        const quote = this.quotes[symbol];
        const fillPrice = orderType === 'market' ? (quote?.last || limitPrice) : limitPrice;

        // Add to orders
        const now = new Date();
        const timeStr = now.toLocaleTimeString('en-US', { hour12: false });

        this.orders.unshift({
            time: timeStr,
            symbol: symbol,
            action: actionLabels[action],
            qty: qty,
            type: orderType === 'market' ? 'Market' : 'Limit',
            price: fillPrice,
            status: orderType === 'market' ? 'Filled' : 'Open',
        });

        // Update positions if market order (instant fill)
        if (orderType === 'market') {
            this.updatePositionAfterFill(symbol, qty, fillPrice, action);
        }

        // Re-render
        this.renderOrders();
        this.renderPositions();
        this.updateAccountDisplay();

        // Clear form
        this.clearOrder();
        document.getElementById('tradingOrderPreview').style.display = 'none';

        // Show confirmation
        alert(`Order submitted successfully!\n\n${actionLabels[action]} ${qty} ${symbol} @ ${orderType === 'market' ? 'Market' : '$' + fillPrice.toFixed(2)}`);
    },

    updatePositionAfterFill(symbol, qty, price, action) {
        const existingPos = this.positions.find(p => p.symbol === symbol);

        if (action.includes('buy')) {
            if (existingPos) {
                // Average in
                const totalCost = existingPos.avgCost * existingPos.qty + price * qty;
                existingPos.qty += qty;
                existingPos.avgCost = totalCost / existingPos.qty;
                existingPos.current = price;
            } else {
                // New position
                this.positions.push({
                    symbol: symbol,
                    qty: qty,
                    avgCost: price,
                    current: price,
                });
            }
            // Reduce cash
            this.account.cash -= price * qty;
        } else {
            if (existingPos) {
                existingPos.qty -= qty;
                if (existingPos.qty <= 0) {
                    this.positions = this.positions.filter(p => p.symbol !== symbol);
                }
                // Add to cash
                this.account.cash += price * qty;
            }
        }
    },

    clearOrder() {
        document.getElementById('tradeSymbol').value = '';
        document.getElementById('tradeQuantity').value = '';
        document.getElementById('tradeLimitPrice').value = '';
        document.getElementById('tradeStopPrice').value = '';
        document.getElementById('tradeAction').value = 'buy';
        document.getElementById('tradeOrderType').value = 'market';
        document.getElementById('tradeTimeInForce').value = 'day';
        document.getElementById('tradingOptionsFields').style.display = 'none';
        document.getElementById('tradingQuoteBox').innerHTML = '<p class="trading-quote-placeholder">Enter a symbol to see quote</p>';
        this.togglePriceFields();
    },

    renderPositions() {
        const tbody = document.getElementById('tradingPositionsBody');
        if (!tbody) return;

        if (this.positions.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8" class="trading-empty">No open positions</td></tr>';
            return;
        }

        tbody.innerHTML = this.positions.map(pos => {
            const marketValue = pos.qty * pos.current;
            const costBasis = pos.qty * pos.avgCost;
            const pnl = marketValue - costBasis;
            const pnlPct = ((pos.current - pos.avgCost) / pos.avgCost) * 100;
            const pnlClass = pnl >= 0 ? 'positive' : 'negative';

            return `
                <tr>
                    <td class="trading-symbol">${pos.symbol}</td>
                    <td>${pos.qty}</td>
                    <td>$${pos.avgCost.toFixed(2)}</td>
                    <td>$${pos.current.toFixed(2)}</td>
                    <td>$${marketValue.toFixed(2)}</td>
                    <td class="${pnlClass}">${pnl >= 0 ? '+' : ''}$${pnl.toFixed(2)}</td>
                    <td class="${pnlClass}">${pnl >= 0 ? '+' : ''}${pnlPct.toFixed(2)}%</td>
                    <td>
                        <button class="btn btn-sm trading-close-btn" data-symbol="${pos.symbol}" data-qty="${pos.qty}">Close</button>
                    </td>
                </tr>
            `;
        }).join('');

        // Add close button handlers
        tbody.querySelectorAll('.trading-close-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const symbol = btn.dataset.symbol;
                const qty = btn.dataset.qty;
                document.getElementById('tradeSymbol').value = symbol;
                document.getElementById('tradeQuantity').value = qty;
                document.getElementById('tradeAction').value = 'sell';
                document.getElementById('tradeOrderType').value = 'market';
                this.fetchQuote(symbol);
            });
        });
    },

    renderOrders() {
        const tbody = document.getElementById('tradingOrdersBody');
        if (!tbody) return;

        if (this.orders.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8" class="trading-empty">No recent orders</td></tr>';
            return;
        }

        tbody.innerHTML = this.orders.slice(0, 10).map(order => {
            const statusClass = order.status === 'Filled' ? 'filled' :
                               order.status === 'Open' ? 'open' :
                               order.status === 'Canceled' ? 'canceled' : '';
            const actionClass = order.action.includes('Buy') ? 'buy' : 'sell';

            return `
                <tr>
                    <td>${order.time}</td>
                    <td class="trading-symbol">${order.symbol}</td>
                    <td class="trading-action ${actionClass}">${order.action}</td>
                    <td>${order.qty}</td>
                    <td>${order.type}</td>
                    <td>$${order.price.toFixed(2)}</td>
                    <td><span class="trading-status-badge ${statusClass}">${order.status}</span></td>
                    <td>
                        ${order.status === 'Open' ?
                            `<button class="btn btn-sm trading-cancel-btn" data-index="${this.orders.indexOf(order)}">Cancel</button>` :
                            '-'}
                    </td>
                </tr>
            `;
        }).join('');

        // Add cancel button handlers
        tbody.querySelectorAll('.trading-cancel-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const index = parseInt(btn.dataset.index);
                if (this.orders[index]) {
                    this.orders[index].status = 'Canceled';
                    this.renderOrders();
                }
            });
        });
    },

    updateAccountDisplay() {
        // Recalculate account value from positions
        const positionsValue = this.positions.reduce((sum, pos) => sum + pos.qty * pos.current, 0);
        this.account.value = this.account.cash + positionsValue;
        this.account.buyingPower = this.account.cash * 2; // 2x margin

        document.getElementById('accountValue').textContent = `$${this.account.value.toLocaleString('en-US', { minimumFractionDigits: 2 })}`;
        document.getElementById('cashAvailable').textContent = `$${this.account.cash.toLocaleString('en-US', { minimumFractionDigits: 2 })}`;
        document.getElementById('buyingPower').textContent = `$${this.account.buyingPower.toLocaleString('en-US', { minimumFractionDigits: 2 })}`;

        const dayPnLEl = document.getElementById('dayPnL');
        const pnlClass = this.account.dayPnL >= 0 ? 'positive' : 'negative';
        dayPnLEl.className = `trading-account-value ${pnlClass}`;
        dayPnLEl.textContent = `${this.account.dayPnL >= 0 ? '+' : ''}$${this.account.dayPnL.toLocaleString('en-US', { minimumFractionDigits: 2 })}`;
    },

    showConnectDialog() {
        alert('Brokerage Connection\n\nIn production, this would:\n1. Redirect to brokerage OAuth login\n2. User authorizes the app\n3. Receive access token\n4. Store encrypted credentials\n\nSupported brokerages:\n- Charles Schwab\n- Interactive Brokers\n- Alpaca\n- E*TRADE\n- Tradier');
    },
};

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('tradingTab')) {
        Trading.init();
    }
});

window.Trading = Trading;
