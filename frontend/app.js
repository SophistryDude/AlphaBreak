// AlphaBreak Frontend Application

// Configuration
const CONFIG = {
    API_BASE_URL: '', // Empty for relative URLs (works with nginx proxy)
    API_KEY: '', // Empty for development mode (no API key required)
};

// State management
const state = {
    apiHealthy: false,
    activeTab: 'watchlist',
};

// Page titles for sidebar navigation
const PAGE_TITLES = {
    sentiment: 'Sentiment Analysis',
    earnings: 'Quarterly Earnings',
    reports: 'Trend Break Reports',
    options: 'Options Analysis',
    trading: 'Trade Execution',
    longterm: 'Long Term Trading Watchlist',
    watchlist: 'Security Analysis',
    aidashboard: 'AI Dashboard',
    trend: 'Trend Prediction',
    indicators: 'Indicator Guide',
    portfolio: 'Portfolio Tracker',
    forex: 'Forex Correlations',
    stats: 'Performance Stats',
    account: 'My Account',
};

// Initialize application
document.addEventListener('DOMContentLoaded', () => {
    // Initialize authentication first
    if (typeof Auth !== 'undefined') {
        Auth.init();
    }
    // Initialize notifications (after auth)
    if (typeof Notifications !== 'undefined') {
        Notifications.init();
    }
    // Initialize account (after auth)
    if (typeof Account !== 'undefined') {
        Account.init();
    }
    initializeSidebar();
    initializeForms();
    checkApiHealth();
    setDefaultDates();
    initWidgetCollapse();
});

// Widget collapse — works for all widgets with collapse buttons
function initWidgetCollapse() {
    // Market Sentiment (special ID)
    _initCollapse('sentimentCollapseBtn', 'sentimentCollapsible', 'sentimentCollapsed');

    // All generic widget collapse buttons
    document.querySelectorAll('.widget-collapse-btn').forEach(btn => {
        const targetId = btn.dataset.target;
        if (!targetId) return;
        _initCollapse(btn, targetId, 'widgetCollapsed_' + targetId);
    });
}

function _initCollapse(btnOrId, bodyId, storageKey) {
    const btn = typeof btnOrId === 'string' ? document.getElementById(btnOrId) : btnOrId;
    const body = document.getElementById(bodyId);
    if (!btn || !body) return;

    function setCollapsed(collapsed) {
        if (collapsed) {
            body.classList.add('hidden');
            btn.classList.add('collapsed');
        } else {
            body.classList.remove('hidden');
            btn.classList.remove('collapsed');
        }
        localStorage.setItem(storageKey, String(collapsed));
    }

    const saved = localStorage.getItem(storageKey) === 'true';
    setCollapsed(saved);

    btn.addEventListener('click', () => {
        setCollapsed(!body.classList.contains('hidden'));
    });
}

// Sidebar and hamburger menu management
function initializeSidebar() {
    const hamburgerBtn = document.getElementById('hamburgerBtn');
    const sidebar = document.getElementById('sidebar');
    const appLayout = document.querySelector('.app-layout');
    const sidebarLinks = document.querySelectorAll('.sidebar-link');
    const tabContents = document.querySelectorAll('.tab-content');

    // Restore sidebar state from localStorage
    const wasClosed = localStorage.getItem('sidebarClosed') === 'true';
    if (wasClosed) {
        sidebar.classList.add('closed');
        appLayout.classList.add('sidebar-closed');
    } else {
        // Sidebar starts expanded by default (unless it was closed)
        sidebar.classList.add('expanded');
    }

    // Toggle sidebar expansion (temporary overlay on mobile)
    function toggleSidebar() {
        sidebar.classList.toggle('expanded');
    }

    // Toggle sidebar completely closed/open (persistent)
    function toggleSidebarClosed() {
        const isClosed = sidebar.classList.toggle('closed');
        appLayout.classList.toggle('sidebar-closed');
        localStorage.setItem('sidebarClosed', isClosed);
    }

    function closeSidebar() {
        sidebar.classList.remove('expanded');
    }

    // Hamburger button click - single click expands, double click toggles closed
    let clickTimeout = null;
    hamburgerBtn.addEventListener('click', (e) => {
        if (clickTimeout) {
            // Double click - toggle sidebar closed/open
            clearTimeout(clickTimeout);
            clickTimeout = null;
            toggleSidebarClosed();
        } else {
            // Single click - toggle expansion
            clickTimeout = setTimeout(() => {
                toggleSidebar();
                clickTimeout = null;
            }, 250);
        }
    });

    // Sidebar link clicks
    sidebarLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const tabName = link.dataset.tab;

            // Update active states
            sidebarLinks.forEach(l => l.classList.remove('active'));
            tabContents.forEach(content => content.classList.remove('active'));

            link.classList.add('active');
            document.getElementById(`${tabName}Tab`).classList.add('active');

            // Update page title
            document.getElementById('currentPageTitle').textContent = PAGE_TITLES[tabName] || tabName;

            state.activeTab = tabName;

            // Hide persistent sentiment widget on forex and portfolio tabs
            const persistentSentiment = document.getElementById('persistentSentiment');
            if (persistentSentiment) {
                persistentSentiment.style.display = (tabName === 'forex' || tabName === 'portfolio' || tabName === 'account') ? 'none' : '';
            }

            // Close sidebar after selection
            closeSidebar();
        });
    });

    // Username click -> Account tab
    const userNameLink = document.getElementById('authUserName');
    if (userNameLink) {
        userNameLink.addEventListener('click', (e) => {
            e.preventDefault();
            sidebarLinks.forEach(l => l.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));
            document.getElementById('accountTab').classList.add('active');
            document.getElementById('currentPageTitle').textContent = PAGE_TITLES['account'];
            state.activeTab = 'account';
            const ps = document.getElementById('persistentSentiment');
            if (ps) ps.style.display = 'none';
        });
    }

    // Keyboard escape to close
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && sidebar.classList.contains('expanded')) {
            closeSidebar();
        }
    });
}

