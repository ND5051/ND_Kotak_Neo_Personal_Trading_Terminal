/**
 * Kotak Neo Personal Trading Terminal - Phase 11B
 * Market Watch Controller (Watchlists, Search Ctrl+K, Depth Popover, Drag & Drop)
 */

(function (window, document) {
    'use strict';

    class MarketWatchController {
        constructor() {
            this.watchlists = [];
            this.activeWatchlistId = 1;
            this.activeWatchlistIndex = 0;
            this.focusedRowIndex = -1;
            this.searchDebounceTimer = null;
            this.selectedSearchResultIndex = -1;
            this.currentDepthToken = null;
            this.ws = window.workspaceManager;

            this.init();
        }

        init() {
            this.bindWatchlistTabs();
            this.bindSearchModal();
            this.bindDepthModal();
            this.bindKeyboardShortcuts();
            this.loadWatchlists();

            console.log('[MarketWatchController] Phase 11B Initialized.');
        }

        /* ==========================================================================
           1. Watchlists & Tabs Management
           ========================================================================== */
        bindWatchlistTabs() {
            const tabs = document.querySelectorAll('.mw-tab');
            tabs.forEach(tab => {
                tab.addEventListener('click', (e) => {
                    const wlId = parseInt(tab.getAttribute('data-wl-id'), 10);
                    const wlIdx = parseInt(tab.getAttribute('data-wl-index'), 10);
                    this.switchWatchlist(wlId, wlIdx);
                });
            });

            const editBtn = document.getElementById('mw-tab-edit-btn');
            if (editBtn) {
                editBtn.addEventListener('click', () => this.renameActiveWatchlist());
            }

            const emptySearchBtn = document.getElementById('mw-empty-search-btn');
            if (emptySearchBtn) {
                emptySearchBtn.addEventListener('click', () => this.openSearchModal());
            }
        }

        async loadWatchlists() {
            try {
                const resp = await fetch('/api/market-watch/watchlists');
                if (resp.ok) {
                    const data = await resp.json();
                    if (data && data.data && data.data.watchlists && data.data.watchlists.length > 0) {
                        this.watchlists = data.data.watchlists;
                    }
                }
            } catch (err) {
                console.debug('[MarketWatch] Could not load API watchlists, using local defaults:', err.message);
            }

            // Fallback to default watchlists if empty
            if (!this.watchlists || this.watchlists.length === 0) {
                this.watchlists = [
                    {
                        id: 1,
                        name: "Indices & Core",
                        is_default: true,
                        items: [
                            { id: 101, instrument_token: "26000", exchange_segment: "nse_cm", trading_symbol: "NIFTY 50", quote: { ltp: 24520.50, change: 102.30, percent_change: 0.42 } },
                            { id: 102, instrument_token: "26009", exchange_segment: "nse_cm", trading_symbol: "BANKNIFTY", quote: { ltp: 52180.20, change: -78.40, percent_change: -0.15 } },
                            { id: 103, instrument_token: "2885", exchange_segment: "nse_cm", trading_symbol: "RELIANCE EQ", quote: { ltp: 2945.00, change: 15.50, percent_change: 0.53 } },
                            { id: 104, instrument_token: "1333", exchange_segment: "nse_cm", trading_symbol: "HDFCBANK EQ", quote: { ltp: 1680.20, change: -4.30, percent_change: -0.26 } },
                            { id: 105, instrument_token: "45210", exchange_segment: "nse_fo", trading_symbol: "NIFTY28NOV24500CE", quote: { ltp: 142.50, change: 12.40, percent_change: 9.53 } },
                            { id: 106, instrument_token: "45211", exchange_segment: "nse_fo", trading_symbol: "NIFTY28NOV24500PE", quote: { ltp: 98.20, change: -8.10, percent_change: -7.62 } }
                        ]
                    },
                    { id: 2, name: "Options Active", is_default: false, items: [] },
                    { id: 3, name: "Bank F&O", is_default: false, items: [] },
                    { id: 4, name: "High Beta", is_default: false, items: [] },
                    { id: 5, name: "Watchlist 5", is_default: false, items: [] }
                ];
            }

            // Restore last selected watchlist from persistence
            if (this.ws) {
                const savedWlId = this.ws.get('selected_watchlist_id', 1);
                const matchIdx = this.watchlists.findIndex(w => w.id === savedWlId);
                if (matchIdx !== -1) {
                    this.activeWatchlistId = savedWlId;
                    this.activeWatchlistIndex = matchIdx;
                }
            }

            this.renderTabs();
            this.renderActiveWatchlist();
        }

        renderTabs() {
            this.watchlists.forEach((wl, idx) => {
                if (idx < 5) {
                    const tabBtn = document.getElementById(`mw-tab-${idx + 1}`);
                    if (tabBtn) {
                        tabBtn.setAttribute('data-wl-id', wl.id);
                        const nameEl = tabBtn.querySelector('.mw-tab-name');
                        if (nameEl) nameEl.textContent = wl.name;

                        if (idx === this.activeWatchlistIndex) {
                            tabBtn.classList.add('active');
                        } else {
                            tabBtn.classList.remove('active');
                        }
                    }
                }
            });
        }

        switchWatchlist(wlId, wlIdx) {
            this.activeWatchlistId = wlId;
            this.activeWatchlistIndex = wlIdx;

            document.querySelectorAll('.mw-tab').forEach((t, i) => {
                if (i === wlIdx) {
                    t.classList.add('active');
                } else {
                    t.classList.remove('active');
                }
            });

            if (this.ws) {
                this.ws.set('selected_watchlist_id', wlId);
            }

            this.renderActiveWatchlist();
        }

        renameActiveWatchlist() {
            const currentWl = this.watchlists[this.activeWatchlistIndex];
            if (!currentWl) return;

            const newName = prompt('Enter new watchlist name:', currentWl.name);
            if (newName && newName.trim().length >= 2) {
                currentWl.name = newName.trim();
                this.renderTabs();
                const activeLabel = document.getElementById('mw-active-wl-label');
                if (activeLabel) activeLabel.textContent = `Active: ${currentWl.name}`;
            }
        }

        /* ==========================================================================
           2. Scrip Grid Rendering & Actions
           ========================================================================== */
        renderActiveWatchlist() {
            const currentWl = this.watchlists[this.activeWatchlistIndex] || { items: [] };
            const scripListEl = document.getElementById('mw-scrip-list');
            const emptyStateEl = document.getElementById('mw-empty-state');
            const quotaCountEl = document.getElementById('mw-quota-count');
            const activeLabel = document.getElementById('mw-active-wl-label');

            if (!scripListEl) return;

            const items = currentWl.items || [];
            if (quotaCountEl) quotaCountEl.textContent = items.length;
            if (activeLabel) activeLabel.textContent = `Active: ${currentWl.name || 'Watchlist'}`;

            if (items.length === 0) {
                scripListEl.innerHTML = '';
                if (emptyStateEl) emptyStateEl.classList.remove('hidden');
                return;
            }

            if (emptyStateEl) emptyStateEl.classList.add('hidden');
            scripListEl.innerHTML = '';

            items.forEach((item, index) => {
                const row = this.createScripRow(item, index);
                scripListEl.appendChild(row);
            });
        }

        createScripRow(item, index) {
            const q = item.quote || { ltp: 100.0, change: 0.0, percent_change: 0.0 };
            const isPositive = (q.change || 0) >= 0;
            const chgSign = isPositive ? '+' : '';
            const chgClass = isPositive ? 'text-success' : 'text-danger';

            const row = document.createElement('div');
            row.className = 'scrip-row';
            row.setAttribute('data-token', item.instrument_token);
            row.setAttribute('data-segment', item.exchange_segment);
            row.setAttribute('data-symbol', item.trading_symbol);
            row.setAttribute('data-item-id', item.id);
            row.setAttribute('data-index', index);
            row.setAttribute('draggable', 'true');

            row.innerHTML = `
                <div class="scrip-primary-line">
                    <div class="scrip-symbol-wrap">
                        <span class="scrip-symbol">${item.trading_symbol}</span>
                        <span class="scrip-seg-tag">${(item.exchange_segment || 'nse_cm').toUpperCase()}</span>
                    </div>
                    <div class="scrip-ltp-wrap">
                        <span class="scrip-ltp font-numeric ${chgClass}" id="scrip-ltp-${item.instrument_token}">${(q.ltp || 0).toFixed(2)}</span>
                    </div>
                </div>
                <div class="scrip-secondary-line">
                    <span class="scrip-contract-meta">${item.display_name || item.trading_symbol}</span>
                    <span class="scrip-chg font-numeric ${chgClass}" id="scrip-chg-${item.instrument_token}">${chgSign}${(q.change || 0).toFixed(2)} (${chgSign}${(q.percent_change || 0).toFixed(2)}%)</span>
                </div>
                <div class="scrip-hover-actions">
                    <button class="action-btn action-btn-buy" title="Buy (B)">B</button>
                    <button class="action-btn action-btn-sell" title="Sell (S)">S</button>
                    <button class="action-btn action-btn-depth" title="Market Depth (D)">D</button>
                    <button class="action-btn action-btn-chain" title="Option Chain (O)">O</button>
                    <button class="action-btn action-btn-delete" title="Delete Scrip">✕</button>
                </div>
            `;

            // Hover actions click handlers
            const buyBtn = row.querySelector('.action-btn-buy');
            const sellBtn = row.querySelector('.action-btn-sell');
            const depthBtn = row.querySelector('.action-btn-depth');
            const chainBtn = row.querySelector('.action-btn-chain');
            const delBtn = row.querySelector('.action-btn-delete');

            if (buyBtn) {
                buyBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    this.launchOrderTicket(item, 'BUY');
                });
            }

            if (sellBtn) {
                sellBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    this.launchOrderTicket(item, 'SELL');
                });
            }

            if (depthBtn) {
                depthBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    this.openMarketDepth(item);
                });
            }

            if (chainBtn) {
                chainBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    this.openOptionChain(item);
                });
            }

            if (delBtn) {
                delBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    this.deleteScrip(item);
                });
            }

            // Click row to focus
            row.addEventListener('click', () => {
                document.querySelectorAll('.scrip-row').forEach(r => r.classList.remove('focused'));
                row.classList.add('focused');
                this.focusedRowIndex = index;
            });

            // HTML5 Drag-and-Drop Reordering
            this.bindDragAndDrop(row, index);

            return row;
        }

        bindDragAndDrop(row, index) {
            row.addEventListener('dragstart', (e) => {
                row.classList.add('dragging');
                e.dataTransfer.setData('text/plain', index);
            });

            row.addEventListener('dragend', () => {
                row.classList.remove('dragging');
                document.querySelectorAll('.scrip-row').forEach(r => r.classList.remove('drag-over'));
            });

            row.addEventListener('dragover', (e) => {
                e.preventDefault();
                row.classList.add('drag-over');
            });

            row.addEventListener('dragleave', () => {
                row.classList.remove('drag-over');
            });

            row.addEventListener('drop', (e) => {
                e.preventDefault();
                row.classList.remove('drag-over');
                const fromIndex = parseInt(e.dataTransfer.getData('text/plain'), 10);
                const toIndex = index;

                if (fromIndex !== toIndex) {
                    this.reorderScrips(fromIndex, toIndex);
                }
            });
        }

        reorderScrips(fromIndex, toIndex) {
            const currentWl = this.watchlists[this.activeWatchlistIndex];
            if (!currentWl || !currentWl.items) return;

            const movedItem = currentWl.items.splice(fromIndex, 1)[0];
            currentWl.items.splice(toIndex, 0, movedItem);

            this.renderActiveWatchlist();

            // Sync with backend API
            const itemIds = currentWl.items.map(it => it.id);
            fetch(`/api/market-watch/watchlists/${currentWl.id}/reorder`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ item_ids: itemIds })
            }).catch(e => console.debug('[MarketWatch] Reorder synced locally:', e.message));
        }

        async deleteScrip(item) {
            const currentWl = this.watchlists[this.activeWatchlistIndex];
            if (!currentWl || !currentWl.items) return;

            const idx = currentWl.items.findIndex(it => it.id === item.id);
            if (idx !== -1) {
                currentWl.items.splice(idx, 1);
                this.renderActiveWatchlist();

                // Backend call
                fetch(`/api/market-watch/watchlists/${currentWl.id}/items/${item.id}`, {
                    method: 'DELETE'
                }).catch(e => console.debug('[MarketWatch] Delete synced locally:', e.message));

                if (window.terminalShell) {
                    window.terminalShell.showToast(`Removed ${item.trading_symbol}`);
                }
            }
        }

        /* ==========================================================================
           3. Search Command Palette Modal (Ctrl+K or /)
           ========================================================================== */
        bindSearchModal() {
            const trigger = document.getElementById('mw-search-trigger');
            const modal = document.getElementById('scrip-search-modal');
            const input = document.getElementById('scrip-search-input');
            const segPills = document.querySelectorAll('.seg-pill');

            if (trigger) {
                trigger.addEventListener('click', () => this.openSearchModal());
            }

            if (input) {
                input.addEventListener('input', (e) => {
                    const query = e.target.value.trim();
                    clearTimeout(this.searchDebounceTimer);
                    this.searchDebounceTimer = setTimeout(() => {
                        this.executeSearch(query);
                    }, 150);
                });
            }

            segPills.forEach(pill => {
                pill.addEventListener('click', () => {
                    segPills.forEach(p => p.classList.remove('active'));
                    pill.classList.add('active');
                    if (input && input.value.trim().length >= 2) {
                        this.executeSearch(input.value.trim());
                    }
                });
            });

            // Quick suggest tags
            document.querySelectorAll('.suggest-tag').forEach(tag => {
                tag.addEventListener('click', () => {
                    const q = tag.getAttribute('data-query');
                    if (input) {
                        input.value = q;
                        this.executeSearch(q);
                    }
                });
            });
        }

        openSearchModal() {
            const modal = document.getElementById('scrip-search-modal');
            const input = document.getElementById('scrip-search-input');
            const targetWlLabel = document.getElementById('search-target-wl');
            const currentWl = this.watchlists[this.activeWatchlistIndex] || { name: 'Watchlist 1' };

            if (targetWlLabel) targetWlLabel.textContent = currentWl.name;
            if (modal) modal.classList.remove('hidden');
            if (input) {
                input.value = '';
                input.focus();
            }
        }

        closeSearchModal() {
            const modal = document.getElementById('scrip-search-modal');
            if (modal) modal.classList.add('hidden');
        }

        async executeSearch(query) {
            const container = document.getElementById('search-results-container');
            if (!container) return;

            if (!query || query.length < 2) {
                container.innerHTML = `
                    <div class="search-initial-hint">
                        <p>Type at least 2 characters to search instruments.</p>
                    </div>
                `;
                return;
            }

            const activePill = document.querySelector('.seg-pill.active');
            const seg = activePill ? activePill.getAttribute('data-segment') : '';
            const segParam = seg ? `&segment=${encodeURIComponent(seg)}` : '';

            container.innerHTML = `<div class="search-initial-hint"><p>Searching '${query}'...</p></div>`;

            try {
                const resp = await fetch(`/api/market-watch/search?q=${encodeURIComponent(query)}${segParam}`);
                if (resp.ok) {
                    const data = await resp.json();
                    const results = (data.data && data.data.instruments) ? data.data.instruments : [];
                    this.renderSearchResults(results, query);
                } else {
                    this.renderMockSearchResults(query, seg);
                }
            } catch (e) {
                this.renderMockSearchResults(query, seg);
            }
        }

        renderSearchResults(results, query) {
            const container = document.getElementById('search-results-container');
            if (!container) return;

            if (!results || results.length === 0) {
                container.innerHTML = `<div class="search-initial-hint"><p>No matching instruments found for '${query}'.</p></div>`;
                return;
            }

            container.innerHTML = '';
            results.slice(0, 30).forEach((item, index) => {
                const row = document.createElement('div');
                row.className = 'search-result-item';
                row.setAttribute('data-index', index);

                row.innerHTML = `
                    <div class="search-item-info">
                        <div class="search-item-title-row">
                            <span class="search-item-symbol">${item.trading_symbol || item.symbol}</span>
                            <span class="scrip-seg-tag">${(item.exchange_segment || 'nse_cm').toUpperCase()}</span>
                        </div>
                        <span class="search-item-desc">${item.display_name || item.name || item.trading_symbol}</span>
                    </div>
                    <div class="search-item-actions">
                        <button class="btn btn-xs btn-primary search-add-btn">+ Add</button>
                        <button class="btn btn-xs btn-ghost search-buy-btn" style="color: var(--accent-blue);">B</button>
                        <button class="btn btn-xs btn-ghost search-sell-btn" style="color: var(--accent-orange);">S</button>
                    </div>
                `;

                const addBtn = row.querySelector('.search-add-btn');
                const buyBtn = row.querySelector('.search-buy-btn');
                const sellBtn = row.querySelector('.search-sell-btn');

                addBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    this.addScripToActiveWatchlist(item);
                });

                buyBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    this.closeSearchModal();
                    this.launchOrderTicket(item, 'BUY');
                });

                sellBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    this.closeSearchModal();
                    this.launchOrderTicket(item, 'SELL');
                });

                row.addEventListener('click', () => {
                    this.addScripToActiveWatchlist(item);
                });

                container.appendChild(row);
            });
        }

        renderMockSearchResults(query, seg) {
            const mockCatalog = [
                { instrument_token: "26000", exchange_segment: "nse_cm", trading_symbol: "NIFTY 50", display_name: "Nifty 50 Index" },
                { instrument_token: "26009", exchange_segment: "nse_cm", trading_symbol: "BANKNIFTY", display_name: "Nifty Bank Index" },
                { instrument_token: "2885", exchange_segment: "nse_cm", trading_symbol: "RELIANCE", display_name: "Reliance Industries Ltd" },
                { instrument_token: "1333", exchange_segment: "nse_cm", trading_symbol: "HDFCBANK", display_name: "HDFC Bank Ltd" },
                { instrument_token: "11536", exchange_segment: "nse_cm", trading_symbol: "TCS", display_name: "Tata Consultancy Services" },
                { instrument_token: "1594", exchange_segment: "nse_cm", trading_symbol: "INFY", display_name: "Infosys Ltd" },
                { instrument_token: "45210", exchange_segment: "nse_fo", trading_symbol: "NIFTY28NOV24500CE", display_name: "Nifty 28Nov 24500 Call" },
                { instrument_token: "45211", exchange_segment: "nse_fo", trading_symbol: "NIFTY28NOV24500PE", display_name: "Nifty 28Nov 24500 Put" },
                { instrument_token: "45220", exchange_segment: "nse_fo", trading_symbol: "NIFTY28NOV24600CE", display_name: "Nifty 28Nov 24600 Call" },
                { instrument_token: "45221", exchange_segment: "nse_fo", trading_symbol: "NIFTY28NOV24600PE", display_name: "Nifty 28Nov 24600 Put" }
            ];

            const qUpper = query.toUpperCase();
            const filtered = mockCatalog.filter(m => {
                const matchSeg = seg ? m.exchange_segment.toLowerCase() === seg.toLowerCase() : true;
                const matchText = m.trading_symbol.includes(qUpper) || m.display_name.toUpperCase().includes(qUpper);
                return matchSeg && matchText;
            });

            this.renderSearchResults(filtered, query);
        }

        async addScripToActiveWatchlist(scrip) {
            const currentWl = this.watchlists[this.activeWatchlistIndex];
            if (!currentWl) return;

            currentWl.items = currentWl.items || [];
            if (currentWl.items.length >= 50) {
                alert('Watchlist Quota Exceeded (Max 50 items allowed).');
                return;
            }

            // Check duplicate
            const exists = currentWl.items.some(it => it.instrument_token === scrip.instrument_token);
            if (exists) {
                if (window.terminalShell) window.terminalShell.showToast(`${scrip.trading_symbol} already in watchlist.`);
                this.closeSearchModal();
                return;
            }

            const newItem = {
                id: Date.now(),
                instrument_token: scrip.instrument_token || "1001",
                exchange_segment: scrip.exchange_segment || "nse_cm",
                trading_symbol: scrip.trading_symbol || scrip.symbol,
                display_name: scrip.display_name || scrip.trading_symbol,
                quote: { ltp: 150.0, change: 1.5, percent_change: 1.01 }
            };

            currentWl.items.push(newItem);
            this.renderActiveWatchlist();
            this.closeSearchModal();

            // API Call
            fetch(`/api/market-watch/watchlists/${currentWl.id}/items`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    instrument_token: newItem.instrument_token,
                    exchange_segment: newItem.exchange_segment,
                    trading_symbol: newItem.trading_symbol,
                    display_name: newItem.display_name
                })
            }).catch(e => console.debug('[MarketWatch] Add synced locally:', e.message));

            if (window.terminalShell) {
                window.terminalShell.showToast(`Added ${newItem.trading_symbol} to ${currentWl.name}`);
            }
        }

        /* ==========================================================================
           4. 5-Level Market Depth DOM Popover
           ========================================================================== */
        bindDepthModal() {
            const closeBtn = document.getElementById('close-depth-btn');
            const buyBtn = document.getElementById('depth-buy-btn');
            const sellBtn = document.getElementById('depth-sell-btn');

            if (closeBtn) {
                closeBtn.addEventListener('click', () => this.closeMarketDepth());
            }

            if (buyBtn) {
                buyBtn.addEventListener('click', () => {
                    const item = this.currentDepthItem;
                    this.closeMarketDepth();
                    if (item) this.launchOrderTicket(item, 'BUY');
                });
            }

            if (sellBtn) {
                sellBtn.addEventListener('click', () => {
                    const item = this.currentDepthItem;
                    this.closeMarketDepth();
                    if (item) this.launchOrderTicket(item, 'SELL');
                });
            }
        }

        openMarketDepth(item) {
            this.currentDepthItem = item;
            const modal = document.getElementById('market-depth-modal');
            const symEl = document.getElementById('depth-symbol');
            const segEl = document.getElementById('depth-segment');
            const ltpEl = document.getElementById('depth-ltp');
            const chgEl = document.getElementById('depth-chg');

            if (symEl) symEl.textContent = item.trading_symbol;
            if (segEl) segEl.textContent = (item.exchange_segment || 'NSE').toUpperCase();
            
            const q = item.quote || { ltp: 142.50, change: 12.40, percent_change: 9.53 };
            if (ltpEl) ltpEl.textContent = (q.ltp || 0).toFixed(2);
            if (chgEl) chgEl.textContent = `${(q.change || 0) >= 0 ? '+' : ''}${(q.change || 0).toFixed(2)} (${(q.percent_change || 0).toFixed(2)}%)`;

            if (modal) modal.classList.remove('hidden');
        }

        closeMarketDepth() {
            const modal = document.getElementById('market-depth-modal');
            if (modal) modal.classList.add('hidden');
        }

        /* ==========================================================================
           5. Option Chain Bridge
           ========================================================================== */
        openOptionChain(item) {
            if (window.terminalShell) {
                window.terminalShell.switchTab('option_chain');
                window.terminalShell.showToast(`Switched to Option Chain for ${item.trading_symbol}`);
            }
        }

        /* ==========================================================================
           6. Order Ticket Launch Bridge
           ========================================================================== */
        launchOrderTicket(item, side = 'BUY') {
            if (window.orderTicketController) {
                window.orderTicketController.openTicket(item, side);
            }
        }

        /* ==========================================================================
           7. Keyboard Navigation Map
           ========================================================================== */
        bindKeyboardShortcuts() {
            window.addEventListener('keydown', (e) => {
                if (['INPUT', 'TEXTAREA'].includes(document.activeElement.tagName)) {
                    if (e.key === 'Escape') {
                        this.closeSearchModal();
                        this.closeMarketDepth();
                    }
                    return;
                }

                // Ctrl + K or / : Open search
                if (e.key === '/' || (e.ctrlKey && e.key === 'k')) {
                    e.preventDefault();
                    this.openSearchModal();
                    return;
                }

                // Arrow navigation on scrips
                const rows = document.querySelectorAll('.scrip-row');
                if (rows.length > 0) {
                    if (e.key === 'ArrowDown') {
                        e.preventDefault();
                        this.focusedRowIndex = (this.focusedRowIndex + 1) % rows.length;
                        rows.forEach((r, idx) => {
                            if (idx === this.focusedRowIndex) {
                                r.classList.add('focused');
                                r.scrollIntoView({ block: 'nearest' });
                            } else {
                                r.classList.remove('focused');
                            }
                        });
                        return;
                    }

                    if (e.key === 'ArrowUp') {
                        e.preventDefault();
                        this.focusedRowIndex = (this.focusedRowIndex - 1 + rows.length) % rows.length;
                        rows.forEach((r, idx) => {
                            if (idx === this.focusedRowIndex) {
                                r.classList.add('focused');
                                r.scrollIntoView({ block: 'nearest' });
                            } else {
                                r.classList.remove('focused');
                            }
                        });
                        return;
                    }

                    // B key on focused row
                    if ((e.key === 'b' || e.key === 'B') && this.focusedRowIndex >= 0) {
                        e.preventDefault();
                        const currentWl = this.watchlists[this.activeWatchlistIndex];
                        if (currentWl && currentWl.items[this.focusedRowIndex]) {
                            this.launchOrderTicket(currentWl.items[this.focusedRowIndex], 'BUY');
                        }
                        return;
                    }

                    // S key on focused row
                    if ((e.key === 's' || e.key === 'S') && this.focusedRowIndex >= 0) {
                        e.preventDefault();
                        const currentWl = this.watchlists[this.activeWatchlistIndex];
                        if (currentWl && currentWl.items[this.focusedRowIndex]) {
                            this.launchOrderTicket(currentWl.items[this.focusedRowIndex], 'SELL');
                        }
                        return;
                    }

                    // D key on focused row (Depth)
                    if ((e.key === 'd' || e.key === 'D') && this.focusedRowIndex >= 0) {
                        e.preventDefault();
                        const currentWl = this.watchlists[this.activeWatchlistIndex];
                        if (currentWl && currentWl.items[this.focusedRowIndex]) {
                            this.openMarketDepth(currentWl.items[this.focusedRowIndex]);
                        }
                        return;
                    }

                    // O key on focused row (Option Chain)
                    if ((e.key === 'o' || e.key === 'O') && this.focusedRowIndex >= 0) {
                        e.preventDefault();
                        const currentWl = this.watchlists[this.activeWatchlistIndex];
                        if (currentWl && currentWl.items[this.focusedRowIndex]) {
                            this.openOptionChain(currentWl.items[this.focusedRowIndex]);
                        }
                        return;
                    }
                }
            });
        }
    }

    // Export singleton instance
    window.marketWatchController = new MarketWatchController();
})(window, document);
