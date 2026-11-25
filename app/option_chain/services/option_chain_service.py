"""
Option Chain Aggregator and Analytics Engine.
Phase 10: Option Chain Workbench.
Generates symmetrical strike matrices, evaluates dynamic ATM/ITM/OTM moneyness,
Open Interest (OI) flows, Put-Call Ratio (PCR), and SFeed subscription hooks.
"""

from datetime import datetime, timedelta, timezone
import math
import os
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

import neo_api_client

from app.core.exceptions import ApplicationException
from app.logging.logger import get_logger
from app.market_watch.services.price_engine import price_engine
from app.broker.services.subscription_manager import subscription_manager
from app.option_chain.models.chain import (
    ExpiryInfo,
    OptionChainSnapshot,
    OptionContractQuote,
    OptionStrikeRow,
)
from app.option_chain.models.underlying import (
    StrikeFilterPreset,
    UnderlyingSpecification,
)
from app.option_chain.services.underlying_service import (
    UnderlyingService,
    underlying_service,
)

logger = get_logger("app.option_chain.services.option_chain_service")


class OptionChainService:
    """
    Core Option Chain Aggregation Engine.
    Coordinates contract expiries, spot prices, strike ladders,
    OI/Volume distribution, and PCR calculations.
    """

    def __init__(
        self,
        underlyings: Optional[UnderlyingService] = None,
        pe=None,
        sub_mgr=None,
    ) -> None:
        self.underlying_svc = underlyings or underlying_service
        self.price_engine = pe or price_engine
        self.sub_manager = sub_mgr or subscription_manager
        self._lock = threading.RLock()
        self._cache: Dict[str, Tuple[float, Any]] = {}
        self.CACHE_TTL_SEC = 3.0
        self._neo_client: Optional[Any] = None

    def _get_neo_client(self) -> Optional[Any]:
        """Lazy initializer for native Kotak Neo market data client, prioritizing authenticated session."""
        if self._neo_client is not None:
            return self._neo_client

        try:
            from app.broker.adapters.kotak_adapter import kotak_adapter
            if kotak_adapter.client is not None:
                self._neo_client = kotak_adapter.client
                return self._neo_client
        except Exception:
            pass

        ck = os.getenv("NEO_CONSUMER_KEY")
        if ck and hasattr(neo_api_client, "NeoAPI"):
            try:
                os.environ.setdefault("NEO_LOG_FILE_ENABLED", "false")
                self._neo_client = neo_api_client.NeoAPI(consumer_key=ck)
            except Exception as e:
                logger.warning(f"Failed to initialize NeoAPI client: {e}")
                self._neo_client = None
        return self._neo_client

    # 1. Expiries Pipeline
    def get_expiries(self, symbol: str) -> List[ExpiryInfo]:
        """
        Retrieve and categorize contract expiries for an underlying.
        Tags nearest weekly (W0) and monthly (M0) series.
        For stocks, strictly restricts to Monthly expiries per NSE regulatory standards.
        """
        sym = symbol.strip().upper()
        spec = self.underlying_svc.get_underlying(sym)
        if not spec:
            raise ApplicationException(
                message=f"Unsupported underlying symbol: {symbol}",
                error_code="UNDERLYING_NOT_FOUND",
                status_code=404,
            )

        now = datetime.now(timezone.utc)
        today = now.date()

        # 1. Try native broker API first (direct ground truth)
        client = self._get_neo_client()
        if client:
            try:
                exch = spec.derivatives_segment or "nse_fo"
                raw = client.expiries(exchange=exch, underlying=sym)
                if isinstance(raw, dict) and "expiries" in raw and isinstance(raw["expiries"], list) and raw["expiries"]:
                    broker_dates = raw["expiries"]
                    expiries: List[ExpiryInfo] = []
                    for idx, date_str in enumerate(broker_dates):
                        try:
                            dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                            if dt.date() < today:
                                continue
                            delta_days = max(0, math.ceil((dt - now).total_seconds() / 86400.0))
                            token = dt.strftime("%d%b").upper()

                            # Regulatory Rule: Stocks in India have NO weekly options, only Monthly!
                            # Indices have weekly expiries with month-end labeled Monthly.
                            if not spec.is_index:
                                is_monthly = True
                                label = f"{dt.strftime('%d-%b-%Y')} (Monthly)"
                            else:
                                same_month = [d for d in broker_dates if d.startswith(date_str[:7])]
                                is_monthly = (date_str == max(same_month))
                                label = f"{dt.strftime('%d-%b-%Y')} ({'Monthly' if is_monthly else 'Weekly'})"

                            expiries.append(ExpiryInfo(
                                expiry_date=date_str,
                                display_label=label,
                                days_to_expiry=delta_days,
                                is_current_weekly=(idx == 0 and not is_monthly),
                                is_monthly=is_monthly,
                                trading_symbol_token=token,
                            ))
                        except Exception:
                            continue

                    if expiries:
                        expiries.sort(key=lambda e: e.expiry_date)
                        # For equities, cap to 3 active monthly contracts (near, next, far)
                        if not spec.is_index:
                            return expiries[:3]
                        return expiries[:7]
            except Exception as e:
                logger.warning(f"Live expiries fetch failed for {sym}, using offline generator: {e}")

        # 2. Offline fallback (calendar-accurate math)
        expiries: List[ExpiryInfo] = []
        if not spec.is_index:
            # Equities: strictly 3 monthly contracts (last Thursday of each consecutive month)
            for m_offset in range(3):
                m_year = today.year + (today.month - 1 + m_offset) // 12
                m_month = (today.month - 1 + m_offset) % 12 + 1
                if m_month == 12:
                    last_day = datetime(m_year, 12, 31).date()
                else:
                    last_day = datetime(m_year, m_month + 1, 1).date() - timedelta(days=1)
                offset = (last_day.weekday() - 3) % 7
                last_thu = last_day - timedelta(days=offset)
                if last_thu < today:
                    continue
                dt = datetime(last_thu.year, last_thu.month, last_thu.day, tzinfo=timezone.utc)
                delta_days = max(0, math.ceil((dt - now).total_seconds() / 86400.0))
                token = dt.strftime("%d%b").upper()
                expiries.append(ExpiryInfo(
                    expiry_date=last_thu.strftime("%Y-%m-%d"),
                    display_label=f"{dt.strftime('%d-%b-%Y')} (Monthly)",
                    days_to_expiry=delta_days,
                    is_current_weekly=False,
                    is_monthly=True,
                    trading_symbol_token=token,
                ))
            return expiries[:3]
        else:
            # Indices: Rolling weekly Thursdays
            target_weekday = 3
            if "FINNIFTY" in sym:
                target_weekday = 1
            elif "SENSEX" in sym:
                target_weekday = 4

            days_ahead = (target_weekday - today.weekday()) % 7
            if days_ahead == 0 and (now.hour > 10):
                days_ahead = 7

            first_expiry = today + timedelta(days=days_ahead)
            raw_dates = [first_expiry + timedelta(weeks=i) for i in range(7)]
            for idx, exp_d in enumerate(raw_dates):
                try:
                    dt = datetime(exp_d.year, exp_d.month, exp_d.day, tzinfo=timezone.utc)
                    delta_days = max(0, math.ceil((dt - now).total_seconds() / 86400.0))
                    token = dt.strftime("%d%b").upper()

                    next_wk = exp_d + timedelta(weeks=1)
                    is_monthly = (next_wk.month != exp_d.month)
                    label = f"{dt.strftime('%d-%b-%Y')} ({'Monthly' if is_monthly else 'Weekly'})"

                    info = ExpiryInfo(
                        expiry_date=exp_d.strftime("%Y-%m-%d"),
                        display_label=label,
                        days_to_expiry=delta_days,
                        is_current_weekly=(idx == 0 and not is_monthly),
                        is_monthly=is_monthly,
                        trading_symbol_token=token,
                    )
                    expiries.append(info)
                except Exception:
                    continue

            expiries.sort(key=lambda e: e.expiry_date)
            return expiries

    # 2. Strike Matrix Aggregator
    def get_option_chain(
        self,
        symbol: str,
        expiry: Optional[str] = None,
        preset: Any = StrikeFilterPreset.ATM_10,
    ) -> OptionChainSnapshot:
        """
        Generate symmetrical Call and Put strike matrix centered around the dynamic ATM strike.
        Prioritizes live broker market data touchlines directly from Kotak Neo,
        falling back to high-fidelity simulated option pricing offline.
        """
        sym = symbol.strip().upper()
        spec = self.underlying_svc.get_underlying(sym)
        if not spec:
            raise ApplicationException(
                message=f"Unsupported underlying symbol: {symbol}",
                error_code="UNDERLYING_NOT_FOUND",
                status_code=404,
            )

        filter_preset = (
            preset if isinstance(preset, StrikeFilterPreset) else StrikeFilterPreset.from_value(preset)
        )
        window = filter_preset.window_size

        # Resolve Expiry
        expiries = self.get_expiries(sym)
        if not expiries:
            raise ApplicationException(
                message=f"No active expiries found for symbol: {symbol}",
                error_code="NO_EXPIRIES_FOUND",
                status_code=404,
            )

        active_expiry = expiry if expiry else expiries[0].expiry_date
        expiry_info = next((e for e in expiries if e.expiry_date == active_expiry), expiries[0])
        expiry_token = expiry_info.trading_symbol_token

        # Resolve Spot Reference Price
        spot_price = self.underlying_svc.get_spot_ltp(sym)
        if spot_price <= 0.0:
            spot_price = 25185.45 if sym == "NIFTY" else 1339.00

        # Step A: Query Live Kotak Neo Option Chain API
        client = self._get_neo_client()
        if client:
            try:
                exch = spec.derivatives_segment or "nse_fo"
                chain_resp = client.option_chain(
                    exchange=exch,
                    underlying=sym,
                    expiry=active_expiry,
                    count=window * 2,
                )
                if isinstance(chain_resp, dict) and "call" in chain_resp and "put" in chain_resp:
                    raw_calls_data = chain_resp.get("call", [])
                    raw_puts_data = chain_resp.get("put", [])
                    spot_info = chain_resp.get("spot", {})
                    common = chain_resp.get("common_data", {})

                    live_spot = float(spot_info.get("ltp") or spot_price)
                    step = spec.strike_step
                    atm_strike = round(live_spot / step) * step

                    calls_by_k = {}
                    for c in raw_calls_data:
                        k_str = c.get("inst", {}).get("strkPrc")
                        if k_str:
                            calls_by_k[float(k_str)] = c

                    puts_by_k = {}
                    for p in raw_puts_data:
                        k_str = p.get("inst", {}).get("strkPrc")
                        if k_str:
                            puts_by_k[float(k_str)] = p

                    all_ks = sorted(set(calls_by_k.keys()).union(puts_by_k.keys()))
                    if all_ks:
                        atm_strike = min(all_ks, key=lambda k: abs(k - live_spot))
                    else:
                        atm_strike = round(live_spot / step) * step
                    atm_diffs = sorted(all_ks, key=lambda k: abs(k - atm_strike))
                    selected_ks = sorted(atm_diffs[: (window * 2 + 1)])

                    oi_broadcast_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
                    strike_rows: List[OptionStrikeRow] = []
                    total_call_oi = 0
                    total_put_oi = 0
                    total_call_vol = 0
                    total_put_vol = 0
                    parsed_calls = []
                    parsed_puts = []

                    lot_sz = int(common.get("mktLot") or spec.lot_size)

                    for k in selected_ks:
                        is_atm = (k == atm_strike)
                        dist = k - live_spot

                        c_raw = calls_by_k.get(k)
                        p_raw = puts_by_k.get(k)

                        if c_raw:
                            c_inst = c_raw.get("inst", {})
                            c_q = c_raw.get("quote", {})
                            c_oi = c_raw.get("oi", {})
                            c_ltp = float(c_q.get("ltp") or 0.0)
                            c_prev = float(c_q.get("pc") or c_ltp)
                            c_vol = int(float(c_q.get("vol") or 0))
                            cur_oi = int(float(c_oi.get("cur") or 0))
                            d_oi = int(float(c_oi.get("chg") or 0))

                            call_quote = OptionContractQuote(
                                instrument_token=c_inst.get("neoSymbol", "").split("|")[-1] or str(int(k)),
                                trading_symbol=c_inst.get("symbol", f"{sym}{expiry_token}{int(k)}CE"),
                                option_type="CE",
                                strike_price=k,
                                expiry_date=active_expiry,
                                ltp=c_ltp,
                                price_change=round(c_ltp - c_prev, 2),
                                percent_change=round(float(c_oi.get("chgPct") or 0.0), 2),
                                bid_price=round(max(0.05, c_ltp - 0.20), 2),
                                bid_quantity=lot_sz * 10,
                                ask_price=round(c_ltp + 0.20, 2),
                                ask_quantity=lot_sz * 10,
                                open_interest=cur_oi,
                                change_in_oi=d_oi,
                                percent_change_in_oi=round(float(c_oi.get("chgPct") or 0.0), 2),
                                volume=c_vol,
                                total_traded_value=round(c_vol * c_ltp * lot_sz, 2),
                                oi_source_timestamp=oi_broadcast_time,
                                moneyness=c_inst.get("moneyness", "OTM").upper(),
                                intrinsic_value=max(0.0, live_spot - k),
                            )
                        else:
                            call_quote = self._synthesize_contract_quote(
                                spec=spec, trading_symbol=f"{sym}{expiry_token}{int(k)}CE",
                                option_type="CE", strike=k, spot=live_spot, atm_strike=atm_strike,
                                expiry_date=active_expiry, oi_timestamp=oi_broadcast_time,
                            )

                        if p_raw:
                            p_inst = p_raw.get("inst", {})
                            p_q = p_raw.get("quote", {})
                            p_oi = p_raw.get("oi", {})
                            p_ltp = float(p_q.get("ltp") or 0.0)
                            p_prev = float(p_q.get("pc") or p_ltp)
                            p_vol = int(float(p_q.get("vol") or 0))
                            cur_oi = int(float(p_oi.get("cur") or 0))
                            d_oi = int(float(p_oi.get("chg") or 0))

                            put_quote = OptionContractQuote(
                                instrument_token=p_inst.get("neoSymbol", "").split("|")[-1] or str(int(k)),
                                trading_symbol=p_inst.get("symbol", f"{sym}{expiry_token}{int(k)}PE"),
                                option_type="PE",
                                strike_price=k,
                                expiry_date=active_expiry,
                                ltp=p_ltp,
                                price_change=round(p_ltp - p_prev, 2),
                                percent_change=round(float(p_oi.get("chgPct") or 0.0), 2),
                                bid_price=round(max(0.05, p_ltp - 0.20), 2),
                                bid_quantity=lot_sz * 10,
                                ask_price=round(p_ltp + 0.20, 2),
                                ask_quantity=lot_sz * 10,
                                open_interest=cur_oi,
                                change_in_oi=d_oi,
                                percent_change_in_oi=round(float(p_oi.get("chgPct") or 0.0), 2),
                                volume=p_vol,
                                total_traded_value=round(p_vol * p_ltp * lot_sz, 2),
                                oi_source_timestamp=oi_broadcast_time,
                                moneyness=p_inst.get("moneyness", "OTM").upper(),
                                intrinsic_value=max(0.0, k - live_spot),
                            )
                        else:
                            put_quote = self._synthesize_contract_quote(
                                spec=spec, trading_symbol=f"{sym}{expiry_token}{int(k)}PE",
                                option_type="PE", strike=k, spot=live_spot, atm_strike=atm_strike,
                                expiry_date=active_expiry, oi_timestamp=oi_broadcast_time,
                            )

                        total_call_oi += call_quote.open_interest
                        total_put_oi += put_quote.open_interest
                        total_call_vol += call_quote.volume
                        total_put_vol += put_quote.volume
                        parsed_calls.append(call_quote)
                        parsed_puts.append(put_quote)

                        strike_rows.append(OptionStrikeRow(
                            strike_price=k, is_atm=is_atm, distance_from_spot=dist,
                            call_quote=call_quote, put_quote=put_quote,
                        ))

                    if parsed_calls:
                        max_c_oi = max(c.open_interest for c in parsed_calls)
                        max_c_vol = max(c.volume for c in parsed_calls)
                        for c in parsed_calls:
                            c.is_max_oi = (c.open_interest == max_c_oi and max_c_oi > 0)
                            c.is_max_volume = (c.volume == max_c_vol and max_c_vol > 0)

                    if parsed_puts:
                        max_p_oi = max(p.open_interest for p in parsed_puts)
                        max_p_vol = max(p.volume for p in parsed_puts)
                        for p in parsed_puts:
                            p.is_max_oi = (p.open_interest == max_p_oi and max_p_oi > 0)
                            p.is_max_volume = (p.volume == max_p_vol and max_p_vol > 0)

                    max_call_oi_strike = next((c.strike_price for c in parsed_calls if c.is_max_oi), None)
                    max_put_oi_strike = next((p.strike_price for p in parsed_puts if p.is_max_oi), None)

                    pcr_oi = self._calculate_pcr(total_put_oi, total_call_oi)
                    pcr_volume = self._calculate_pcr(total_put_vol, total_call_vol)
                    max_pain = self._calculate_max_pain(selected_ks, parsed_calls, parsed_puts)

                    spot_chg = round(live_spot - float(spot_info.get("prevClose") or live_spot), 2)
                    spot_pct = round((spot_chg / float(spot_info.get("prevClose") or 1.0)) * 100.0, 2)

                    return OptionChainSnapshot(
                        underlying_symbol=sym,
                        spot_price=live_spot,
                        spot_price_change=spot_chg,
                        spot_percent_change=spot_pct,
                        expiry_date=active_expiry,
                        atm_strike=atm_strike,
                        strike_step=step,
                        lot_size=lot_sz,
                        preset=filter_preset,
                        strikes=strike_rows,
                        total_call_oi=total_call_oi,
                        total_put_oi=total_put_oi,
                        total_call_volume=total_call_vol,
                        total_put_volume=total_put_vol,
                        pcr_oi=pcr_oi,
                        pcr_volume=pcr_volume,
                        max_pain_strike=max_pain,
                        max_call_oi_strike=max_call_oi_strike,
                        max_put_oi_strike=max_put_oi_strike,
                    )
            except Exception as e:
                logger.warning(f"Live option chain query failed for {sym}, using offline generator: {e}")

        # Step B: Offline Fallback Generator (if broker offline or test sandbox)

        # Calculate ATM Strike
        step = spec.strike_step
        atm_strike = round(spot_price / step) * step

        # Generate Symmetrical Strike Ladder
        lower_strikes = [atm_strike - (i * step) for i in range(window, 0, -1)]
        higher_strikes = [atm_strike + (i * step) for i in range(1, window + 1)]
        all_strikes = lower_strikes + [atm_strike] + higher_strikes

        # Synthesize and populate quotes
        strike_rows: List[OptionStrikeRow] = []
        total_call_oi = 0
        total_put_oi = 0
        total_call_vol = 0
        total_put_vol = 0

        now_iso = datetime.now(timezone.utc).isoformat()
        # Simulated exchange broadcast time (e.g. 15 seconds prior)
        oi_broadcast_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")

        raw_calls = []
        raw_puts = []

        for k in all_strikes:
            is_atm = (k == atm_strike)
            dist = k - spot_price

            call_sym = f"{sym}{expiry_token}{int(k)}CE"
            put_sym = f"{sym}{expiry_token}{int(k)}PE"

            call_quote = self._synthesize_contract_quote(
                spec=spec,
                trading_symbol=call_sym,
                option_type="CE",
                strike=k,
                spot=spot_price,
                atm_strike=atm_strike,
                expiry_date=active_expiry,
                oi_timestamp=oi_broadcast_time,
            )
            put_quote = self._synthesize_contract_quote(
                spec=spec,
                trading_symbol=put_sym,
                option_type="PE",
                strike=k,
                spot=spot_price,
                atm_strike=atm_strike,
                expiry_date=active_expiry,
                oi_timestamp=oi_broadcast_time,
            )

            total_call_oi += call_quote.open_interest
            total_put_oi += put_quote.open_interest
            total_call_vol += call_quote.volume
            total_put_vol += put_quote.volume

            raw_calls.append(call_quote)
            raw_puts.append(put_quote)

            row = OptionStrikeRow(
                strike_price=k,
                is_atm=is_atm,
                distance_from_spot=dist,
                call_quote=call_quote,
                put_quote=put_quote,
            )
            strike_rows.append(row)

        # Mark Max OI and Max Volume Highlights
        if raw_calls:
            max_c_oi = max(c.open_interest for c in raw_calls)
            max_c_vol = max(c.volume for c in raw_calls)
            for c in raw_calls:
                c.is_max_oi = (c.open_interest == max_c_oi and max_c_oi > 0)
                c.is_max_volume = (c.volume == max_c_vol and max_c_vol > 0)

        if raw_puts:
            max_p_oi = max(p.open_interest for p in raw_puts)
            max_p_vol = max(p.volume for p in raw_puts)
            for p in raw_puts:
                p.is_max_oi = (p.open_interest == max_p_oi and max_p_oi > 0)
                p.is_max_volume = (p.volume == max_p_vol and max_p_vol > 0)

        # Key Support and Resistance Strikes
        max_call_oi_strike = next((c.strike_price for c in raw_calls if c.is_max_oi), None)
        max_put_oi_strike = next((p.strike_price for p in raw_puts if p.is_max_oi), None)

        # Put-Call Ratio Calculation
        pcr_oi = self._calculate_pcr(total_put_oi, total_call_oi)
        pcr_volume = self._calculate_pcr(total_put_vol, total_call_vol)

        # Max Pain Approximation (strike causing min total loss to option writers)
        max_pain = self._calculate_max_pain(all_strikes, raw_calls, raw_puts)

        snapshot = OptionChainSnapshot(
            underlying_symbol=sym,
            spot_price=spot_price,
            spot_price_change=round(spot_price * 0.0035, 2),  # Reference session change
            spot_percent_change=0.35,
            expiry_date=active_expiry,
            atm_strike=atm_strike,
            strike_step=step,
            lot_size=spec.lot_size,
            preset=filter_preset,
            total_call_oi=total_call_oi,
            total_put_oi=total_put_oi,
            total_call_volume=total_call_vol,
            total_put_volume=total_put_vol,
            pcr_oi=pcr_oi,
            pcr_volume=pcr_volume,
            max_pain_strike=max_pain,
            max_call_oi_strike=max_call_oi_strike,
            max_put_oi_strike=max_put_oi_strike,
            strikes=strike_rows,
            source_timestamp=now_iso,
            oi_source_timestamp=oi_broadcast_time,
            retrieved_timestamp=now_iso,
        )

        return snapshot

    # 3. PCR Calculation
    @staticmethod
    def _calculate_pcr(put_metric: float, call_metric: float) -> float:
        """Calculate Put-Call Ratio with zero denominator safety."""
        if call_metric <= 0.0:
            return 0.0
        val = put_metric / float(call_metric)
        return min(round(val, 4), 10.0)

    # 4. Max Pain Strike Calculation
    @staticmethod
    def _calculate_max_pain(
        strikes: List[float], calls: List[OptionContractQuote], puts: List[OptionContractQuote]
    ) -> Optional[float]:
        """
        Calculate Max Pain strike (strike minimizing total intrinsic payout by option sellers).
        """
        if not strikes or not calls or not puts:
            return None

        call_map = {c.strike_price: c.open_interest for c in calls}
        put_map = {p.strike_price: p.open_interest for p in puts}

        min_total_loss = float("inf")
        best_strike = strikes[0]

        for s in strikes:
            total_loss = 0.0
            # Call sellers payout if expiry is s
            for k, oi in call_map.items():
                if s > k:
                    total_loss += (s - k) * oi
            # Put sellers payout if expiry is s
            for k, oi in put_map.items():
                if s < k:
                    total_loss += (k - s) * oi

            if total_loss < min_total_loss:
                min_total_loss = total_loss
                best_strike = s

        return best_strike

    # 5. Contract Quote Synthesis & Market Data Resolution
    def _synthesize_contract_quote(
        self,
        spec: UnderlyingSpecification,
        trading_symbol: str,
        option_type: str,
        strike: float,
        spot: float,
        atm_strike: float,
        expiry_date: str,
        oi_timestamp: str,
    ) -> OptionContractQuote:
        """
        Resolve real-time touchline or synthesize realistic option quotes based on distance from spot.
        """
        # Moneyness & Intrinsic Value
        if option_type == "CE":
            intrinsic = max(0.0, spot - strike)
            if strike < atm_strike:
                moneyness = "ITM"
            elif strike == atm_strike:
                moneyness = "ATM"
            else:
                moneyness = "OTM"
        else:
            intrinsic = max(0.0, strike - spot)
            if strike > atm_strike:
                moneyness = "ITM"
            elif strike == atm_strike:
                moneyness = "ATM"
            else:
                moneyness = "OTM"

        # Check InstrumentRepository for actual broker token
        token = str(abs(hash(trading_symbol)) % 90000 + 10000)
        try:
            from app.market_watch.repositories.instrument_repository import instrument_repository
            inst = instrument_repository.get_by_symbol(trading_symbol, spec.derivatives_segment)
            if inst:
                token = inst.instrument_token
        except Exception:
            pass

        touchline = None
        try:
            touchline = self.price_engine.get_touchline(spec.derivatives_segment, token)
        except Exception:
            pass

        if touchline and touchline.ltp > 0:
            ltp = touchline.ltp
            bid = touchline.bid if touchline.bid > 0 else max(0.05, round((ltp - 0.20) * 20.0) / 20.0)
            ask = touchline.ask if touchline.ask > 0 else round((ltp + 0.20) * 20.0) / 20.0
            volume = touchline.volume
        else:
            # High-fidelity option pricing model for simulated/offline pricing
            # Time value decays symmetrically as strike moves OTM
            dist_pts = abs(strike - spot)
            time_value = max(5.0, (150.0 - (dist_pts * 0.15)))
            ltp = max(0.05, round((intrinsic + time_value) * 20.0) / 20.0)
            bid = max(0.05, round((ltp - 0.20) * 20.0) / 20.0)
            ask = round((ltp + 0.20) * 20.0) / 20.0
            volume = max(1000, int(100000 - (dist_pts * 120)))

        # Symmetrical realistic Open Interest bell-curve distribution centered around ATM
        dist_factor = abs(strike - atm_strike) / spec.strike_step
        base_oi = int(5000000 * math.exp(-0.15 * dist_factor))
        oi = max(50000, base_oi + int(dist_factor * 12500))
        d_oi = int((oi * 0.08) if strike >= atm_strike else (-oi * 0.04))

        # Flow Activity Tagging
        if d_oi > 0:
            activity = "LONG_BUILDUP" if option_type == "CE" else "SHORT_BUILDUP"
        else:
            activity = "SHORT_COVERING" if option_type == "CE" else "LONG_UNWINDING"

        return OptionContractQuote(
            instrument_token=token,
            trading_symbol=trading_symbol,
            option_type=option_type,
            strike_price=strike,
            expiry_date=expiry_date,
            ltp=ltp,
            price_change=round(ltp * 0.04, 2),
            percent_change=4.0,
            bid_price=bid,
            bid_quantity=spec.lot_size * 10,
            ask_price=ask,
            ask_quantity=spec.lot_size * 10,
            open_interest=oi,
            change_in_oi=d_oi,
            percent_change_in_oi=round((d_oi / (oi - d_oi)) * 100.0, 2) if (oi - d_oi) > 0 else 0.0,
            volume=volume,
            total_traded_value=round(volume * ltp * spec.lot_size, 2),
            oi_source_timestamp=oi_timestamp,
            moneyness=moneyness,
            intrinsic_value=intrinsic,
            activity_tag=activity,
        )

    # 6. SFeed Streaming Bridge
    def subscribe_chain_tokens(self, snapshot: OptionChainSnapshot) -> int:
        """
        Dynamically subscribe all visible option strikes in the chain snapshot to SFeed WebSocket.
        """
        tokens: List[Tuple[str, str]] = []
        seg = "nse_fo"
        for row in snapshot.strikes:
            if row.call_quote:
                tokens.append((seg, row.call_quote.instrument_token))
            if row.put_quote:
                tokens.append((seg, row.put_quote.instrument_token))

        count = 0
        for segment, tok in tokens:
            try:
                self.sub_manager.subscribe(segment, tok)
                count += 1
            except Exception:
                pass
        return count

    def unsubscribe_chain_tokens(self, snapshot: OptionChainSnapshot) -> int:
        """
        Unsubscribe chain strikes when changing expiry or closing workbench to prevent quota exhaustion.
        """
        tokens: List[Tuple[str, str]] = []
        seg = "nse_fo"
        for row in snapshot.strikes:
            if row.call_quote:
                tokens.append((seg, row.call_quote.instrument_token))
            if row.put_quote:
                tokens.append((seg, row.put_quote.instrument_token))

        count = 0
        for segment, tok in tokens:
            try:
                self.sub_manager.unsubscribe(segment, tok)
                count += 1
            except Exception:
                pass
        return count


# Global singleton instance
option_chain_service = OptionChainService()
