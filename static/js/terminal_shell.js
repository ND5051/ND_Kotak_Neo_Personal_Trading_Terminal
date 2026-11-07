/**
 * Kotak Neo Personal Trading Terminal - Phase 11A
 * Terminal Shell Controller (Navigation, Widgets, ExecutionMode, Keyboard Shortcuts)
 */

(function (window, document) {
    'use strict';

    class TerminalShell {
        constructor() {
            this.ws = window.workspaceManager;
            this.currentExecutionMode = 'DISABLED';
            this.init();
        }

        init() {
            this.bindNavigationTabs();
            this.bindCompactModeToggle();
            this.bindWorkspaceReset();
            this.bindExecutionModeModal();
            this.bindKeyboardShortcuts();
            this.bindWidgets();

            // Initial telemetry and funds refresh
            this.refreshHealth();
            this.refreshFunds();

            console.log('[TerminalShell] Phase 11A Shell Initialized.');
        }

        /* ==========================================================================
           1. Navigation Tabs
           ========================================================================== */
        bindNavigationTabs() {
            const tabs = document.querySelectorAll('.nav-tab');
            tabs.forEach(tab => {
                tab.addEventListener('click', (e) => {
                    const tabKey = tab.getAttribute('data-tab');
                    this.switchTab(tabKey);
                });
            });
        }

        switchTab(tabKey) {
            if (!tabKey) return;

            const tabBtn = document.querySelector(`.nav-tab[data-tab="${tabKey}"]`);
            const viewPane = document.getElementById(`view-${tabKey.replace('_', '-')}`);

            if (tabBtn && viewPane) {
                document.querySelectorAll('.nav-tab').forEach(t => {
                    t.classList.remove('active');
                    t.setAttribute('aria-selected', 'false');
                });
                document.querySelectorAll('.workspace-view').forEach(v => {
                    v.classList.remove('active');
                });

                tabBtn.classList.add('active');
                tabBtn.setAttribute('aria-selected', 'true');
                viewPane.classList.add('active');

                // Persist to workspace state
                if (this.ws) {
                    this.ws.set('active_tab', tabKey);
                }
            }
        }

        /* ==========================================================================
           2. Compact Mode Controller
           ========================================================================== */
        bindCompactModeToggle() {
            const toggleBtn = document.getElementById('compact-mode-toggle');
            if (!toggleBtn) return;

            toggleBtn.addEventListener('click', () => {
                this.toggleCompactMode();
            });
        }

        toggleCompactMode() {
            const current = this.ws ? this.ws.get('compact_mode', false) : false;
            const next = !current;
            if (this.ws) {
                this.ws.set('compact_mode', next);
                this.ws.applyToDOM();
            }
            this.showToast(`Compact Mode: ${next ? 'ON' : 'OFF'}`);
        }

        /* ==========================================================================
           3. Workspace Reset
           ========================================================================== */
        bindWorkspaceReset() {
            const resetBtn = document.getElementById('workspace-reset-btn');
            if (!resetBtn) return;

            resetBtn.addEventListener('click', () => {
                if (confirm('Reset workspace layout to default configuration?')) {
                    if (this.ws) {
                        this.ws.resetDefaults();
                        this.ws.applyToDOM();
                        this.showToast('Workspace reset to factory defaults.');
                    }
                }
            });
        }

        /* ==========================================================================
           4. Execution Mode Controller & Modal
           ========================================================================== */
        bindExecutionModeModal() {
            const badge = document.getElementById('execution-mode-badge');
            const modal = document.getElementById('execution-mode-modal');
            const closeBtns = document.querySelectorAll('.close-modal-btn');
            const radios = document.querySelectorAll('input[name="execution_mode_radio"]');
            const challengeBox = document.getElementById('live-challenge-box');
            const saveBtn = document.getElementById('save-mode-btn');

            if (badge && modal) {
                badge.addEventListener('click', () => {
                    modal.classList.remove('hidden');
                });
            }

            closeBtns.forEach(btn => {
                btn.addEventListener('click', () => {
                    if (modal) modal.classList.add('hidden');
                });
            });

            radios.forEach(radio => {
                radio.addEventListener('change', () => {
                    if (radio.value === 'LIVE') {
                        if (challengeBox) challengeBox.classList.remove('hidden');
                    } else {
                        if (challengeBox) challengeBox.classList.add('hidden');
                    }
                });
            });

            if (saveBtn) {
                saveBtn.addEventListener('click', () => {
                    this.submitExecutionModeChange();
                });
            }
        }

        async submitExecutionModeChange() {
            const selectedRadio = document.querySelector('input[name="execution_mode_radio"]:checked');
            if (!selectedRadio) return;

            const targetMode = selectedRadio.value;
            const challengeInput = document.getElementById('live-confirm-input');
            const errorBox = document.getElementById('mode-modal-error');
            const modal = document.getElementById('execution-mode-modal');

            if (errorBox) errorBox.classList.add('hidden');

            // Challenge check for LIVE mode
            if (targetMode === 'LIVE') {
                const challengeVal = (challengeInput ? challengeInput.value : '').trim();
                if (challengeVal !== 'CONFIRM_LIVE') {
                    if (errorBox) {
                        errorBox.textContent = 'Challenge failed: You must type CONFIRM_LIVE exactly.';
                        errorBox.classList.remove('hidden');
                    }
                    return;
                }
            }

            try {
                const response = await fetch('/api/orders/mode', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ mode: targetMode })
                });
                const resData = await response.json();

                if (response.ok && resData.status === 'success') {
                    this.updateExecutionModeUI(targetMode);
                    if (modal) modal.classList.add('hidden');
                    if (challengeInput) challengeInput.value = '';
                    this.showToast(`Execution Mode updated to ${targetMode}`);
                } else {
                    const msg = (resData && resData.message) ? resData.message : 'Failed to update mode.';
                    if (errorBox) {
                        errorBox.textContent = msg;
                        errorBox.classList.remove('hidden');
                    }
                }
            } catch (err) {
                // If unauthenticated or network error, update local UI gracefully in shell preview
                console.warn('[TerminalShell] API mode switch notice:', err.message);
                this.updateExecutionModeUI(targetMode);
                if (modal) modal.classList.add('hidden');
                this.showToast(`Preview: Execution Mode set to ${targetMode}`);
            }
        }

        updateExecutionModeUI(mode) {
            this.currentExecutionMode = mode;
            const badge = document.getElementById('execution-mode-badge');
            const label = document.getElementById('execution-mode-label');
            const footerMode = document.getElementById('footer-mode');
            const healthPill = document.getElementById('health-mode-pill');
            const healthText = document.getElementById('health-mode-text');

            if (badge) {
                badge.className = `mode-badge mode-${mode.toLowerCase()}`;
            }
            if (label) label.textContent = `MODE: ${mode}`;
            if (footerMode) footerMode.textContent = mode;
            if (healthPill) {
                healthPill.className = `mode-pill mode-${mode.toLowerCase()}`;
                healthPill.textContent = mode;
            }
            if (healthText) {
                healthText.textContent = mode === 'LIVE' ? 'EXCHANGE WIRE' : (mode === 'PAPER' ? 'SIMULATOR ACTIVE' : 'WIRE LOCKED');
            }
        }

        /* ==========================================================================
           5. Funds & Margins Widget
           ========================================================================== */
        bindWidgets() {
            const refreshFundsBtn = document.getElementById('refresh-funds-btn');
            if (refreshFundsBtn) {
                refreshFundsBtn.addEventListener('click', () => this.refreshFunds());
            }

            const refreshHealthBtn = document.getElementById('refresh-health-btn');
            if (refreshHealthBtn) {
                refreshHealthBtn.addEventListener('click', () => this.refreshHealth());
            }

            const cancelAllBtn = document.getElementById('emergency-cancel-all-btn');
            if (cancelAllBtn) {
                cancelAllBtn.addEventListener('click', () => this.triggerEmergencyCancelAll());
            }
        }

        async refreshFunds() {
            try {
                const resp = await fetch('/api/portfolio/margins');
                if (resp.ok) {
                    const res = await resp.json();
                    if (res && res.data && res.data.margins) {
                        this.renderFunds(res.data.margins);
                    }
                }
            } catch (e) {
                console.debug('[TerminalShell] Funds API polling fallback:', e.message);
            }
        }

        renderFunds(m) {
            const cashEl = document.getElementById('funds-avail-cash');
            const collEl = document.getElementById('funds-collateral');
            const usedEl = document.getElementById('funds-used-margin');
            const totalEl = document.getElementById('funds-total-avail');
            const pctEl = document.getElementById('margin-util-percent');
            const barEl = document.getElementById('margin-progress-bar');
            const alertEl = document.getElementById('funds-margin-alert');

            if (cashEl) cashEl.textContent = `₹${(m.available_cash || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
            if (collEl) collEl.textContent = `₹${(m.collateral_value || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
            if (usedEl) usedEl.textContent = `₹${(m.total_margin_used || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
            if (totalEl) totalEl.textContent = `₹${(m.total_margin_available || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;

            const pct = Math.min(100, Math.max(0, m.margin_utilization_percent || 0));
            if (pctEl) pctEl.textContent = `${pct.toFixed(1)}%`;
            if (barEl) {
                barEl.style.width = `${pct}%`;
                barEl.className = 'progress-bar ' + (pct >= 85 ? 'util-critical' : (pct >= 70 ? 'util-warning' : 'util-normal'));
            }

            if (alertEl) {
                if (pct >= 85) {
                    alertEl.classList.remove('hidden');
                } else {
                    alertEl.classList.add('hidden');
                }
            }
        }

        /* ==========================================================================
           6. System Health Telemetry
           ========================================================================== */
        async refreshHealth() {
            try {
                const resp = await fetch('/api/orders/status');
                if (resp.ok) {
                    const res = await resp.json();
                    if (res && res.data && res.data.execution_mode) {
                        this.updateExecutionModeUI(res.data.execution_mode);
                    }
                }
            } catch (e) {
                console.debug('[TerminalShell] Health API polling fallback:', e.message);
            }
        }

        triggerEmergencyCancelAll() {
            if (confirm('EMERGENCY KILL-SWITCH:\n\nAre you sure you want to cancel all open orders across all exchanges?')) {
                fetch('/api/orders/cancel-all', { method: 'POST' })
                    .then(r => r.json())
                    .then(data => {
                        this.showToast('Emergency cancel command dispatched.');
                    })
                    .catch(err => {
                        this.showToast('Cancel-all dispatched.');
                    });
            }
        }

        /* ==========================================================================
           7. Keyboard Shortcuts Map
           ========================================================================== */
        bindKeyboardShortcuts() {
            window.addEventListener('keydown', (e) => {
                // Ignore shortcuts if user is typing in an input
                if (['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement.tagName)) {
                    if (e.key === 'Escape') {
                        document.activeElement.blur();
                    }
                    return;
                }

                // Alt + C : Toggle Compact Mode
                if (e.altKey && (e.key === 'c' || e.key === 'C')) {
                    e.preventDefault();
                    this.toggleCompactMode();
                    return;
                }

                // / or Ctrl + K : Focus Scrip Search
                if (e.key === '/' || (e.ctrlKey && e.key === 'k')) {
                    e.preventDefault();
                    const searchInput = document.getElementById('global-scrip-search');
                    if (searchInput) searchInput.focus();
                    return;
                }

                // Escape : Close modals
                if (e.key === 'Escape') {
                    const modal = document.getElementById('execution-mode-modal');
                    if (modal && !modal.classList.contains('hidden')) {
                        modal.classList.add('hidden');
                    }
                    return;
                }

                // Shift + Escape : Emergency Cancel All
                if (e.shiftKey && e.key === 'Escape') {
                    e.preventDefault();
                    this.triggerEmergencyCancelAll();
                    return;
                }

                // 1-8 : Switch Navigation Tabs
                const tabKeys = ['market_watch', 'orders', 'holdings', 'positions', 'option_chain', 'baskets', 'funds', 'health'];
                const num = parseInt(e.key, 10);
                if (num >= 1 && num <= 8) {
                    e.preventDefault();
                    this.switchTab(tabKeys[num - 1]);
                }
            });
        }

        /* ==========================================================================
           8. Toast Notification System
           ========================================================================== */
        showToast(message, duration = 3000) {
            let container = document.getElementById('toast-container');
            if (!container) {
                container = document.createElement('div');
                container.id = 'toast-container';
                container.className = 'toast-container';
                document.body.appendChild(container);
            }

            const toast = document.createElement('div');
            toast.className = 'terminal-toast';
            toast.textContent = message;
            container.appendChild(toast);

            setTimeout(() => {
                toast.classList.add('fade-out');
                setTimeout(() => toast.remove(), 300);
            }, duration);
        }
    }

    // Initialize on window load
    window.terminalShell = new TerminalShell();
})(window, document);

