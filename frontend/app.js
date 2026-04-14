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
    pricing: 'Plans & Pricing',
    contact: 'Contact',
    landing: 'AlphaBreak',
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
    initLanding();
    initContactForm();
    showLandingIfNeeded();
    checkApiHealth();
    setDefaultDates();
    initWidgetCollapse();
    initProgrammaticTickerRoute();
    initComparisonRoute();
    // Onboarding tour (after auth state is resolved)
    setTimeout(() => {
        if (typeof Onboarding !== 'undefined') Onboarding.init();
    }, 500);
});

// Programmatic ticker SEO routes: /stocks/<TICKER>
// The nginx config rewrites /stocks/* → /index.html, so the SPA bootstraps
// with the original path intact in location.pathname. We detect it here,
// extract the ticker, rewrite title + meta tags for per-ticker SEO, and
// deep-link into the Analyze tab.
function initProgrammaticTickerRoute() {
    const path = window.location.pathname;
    const match = path.match(/^\/stocks\/([A-Z0-9\-\.]{1,10})\/?$/i);
    if (!match) return;

    const ticker = match[1].toUpperCase();

    // Ticker-specific meta — overrides the generic index.html tags so each
    // /stocks/<T> URL looks like its own page to crawlers.
    document.title = `${ticker} Stock Analysis — AI Score, Trend Breaks, Options | AlphaBreak`;
    _setMeta('name', 'description', `Free AI-powered analysis for ${ticker}: auto-detected trendlines, trend break probability, 17 technical indicators, options chain, institutional holdings, dark pool flow, and regime classification. No signup required.`);
    _setMeta('property', 'og:title', `${ticker} Stock Analysis | AlphaBreak`);
    _setMeta('property', 'og:description', `AI-scored technical + fundamental analysis for ${ticker}. Free tier, no account required.`);
    _setMeta('property', 'og:url', `https://alphabreak.vip/stocks/${ticker}`);
    _setMeta('name', 'twitter:title', `${ticker} Stock Analysis | AlphaBreak`);
    _setMeta('name', 'twitter:description', `AI-scored technical + fundamental analysis for ${ticker}. Free.`);
    const canonical = document.querySelector('link[rel="canonical"]');
    if (canonical) canonical.href = `https://alphabreak.vip/stocks/${ticker}`;

    // Inject a per-ticker Schema.org block so Google gets a FinancialProduct entity.
    const tickerSchema = document.createElement('script');
    tickerSchema.type = 'application/ld+json';
    tickerSchema.textContent = JSON.stringify({
        "@context": "https://schema.org",
        "@type": "FinancialProduct",
        "name": `${ticker} Stock Analysis`,
        "description": `AI-powered analysis of ${ticker} including trend break detection, technical indicators, options analytics, and institutional holdings.`,
        "url": `https://alphabreak.vip/stocks/${ticker}`,
        "provider": { "@type": "Organization", "name": "AlphaBreak", "url": "https://alphabreak.vip/" },
    });
    document.head.appendChild(tickerSchema);

    // Switch the SPA to the analyze tab and load this ticker once Analyze is ready.
    const loadTicker = () => {
        const tabContents = document.querySelectorAll('.tab-content');
        const sidebarLinks = document.querySelectorAll('.sidebar-link');
        tabContents.forEach(c => c.classList.remove('active'));
        sidebarLinks.forEach(l => l.classList.remove('active'));
        const watchlistTab = document.getElementById('watchlistTab');
        const watchlistLink = document.querySelector('[data-tab="watchlist"]');
        if (watchlistTab) watchlistTab.classList.add('active');
        if (watchlistLink) watchlistLink.classList.add('active');
        document.getElementById('currentPageTitle').textContent = `${ticker} — Security Analysis`;
        state.activeTab = 'watchlist';

        const input = document.getElementById('analyzeTickerInput');
        if (input) input.value = ticker;
        if (typeof Analyze !== 'undefined' && Analyze.analyzeTicker) {
            Analyze.analyzeTicker(ticker);
        }
    };
    // Analyze.init() runs after DOMContentLoaded, so defer one tick.
    setTimeout(loadTicker, 0);
}

