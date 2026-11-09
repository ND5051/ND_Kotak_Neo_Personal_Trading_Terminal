# Kotak Neo Personal Trading Terminal
## Live User Acceptance Testing (UAT) Checklist & Sign-Off Matrix

**Document Version:** 1.0.0  
**Phase:** Phase 12B (Live Equity, F&O & Basket Order UAT)  
**Target Milestone:** Milestone M7 (Production Hardening & Live Operational Readiness)  
**Status:** Pre-Execution Verification Standard  
**Date:** 2026-11-09  

---

## 1. Executive Summary

This checklist establishes the mandatory, step-by-step verification protocol required before taking live capital into the market with the **Kotak Neo Personal Trading Terminal**. Every operator must execute and sign off on each item in sequence to verify that safety guards, execution controls, state reconciliation, and risk boundaries function with zero discrepancies.

All tests conform to the **Project Constitution**:
- **Human-Initiated Only:** All actions must be triggered explicitly by the operator.
- **Defensive Execution:** Pure market orders are prohibited; Market Protection (MP) collars are enforced.
- **The Golden Rule:** Unconfirmed orders must render as `RECONCILING`. Absence of data renders as `—`.
- **Zero Dummy Data:** All live tests interact directly with broker API endpoints and live exchange matching engines.

---

## 2. Master Verification Checklist

