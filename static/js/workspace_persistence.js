/**
 * Kotak Neo Personal Trading Terminal - Phase 11A
 * Workspace Persistence Module (Browser localStorage v1)
 */

(function (window) {
    'use strict';

    const STORAGE_KEY = 'kotak_neo_workspace_v1';

    const DEFAULT_WORKSPACE_STATE = {
        version: 1,
        theme: 'light',
        active_tab: 'market_watch',
        compact_mode: false,
        sidebar_collapsed: false,
        sidebar_width: 340,
        selected_watchlist_id: 1,
        selected_underlying: 'NIFTY',
        option_chain_preset: 'ATM_10',
        last_updated: new Date().toISOString()
    };

    class WorkspaceManager {
        constructor() {
            this.state = this.loadState();
        }

        /**
         * Load workspace state from localStorage or return defaults.
         */
        loadState() {
            try {
                const stored = window.localStorage.getItem(STORAGE_KEY);
                if (stored) {
                    const parsed = JSON.parse(stored);
                    if (parsed && parsed.version === DEFAULT_WORKSPACE_STATE.version) {
                        return Object.assign({}, DEFAULT_WORKSPACE_STATE, parsed);
                    }
                }
            } catch (err) {
                console.warn('[WorkspaceManager] Could not read localStorage; using defaults:', err);
            }
            return Object.assign({}, DEFAULT_WORKSPACE_STATE);
        }

        /**
         * Persist current state to localStorage.
         */
        saveState() {
            try {
                this.state.last_updated = new Date().toISOString();
                window.localStorage.setItem(STORAGE_KEY, JSON.stringify(this.state));
                window.dispatchEvent(new CustomEvent('workspace:saved', { detail: this.state }));
            } catch (err) {
                console.error('[WorkspaceManager] Failed to write localStorage:', err);
            }
        }

        /**
         * Get a property from state.
         */
        get(key, defaultValue = null) {
            return this.state[key] !== undefined ? this.state[key] : defaultValue;
        }

        /**
         * Update one or more properties and save.
         */
        set(keyOrUpdates, value = undefined) {
            if (typeof keyOrUpdates === 'object' && keyOrUpdates !== null) {
                Object.assign(this.state, keyOrUpdates);
            } else if (typeof keyOrUpdates === 'string') {
                this.state[keyOrUpdates] = value;
            }
            this.saveState();
        }

        /**
         * Reset workspace to factory defaults.
         */
        resetDefaults() {
            this.state = Object.assign({}, DEFAULT_WORKSPACE_STATE, {
                last_updated: new Date().toISOString()
            });
            this.saveState();
            return this.state;
        }

        /**
         * Apply saved state directly to DOM classes and active tabs.
         */
        applyToDOM() {
            const body = document.getElementById('app-root') || document.body;

            // 0. Theme Application (Light / Dark)
            const currentTheme = this.state.theme || 'light';
            document.documentElement.setAttribute('data-theme', currentTheme);
            if (currentTheme === 'light') {
                body.classList.add('light-theme');
                body.classList.remove('theme-dark', 'dark-theme');
            } else {
                body.classList.add('theme-dark', 'dark-theme');
                body.classList.remove('light-theme');
            }
            const themeIcon = document.getElementById('theme-icon');
            const themeLabel = document.getElementById('theme-label');
            if (themeIcon) themeIcon.textContent = currentTheme === 'light' ? '☀️' : '🌙';
            if (themeLabel) themeLabel.textContent = `Theme: ${currentTheme === 'light' ? 'Light' : 'Dark'}`;

            // 1. Compact Mode
            const compactLabel = document.getElementById('compact-label');
            const heroDensity = document.getElementById('hero-density-state');
            
            if (this.state.compact_mode) {
                body.classList.add('compact-mode');
                if (compactLabel) compactLabel.textContent = 'Compact: ON';
                if (heroDensity) heroDensity.textContent = 'COMPACT';
            } else {
                body.classList.remove('compact-mode');
                if (compactLabel) compactLabel.textContent = 'Compact: OFF';
                if (heroDensity) heroDensity.textContent = 'STANDARD';
            }

            // 2. Active Tab
            const activeTab = this.state.active_tab || 'market_watch';
            const tabBtn = document.querySelector(`.nav-tab[data-tab="${activeTab}"]`);
            const viewPane = document.getElementById(`view-${activeTab.replace('_', '-')}`);

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
            }
        }
    }

    // Export singleton instance to window
    window.workspaceManager = new WorkspaceManager();

    // Auto-apply on DOM load
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            window.workspaceManager.applyToDOM();
        });
    } else {
        window.workspaceManager.applyToDOM();
    }
})(window);