// Programmatic comparison routes: /compare/<slug>
// Similar pattern — static shell pages handled client-side. Supported slugs:
// tradingview, seeking-alpha, bloomberg.
function initComparisonRoute() {
    const path = window.location.pathname;
    const match = path.match(/^\/compare\/(tradingview|seeking-alpha|bloomberg)\/?$/i);
    if (!match) return;
    const slug = match[1].toLowerCase();

    // Show the comparison tab (we add one in index.html below).
    const tab = document.getElementById(`compare-${slug}-Tab`);
    if (!tab) return;
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    document.querySelectorAll('.sidebar-link').forEach(l => l.classList.remove('active'));
    tab.classList.add('active');

    const labels = {
        'tradingview': 'TradingView',
        'seeking-alpha': 'Seeking Alpha',
        'bloomberg': 'Bloomberg Terminal',
    };
    const competitor = labels[slug];
    document.title = `AlphaBreak vs ${competitor} — Honest Comparison 2026 | AlphaBreak`;
    _setMeta('name', 'description', `How AlphaBreak compares to ${competitor}: feature-by-feature breakdown, pricing, and honest pros/cons. Free tier, no credit card.`);
    _setMeta('property', 'og:title', `AlphaBreak vs ${competitor}`);
    _setMeta('property', 'og:url', `https://alphabreak.vip/compare/${slug}`);
    const canonical = document.querySelector('link[rel="canonical"]');
    if (canonical) canonical.href = `https://alphabreak.vip/compare/${slug}`;
    document.getElementById('currentPageTitle').textContent = `AlphaBreak vs ${competitor}`;
    state.activeTab = `compare-${slug}`;
}

function _setMeta(attrName, attrValue, content) {
    let tag = document.querySelector(`meta[${attrName}="${attrValue}"]`);
    if (!tag) {
        tag = document.createElement('meta');
        tag.setAttribute(attrName, attrValue);
        document.head.appendChild(tag);
    }
    tag.setAttribute('content', content);
}

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
                persistentSentiment.style.display = (tabName === 'forex' || tabName === 'portfolio' || tabName === 'account' || tabName === 'contact' || tabName === 'landing' || tabName === 'pricing') ? 'none' : '';
            }

            // Apply inline auth gate if the tab requires an account
            _applyAuthGateToActiveTab();

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

    // ── Global: "Upgrade to Pro" buttons → navigate to Pricing tab ───────
    document.addEventListener('click', (e) => {
        const btn = e.target.closest('.pro-locked-btn, .pricing-upgrade-btn');
        if (!btn) return;
        e.preventDefault();
        // Switch to pricing tab
        sidebarLinks.forEach(l => l.classList.remove('active'));
        tabContents.forEach(c => c.classList.remove('active'));
        const pricingLink = document.querySelector('[data-tab="pricing"]');
        if (pricingLink) pricingLink.classList.add('active');
        document.getElementById('pricingTab').classList.add('active');
        document.getElementById('currentPageTitle').textContent = PAGE_TITLES['pricing'];
        state.activeTab = 'pricing';
        const ps = document.getElementById('persistentSentiment');
        if (ps) ps.style.display = 'none';
        closeSidebar();
        // Scroll to top
        window.scrollTo(0, 0);
    });

    // ── Pricing: Monthly / Annual toggle ─────────────────────────────────
    const monthlyBtn = document.getElementById('pricingMonthly');
    const annualBtn = document.getElementById('pricingAnnual');
    if (monthlyBtn && annualBtn) {
        function setPricingMode(annual) {
            document.querySelectorAll('.pricing-price[data-monthly]').forEach(el => {
                const mo = el.dataset.monthly;
                const yr = el.dataset.annual;
                el.innerHTML = annual
                    ? `$${yr}<span class="pricing-period">/mo</span>`
                    : `$${mo}<span class="pricing-period">/mo</span>`;
            });
            monthlyBtn.classList.toggle('active', !annual);
            annualBtn.classList.toggle('active', annual);
        }
        monthlyBtn.addEventListener('click', () => setPricingMode(false));
        annualBtn.addEventListener('click', () => setPricingMode(true));
    }
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

