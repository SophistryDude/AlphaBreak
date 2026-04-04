// ============================================================================
// Premium Gating — Shared module for Pro feature trials + paywalls
// ============================================================================
// Usage:
//   if (Premium.canAccess('quant_grades')) { render(); }
//   else { Premium.showLocked('elementId', 'quant_grades'); }

const Premium = (() => {
    const STORAGE_KEY = 'alphabreak_premium_trials';

    // Feature definitions: id, display name, description
    const FEATURES = {
        quant_grades: {
            name: 'Quant Letter Grades',
            desc: 'A+ through F scoring across Value, Growth, Profitability, Momentum, Revisions, and AI Score vs sector peers.',
        },
        institutional_13f: {
            name: '13F Institutional Holdings',
            desc: 'See which hedge funds hold this stock, who\'s buying/selling, and net position changes from SEC 13F filings.',
        },
        earnings_detail: {
            name: 'Earnings Calendar + CBOE Analysis',
            desc: 'Quarterly earnings with EPS beat/miss history, CBOE options flow (P/C ratio, call/put volume), and detailed charts.',
        },
        candlestick_patterns: {
            name: 'Candlestick Pattern Recognition',
            desc: 'Auto-detected patterns (Doji, Hammer, Engulfing, Morning Star, etc.) with AI-scored probability on chart.',
        },
        trendlines: {
            name: 'Auto-Detected Trendlines',
            desc: 'AI-drawn support/resistance with confidence scoring, regime-aware analysis, and historical analog matching.',
        },
        seasonality: {
            name: 'Seasonality Heatmap',
            desc: '5-year monthly return analysis showing which months historically perform best for this stock.',
        },
        ai_screener: {
            name: 'AI Screener (Unlimited)',
            desc: 'Score any ticker with full quant grades. Free users get 3/month.',
        },
    };

    function _getTrials() {
        try {
            return JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
        } catch (e) { return {}; }
    }

    function _saveTrials(trials) {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(trials));
    }

    function isPremium() {
        return typeof Auth !== 'undefined' && Auth.isAuthenticated && Auth.user?.is_premium;
    }

    /**
     * Check if user can access a feature.
     * Premium users: always true.
     * Free users: true if they haven't used their 1 free trial yet.
     * Returns: { allowed: bool, isTrial: bool, isLocked: bool }
     */
    function checkAccess(featureId) {
        if (isPremium()) return { allowed: true, isTrial: false, isLocked: false };

        const trials = _getTrials();
        const used = trials[featureId];

        if (!used) {
            // First time — allow as trial
            return { allowed: true, isTrial: true, isLocked: false };
        }

        // Already used trial
        return { allowed: false, isTrial: false, isLocked: true };
    }

    /**
     * Shorthand: can the user access this feature right now?
     */
    function canAccess(featureId) {
        return checkAccess(featureId).allowed;
    }

    /**
     * Record that the user has used their free trial for a feature.
     */
    function recordTrial(featureId) {
        if (isPremium()) return; // Don't track for premium users
        const trials = _getTrials();
        if (!trials[featureId]) {
            trials[featureId] = {
                used_at: new Date().toISOString(),
                ticker: null,
            };
            _saveTrials(trials);
        }
    }

    /**
     * Show the locked state in a container element.
     */
    function showLocked(elementId, featureId) {
        const el = document.getElementById(elementId);
        if (!el) return;

        const feature = FEATURES[featureId] || { name: featureId, desc: '' };

        el.innerHTML = `
            <div class="pro-locked">
                <div class="pro-locked-icon">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="24" height="24">
                        <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
                        <path d="M7 11V7a5 5 0 0110 0v4"></path>
                    </svg>
                </div>
                <div class="pro-locked-title">${feature.name}</div>
                <div class="pro-locked-desc">${feature.desc}</div>
                <button class="btn btn-primary btn-sm pro-locked-btn">Upgrade to Pro — $99/mo</button>
            </div>
        `;
    }

    /**
     * Show trial banner above content. Call this when isTrial=true.
     */
    function showTrialBanner(elementId, featureId) {
        const el = document.getElementById(elementId);
        if (!el) return;

        const feature = FEATURES[featureId] || { name: featureId };

        // Don't add duplicate banners
        if (el.querySelector('.pro-trial-banner')) return;

        const banner = document.createElement('div');
        banner.className = 'pro-trial-banner';
        banner.innerHTML = `
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                <path d="M12 2L2 7l10 5 10-5-10-5z"></path>
                <path d="M2 17l10 5 10-5M2 12l10 5 10-5"></path>
            </svg>
            <span>Free trial of <strong>${feature.name}</strong>. Upgrade to Pro for permanent access.</span>
        `;
        el.insertBefore(banner, el.firstChild);
    }

    /**
     * Get feature info
     */
    function getFeatureInfo(featureId) {
        return FEATURES[featureId] || null;
    }

    return { checkAccess, canAccess, recordTrial, showLocked, showTrialBanner, isPremium, getFeatureInfo };
})();