// Form initialization
function initializeForms() {
    // Trend Break Form
    document.getElementById('trendForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        await handleTrendPrediction(e.target);
    });

    // Options Form
    document.getElementById('optionsForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        await handleOptionsAnalysis(e.target);
    });

    // Stats Form
    document.getElementById('statsForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        await handleStatsRequest(e.target);
    });

    // Auto-uppercase ticker inputs
    const tickerInputs = document.querySelectorAll('input[name="ticker"]');
    tickerInputs.forEach(input => {
        input.addEventListener('input', (e) => {
            e.target.value = e.target.value.toUpperCase();
        });
    });
}

// Set default dates (last year to today)
function setDefaultDates() {
    const today = new Date();
    const lastYear = new Date(today);
    lastYear.setFullYear(today.getFullYear() - 1);

    const formatDate = (date) => date.toISOString().split('T')[0];

    // Trend form
    document.getElementById('trendStartDate').value = formatDate(lastYear);
    document.getElementById('trendEndDate').value = formatDate(today);

    // Options form
    document.getElementById('optionsStartDate').value = formatDate(lastYear);
    document.getElementById('optionsEndDate').value = formatDate(today);
}

// Check API health
async function checkApiHealth() {
    const statusIndicator = document.querySelector('.status-indicator');
    const statusText = document.querySelector('.status-text');

    try {
        const response = await fetch(`${CONFIG.API_BASE_URL}/api/health`);
        const data = await response.json();

        if (data.status === 'healthy') {
            state.apiHealthy = true;
            statusIndicator.classList.add('healthy');
            statusText.textContent = 'API Online';
        } else {
            throw new Error('API unhealthy');
        }
    } catch (error) {
        state.apiHealthy = false;
        statusIndicator.classList.add('error');
        statusText.textContent = 'API Offline';
        showError('Unable to connect to API. Please check your connection.');
    }
}

// Handle trend prediction
async function handleTrendPrediction(form) {
    const formData = new FormData(form);
    const data = {
        ticker: formData.get('ticker'),
        start_date: formData.get('start_date'),
        end_date: formData.get('end_date'),
    };

    const button = form.querySelector('button[type="submit"]');
    setLoadingState(button, true);
    hideResults('trendResults');

    try {
        const response = await apiRequest('/api/predict/trend-break', 'POST', data);

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.message || 'Prediction failed');
        }

        const result = await response.json();
        displayTrendResults(result);
    } catch (error) {
        showError(error.message);
    } finally {
        setLoadingState(button, false);
    }
}

