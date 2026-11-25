/**
 * Kotak Neo Personal Trading Terminal - Phase 11D
 * Option Chain Workbench Controller: Symmetrical Matrix, In-Cell OI, PCR, Presets & Basket Handoff
 */

(function (window, document) {
    'use strict';

    class OptionChainController {
        constructor() {
            this.symbol = 'NIFTY';
            this.expiry = null;
            this.preset = 'ATM_10';
            this.spotPrice = 24500.0;
            this.strikes = [];
            this.expiries = [];
            this.underlyings = [];
            this.favourites = [];
            this.pcrData = null;
            this.pollTimer = null;

            this.init();
        }

        init() {
            this.bindControls();
            this.bindStrategyShortcuts();
            this.loadUnderlyings();
            this.startPolling();

            console.log('[OptionChainController] Phase 11D Initialized.');
        }

        startPolling() {
            if (this.pollTimer) {
                clearInterval(this.pollTimer);
            }
            // Auto-refresh option chain touchlines every 1.5 seconds when view is visible
            this.pollTimer = setInterval(() => {
                const view = document.getElementById('view-option-chain');
                if (view && view.classList.contains('active')) {
                    const searchInput = document.getElementById('oc-underlying-search');
                    const dropdown = document.getElementById('oc-underlying-dropdown');
                    if (document.activeElement === searchInput) return;
                    if (dropdown && !dropdown.classList.contains('hidden')) return;

                    this.fetchMatrix(true);
                }
            }, 1500);
        }

        stopPolling() {
            if (this.pollTimer) {
                clearInterval(this.pollTimer);
                this.pollTimer = null;
            }
        }

        bindControls() {
            const underlyingSel = document.getElementById('oc-underlying-select');
            const searchInput = document.getElementById('oc-underlying-search');
            const dropdown = document.getElementById('oc-underlying-dropdown');
            const expirySel = document.getElementById('oc-expiry-select');
            const presetSel = document.getElementById('oc-preset-select');
            const refreshBtn = document.getElementById('oc-refresh-btn');
            const favBtn = document.getElementById('oc-fav-btn');
            const openBasketBtn = document.getElementById('oc-open-basket-btn');

            // 1. Index Quick Chips (NIFTY, BANKNIFTY, SENSEX)
            document.querySelectorAll('.oc-index-chip').forEach(chip => {
                chip.addEventListener('click', (e) => {
                    const sym = e.currentTarget.getAttribute('data-symbol');
                    if (sym) this.selectUnderlying(sym);
                });
            });

            // 2. Searchable Combobox Controls
            if (searchInput) {
                searchInput.addEventListener('focus', () => {
                    this.openSearchDropdown();
                });

                searchInput.addEventListener('click', () => {
                    this.openSearchDropdown();
                });

                let searchTimer = null;
                searchInput.addEventListener('input', (e) => {
                    clearTimeout(searchTimer);
                    searchTimer = setTimeout(() => {
                        this.searchUnderlyings(e.target.value);
                    }, 200);
                });

                searchInput.addEventListener('keydown', (e) => {
                    if (e.key === 'Escape') {
                        this.closeSearchDropdown();
                    } else if (e.key === 'Enter') {
                        e.preventDefault();
                        const firstItem = dropdown ? dropdown.querySelector('.oc-dropdown-item') : null;
                        if (firstItem) {
                            const sym = firstItem.getAttribute('data-symbol');
                            if (sym) this.selectUnderlying(sym);
                        } else if (searchInput.value.trim()) {
                            let typed = searchInput.value.trim().split(' ')[0].split('(')[0].toUpperCase();
                            this.selectUnderlying(typed);
                        }
                    }
                });
            }

            // Close dropdown when clicking outside
            document.addEventListener('click', (e) => {
                if (!e.target.closest('.oc-combobox-wrapper')) {
                    this.closeSearchDropdown();
                }
            });

            if (underlyingSel) {
                underlyingSel.addEventListener('change', (e) => {
                    this.selectUnderlying(e.target.value);
                });
            }

            if (expirySel) {
                expirySel.addEventListener('change', (e) => {
                    this.expiry = e.target.value;
                    this.fetchMatrix();
                });
            }

            if (presetSel) {
                presetSel.addEventListener('change', (e) => {
                    this.preset = e.target.value;
                    this.fetchMatrix();
                });
            }

            if (refreshBtn) {
                refreshBtn.addEventListener('click', () => {
                    this.fetchMatrix();
                    if (window.terminalShell) window.terminalShell.showToast(`Refreshed ${this.symbol} Option Chain.`);
                });
            }

            if (favBtn) {
                favBtn.addEventListener('click', () => this.toggleFavourite());
            }

            if (openBasketBtn) {
                openBasketBtn.addEventListener('click', () => {
                    if (window.basketBuilderController) {
                        window.basketBuilderController.toggleDrawer();
                    }
                });
            }
        }

        openSearchDropdown() {
            const dropdown = document.getElementById('oc-underlying-dropdown');
            if (!dropdown) return;
            dropdown.classList.remove('hidden');
            const searchInput = document.getElementById('oc-underlying-search');
            if (searchInput) {
                searchInput.select();
            }
            this.searchUnderlyings('');
        }

        closeSearchDropdown() {
            const dropdown = document.getElementById('oc-underlying-dropdown');
            if (dropdown) dropdown.classList.add('hidden');
        }

        async searchUnderlyings(query = '') {
            const dropdown = document.getElementById('oc-underlying-dropdown');
            if (!dropdown) return;

            let cleanQuery = (query || '').trim();
            if (cleanQuery.includes('(')) {
                cleanQuery = cleanQuery.split('(')[0].trim();
            }

            try {
                const res = await fetch(`/api/option-chain/underlyings?q=${encodeURIComponent(cleanQuery)}`, { credentials: 'same-origin' });
                if (!res.ok) return;
                const json = await res.json();
                const list = (json.data && json.data.underlyings) || [];
                this.renderDropdownResults(list);
            } catch (err) {
                console.error('[OptionChain] Search error:', err);
            }
        }

        renderDropdownResults(results) {
            const dropdown = document.getElementById('oc-underlying-dropdown');
            if (!dropdown) return;

            if (!results || results.length === 0) {
                dropdown.innerHTML = `<div style="padding: 10px 14px; font-size: 0.8rem; color: var(--text-muted); text-align: center;">No matching F&O instruments</div>`;
                return;
            }

            let html = '';
            const coreSymbols = ['NIFTY', 'BANKNIFTY', 'SENSEX'];
            const coreItems = results.filter(r => coreSymbols.includes(r.symbol));
            const favItems = results.filter(r => r.is_favourite && !coreSymbols.includes(r.symbol));
            const stockItems = results.filter(r => !coreSymbols.includes(r.symbol) && !r.is_favourite);

            const renderItem = (u) => `
                <div class="oc-dropdown-item" data-symbol="${u.symbol}">
                    <div style="display:flex; align-items:center;">
                        <span class="item-sym">${u.is_favourite ? '★ ' : ''}${u.symbol}</span>
                        <span class="item-desc">${u.display_name || ''}</span>
                    </div>
                    <span class="item-lot">${u.is_index ? 'Index' : 'Lot: ' + (u.lot_size || 1)}</span>
                </div>
            `;

            if (coreItems.length > 0) {
                html += `<div class="oc-dropdown-group-header">Core Benchmark Indices</div>`;
                coreItems.forEach(u => { html += renderItem(u); });
            }

            if (favItems.length > 0) {
                html += `<div class="oc-dropdown-group-header">⭐ Favourite Underlyings</div>`;
                favItems.forEach(u => { html += renderItem(u); });
            }

            if (stockItems.length > 0) {
                html += `<div class="oc-dropdown-group-header">F&O Equities & Underlyings (${results.length})</div>`;
                stockItems.forEach(u => { html += renderItem(u); });
            }

            dropdown.innerHTML = html;

            dropdown.querySelectorAll('.oc-dropdown-item').forEach(item => {
                item.addEventListener('click', (e) => {
                    const sym = e.currentTarget.getAttribute('data-symbol');
                    if (sym) {
                        this.selectUnderlying(sym);
                        this.closeSearchDropdown();
                    }
                });
            });
        }

        selectUnderlying(symbol) {
            if (!symbol) return;
            const sym = symbol.trim().toUpperCase();
            this.symbol = sym;

            // 1. Update Core Index Chips
            document.querySelectorAll('.oc-index-chip').forEach(chip => {
                chip.classList.toggle('active', chip.getAttribute('data-symbol') === sym);
            });

            // 2. Update Search Input Display
            const searchInput = document.getElementById('oc-underlying-search');
            if (searchInput) {
                const match = this.underlyings.find(u => (u.symbol || u) === sym);
                searchInput.value = match ? `${match.symbol} (${match.display_name || match.symbol})` : sym;
            }

            // 3. Keep Hidden Select Synchronized
            const sel = document.getElementById('oc-underlying-select');
            if (sel) {
                let opt = Array.from(sel.options).find(o => o.value === sym);
                if (!opt) {
                    opt = document.createElement('option');
                    opt.value = sym;
                    opt.textContent = sym;
                    sel.appendChild(opt);
                }
                sel.value = sym;
            }

            this.closeSearchDropdown();
            this.loadExpiries();
        }

        bindStrategyShortcuts() {
            const buttons = document.querySelectorAll('[data-oc-strat]');
            buttons.forEach(btn => {
                btn.addEventListener('click', (e) => {
                    const strat = e.currentTarget.getAttribute('data-oc-strat');
                    this.launchQuickStrategy(strat);
                });
            });
        }

        /* ==========================================================================
           1. Underlyings & Expiries Data Fetching
           ========================================================================== */
        async loadUnderlyings() {
            try {
                const res = await fetch('/api/option-chain/underlyings', { credentials: 'same-origin' });
                if (!res.ok) return;
                const json = await res.json();
                this.underlyings = (json.data && json.data.underlyings) || [];
                this.renderUnderlyings();
                this.loadExpiries();
            } catch (err) {
                console.error('[OptionChain] Load underlyings error:', err);
                this.loadExpiries();
            }
        }

        renderUnderlyings() {
            const sel = document.getElementById('oc-underlying-select');
            const searchInput = document.getElementById('oc-underlying-search');
            if (!sel || this.underlyings.length === 0) return;

            sel.innerHTML = '';
            this.underlyings.forEach(u => {
                const opt = document.createElement('option');
                opt.value = u.symbol || u;
                opt.textContent = `${u.display_name || u.symbol || u} ${u.spot_price ? '(' + u.spot_price.toFixed(2) + ')' : ''}`;
                if (u.is_favourite) opt.textContent = `★ ${opt.textContent}`;
                if ((u.symbol || u) === this.symbol) opt.selected = true;
                sel.appendChild(opt);
            });

            if (searchInput && (!searchInput.value || searchInput.value.includes('NIFTY'))) {
                const current = this.underlyings.find(u => (u.symbol || u) === this.symbol);
                if (current) {
                    searchInput.value = `${current.symbol} (${current.display_name || current.symbol})`;
                }
            }
        }

        async loadExpiries() {
            try {
                const res = await fetch(`/api/option-chain/expiries?symbol=${this.symbol}`, { credentials: 'same-origin' });
                if (!res.ok) return;
                const json = await res.json();
                this.expiries = (json.data && json.data.expiries) || [];

                const sel = document.getElementById('oc-expiry-select');
                if (!sel) return;
                sel.innerHTML = '';

                if (this.expiries.length === 0) {
                    const opt = document.createElement('option');
                    opt.value = '';
                    opt.textContent = 'No active expiries';
                    sel.appendChild(opt);
                    return;
                }

                this.expiries.forEach((exp, idx) => {
                    const opt = document.createElement('option');
                    opt.value = exp.expiry_date || exp;
                    opt.textContent = `${exp.display_label || exp.expiry_date || exp} ${exp.expiry_type ? '(' + exp.expiry_type + ')' : ''}`;
                    if (idx === 0) opt.selected = true;
                    sel.appendChild(opt);
                });

                this.expiry = sel.value;
                this.fetchMatrix();
            } catch (err) {
                console.error('[OptionChain] Load expiries error:', err);
            }
        }

        async toggleFavourite() {
            const star = document.getElementById('oc-fav-star');
            const isCurrentlyFav = star && star.textContent === '★';
            const nextFav = !isCurrentlyFav;

            try {
                const res = await fetch('/api/option-chain/favourites', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'same-origin',
                    body: JSON.stringify({ symbol: this.symbol, is_favourite: nextFav })
                });
                if (res.ok) {
                    if (star) star.textContent = nextFav ? '★' : '☆';
                    if (window.terminalShell) {
                        window.terminalShell.showToast(`${this.symbol} ${nextFav ? 'pinned to' : 'removed from'} favourites.`);
                    }
                }
            } catch (e) {
                console.error('[OptionChain] Toggle favourite error:', e);
            }
        }

        /* ==========================================================================
           2. Symmetrical Strike Matrix Fetch & Rendering
           ========================================================================== */
        async fetchMatrix(isSilent = false) {
            if (!this.expiry) return;

            try {
                const url = `/api/option-chain?symbol=${this.symbol}&expiry=${this.expiry}&preset=${this.preset}`;
                const res = await fetch(url, { credentials: 'same-origin' });
                if (!res.ok) return;
                const json = await res.json();
                const data = json.data || {};

                this.spotPrice = data.spot_price || this.spotPrice;
                this.atmStrike = data.atm_strike !== undefined ? data.atm_strike : null;
                this.strikes = data.strikes || [];
                this.pcrData = {
                    pcr_oi: data.pcr_oi,
                    pcr_volume: data.pcr_volume,
                    total_call_oi: data.total_call_oi,
                    total_put_oi: data.total_put_oi,
                    max_pain_strike: data.max_pain_strike,
                    max_call_oi_strike: data.max_call_oi_strike,
                    max_put_oi_strike: data.max_put_oi_strike
                };

                this.renderHeaderAndSentiment(data);

                if (isSilent && document.getElementById('oc-matrix-tbody') && document.getElementById('oc-matrix-tbody').children.length > 0) {
                    this.updateMatrixValuesInPlace();
                } else {
                    this.renderMatrixTable();
                }
            } catch (err) {
                console.error('[OptionChain] Fetch matrix error:', err);
            }
        }

        renderHeaderAndSentiment(data) {
            const spotEl = document.getElementById('oc-spot-price');
            const chgEl = document.getElementById('oc-spot-change');
            if (spotEl) spotEl.textContent = this.spotPrice.toLocaleString('en-IN', { minimumFractionDigits: 2 });
            if (chgEl) {
                const chg = data.spot_change || 0;
                const chgPct = data.spot_change_pct || 0;
                chgEl.textContent = `${chg >= 0 ? '+' : ''}${chg.toFixed(2)} (${chgPct.toFixed(2)}%)`;
                chgEl.className = `font-numeric ${chg >= 0 ? 'text-success' : 'text-danger'}`;
            }

            // PCR & Max Pain
            const callOiEl = document.getElementById('oc-total-call-oi');
            const putOiEl = document.getElementById('oc-total-put-oi');
            const pcrOiEl = document.getElementById('oc-pcr-oi');
            const pcrSentEl = document.getElementById('oc-pcr-sentiment');
            const pcrVolEl = document.getElementById('oc-pcr-vol');
            const maxPainEl = document.getElementById('oc-max-pain');
            const supEl = document.getElementById('oc-key-support');
            const resEl = document.getElementById('oc-key-resistance');

            if (callOiEl) callOiEl.textContent = (data.total_call_oi || 0).toLocaleString('en-IN');
            if (putOiEl) putOiEl.textContent = (data.total_put_oi || 0).toLocaleString('en-IN');

            const pcrOi = data.pcr_oi || 1.0;
            if (pcrOiEl) pcrOiEl.textContent = pcrOi.toFixed(2);
            if (pcrSentEl) {
                if (pcrOi > 1.20) {
                    pcrSentEl.textContent = 'BULLISH';
                    pcrSentEl.className = 'badge badge-success';
                } else if (pcrOi < 0.80) {
                    pcrSentEl.textContent = 'BEARISH';
                    pcrSentEl.className = 'badge badge-danger';
                } else {
                    pcrSentEl.textContent = 'NEUTRAL';
                    pcrSentEl.className = 'badge badge-neutral';
                }
            }

            if (pcrVolEl) pcrVolEl.textContent = (data.pcr_volume || 1.0).toFixed(2);
            if (maxPainEl) maxPainEl.textContent = data.max_pain_strike ? `₹${data.max_pain_strike}` : '—';
            if (supEl) supEl.textContent = data.max_put_oi_strike ? `S: ${data.max_put_oi_strike}` : 'S: —';
            if (resEl) resEl.textContent = data.max_call_oi_strike ? `R: ${data.max_call_oi_strike}` : 'R: —';
        }

        updateMatrixValuesInPlace() {
            const tbody = document.getElementById('oc-matrix-tbody');
            if (!tbody) return;
            const existingRows = tbody.querySelectorAll('tr[data-strike]');
            if (existingRows.length !== this.strikes.length) {
                this.renderMatrixTable();
                return;
            }

            let maxOI = 1;
            this.strikes.forEach(s => {
                const c = s.call || s.call_quote;
                const p = s.put || s.put_quote;
                if (c && c.open_interest > maxOI) maxOI = c.open_interest;
                if (p && p.open_interest > maxOI) maxOI = p.open_interest;
            });

            this.strikes.forEach((row, idx) => {
                const k = row.strike_price;
                const tr = existingRows[idx];
                if (!tr || tr.getAttribute('data-strike') !== String(k)) {
                    this.renderMatrixTable();
                    return;
                }

                const isAtm = row.is_atm === true || (this.atmStrike !== null && Math.abs(k - this.atmStrike) < 0.01);
                if (isAtm && !tr.classList.contains('strike-atm')) {
                    tr.classList.add('strike-atm');
                } else if (!isAtm && tr.classList.contains('strike-atm')) {
                    tr.classList.remove('strike-atm');
                }

                const c = row.call || row.call_quote || {};
                const p = row.put || row.put_quote || {};

                const cLtp = Number(c.ltp !== undefined ? c.ltp : (c.last_price || 0));
                const pLtp = Number(p.ltp !== undefined ? p.ltp : (p.last_price || 0));
                const cBid = Number(c.bid_price !== undefined ? c.bid_price : (c.bid !== undefined ? c.bid : (cLtp > 0 ? Math.max(0.05, cLtp - 0.20) : 0)));
                const cAsk = Number(c.ask_price !== undefined ? c.ask_price : (c.ask !== undefined ? c.ask : (cLtp > 0 ? cLtp + 0.20 : 0)));
                const pBid = Number(p.bid_price !== undefined ? p.bid_price : (p.bid !== undefined ? p.bid : (pLtp > 0 ? Math.max(0.05, pLtp - 0.20) : 0)));
                const pAsk = Number(p.ask_price !== undefined ? p.ask_price : (p.ask !== undefined ? p.ask : (pLtp > 0 ? pLtp + 0.20 : 0)));

                const cOi = c.open_interest || 0;
                const pOi = p.open_interest || 0;
                const cChgOi = c.change_in_oi !== undefined ? c.change_in_oi : (c.change_oi || 0);
                const pChgOi = p.change_in_oi !== undefined ? p.change_in_oi : (p.change_oi || 0);
                const cVol = c.volume || 0;
                const pVol = p.volume || 0;

                const cOiPct = Math.min(100, Math.max(0, (cOi / maxOI) * 100));
                const pOiPct = Math.min(100, Math.max(0, (pOi / maxOI) * 100));

                // 1. Call LTP with flash
                const cLtpEl = tr.querySelector('.call-ltp-cell');
                if (cLtpEl) {
                    const prevLtp = parseFloat(cLtpEl.textContent.replace(/[₹,]/g, '')) || 0;
                    const newTxt = `₹${cLtp > 0 ? cLtp.toFixed(2) : '—'}`;
                    if (cLtpEl.textContent !== newTxt) {
                        cLtpEl.textContent = newTxt;
                        if (prevLtp > 0 && cLtp > prevLtp) {
                            cLtpEl.classList.add('flash-green');
                            setTimeout(() => cLtpEl.classList.remove('flash-green'), 400);
                        } else if (prevLtp > 0 && cLtp < prevLtp) {
                            cLtpEl.classList.add('flash-red');
                            setTimeout(() => cLtpEl.classList.remove('flash-red'), 400);
                        }
                    }
                }

                // 2. Put LTP with flash
                const pLtpEl = tr.querySelector('.put-ltp-cell');
                if (pLtpEl) {
                    const prevLtp = parseFloat(pLtpEl.textContent.replace(/[₹,]/g, '')) || 0;
                    const newTxt = `₹${pLtp > 0 ? pLtp.toFixed(2) : '—'}`;
                    if (pLtpEl.textContent !== newTxt) {
                        pLtpEl.textContent = newTxt;
                        if (prevLtp > 0 && pLtp > prevLtp) {
                            pLtpEl.classList.add('flash-green');
                            setTimeout(() => pLtpEl.classList.remove('flash-green'), 400);
                        } else if (prevLtp > 0 && pLtp < prevLtp) {
                            pLtpEl.classList.add('flash-red');
                            setTimeout(() => pLtpEl.classList.remove('flash-red'), 400);
                        }
                    }
                }

                // 3. Bid & Ask
                const cBidEl = tr.querySelector('.call-bid-cell');
                if (cBidEl) cBidEl.textContent = `₹${cBid > 0 ? cBid.toFixed(2) : '—'}`;
                const cAskEl = tr.querySelector('.call-ask-cell');
                if (cAskEl) cAskEl.textContent = `₹${cAsk > 0 ? cAsk.toFixed(2) : '—'}`;

                const pBidEl = tr.querySelector('.put-bid-cell');
                if (pBidEl) pBidEl.textContent = `₹${pBid > 0 ? pBid.toFixed(2) : '—'}`;
                const pAskEl = tr.querySelector('.put-ask-cell');
                if (pAskEl) pAskEl.textContent = `₹${pAsk > 0 ? pAsk.toFixed(2) : '—'}`;

                // 4. Volume & dOI
                const cVolEl = tr.querySelector('.call-vol-cell');
                if (cVolEl) cVolEl.textContent = cVol ? (cVol / 1000).toFixed(1) + 'k' : '—';
                const pVolEl = tr.querySelector('.put-vol-cell');
                if (pVolEl) pVolEl.textContent = pVol ? (pVol / 1000).toFixed(1) + 'k' : '—';

                const cChgEl = tr.querySelector('.call-choi-cell');
                if (cChgEl) cChgEl.textContent = cChgOi ? ((cChgOi >= 0 ? '+' : '') + cChgOi.toLocaleString('en-IN')) : '—';
                const pChgEl = tr.querySelector('.put-choi-cell');
                if (pChgEl) pChgEl.textContent = pChgOi ? ((pChgOi >= 0 ? '+' : '') + pChgOi.toLocaleString('en-IN')) : '—';

                // 5. Open Interest
                const cOiTxt = tr.querySelector('.call-oi-text');
                if (cOiTxt) cOiTxt.textContent = cOi ? cOi.toLocaleString('en-IN') : '—';
                const cOiBar = tr.querySelector('.oi-bar.call');
                if (cOiBar) cOiBar.style.width = `${cOiPct.toFixed(1)}%`;

                const pOiTxt = tr.querySelector('.put-oi-text');
                if (pOiTxt) pOiTxt.textContent = pOi ? pOi.toLocaleString('en-IN') : '—';
                const pOiBar = tr.querySelector('.oi-bar.put');
                if (pOiBar) pOiBar.style.width = `${pOiPct.toFixed(1)}%`;
            });
        }

        renderMatrixTable() {
            const tbody = document.getElementById('oc-matrix-tbody');
            const empty = document.getElementById('oc-empty-state');
            if (!tbody) return;

            tbody.innerHTML = '';

            if (this.strikes.length === 0) {
                if (empty) empty.classList.remove('hidden');
                return;
            }
            if (empty) empty.classList.add('hidden');

            // Find max OI across all strikes for horizontal visual bar scaling
            let maxOI = 1;
            this.strikes.forEach(s => {
                const c = s.call || s.call_quote;
                const p = s.put || s.put_quote;
                if (c && c.open_interest > maxOI) maxOI = c.open_interest;
                if (p && p.open_interest > maxOI) maxOI = p.open_interest;
            });

            this.strikes.forEach(row => {
                const k = row.strike_price;
                const isAtm = row.is_atm === true || (this.atmStrike !== null && Math.abs(k - this.atmStrike) < 0.01);
                const c = row.call || row.call_quote || {};
                const p = row.put || row.put_quote || {};

                const cLtp = c.ltp !== undefined ? c.ltp : (c.last_price || 0);
                const pLtp = p.ltp !== undefined ? p.ltp : (p.last_price || 0);
                const cBid = Number(c.bid_price !== undefined ? c.bid_price : (c.bid !== undefined ? c.bid : (cLtp > 0 ? Math.max(0.05, cLtp - 0.20) : 0)));
                const cAsk = Number(c.ask_price !== undefined ? c.ask_price : (c.ask !== undefined ? c.ask : (cLtp > 0 ? cLtp + 0.20 : 0)));
                const pBid = Number(p.bid_price !== undefined ? p.bid_price : (p.bid !== undefined ? p.bid : (pLtp > 0 ? Math.max(0.05, pLtp - 0.20) : 0)));
                const pAsk = Number(p.ask_price !== undefined ? p.ask_price : (p.ask !== undefined ? p.ask : (pLtp > 0 ? pLtp + 0.20 : 0)));
                const cOi = c.open_interest || 0;
                const pOi = p.open_interest || 0;
                const cChgOi = c.change_in_oi !== undefined ? c.change_in_oi : (c.change_oi || 0);
                const pChgOi = p.change_in_oi !== undefined ? p.change_in_oi : (p.change_oi || 0);
                const cVol = c.volume || 0;
                const pVol = p.volume || 0;

                const cOiPct = Math.min(100, Math.max(0, (cOi / maxOI) * 100));
                const pOiPct = Math.min(100, Math.max(0, (pOi / maxOI) * 100));

                const tr = document.createElement('tr');
                tr.setAttribute('data-strike', k);
                if (isAtm) tr.className = 'strike-atm';

                const isCallItm = k < this.spotPrice;
                const isPutItm = k > this.spotPrice;

                tr.innerHTML = `
                    <!-- Calls Section -->
                    <td class="text-right font-numeric oi-cell ${isCallItm ? 'itm-call' : ''}">
                        <div class="oi-bar call" style="width: ${cOiPct.toFixed(1)}%;"></div>
                        <span class="oi-text call-oi-text">${cOi ? cOi.toLocaleString('en-IN') : '—'}</span>
                        ${c.is_max_oi ? '<span class="badge-resistance" title="Key Resistance (Max OI)">R</span>' : ''}
                    </td>
                    <td class="text-right font-numeric call-choi-cell ${cChgOi >= 0 ? 'text-success' : 'text-danger'} ${isCallItm ? 'itm-call' : ''}">
                        ${cChgOi ? ((cChgOi >= 0 ? '+' : '') + cChgOi.toLocaleString('en-IN')) : '—'}
                    </td>
                    <td class="text-right font-numeric call-vol-cell ${isCallItm ? 'itm-call' : ''}">
                        ${cVol ? (cVol / 1000).toFixed(1) + 'k' : '—'}
                    </td>
                    <td class="text-right font-numeric bid-cell call-bid-cell ${isCallItm ? 'itm-call' : ''}" style="cursor: pointer;" data-action="click-call-bid" title="Sell Call @ Best Bid ₹${cBid.toFixed(2)}">
                        ₹${cBid > 0 ? cBid.toFixed(2) : '—'}
                    </td>
                    <td class="text-right font-numeric ask-cell call-ask-cell ${isCallItm ? 'itm-call' : ''}" style="cursor: pointer;" data-action="click-call-ask" title="Buy Call @ Best Ask ₹${cAsk.toFixed(2)}">
                        ₹${cAsk > 0 ? cAsk.toFixed(2) : '—'}
                    </td>
                    <td class="text-right font-numeric font-bold call-ltp-cell ${isCallItm ? 'itm-call' : ''}" style="cursor: pointer;" data-action="click-call-ltp" title="Click to Buy Call @ ₹${cLtp.toFixed(2)}">
                        ₹${cLtp > 0 ? cLtp.toFixed(2) : '—'}
                    </td>
                    <td class="text-center ${isCallItm ? 'itm-call' : ''}">
                        <div class="table-actions">
                            <button class="btn btn-xs btn-action-add" data-action="buy-call" title="Buy Call">B</button>
                            <button class="btn btn-xs btn-action-exit" data-action="sell-call" title="Sell Call">S</button>
                            <button class="btn btn-xs btn-action-reverse" data-action="basket-call" title="Add Call Leg to Basket">➕</button>
                        </div>
                    </td>

                    <!-- Strike Column (Center) -->
                    <td class="text-center font-numeric strike-cell">
                        ${isAtm ? '<span class="badge badge-warning" style="font-size:0.6rem; margin-right:3px;">ATM</span>' : ''}
                        ${k.toLocaleString('en-IN')}
                    </td>

                    <!-- Puts Section -->
                    <td class="text-center ${isPutItm ? 'itm-put' : ''}">
                        <div class="table-actions">
                            <button class="btn btn-xs btn-action-reverse" data-action="basket-put" title="Add Put Leg to Basket">➕</button>
                            <button class="btn btn-xs btn-action-add" data-action="buy-put" title="Buy Put">B</button>
                            <button class="btn btn-xs btn-action-exit" data-action="sell-put" title="Sell Put">S</button>
                        </div>
                    </td>
                    <td class="text-right font-numeric font-bold put-ltp-cell ${isPutItm ? 'itm-put' : ''}" style="cursor: pointer;" data-action="click-put-ltp" title="Click to Buy Put @ ₹${pLtp.toFixed(2)}">
                        ₹${pLtp > 0 ? pLtp.toFixed(2) : '—'}
                    </td>
                    <td class="text-right font-numeric bid-cell put-bid-cell ${isPutItm ? 'itm-put' : ''}" style="cursor: pointer;" data-action="click-put-bid" title="Sell Put @ Best Bid ₹${pBid.toFixed(2)}">
                        ₹${pBid > 0 ? pBid.toFixed(2) : '—'}
                    </td>
                    <td class="text-right font-numeric ask-cell put-ask-cell ${isPutItm ? 'itm-put' : ''}" style="cursor: pointer;" data-action="click-put-ask" title="Buy Put @ Best Ask ₹${pAsk.toFixed(2)}">
                        ₹${pAsk > 0 ? pAsk.toFixed(2) : '—'}
                    </td>
                    <td class="text-right font-numeric put-vol-cell ${isPutItm ? 'itm-put' : ''}">
                        ${pVol ? (pVol / 1000).toFixed(1) + 'k' : '—'}
                    </td>
                    <td class="text-right font-numeric put-choi-cell ${pChgOi >= 0 ? 'text-success' : 'text-danger'} ${isPutItm ? 'itm-put' : ''}">
                        ${pChgOi ? ((pChgOi >= 0 ? '+' : '') + pChgOi.toLocaleString('en-IN')) : '—'}
                    </td>
                    <td class="text-right font-numeric oi-cell ${isPutItm ? 'itm-put' : ''}">
                        <div class="oi-bar put" style="width: ${pOiPct.toFixed(1)}%;"></div>
                        <span class="oi-text put-oi-text">${pOi ? pOi.toLocaleString('en-IN') : '—'}</span>
                        ${p.is_max_oi ? '<span class="badge-support" title="Key Support (Max OI)">S</span>' : ''}
                    </td>

                    <!-- Watchlist Pin -->
                    <td class="text-center">
                        <button class="btn btn-xs btn-ghost" data-action="pin-strike" title="Pin to active Watchlist">📌</button>
                    </td>
                `;

                // Bind single-order action buttons
                const btnBuyCall = tr.querySelector('[data-action="buy-call"]');
                const btnSellCall = tr.querySelector('[data-action="sell-call"]');
                const btnBasketCall = tr.querySelector('[data-action="basket-call"]');
                const clickCallLtp = tr.querySelector('[data-action="click-call-ltp"]');
                const clickCallBid = tr.querySelector('[data-action="click-call-bid"]');
                const clickCallAsk = tr.querySelector('[data-action="click-call-ask"]');

                const btnBuyPut = tr.querySelector('[data-action="buy-put"]');
                const btnSellPut = tr.querySelector('[data-action="sell-put"]');
                const btnBasketPut = tr.querySelector('[data-action="basket-put"]');
                const clickPutLtp = tr.querySelector('[data-action="click-put-ltp"]');
                const clickPutBid = tr.querySelector('[data-action="click-put-bid"]');
                const clickPutAsk = tr.querySelector('[data-action="click-put-ask"]');
                const btnPin = tr.querySelector('[data-action="pin-strike"]');

                if (btnBuyCall) btnBuyCall.addEventListener('click', () => this.tradeContract(c, 'BUY'));
                if (btnSellCall) btnSellCall.addEventListener('click', () => this.tradeContract(c, 'SELL'));
                if (btnBasketCall) btnBasketCall.addEventListener('click', () => this.addContractToBasket(c, 'BUY'));
                if (clickCallLtp) clickCallLtp.addEventListener('click', () => this.tradeContract(c, 'BUY'));
                if (clickCallBid) clickCallBid.addEventListener('click', () => this.tradeContract(c, 'SELL'));
                if (clickCallAsk) clickCallAsk.addEventListener('click', () => this.tradeContract(c, 'BUY'));

                if (btnBuyPut) btnBuyPut.addEventListener('click', () => this.tradeContract(p, 'BUY'));
                if (btnSellPut) btnSellPut.addEventListener('click', () => this.tradeContract(p, 'SELL'));
                if (btnBasketPut) btnBasketPut.addEventListener('click', () => this.addContractToBasket(p, 'BUY'));
                if (clickPutLtp) clickPutLtp.addEventListener('click', () => this.tradeContract(p, 'BUY'));
                if (clickPutBid) clickPutBid.addEventListener('click', () => this.tradeContract(p, 'SELL'));
                if (clickPutAsk) clickPutAsk.addEventListener('click', () => this.tradeContract(p, 'BUY'));

                if (btnPin) btnPin.addEventListener('click', () => this.pinToWatchlist(c, p, k));

                tbody.appendChild(tr);
            });
        }

        /* ==========================================================================
           3. Action Handlers (Trade Ticket, Basket Addition, Watchlist Pin)
           ========================================================================== */
        tradeContract(contract, side = 'BUY') {
            if (!window.orderTicketController || !contract.trading_symbol) return;
            const ltp = contract.ltp !== undefined ? contract.ltp : (contract.last_price || 0);
            const lot = this.symbol.includes('BANKNIFTY') ? 15 : (this.symbol.includes('SENSEX') ? 10 : 65);
            window.orderTicketController.openTicket({
                trading_symbol: contract.trading_symbol,
                instrument_token: contract.instrument_token || '0',
                exchange_segment: contract.exchange_segment || 'nse_fo',
                ltp: ltp,
                last_price: ltp,
                lot_size: lot
            }, side, {
                product: 'NRML',
                price: ltp,
                quantity: lot,
                notice: `${side} ${contract.trading_symbol} @ ₹${ltp.toFixed(2)}`
            });
        }

        addContractToBasket(contract, side = 'BUY') {
            if (!window.basketBuilderController || !contract.trading_symbol) return;
            const ltp = contract.ltp !== undefined ? contract.ltp : (contract.last_price || 100.0);
            const lot = this.symbol.includes('BANKNIFTY') ? 15 : (this.symbol.includes('SENSEX') ? 10 : 65);
            const leg = {
                instrument_token: contract.instrument_token || '0',
                trading_symbol: contract.trading_symbol,
                exchange_segment: contract.exchange_segment || 'nse_fo',
                side: side,
                product_type: 'NRML',
                order_type: 'LIMIT',
                price: ltp,
                lot_size: lot,
                lots: 1,
                quantity: lot,
                execution_stage: side === 'BUY' ? 1 : 2
            };

            window.basketBuilderController.addLeg(leg);
            if (window.terminalShell) {
                window.terminalShell.showToast(`Added ${side} ${contract.trading_symbol} to Basket.`);
            }
        }

        async pinToWatchlist(callContract, putContract, strike) {
            const target = callContract.trading_symbol ? callContract : putContract;
            if (!target || !target.trading_symbol) return;

            try {
                // Pin to Watchlist 1 (ID: 1)
                const res = await fetch('/api/market-watch/watchlists/1/items', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'same-origin',
                    body: JSON.stringify({
                        instrument_token: target.instrument_token || '0',
                        exchange_segment: target.exchange_segment || 'nse_fo',
                        trading_symbol: target.trading_symbol,
                        display_name: target.trading_symbol
                    })
                });
                if (res.ok) {
                    if (window.terminalShell) {
                        window.terminalShell.showToast(`📌 Pinned ${target.trading_symbol} to Watchlist.`);
                    }
                    if (window.marketWatchController) {
                        window.marketWatchController.fetchWatchlistItems(1);
                    }
                }
            } catch (e) {
                console.error('[OptionChain] Pin to watchlist error:', e);
            }
        }

        launchQuickStrategy(stratType) {
            if (!window.basketBuilderController) return;
            window.basketBuilderController.instantiateTemplate(stratType, {
                underlying: this.symbol,
                spotPrice: this.spotPrice,
                expiry: this.expiry
            });
        }
    }

    // Export singleton instance
    window.optionChainController = new OptionChainController();
})(window, document);