// ── Landing page logic ──────────────────────────────────────────────────────
function initLanding() {
    // "Get Started Free" buttons → open sign-up modal
    document.querySelectorAll('.landing-cta-signup').forEach(btn => {
        btn.addEventListener('click', () => {
            if (typeof Auth !== 'undefined') Auth.showModal('register');
        });
    });

    // "See Features" → scroll to features grid
    const demoBtn = document.getElementById('landingDemo');
    if (demoBtn) {
        demoBtn.addEventListener('click', () => {
            document.querySelector('.landing-features-grid')?.scrollIntoView({ behavior: 'smooth' });
        });
    }

    // "View Pricing" → go to pricing tab
    document.querySelectorAll('.landing-cta-pricing').forEach(btn => {
        btn.addEventListener('click', () => {
            const pricingLink = document.querySelector('[data-tab="pricing"]');
            if (pricingLink) pricingLink.click();
        });
    });
}

// Tabs that require an account — everything else is open to anonymous visitors.
// Kept small and explicit so adding features to the free tier doesn't accidentally
// gate them.
const AUTH_REQUIRED_TABS = new Set(['portfolio', 'trading', 'account']);

// Initial tab selection for unauthenticated vs authenticated visitors.
// Previously this hid the sidebar and locked the whole app behind login — killing
// conversions because Google can't show us to anyone who hasn't already signed up.
// New behavior: everyone sees the full app. Unauthenticated visitors land on the
// Security Analysis tab (the core free value) unless the URL hash deep-links
// somewhere else. The landing-page marketing tab is still reachable but no longer
// blocks the app.
function showLandingIfNeeded() {
    const isAuth = typeof Auth !== 'undefined' && Auth.isAuthenticated;
    const hasStoredToken = !!(localStorage.getItem('alphabreak_access_token') && localStorage.getItem('alphabreak_user'));

    const sidebar = document.getElementById('sidebar');
    // Sidebar is always visible now — anonymous visitors get to browse everything
    // that doesn't require user state.
    if (sidebar) sidebar.classList.remove('landing-hidden');

    // If a tab is already active (e.g. from deep-linked programmatic SEO page),
    // leave it alone. Otherwise pick a sensible default.
    if (document.querySelector('.tab-content.active')) {
        // Re-check auth gating on whatever tab is currently active.
        _applyAuthGateToActiveTab();
        return;
    }

    const tabContents = document.querySelectorAll('.tab-content');
    const sidebarLinks = document.querySelectorAll('.sidebar-link');
    tabContents.forEach(c => c.classList.remove('active'));
    sidebarLinks.forEach(l => l.classList.remove('active'));

    if (isAuth || hasStoredToken) {
        // Authenticated — go straight to the main analysis tab.
        const watchlistTab = document.getElementById('watchlistTab');
        const watchlistLink = document.querySelector('[data-tab="watchlist"]');
        if (watchlistTab) watchlistTab.classList.add('active');
        if (watchlistLink) watchlistLink.classList.add('active');
        document.getElementById('currentPageTitle').textContent = PAGE_TITLES['watchlist'] || 'Security Analysis';
        state.activeTab = 'watchlist';

        if (typeof Dashboard !== 'undefined' && Dashboard._sentimentPending) {
            Dashboard._sentimentPending = false;
            setTimeout(() => Dashboard.updateMarketSentimentChart(), 100);
        }
    } else {
        // Anonymous visitor — land on Security Analysis too. The landing page
        // marketing content is still reachable from the sidebar footer if needed
        // but the free product is what converts, not the pitch.
        const watchlistTab = document.getElementById('watchlistTab');
        const watchlistLink = document.querySelector('[data-tab="watchlist"]');
        if (watchlistTab) watchlistTab.classList.add('active');
        if (watchlistLink) watchlistLink.classList.add('active');
        document.getElementById('currentPageTitle').textContent = PAGE_TITLES['watchlist'] || 'Security Analysis';
        state.activeTab = 'watchlist';
    }
}

// Called whenever a tab becomes active — if the tab requires auth and the user
// is anonymous, overlay it with a sign-in prompt rather than dumping broken UI
// on them.
function _applyAuthGateToActiveTab() {
    const tabName = state.activeTab;
    if (!AUTH_REQUIRED_TABS.has(tabName)) {
        // Free tab — remove any previously-added gate.
        _clearInlineAuthGate();
        return;
    }
    const isAuth = typeof Auth !== 'undefined' && Auth.isAuthenticated;
    if (isAuth) {
        _clearInlineAuthGate();
        return;
    }
    _showInlineAuthGate(tabName);
}

function _clearInlineAuthGate() {
    document.querySelectorAll('.inline-auth-gate').forEach(el => el.remove());
}

