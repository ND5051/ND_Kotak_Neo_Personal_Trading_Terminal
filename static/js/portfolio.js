/**
 * Kotak Neo Personal Trading Terminal - Phase 11C
 * Portfolio Controller: Holdings (CNC), Positions (MIS/NRML), Live MTM, Quick Actions & Funds Ledger
 */

(function (window, document) {
    'use strict';

    class PortfolioController {
        constructor() {
            this.holdings = [];
            this.positions = [];
            this.margins = null;
            this.lastRefreshed = null;
            this.posFilter = 'ALL';
            this.posProductFilter = 'ALL';
            this.activeReverseItem = null;
            this.activeExitItem = null;

            this.init();
        }

        init() {
            this.bindEvents();
            this.bindFilterTabs();
            this.bindModals();

            // Initial load
            this.loadAll();

            console.log('[PortfolioController] Phase 11C Initialized.');
        }

        bindEvents() {
            // Refresh buttons
            const refHoldingsBtn = document.getElementById('refresh-holdings-btn');
            const refPositionsBtn = document.getElementById('refresh-positions-btn');
            const refFundsBtn = document.getElementById('refresh-funds-expanded-btn');

            if (refHoldingsBtn) {
                refHoldingsBtn.addEventListener('click', () => this.forceRefresh());
            }
            if (refPositionsBtn) {
                refPositionsBtn.addEventListener('click', () => this.forceRefresh());
            }
            if (refFundsBtn) {
                refFundsBtn.addEventListener('click', () => this.forceRefresh());
            }

            // Funds actions
            const addFundsBtn = document.getElementById('btn-add-funds');
            const withdrawBtn = document.getElementById('btn-withdraw-funds');
            if (addFundsBtn) {
                addFundsBtn.addEventListener('click', () => {
                    if (window.terminalShell) window.terminalShell.showToast('Banking Gateway: UPI / Netbanking Portal Connected.');
                });
            }
            if (withdrawBtn) {
                withdrawBtn.addEventListener('click', () => {
                    if (window.terminalShell) window.terminalShell.showToast('Funds Withdrawal: Payout requests processed at 17:00 IST.');
                });
            }
        }

        bindFilterTabs() {
            // Positions filter tabs
            const posTabs = document.querySelectorAll('[data-pos-filter]');
            posTabs.forEach(tab => {
                tab.addEventListener('click', (e) => {
                    posTabs.forEach(t => t.classList.remove('active'));
                    const target = e.currentTarget;
                    target.classList.add('active');
                    this.posFilter = target.getAttribute('data-pos-filter');
                    this.renderPositions();
                });
            });

            // Product filter dropdown
            const prodFilter = document.getElementById('pos-product-filter');
            if (prodFilter) {
                prodFilter.addEventListener('change', (e) => {
                    this.posProductFilter = e.target.value;
                    this.renderPositions();
                });
            }
        }

        bindModals() {
            // Emergency Square Off All
            const sqAllBtn = document.getElementById('btn-square-off-all');
            const sqAllModal = document.getElementById('square-off-all-modal');
            const sqAllClose = document.getElementById('sq-all-close-btn');
            const sqAllCancel = document.getElementById('sq-all-cancel-btn');
            const sqAllConfirm = document.getElementById('sq-all-confirm-btn');
            const challengeInput = document.getElementById('sq-all-challenge-input');

            if (sqAllBtn && sqAllModal) {
                sqAllBtn.addEventListener('click', () => {
                    const openPositions = this.positions.filter(p => p.net_quantity !== 0);
                    if (openPositions.length === 0) {
                        if (window.terminalShell) window.terminalShell.showToast('No active open positions to square off.');
                        return;
                    }
                    this.renderSquareOffList(openPositions);
                    sqAllModal.classList.remove('hidden');
                });
            }

            const closeSqModal = () => {
                if (sqAllModal) sqAllModal.classList.add('hidden');
                if (challengeInput) challengeInput.value = '';
            };

            if (sqAllClose) sqAllClose.addEventListener('click', closeSqModal);
            if (sqAllCancel) sqAllCancel.addEventListener('click', closeSqModal);

            if (sqAllConfirm) {
                sqAllConfirm.addEventListener('click', () => this.executeSquareOffAll());
            }

            // Reverse Position Modal
            const revModal = document.getElementById('reverse-position-modal');
            const revClose = document.getElementById('rev-close-btn');
            const revCancel = document.getElementById('rev-cancel-btn');
            const revConfirm = document.getElementById('rev-confirm-btn');

            const closeRevModal = () => {
                if (revModal) revModal.classList.add('hidden');
                this.activeReverseItem = null;
            };

            if (revClose) revClose.addEventListener('click', closeRevModal);
            if (revCancel) revCancel.addEventListener('click', closeRevModal);

            if (revConfirm) {
                revConfirm.addEventListener('click', () => {
                    if (this.activeReverseItem) {
                        this.executePositionReverse(this.activeReverseItem);
                        closeRevModal();
                    }
                });
            }

            // High-Exposure Exit Modal (> ₹1,00,000 Safety Threshold)
            const highExpModal = document.getElementById('high-exposure-exit-modal');
            const highExpClose = document.getElementById('high-exp-close-btn');
            const highExpCancel = document.getElementById('high-exp-cancel-btn');
            const highExpProceed = document.getElementById('high-exp-proceed-btn');

            const closeHighExpModal = () => {
                if (highExpModal) highExpModal.classList.add('hidden');
                this.activeExitItem = null;
            };

            if (highExpClose) highExpClose.addEventListener('click', closeHighExpModal);
            if (highExpCancel) highExpCancel.addEventListener('click', closeHighExpModal);

            if (highExpProceed) {
                highExpProceed.addEventListener('click', () => {
                    if (this.activeExitItem) {
                        const item = this.activeExitItem;
                        closeHighExpModal();
                        this.proceedWithPositionExit(item);
                    }
                });
            }
        }

        /* ==========================================================================
           Data Fetching & Refresh
           ========================================================================== */
        async loadAll() {
            try {
                await Promise.all([
                    this.fetchHoldings(),
                    this.fetchPositions(),
                    this.fetchMargins(),
                    this.fetchPnl()
                ]);
            } catch (err) {
                console.warn('[PortfolioController] Load all warning:', err);
            }
        }

        async forceRefresh() {
            this.setSpinners(true);
            try {
                const res = await fetch('/api/portfolio/refresh', { credentials: 'same-origin', method: 'POST' });
                const json = await res.json();
                if (json.data && json.data.summary) {
                    this.updateTimestamp(json.data.summary.retrieved_timestamp || new Date().toISOString());
                }
                await this.loadAll();
                if (window.terminalShell) {
                    window.terminalShell.showToast('Portfolio & Margin balances refreshed from broker.');
                }
            } catch (err) {
                console.error('[PortfolioController] Force refresh failed:', err);
                if (window.terminalShell) {
                    window.terminalShell.showToast('Refresh failed: Network / Broker error.');
                }
            } finally {
                this.setSpinners(false);
            }
        }

        setSpinners(spinning) {
            document.querySelectorAll('.refresh-icon').forEach(icon => {
                if (spinning) icon.classList.add('spinning');
                else icon.classList.remove('spinning');
            });
        }

        updateTimestamp(isoTimestamp) {
            this.lastRefreshed = isoTimestamp;
            let display = '--:--:--';
            if (isoTimestamp) {
                const date = new Date(isoTimestamp);
                display = isNaN(date.getTime()) ? isoTimestamp : date.toLocaleTimeString('en-IN', { hour12: false });
            }
            const hEl = document.getElementById('holdings-last-refreshed');
            const pEl = document.getElementById('positions-last-refreshed');
            const fEl = document.getElementById('funds-last-refreshed');
            if (hEl) hEl.textContent = display;
            if (pEl) pEl.textContent = display;
            if (fEl) fEl.textContent = display;
        }

        /* ==========================================================================
           Holdings Screen
           ========================================================================== */
        async fetchHoldings() {
            try {
                const res = await fetch('/api/portfolio/holdings', { credentials: 'same-origin' });
                if (!res.ok) return;
                const json = await res.json();
                this.holdings = (json.data && json.data.holdings) || [];
                this.renderHoldings();
            } catch (e) {
                console.error('[PortfolioController] Fetch holdings error:', e);
            }
        }

        renderHoldings() {
            const tbody = document.getElementById('holdings-tbody');
            const empty = document.getElementById('holdings-empty-state');
            if (!tbody) return;

            tbody.innerHTML = '';

            let totalInvested = 0;
            let currentVal = 0;
            let dayPnl = 0;

            if (this.holdings.length === 0) {
                if (empty) empty.classList.remove('hidden');
            } else {
                if (empty) empty.classList.add('hidden');

                this.holdings.forEach(item => {
                    const totalQty = (item.quantity || 0) + (item.t1_quantity || 0);
                    const avgPrice = item.average_price || 0;
                    const ltp = item.last_price || item.close_price || 0;
                    const invested = totalQty * avgPrice;
                    const curVal = totalQty * ltp;
                    const pnl = curVal - invested;
                    const pnlPct = invested > 0 ? (pnl / invested) * 100 : 0;
                    const dPnl = item.day_pnl || 0;

                    totalInvested += invested;
                    currentVal += curVal;
                    dayPnl += dPnl;

                    const tr = document.createElement('tr');
                    tr.innerHTML = `
                        <td>
                            <div class="scrip-symbol-block">
                                <span class="font-bold">${item.trading_symbol}</span>
                                <span class="badge-segment">${(item.exchange_segment || 'NSE').toUpperCase()}</span>
                            </div>
                        </td>
                        <td class="text-right font-numeric">${item.quantity || 0}</td>
                        <td class="text-right font-numeric text-muted">${item.t1_quantity || 0}</td>
                        <td class="text-right font-numeric">₹${avgPrice.toFixed(2)}</td>
                        <td class="text-right font-numeric font-bold">₹${ltp > 0 ? ltp.toFixed(2) : '—'}</td>
                        <td class="text-right font-numeric">₹${curVal.toFixed(2)}</td>
                        <td class="text-right font-numeric ${pnl >= 0 ? 'text-success' : 'text-danger'}">
                            ${pnl >= 0 ? '+' : ''}₹${pnl.toFixed(2)} (${pnlPct.toFixed(2)}%)
                        </td>
                        <td class="text-right font-numeric ${dPnl >= 0 ? 'text-success' : 'text-danger'}">
                            ${dPnl >= 0 ? '+' : ''}₹${dPnl.toFixed(2)}
                        </td>
                        <td class="text-center">
                            <div class="table-actions">
                                <button class="btn btn-xs btn-action-add" data-action="add-holding" title="Buy more shares">Add</button>
                                <button class="btn btn-xs btn-action-exit" data-action="exit-holding" title="Sell holding from Demat">Exit</button>
                            </div>
                        </td>
                    `;

                    // Bind action buttons
                    const addBtn = tr.querySelector('[data-action="add-holding"]');
                    const exitBtn = tr.querySelector('[data-action="exit-holding"]');

                    if (addBtn) {
                        addBtn.addEventListener('click', () => this.handleHoldingAdd(item));
                    }
                    if (exitBtn) {
                        exitBtn.addEventListener('click', () => this.handleHoldingExit(item));
                    }

                    tbody.appendChild(tr);
                });
            }

            // Summary metrics strip
            const totalPnl = currentVal - totalInvested;
            const totalPnlPct = totalInvested > 0 ? (totalPnl / totalInvested) * 100 : 0;

            const invEl = document.getElementById('holdings-total-invested');
            const curEl = document.getElementById('holdings-current-val');
            const pnlEl = document.getElementById('holdings-total-pnl');
            const dayEl = document.getElementById('holdings-day-pnl');

            if (invEl) invEl.textContent = `₹${totalInvested.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
            if (curEl) curEl.textContent = `₹${currentVal.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
            if (pnlEl) {
                pnlEl.textContent = `${totalPnl >= 0 ? '+' : ''}₹${totalPnl.toFixed(2)} (${totalPnlPct.toFixed(2)}%)`;
                pnlEl.className = `val font-numeric ${totalPnl >= 0 ? 'text-success' : 'text-danger'}`;
            }
            if (dayEl) {
                dayEl.textContent = `${dayPnl >= 0 ? '+' : ''}₹${dayPnl.toFixed(2)}`;
                dayEl.className = `val font-numeric ${dayPnl >= 0 ? 'text-success' : 'text-danger'}`;
            }
        }

        handleHoldingAdd(item) {
            if (!window.orderTicketController) return;
            window.orderTicketController.openTicket(item, 'BUY', {
                product: 'CNC',
                quantity: 1,
                price: item.last_price || item.close_price,
                notice: `Add to Holdings: BUY 1 ${item.trading_symbol} CNC`
            });
        }

        handleHoldingExit(item) {
            if (!window.orderTicketController) return;
            const availQty = item.quantity || 0;
            if (availQty <= 0) {
                if (window.terminalShell) window.terminalShell.showToast(`Cannot exit ${item.trading_symbol}: 0 settled shares available (T1 cannot be sold).`);
                return;
            }
            window.orderTicketController.openTicket(item, 'SELL', {
                product: 'CNC',
                quantity: availQty,
                price: item.last_price || item.close_price,
                notice: `Exit Holdings: SELL ${availQty} ${item.trading_symbol} CNC`
            });
        }

        /* ==========================================================================
           Positions Screen & Live MTM
           ========================================================================== */
        async fetchPositions() {
            try {
                const res = await fetch('/api/portfolio/positions?type=net&status=all', { credentials: 'same-origin' });
                if (!res.ok) return;
                const json = await res.json();
                this.positions = (json.data && json.data.positions) || [];
                this.renderPositions();
            } catch (e) {
                console.error('[PortfolioController] Fetch positions error:', e);
            }
        }

        renderPositions() {
            const tbody = document.getElementById('positions-tbody');
            const empty = document.getElementById('positions-empty-state');
            if (!tbody) return;

            tbody.innerHTML = '';

            let openCount = 0;
            let closedCount = 0;
            let totalRealized = 0;
            let totalMtm = 0;
            let totalExposure = 0;

            const filtered = this.positions.filter(pos => {
                const isOpen = pos.net_quantity !== 0;
                if (isOpen) openCount++;
                else closedCount++;

                // Tab filter
                if (this.posFilter === 'OPEN' && !isOpen) return false;
                if (this.posFilter === 'CLOSED' && isOpen) return false;

                // Product filter
                if (this.posProductFilter !== 'ALL' && (pos.product_type || '').toUpperCase() !== this.posProductFilter) {
                    return false;
                }
                return true;
            });

            // Update tab badge counts
            const countAll = document.getElementById('pos-count-all');
            const countOpen = document.getElementById('pos-count-open');
            const countClosed = document.getElementById('pos-count-closed');
            const totalOpenSpan = document.getElementById('total-open-positions');

            if (countAll) countAll.textContent = this.positions.length;
            if (countOpen) countOpen.textContent = openCount;
            if (countClosed) countClosed.textContent = closedCount;
            if (totalOpenSpan) totalOpenSpan.textContent = openCount;

            const navPosBadge = document.getElementById('badge-open-positions');
            if (navPosBadge) navPosBadge.textContent = openCount;

            if (filtered.length === 0) {
                if (empty) empty.classList.remove('hidden');
            } else {
                if (empty) empty.classList.add('hidden');

                filtered.forEach(pos => {
                    const netQty = pos.net_quantity || 0;
                    const isOpen = netQty !== 0;
                    const buyAvg = pos.buy_average || 0;
                    const sellAvg = pos.sell_average || 0;
                    const ltp = pos.last_price || 0;

                    let realized = pos.realized_pnl || 0;
                    let mtm = 0;

                    if (isOpen) {
                        if (netQty > 0) {
                            mtm = ltp > 0 ? (netQty * (ltp - buyAvg)) : 0;
                        } else {
                            mtm = ltp > 0 ? (Math.abs(netQty) * (sellAvg - ltp)) : 0;
                        }
                    }

                    const netPnl = realized + mtm;
                    totalRealized += realized;
                    totalMtm += mtm;

                    // Approximate exposure margin: Qty * LTP
                    if (isOpen) {
                        totalExposure += Math.abs(netQty) * (ltp > 0 ? ltp : (buyAvg || sellAvg));
                    }

                    const tr = document.createElement('tr');
                    const qtyClass = netQty > 0 ? 'text-success font-bold' : (netQty < 0 ? 'text-danger font-bold' : 'text-muted');
                    const qtyFormatted = netQty > 0 ? `+${netQty}` : `${netQty}`;

                    tr.innerHTML = `
                        <td><span class="badge badge-product">${pos.product_type || 'MIS'}</span></td>
                        <td>
                            <div class="scrip-symbol-block">
                                <span class="font-bold">${pos.trading_symbol}</span>
                                <span class="badge-segment">${(pos.exchange_segment || 'NSE').toUpperCase()}</span>
                            </div>
                        </td>
                        <td class="text-right font-numeric ${qtyClass}">${qtyFormatted}</td>
                        <td class="text-right font-numeric">₹${buyAvg.toFixed(2)}</td>
                        <td class="text-right font-numeric">₹${sellAvg.toFixed(2)}</td>
                        <td class="text-right font-numeric font-bold">₹${ltp > 0 ? ltp.toFixed(2) : '—'}</td>
                        <td class="text-right font-numeric ${realized >= 0 ? 'text-success' : 'text-danger'}">
                            ${realized >= 0 ? '+' : ''}₹${realized.toFixed(2)}
                        </td>
                        <td class="text-right font-numeric ${mtm >= 0 ? 'text-success' : 'text-danger'}">
                            ${isOpen ? (ltp > 0 ? `${mtm >= 0 ? '+' : ''}₹${mtm.toFixed(2)}` : '—') : '0.00'}
                        </td>
                        <td class="text-right font-numeric ${netPnl >= 0 ? 'text-success' : 'text-danger'} font-bold">
                            ${netPnl >= 0 ? '+' : ''}₹${netPnl.toFixed(2)}
                        </td>
                        <td class="text-center">
                            ${isOpen ? `
                                <div class="table-actions">
                                    <button class="btn btn-xs btn-action-add" data-action="pos-add" title="Add / Scale position">Add</button>
                                    <button class="btn btn-xs btn-action-exit" data-action="pos-exit" title="Square off this open position">Exit</button>
                                    <button class="btn btn-xs btn-action-reverse" data-action="pos-reverse" title="Flip position 180° with 2x size">Reverse</button>
                                </div>
                            ` : `<span class="badge badge-neutral">CLOSED</span>`}
                        </td>
                    `;

                    if (isOpen) {
                        const addBtn = tr.querySelector('[data-action="pos-add"]');
                        const exitBtn = tr.querySelector('[data-action="pos-exit"]');
                        const revBtn = tr.querySelector('[data-action="pos-reverse"]');

                        if (addBtn) addBtn.addEventListener('click', () => this.handlePositionAdd(pos));
                        if (exitBtn) exitBtn.addEventListener('click', () => this.handlePositionExit(pos));
                        if (revBtn) revBtn.addEventListener('click', () => this.promptPositionReverse(pos));
                    }

                    tbody.appendChild(tr);
                });
            }

            // Summary metrics strip
            const netDayPnl = totalRealized + totalMtm;
            const rEl = document.getElementById('pos-realized-pnl');
            const mEl = document.getElementById('pos-unrealized-mtm');
            const nEl = document.getElementById('pos-net-pnl');
            const expEl = document.getElementById('pos-exposure-margin');

            if (rEl) {
                rEl.textContent = `${totalRealized >= 0 ? '+' : ''}₹${totalRealized.toFixed(2)}`;
                rEl.className = `val font-numeric ${totalRealized >= 0 ? 'text-success' : 'text-danger'}`;
            }
            if (mEl) {
                mEl.textContent = `${totalMtm >= 0 ? '+' : ''}₹${totalMtm.toFixed(2)}`;
                mEl.className = `val font-numeric ${totalMtm >= 0 ? 'text-success' : 'text-danger'}`;
            }
            if (nEl) {
                nEl.textContent = `${netDayPnl >= 0 ? '+' : ''}₹${netDayPnl.toFixed(2)}`;
                nEl.className = `val font-numeric ${netDayPnl >= 0 ? 'text-success' : 'text-danger'}`;
            }
            if (expEl) {
                expEl.textContent = `₹${totalExposure.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
            }

            const navDayPnl = document.getElementById('nav-day-pnl');
            if (navDayPnl) {
                navDayPnl.textContent = `${netDayPnl >= 0 ? '+' : ''}₹${netDayPnl.toFixed(2)}`;
                navDayPnl.className = `pnl-value font-numeric ${netDayPnl >= 0 ? 'text-success' : 'text-danger'}`;
            }

            // Enable / Disable emergency Square Off All button
            const sqAllBtn = document.getElementById('btn-square-off-all');
            if (sqAllBtn) {
                sqAllBtn.disabled = openCount === 0;
            }
        }

        handlePositionAdd(pos) {
            if (!window.orderTicketController) return;
            const side = pos.net_quantity > 0 ? 'BUY' : 'SELL';
            const isFo = (pos.exchange_segment || '').toLowerCase().includes('fo');
            const defaultQty = isFo ? (pos.trading_symbol.includes('BANKNIFTY') ? 15 : 25) : 1;

            window.orderTicketController.openTicket(pos, side, {
                product: pos.product_type || 'MIS',
                quantity: defaultQty,
                price: pos.last_price || 0,
                notice: `Add Position: ${side} ${defaultQty} ${pos.trading_symbol} (${pos.product_type})`
            });
        }

        handlePositionExit(pos) {
            if (!window.orderTicketController) return;
            const qty = Math.abs(pos.net_quantity || 0);
            const price = pos.last_price || pos.buy_average || pos.sell_average || 0;
            const exposure = qty * price;

            // Position Exit Safety Threshold: If exposure > ₹1,00,000, show confirmation modal
            if (exposure > 100000) {
                this.promptHighExposureExit(pos, exposure, price, qty);
            } else {
                this.proceedWithPositionExit(pos);
            }
        }

        promptHighExposureExit(pos, exposure, price, qty) {
            this.activeExitItem = pos;
            const modal = document.getElementById('high-exposure-exit-modal');
            const symEl = document.getElementById('high-exp-symbol');
            const prodEl = document.getElementById('high-exp-product');
            const qtyEl = document.getElementById('high-exp-qty');
            const priceEl = document.getElementById('high-exp-price');
            const valEl = document.getElementById('high-exp-val');
            const actionEl = document.getElementById('high-exp-action');

            const side = pos.net_quantity > 0 ? 'SELL' : 'BUY';

            if (symEl) symEl.textContent = pos.trading_symbol;
            if (prodEl) prodEl.textContent = pos.product_type || 'MIS';
            if (qtyEl) qtyEl.textContent = `${pos.net_quantity > 0 ? '+' : ''}${pos.net_quantity} Qty`;
            if (priceEl) priceEl.textContent = `₹${price.toFixed(2)}`;
            if (valEl) valEl.textContent = `₹${exposure.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
            if (actionEl) actionEl.textContent = `Place ${side} Order for ${qty} Qty @ Market/LTP`;

            if (modal) modal.classList.remove('hidden');
        }

        proceedWithPositionExit(pos) {
            if (!window.orderTicketController) return;
            const side = pos.net_quantity > 0 ? 'SELL' : 'BUY';
            const exitQty = Math.abs(pos.net_quantity);

            window.orderTicketController.openTicket(pos, side, {
                product: pos.product_type || 'MIS',
                quantity: exitQty,
                price: pos.last_price || 0,
                notice: `EXIT POSITION: ${side} ${exitQty} ${pos.trading_symbol} (${pos.product_type})`
            });
        }

        promptPositionReverse(pos) {
            this.activeReverseItem = pos;
            const revModal = document.getElementById('reverse-position-modal');
            const symEl = document.getElementById('rev-symbol');
            const curEl = document.getElementById('rev-current-pos');
            const newEl = document.getElementById('rev-new-pos');
            const actionEl = document.getElementById('rev-action-text');

            const currentSide = pos.net_quantity > 0 ? 'LONG' : 'SHORT';
            const currentQty = Math.abs(pos.net_quantity);
            const reverseSide = pos.net_quantity > 0 ? 'SHORT' : 'LONG';
            const reverseOrderSide = pos.net_quantity > 0 ? 'SELL' : 'BUY';
            const reverseOrderQty = currentQty * 2;

            if (symEl) symEl.textContent = `${pos.trading_symbol} (${pos.product_type})`;
            if (curEl) curEl.textContent = `${currentSide} (+${currentQty} Qty)`;
            if (newEl) newEl.textContent = `${reverseSide} (-${currentQty} Qty)`;
            if (actionEl) actionEl.textContent = `Place ${reverseOrderSide} order for ${reverseOrderQty} Qty (2x ${currentQty})`;

            if (revModal) revModal.classList.remove('hidden');
        }

        executePositionReverse(pos) {
            if (!window.orderTicketController) return;
            const side = pos.net_quantity > 0 ? 'SELL' : 'BUY';
            const revQty = Math.abs(pos.net_quantity) * 2;

            window.orderTicketController.openTicket(pos, side, {
                product: pos.product_type || 'MIS',
                quantity: revQty,
                price: pos.last_price || 0,
                notice: `REVERSE POSITION: ${side} ${revQty} ${pos.trading_symbol} (${pos.product_type})`
            });
        }

        renderSquareOffList(openPositions) {
            const listEl = document.getElementById('sq-all-positions-list');
            if (!listEl) return;
            listEl.innerHTML = '';

            openPositions.forEach(p => {
                const exitSide = p.net_quantity > 0 ? 'SELL' : 'BUY';
                const qty = Math.abs(p.net_quantity);
                const li = document.createElement('li');
                li.innerHTML = `<strong>${exitSide}</strong> ${qty} Qty <code>${p.trading_symbol}</code> (${p.product_type})`;
                listEl.appendChild(li);
            });
        }

        async executeSquareOffAll() {
            const sqAllModal = document.getElementById('square-off-all-modal');
            const challengeInput = document.getElementById('sq-all-challenge-input');
            const mode = window.terminalShell ? window.terminalShell.executionMode : 'PAPER';

            if (mode === 'LIVE') {
                const entered = (challengeInput ? challengeInput.value : '').trim();
                if (entered !== 'CONFIRM_EXIT_ALL') {
                    if (window.terminalShell) window.terminalShell.showToast('Confirmation failed. You must type CONFIRM_EXIT_ALL in LIVE mode.');
                    return;
                }
            }

            const openPositions = this.positions.filter(p => p.net_quantity !== 0);
            if (openPositions.length === 0) {
                if (sqAllModal) sqAllModal.classList.add('hidden');
                return;
            }

            let successCount = 0;
            for (const pos of openPositions) {
                const side = pos.net_quantity > 0 ? 'SELL' : 'BUY';
                const qty = Math.abs(pos.net_quantity);
                try {
                    const payload = {
                        trading_symbol: pos.trading_symbol,
                        exchange_segment: pos.exchange_segment || 'nse_cm',
                        instrument_token: pos.instrument_token,
                        side: side,
                        order_type: 'MARKET',
                        product_type: pos.product_type || 'MIS',
                        quantity: qty,
                        price: 0.0,
                        trigger_price: 0.0,
                        validity: 'DAY',
                        available_cash: 1000000.0
                    };
                    const res = await fetch('/api/orders/place', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        credentials: 'same-origin',
                        body: JSON.stringify(payload)
                    });
                    if (res.ok) successCount++;
                } catch (e) {
                    console.error('[SquareOffAll] Failed for pos:', pos.trading_symbol, e);
                }
            }

            if (sqAllModal) sqAllModal.classList.add('hidden');
            if (challengeInput) challengeInput.value = '';

            if (window.terminalShell) {
                window.terminalShell.showToast(`Emergency Square Off: Dispatched ${successCount} of ${openPositions.length} exit orders.`);
            }

            // Refresh portfolio and orders
            this.forceRefresh();
            if (window.orderBookController) {
                window.orderBookController.fetchOrders();
            }
        }

        /* ==========================================================================
           Funds & Expanded Ledger
           ========================================================================== */
        async fetchMargins() {
            try {
                const res = await fetch('/api/portfolio/margins', { credentials: 'same-origin' });
                if (!res.ok) return;
                const json = await res.json();
                this.margins = (json.data && json.data.margins) || null;
                this.renderFunds();
            } catch (e) {
                console.error('[PortfolioController] Fetch margins error:', e);
            }
        }

        renderFunds() {
            if (!this.margins) return;
            const m = this.margins;

            const availCash = m.available_cash || 0;
            const collateral = m.collateral_equity || 0;
            const mtmCredit = m.unrealized_mtm || 0;
            const totalAvail = m.net_margin_available || (availCash + collateral);

            const spanMargin = m.used_margin_span || 0;
            const exposureMargin = m.used_margin_exposure || 0;
            const premiumBlocked = m.used_margin_option_premium || 0;
            const totalUsed = m.total_margin_used || (spanMargin + exposureMargin + premiumBlocked);

            // Populate ledger
            const cEl = document.getElementById('funds-avail-cash');
            const colEl = document.getElementById('funds-collateral');
            const mtmEl = document.getElementById('funds-mtm-credit');
            const totAvailEl = document.getElementById('funds-total-avail');

            if (cEl) cEl.textContent = `₹${availCash.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
            if (colEl) colEl.textContent = `₹${collateral.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
            if (mtmEl) mtmEl.textContent = `${mtmCredit >= 0 ? '+' : ''}₹${mtmCredit.toFixed(2)}`;
            if (totAvailEl) totAvailEl.textContent = `₹${totalAvail.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;

            const spEl = document.getElementById('funds-span-margin');
            const expEl = document.getElementById('funds-exposure-margin');
            const premEl = document.getElementById('funds-premium-blocked');
            const totUsedEl = document.getElementById('funds-total-used');

            if (spEl) spEl.textContent = `₹${spanMargin.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
            if (expEl) expEl.textContent = `₹${exposureMargin.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
            if (premEl) premEl.textContent = `₹${premiumBlocked.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
            if (totUsedEl) totUsedEl.textContent = `₹${totalUsed.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;

            // Utilization Bar
            const utilizationPct = totalAvail > 0 ? Math.min(100, Math.max(0, (totalUsed / totalAvail) * 100)) : 0;
            const barFill = document.getElementById('funds-utilization-bar');
            const pctEl = document.getElementById('funds-utilization-pct');
            const usedSum = document.getElementById('funds-used-summary');
            const availSum = document.getElementById('funds-avail-summary');
            const thresholdText = document.getElementById('funds-threshold-text');
            const statusIndicator = document.getElementById('funds-threshold-indicator');

            if (barFill) barFill.style.width = `${utilizationPct.toFixed(1)}%`;
            if (pctEl) pctEl.textContent = `${utilizationPct.toFixed(1)}%`;
            if (usedSum) usedSum.textContent = `₹${totalUsed.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
            if (availSum) availSum.textContent = `₹${totalAvail.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;

            if (barFill && statusIndicator && thresholdText) {
                barFill.className = 'progress-bar-fill';
                statusIndicator.className = 'status-indicator';

                if (utilizationPct >= 85) {
                    barFill.classList.add('danger');
                    statusIndicator.classList.add('danger');
                    thresholdText.textContent = 'Status: CRITICAL MARGIN ALERT (≥85% Hard Limit Hit). New exposure locked.';
                } else if (utilizationPct >= 70) {
                    barFill.classList.add('caution');
                    statusIndicator.classList.add('caution');
                    thresholdText.textContent = 'Status: CAUTION ZONE (≥70% Capital Utilized).';
                } else {
                    statusIndicator.classList.add('safe');
                    thresholdText.textContent = 'Status: SAFE CAPITAL BUFFER (Thresholds: 70% Caution, 85% Hard Limit)';
                }
            }

            // Risk Snapshot
            const peakEl = document.getElementById('funds-peak-margin');
            const adhocEl = document.getElementById('funds-adhoc-margin');
            const tsEl = document.getElementById('funds-balance-timestamp');

            if (peakEl) peakEl.textContent = `₹${(m.peak_margin || totalUsed).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
            if (adhocEl) adhocEl.textContent = `₹${(m.adhoc_margin || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
            if (tsEl) {
                const ts = m.retrieved_timestamp || m.source_timestamp || this.lastRefreshed;
                tsEl.textContent = ts ? new Date(ts).toLocaleTimeString('en-IN', { hour12: false }) : '--:--:--';
            }
        }

        async fetchPnl() {
            try {
                const res = await fetch('/api/portfolio/pnl', { credentials: 'same-origin' });
                if (!res.ok) return;
                const json = await res.json();
                if (json.data && json.data.retrieved_timestamp) {
                    this.updateTimestamp(json.data.retrieved_timestamp);
                }
            } catch (e) {
                console.error('[PortfolioController] Fetch pnl error:', e);
            }
        }
    }

    // Export singleton instance
    window.portfolioController = new PortfolioController();
})(window, document);
