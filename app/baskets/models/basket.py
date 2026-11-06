from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import time
from typing import Any, Dict, List, Optional
import uuid

from app.orders.models.execution_mode import ExecutionMode
from app.orders.models.order import (
    OrderSide,
    OrderStatus,
    OrderType,
    ProductType,
    Validity,
)


class StrategyType(str, Enum):
    """Supported option structures and multi-leg strategies."""

    CUSTOM = "CUSTOM"
    BULL_CALL_SPREAD = "BULL_CALL_SPREAD"
    BEAR_PUT_SPREAD = "BEAR_PUT_SPREAD"
    LONG_STRADDLE = "LONG_STRADDLE"
    SHORT_STRADDLE = "SHORT_STRADDLE"
    LONG_STRANGLE = "LONG_STRANGLE"
    SHORT_STRANGLE = "SHORT_STRANGLE"
    IRON_CONDOR = "IRON_CONDOR"
    IRON_BUTTERFLY = "IRON_BUTTERFLY"
    COVERED_CALL = "COVERED_CALL"
    PROTECTIVE_PUT = "PROTECTIVE_PUT"


class BasketFailurePolicy(str, Enum):
    """Policy governing execution when an individual leg fails."""

    ABORT_REMAINING = "ABORT_REMAINING"         # Phase 9 Default: stop subsequent legs, prompt operator
    CONTINUE = "CONTINUE"                       # Continue independent legs (CUSTOM only)
    COMPENSATING_ACTION = "COMPENSATING_ACTION" # Reserved for future phases (Prohibited in Phase 9)


class BasketExecutionMode(str, Enum):
    """Sequencing mode for multi-leg wire dispatch."""

    SEQUENTIAL = "SEQUENTIAL"                   # Phase 9 Default: Leg i -> wait -> Leg i+1
    PARALLEL = "PARALLEL"                       # Concurrent thread dispatch
    DEPENDENCY = "DEPENDENCY"                   # DAG sequencing (e.g. wings before body)


class BasketExposureState(str, Enum):
    """Financial risk and hedging exposure state of the basket."""

    NEUTRAL = "NEUTRAL"                         # No market exposure (unfilled or closed)
    PARTIALLY_EXPOSED = "PARTIALLY_EXPOSED"     # Asymmetric fill or missing hedge
    FULLY_HEDGED = "FULLY_HEDGED"               # Complete risk-defined structure active
    UNKNOWN = "UNKNOWN"                         # One or more legs in RECONCILING / unconfirmed wire state


class BasketState(str, Enum):
    """Finite State Machine states governing Basket lifecycle."""

    DRAFT = "DRAFT"                             # Unvalidated basket draft
    VALIDATED = "VALIDATED"                     # Structural syntax & strike ladder verified
    READY = "READY"                             # Pre-trade capital risk and margin checks cleared
    EXECUTING = "EXECUTING"                     # Actively routing legs
    PARTIALLY_EXECUTED = "PARTIALLY_EXECUTED"   # Execution halted with partial fills
    EXECUTED = "EXECUTED"                       # All legs 100% filled (Terminal)
    FAILED = "FAILED"                           # Validation failed or initial leg rejected (Terminal)
    CANCELLED = "CANCELLED"                     # Operator cancelled (Terminal)
    RECONCILING = "RECONCILING"                 # Golden Rule: awaiting broker state resolution


@dataclass
class BasketLeg:
    """Individual leg component of a multi-leg basket."""

    leg_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    leg_index: int = 0
    trading_symbol: str = ""
    exchange_segment: str = "nse_fo"
    instrument_token: str = ""
    side: OrderSide = OrderSide.BUY
    order_type: OrderType = OrderType.LIMIT
    product_type: ProductType = ProductType.MIS
    validity: Validity = Validity.DAY
    quantity: int = 0
    price: float = 0.0
    trigger_price: float = 0.0

    # Execution Linkage
    order_id: Optional[str] = None              # Internal client_order_id once placed
    broker_order_id: Optional[str] = None      # Broker assigned order number
    status: OrderStatus = OrderStatus.PENDING_VALIDATION
    filled_quantity: int = 0
    average_price: float = 0.0

    # Dependency Routing
    depends_on_leg_index: Optional[int] = None  # Wait for Leg[index] == FILLED before dispatch

    def __post_init__(self) -> None:
        if isinstance(self.side, str):
            try:
                self.side = OrderSide(self.side.upper())
            except ValueError:
                pass
        if isinstance(self.order_type, str):
            try:
                self.order_type = OrderType(self.order_type.upper())
            except ValueError:
                pass
        if isinstance(self.product_type, str):
            try:
                self.product_type = ProductType(self.product_type.upper())
            except ValueError:
                pass
        if isinstance(self.validity, str):
            try:
                self.validity = Validity(self.validity.upper())
            except ValueError:
                pass
        if isinstance(self.status, str):
            try:
                self.status = OrderStatus(self.status.upper())
            except ValueError:
                pass

    def to_dict(self) -> Dict[str, Any]:
        """Convert leg model to dictionary."""
        return {
            "leg_id": self.leg_id,
            "leg_index": self.leg_index,
            "trading_symbol": self.trading_symbol,
            "exchange_segment": self.exchange_segment,
            "instrument_token": self.instrument_token,
            "side": self.side.value if isinstance(self.side, OrderSide) else str(self.side),
            "order_type": self.order_type.value if isinstance(self.order_type, OrderType) else str(self.order_type),
            "product_type": self.product_type.value if isinstance(self.product_type, ProductType) else str(self.product_type),
            "validity": self.validity.value if isinstance(self.validity, Validity) else str(self.validity),
            "quantity": self.quantity,
            "price": round(self.price, 2),
            "trigger_price": round(self.trigger_price, 2),
            "order_id": self.order_id,
            "broker_order_id": self.broker_order_id,
            "status": self.status.value if isinstance(self.status, OrderStatus) else str(self.status),
            "filled_quantity": self.filled_quantity,
            "average_price": round(self.average_price, 2),
            "depends_on_leg_index": self.depends_on_leg_index,
        }


