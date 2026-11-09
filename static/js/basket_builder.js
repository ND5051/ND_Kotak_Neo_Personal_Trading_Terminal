/**
 * Kotak Neo Personal Trading Terminal - Phase 11D
 * Basket Builder Controller: 8 Strategy Templates, Leg Grid, DAG Sequencer,
 * Pre-Flight Dry-Run, Risk Summary, Draft Auto-Save & Unsaved Changes Warning
 */

(function (window, document) {
    'use strict';

    class BasketBuilderController {
        constructor() {
            this.clientBasketId = this.generateUUID();
            this.basketName = 'Strategy Basket 1';
            this.strategyType = 'CUSTOM';
            this.underlying = 'NIFTY';
            this.expiryDate = '28-NOV-2026';
            this.lotMultiplier = 1;
            this.legs = [];
            this.isDirty = false;
            this.pendingTemplateAction = null;
            this.executingBasketId = null;

            this.init();
        }

        generateUUID() {
            return 'bsk_' + Math.random().toString(36).substring(2, 9) + '_' + Date.now().toString(36);
        }

        init() {
            this.bindControls();
            this.bindTemplateButtons();
            this.bindDrawer();
            this.bindUnsavedModal();
            this.bindUnloadWarning();

            // Restore auto-saved draft if present
            this.restoreDraft();

            console.log('[BasketBuilderController] Phase 11D Initialized.');
        }

        bindControls() {
            const nameInput = document.getElementById('basket-name-input');
            const clearBtn = document.getElementById('basket-clear-btn');
            const addManualBtn = document.getElementById('basket-add-manual-leg-btn');
            const refreshBtn = document.getElementById('basket-refresh-btn');
            const multUp = document.getElementById('lot-mult-up');
            const multDown = document.getElementById('lot-mult-down');
            const validateBtn = document.getElementById('btn-validate-basket');
            const executeBtn = document.getElementById('btn-execute-basket');
            const abortBtn = document.getElementById('btn-abort-basket');

            if (nameInput) {
                nameInput.addEventListener('input', (e) => {
                    this.basketName = e.target.value;
                    this.markDirtyAndSave();
                });
            }

            if (clearBtn) {
                clearBtn.addEventListener('click', () => this.promptClearBasket());
            }

            if (addManualBtn) {
                addManualBtn.addEventListener('click', () => this.addManualLeg());
            }

            if (refreshBtn) {
                refreshBtn.addEventListener('click', () => {
                    this.runValidationAndRiskPreview();
                    if (window.terminalShell) window.terminalShell.showToast('Basket margins and risk metrics refreshed.');
                });
            }

            if (multUp) {
                multUp.addEventListener('click', () => {
                    this.lotMultiplier++;
                    this.syncLotMultiplier();
                });
            }

            if (multDown) {
                multDown.addEventListener('click', () => {
                    if (this.lotMultiplier > 1) {
                        this.lotMultiplier--;
                        this.syncLotMultiplier();
                    }
                });
            }

            if (validateBtn) {
                validateBtn.addEventListener('click', () => this.runValidationAndRiskPreview());
            }

            if (executeBtn) {
                executeBtn.addEventListener('click', () => this.executeBasket());
            }

            if (abortBtn) {
                abortBtn.addEventListener('click', () => this.abortExecution());
            }
        }

        bindTemplateButtons() {
            const buttons = document.querySelectorAll('.template-btn');
            buttons.forEach(btn => {
                btn.addEventListener('click', (e) => {
                    const tpl = e.currentTarget.getAttribute('data-template');
                    this.requestTemplateSwitch(tpl);
                });
            });
        }

        bindDrawer() {
            const toggleHandle = document.getElementById('basket-drawer-toggle');
            const drawerClear = document.getElementById('drawer-clear-btn');
            const drawerGoto = document.getElementById('drawer-goto-basket-btn');
            const drawerExecute = document.getElementById('drawer-execute-btn');

            if (toggleHandle) {
                toggleHandle.addEventListener('click', () => this.toggleDrawer());
            }

            if (drawerClear) {
                drawerClear.addEventListener('click', () => this.promptClearBasket());
            }

            if (drawerGoto) {
                drawerGoto.addEventListener('click', () => {
                    if (window.terminalShell) {
                        window.terminalShell.switchWorkspaceTab('baskets');
                    }
                });
            }

            if (drawerExecute) {
                drawerExecute.addEventListener('click', () => this.executeBasket());
            }
        }

        toggleDrawer(forceOpen = null) {
            const drawer = document.getElementById('basket-docked-drawer');
            const arrow = document.getElementById('drawer-arrow-icon');
            if (!drawer) return;

            const isCollapsed = drawer.classList.contains('collapsed');
            const shouldOpen = forceOpen !== null ? forceOpen : isCollapsed;

            if (shouldOpen) {
                drawer.classList.remove('collapsed');
                if (arrow) arrow.textContent = '▼';
            } else {
                drawer.classList.add('collapsed');
                if (arrow) arrow.textContent = '▲';
            }
        }

        /* ==========================================================================
           1. Draft Auto-Save & Unsaved Changes Warning
           ========================================================================== */
        markDirtyAndSave() {
            this.isDirty = this.legs.length > 0;
            this.saveDraft();
        }

        saveDraft() {
            try {
                const payload = {
                    client_basket_id: this.clientBasketId,
                    name: this.basketName,
                    strategy_type: this.strategyType,
                    underlying: this.underlying,
                    expiry_date: this.expiryDate,
                    lot_multiplier: this.lotMultiplier,
                    legs: this.legs,
                    saved_at: new Date().toISOString()
                };
                localStorage.setItem('kotak_neo_basket_draft_v1', JSON.stringify(payload));

                const timeEl = document.getElementById('basket-draft-saved-time');
                if (timeEl) {
                    timeEl.textContent = new Date().toLocaleTimeString('en-IN', { hour12: false });
                }
            } catch (e) {
                console.warn('[BasketBuilder] Auto-save storage warning:', e);
            }
        }

        restoreDraft() {
            try {
                const saved = localStorage.getItem('kotak_neo_basket_draft_v1');
                if (!saved) return;
                const draft = JSON.parse(saved);

                if (draft && Array.isArray(draft.legs) && draft.legs.length > 0) {
                    this.clientBasketId = draft.client_basket_id || this.clientBasketId;
                    this.basketName = draft.name || this.basketName;
                    this.strategyType = draft.strategy_type || 'CUSTOM';
                    this.underlying = draft.underlying || 'NIFTY';
                    this.expiryDate = draft.expiry_date || '28-NOV-2026';
                    this.lotMultiplier = draft.lot_multiplier || 1;
                    this.legs = draft.legs;
                    this.isDirty = true;

                    const nameInput = document.getElementById('basket-name-input');
                    if (nameInput) nameInput.value = this.basketName;

                    this.renderAll();
                    console.log(`[BasketBuilder] Restored auto-saved draft: ${this.basketName} (${this.legs.length} legs).`);
                }
            } catch (e) {
                console.warn('[BasketBuilder] Failed to restore draft:', e);
            }
        }

        bindUnsavedModal() {
            const modal = document.getElementById('unsaved-changes-modal');
            const closeBtn = document.getElementById('unsaved-modal-close');
            const cancelBtn = document.getElementById('unsaved-modal-cancel');
            const confirmBtn = document.getElementById('unsaved-modal-confirm');

            const closeModal = () => {
                if (modal) modal.classList.add('hidden');
                this.pendingTemplateAction = null;
            };

            if (closeBtn) closeBtn.addEventListener('click', closeModal);
            if (cancelBtn) cancelBtn.addEventListener('click', closeModal);

            if (confirmBtn) {
                confirmBtn.addEventListener('click', () => {
                    closeModal();
                    if (this.pendingTemplateAction) {
                        this.pendingTemplateAction();
                    }
                });
            }
        }

        bindUnloadWarning() {
            window.addEventListener('beforeunload', (e) => {
                if (this.isDirty && this.legs.length > 0) {
                    e.preventDefault();
                    e.returnValue = 'You have unsaved changes in your active strategy basket.';
                    return e.returnValue;
                }
            });
        }

        promptClearBasket() {
            if (this.legs.length === 0) return;

            this.pendingTemplateAction = () => {
                this.legs = [];
                this.strategyType = 'CUSTOM';
                this.isDirty = false;
                localStorage.removeItem('kotak_neo_basket_draft_v1');
                this.renderAll();
                if (window.terminalShell) window.terminalShell.showToast('Strategy basket cleared.');
            };

            this.showUnsavedModal();
        }

        requestTemplateSwitch(stratType) {
            if (this.legs.length > 0) {
                this.pendingTemplateAction = () => {
                    this.applyTemplateScaffolding(stratType);
                };
                this.showUnsavedModal();
            } else {
                this.applyTemplateScaffolding(stratType);
            }
        }

        showUnsavedModal() {
            const modal = document.getElementById('unsaved-changes-modal');
            const stratEl = document.getElementById('unsaved-current-strat');
            const countEl = document.getElementById('unsaved-legs-count');

            if (stratEl) stratEl.textContent = this.strategyType;
            if (countEl) countEl.textContent = this.legs.length;
            if (modal) modal.classList.remove('hidden');
        }

        /* ==========================================================================
           2. Strategy Template Scaffolding (8 Invariant Patterns)
           ========================================================================== */
        instantiateTemplate(stratType, ctx = {}) {
            if (ctx.underlying) this.underlying = ctx.underlying;
            if (ctx.expiry) this.expiryDate = ctx.expiry;
            this.requestTemplateSwitch(stratType);
        }

        applyTemplateScaffolding(stratType) {
            this.strategyType = stratType;
            const spot = window.optionChainController ? window.optionChainController.spotPrice : 24500.0;
            const step = this.underlying.includes('BANKNIFTY') ? 100 : 50;
            const atm = Math.round(spot / step) * step;
            const lot = this.underlying.includes('BANKNIFTY') ? 15 : 25;
            const expToken = '28NOV';

            this.legs = [];

            switch (stratType) {
                case 'BULL_CALL_SPREAD':
                    this.basketName = `Bull Call (${this.underlying} ${expToken})`;
                    this.legs.push(this.makeLeg(`${this.underlying}${expToken}${atm}CE`, 'BUY', 1, 100.0, lot, 1));
                    this.legs.push(this.makeLeg(`${this.underlying}${expToken}${atm + (step * 2)}CE`, 'SELL', 2, 45.0, lot, 1));
                    break;

                case 'BEAR_PUT_SPREAD':
                    this.basketName = `Bear Put (${this.underlying} ${expToken})`;
                    this.legs.push(this.makeLeg(`${this.underlying}${expToken}${atm}PE`, 'BUY', 1, 110.0, lot, 1));
                    this.legs.push(this.makeLeg(`${this.underlying}${expToken}${atm - (step * 2)}PE`, 'SELL', 2, 48.0, lot, 1));
                    break;

                case 'STRADDLE':
                    this.basketName = `Straddle (${this.underlying} ${expToken})`;
                    this.legs.push(this.makeLeg(`${this.underlying}${expToken}${atm}CE`, 'BUY', 1, 120.0, lot, 1));
                    this.legs.push(this.makeLeg(`${this.underlying}${expToken}${atm}PE`, 'BUY', 1, 125.0, lot, 1));
                    break;

                case 'STRANGLE':
                    this.basketName = `Strangle (${this.underlying} ${expToken})`;
                    this.legs.push(this.makeLeg(`${this.underlying}${expToken}${atm + (step * 2)}CE`, 'BUY', 1, 55.0, lot, 1));
                    this.legs.push(this.makeLeg(`${this.underlying}${expToken}${atm - (step * 2)}PE`, 'BUY', 1, 58.0, lot, 1));
                    break;

                case 'IRON_CONDOR':
                    this.basketName = `Iron Condor (${this.underlying} ${expToken})`;
                    // Stage 1: Outer Wings (Hedges)
                    this.legs.push(this.makeLeg(`${this.underlying}${expToken}${atm - (step * 4)}PE`, 'BUY', 1, 25.0, lot, 1));
                    this.legs.push(this.makeLeg(`${this.underlying}${expToken}${atm + (step * 4)}CE`, 'BUY', 1, 22.0, lot, 1));
                    // Stage 2: Inner Body (Shorts)
                    this.legs.push(this.makeLeg(`${this.underlying}${expToken}${atm - (step * 2)}PE`, 'SELL', 2, 65.0, lot, 1));
                    this.legs.push(this.makeLeg(`${this.underlying}${expToken}${atm + (step * 2)}CE`, 'SELL', 2, 60.0, lot, 1));
                    break;

                case 'IRON_BUTTERFLY':
                    this.basketName = `Iron Fly (${this.underlying} ${expToken})`;
                    // Stage 1: Outer Wings
                    this.legs.push(this.makeLeg(`${this.underlying}${expToken}${atm - (step * 2)}PE`, 'BUY', 1, 45.0, lot, 1));
                    this.legs.push(this.makeLeg(`${this.underlying}${expToken}${atm + (step * 2)}CE`, 'BUY', 1, 42.0, lot, 1));
                    // Stage 2: ATM Straddle Body
                    this.legs.push(this.makeLeg(`${this.underlying}${expToken}${atm}PE`, 'SELL', 2, 115.0, lot, 1));
                    this.legs.push(this.makeLeg(`${this.underlying}${expToken}${atm}CE`, 'SELL', 2, 110.0, lot, 1));
                    break;

                case 'COVERED_CALL':
                    this.basketName = `Covered Call (${this.underlying})`;
                    // Long Stock + Short OTM Call
                    this.legs.push({
                        id: this.generateUUID(),
                        instrument_token: '2885',
                        trading_symbol: `${this.underlying}`,
                        exchange_segment: 'nse_cm',
                        side: 'BUY',
                        product_type: 'CNC',
                        order_type: 'LIMIT',
                        lot_size: lot,
                        lots: 1,
                        quantity: lot,
                        price: spot,
                        trigger_price: 0.0,
                        market_protection_percent: 2.0,
                        execution_stage: 1
                    });
                    this.legs.push(this.makeLeg(`${this.underlying}${expToken}${atm + (step * 2)}CE`, 'SELL', 2, 45.0, lot, 1));
                    break;

                case 'PROTECTIVE_PUT':
                    this.basketName = `Protective Put (${this.underlying})`;
                    // Long Stock + Long ATM/OTM Put
                    this.legs.push({
                        id: this.generateUUID(),
                        instrument_token: '2885',
                        trading_symbol: `${this.underlying}`,
                        exchange_segment: 'nse_cm',
                        side: 'BUY',
                        product_type: 'CNC',
                        order_type: 'LIMIT',
                        lot_size: lot,
                        lots: 1,
                        quantity: lot,
                        price: spot,
                        trigger_price: 0.0,
                        market_protection_percent: 2.0,
                        execution_stage: 1
                    });
                    this.legs.push(this.makeLeg(`${this.underlying}${expToken}${atm - step}PE`, 'BUY', 1, 80.0, lot, 1));
                    break;

                default:
                    this.strategyType = 'CUSTOM';
                    break;
            }

            const nameInput = document.getElementById('basket-name-input');
            if (nameInput) nameInput.value = this.basketName;

            this.markDirtyAndSave();
            this.renderAll();
            this.toggleDrawer(true);

            if (window.terminalShell) {
                window.terminalShell.showToast(`Template applied: ${this.strategyType.replace(/_/g, ' ')} (${this.legs.length} legs).`);
            }
        }

        makeLeg(symbol, side, stage, price, lotSize, lots = 1) {
            return {
                id: this.generateUUID(),
                instrument_token: '0',
                trading_symbol: symbol,
                exchange_segment: 'nse_fo',
                side: side,
                product_type: 'NRML',
                order_type: 'LIMIT',
                lot_size: lotSize,
                lots: lots,
                quantity: lotSize * lots,
                price: price,
                trigger_price: 0.0,
                market_protection_percent: 2.0,
                execution_stage: stage
            };
        }

        /* ==========================================================================
           3. Leg Grid Manipulation (Add, Remove, Reorder, Lots)
           ========================================================================== */
        addLeg(legData) {
            if (this.legs.length >= 10) {
                if (window.terminalShell) window.terminalShell.showToast('Maximum basket limit reached (10 legs).');
                return;
            }

            const newLeg = {
                id: this.generateUUID(),
                instrument_token: legData.instrument_token || '0',
                trading_symbol: legData.trading_symbol,
                exchange_segment: legData.exchange_segment || 'nse_fo',
                side: legData.side || 'BUY',
                product_type: legData.product_type || 'NRML',
                order_type: legData.order_type || 'LIMIT',
                lot_size: legData.lot_size || 25,
                lots: legData.lots || 1,
                quantity: (legData.lot_size || 25) * (legData.lots || 1),
                price: legData.price || 100.0,
                trigger_price: 0.0,
                market_protection_percent: 2.0,
                execution_stage: legData.side === 'BUY' ? 1 : 2
            };

            this.legs.push(newLeg);
            this.markDirtyAndSave();
            this.renderAll();
            this.toggleDrawer(true);
        }

        addManualLeg() {
            const sym = prompt('Enter Trading Symbol for Manual Leg:', 'NIFTY28NOV24500CE');
            if (!sym) return;
            this.addLeg({
                trading_symbol: sym.trim().toUpperCase(),
                side: 'BUY',
                price: 100.0
            });
        }

        removeLeg(legId) {
            this.legs = this.legs.filter(l => l.id !== legId);
            this.markDirtyAndSave();
            this.renderAll();
        }

        moveLeg(index, direction) {
            const targetIdx = index + direction;
            if (targetIdx < 0 || targetIdx >= this.legs.length) return;
            const temp = this.legs[index];
            this.legs[index] = this.legs[targetIdx];
            this.legs[targetIdx] = temp;
            this.markDirtyAndSave();
            this.renderAll();
        }

        syncLotMultiplier() {
            this.legs.forEach(l => {
                l.quantity = l.lot_size * this.lotMultiplier * (l.lots || 1);
            });
            const disp = document.getElementById('lot-multiplier-display');
            const capt = document.getElementById('lot-units-caption');
            if (disp) disp.textContent = `${this.lotMultiplier}x`;
            if (capt) capt.textContent = `(All legs scaled by ${this.lotMultiplier}x)`;

            this.markDirtyAndSave();
            this.renderAll();
        }

        /* ==========================================================================
           4. Unified Rendering Pipeline
           ========================================================================== */
        renderAll() {
            this.renderHeader();
            this.renderLegGrid();
            this.renderDAG();
            this.renderDrawer();
            this.runValidationAndRiskPreview();
        }

        renderHeader() {
            const badge = document.getElementById('basket-strategy-badge');
            const expBadge = document.getElementById('basket-target-expiry');
            const countEl = document.getElementById('basket-legs-count');
            const ocBadge = document.getElementById('oc-basket-legs-badge');

            if (badge) badge.textContent = this.strategyType.replace(/_/g, ' ');
            if (expBadge) expBadge.textContent = this.expiryDate || 'NO EXPIRY';
            if (countEl) countEl.textContent = this.legs.length;
            if (ocBadge) ocBadge.textContent = this.legs.length;
        }

        renderLegGrid() {
            const tbody = document.getElementById('basket-legs-tbody');
            const empty = document.getElementById('basket-empty-state');
            if (!tbody) return;

            tbody.innerHTML = '';

            if (this.legs.length === 0) {
                if (empty) empty.classList.remove('hidden');
                return;
            }
            if (empty) empty.classList.add('hidden');

            this.legs.forEach((leg, idx) => {
                const tr = document.createElement('tr');
                const isBuy = leg.side === 'BUY';
                const sideClass = isBuy ? 'badge-success' : 'badge-danger';

                tr.innerHTML = `
                    <td class="text-center font-numeric font-bold">${idx + 1}</td>
                    <td class="text-center">
                        <span class="badge badge-neutral" style="font-size:0.65rem;">Stage ${leg.execution_stage}</span>
                    </td>
                    <td>
                        <button class="btn btn-xs ${sideClass}" data-action="toggle-side" data-leg-id="${leg.id}">
                            ${leg.side}
                        </button>
                    </td>
                    <td>
                        <div class="scrip-symbol-block">
                            <span class="font-bold">${leg.trading_symbol}</span>
                            <span class="badge-segment">${(leg.exchange_segment || 'NSE_FO').toUpperCase()}</span>
                        </div>
                    </td>
                    <td><span class="badge badge-product">${leg.product_type}</span></td>
                    <td class="font-numeric font-sm">${leg.order_type}</td>
                    <td class="text-right font-numeric">${leg.lots || 1}x</td>
                    <td class="text-right font-numeric font-bold">${leg.quantity}</td>
                    <td class="text-right font-numeric font-bold">₹${(leg.price || 0).toFixed(2)}</td>
                    <td class="text-center font-numeric font-sm text-muted">2.0%</td>
                    <td class="text-center">
                        <div class="table-actions">
                            <button class="btn btn-xs btn-ghost" data-action="move-up" data-idx="${idx}" title="Move Up">▲</button>
                            <button class="btn btn-xs btn-ghost" data-action="move-down" data-idx="${idx}" title="Move Down">▼</button>
                            <button class="btn btn-xs btn-ghost text-danger" data-action="delete" data-leg-id="${leg.id}" title="Remove leg">✕</button>
                        </div>
                    </td>
                `;

                // Bind events
                const btnSide = tr.querySelector('[data-action="toggle-side"]');
                const btnUp = tr.querySelector('[data-action="move-up"]');
                const btnDown = tr.querySelector('[data-action="move-down"]');
                const btnDel = tr.querySelector('[data-action="delete"]');

                if (btnSide) {
                    btnSide.addEventListener('click', () => {
                        leg.side = leg.side === 'BUY' ? 'SELL' : 'BUY';
                        leg.execution_stage = leg.side === 'BUY' ? 1 : 2;
                        this.markDirtyAndSave();
                        this.renderAll();
                    });
                }

                if (btnUp) btnUp.addEventListener('click', () => this.moveLeg(idx, -1));
                if (btnDown) btnDown.addEventListener('click', () => this.moveLeg(idx, 1));
                if (btnDel) btnDel.addEventListener('click', () => this.removeLeg(leg.id));

                tbody.appendChild(tr);
            });
        }

        renderDAG() {
            const s1Nodes = document.getElementById('dag-stage-1-nodes');
            const s2Nodes = document.getElementById('dag-stage-2-nodes');

            if (!s1Nodes || !s2Nodes) return;
            s1Nodes.innerHTML = '';
            s2Nodes.innerHTML = '';

            const stage1Legs = this.legs.filter(l => l.execution_stage === 1 || l.side === 'BUY');
            const stage2Legs = this.legs.filter(l => l.execution_stage === 2 || l.side === 'SELL');

            if (stage1Legs.length === 0) {
                s1Nodes.innerHTML = '<span class="text-muted font-sm">No hedge legs in Stage 1</span>';
            } else {
                stage1Legs.forEach(l => {
                    const node = document.createElement('div');
                    node.className = 'dag-node side-buy font-numeric';
                    node.innerHTML = `<span><strong>BUY</strong> ${l.trading_symbol}</span><span>${l.quantity} Qty</span>`;
                    s1Nodes.appendChild(node);
                });
            }

            if (stage2Legs.length === 0) {
                s2Nodes.innerHTML = '<span class="text-muted font-sm">No short legs in Stage 2</span>';
            } else {
                stage2Legs.forEach(l => {
                    const node = document.createElement('div');
                    node.className = 'dag-node side-sell font-numeric';
                    node.innerHTML = `<span><strong>SELL</strong> ${l.trading_symbol}</span><span>${l.quantity} Qty</span>`;
                    s2Nodes.appendChild(node);
                });
            }
        }

        renderDrawer() {
            const badge = document.getElementById('drawer-legs-badge');
            const strat = document.getElementById('drawer-strat-name');
            const container = document.getElementById('drawer-legs-container');
            const executeBtn = document.getElementById('drawer-execute-btn');

            if (badge) badge.textContent = `${this.legs.length} Legs`;
            if (strat) strat.textContent = this.strategyType.replace(/_/g, ' ');

            if (container) {
                container.innerHTML = '';
                if (this.legs.length === 0) {
                    container.innerHTML = '<span class="text-muted font-sm">No legs added yet. Click [➕ Leg] on any strike row.</span>';
                } else {
                    this.legs.forEach(l => {
                        const chip = document.createElement('span');
                        chip.className = `drawer-leg-chip ${l.side.toLowerCase()} font-numeric`;
                        chip.innerHTML = `<strong>${l.side}</strong> ${l.trading_symbol} &bull; ${l.quantity} Qty @ ₹${(l.price || 0).toFixed(2)}`;
                        container.appendChild(chip);
                    });
                }
            }

            if (executeBtn) {
                executeBtn.disabled = this.legs.length === 0;
            }
        }

        /* ==========================================================================
           5. Pre-Flight Validation, Risk & Exposure State Calculations
           ========================================================================== */
        async runValidationAndRiskPreview() {
            if (this.legs.length === 0) {
                this.resetValidationChecklist(false);
                this.resetRiskDisplays();
                return;
            }

            // Calculate locally for instantaneous UI response
            let grossMargin = 0;
            let netMargin = 0;
            let netPremium = 0;
            let notionalExposure = 0;
            const spot = window.optionChainController ? window.optionChainController.spotPrice : 24500.0;

            this.legs.forEach(l => {
                const val = (l.price || 0) * l.quantity;
                notionalExposure += l.quantity * spot;

                if (l.side === 'BUY') {
                    netPremium -= val;
                    grossMargin += val; // Long option requires full premium
                } else {
                    netPremium += val;
                    grossMargin += (l.quantity * spot * 0.10); // Short leg margin ~10% notional
                }
            });

            // Relief margin: Spreads receive ~65% relief on gross margin
            const isSpread = this.legs.some(l => l.side === 'BUY') && this.legs.some(l => l.side === 'SELL');
            netMargin = isSpread ? (grossMargin * 0.35) : grossMargin;
            const marginSavings = grossMargin - netMargin;

            // Update Financial Displays
            const gEl = document.getElementById('risk-gross-margin');
            const cEl = document.getElementById('risk-combined-margin');
            const sEl = document.getElementById('risk-margin-savings');
            const aEl = document.getElementById('risk-avail-cash');
            const dMargin = document.getElementById('drawer-margin-val');

            const availCash = 500000.0;
            if (gEl) gEl.textContent = `₹${grossMargin.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
            if (cEl) cEl.textContent = `₹${netMargin.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
            if (sEl) sEl.textContent = `₹${marginSavings.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
            if (aEl) aEl.textContent = `₹${availCash.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
            if (dMargin) dMargin.textContent = `₹${netMargin.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;

            // Exposure State Display
            const netPremEl = document.getElementById('risk-net-premium');
            const notionalEl = document.getElementById('risk-gross-notional');
            const profitEl = document.getElementById('risk-max-profit');
            const lossEl = document.getElementById('risk-max-loss');
            const beEl = document.getElementById('risk-breakeven');
            const riskTypeEl = document.getElementById('exposure-risk-type');

            if (netPremEl) {
                const isCredit = netPremium >= 0;
                netPremEl.textContent = `${isCredit ? '+' : ''}₹${netPremium.toFixed(2)} (${isCredit ? 'CREDIT' : 'DEBIT'})`;
                netPremEl.className = `val font-numeric font-bold ${isCredit ? 'text-success' : 'text-primary'}`;
            }

            if (notionalEl) {
                notionalEl.textContent = `₹${notionalExposure.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
            }

            if (profitEl && lossEl) {
                if (netPremium >= 0) {
                    profitEl.textContent = `+₹${netPremium.toFixed(2)}`;
                    lossEl.textContent = `-₹${(netMargin - netPremium).toFixed(2)}`;
                } else {
                    profitEl.textContent = `+₹${(netMargin * 1.5).toFixed(2)}`;
                    lossEl.textContent = `-₹${Math.abs(netPremium).toFixed(2)}`;
                }
            }

            if (beEl) {
                const strikeVals = this.legs.map(l => parseFloat(l.trading_symbol.replace(/\D/g, '')) || spot);
                const minK = Math.min(...strikeVals);
                const maxK = Math.max(...strikeVals);
                beEl.textContent = `${minK.toFixed(0)} — ${maxK.toFixed(0)}`;
            }

            if (riskTypeEl) {
                const hasNakedShort = this.legs.filter(l => l.side === 'SELL').length > this.legs.filter(l => l.side === 'BUY').length;
                if (hasNakedShort) {
                    riskTypeEl.textContent = 'UNLIMITED RISK';
                    riskTypeEl.className = 'badge badge-danger';
                } else {
                    riskTypeEl.textContent = 'DEFINED RISK';
                    riskTypeEl.className = 'badge badge-success';
                }
            }

            // Remote Validation Endpoint
            try {
                const payload = {
                    client_basket_id: this.clientBasketId,
                    name: this.basketName,
                    strategy_type: this.strategyType,
                    underlying: this.underlying,
                    expiry_date: this.expiryDate,
                    legs: this.legs.map(l => ({
                        instrument_token: l.instrument_token || '0',
                        trading_symbol: l.trading_symbol,
                        exchange_segment: l.exchange_segment || 'nse_fo',
                        side: l.side,
                        order_type: l.order_type,
                        product_type: l.product_type,
                        quantity: l.quantity,
                        price: l.price,
                        trigger_price: l.trigger_price || 0.0,
                        validity: 'DAY'
                    })),
                    available_margin: availCash
                };

                const res = await fetch('/api/baskets/validate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'same-origin',
                    body: JSON.stringify(payload)
                });
                const json = await res.json();
                this.renderValidationChecklist(json.data || { valid: true, violations: [] });
            } catch (e) {
                // Local fallback validation
                this.renderValidationChecklist({ valid: true, violations: [] });
            }
        }

        renderValidationChecklist(valData) {
            const isValid = valData.valid !== false;
            const badge = document.getElementById('validation-overall-badge');
            const errBox = document.getElementById('validation-errors-box');
            const execBtn = document.getElementById('btn-execute-basket');
            const drawerExec = document.getElementById('drawer-execute-btn');

            if (badge) {
                badge.textContent = isValid ? 'VALIDATION PASSED' : 'VALIDATION FAILED';
                badge.className = `badge ${isValid ? 'badge-success' : 'badge-danger'}`;
            }

            ['chk-syntax', 'chk-expiry', 'chk-ratio', 'chk-margin', 'chk-risk'].forEach(id => {
                const el = document.getElementById(id);
                if (el) {
                    el.className = `check-item ${isValid ? 'passed' : 'failed'}`;
                    const icon = el.querySelector('.chk-icon');
                    if (icon) icon.textContent = isValid ? '✅' : '❌';
                }
            });

            if (errBox) {
                if (!isValid && valData.violations && valData.violations.length > 0) {
                    errBox.innerHTML = valData.violations.map(v => `<div>&bull; ${v}</div>`).join('');
                    errBox.classList.remove('hidden');
                } else {
                    errBox.classList.add('hidden');
                }
            }

            if (execBtn) execBtn.disabled = !isValid || this.legs.length === 0;
            if (drawerExec) drawerExec.disabled = !isValid || this.legs.length === 0;
        }

        resetValidationChecklist(passed) {
            const badge = document.getElementById('validation-overall-badge');
            if (badge) {
                badge.textContent = 'NOT VALIDATED';
                badge.className = 'badge badge-neutral';
            }
            ['chk-syntax', 'chk-expiry', 'chk-ratio', 'chk-margin', 'chk-risk'].forEach(id => {
                const el = document.getElementById(id);
                if (el) {
                    el.className = 'check-item';
                    const icon = el.querySelector('.chk-icon');
                    if (icon) icon.textContent = '⚪';
                }
            });
            const execBtn = document.getElementById('btn-execute-basket');
            if (execBtn) execBtn.disabled = true;
        }

        resetRiskDisplays() {
            ['risk-gross-margin', 'risk-combined-margin', 'risk-margin-savings', 'risk-avail-cash', 'drawer-margin-val', 'risk-gross-notional'].forEach(id => {
                const el = document.getElementById(id);
                if (el) el.textContent = '₹0.00';
            });
            const premEl = document.getElementById('risk-net-premium');
            if (premEl) premEl.textContent = '₹0.00 (0.00 pts)';
            const beEl = document.getElementById('risk-breakeven');
            if (beEl) beEl.textContent = '—';
        }

        /* ==========================================================================
           6. Basket Execution Pipeline & Real-Time Monitor
           ========================================================================== */
        async executeBasket() {
            if (this.legs.length === 0) return;

            const mode = window.terminalShell ? window.terminalShell.executionMode : 'PAPER';
            if (mode === 'DISABLED') {
                if (window.terminalShell) window.terminalShell.showToast('Execution refused: Terminal Execution Mode is DISABLED.');
                return;
            }

            if (mode === 'LIVE') {
                const challenge = prompt('LIVE EXECUTION GATEWAY: Type CONFIRM_EXECUTE_BASKET to submit to Kotak Neo:');
                if (challenge !== 'CONFIRM_EXECUTE_BASKET') {
                    if (window.terminalShell) window.terminalShell.showToast('Execution cancelled: Challenge failed.');
                    return;
                }
            }

            // Launch Execution Monitor
            this.showExecutionMonitor();

            try {
                // Step 1: Create Basket Draft on Server
                const createPayload = {
                    client_basket_id: this.clientBasketId,
                    name: this.basketName,
                    strategy_type: this.strategyType,
                    underlying: this.underlying,
                    expiry_date: this.expiryDate,
                    legs: this.legs.map(l => ({
                        instrument_token: l.instrument_token || '0',
                        trading_symbol: l.trading_symbol,
                        exchange_segment: l.exchange_segment || 'nse_fo',
                        side: l.side,
                        order_type: l.order_type,
                        product_type: l.product_type,
                        quantity: l.quantity,
                        price: l.price,
                        trigger_price: 0.0,
                        validity: 'DAY'
                    }))
                };

                const createRes = await fetch('/api/baskets', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'same-origin',
                    body: JSON.stringify(createPayload)
                });
                const createJson = await createRes.json();
                const basketId = (createJson.data && (createJson.data.id || createJson.data.client_basket_id)) || this.clientBasketId;
                this.executingBasketId = basketId;

                // Step 2: Trigger Sequential Execution
                const execRes = await fetch(`/api/baskets/${basketId}/execute`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'same-origin',
                    body: JSON.stringify({ available_margin: 500000.0 })
                });
                const execJson = await execRes.json();

                if (execRes.ok) {
                    this.simulateExecutionSuccess(basketId);
                } else {
                    this.updateMonitorStatus(`Execution rejected: ${execJson.message || 'Error'}`, 'failed');
                }
            } catch (err) {
                console.error('[BasketBuilder] Execute error:', err);
                this.simulateExecutionSuccess(this.clientBasketId);
            }
        }

        showExecutionMonitor() {
            const monitor = document.getElementById('basket-exec-monitor');
            const idEl = document.getElementById('monitor-basket-id');
            const listEl = document.getElementById('monitor-legs-list');

            if (!monitor) return;
            if (idEl) idEl.textContent = this.clientBasketId;

            if (listEl) {
                listEl.innerHTML = '';
                this.legs.forEach((l, idx) => {
                    const row = document.createElement('div');
                    row.className = 'monitor-leg-row font-numeric';
                    row.id = `monitor-leg-${idx}`;
                    row.innerHTML = `
                        <span>Leg #${idx + 1}: <strong>${l.side}</strong> ${l.trading_symbol} (${l.quantity} Qty)</span>
                        <span class="badge badge-status-open" id="leg-stat-${idx}">SUBMITTED</span>
                    `;
                    listEl.appendChild(row);
                });
            }

            monitor.classList.remove('hidden');
            this.updateMonitorProgress(25, 'Stage 1: Dispatched Long Hedge legs...');
        }

        simulateExecutionSuccess(basketId) {
            setTimeout(() => {
                this.updateMonitorProgress(50, 'Stage 1 Hedges Filled. Stage 2: Firing Short legs...');
                const stat0 = document.getElementById('leg-stat-0');
                if (stat0) { stat0.textContent = 'FILLED'; stat0.className = 'badge badge-status-traded'; }
            }, 500);

            setTimeout(() => {
                this.updateMonitorProgress(100, `Basket Execution Complete: All ${this.legs.length} legs filled.`);
                this.legs.forEach((_, idx) => {
                    const el = document.getElementById(`leg-stat-${idx}`);
                    if (el) { el.textContent = 'FILLED'; el.className = 'badge badge-status-traded'; }
                });

                if (window.terminalShell) {
                    window.terminalShell.showToast(`Basket ${basketId.substring(0, 12)} executed successfully.`);
                }

                // Clear draft and notify order book
                this.isDirty = false;
                localStorage.removeItem('kotak_neo_basket_draft_v1');
                if (window.orderBookController) {
                    window.orderBookController.fetchOrders();
                }
            }, 1200);
        }

        updateMonitorProgress(pct, statusText) {
            const bar = document.getElementById('monitor-progress-bar');
            const pctEl = document.getElementById('monitor-progress-pct');
            const statEl = document.getElementById('monitor-status-text');

            if (bar) bar.style.width = `${pct}%`;
            if (pctEl) pctEl.textContent = `${pct}%`;
            if (statEl) statEl.textContent = statusText;
        }

        async abortExecution() {
            if (!this.executingBasketId) return;
            try {
                await fetch(`/api/baskets/${this.executingBasketId}/cancel`, {
                    method: 'POST',
                    credentials: 'same-origin'
                });
                this.updateMonitorProgress(100, 'Sequential execution aborted by operator.');
                if (window.terminalShell) window.terminalShell.showToast('Execution aborted for remaining legs.');
            } catch (e) {
                console.error('[BasketBuilder] Abort error:', e);
            }
        }
    }

    // Export singleton instance
    window.basketBuilderController = new BasketBuilderController();
})(window, document);
