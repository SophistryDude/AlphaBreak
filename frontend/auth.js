/**
 * Authentication Module
 * =====================
 * Handles user authentication state, login, registration, and token management.
 */

const Auth = {
    // Storage keys
    ACCESS_TOKEN_KEY: 'alphabreak_access_token',
    REFRESH_TOKEN_KEY: 'alphabreak_refresh_token',
    USER_KEY: 'alphabreak_user',

    // State
    accessToken: null,
    refreshToken: null,
    user: null,
    isAuthenticated: false,

    /**
     * Initialize auth state from localStorage
     */
    init() {
        this.loadFromStorage();
        this.updateUI();

        // Set up event listeners for auth modal
        this.setupEventListeners();

        // Validate token if present
        if (this.accessToken) {
            this.validateToken();
        }
    },

    /**
     * Load tokens and user from localStorage
     */
    loadFromStorage() {
        try {
            this.accessToken = localStorage.getItem(this.ACCESS_TOKEN_KEY);
            this.refreshToken = localStorage.getItem(this.REFRESH_TOKEN_KEY);

            const userJson = localStorage.getItem(this.USER_KEY);
            this.user = userJson ? JSON.parse(userJson) : null;

            this.isAuthenticated = !!(this.accessToken && this.user);
        } catch (e) {
            console.warn('Failed to load auth from storage:', e);
            this.clearStorage();
        }
    },

    /**
     * Save tokens and user to localStorage
     */
    saveToStorage() {
        try {
            if (this.accessToken) {
                localStorage.setItem(this.ACCESS_TOKEN_KEY, this.accessToken);
            }
            if (this.refreshToken) {
                localStorage.setItem(this.REFRESH_TOKEN_KEY, this.refreshToken);
            }
            if (this.user) {
                localStorage.setItem(this.USER_KEY, JSON.stringify(this.user));
            }
        } catch (e) {
            console.warn('Failed to save auth to storage:', e);
        }
    },

    /**
     * Clear all auth data from localStorage
     */
    clearStorage() {
        localStorage.removeItem(this.ACCESS_TOKEN_KEY);
        localStorage.removeItem(this.REFRESH_TOKEN_KEY);
        localStorage.removeItem(this.USER_KEY);

        this.accessToken = null;
        this.refreshToken = null;
        this.user = null;
        this.isAuthenticated = false;
    },

    /**
     * Register a new user
     */
    async register(email, password, displayName = null) {
        try {
            const response = await fetch(`${CONFIG.API_BASE_URL}/api/auth/register`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, password, display_name: displayName }),
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Registration failed');
            }

            // Store tokens and user
            this.accessToken = data.access_token;
            this.refreshToken = data.refresh_token;
            this.user = data.user;
            this.isAuthenticated = true;

            this.saveToStorage();
            this.updateUI();

            // Migrate watchlist after registration
            if (typeof Watchlist !== 'undefined' && Watchlist.migrateToServer) {
                await Watchlist.migrateToServer();
            }

            return { success: true, user: data.user };
        } catch (e) {
            console.error('Registration error:', e);
            return { success: false, error: e.message };
        }
    },

    /**
     * Login user
     */
    async login(email, password) {
        try {
            const response = await fetch(`${CONFIG.API_BASE_URL}/api/auth/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, password }),
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Login failed');
            }

            // Store tokens and user
            this.accessToken = data.access_token;
            this.refreshToken = data.refresh_token;
            this.user = data.user;
            this.isAuthenticated = true;

            this.saveToStorage();
            this.updateUI();

            // Migrate watchlist after login
            if (typeof Watchlist !== 'undefined' && Watchlist.migrateToServer) {
                await Watchlist.migrateToServer();
            }

            return { success: true, user: data.user };
        } catch (e) {
            console.error('Login error:', e);
            return { success: false, error: e.message };
        }
    },

    /**
     * Logout user
     */
    async logout() {
        try {
            if (this.accessToken && this.refreshToken) {
                await fetch(`${CONFIG.API_BASE_URL}/api/auth/logout`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${this.accessToken}`,
                    },
                    body: JSON.stringify({ refresh_token: this.refreshToken }),
                });
            }
        } catch (e) {
            console.warn('Logout request failed:', e);
        }

        this.clearStorage();
        this.updateUI();

        // Reload watchlist from localStorage
        if (typeof Watchlist !== 'undefined' && Watchlist.loadFromStorage) {
            await Watchlist.loadFromStorage();
            if (Watchlist.render) Watchlist.render();
        }
    },

    /**
     * Refresh the access token using refresh token
     */
    async refreshAccessToken() {
        if (!this.refreshToken) {
            return false;
        }

        try {
            const response = await fetch(`${CONFIG.API_BASE_URL}/api/auth/refresh`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ refresh_token: this.refreshToken }),
            });

            if (!response.ok) {
                throw new Error('Token refresh failed');
            }

            const data = await response.json();
            this.accessToken = data.access_token;
            localStorage.setItem(this.ACCESS_TOKEN_KEY, this.accessToken);

            return true;
        } catch (e) {
            console.warn('Token refresh failed:', e);
            // Clear auth state on refresh failure
            this.clearStorage();
            this.updateUI();
            return false;
        }
    },

    /**
     * Validate current token by fetching user profile
     */
    async validateToken() {
        if (!this.accessToken) {
            return false;
        }

        try {
            const response = await fetch(`${CONFIG.API_BASE_URL}/api/auth/me`, {
                headers: {
                    'Authorization': `Bearer ${this.accessToken}`,
                },
            });

            if (response.status === 401) {
                // Token expired, try refresh (only once to avoid infinite loop)
                if (this._validatingToken) {
                    return false;
                }
                this._validatingToken = true;
                try {
                    const refreshed = await this.refreshAccessToken();
                    if (!refreshed) {
                        return false;
                    }
                    // Retry validation once after refresh
                    const retryResponse = await fetch(`${CONFIG.API_BASE_URL}/api/auth/me`, {
                        headers: { 'Authorization': `Bearer ${this.accessToken}` },
                    });
                    if (!retryResponse.ok) {
                        return false;
                    }
                    const retryData = await retryResponse.json();
                    this.user = retryData.user;
                    this.isAuthenticated = true;
                    this.saveToStorage();
                    this.updateUI();
                    return true;
                } finally {
                    this._validatingToken = false;
                }
            }

            if (!response.ok) {
                throw new Error('Token validation failed');
            }

            const data = await response.json();
            this.user = data.user;
            this.isAuthenticated = true;
            this.saveToStorage();
            this.updateUI();

            return true;
        } catch (e) {
            console.warn('Token validation failed:', e);
            this.clearStorage();
            this.updateUI();
            return false;
        }
    },

    /**
     * Get the current access token (for API requests)
     */
    getAccessToken() {
        return this.accessToken;
    },

    /**
     * Update UI based on auth state
     */
    updateUI() {
        const authActions = document.getElementById('authActions');
        const authUserMenu = document.getElementById('authUserMenu');
        const authUserName = document.getElementById('authUserName');

        if (this.isAuthenticated && this.user) {
            if (authActions) authActions.style.display = 'none';
            if (authUserMenu) authUserMenu.style.display = 'flex';
            if (authUserName) {
                authUserName.textContent = this.user.display_name || this.user.email;
            }
            // Show notification bell and auth-only sidebar items
            if (typeof Notifications !== 'undefined') {
                Notifications.show();
                Notifications.fetchUnreadCount();
                Notifications.startPolling();
            }
            document.querySelectorAll('.auth-only-sidebar-item').forEach(el => el.style.display = '');
        } else {
            if (authActions) authActions.style.display = 'flex';
            if (authUserMenu) authUserMenu.style.display = 'none';
            // Hide notification bell and auth-only sidebar items
            if (typeof Notifications !== 'undefined') {
                Notifications.hide();
            }
            document.querySelectorAll('.auth-only-sidebar-item').forEach(el => el.style.display = 'none');
        }
    },

    /**
     * Show the auth modal
     */
    showModal(tab = 'login') {
        const overlay = document.getElementById('authModalOverlay');
        const loginForm = document.getElementById('loginFormContainer');
        const registerForm = document.getElementById('registerFormContainer');
        const loginTab = document.getElementById('loginTab');
        const registerTab = document.getElementById('registerTab');

        if (overlay) overlay.style.display = 'flex';

        // Clear any previous errors
        const loginError = document.getElementById('loginError');
        const registerError = document.getElementById('registerError');
        if (loginError) loginError.textContent = '';
        if (registerError) registerError.textContent = '';

        // Show correct form
        if (tab === 'login') {
            if (loginForm) loginForm.style.display = 'block';
            if (registerForm) registerForm.style.display = 'none';
            if (loginTab) loginTab.classList.add('active');
            if (registerTab) registerTab.classList.remove('active');
        } else {
            if (loginForm) loginForm.style.display = 'none';
            if (registerForm) registerForm.style.display = 'block';
            if (loginTab) loginTab.classList.remove('active');
            if (registerTab) registerTab.classList.add('active');
        }
    },

    /**
     * Hide the auth modal
     */
    hideModal() {
        const overlay = document.getElementById('authModalOverlay');
        if (overlay) overlay.style.display = 'none';

        // Clear form inputs
        const forms = document.querySelectorAll('.auth-form');
        forms.forEach(form => form.reset());
    },

    /**
     * Set up event listeners for auth UI
     */
    setupEventListeners() {
        // Sign In button
        const signInBtn = document.getElementById('authSignInBtn');
        if (signInBtn) {
            signInBtn.addEventListener('click', () => this.showModal('login'));
        }

        // Sign Up button
        const signUpBtn = document.getElementById('authSignUpBtn');
        if (signUpBtn) {
            signUpBtn.addEventListener('click', () => this.showModal('register'));
        }

        // Sign Out button
        const signOutBtn = document.getElementById('authSignOutBtn');
        if (signOutBtn) {
            signOutBtn.addEventListener('click', () => this.logout());
        }

        // Modal close button
        const closeBtn = document.getElementById('authModalClose');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => this.hideModal());
        }

        // Close on overlay click
        const overlay = document.getElementById('authModalOverlay');
        if (overlay) {
            overlay.addEventListener('click', (e) => {
                if (e.target === overlay) this.hideModal();
            });
        }

        // Tab switching
        const loginTab = document.getElementById('loginTab');
        const registerTab = document.getElementById('registerTab');

        if (loginTab) {
            loginTab.addEventListener('click', () => this.showModal('login'));
        }
        if (registerTab) {
            registerTab.addEventListener('click', () => this.showModal('register'));
        }

        // Login form submission
        const loginForm = document.getElementById('loginForm');
        if (loginForm) {
            loginForm.addEventListener('submit', async (e) => {
                e.preventDefault();
                const email = document.getElementById('loginEmail').value;
                const password = document.getElementById('loginPassword').value;
                const errorEl = document.getElementById('loginError');
                const submitBtn = loginForm.querySelector('button[type="submit"]');

                // Disable button during request
                if (submitBtn) submitBtn.disabled = true;

                const result = await this.login(email, password);

                if (submitBtn) submitBtn.disabled = false;

                if (result.success) {
                    this.hideModal();
                } else {
                    if (errorEl) errorEl.textContent = result.error;
                }
            });
        }

        // Register form submission
        const registerForm = document.getElementById('registerForm');
        if (registerForm) {
            registerForm.addEventListener('submit', async (e) => {
                e.preventDefault();
                const email = document.getElementById('registerEmail').value;
                const password = document.getElementById('registerPassword').value;
                const confirmPassword = document.getElementById('registerConfirmPassword').value;
                const displayName = document.getElementById('registerDisplayName')?.value || null;
                const errorEl = document.getElementById('registerError');
                const submitBtn = registerForm.querySelector('button[type="submit"]');

                // Validate passwords match
                if (password !== confirmPassword) {
                    if (errorEl) errorEl.textContent = 'Passwords do not match';
                    return;
                }

                // Disable button during request
                if (submitBtn) submitBtn.disabled = true;

                const result = await this.register(email, password, displayName);

                if (submitBtn) submitBtn.disabled = false;

                if (result.success) {
                    this.hideModal();
                } else {
                    if (errorEl) errorEl.textContent = result.error;
                }
            });
        }
    },
};

// Export for use in other modules
if (typeof window !== 'undefined') {
    window.Auth = Auth;
}
