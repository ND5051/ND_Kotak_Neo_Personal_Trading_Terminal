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

            this.init();
        }

        init() {
            this.bindControls();
            this.bindStrategyShortcuts();
            this.loadUnderlyings();

            console.log('[OptionChainController] Phase 11D Initialized.');
        }

        bindControls() {
            const underlyingSel = document.getElementById('oc-underlying-select');
            const expirySel = document.getElementById('oc-expiry-select');
            const presetSel = document.getElementById('oc-preset-select');
            const refreshBtn = document.getElementById('oc-refresh-btn');
            const favBtn = document.getElementById('oc-fav-btn');
            const openBasketBtn = document.getElementById('oc-open-basket-btn');

            if (underlyingSel) {
                underlyingSel.addEventListener('change', (e) => {
                    this.symbol = e.target.value;
                    this.loadExpiries();
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
        async fetchMatrix() {
            if (!this.expiry) return;

            try {
                const url = `/api/option-chain?symbol=${this.symbol}&expiry=${this.expiry}&preset=${this.preset}`;
                const res = await fetch(url, { credentials: 'same-origin' });
                if (!res.ok) return;
                const json = await res.json();
                const data = json.data || {};

                this.spotPrice = data.spot_price || this.spotPrice;
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
                this.renderMatrixTable();
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
                if (s.call && s.call.open_interest > maxOI) maxOI = s.call.open_interest;
                if (s.put && s.put.open_interest > maxOI) maxOI = s.put.open_interest;
            });

            this.strikes.forEach(row => {
                const k = row.strike_price;
                const isAtm = row.is_atm || Math.abs(k - this.spotPrice) <= 25;
                const c = row.call || {};
                const p = row.put || {};

                const cOiPct = Math.min(100, Math.max(0, ((c.open_interest || 0) / maxOI) * 100));
                const pOiPct = Math.min(100, Math.max(0, ((p.open_interest || 0) / maxOI) * 100));

                const tr = document.createElement('tr');
                if (isAtm) tr.className = 'strike-atm';

                const isCallItm = k < this.spotPrice;
                const isPutItm = k > this.spotPrice;

                tr.innerHTML = `
                    <!-- Calls Section -->
                    <td class="text-right font-numeric oi-cell ${isCallItm ? 'itm-call' : ''}">
                        <div class="oi-bar call" style="width: ${cOiPct.toFixed(1)}%;"></div>
                        <span class="oi-text">${c.open_interest ? c.open_interest.toLocaleString('en-IN') : '—'}</span>
                        ${c.is_key_resistance ? '<span class="badge-resistance" title="Key Resistance">R</span>' : ''}
                    </td>
                    <td class="text-right font-numeric ${(c.change_oi || 0) >= 0 ? 'text-success' : 'text-danger'} ${isCallItm ? 'itm-call' : ''}">
                        ${c.change_oi ? ((c.change_oi >= 0 ? '+' : '') + c.change_oi.toLocaleString('en-IN')) : '—'}
                    </td>
                    <td class="text-right font-numeric ${isCallItm ? 'itm-call' : ''}">
                        ${c.volume ? (c.volume / 1000).toFixed(1) : '—'}
                    </td>
                    <td class="text-right font-numeric font-bold ${isCallItm ? 'itm-call' : ''}">
                        ₹${c.last_price ? c.last_price.toFixed(2) : '—'}
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
                    <td class="text-right font-numeric font-bold ${isPutItm ? 'itm-put' : ''}">
                        ₹${p.last_price ? p.last_price.toFixed(2) : '—'}
                    </td>
                    <td class="text-right font-numeric ${isPutItm ? 'itm-put' : ''}">
                        ${p.volume ? (p.volume / 1000).toFixed(1) : '—'}
                    </td>
                    <td class="text-right font-numeric ${(p.change_oi || 0) >= 0 ? 'text-success' : 'text-danger'} ${isPutItm ? 'itm-put' : ''}">
                        ${p.change_oi ? ((p.change_oi >= 0 ? '+' : '') + p.change_oi.toLocaleString('en-IN')) : '—'}
                    </td>
                    <td class="text-right font-numeric oi-cell ${isPutItm ? 'itm-put' : ''}">
                        <div class="oi-bar put" style="width: ${pOiPct.toFixed(1)}%;"></div>
                        <span class="oi-text">${p.open_interest ? p.open_interest.toLocaleString('en-IN') : '—'}</span>
                        ${p.is_key_support ? '<span class="badge-support" title="Key Support">S</span>' : ''}
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

                const btnBuyPut = tr.querySelector('[data-action="buy-put"]');
                const btnSellPut = tr.querySelector('[data-action="sell-put"]');
                const btnBasketPut = tr.querySelector('[data-action="basket-put"]');
                const btnPin = tr.querySelector('[data-action="pin-strike"]');

                if (btnBuyCall) btnBuyCall.addEventListener('click', () => this.tradeContract(c, 'BUY'));
                if (btnSellCall) btnSellCall.addEventListener('click', () => this.tradeContract(c, 'SELL'));
                if (btnBasketCall) btnBasketCall.addEventListener('click', () => this.addContractToBasket(c, 'BUY'));

                if (btnBuyPut) btnBuyPut.addEventListener('click', () => this.tradeContract(p, 'BUY'));
                if (btnSellPut) btnSellPut.addEventListener('click', () => this.tradeContract(p, 'SELL'));
                if (btnBasketPut) btnBasketPut.addEventListener('click', () => this.addContractToBasket(p, 'BUY'));

                if (btnPin) btnPin.addEventListener('click', () => this.pinToWatchlist(c, p, k));

                tbody.appendChild(tr);
            });
        }

        /* ==========================================================================
           3. Action Handlers (Trade Ticket, Basket Addition, Watchlist Pin)
           ========================================================================== */
        tradeContract(contract, side = 'BUY') {
            if (!window.orderTicketController || !contract.trading_symbol) return;
            window.orderTicketController.openTicket(contract, side, {
                product: 'NRML',
                price: contract.last_price || 0,
                notice: `${side} ${contract.trading_symbol} @ ₹${(contract.last_price || 0).toFixed(2)}`
            });
        }

        addContractToBasket(contract, side = 'BUY') {
            if (!window.basketBuilderController || !contract.trading_symbol) return;
            const leg = {
                instrument_token: contract.instrument_token || '0',
                trading_symbol: contract.trading_symbol,
                exchange_segment: contract.exchange_segment || 'nse_fo',
                side: side,
                product_type: 'NRML',
                order_type: 'LIMIT',
                price: contract.last_price || 100.0,
                lot_size: this.symbol.includes('BANKNIFTY') ? 15 : 25,
                lots: 1,
                quantity: this.symbol.includes('BANKNIFTY') ? 15 : 25,
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
