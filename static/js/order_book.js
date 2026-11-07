/**
 * Kotak Neo Personal Trading Terminal - Phase 11C
 * Order Book, Trade Book, and FSM Timeline Controller
 */

(function (window, document) {
    'use strict';

    class OrderBookController {
        constructor() {
            this.orders = [];
            this.trades = [];
            this.statusFilter = 'ALL';
            this.searchQuery = '';
            this.lastRefreshed = null;

            this.init();
        }

        init() {
            this.bindSubtabs();
            this.bindStatusTabs();
            this.bindSearch();
            this.bindRefreshButtons();
            this.bindBatchCancel();
            this.bindTimelineModal();

            // Initial load
            this.fetchOrders();
            this.fetchTrades();

            console.log('[OrderBookController] Phase 11C Initialized.');
        }

        bindSubtabs() {
            const subtabs = document.querySelectorAll('.orders-subtab');
            const subviewOrders = document.getElementById('subview-orders-book');
            const subviewTrades = document.getElementById('subview-trades-book');

            subtabs.forEach(tab => {
                tab.addEventListener('click', (e) => {
                    subtabs.forEach(t => t.classList.remove('active'));
                    const target = e.currentTarget;
                    target.classList.add('active');
                    const which = target.getAttribute('data-orders-subtab');

                    if (which === 'orders') {
                        if (subviewOrders) subviewOrders.classList.remove('hidden');
                        if (subviewTrades) subviewTrades.classList.add('hidden');
                        this.fetchOrders();
                    } else if (which === 'trades') {
                        if (subviewOrders) subviewOrders.classList.add('hidden');
                        if (subviewTrades) subviewTrades.classList.remove('hidden');
                        this.fetchTrades();
                    }
                });
            });
        }

        bindStatusTabs() {
            const tabs = document.querySelectorAll('[data-order-status]');
            tabs.forEach(tab => {
                tab.addEventListener('click', (e) => {
                    tabs.forEach(t => t.classList.remove('active'));
                    const target = e.currentTarget;
                    target.classList.add('active');
                    this.statusFilter = target.getAttribute('data-order-status');
                    this.renderOrders();
                });
            });
        }

        bindSearch() {
            const searchInput = document.getElementById('order-search-input');
            if (searchInput) {
                searchInput.addEventListener('input', (e) => {
                    this.searchQuery = (e.target.value || '').trim().toLowerCase();
                    this.renderOrders();
                });
            }
        }

        bindRefreshButtons() {
            const refOrdersBtn = document.getElementById('refresh-orders-btn');
            const refTradesBtn = document.getElementById('refresh-trades-btn');

            if (refOrdersBtn) {
                refOrdersBtn.addEventListener('click', () => {
                    this.fetchOrders();
                    if (window.terminalShell) window.terminalShell.showToast('Order book refreshed.');
                });
            }
            if (refTradesBtn) {
                refTradesBtn.addEventListener('click', () => {
                    this.fetchTrades();
                    if (window.terminalShell) window.terminalShell.showToast('Trade book refreshed.');
                });
            }
        }

        bindBatchCancel() {
            const btn = document.getElementById('btn-cancel-all-orders');
            if (btn) {
                btn.addEventListener('click', () => this.cancelAllOpenOrders());
            }
        }

        bindTimelineModal() {
            const modal = document.getElementById('order-timeline-modal');
            const closeX = document.getElementById('timeline-modal-close');
            const closeBtn = document.getElementById('timeline-modal-close-btn');

            const closeModal = () => {
                if (modal) modal.classList.add('hidden');
            };

            if (closeX) closeX.addEventListener('click', closeModal);
            if (closeBtn) closeBtn.addEventListener('click', closeModal);
        }

        /* ==========================================================================
           Order Book Fetch & Rendering
           ========================================================================== */
        async fetchOrders() {
            try {
                const res = await fetch('/api/orders?limit=100', { credentials: 'same-origin' });
                if (!res.ok) return;
                const json = await res.json();
                this.orders = (json.data && json.data.orders) || [];
                this.updateOrdersTimestamp();
                this.renderOrders();
            } catch (err) {
                console.error('[OrderBookController] Fetch orders error:', err);
            }
        }

        updateOrdersTimestamp() {
            const now = new Date();
            const timeStr = now.toLocaleTimeString('en-IN', { hour12: false });
            const label = document.getElementById('orders-last-refreshed');
            if (label) label.textContent = timeStr;
        }

        renderOrders() {
            const tbody = document.getElementById('orders-tbody');
            const empty = document.getElementById('orders-empty-state');
            if (!tbody) return;

            tbody.innerHTML = '';

            let openCount = 0;
            let executedCount = 0;
            let cancelledCount = 0;
            let rejectedCount = 0;
            let reconcilingCount = 0;

            // Compute counts
            this.orders.forEach(o => {
                const s = (o.status || '').toUpperCase();
                if (s === 'OPEN' || s === 'PENDING' || s === 'SUBMITTED' || s === 'VALIDATED') openCount++;
                else if (s === 'TRADED' || s === 'FILLED') executedCount++;
                else if (s === 'CANCELLED') cancelledCount++;
                else if (s === 'REJECTED' || s === 'FAILED') rejectedCount++;
                else if (s === 'RECONCILING') reconcilingCount++;
            });

            // Update badge counts
            const cntAll = document.getElementById('order-count-all');
            const cntOpen = document.getElementById('order-count-open');
            const cntExec = document.getElementById('order-count-executed');
            const cntCanc = document.getElementById('order-count-cancelled');
            const cntRej = document.getElementById('order-count-rejected');
            const cntRec = document.getElementById('order-count-reconciling');
            const cancelAllCnt = document.getElementById('cancel-all-count');
            const cancelAllBtn = document.getElementById('btn-cancel-all-orders');

            if (cntAll) cntAll.textContent = this.orders.length;
            if (cntOpen) cntOpen.textContent = openCount;
            if (cntExec) cntExec.textContent = executedCount;
            if (cntCanc) cntCanc.textContent = cancelledCount;
            if (cntRej) cntRej.textContent = rejectedCount;
            if (cntRec) cntRec.textContent = reconcilingCount;
            if (cancelAllCnt) cancelAllCnt.textContent = openCount;
            if (cancelAllBtn) cancelAllBtn.disabled = openCount === 0;

            const navOrdersBadge = document.getElementById('badge-open-orders');
            if (navOrdersBadge) navOrdersBadge.textContent = openCount;

            // Filter orders
            const filtered = this.orders.filter(o => {
                const s = (o.status || '').toUpperCase();
                // Filter tab
                if (this.statusFilter === 'OPEN') {
                    if (s !== 'OPEN' && s !== 'PENDING' && s !== 'SUBMITTED' && s !== 'VALIDATED') return false;
                } else if (this.statusFilter === 'TRADED') {
                    if (s !== 'TRADED' && s !== 'FILLED') return false;
                } else if (this.statusFilter === 'CANCELLED') {
                    if (s !== 'CANCELLED') return false;
                } else if (this.statusFilter === 'REJECTED') {
                    if (s !== 'REJECTED' && s !== 'FAILED') return false;
                } else if (this.statusFilter === 'RECONCILING') {
                    if (s !== 'RECONCILING') return false;
                }

                // Text search
                if (this.searchQuery) {
                    const sym = (o.trading_symbol || '').toLowerCase();
                    const id = (o.client_order_id || '').toLowerCase();
                    if (!sym.includes(this.searchQuery) && !id.includes(this.searchQuery)) {
                        return false;
                    }
                }
                return true;
            });

            if (filtered.length === 0) {
                if (empty) empty.classList.remove('hidden');
            } else {
                if (empty) empty.classList.add('hidden');

                filtered.forEach(o => {
                    const statusUpper = (o.status || 'OPEN').toUpperCase();
                    const isOpen = statusUpper === 'OPEN' || statusUpper === 'PENDING';
                    const sideClass = (o.order_side || o.side || 'BUY').toUpperCase() === 'BUY' ? 'text-success font-bold' : 'text-danger font-bold';

                    let timeDisplay = '--:--:--';
                    if (o.created_at) {
                        const d = new Date(o.created_at);
                        timeDisplay = isNaN(d.getTime()) ? o.created_at : d.toLocaleTimeString('en-IN', { hour12: false });
                    }

                    const badgeClass = this.getStatusBadgeClass(statusUpper);

                    const tr = document.createElement('tr');
                    tr.innerHTML = `
                        <td class="font-numeric text-muted">${timeDisplay}</td>
                        <td class="font-numeric" title="${o.client_order_id}">
                            <code>${o.client_order_id.substring(0, 14)}...</code>
                        </td>
                        <td>
                            <div class="scrip-symbol-block">
                                <span class="font-bold">${o.trading_symbol}</span>
                                <span class="badge-segment">${(o.exchange_segment || 'NSE').toUpperCase()}</span>
                            </div>
                        </td>
                        <td><span class="badge badge-product">${o.product_type || 'MIS'}</span></td>
                        <td class="font-numeric">${o.order_type || 'LIMIT'}</td>
                        <td class="${sideClass}">${(o.order_side || o.side || 'BUY').toUpperCase()}</td>
                        <td class="text-right font-numeric">${o.quantity} / ${o.filled_quantity || 0}</td>
                        <td class="text-right font-numeric">₹${(o.price || 0).toFixed(2)}</td>
                        <td><span class="${badgeClass}">${statusUpper}</span></td>
                        <td class="text-center">
                            <div class="table-actions">
                                ${isOpen ? `
                                    <button class="btn btn-xs btn-action-modify" data-action="modify" title="Modify order price/qty">Mod</button>
                                    <button class="btn btn-xs btn-action-cancel" data-action="cancel" title="Cancel open order">Can</button>
                                ` : ''}
                                <button class="btn btn-xs btn-action-timeline" data-action="timeline" title="View FSM state transitions">Timeline</button>
                            </div>
                        </td>
                    `;

                    // Bind actions
                    const modBtn = tr.querySelector('[data-action="modify"]');
                    const canBtn = tr.querySelector('[data-action="cancel"]');
                    const timeBtn = tr.querySelector('[data-action="timeline"]');

                    if (modBtn) {
                        modBtn.addEventListener('click', () => this.handleOrderModify(o));
                    }
                    if (canBtn) {
                        canBtn.addEventListener('click', () => this.handleOrderCancel(o));
                    }
                    if (timeBtn) {
                        timeBtn.addEventListener('click', () => this.showOrderTimeline(o));
                    }

                    tbody.appendChild(tr);
                });
            }
        }

        getStatusBadgeClass(status) {
            switch (status) {
                case 'OPEN':
                case 'PENDING':
                case 'SUBMITTED':
                case 'VALIDATED':
                    return 'badge-status-open';
                case 'TRADED':
                case 'FILLED':
                    return 'badge-status-traded';
                case 'CANCELLED':
                    return 'badge-status-cancelled';
                case 'REJECTED':
                case 'FAILED':
                    return 'badge-status-rejected';
                case 'RECONCILING':
                    return 'badge-status-reconciling';
                default:
                    return 'badge badge-neutral';
            }
        }

        /* ==========================================================================
           Order Modify, Cancel & Batch Actions
           ========================================================================== */
        handleOrderModify(order) {
            const newPriceStr = prompt(`Modify Price for ${order.trading_symbol}:`, (order.price || 0).toFixed(2));
            if (newPriceStr === null) return;
            const newPrice = parseFloat(newPriceStr);
            if (isNaN(newPrice) || newPrice <= 0) {
                if (window.terminalShell) window.terminalShell.showToast('Invalid price entered.');
                return;
            }

            this.sendOrderModify(order.client_order_id, { price: newPrice });
        }

        async sendOrderModify(clientOrderId, modifications) {
            try {
                const res = await fetch(`/api/orders/${clientOrderId}/modify`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'same-origin',
                    body: JSON.stringify(modifications)
                });
                const json = await res.json();
                if (res.ok) {
                    if (window.terminalShell) window.terminalShell.showToast(`Order ${clientOrderId.substring(0, 8)} modified successfully.`);
                    this.fetchOrders();
                } else {
                    if (window.terminalShell) window.terminalShell.showToast(`Modify failed: ${json.message || 'Unknown error'}`);
                }
            } catch (e) {
                console.error('[OrderBook] Modify request error:', e);
                if (window.terminalShell) window.terminalShell.showToast('Network error during modification.');
            }
        }

        async handleOrderCancel(order) {
            const confirmed = confirm(`Cancel order for ${order.quantity} ${order.trading_symbol}?`);
            if (!confirmed) return;

            try {
                const res = await fetch(`/api/orders/${order.client_order_id}/cancel`, {
                    method: 'DELETE',
                    credentials: 'same-origin'
                });
                const json = await res.json();
                if (res.ok) {
                    if (window.terminalShell) window.terminalShell.showToast(`Order ${order.client_order_id.substring(0, 8)} cancelled.`);
                    this.fetchOrders();
                } else {
                    if (window.terminalShell) window.terminalShell.showToast(`Cancel failed: ${json.message || 'Unknown error'}`);
                }
            } catch (e) {
                console.error('[OrderBook] Cancel request error:', e);
            }
        }

        async cancelAllOpenOrders() {
            const confirmed = confirm('⚠️ EMERGENCY: Are you sure you want to cancel ALL open orders across the terminal?');
            if (!confirmed) return;

            try {
                const res = await fetch('/api/orders/cancel-all', {
                    method: 'POST',
                    credentials: 'same-origin'
                });
                const json = await res.json();
                if (res.ok) {
                    if (window.terminalShell) window.terminalShell.showToast('Batch cancel dispatched for all open orders.');
                    this.fetchOrders();
                } else {
                    if (window.terminalShell) window.terminalShell.showToast(`Batch cancel failed: ${json.message || 'Error'}`);
                }
            } catch (e) {
                console.error('[OrderBook] Batch cancel error:', e);
            }
        }

        /* ==========================================================================
           Order Timeline Modal (Visual FSM Progression)
           ========================================================================== */
        async showOrderTimeline(order) {
            const modal = document.getElementById('order-timeline-modal');
            const idEl = document.getElementById('timeline-client-order-id');
            const subEl = document.getElementById('timeline-symbol-side');
            const listEl = document.getElementById('timeline-event-list');

            if (!modal) return;

            if (idEl) idEl.textContent = order.client_order_id;
            if (subEl) {
                const side = (order.order_side || order.side || 'BUY').toUpperCase();
                subEl.textContent = `${order.trading_symbol} ${order.quantity} Qty ${side} (${order.product_type || 'MIS'})`;
            }

            modal.classList.remove('hidden');

            try {
                const res = await fetch(`/api/orders/${order.client_order_id}`, { credentials: 'same-origin' });
                if (!res.ok) return;
                const json = await res.json();
                const timeline = (json.data && json.data.timeline) || [];
                const orderData = (json.data && json.data.order) || order;

                this.renderStepperAndEvents(orderData, timeline);
            } catch (e) {
                console.error('[OrderBook] Fetch timeline error:', e);
            }
        }

        renderStepperAndEvents(order, timeline) {
            const listEl = document.getElementById('timeline-event-list');
            if (listEl) listEl.innerHTML = '';

            const status = (order.status || 'DRAFT').toUpperCase();

            // Stepper nodes
            const nDraft = document.getElementById('step-node-draft');
            const nVal = document.getElementById('step-node-validated');
            const nSub = document.getElementById('step-node-submitted');
            const nPend = document.getElementById('step-node-pending');
            const nTerm = document.getElementById('step-node-terminal');

            const tDraft = document.getElementById('step-time-draft');
            const tVal = document.getElementById('step-time-validated');
            const tSub = document.getElementById('step-time-submitted');
            const tPend = document.getElementById('step-time-pending');
            const tTerm = document.getElementById('step-time-terminal');

            const l1 = document.getElementById('step-line-1');
            const l2 = document.getElementById('step-line-2');
            const l3 = document.getElementById('step-line-3');
            const l4 = document.getElementById('step-line-4');

            const termLabel = document.getElementById('step-label-terminal');

            // Reset classes
            [nDraft, nVal, nSub, nPend, nTerm].forEach(n => {
                if (n) n.className = 'step-node';
            });
            [l1, l2, l3, l4].forEach(l => {
                if (l) l.className = 'step-line';
            });

            // Set times based on timeline events
            let draftTime = order.created_at ? this.formatMsTime(order.created_at) : '--:--:--';
            let valTime = '--:--:--';
            let subTime = '--:--:--';
            let pendTime = '--:--:--';
            let termTime = '--:--:--';

            timeline.forEach(ev => {
                const to = (ev.to_status || '').toUpperCase();
                const tStr = ev.timestamp ? this.formatMsTime(ev.timestamp) : '--:--:--';
                if (to === 'VALIDATED') valTime = tStr;
                else if (to === 'SUBMITTED') subTime = tStr;
                else if (to === 'PENDING') pendTime = tStr;
                else if (to === 'TRADED' || to === 'FILLED' || to === 'REJECTED' || to === 'CANCELLED' || to === 'RECONCILING') {
                    termTime = tStr;
                }
            });

            if (tDraft) tDraft.textContent = draftTime;
            if (tVal) tVal.textContent = valTime;
            if (tSub) tSub.textContent = subTime;
            if (tPend) tPend.textContent = pendTime;
            if (tTerm) tTerm.textContent = termTime;

            // Highlight progress
            if (nDraft) nDraft.classList.add('completed');
            if (l1) l1.classList.add('completed');

            if (status === 'DRAFT') {
                if (nDraft) { nDraft.classList.remove('completed'); nDraft.classList.add('active'); }
            } else if (status === 'VALIDATED') {
                if (nVal) nVal.classList.add('active');
            } else if (status === 'SUBMITTED') {
                if (nVal) nVal.classList.add('completed');
                if (l2) l2.classList.add('completed');
                if (nSub) nSub.classList.add('active');
            } else if (status === 'PENDING') {
                if (nVal) nVal.classList.add('completed');
                if (l2) l2.classList.add('completed');
                if (nSub) nSub.classList.add('completed');
                if (l3) l3.classList.add('completed');
                if (nPend) nPend.classList.add('active');
            } else if (status === 'TRADED' || status === 'FILLED') {
                if (nVal) nVal.classList.add('completed');
                if (l2) l2.classList.add('completed');
                if (nSub) nSub.classList.add('completed');
                if (l3) l3.classList.add('completed');
                if (nPend) nPend.classList.add('completed');
                if (l4) l4.classList.add('completed');
                if (nTerm) nTerm.classList.add('completed');
                if (termLabel) termLabel.textContent = 'TRADED';
            } else if (status === 'REJECTED' || status === 'FAILED') {
                if (nVal) nVal.classList.add('completed');
                if (l2) l2.classList.add('completed');
                if (nSub) nSub.classList.add('completed');
                if (l3) l3.classList.add('completed');
                if (nTerm) nTerm.classList.add('failed');
                if (termLabel) termLabel.textContent = 'REJECTED';
            } else if (status === 'CANCELLED') {
                if (nVal) nVal.classList.add('completed');
                if (l2) l2.classList.add('completed');
                if (nSub) nSub.classList.add('completed');
                if (l3) l3.classList.add('completed');
                if (nPend) nPend.classList.add('completed');
                if (l4) l4.classList.add('completed');
                if (nTerm) nTerm.classList.add('completed');
                if (termLabel) termLabel.textContent = 'CANCELLED';
            } else if (status === 'RECONCILING') {
                if (nVal) nVal.classList.add('completed');
                if (l2) l2.classList.add('completed');
                if (nSub) nSub.classList.add('completed');
                if (l3) l3.classList.add('completed');
                if (nPend) nPend.classList.add('completed');
                if (l4) l4.classList.add('completed');
                if (nTerm) nTerm.classList.add('active');
                if (termLabel) termLabel.textContent = 'RECONCILING';
            }

            // Populate event list
            if (listEl) {
                if (timeline.length === 0) {
                    const item = document.createElement('div');
                    item.className = 'timeline-event-item';
                    item.innerHTML = `
                        <span class="timeline-event-time font-numeric">${draftTime}</span>
                        <span class="badge badge-neutral timeline-event-badge">${status}</span>
                        <span class="timeline-event-desc">Order registered in client repository. Current status: ${status}.</span>
                    `;
                    listEl.appendChild(item);
                } else {
                    timeline.forEach((ev, idx) => {
                        const item = document.createElement('div');
                        item.className = 'timeline-event-item';
                        const tStr = ev.timestamp ? this.formatMsTime(ev.timestamp) : '--:--:--';
                        const toStatus = (ev.to_status || 'UNKNOWN').toUpperCase();
                        const badgeClass = this.getStatusBadgeClass(toStatus);
                        item.innerHTML = `
                            <span class="timeline-event-time font-numeric">${tStr}</span>
                            <span class="${badgeClass} timeline-event-badge">${toStatus}</span>
                            <span class="timeline-event-desc">${idx + 1}. [${ev.from_status} &rarr; ${toStatus}] ${ev.reason || 'FSM state change verified.'}</span>
                        `;
                        listEl.appendChild(item);
                    });
                }
            }
        }

        formatMsTime(ts) {
            const d = new Date(ts);
            if (isNaN(d.getTime())) return ts;
            const hh = String(d.getHours()).padStart(2, '0');
            const mm = String(d.getMinutes()).padStart(2, '0');
            const ss = String(d.getSeconds()).padStart(2, '0');
            const ms = String(d.getMilliseconds()).padStart(3, '0');
            return `${hh}:${mm}:${ss}.${ms}`;
        }

        /* ==========================================================================
           Trade Book Fetch & Rendering
           ========================================================================== */
        async fetchTrades() {
            try {
                const res = await fetch('/api/orders/trades', { credentials: 'same-origin' });
                if (!res.ok) return;
                const json = await res.json();
                this.trades = (json.data && json.data.trades) || [];
                this.updateTradesTimestamp();
                this.renderTrades();
            } catch (err) {
                console.error('[OrderBookController] Fetch trades error:', err);
            }
        }

        updateTradesTimestamp() {
            const now = new Date();
            const timeStr = now.toLocaleTimeString('en-IN', { hour12: false });
            const label = document.getElementById('trades-last-refreshed');
            if (label) label.textContent = timeStr;
        }

        renderTrades() {
            const tbody = document.getElementById('trades-tbody');
            const empty = document.getElementById('trades-empty-state');
            const countEl = document.getElementById('trade-total-count');
            const turnoverEl = document.getElementById('trade-total-turnover');

            if (!tbody) return;

            tbody.innerHTML = '';

            let totalTurnover = 0;
            if (countEl) countEl.textContent = this.trades.length;

            if (this.trades.length === 0) {
                if (empty) empty.classList.remove('hidden');
                if (turnoverEl) turnoverEl.textContent = '₹0.00';
            } else {
                if (empty) empty.classList.add('hidden');

                this.trades.forEach(t => {
                    const qty = t.quantity || 0;
                    const price = t.fill_price || t.price || 0;
                    const tradeVal = qty * price;
                    totalTurnover += tradeVal;

                    const sideUpper = (t.order_side || t.side || 'BUY').toUpperCase();
                    const sideClass = sideUpper === 'BUY' ? 'text-success font-bold' : 'text-danger font-bold';

                    let timeDisplay = '--:--:--';
                    if (t.created_at || t.trade_timestamp) {
                        timeDisplay = this.formatMsTime(t.created_at || t.trade_timestamp);
                    }

                    const tr = document.createElement('tr');
                    tr.innerHTML = `
                        <td class="font-numeric text-muted">${timeDisplay}</td>
                        <td class="font-numeric"><code>${t.trade_id || t.id || 'TRD_...'}</code></td>
                        <td class="font-numeric"><code>${(t.client_order_id || '').substring(0, 12)}...</code></td>
                        <td>
                            <div class="scrip-symbol-block">
                                <span class="font-bold">${t.trading_symbol}</span>
                            </div>
                        </td>
                        <td><span class="badge-segment">${(t.exchange_segment || 'NSE').toUpperCase()}</span></td>
                        <td class="${sideClass}">${sideUpper}</td>
                        <td class="text-right font-numeric font-bold">${qty}</td>
                        <td class="text-right font-numeric">₹${price.toFixed(2)}</td>
                        <td class="text-right font-numeric font-bold">₹${tradeVal.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</td>
                    `;
                    tbody.appendChild(tr);
                });

                if (turnoverEl) {
                    turnoverEl.textContent = `₹${totalTurnover.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
                }
            }
        }
    }

    // Export singleton instance
    window.orderBookController = new OrderBookController();
})(window, document);
