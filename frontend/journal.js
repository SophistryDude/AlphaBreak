/**
 * Trade Journal Module
 * ====================
 * Full journal: list, detail, create, import, AI scoring, sharing, premium features.
 */

const Journal = {
    entries: [],
    page: 1,
    perPage: 20,
    total: 0,
    viewMode: 'my', // 'my' or 'public'
    isPremium: false,
    trialStatus: {},

    EVENT_LABELS: {
        pre_trade_plan: 'Pre-Trade Plan',
        post_trade_review: 'Post-Trade Review',
        pattern_recognition: 'Pattern Recognition',
    },

    init() {
        // Load premium status
        if (typeof Auth !== 'undefined' && Auth.user) {
            this.isPremium = Auth.user.is_premium || false;
        }
    },

    async load() {
        if (!Auth.isAuthenticated) return;
        this.isPremium = Auth.user?.is_premium || false;
        await this.loadTrialStatus();
        await this.loadEntries();
    },

    async loadTrialStatus() {
        try {
            const res = await apiRequest('/api/user/preferences');
            if (res.ok) {
                const data = await res.json();
                const prefs = data.preferences || {};
                this.trialStatus = {
                    pre_trade_plan: prefs.trial_pre_trade_plan_used === 'true',
                    post_trade_review: prefs.trial_post_trade_review_used === 'true',
                    pattern_recognition: prefs.trial_pattern_recognition_used === 'true',
                };
            }
        } catch (e) { /* ignore */ }
    },

    // ──────────────────────────────────────────────
    // List View
    // ──────────────────────────────────────────────

    async loadEntries() {
        const list = document.getElementById('journalEntryList');
        if (!list) return;

        const params = new URLSearchParams({ page: this.page, per_page: this.perPage });
        const ticker = document.getElementById('journalFilterTicker')?.value;
        const direction = document.getElementById('journalFilterDirection')?.value;
        const pnl = document.getElementById('journalFilterPnl')?.value;
        if (ticker) params.set('ticker', ticker);
        if (direction) params.set('direction', direction);
        if (pnl) params.set('pnl', pnl);

        const endpoint = this.viewMode === 'public' ? '/api/journal/public' : '/api/journal/entries';

        try {
            const res = await apiRequest(`${endpoint}?${params}`);
            if (!res.ok) throw new Error('Failed');
            const data = await res.json();
            this.entries = data.entries || [];
            this.total = data.total || 0;
            this.renderList();
        } catch (e) {
            list.innerHTML = '<p class="empty-state">Failed to load journal entries</p>';
        }
    },

    renderList() {
        const list = document.getElementById('journalEntryList');
        if (!list) return;

        if (!this.entries.length) {
            list.innerHTML = '<p class="empty-state">No journal entries yet. Use the buttons above to import trades or create a new entry.</p>';
            return;
        }

        let html = '<table class="data-table journal-table"><thead><tr>' +
            '<th>Date</th><th>Ticker</th><th>Direction</th><th>P&L</th><th>AI Grade</th><th>Notes</th>' +
            (this.isPremium ? '<th>Tags</th>' : '') +
            '<th>Shared</th><th></th>' +
            '</tr></thead><tbody>';

        for (const e of this.entries) {
            const pnlClass = (e.realized_pnl || 0) > 0 ? 'positive' : (e.realized_pnl || 0) < 0 ? 'negative' : '';
            const pnlStr = e.realized_pnl != null ? `$${e.realized_pnl.toFixed(0)}` : '-';
            const aiGrade = e.ai_score?.overall_grade || '-';
            const aiClass = this.gradeClass(aiGrade);
            const notes = (e.entry_notes || '').substring(0, 40);
            const tags = (e.tags || []).map(t => `<span class="journal-tag">${this.esc(t)}</span>`).join('');
            const shared = e.is_public ? '<span class="shared-badge">Public</span>' : '';
            const author = e.author_name ? `<span class="author-name">${this.esc(e.author_name)}</span>` : '';

            html += `<tr class="journal-entry-row" onclick="Journal.openEntry(${e.id})">
                <td>${e.trade_date || ''}</td>
                <td><strong>${this.esc(e.ticker)}</strong> ${author}</td>
                <td>${e.direction || ''}</td>
                <td class="${pnlClass}">${pnlStr}</td>
                <td><span class="journal-ai-badge ${aiClass}">${aiGrade}</span></td>
                <td class="notes-preview">${this.esc(notes)}</td>
                ${this.isPremium ? `<td>${tags}</td>` : ''}
                <td>${shared}</td>
                <td><button class="btn-icon" title="View">&#9654;</button></td>
            </tr>`;
        }

        html += '</tbody></table>';

        // Pagination
        const totalPages = Math.ceil(this.total / this.perPage);
        if (totalPages > 1) {
            html += '<div class="journal-pagination">';
            if (this.page > 1) html += `<button class="btn btn-sm btn-ghost" onclick="Journal.page=${this.page - 1};Journal.loadEntries()">Prev</button>`;
            html += `<span>Page ${this.page} of ${totalPages}</span>`;
            if (this.page < totalPages) html += `<button class="btn btn-sm btn-ghost" onclick="Journal.page=${this.page + 1};Journal.loadEntries()">Next</button>`;
            html += '</div>';
        }

        list.innerHTML = html;
    },

    // ──────────────────────────────────────────────
    // Entry Detail Modal
    // ──────────────────────────────────────────────

    async openEntry(id) {
        try {
            const res = await apiRequest(`/api/journal/entries/${id}`);
            if (!res.ok) throw new Error('Failed');
            const data = await res.json();
            this.renderDetailModal(data.entry);
        } catch (e) {
            if (typeof showSnackbar === 'function') showSnackbar('Failed to load entry', 'error');
        }
    },

    renderDetailModal(entry) {
        const existing = document.getElementById('journalDetailModal');
        if (existing) existing.remove();

        const pnlClass = (entry.realized_pnl || 0) > 0 ? 'positive' : 'negative';
        const ai = entry.ai_score || {};
        const plan = entry.pre_trade_plan || {};
        const review = entry.post_trade_review || {};
        const pattern = entry.pattern_data || {};

        const modal = document.createElement('div');
        modal.id = 'journalDetailModal';
        modal.className = 'modal-overlay';
        modal.innerHTML = `
        <div class="modal-content journal-detail-modal">
            <div class="modal-header">
                <h2>${this.esc(entry.ticker)} — ${entry.direction || 'long'} ${entry.trade_date || ''}</h2>
                <button class="modal-close" onclick="document.getElementById('journalDetailModal').remove()">&times;</button>
            </div>
            <div class="modal-body">
                <!-- P&L Summary -->
                <div class="journal-detail-pnl">
                    <span class="pnl-amount ${pnlClass}">${entry.realized_pnl != null ? '$' + entry.realized_pnl.toFixed(2) : 'Open'}</span>
                    <span class="pnl-pct ${pnlClass}">${entry.realized_pnl_pct != null ? (entry.realized_pnl_pct * 100).toFixed(2) + '%' : ''}</span>
                    <span>Entry: $${entry.entry_price || '-'} | Exit: $${entry.exit_price || '-'} | Qty: ${entry.quantity || '-'}</span>
                </div>

                <!-- Notes (Free) -->
                <div class="journal-detail-section">
                    <h4>Entry Notes</h4>
                    <textarea id="jd_entry_notes" class="profile-input" rows="3">${this.esc(entry.entry_notes || '')}</textarea>
                </div>
                <div class="journal-detail-section">
                    <h4>Exit Notes</h4>
                    <textarea id="jd_exit_notes" class="profile-input" rows="3">${this.esc(entry.exit_notes || '')}</textarea>
                </div>
                <div class="journal-detail-section">
                    <h4>Lessons Learned</h4>
                    <textarea id="jd_lessons" class="profile-input" rows="2">${this.esc(entry.lessons_learned || '')}</textarea>
                </div>

                <!-- AI Score (Free) -->
                <div class="journal-detail-section">
                    <h4>AI Trade Score ${ai.overall_grade ? `<span class="journal-ai-badge ${this.gradeClass(ai.overall_grade)}">${ai.overall_grade}</span>` : ''}</h4>
                    ${ai.entry_score != null ? `
                        <div class="ai-score-grid">
                            <div>Entry: <strong>${ai.entry_score}/100</strong></div>
                            <div>Exit: <strong>${ai.exit_score}/100</strong></div>
                            <div>Timing: <strong>${ai.timing_grade || '-'}</strong></div>
                            <div>Overall: <strong>${ai.overall_score}/100</strong></div>
                        </div>
                        ${ai.suggestions ? `<ul class="ai-suggestions">${ai.suggestions.map(s => `<li>${this.esc(s)}</li>`).join('')}</ul>` : ''}
                    ` : `<button class="btn btn-sm btn-primary" onclick="Journal.generateAiScore(${entry.id})">Generate AI Score</button>`}
                </div>

                <!-- Share (Free) -->
                <div class="journal-detail-section">
                    <h4>Sharing</h4>
                    <label class="toggle">
                        <input type="checkbox" ${entry.is_public ? 'checked' : ''} onchange="Journal.toggleShare(${entry.id}, this.checked)">
                        <span class="toggle-slider"></span>
                    </label>
                    <span style="margin-left:8px;">${entry.is_public ? 'Public — visible to community' : 'Private'}</span>
                </div>

                <!-- Pre-Trade Plan (Premium/Trial) -->
                <div class="journal-detail-section premium-section">
                    <h4>Pre-Trade Plan ${this.premiumBadge('pre_trade_plan')}</h4>
                    ${plan.thesis ? `
                        <div class="plan-display">
                            <p><strong>Thesis:</strong> ${this.esc(plan.thesis)}</p>
                            <p><strong>Setup:</strong> ${this.esc(plan.setup_type || '')}</p>
                            <p><strong>R:R:</strong> ${plan.risk_reward || '-'} | Target: $${plan.target_price || '-'} | Stop: $${plan.stop_price || '-'}</p>
                            <p><strong>Confidence:</strong> ${plan.confidence || '-'}/5</p>
                        </div>
                    ` : `<button class="btn btn-sm ${this.isPremium ? 'btn-primary' : 'btn-ghost'}" onclick="Journal.showPlanForm(${entry.id})">${this.premiumButtonLabel('pre_trade_plan', 'Create Plan')}</button>`}
                </div>

                <!-- Post-Trade Review (Premium/Trial) -->
                <div class="journal-detail-section premium-section">
                    <h4>Post-Trade Review ${this.premiumBadge('post_trade_review')}</h4>
                    ${review.grade ? `
                        <div class="review-display">
                            <p><strong>Grade:</strong> ${review.grade}</p>
                            <p><strong>What worked:</strong> ${this.esc(review.what_worked || '')}</p>
                            <p><strong>What failed:</strong> ${this.esc(review.what_failed || '')}</p>
                            <p><strong>Would change:</strong> ${this.esc(review.would_change || '')}</p>
                        </div>
                    ` : `<button class="btn btn-sm ${this.isPremium ? 'btn-primary' : 'btn-ghost'}" onclick="Journal.showReviewForm(${entry.id})">${this.premiumButtonLabel('post_trade_review', 'Write Review')}</button>`}
                </div>

                <!-- Pattern (Premium/Trial) -->
                <div class="journal-detail-section premium-section">
                    <h4>Pattern Detection ${this.premiumBadge('pattern_recognition')}</h4>
                    ${pattern.detected_pattern ? `
                        <div class="pattern-display">
                            <span class="journal-tag">${pattern.detected_pattern.replace(/_/g, ' ')}</span>
                            <span>Confidence: ${(pattern.confidence * 100).toFixed(0)}%</span>
                        </div>
                    ` : `<button class="btn btn-sm ${this.isPremium ? 'btn-primary' : 'btn-ghost'}" onclick="Journal.detectPattern(${entry.id})">${this.premiumButtonLabel('pattern_recognition', 'Detect Pattern')}</button>`}
                </div>

                <!-- Tags (Premium) -->
                ${this.isPremium ? `
                <div class="journal-detail-section">
                    <h4>Tags</h4>
                    <div id="jd_tags_container">
                        ${(entry.tags || []).map(t => `<span class="journal-tag">${this.esc(t)} <button onclick="Journal.removeTag(${entry.id}, '${t}')">&times;</button></span>`).join('')}
                    </div>
                    <div class="profile-input-row" style="margin-top:8px;">
                        <input type="text" id="jd_new_tag" class="profile-input" placeholder="Add tag..." style="max-width:200px;">
                        <button class="btn btn-sm btn-ghost" onclick="Journal.addTag(${entry.id})">Add</button>
                    </div>
                </div>
                ` : `<div class="journal-detail-section premium-section">
                    <h4>Tags <span class="premium-lock-badge">Premium</span></h4>
                    <p class="muted-text">Upgrade to Premium to categorize trades with custom tags.</p>
                </div>`}

                <!-- Actions -->
                <div class="journal-detail-actions">
                    <button class="btn btn-primary" onclick="Journal.saveNotes(${entry.id})">Save Notes</button>
                    <button class="btn btn-ghost btn-danger" onclick="Journal.deleteEntry(${entry.id})">Delete</button>
                </div>
            </div>
        </div>`;

        document.body.appendChild(modal);
    },

    // ──────────────────────────────────────────────
    // Actions
    // ──────────────────────────────────────────────

    async saveNotes(id) {
        const data = {
            entry_notes: document.getElementById('jd_entry_notes')?.value || '',
            exit_notes: document.getElementById('jd_exit_notes')?.value || '',
            lessons_learned: document.getElementById('jd_lessons')?.value || '',
        };
        try {
            const res = await apiRequest(`/api/journal/entries/${id}`, 'PUT', data);
            if (res.ok) {
                if (typeof showSnackbar === 'function') showSnackbar('Notes saved', 'success');
            }
        } catch (e) { /* ignore */ }
    },

    async generateAiScore(id) {
        try {
            const res = await apiRequest(`/api/journal/entries/${id}/ai-score`, 'POST');
            if (res.ok) {
                if (typeof showSnackbar === 'function') showSnackbar('AI Score generated', 'success');
                this.openEntry(id); // Refresh detail
            }
        } catch (e) { /* ignore */ }
    },

    async toggleShare(id, isPublic) {
        await apiRequest(`/api/journal/entries/${id}/share`, 'PUT', { is_public: isPublic });
    },

    async scoreAll() {
        try {
            const res = await apiRequest('/api/journal/score-all', 'POST');
            if (res.ok) {
                const data = await res.json();
                if (typeof showSnackbar === 'function') showSnackbar(`Scored ${data.scored} trades`, 'success');
                this.loadEntries();
            }
        } catch (e) { /* ignore */ }
    },

    async importTrades() {
        try {
            const res = await apiRequest('/api/journal/import-trades', 'POST');
            if (res.ok) {
                const data = await res.json();
                if (typeof showSnackbar === 'function') showSnackbar(`Imported ${data.imported} trades`, 'success');
                this.loadEntries();
            }
        } catch (e) { /* ignore */ }
    },

    async deleteEntry(id) {
        if (!confirm('Delete this journal entry?')) return;
        await apiRequest(`/api/journal/entries/${id}`, 'DELETE');
        document.getElementById('journalDetailModal')?.remove();
        this.loadEntries();
    },

    // ──────────────────────────────────────────────
    // Premium Features
    // ──────────────────────────────────────────────

    async callPremiumEndpoint(url, method, body, feature) {
        const res = await apiRequest(url, method, body);
        if (res.status === 403) {
            const data = await res.json();
            if (data.upgrade_required) {
                this.showUpsellModal(feature, !data.trial_used);
                return null;
            }
        }
        return res;
    },

    async detectPattern(id) {
        const res = await this.callPremiumEndpoint(`/api/journal/entries/${id}/pattern`, 'POST', null, 'pattern_recognition');
        if (res?.ok) {
            if (typeof showSnackbar === 'function') showSnackbar('Pattern detected', 'success');
            this.openEntry(id);
        }
    },

    showPlanForm(id) {
        if (!this.isPremium && this.trialStatus.pre_trade_plan) {
            this.showUpsellModal('pre_trade_plan', false);
            return;
        }
        const thesis = prompt('What is your trade thesis?');
        if (!thesis) return;
        const setup = prompt('Setup type (trend_break, mean_reversion, breakout, earnings):') || 'trend_break';
        const target = prompt('Target price:') || '';
        const stop = prompt('Stop price:') || '';
        const confidence = prompt('Confidence (1-5):') || '3';
        const rr = target && stop ? (Math.abs(parseFloat(target) - parseFloat(stop)) > 0 ? 'calculated' : '-') : '-';

        this.callPremiumEndpoint(`/api/journal/entries/${id}/pre-trade-plan`, 'POST', {
            thesis, setup_type: setup, target_price: target, stop_price: stop,
            confidence: parseInt(confidence), risk_reward: rr,
        }, 'pre_trade_plan').then(res => {
            if (res?.ok) { this.openEntry(id); this.trialStatus.pre_trade_plan = true; }
        });
    },

    showReviewForm(id) {
        if (!this.isPremium && this.trialStatus.post_trade_review) {
            this.showUpsellModal('post_trade_review', false);
            return;
        }
        const grade = prompt('Grade this trade (A, B, C, D, F):') || 'C';
        const worked = prompt('What worked?') || '';
        const failed = prompt('What failed?') || '';
        const change = prompt('What would you change?') || '';

        this.callPremiumEndpoint(`/api/journal/entries/${id}/post-trade-review`, 'POST', {
            grade, what_worked: worked, what_failed: failed, would_change: change,
        }, 'post_trade_review').then(res => {
            if (res?.ok) { this.openEntry(id); this.trialStatus.post_trade_review = true; }
        });
    },

    async addTag(id) {
        const input = document.getElementById('jd_new_tag');
        const tag = input?.value?.trim();
        if (!tag) return;

        const entry = this.entries.find(e => e.id === id);
        const currentTags = entry?.tags || [];
        const newTags = [...new Set([...currentTags, tag])];

        const res = await apiRequest(`/api/journal/entries/${id}/tags`, 'PUT', { tags: newTags });
        if (res.ok) { input.value = ''; this.openEntry(id); }
    },

    async removeTag(id, tag) {
        const entry = this.entries.find(e => e.id === id);
        const newTags = (entry?.tags || []).filter(t => t !== tag);
        await apiRequest(`/api/journal/entries/${id}/tags`, 'PUT', { tags: newTags });
        this.openEntry(id);
    },

    // ──────────────────────────────────────────────
    // New Entry Modal
    // ──────────────────────────────────────────────

    showNewEntryModal() {
        const existing = document.getElementById('journalNewModal');
        if (existing) existing.remove();

        const modal = document.createElement('div');
        modal.id = 'journalNewModal';
        modal.className = 'modal-overlay';
        modal.innerHTML = `
        <div class="modal-content" style="max-width:500px;">
            <div class="modal-header">
                <h2>New Journal Entry</h2>
                <button class="modal-close" onclick="document.getElementById('journalNewModal').remove()">&times;</button>
            </div>
            <div class="modal-body">
                <div class="profile-form-group">
                    <label>Ticker</label>
                    <input type="text" id="jn_ticker" class="profile-input" placeholder="AAPL" maxlength="10">
                </div>
                <div class="profile-form-group">
                    <label>Direction</label>
                    <select id="jn_direction" class="profile-input"><option value="long">Long</option><option value="short">Short</option></select>
                </div>
                <div class="profile-form-group">
                    <label>Entry Price</label>
                    <input type="number" id="jn_entry_price" class="profile-input" step="0.01">
                </div>
                <div class="profile-form-group">
                    <label>Entry Notes</label>
                    <textarea id="jn_notes" class="profile-input" rows="3" placeholder="Why are you entering this trade?"></textarea>
                </div>
                <button class="btn btn-primary" onclick="Journal.createManualEntry()">Create Entry</button>
            </div>
        </div>`;
        document.body.appendChild(modal);
    },

    async createManualEntry() {
        const data = {
            ticker: document.getElementById('jn_ticker')?.value?.toUpperCase(),
            direction: document.getElementById('jn_direction')?.value,
            entry_price: parseFloat(document.getElementById('jn_entry_price')?.value) || null,
            trade_date: new Date().toISOString().slice(0, 10),
            entry_notes: document.getElementById('jn_notes')?.value || '',
        };
        if (!data.ticker) return;

        const res = await apiRequest('/api/journal/entries', 'POST', data);
        if (res.ok) {
            document.getElementById('journalNewModal')?.remove();
            this.loadEntries();
            if (typeof showSnackbar === 'function') showSnackbar('Entry created', 'success');
        }
    },

    // ──────────────────────────────────────────────
    // Upsell Modal
    // ──────────────────────────────────────────────

    showUpsellModal(feature, trialAvailable) {
        const existing = document.getElementById('premiumUpsellModal');
        if (existing) existing.remove();

        const label = this.EVENT_LABELS[feature] || feature;
        const modal = document.createElement('div');
        modal.id = 'premiumUpsellModal';
        modal.className = 'modal-overlay';
        modal.innerHTML = `
        <div class="modal-content premium-upsell-content">
            <div class="modal-header">
                <h2>Premium Feature</h2>
                <button class="modal-close" onclick="document.getElementById('premiumUpsellModal').remove()">&times;</button>
            </div>
            <div class="modal-body" style="text-align:center;">
                <div class="premium-badge" style="font-size:16px;margin:20px 0;">Premium</div>
                <h3>${label}</h3>
                ${trialAvailable
                    ? `<p>You have <strong>1 free trial</strong> remaining for this feature.</p>
                       <button class="btn btn-primary" onclick="document.getElementById('premiumUpsellModal').remove()">Use Free Trial</button>`
                    : `<p>You've used your free trial. Upgrade to Premium for unlimited access.</p>`}
                <button class="btn btn-ghost" style="margin-top:12px;" onclick="document.getElementById('premiumUpsellModal').remove()">
                    ${trialAvailable ? 'Maybe Later' : 'Close'}
                </button>
            </div>
        </div>`;
        document.body.appendChild(modal);
    },

    // ──────────────────────────────────────────────
    // View Toggles
    // ──────────────────────────────────────────────

    switchView(mode) {
        this.viewMode = mode;
        this.page = 1;
        document.getElementById('journalMyBtn')?.classList.toggle('active', mode === 'my');
        document.getElementById('journalPublicBtn')?.classList.toggle('active', mode === 'public');
        this.loadEntries();
    },

    // ──────────────────────────────────────────────
    // Helpers
    // ──────────────────────────────────────────────

    gradeClass(grade) {
        const map = { A: 'grade-a', B: 'grade-b', C: 'grade-c', D: 'grade-d', F: 'grade-f' };
        return map[grade] || '';
    },

    premiumBadge(feature) {
        if (this.isPremium) return '';
        const used = this.trialStatus[feature];
        if (used) return '<span class="premium-lock-badge">Premium</span>';
        return '<span class="premium-trial-badge">1 Free Trial</span>';
    },

    premiumButtonLabel(feature, defaultLabel) {
        if (this.isPremium) return defaultLabel;
        const used = this.trialStatus[feature];
        return used ? 'Upgrade to Premium' : `${defaultLabel} (Free Trial)`;
    },

    esc(str) {
        if (!str) return '';
        const d = document.createElement('div');
        d.textContent = str;
        return d.innerHTML;
    },
};

window.Journal = Journal;