```
+---------------------------------------------------------------------------------------------------------+
|                                  MASTER LIVE UAT CHECKLIST MATRIX                                       |
+---------------------------------------------------------------------------------------------------------+
| [ ] 1. DISABLED Mode Invariant Verification                                                             |
|     [ ] 1.1 Header Execution Mode badge displays DISABLED (Red).                                       |
|     [ ] 1.2 Order Ticket submit button is disabled with lock banner.                                    |
|     [ ] 1.3 Direct API call POST /api/orders/place returns HTTP 403 Forbidden.                          |
|     [ ] 1.4 Basket Builder submit button is disabled with warning indicator.                             |
|     [ ] 1.5 Direct API call POST /api/baskets/<id>/execute returns HTTP 403 Forbidden.                  |
+---------------------------------------------------------------------------------------------------------+
| [ ] 2. PAPER Mode Simulation Verification                                                               |
|     [ ] 2.1 Switch Execution Mode to PAPER via header modal (Alt+E).                                    |
|     [ ] 2.2 Header displays PAPER badge (Amber).                                                        |
|     [ ] 2.3 Order Ticket displays PAPER execution notice.                                               |
|     [ ] 2.4 Place 1 share INFY BUY Limit order @ ₹1,500.00 in PAPER mode.                              |
|     [ ] 2.5 Verify order appears in Order Book as TRADED without broker wire submission.                |
|     [ ] 2.6 Verify Trade Book records simulated fill with millisecond timestamp.                        |
|     [ ] 2.7 Verify Positions view updates simulated MTM and net quantity.                               |
+---------------------------------------------------------------------------------------------------------+
| [ ] 3. LIVE Mode Gating & Challenge Verification                                                        |
|     [ ] 3.1 Trigger Mode Switch modal and select LIVE radio option.                                     |
|     [ ] 3.2 Verify mandatory typing challenge box appears requiring "CONFIRM_LIVE".                     |
|     [ ] 3.3 Verify typing incorrect text ("LIVE", "confirm", "yes") keeps submit button disabled.       |
|     [ ] 3.4 Type exact string "CONFIRM_LIVE" and confirm.                                               |
|     [ ] 3.5 Header displays LIVE pulse badge (Green).                                                   |
|     [ ] 3.6 Order Ticket displays live capital warning banner.                                          |
|     [ ] 3.7 Audit log records AUDIT_MODE_CHANGED: actor, timestamp, previous_mode, new_mode.            |
+---------------------------------------------------------------------------------------------------------+
| [ ] 4. Global Emergency Kill-Switch Drill                                                               |
|     [ ] 4.1 Stage 2 open Limit orders resting on the exchange (e.g. 5% below market).                   |
|     [ ] 4.2 Verify orders appear with status PENDING/OPEN in Order Book (Alt+2).                        |
|     [ ] 4.3 Press Shift + Esc from anywhere in the terminal.                                            |
|     [ ] 4.4 Confirm modal prompt: "CANCEL ALL ACTIVE ORDERS?".                                          |
|     [ ] 4.5 Assert all open orders transition to CANCELLED within 500ms.                                |
|     [ ] 4.6 Verify audit log emits AUDIT_EMERGENCY_CANCEL_ALL with user ID and client IP.               |
|     [ ] 4.7 Test WebSocket severed fallback: disconnect network, press Shift+Esc; assert REST cancel.  |
+---------------------------------------------------------------------------------------------------------+
| [ ] 5. Live Equity Order Verification (Micro-Lot: 1 Share)                                              |
|     [ ] 5.1 Select liquid equity scrip on nse_cm (e.g. ITC or INFY).                                    |
|     [ ] 5.2 Validate tick size modulo: Attempt limit order @ ₹450.13; verify auto-rounded to ₹450.15.   |
|     [ ] 5.3 Place BUY LIMIT order 1 Share @ 3% below market LTP.                                        |
|     [ ] 5.4 Verify broker acknowledgment returned (nOrdNo populated).                                   |
|     [ ] 5.5 Verify Order Book displays status PENDING on exchange.                                      |
|     [ ] 5.6 Modify order: Amend price by +₹0.10 tick; verify status MODIFIED.                           |
|     [ ] 5.7 Cancel order: Click [Can] button; verify status CANCELLED.                                  |
|     [ ] 5.8 Market Protection Test: Place MARKET order with 2% MP buffer; assert fills as Limit.        |
|     [ ] 5.9 Verify Trade Book captures trade fill ID and volume-weighted traded price.                  |
|     [ ] 5.10 Verify Positions view displays Net Qty = 1, product = CNC/MIS.                             |
|     [ ] 5.11 Square off position via [Exit] button; verify net position returns to 0.                   |
+---------------------------------------------------------------------------------------------------------+
| [ ] 6. Live Option Order Verification (Micro-Lot: 1 Lot)                                                |
|     [ ] 6.1 Select liquid derivative contract on nse_fo (e.g. NIFTY Current Expiry OTM Call).           |
|     [ ] 6.2 Validate lot size invariant: Quantity must be integer multiple of benchmark lot (50 Qty).  |
|     [ ] 6.3 Pre-trade margin preview: Verify required margin <= available cash balance.                 |
|     [ ] 6.4 Place BUY LIMIT order with 5% MP buffer.                                                    |
|     [ ] 6.5 Verify execution report polls and resolves to TRADED.                                       |
|     [ ] 6.6 Native Broker Stop Loss: Place SELL order_type="SL" with clean price == trigger_price.       |
|     [ ] 6.7 Verify SL order rests with status TRIGGER_PENDING.                                          |
|     [ ] 6.8 Cancel SL order; square off net option position; verify net quantity is 0.                  |
+---------------------------------------------------------------------------------------------------------+
| [ ] 7. Live Multi-Leg Basket Verification                                                               |
|     [ ] 7.1 Open Basket Builder (Alt+6) and select "Bull Call Spread" template.                         |
|     [ ] 7.2 Verify strikes: Leg 1 Buy ATM Call, Leg 2 Sell OTM Call.                                    |
|     [ ] 7.3 Click [Validate Basket]; verify 5-point checklist returns VALIDATION PASSED.               |
|     [ ] 7.4 Click [EXECUTE BASKET]; verify typing challenge "CONFIRM_EXECUTE_BASKET".                   |
|     [ ] 7.5 Verify Sequential DAG Pipeline:                                                             |
|             - Stage 1 (Long Hedge Leg 1) dispatches first and reports TRADED.                           |
|             - Stage 2 (Short Leg 2) dispatches second under reduced SPAN margin block.                  |
|     [ ] 7.6 Verify Exposure State transitions: NEUTRAL -> PARTIALLY_EXPOSED -> FULLY_HEDGED.            |
|     [ ] 7.7 Verify Real-Time Execution Monitor reflects 100% completion.                                |
|     [ ] 7.8 Square off basket legs sequentially (Short leg first, Long leg second).                     |
+---------------------------------------------------------------------------------------------------------+
| [ ] 8. End-of-Day (EOD) Reconciliation Verification                                                     |
|     [ ] 8.1 Confirm 0 orders remain in RECONCILING, SUBMITTED, or PENDING states.                       |
|     [ ] 8.2 Compare Trade Book trade fills against official Kotak Neo broker statement.                 |
|     [ ] 8.3 Verify overnight carry-forward Demat CNC holdings match Demat depository ledger.            |
|     [ ] 8.4 Verify Funds Ledger: Cash balance, SPAN margin, and MTM credits match broker app.           |
|     [ ] 8.5 Switch global ExecutionMode back to DISABLED.                                               |
|     [ ] 8.6 Trigger automated pre-shutdown SQLite database backup.                                      |
+---------------------------------------------------------------------------------------------------------+
```

---

## 3. Operator Sign-Off Record

| Verification Item | Operator Initial | Date (YYYY-MM-DD) | Time (IST) | Result (PASS / FAIL) | Notes / Anomalies |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **1. DISABLED Mode** | ________ | ________ | ________ | ________ | ________________________ |
| **2. PAPER Mode** | ________ | ________ | ________ | ________ | ________________________ |
| **3. LIVE Mode** | ________ | ________ | ________ | ________ | ________________________ |
| **4. Kill-Switch** | ________ | ________ | ________ | ________ | ________________________ |
| **5. Equity Order** | ________ | ________ | ________ | ________ | ________________________ |
| **6. Option Order** | ________ | ________ | ________ | ________ | ________________________ |
| **7. Basket Order** | ________ | ________ | ________ | ________ | ________________________ |
| **8. EOD Reconciliation** | ________ | ________ | ________ | ________ | ________________________ |

**Primary Operator Signature:** ___________________________  
**Trading Terminal Version:** Milestone M7 (Phase 12B v1.0.0)  
**Broker Environment:** Kotak Neo Broker API (`kotakneoapi>=3.0.13`)  