// Display trend prediction results
function displayTrendResults(data) {
    const resultsDiv = document.getElementById('trendResults');

    // Update ticker and timestamp
    document.getElementById('resultTicker').textContent = data.ticker;
    document.getElementById('resultTimestamp').textContent =
        new Date(data.timestamp).toLocaleString();

    // Update prediction metrics
    const prediction = data.prediction;
    const probability = (prediction.trend_break_probability * 100).toFixed(1);
    document.getElementById('breakProbability').textContent = `${probability}%`;

    const confidenceBar = document.getElementById('confidenceBar');
    confidenceBar.style.width = `${probability}%`;

    // Direction with color
    const directionElement = document.getElementById('predictedDirection');
    directionElement.textContent = prediction.predicted_direction.toUpperCase();
    directionElement.className = 'metric-value';
    if (prediction.predicted_direction === 'up') {
        directionElement.classList.add('positive');
    } else if (prediction.predicted_direction === 'down') {
        directionElement.classList.add('negative');
    }

    document.getElementById('confidence').textContent =
        `${(prediction.confidence * 100).toFixed(1)}%`;
    document.getElementById('currentPrice').textContent =
        `$${prediction.current_price.toFixed(2)}`;
    document.getElementById('targetPrice').textContent =
        `$${prediction.target_price.toFixed(2)}`;

    // Display indicators
    const indicatorsList = document.getElementById('indicatorsList');
    indicatorsList.innerHTML = '';

    data.indicators_used.forEach(indicator => {
        const indicatorDiv = document.createElement('div');
        indicatorDiv.className = 'indicator-item';
        indicatorDiv.innerHTML = `
            <div class="indicator-name">${indicator.name}</div>
            <div class="indicator-details">
                <span>Value: ${indicator.value.toFixed(2)}</span>
                <span>Weight: ${(indicator.weight * 100).toFixed(0)}%</span>
            </div>
        `;
        indicatorsList.appendChild(indicatorDiv);
    });

    // Model version
    document.getElementById('modelVersion').textContent = data.model_version;

    // Show results
    resultsDiv.style.display = 'block';
    resultsDiv.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

// Handle options analysis
async function handleOptionsAnalysis(form) {
    const formData = new FormData(form);
    const data = {
        ticker: formData.get('ticker'),
        start_date: formData.get('start_date'),
        end_date: formData.get('end_date'),
    };

    // Add optional fields if provided
    const optionType = formData.get('option_type');
    const trendDirection = formData.get('trend_direction');
    if (optionType) data.option_type = optionType;
    if (trendDirection) data.trend_direction = trendDirection;

    const button = form.querySelector('button[type="submit"]');
    setLoadingState(button, true);
    hideResults('optionsResults');

    try {
        const response = await apiRequest('/api/predict/options', 'POST', data);

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.message || 'Options analysis failed');
        }

        const result = await response.json();
        displayOptionsResults(result);
    } catch (error) {
        showError(error.message);
    } finally {
        setLoadingState(button, false);
    }
}

