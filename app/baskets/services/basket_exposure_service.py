from typing import Optional

from app.baskets.models.basket import Basket, BasketExposureState, StrategyType
from app.orders.models.order import OrderStatus


class BasketExposureService:
    """
    Evaluates multi-leg portfolio risk and financial hedging state.
    Decoupled from lifecycle state (BasketState) to provide clear visibility
    into directional delta and unhedged leg exposure.
    """

    def compute_exposure_state(self, basket: Basket) -> BasketExposureState:
        """
        Evaluate current leg statuses and determine authoritative BasketExposureState.
        """
        if not basket.legs:
            return BasketExposureState.NEUTRAL

        filled_legs = [l for l in basket.legs if l.status == OrderStatus.FILLED]
        reconciling_legs = [l for l in basket.legs if l.status == OrderStatus.RECONCILING]
        rejected_or_failed = [
            l for l in basket.legs if l.status in (OrderStatus.REJECTED, OrderStatus.FAILED, OrderStatus.CANCELLED)
        ]
        pending_or_working = [
            l for l in basket.legs
            if l.status in (OrderStatus.PENDING_VALIDATION, OrderStatus.VALIDATED, OrderStatus.SUBMITTED, OrderStatus.ACKNOWLEDGED)
        ]

        total_legs = len(basket.legs)

        # 1. Zero fills anywhere
        if len(filled_legs) == 0:
            if len(reconciling_legs) > 0:
                # Wire is in flight or disconnected; outcome unknown
                return BasketExposureState.UNKNOWN
            # No legs executed or in unconfirmed state
            return BasketExposureState.NEUTRAL

        # 2. All legs are completely filled
        if len(filled_legs) == total_legs:
            return BasketExposureState.FULLY_HEDGED

        # 3. Some legs filled, some reconciling
        if len(filled_legs) > 0 and len(reconciling_legs) > 0:
            return BasketExposureState.PARTIALLY_EXPOSED

        # 4. Some legs filled, others rejected/failed/cancelled or unexecuted
        if len(filled_legs) > 0 and (len(rejected_or_failed) > 0 or len(pending_or_working) > 0):
            return BasketExposureState.PARTIALLY_EXPOSED

        # Default fallback
        return BasketExposureState.PARTIALLY_EXPOSED

    def update_exposure_state(self, basket: Basket) -> BasketExposureState:
        """Compute and mutate basket.exposure_state."""
        new_state = self.compute_exposure_state(basket)
        basket.exposure_state = new_state
        return new_state


# Global singleton
basket_exposure_service = BasketExposureService()