@dataclass
class Basket:
    """Standardized multi-leg Basket and Option Strategy container."""

    basket_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    client_basket_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    basket_idempotency_key: str = ""
    user_id: int = 1
    name: str = ""
    strategy_type: StrategyType = StrategyType.CUSTOM
    strategy_version: str = "V1"
    execution_mode: ExecutionMode = ExecutionMode.DISABLED
    basket_execution_mode: BasketExecutionMode = BasketExecutionMode.SEQUENTIAL
    failure_policy: BasketFailurePolicy = BasketFailurePolicy.ABORT_REMAINING

    # Status & Exposure
    status: BasketState = BasketState.DRAFT
    exposure_state: BasketExposureState = BasketExposureState.NEUTRAL

    # Legs
    legs: List[BasketLeg] = field(default_factory=list)

    # Risk & Capital
    estimated_margin: float = 0.0
    margin_snapshot: Dict[str, Any] = field(default_factory=dict)
    validation_timestamp: Optional[str] = None
    rejection_reason: Optional[str] = None

    # Audit & Dual Timestamps
    source_timestamp: Optional[str] = None
    retrieved_timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if isinstance(self.strategy_type, str):
            try:
                self.strategy_type = StrategyType(self.strategy_type)
            except ValueError:
                pass
        if isinstance(self.execution_mode, str):
            try:
                self.execution_mode = ExecutionMode(self.execution_mode)
            except ValueError:
                pass
        if isinstance(self.basket_execution_mode, str):
            try:
                self.basket_execution_mode = BasketExecutionMode(self.basket_execution_mode)
            except ValueError:
                pass
        if isinstance(self.failure_policy, str):
            try:
                self.failure_policy = BasketFailurePolicy(self.failure_policy)
            except ValueError:
                pass
        if isinstance(self.status, str):
            try:
                self.status = BasketState(self.status)
            except ValueError:
                pass
        if isinstance(self.exposure_state, str):
            try:
                self.exposure_state = BasketExposureState(self.exposure_state)
            except ValueError:
                pass

    def is_terminal(self) -> bool:
        """Return True if basket has reached an irreversible end state."""
        return self.status in (
            BasketState.EXECUTED,
            BasketState.FAILED,
            BasketState.CANCELLED,
        )

    def is_open(self) -> bool:
        """Return True if basket is active or in-flight."""
        return self.status in (
            BasketState.READY,
            BasketState.EXECUTING,
            BasketState.PARTIALLY_EXECUTED,
            BasketState.RECONCILING,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert basket model to dictionary."""
        return {
            "basket_id": self.basket_id,
            "client_basket_id": self.client_basket_id,
            "basket_idempotency_key": self.basket_idempotency_key,
            "user_id": self.user_id,
            "name": self.name,
            "strategy_type": self.strategy_type.value if isinstance(self.strategy_type, StrategyType) else str(self.strategy_type),
            "strategy_version": self.strategy_version,
            "execution_mode": self.execution_mode.value if isinstance(self.execution_mode, ExecutionMode) else str(self.execution_mode),
            "basket_execution_mode": (
                self.basket_execution_mode.value
                if isinstance(self.basket_execution_mode, BasketExecutionMode)
                else str(self.basket_execution_mode)
            ),
            "failure_policy": (
                self.failure_policy.value
                if isinstance(self.failure_policy, BasketFailurePolicy)
                else str(self.failure_policy)
            ),
            "status": self.status.value if isinstance(self.status, BasketState) else str(self.status),
            "exposure_state": (
                self.exposure_state.value
                if isinstance(self.exposure_state, BasketExposureState)
                else str(self.exposure_state)
            ),
            "legs": [leg.to_dict() for leg in self.legs],
            "total_legs": len(self.legs),
            "estimated_margin": round(self.estimated_margin, 2),
            "margin_snapshot": self.margin_snapshot,
            "validation_timestamp": self.validation_timestamp,
            "rejection_reason": self.rejection_reason,
            "source_timestamp": self.source_timestamp,
            "retrieved_timestamp": self.retrieved_timestamp,
            "created_at": round(self.created_at, 3),
            "updated_at": round(self.updated_at, 3),
        }


@dataclass
class BasketEventRecord:
    """Audit record capturing an atomic transition in the Basket lifecycle."""

    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    basket_id: str = ""
    client_basket_id: str = ""
    from_status: str = ""
    to_status: str = ""
    from_exposure: str = ""
    to_exposure: str = ""
    reason: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    source_timestamp: Optional[str] = None
    retrieved_timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "basket_id": self.basket_id,
            "client_basket_id": self.client_basket_id,
            "from_status": self.from_status,
            "to_status": self.to_status,
            "from_exposure": self.from_exposure,
            "to_exposure": self.to_exposure,
            "reason": self.reason,
            "details": self.details,
            "source_timestamp": self.source_timestamp,
            "retrieved_timestamp": self.retrieved_timestamp,
            "timestamp": round(self.timestamp, 3),
        }
