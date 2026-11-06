from datetime import datetime, timezone
import threading
from typing import Any, Dict, Optional, Set

from app.baskets.models.basket import Basket, BasketState
from app.baskets.repositories.basket_repository import (
    BasketRepositoryInterface,
    basket_repository,
)
from app.core.audit import (
    audit_logger,
    AuditCategory,
    AUDIT_BASKET_CANCELLED,
    AUDIT_BASKET_FAILED,
    AUDIT_BASKET_RECONCILIATION,
)
from app.core.exceptions import IllegalBasketStateTransitionException
from app.core.request_context import get_correlation_id, get_request_id
from app.events.event_bus import publish
from app.events.event_types import (
    BASKET_CANCELLED,
    BASKET_COMPLETED,
    BASKET_CREATED,
    BASKET_EXECUTION_STARTED,
    BASKET_FAILED,
    BASKET_RECONCILING,
    BASKET_VALIDATED,
)
from app.logging.logger import get_logger

logger = get_logger("app.baskets.services.state_machine")


class BasketStateMachine:
    """
    Finite State Machine governing Basket lifecycle.
    Guarantees strict state transitions and prevents terminal state corruption.
    """

    LEGAL_TRANSITIONS: Dict[BasketState, Set[BasketState]] = {
        BasketState.DRAFT: {
            BasketState.VALIDATED,
            BasketState.CANCELLED,
        },
        BasketState.VALIDATED: {
            BasketState.READY,
            BasketState.FAILED,
            BasketState.CANCELLED,
        },
        BasketState.READY: {
            BasketState.EXECUTING,
            BasketState.CANCELLED,
        },
        BasketState.EXECUTING: {
            BasketState.EXECUTED,
            BasketState.PARTIALLY_EXECUTED,
            BasketState.FAILED,
            BasketState.RECONCILING,
        },
        BasketState.PARTIALLY_EXECUTED: {
            BasketState.CANCELLED,
            BasketState.RECONCILING,
        },
        BasketState.RECONCILING: {
            BasketState.EXECUTED,
            BasketState.PARTIALLY_EXECUTED,
            BasketState.FAILED,
        },
        BasketState.EXECUTED: set(),
        BasketState.FAILED: set(),
        BasketState.CANCELLED: set(),
    }

    def __init__(self, repository: Optional[BasketRepositoryInterface] = None) -> None:
        self.repository = repository or basket_repository
        self._lock = threading.RLock()

    def transition_to(
        self,
        basket: Basket,
        target_state: BasketState,
        reason: str = "",
        details: Optional[Dict[str, Any]] = None,
    ) -> Basket:
        """
        Transition basket to target_state with legal boundary enforcement,
        audit logging, and event bus notification.
        """
        with self._lock:
            current_state = basket.status

            # Idempotent no-op
            if current_state == target_state:
                return basket

            # Check legality
            allowed = self.LEGAL_TRANSITIONS.get(current_state, set())
            if target_state not in allowed:
                err_msg = (
                    f"Illegal basket state transition from {current_state.value} to {target_state.value} "
                    f"for basket {basket.client_basket_id}."
                )
                logger.error(err_msg, event="ILLEGAL_BASKET_TRANSITION")
                raise IllegalBasketStateTransitionException(
                    message=err_msg,
                    details={
                        "basket_id": basket.basket_id,
                        "client_basket_id": basket.client_basket_id,
                        "current_state": current_state.value,
                        "target_state": target_state.value,
                        "allowed_targets": [s.value for s in allowed],
                    },
                )

            # Mutate state
            basket.status = target_state
            if reason:
                basket.rejection_reason = reason if target_state == BasketState.FAILED else basket.rejection_reason

            # Record transition
            try:
                self.repository.record_transition(
                    basket_id=basket.basket_id,
                    client_basket_id=basket.client_basket_id,
                    from_status=current_state.value,
                    to_status=target_state.value,
                    from_exposure=basket.exposure_state.value,
                    to_exposure=basket.exposure_state.value,
                    reason=reason,
                    details=details or {},
                    source_timestamp=basket.source_timestamp,
                )
            except Exception as e:
                logger.warning(
                    f"Failed to record basket transition event: {str(e)}",
                    event="BASKET_EVENT_LOG_FAIL",
                )

            # Publish event
            self._publish_transition_event(basket, target_state, reason, details)

            logger.info(
                f"Basket {basket.client_basket_id} transitioned: {current_state.value} -> {target_state.value} ({reason})",
                event="BASKET_STATE_TRANSITION",
            )
            return basket

    def _publish_transition_event(
        self,
        basket: Basket,
        target_state: BasketState,
        reason: str,
        details: Optional[Dict[str, Any]],
    ) -> None:
        event_map = {
            BasketState.VALIDATED: BASKET_VALIDATED,
            BasketState.EXECUTING: BASKET_EXECUTION_STARTED,
            BasketState.EXECUTED: BASKET_COMPLETED,
            BasketState.FAILED: BASKET_FAILED,
            BasketState.CANCELLED: BASKET_CANCELLED,
            BasketState.RECONCILING: BASKET_RECONCILING,
        }
        evt_type = event_map.get(target_state)
        if evt_type:
            publish(
                evt_type,
                {
                    "basket_id": basket.basket_id,
                    "client_basket_id": basket.client_basket_id,
                    "status": target_state.value,
                    "exposure_state": basket.exposure_state.value,
                    "reason": reason,
                    "details": details or {},
                },
            )


# Global singleton
basket_state_machine = BasketStateMachine()

