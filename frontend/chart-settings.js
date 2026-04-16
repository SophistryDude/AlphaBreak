// ============================================================================
// AlphaBreak Chart Indicator Settings
// ============================================================================
// Configurable indicator parameters with localStorage persistence.
// Provides a gear-icon popover on each indicator pane label and a
// toolbar-level settings dropdown for all indicators at once.
//
// Flow: user clicks gear → popover shows numeric inputs → on Apply,
// settings are saved to localStorage and the indicator is re-rendered
// with the new parameters via toggle-off / toggle-on.
// ============================================================================

const ChartSettings = (() => {

    const STORAGE_KEY = 'chartIndicatorSettings';

    // Registry: each indicator's configurable parameters.
    // `key` matches the indicator name used in toggleIndicator().
    // `params` is an array of { name, label, default, min, max, step }.
    const REGISTRY = {
        rsi: {
            label: 'RSI',
            params: [
                { name: 'period', label: 'Period', default: 14, min: 2, max: 100, step: 1 },
            ],
        },
        macd: {
            label: 'MACD',
            params: [
                { name: 'fast', label: 'Fast EMA', default: 12, min: 2, max: 50, step: 1 },
                { name: 'slow', label: 'Slow EMA', default: 26, min: 5, max: 100, step: 1 },
                { name: 'signal', label: 'Signal', default: 9, min: 2, max: 50, step: 1 },
            ],
        },
        stochastic: {
            label: 'Stochastic',
            params: [
                { name: 'kPeriod', label: '%K Period', default: 14, min: 2, max: 100, step: 1 },
                { name: 'dPeriod', label: '%D Period', default: 3, min: 2, max: 50, step: 1 },
            ],
        },
        atr: {
            label: 'ATR',
            params: [
                { name: 'period', label: 'Period', default: 14, min: 2, max: 100, step: 1 },
            ],
        },
        adx: {
            label: 'ADX',
            params: [
                { name: 'period', label: 'Period', default: 14, min: 2, max: 100, step: 1 },
            ],
        },
        supertrend: {
            label: 'Supertrend',
            params: [
                { name: 'period', label: 'ATR Period', default: 10, min: 2, max: 50, step: 1 },
                { name: 'multiplier', label: 'Multiplier', default: 3, min: 0.5, max: 10, step: 0.5 },
            ],
        },
        keltner: {
            label: 'Keltner Channels',
            params: [
                { name: 'emaPeriod', label: 'EMA Period', default: 20, min: 2, max: 100, step: 1 },
                { name: 'atrPeriod', label: 'ATR Period', default: 10, min: 2, max: 50, step: 1 },
                { name: 'multiplier', label: 'Multiplier', default: 2, min: 0.5, max: 5, step: 0.5 },
            ],
        },
        ichimoku: {
            label: 'Ichimoku Cloud',
            params: [
                { name: 'tenkanP', label: 'Tenkan', default: 9, min: 2, max: 50, step: 1 },
                { name: 'kijunP', label: 'Kijun', default: 26, min: 5, max: 100, step: 1 },
                { name: 'senkouP', label: 'Senkou B', default: 52, min: 10, max: 200, step: 1 },
            ],
        },
        squeeze: {
            label: 'Squeeze Momentum',
            params: [
                { name: 'length', label: 'Length', default: 20, min: 5, max: 50, step: 1 },
                { name: 'mult', label: 'BB Mult', default: 2.0, min: 0.5, max: 5, step: 0.5 },
                { name: 'kcLength', label: 'KC Length', default: 20, min: 5, max: 50, step: 1 },
                { name: 'kcMult', label: 'KC Mult', default: 1.5, min: 0.5, max: 5, step: 0.5 },
            ],
        },
    };

    // ── Settings persistence ────────────────────────────────────────

    let _cache = null;

    function _loadAll() {
        if (_cache) return _cache;
        try {
            const raw = localStorage.getItem(STORAGE_KEY);
            _cache = raw ? JSON.parse(raw) : {};
        } catch (e) { _cache = {}; }
        return _cache;
    }

    function _saveAll() {
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(_cache || {}));
        } catch (e) { /* quota or disabled */ }
    }

    function get(indicator) {
        const all = _loadAll();
        const reg = REGISTRY[indicator];
        if (!reg) return {};
        const saved = all[indicator] || {};
        const result = {};
        for (const p of reg.params) {
            result[p.name] = saved[p.name] != null ? saved[p.name] : p.default;
        }
        return result;
    }

    function set(indicator, values) {
        const all = _loadAll();
        all[indicator] = { ...values };
        _cache = all;
        _saveAll();
    }

    function reset(indicator) {
        const all = _loadAll();
        delete all[indicator];
        _cache = all;
        _saveAll();
    }

    // ── Popover UI ──────────────────────────────────────────────────

    let activePopover = null;

    function _closePopover() {
        if (activePopover) {
            activePopover.remove();
            activePopover = null;
        }
        document.removeEventListener('mousedown', _onOutsideClick, true);
    }

    function _onOutsideClick(e) {
        if (activePopover && !activePopover.contains(e.target)) {
            _closePopover();
        }
    }

    function showSettings(indicator, anchorEl, onApply) {
        _closePopover();

        const reg = REGISTRY[indicator];
        if (!reg) return;

        const current = get(indicator);
        const pop = document.createElement('div');
        pop.className = 'indicator-settings-popover';

        let fieldsHtml = '';
        for (const p of reg.params) {
            const val = current[p.name];
            fieldsHtml += `
                <div class="ind-settings-field">
                    <label>${p.label}</label>
                    <input type="number" data-param="${p.name}"
                           value="${val}" min="${p.min}" max="${p.max}" step="${p.step}">
                </div>
            `;
        }

        pop.innerHTML = `
            <div class="ind-settings-header">
                <span>${reg.label} Settings</span>
                <button class="ind-settings-close" title="Close">&times;</button>
            </div>
            <div class="ind-settings-body">
                ${fieldsHtml}
            </div>
            <div class="ind-settings-footer">
                <button class="ind-settings-reset" title="Restore defaults">Reset</button>
                <button class="ind-settings-apply">Apply</button>
            </div>
        `;

        // Position near the anchor
        document.body.appendChild(pop);
        activePopover = pop;

        const rect = anchorEl.getBoundingClientRect();
        pop.style.top = (rect.bottom + window.scrollY + 6) + 'px';
        let left = rect.left + window.scrollX;
        const popRect = pop.getBoundingClientRect();
        if (left + popRect.width + 8 > window.innerWidth) {
            left = window.innerWidth - popRect.width - 8;
        }
        pop.style.left = Math.max(8, left) + 'px';

        // Events
        pop.querySelector('.ind-settings-close').addEventListener('click', _closePopover);

        pop.querySelector('.ind-settings-apply').addEventListener('click', () => {
            const values = {};
            for (const input of pop.querySelectorAll('input[data-param]')) {
                values[input.dataset.param] = parseFloat(input.value);
            }
            set(indicator, values);
            _closePopover();
            if (onApply) onApply(indicator, values);
        });

        pop.querySelector('.ind-settings-reset').addEventListener('click', () => {
            reset(indicator);
            // Restore default values in inputs
            for (const p of reg.params) {
                const input = pop.querySelector(`input[data-param="${p.name}"]`);
                if (input) input.value = p.default;
            }
        });

        setTimeout(() => document.addEventListener('mousedown', _onOutsideClick, true), 0);
    }

    // ── Gear icon injection ─────────────────────────────────────────
    // Call after an indicator pane is rendered. Adds a small gear icon
    // next to the pane label that opens the settings popover.

    function addGearToPane(containerId, indicator, onApply) {
        if (!REGISTRY[indicator]) return;

        const container = document.getElementById(containerId);
        if (!container) return;

        // Find the most recently added indicator pane label
        const panes = container.querySelectorAll('.indicator-pane');
        const lastPane = panes[panes.length - 1];
        if (!lastPane) return;

        const label = lastPane.querySelector('.indicator-pane-label');
        if (!label || label.querySelector('.ind-settings-gear')) return;

        const gear = document.createElement('span');
        gear.className = 'ind-settings-gear';
        gear.title = 'Settings';
        gear.innerHTML = '&#9881;';
        gear.style.cssText = 'cursor:pointer;margin-left:6px;font-size:12px;opacity:0.6;pointer-events:auto;';
        gear.addEventListener('click', (e) => {
            e.stopPropagation();
            showSettings(indicator, gear, onApply);
        });
        gear.addEventListener('mouseenter', () => { gear.style.opacity = '1'; });
        gear.addEventListener('mouseleave', () => { gear.style.opacity = '0.6'; });
        label.appendChild(gear);
    }

    // ── Indicator Search Dropdown ──────────────────────────────────
    // Filterable list of all 17 indicators with toggle checkboxes.
    // Uses ChartTooltips.DESCRIPTIONS for names and descriptions and
    // ChartPresets.ALL_TOGGLES for the authoritative toggle list.

    let searchMenu = null;

    function _closeSearch() {
        searchMenu?.remove();
        searchMenu = null;
        document.removeEventListener('mousedown', _onSearchOutside, true);
    }

    function _onSearchOutside(e) {
        if (searchMenu && !searchMenu.contains(e.target)) _closeSearch();
    }

    function attachIndicatorSearch(triggerBtn) {
        if (!triggerBtn) return;

        triggerBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            if (searchMenu) { _closeSearch(); return; }

            const tooltips = (typeof ChartTooltips !== 'undefined') ? ChartTooltips.DESCRIPTIONS : {};
            const toggles = (typeof ChartPresets !== 'undefined') ? ChartPresets.ALL_TOGGLES : [];

            const items = toggles.map(id => {
                const desc = tooltips[id] || {};
                const el = document.getElementById(id);
                return { id, title: desc.title || id.replace('toggle', ''), what: desc.what || '', checked: el?.checked || false };
            });

            searchMenu = document.createElement('div');
            searchMenu.className = 'indicator-search-menu';

            const input = document.createElement('input');
            input.className = 'indicator-search-input';
            input.type = 'text';
            input.placeholder = 'Search indicators...';
            searchMenu.appendChild(input);

            const list = document.createElement('div');
            list.className = 'indicator-search-list';
            searchMenu.appendChild(list);

            function render(filter) {
                const q = (filter || '').toLowerCase();
                list.innerHTML = '';
                for (const item of items) {
                    if (q && !item.title.toLowerCase().includes(q) && !item.what.toLowerCase().includes(q)) continue;
                    const el = document.getElementById(item.id);
                    const isChecked = el?.checked || false;
                    const row = document.createElement('div');
                    row.className = 'indicator-search-item';
                    row.innerHTML = `
                        <input type="checkbox" ${isChecked ? 'checked' : ''}>
                        <div class="indicator-search-item-info">
                            <div class="indicator-search-item-name">${item.title}</div>
                            <div class="indicator-search-item-desc">${item.what}</div>
                        </div>
                    `;
                    row.addEventListener('click', (ev) => {
                        ev.stopPropagation();
                        if (el) {
                            el.checked = !el.checked;
                            el.dispatchEvent(new Event('change', { bubbles: true }));
                        }
                        const cb = row.querySelector('input[type="checkbox"]');
                        if (cb) cb.checked = el?.checked || false;
                    });
                    list.appendChild(row);
                }
            }

            render('');
            input.addEventListener('input', () => render(input.value));

            const rect = triggerBtn.getBoundingClientRect();
            searchMenu.style.position = 'absolute';
            searchMenu.style.top = (rect.bottom + window.scrollY + 4) + 'px';
            let left = rect.left + window.scrollX;
            if (left + 300 > window.innerWidth) left = window.innerWidth - 308;
            searchMenu.style.left = Math.max(8, left) + 'px';

            document.body.appendChild(searchMenu);
            input.focus();
            setTimeout(() => document.addEventListener('mousedown', _onSearchOutside, true), 0);
        });
    }

    return { REGISTRY, get, set, reset, showSettings, addGearToPane, attachIndicatorSearch };
})();

window.ChartSettings = ChartSettings;