// Display options results
function displayOptionsResults(data) {
    const resultsDiv = document.getElementById('optionsResults');

    // Update header
    document.getElementById('optionsResultTicker').textContent = data.ticker;
    document.getElementById('optionsResultTimestamp').textContent =
        new Date(data.timestamp).toLocaleString();

    // Setup "+ Watch" button
    const watchBtn = document.getElementById('optionsAddToWatchlist');
    if (watchBtn) {
        // Remove old listeners by replacing the element
        const newWatchBtn = watchBtn.cloneNode(true);
        watchBtn.parentNode.replaceChild(newWatchBtn, watchBtn);

        newWatchBtn.addEventListener('click', () => {
            if (typeof Watchlist !== 'undefined' && Watchlist.addTicker) {
                Watchlist.addTicker(data.ticker);
            } else {
                showSnackbar(`Watchlist not available`, 'error');
            }
        });
    }

    // Update strategy
    const analysis = data.analysis;
    document.getElementById('strategyName').textContent =
        analysis.recommended_strategy.replace(/_/g, ' ');
    document.getElementById('strategyConfidence').textContent =
        `${(analysis.confidence * 100).toFixed(1)}%`;
    document.getElementById('expectedReturn').textContent =
        `${(analysis.expected_return * 100).toFixed(1)}%`;

    const riskElement = document.getElementById('riskLevel');
    riskElement.textContent = analysis.risk_level.toUpperCase();
    riskElement.className = 'metric-value';
    if (analysis.risk_level === 'low') riskElement.classList.add('positive');
    else if (analysis.risk_level === 'high') riskElement.classList.add('negative');

    // Populate options table
    const tableBody = document.getElementById('optionsTableBody');
    tableBody.innerHTML = '';

    data.options.forEach(option => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td><span class="option-badge ${option.type}">${option.type.toUpperCase()}</span></td>
            <td>$${option.strike.toFixed(2)}</td>
            <td>${option.expiration}</td>
            <td>$${option.last_price.toFixed(2)}</td>
            <td>$${option.fair_value.toFixed(2)}</td>
            <td>${(option.implied_volatility * 100).toFixed(1)}%</td>
            <td>${option.delta.toFixed(3)}</td>
            <td><span class="recommendation-badge ${option.recommendation}">${option.recommendation.toUpperCase()}</span></td>
        `;
        tableBody.appendChild(row);
    });

    // Show results
    resultsDiv.style.display = 'block';
    resultsDiv.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

// Handle stats request
async function handleStatsRequest(form) {
    const formData = new FormData(form);
    const modelVersion = formData.get('model_version');
    const days = formData.get('days');

    let url = '/api/stats/accuracy?';
    if (modelVersion) url += `model_version=${modelVersion}&`;
    url += `days=${days}`;

    const button = form.querySelector('button[type="submit"]');
    setLoadingState(button, true);
    hideResults('statsResults');

    try {
        const response = await apiRequest(url, 'GET');

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.message || 'Failed to fetch statistics');
        }

        const result = await response.json();
        displayStatsResults(result);
    } catch (error) {
        showError(error.message);
    } finally {
        setLoadingState(button, false);
    }
}

// Display stats results
function displayStatsResults(data) {
    const resultsDiv = document.getElementById('statsResults');

    // Accuracy metrics
    const metrics = data.metrics;
    document.getElementById('statsAccuracy').textContent =
        `${(metrics.accuracy * 100).toFixed(1)}%`;
    document.getElementById('statsPrecision').textContent =
        `${(metrics.precision * 100).toFixed(1)}%`;
    document.getElementById('statsRecall').textContent =
        `${(metrics.recall * 100).toFixed(1)}%`;
    document.getElementById('statsF1').textContent =
        `${(metrics.f1_score * 100).toFixed(1)}%`;

    // Trading performance
    const performance = data.trading_performance;

    const returnElement = document.getElementById('statsTotalReturn');
    const returnValue = performance.total_return * 100;
    returnElement.textContent = `${returnValue >= 0 ? '+' : ''}${returnValue.toFixed(1)}%`;
    returnElement.className = 'metric-value';
    returnElement.classList.add(returnValue >= 0 ? 'positive' : 'negative');

    document.getElementById('statsSharpe').textContent =
        performance.sharpe_ratio.toFixed(2);
    document.getElementById('statsWinRate').textContent =
        `${(performance.win_rate * 100).toFixed(1)}%`;

    const drawdownElement = document.getElementById('statsDrawdown');
    drawdownElement.textContent = `${(performance.max_drawdown * 100).toFixed(1)}%`;
    drawdownElement.className = 'metric-value negative';

    // Show results
    resultsDiv.style.display = 'block';
    resultsDiv.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

// API request helper with JWT support
async function apiRequest(endpoint, method = 'GET', body = null) {
    const headers = {
        'Content-Type': 'application/json',
    };

    // Add JWT token if authenticated
    if (typeof Auth !== 'undefined' && Auth.isAuthenticated && Auth.accessToken) {
        headers['Authorization'] = `Bearer ${Auth.accessToken}`;
    }
    // Fallback to API key if configured
    else if (CONFIG.API_KEY) {
        headers['X-API-Key'] = CONFIG.API_KEY;
    }

    const options = {
        method,
        headers,
    };

    if (body && method !== 'GET') {
        options.body = JSON.stringify(body);
    }

    let response = await fetch(`${CONFIG.API_BASE_URL}${endpoint}`, options);

    // Handle 401 - try token refresh
    if (response.status === 401 && typeof Auth !== 'undefined' && Auth.isAuthenticated) {
        const refreshed = await Auth.refreshAccessToken();
        if (refreshed) {
            headers['Authorization'] = `Bearer ${Auth.accessToken}`;
            response = await fetch(`${CONFIG.API_BASE_URL}${endpoint}`, options);
        }
    }

    return response;
}

// Utility: Set loading state
function setLoadingState(button, isLoading) {
    if (isLoading) {
        button.classList.add('loading');
        button.disabled = true;
    } else {
        button.classList.remove('loading');
        button.disabled = false;
    }
}

// Utility: Hide results
function hideResults(resultsId) {
    document.getElementById(resultsId).style.display = 'none';
}

// Error display
function showError(message) {
    const errorDisplay = document.getElementById('errorDisplay');
    const errorMessage = document.getElementById('errorMessage');

    errorMessage.textContent = message;
    errorDisplay.style.display = 'block';

    // Auto-hide after 5 seconds
    setTimeout(() => {
        closeError();
    }, 5000);
}

function closeError() {
    document.getElementById('errorDisplay').style.display = 'none';
}

// Format numbers
function formatCurrency(value) {
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
    }).format(value);
}

function formatPercentage(value) {
    return `${(value * 100).toFixed(2)}%`;
}

// Global Snackbar notification
function showSnackbar(message, type = 'info') {
    // Create snackbar if it doesn't exist
    let snackbar = document.getElementById('snackbar');
    if (!snackbar) {
        snackbar = document.createElement('div');
        snackbar.id = 'snackbar';
        document.body.appendChild(snackbar);
    }

    // Set message and type
    snackbar.textContent = message;
    snackbar.className = `snackbar snackbar-${type} show`;

    // Auto-hide after 3 seconds
    setTimeout(() => {
        snackbar.classList.remove('show');
    }, 3000);
}

// Export for use in HTML
window.closeError = closeError;
window.showSnackbar = showSnackbar;
