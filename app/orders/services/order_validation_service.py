"""
Order Validation Service.
Phase 7: Order Domain Foundation.
Implements pre-flight structural validations, NSE tick size rules, lot size multiples,
freeze limits, Stop Loss trigger logic, and Market Protection (MP) buffering.
"""

from typing import Any, Dict, List, Optional, Tuple

from app.core.audit import AuditCategory, audit_logger
from app.core.exceptions import OrderValidationException
from app.core.request_context import get_correlation_id, get_request_id
from app.events.event_bus import publish
from app.events.event_types import ORDER_VALIDATED, ORDER_VALIDATION_FAILED
from app.logging.logger import get_logger
from app.market_watch.services.instrument_service import (
    InstrumentService,
    instrument_service,
)
from app.orders.models.order import Order, OrderSide, OrderType, ProductType

logger = get_logger("app.orders.services.order_validation_service")


class OrderValidationService:
    """
    Validates order attributes, exchange parameters, and mathematical invariants
    prior to state advancement. Zero execution logic.
    """

    SUPPORTED_SEGMENTS = {"nse_cm", "bse_cm", "nse_fo", "bse_fo", "cde_fo"}

    def __init__(
        self, instruments: Optional[InstrumentService] = None
    ) -> None:
        self.instrument_service = instruments or instrument_service

    def validate_order(self, order: Order) -> Tuple[bool, List[str]]:
        """
        Comprehensive pre-flight validation evaluating all structural order parameters.
        Returns:
            Tuple[bool, List[str]]: (is_valid, list_of_validation_error_messages)
        """
        errors: List[str] = []

        # 1. Attribute Completeness
        if order.quantity <= 0:
            errors.append("Order quantity must be a positive integer greater than zero.")

        if not order.trading_symbol or not order.trading_symbol.strip():
            errors.append("Trading symbol is required and cannot be empty.")

        if not order.instrument_token or not str(order.instrument_token).strip():
            errors.append("Instrument token is required.")

        seg = str(order.exchange_segment).strip().lower()
        if seg not in self.SUPPORTED_SEGMENTS:
            errors.append(
                f"Exchange segment '{order.exchange_segment}' is invalid. Supported: {sorted(list(self.SUPPORTED_SEGMENTS))}."
            )

        if not isinstance(order.side, OrderSide):
            errors.append(f"Invalid order side '{order.side}'. Must be BUY or SELL.")

        if not isinstance(order.order_type, OrderType):
            errors.append(f"Invalid order type '{order.order_type}'. Must be MARKET, LIMIT, SL, or SL_M.")

        if not isinstance(order.product_type, ProductType):
            errors.append(f"Invalid product type '{order.product_type}'. Must be CNC, MIS, or NRML.")

        # CNC restriction for derivatives
        if order.product_type == ProductType.CNC and seg in ("nse_fo", "bse_fo", "cde_fo"):
            errors.append("Product code CNC (Cash and Carry) is not permitted for derivative segments.")

        # 2. Tick Size Verification
        tick_size = 0.0025 if seg == "cde_fo" else 0.05
        if order.order_type in (OrderType.LIMIT, OrderType.SL):
            if order.price <= 0.0:
                errors.append(f"Price must be greater than zero for {order.order_type.value} orders.")
            elif not self._is_valid_tick(order.price, tick_size):
                errors.append(
                    f"Price ₹{order.price:.2f} is invalid. Price must be a multiple of tick size ₹{tick_size}."
                )

        if order.order_type in (OrderType.SL, OrderType.SL_M):
            if order.trigger_price <= 0.0:
                errors.append(f"Trigger price must be greater than zero for {order.order_type.value} orders.")
            elif not self._is_valid_tick(order.trigger_price, tick_size):
                errors.append(
                    f"Trigger price ₹{order.trigger_price:.2f} is invalid. Trigger price must be a multiple of tick size ₹{tick_size}."
                )

        # 3. Stop Loss Trigger Logic
        if order.order_type == OrderType.SL:
            if order.side == OrderSide.BUY:
                if order.price < order.trigger_price:
                    errors.append(
                        f"For Buy SL orders, limit price (₹{order.price:.2f}) must be greater than or equal to trigger price (₹{order.trigger_price:.2f})."
                    )
            elif order.side == OrderSide.SELL:
                if order.price > order.trigger_price:
                    errors.append(
                        f"For Sell SL orders, limit price (₹{order.price:.2f}) must be less than or equal to trigger price (₹{order.trigger_price:.2f})."
                    )

        # 4. Instrument Master & Lot Size Verification
        instrument = self.instrument_service.get_instrument(order.instrument_token, seg)
        lot_size = instrument.lot_size if instrument else 1
        freeze_limit = 10000

        # Known benchmark freeze limits
        sym_clean = order.trading_symbol.upper()
        if "NIFTY" in sym_clean and "BANK" not in sym_clean and seg == "nse_fo":
            freeze_limit = 1800
            lot_size = lot_size if lot_size > 1 else 25
        elif "BANKNIFTY" in sym_clean and seg == "nse_fo":
            freeze_limit = 900
            lot_size = lot_size if lot_size > 1 else 15

        if seg in ("nse_fo", "bse_fo", "cde_fo") and lot_size > 1:
            if order.quantity % lot_size != 0:
                errors.append(
                    f"Order quantity {order.quantity} is invalid for lot size {lot_size}. Quantity must be a multiple of {lot_size}."
                )

        if order.quantity > freeze_limit:
            errors.append(
                f"Order quantity {order.quantity} exceeds exchange freeze limit of {freeze_limit} for {order.trading_symbol}."
            )

        # Disclosed quantity validation
        if order.disclosed_quantity > 0:
            if order.disclosed_quantity > order.quantity:
                errors.append("Disclosed quantity cannot be greater than total order quantity.")
            min_disclosed = max(1, int(order.quantity * 0.10))
            if order.disclosed_quantity < min_disclosed:
                errors.append(
                    f"Disclosed quantity must be at least 10% of total order quantity ({min_disclosed})."
                )

        is_valid = len(errors) == 0

        # Dispatch events & audit
        if is_valid:
            publish(
                ORDER_VALIDATED,
                {
                    "client_order_id": order.client_order_id,
                    "symbol": order.trading_symbol,
                    "tick_size": tick_size,
                    "lot_size": lot_size,
                },
            )
            audit_logger.record(
                category=AuditCategory.ORDER,
                action="ORDER_VALIDATION",
                actor=str(order.user_id),
                correlation_id=get_correlation_id(),
                request_id=get_request_id(),
                details={"client_order_id": order.client_order_id, "status": "PASSED"},
            )
        else:
            publish(
                ORDER_VALIDATION_FAILED,
                {
                    "client_order_id": order.client_order_id,
                    "symbol": order.trading_symbol,
                    "errors": errors,
                },
            )
            audit_logger.record(
                category=AuditCategory.ORDER,
                action="ORDER_VALIDATION",
                actor=str(order.user_id),
                correlation_id=get_correlation_id(),
                request_id=get_request_id(),
                details={"client_order_id": order.client_order_id, "status": "FAILED", "errors": errors},
            )

        return is_valid, errors

    def calculate_market_protection(
        self,
        ref_price: float,
        side: OrderSide,
        mp_percent: float = 2.0,
        tick_size: float = 0.05,
    ) -> float:
        """
        Apply Market Protection buffer to convert pure Market orders into aggressive buffered Limit orders.
        Guarantees tick-size compliance.
        """
        if ref_price <= 0.0:
            return tick_size

        buffer_factor = float(mp_percent) / 100.0
        if side == OrderSide.BUY:
            buffered_price = ref_price * (1.0 + buffer_factor)
        else:
            buffered_price = ref_price * (1.0 - buffer_factor)

        # Snap to tick size
        if buffered_price <= tick_size:
            return tick_size

        ticks = round(buffered_price / tick_size)
        return round(ticks * tick_size, 2 if tick_size >= 0.01 else 4)

    def _is_valid_tick(self, price: float, tick_size: float) -> bool:
        """Mathematically verify price is an exact multiple of exchange tick size."""
        # Convert to integer millipaise to avoid IEEE 754 floating point inaccuracies
        scaled_price = round(price * 10000)
        scaled_tick = round(tick_size * 10000)
        return (scaled_price % scaled_tick) == 0


# Global Singleton Order Validation Service
order_validation_service = OrderValidationService()