function _showInlineAuthGate(tabName) {
    const tabEl = document.getElementById(`${tabName}Tab`);
    if (!tabEl) return;
    // Don't stack multiples
    if (tabEl.querySelector('.inline-auth-gate')) return;

    const labels = {
        portfolio: 'the Portfolio Tracker',
        trading: 'Trade Execution',
        account: 'your account (journal, settings, notifications)',
    };
    const feature = labels[tabName] || 'this feature';

    const gate = document.createElement('div');
    gate.className = 'inline-auth-gate';
    gate.innerHTML = `
        <div class="inline-auth-gate-card">
            <div class="inline-auth-gate-icon">
                <svg viewBox="0 0 24 24" width="36" height="36" fill="none" stroke="currentColor" stroke-width="1.8">
                    <rect x="3" y="11" width="18" height="11" rx="2"></rect>
                    <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
                </svg>
            </div>
            <h2>Sign in to use ${feature}</h2>
            <p>Free to browse Security Analysis, AI Dashboard, Reports, Options, and more without an account.
               Portfolio tracking and journaling need an account so we can save your data.</p>
            <div class="inline-auth-gate-actions">
                <button type="button" class="btn btn-primary inline-auth-gate-signup">Sign up free</button>
                <button type="button" class="btn btn-ghost inline-auth-gate-signin">Sign in</button>
            </div>
            <p class="inline-auth-gate-footer">No credit card required. 30-second signup.</p>
        </div>
    `;
    // Insert at the top of the tab so whatever is below is visually covered.
    tabEl.insertBefore(gate, tabEl.firstChild);

    gate.querySelector('.inline-auth-gate-signup')?.addEventListener('click', () => {
        document.getElementById('authSignUpBtn')?.click();
    });
    gate.querySelector('.inline-auth-gate-signin')?.addEventListener('click', () => {
        document.getElementById('authSignInBtn')?.click();
    });
}

// ── Contact form logic ──────────────────────────────────────────────────────
function initContactForm() {
    const form = document.getElementById('contactForm');
    if (!form) return;

    // Pricing link inside contact page
    document.querySelectorAll('.contact-link-pricing').forEach(a => {
        a.addEventListener('click', (e) => {
            e.preventDefault();
            const pricingLink = document.querySelector('[data-tab="pricing"]');
            if (pricingLink) pricingLink.click();
        });
    });

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const status = document.getElementById('contactFormStatus');
        const submitBtn = form.querySelector('.contact-submit');

        const data = {
            name: document.getElementById('contactName').value.trim(),
            email: document.getElementById('contactEmail').value.trim(),
            subject: document.getElementById('contactSubject').value,
            message: document.getElementById('contactMessage').value.trim(),
        };

        if (!data.name || !data.email || !data.message) {
            status.textContent = 'Please fill in all required fields.';
            status.className = 'contact-form-status error';
            return;
        }

        submitBtn.disabled = true;
        submitBtn.textContent = 'Sending...';

        try {
            const response = await fetch(`${CONFIG.API_BASE_URL}/api/contact`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data),
            });

            if (response.ok) {
                status.textContent = 'Message sent! We\'ll get back to you within 24 hours.';
                status.className = 'contact-form-status success';
                form.reset();
            } else {
                // Fallback: open mailto
                const mailto = `mailto:contact@alphabreak.vip?subject=${encodeURIComponent(data.subject + ': ' + data.name)}&body=${encodeURIComponent(data.message + '\n\nFrom: ' + data.email)}`;
                window.location.href = mailto;
                status.textContent = 'Opening your email client as a fallback...';
                status.className = 'contact-form-status info';
            }
        } catch {
            // API not available — fallback to mailto
            const mailto = `mailto:contact@alphabreak.vip?subject=${encodeURIComponent(data.subject + ': ' + data.name)}&body=${encodeURIComponent(data.message + '\n\nFrom: ' + data.email)}`;
            window.location.href = mailto;
            status.textContent = 'Opening your email client...';
            status.className = 'contact-form-status info';
        }

        submitBtn.disabled = false;
        submitBtn.textContent = 'Send Message';
    });
}

// Export for use in HTML
window.closeError = closeError;
window.showSnackbar = showSnackbar;
window.showLandingIfNeeded = showLandingIfNeeded;
