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
        const holdingType = document.getElementById('journalFilterHoldingType')?.value;
        if (ticker) params.set('ticker', ticker);
        if (direction) params.set('direction', direction);
        if (pnl) params.set('pnl', pnl);
        if (holdingType) params.set('holding_type', holdingType);

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
            '<th>Date</th><th>Ticker</th><th>Type</th><th>Direction</th><th>P&L</th><th>AI Grade</th><th>Notes</th>' +
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
            const typeBadge = this.holdingTypeBadge(e.holding_type);

            html += `<tr class="journal-entry-row" onclick="Journal.openEntry(${e.id})">
                <td>${e.trade_date || ''}</td>
                <td><strong>${this.esc(e.ticker)}</strong> ${author}</td>
                <td>${typeBadge}</td>
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
                <h2>${this.esc(entry.ticker)} — ${entry.direction || 'long'} ${entry.trade_date || ''} ${this.holdingTypeBadge(entry.holding_type)}</h2>
                <button class="modal-close" onclick="document.getElementById('journalDetailModal').remove()">&times;</button>
            </div>
            <div class="modal-body">
                <!-- Market Annotations -->
                ${this.renderAnnotations(entry.annotations)}
                ${!entry.annotations ? `<div class="journal-annotations"><button class="btn btn-sm btn-ghost" onclick="Journal.refreshAnnotations(${entry.id})">Generate Market Annotations</button></div>` : ''}

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
                    ${plan.thesis || plan.entry_criteria ? `
                        <div class="plan-display">
                            ${plan.thesis ? `<p><strong>Thesis:</strong> ${this.esc(plan.thesis)}</p>` : ''}
                            ${plan.entry_criteria ? `<p><strong>Entry Criteria:</strong> ${this.esc(plan.entry_criteria)}</p>` : ''}
                            <p><strong>Target:</strong> $${plan.price_target || plan.target_price || '-'} | <strong>Stop:</strong> $${plan.stop_loss || plan.stop_price || '-'}</p>
                            ${plan.time_horizon ? `<p><strong>Time Horizon:</strong> ${this.formatTimeHorizon(plan.time_horizon)}</p>` : ''}
                            ${plan.catalysts ? `<p><strong>Catalysts:</strong> ${this.esc(plan.catalysts)}</p>` : ''}
                            ${plan.risks ? `<p><strong>Risks:</strong> ${this.esc(plan.risks)}</p>` : ''}
                            <p><strong>Conviction:</strong> ${this.renderConviction(plan.conviction_level || plan.confidence)} | <strong>Setup:</strong> ${this.esc(plan.setup_type || '-')}</p>
                        </div>
                        <button class="btn btn-sm btn-ghost" style="margin-top:8px;" onclick="Journal.editPlan(${entry.id})">Edit Plan</button>
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

                <!-- Chart Snapshots -->
                <div class="journal-detail-section">
                    <h4>Chart Snapshots</h4>
                    <div class="journal-snapshots-row">
                        <div class="journal-snapshot-col">
                            <span class="muted-text" style="font-size:11px;">Entry</span>
                            ${entry.chart_snapshot_entry
                                ? `<img src="${entry.chart_snapshot_entry}" class="journal-snapshot-img" alt="Entry chart">`
                                : `<button class="btn btn-sm btn-ghost" onclick="Journal.captureSnapshot(${entry.id}, 'entry')">Capture Current Chart</button>`
                            }
                        </div>
                        <div class="journal-snapshot-col">
                            <span class="muted-text" style="font-size:11px;">Exit</span>
                            ${entry.chart_snapshot_exit
                                ? `<img src="${entry.chart_snapshot_exit}" class="journal-snapshot-img" alt="Exit chart">`
                                : `<button class="btn btn-sm btn-ghost" onclick="Journal.captureSnapshot(${entry.id}, 'exit')">Capture Current Chart</button>`
                            }
                        </div>
                    </div>
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

    async captureSnapshot(id, type) {
        if (typeof AlphaCharts === 'undefined' || !AlphaCharts.captureBase64) {
            if (typeof showSnackbar === 'function') showSnackbar('Chart not available — navigate to Security Analysis first', 'error');
            return;
        }
        const base64 = AlphaCharts.captureBase64('analyzeChartContainer');
        if (!base64) {
            if (typeof showSnackbar === 'function') showSnackbar('No chart to capture', 'error');
            return;
        }
        const field = type === 'exit' ? 'chart_snapshot_exit' : 'chart_snapshot_entry';
        try {
            const res = await apiRequest(`/api/journal/entries/${id}`, 'PUT', { [field]: base64 });
            if (res.ok) {
                if (typeof showSnackbar === 'function') showSnackbar(`${type === 'exit' ? 'Exit' : 'Entry'} chart captured`, 'success');
                this.openEntry(id);
            }
        } catch (e) {
            if (typeof showSnackbar === 'function') showSnackbar('Failed to save snapshot', 'error');
        }
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

    showPlanForm(id, existingPlan) {
        if (!this.isPremium && this.trialStatus.pre_trade_plan) {
            this.showUpsellModal('pre_trade_plan', false);
            return;
        }

        const plan = existingPlan || {};
        const existing = document.getElementById('journalPlanModal');
        if (existing) existing.remove();

        const modal = document.createElement('div');
        modal.id = 'journalPlanModal';
        modal.className = 'modal-overlay';
        modal.innerHTML = `
        <div class="modal-content" style="max-width:560px;">
            <div class="modal-header">
                <h2>${plan.thesis ? 'Edit' : 'Create'} Pre-Trade Plan</h2>
                <button class="modal-close" onclick="document.getElementById('journalPlanModal').remove()">&times;</button>
            </div>
            <div class="modal-body">
                <div class="profile-form-group">
                    <label>Trade Thesis</label>
                    <textarea id="jp_thesis" class="profile-input" rows="2" placeholder="What is your thesis for this trade?">${this.esc(plan.thesis || '')}</textarea>
                </div>
                <div class="profile-form-group">
                    <label>Entry Criteria</label>
                    <textarea id="jp_entry_criteria" class="profile-input" rows="2" placeholder="What conditions must be met to enter?">${this.esc(plan.entry_criteria || '')}</textarea>
                </div>
                <div class="profile-form-group" style="display:flex;gap:12px;">
                    <div style="flex:1;">
                        <label>Price Target</label>
                        <input type="number" id="jp_price_target" class="profile-input" step="0.01" placeholder="0.00" value="${plan.price_target || ''}">
                    </div>
                    <div style="flex:1;">
                        <label>Stop Loss</label>
                        <input type="number" id="jp_stop_loss" class="profile-input" step="0.01" placeholder="0.00" value="${plan.stop_loss || ''}">
                    </div>
                </div>
                <div class="profile-form-group" style="display:flex;gap:12px;">
                    <div style="flex:1;">
                        <label>Time Horizon</label>
                        <select id="jp_time_horizon" class="profile-input">
                            <option value="">Select...</option>
                            <option value="day_trade" ${plan.time_horizon === 'day_trade' ? 'selected' : ''}>Day Trade</option>
                            <option value="swing" ${plan.time_horizon === 'swing' ? 'selected' : ''}>Swing (1-5 days)</option>
                            <option value="short_term" ${plan.time_horizon === 'short_term' ? 'selected' : ''}>Short-Term (1-4 weeks)</option>
                            <option value="medium_term" ${plan.time_horizon === 'medium_term' ? 'selected' : ''}>Medium-Term (1-3 months)</option>
                            <option value="long_term" ${plan.time_horizon === 'long_term' ? 'selected' : ''}>Long-Term (3+ months)</option>
                        </select>
                    </div>
                    <div style="flex:1;">
                        <label>Conviction (1-5)</label>
                        <select id="jp_conviction" class="profile-input">
                            <option value="1" ${plan.conviction_level === 1 ? 'selected' : ''}>1 - Speculative</option>
                            <option value="2" ${plan.conviction_level === 2 ? 'selected' : ''}>2 - Low</option>
                            <option value="3" ${(plan.conviction_level === 3 || !plan.conviction_level) ? 'selected' : ''}>3 - Moderate</option>
                            <option value="4" ${plan.conviction_level === 4 ? 'selected' : ''}>4 - High</option>
                            <option value="5" ${plan.conviction_level === 5 ? 'selected' : ''}>5 - Very High</option>
                        </select>
                    </div>
                </div>
                <div class="profile-form-group">
                    <label>Catalysts</label>
                    <textarea id="jp_catalysts" class="profile-input" rows="2" placeholder="What events could drive this trade?">${this.esc(plan.catalysts || '')}</textarea>
                </div>
                <div class="profile-form-group">
                    <label>Risks</label>
                    <textarea id="jp_risks" class="profile-input" rows="2" placeholder="Key risks to the thesis">${this.esc(plan.risks || '')}</textarea>
                </div>
                <div class="profile-form-group">
                    <label>Setup Type</label>
                    <select id="jp_setup_type" class="profile-input">
                        <option value="trend_break" ${plan.setup_type === 'trend_break' ? 'selected' : ''}>Trend Break</option>
                        <option value="mean_reversion" ${plan.setup_type === 'mean_reversion' ? 'selected' : ''}>Mean Reversion</option>
                        <option value="breakout" ${plan.setup_type === 'breakout' ? 'selected' : ''}>Breakout</option>
                        <option value="earnings" ${plan.setup_type === 'earnings' ? 'selected' : ''}>Earnings</option>
                        <option value="momentum" ${plan.setup_type === 'momentum' ? 'selected' : ''}>Momentum</option>
                        <option value="other" ${plan.setup_type === 'other' ? 'selected' : ''}>Other</option>
                    </select>
                </div>
                <button class="btn btn-primary" onclick="Journal.submitPlan(${id})">Save Plan</button>
            </div>
        </div>`;
        document.body.appendChild(modal);
    },

    async editPlan(id) {
        try {
            const res = await apiRequest(`/api/journal/entries/${id}`);
            if (!res.ok) return;
            const data = await res.json();
            this.showPlanForm(id, data.entry?.pre_trade_plan || {});
        } catch (e) { /* ignore */ }
    },

    async submitPlan(id) {
        const data = {
            thesis: document.getElementById('jp_thesis')?.value || '',
            entry_criteria: document.getElementById('jp_entry_criteria')?.value || '',
            price_target: document.getElementById('jp_price_target')?.value || null,
            stop_loss: document.getElementById('jp_stop_loss')?.value || null,
            time_horizon: document.getElementById('jp_time_horizon')?.value || '',
            conviction_level: parseInt(document.getElementById('jp_conviction')?.value) || 3,
            catalysts: document.getElementById('jp_catalysts')?.value || '',
            risks: document.getElementById('jp_risks')?.value || '',
            setup_type: document.getElementById('jp_setup_type')?.value || 'trend_break',
        };

        const res = await this.callPremiumEndpoint(
            `/api/journal/entries/${id}/pre-trade-plan`, 'POST', data, 'pre_trade_plan'
        );
        if (res?.ok) {
            document.getElementById('journalPlanModal')?.remove();
            this.openEntry(id);
            this.trialStatus.pre_trade_plan = true;
            if (typeof showSnackbar === 'function') showSnackbar('Pre-trade plan saved', 'success');
        }
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
            if (typeof Onboarding !== 'undefined') Onboarding.trackJournal();
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

    holdingTypeBadge(type) {
        const badges = {
            swing: '<span class="holding-type-badge swing">Swing</span>',
            long_term: '<span class="holding-type-badge long-term">Long Term</span>',
            tsly_yield: '<span class="holding-type-badge tsly">TSLY Yield</span>',
        };
        return badges[type] || badges.swing;
    },

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

    formatTimeHorizon(horizon) {
        const labels = {
            day_trade: 'Day Trade',
            swing: 'Swing (1-5 days)',
            short_term: 'Short-Term (1-4 weeks)',
            medium_term: 'Medium-Term (1-3 months)',
            long_term: 'Long-Term (3+ months)',
        };
        return labels[horizon] || horizon || '-';
    },

    renderConviction(level) {
        if (!level) return '-/5';
        const labels = { 1: 'Speculative', 2: 'Low', 3: 'Moderate', 4: 'High', 5: 'Very High' };
        return `${level}/5 (${labels[level] || ''})`;
    },

    // ──────────────────────────────────────────────
    // Annotations
    // ──────────────────────────────────────────────

    renderAnnotations(annotations) {
        if (!annotations || typeof annotations !== 'object') {
            return '';
        }

        const badges = [];

        // Market regime badge
        if (annotations.market_regime) {
            const regime = annotations.market_regime;
            const regimeClass = regime === 'BULL' ? 'annotation-bull'
                : regime === 'BEAR' ? 'annotation-bear' : 'annotation-range';
            const regimeLabel = regime === 'BULL' ? 'BULL Regime'
                : regime === 'BEAR' ? 'BEAR Regime' : 'RANGE';
            badges.push(`<span class="annotation-badge ${regimeClass}">${regimeLabel}</span>`);
        }

        // Trend break badge
        if (annotations.trend_break_probability != null) {
            const prob = (annotations.trend_break_probability * 100).toFixed(0);
            const dir = annotations.trend_break_direction || '';
            const dirLabel = dir.charAt(0).toUpperCase() + dir.slice(1).toLowerCase();
            const tbClass = dir.toLowerCase() === 'bullish' ? 'annotation-bull'
                : dir.toLowerCase() === 'bearish' ? 'annotation-bear' : 'annotation-range';
            badges.push(`<span class="annotation-badge ${tbClass}">Trend Break ${prob}% ${dirLabel}</span>`);
        }

        // RSI badge
        if (annotations.rsi != null) {
            const rsi = annotations.rsi;
            const rsiLabel = annotations.rsi_signal || 'Neutral';
            const rsiClass = rsiLabel === 'Oversold' ? 'annotation-bull'
                : rsiLabel === 'Overbought' ? 'annotation-bear' : 'annotation-neutral';
            badges.push(`<span class="annotation-badge ${rsiClass}">RSI ${rsi} (${rsiLabel})</span>`);
        }

        // CCI badge
        if (annotations.cci != null) {
            const cci = annotations.cci;
            const cciLabel = annotations.cci_signal || 'Neutral';
            const cciClass = cciLabel === 'Oversold' ? 'annotation-bull'
                : cciLabel === 'Overbought' ? 'annotation-bear' : 'annotation-neutral';
            badges.push(`<span class="annotation-badge ${cciClass}">CCI ${cci} (${cciLabel})</span>`);
        }

        // SMA 20 vs price badge
        if (annotations.sma_20_vs_price) {
            const above = annotations.sma_20_vs_price === 'above';
            const smaClass = above ? 'annotation-bull' : 'annotation-bear';
            const smaLabel = above ? 'Above SMA 20' : 'Below SMA 20';
            badges.push(`<span class="annotation-badge ${smaClass}">${smaLabel}</span>`);
        }

        // Sector sentiment badge
        if (annotations.sector_sentiment && annotations.sector_sentiment !== 'NEUTRAL') {
            const ss = annotations.sector_sentiment;
            const ssClass = ss === 'BULLISH' ? 'annotation-bull'
                : ss === 'BEARISH' ? 'annotation-bear' : 'annotation-neutral';
            const sectorName = annotations.sector_name ? ` (${annotations.sector_name})` : '';
            badges.push(`<span class="annotation-badge ${ssClass}">Sector ${ss}${sectorName}</span>`);
        }

        if (badges.length === 0) {
            return '';
        }

        return `<div class="journal-annotations">
            <h4>Market Conditions at Entry</h4>
            <div class="annotation-badges">${badges.join('')}</div>
        </div>`;
    },

    async refreshAnnotations(id) {
        try {
            const res = await apiRequest(`/api/journal/entries/${id}/annotations`, 'POST');
            if (res.ok) {
                if (typeof showSnackbar === 'function') showSnackbar('Annotations refreshed', 'success');
                this.openEntry(id);
            }
        } catch (e) { /* ignore */ }
    },

    esc(str) {
        if (!str) return '';
        const d = document.createElement('div');
        d.textContent = str;
        return d.innerHTML;
    },
};

window.Journal = Journal;
