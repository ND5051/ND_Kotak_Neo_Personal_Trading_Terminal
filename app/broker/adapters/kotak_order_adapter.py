from abc import ABC, abstractmethod
from datetime import datetime, timezone
import random
import threading
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from app.core.exceptions import BrokerException
from app.logging.logger import get_logger

if TYPE_CHECKING:
    from app.orders.models.order import Order

logger = get_logger("app.broker.adapters.kotak_order")

try:
    from kotakneoapi import NeoAPI
except ImportError:
    try:
        from neo_api_client import NeoAPI  # type: ignore
    except ImportError:
        NeoAPI = None  # type: ignore


class KotakOrderAdapterInterface(ABC):
    """Abstract interface defining the Kotak Neo broker order execution contracts."""

    @abstractmethod
    def place_order(self, order: Order, credentials: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Submit a new order across the wire to the Kotak Neo gateway."""
        pass

    @abstractmethod
    def modify_order(
        self,
        order: Order,
        modifications: Dict[str, Any],
        credentials: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Amend price, quantity, or trigger price of an active order."""
        pass

    @abstractmethod
    def cancel_order(self, order: Order, credentials: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Cancel an open or trigger-pending order resting on the exchange."""
        pass

    @abstractmethod
    def get_order_report(
        self, broker_order_id: str, credentials: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Query execution report for a specific broker order number."""
        pass

    @abstractmethod
    def get_order_book(self, credentials: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Retrieve daily order book from Kotak Neo."""
        pass

    @abstractmethod
    def get_trade_book(self, credentials: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Retrieve daily trade book (executed fills) from Kotak Neo."""
        pass

    def register_simulated_order(
        self, broker_order_id: str, quantity: int, price: float, status: str = "complete"
    ) -> None:
        """Register a simulated or paper order for execution report tracking."""
        pass


class KotakOrderAdapter(KotakOrderAdapterInterface):
    """
    Production Kotak Neo Broker Order Execution Adapter.
    Translates internal Order domain models to Kotak Neo SDK payloads,
    normalizes polymorphic SDK responses, and provides simulated fallbacks.
    """

    def __init__(self, client: Optional[Any] = None) -> None:
        self.client = client
        self._simulated_orders: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()

    def register_simulated_order(
        self, broker_order_id: str, quantity: int, price: float, status: str = "complete"
    ) -> None:
        """Register a simulated or paper order for execution report tracking."""
        with self._lock:
            self._simulated_orders[str(broker_order_id)] = {
                "nOrdNo": str(broker_order_id),
                "ordSt": status,
                "avgPrc": str(price if price > 0 else 100.0),
                "fldQty": str(quantity),
                "rejRsn": "",
            }

    def _is_mock(self) -> bool:
        if self.client is None:
            return True
        return getattr(self.client, "__is_mock__", False) or (NeoAPI is None)

    # 1. Place Order
    def place_order(self, order: Order, credentials: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Submit a new order across the wire to Kotak Neo.
        Maps order types, transaction types, and formats price ticks.
        """
        side_val = getattr(order.side, "value", str(order.side)).upper()
        type_val = getattr(order.order_type, "value", str(order.order_type)).upper()
        prod_val = getattr(order.product_type, "value", str(order.product_type))
        valid_val = getattr(order.validity, "value", str(order.validity))

        logger.info(
            f"Dispatching wire order {order.client_order_id} for {order.trading_symbol} ({side_val} {order.quantity} @ {order.price})",
            event="WIRE_ORDER_DISPATCH",
            client_order_id=order.client_order_id,
            symbol=order.trading_symbol,
            side=side_val,
        )

        # Wire Mapping
        tx_type = "B" if side_val == "BUY" else "S"
        order_type_map = {
            "MARKET": "MKT",
            "LIMIT": "L",
            "SL": "SL",
            "SL_M": "SL-M",
            "SL-M": "SL-M",
        }
        neo_order_type = order_type_map.get(type_val, "L")
        price_str = "0" if type_val == "MARKET" else f"{order.price:.2f}"
        trigger_price_str = f"{order.trigger_price:.2f}" if order.trigger_price else "0"

        payload = {
            "exchange_segment": order.exchange_segment,
            "product": prod_val,
            "price": price_str,
            "order_type": neo_order_type,
            "quantity": str(order.quantity),
            "validity": valid_val,
            "trading_symbol": order.trading_symbol,
            "transaction_type": tx_type,
            "trigger_price": trigger_price_str,
            "disclosed_quantity": str(order.disclosed_quantity or 0),
            "tag": order.client_order_id[:20],  # Kotak tag length ceiling
        }

        if self._is_mock():
            time.sleep(0.03)  # Simulate brief network round-trip
            mock_order_no = f"26{datetime.now().strftime('%m%d%H%M%S')}{random.randint(100, 999)}"
            self.register_simulated_order(
                mock_order_no,
                quantity=int(order.quantity),
                price=float(order.price or 2450.05),
                status="complete",
            )
            logger.info(f"Simulated order placement: {mock_order_no}", event="WIRE_ORDER_MOCK_SUCCESS")
            return {
                "stat": "Ok",
                "nOrdNo": mock_order_no,
                "rejection_reason": None,
                "message": "Order placed successfully (simulated)",
                "raw_response": {"stat": "Ok", "nOrdNo": mock_order_no},
            }

        try:
            raw_response = self.client.place_order(**payload)
            normalized = self._normalize_placement_response(raw_response)
            logger.info("Order placement response received", event="WIRE_ORDER_RESPONSE", response=normalized)
            return normalized
        except Exception as e:
            logger.error(f"Error during order placement: {str(e)}", exc_info=True, event="WIRE_ORDER_ERROR")
            raise BrokerException(f"Kotak Neo order placement failed: {str(e)}") from e

    # 2. Modify Order
    def modify_order(
        self,
        order: Order,
        modifications: Dict[str, Any],
        credentials: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Amend price, quantity, or trigger price of an existing open order."""
        if not order.broker_order_id:
            raise BrokerException("Cannot modify order without a broker_order_id")

        logger.info(
            f"Modifying broker order {order.broker_order_id}: {modifications}",
            event="WIRE_ORDER_MODIFY",
            broker_order_id=order.broker_order_id,
        )

        side_val = getattr(order.side, "value", str(order.side)).upper()
        type_val = getattr(order.order_type, "value", str(order.order_type)).upper()
        prod_val = getattr(order.product_type, "value", str(order.product_type))
        valid_val = getattr(order.validity, "value", str(order.validity))

        order_type_map = {
            "MARKET": "MKT",
            "LIMIT": "L",
            "SL": "SL",
            "SL_M": "SL-M",
            "SL-M": "SL-M",
        }
        neo_order_type = order_type_map.get(type_val, "L")

        payload = {
            "order_id": str(order.broker_order_id),
            "exchange_segment": order.exchange_segment,
            "product": prod_val,
            "order_type": neo_order_type,
            "validity": valid_val,
            "trading_symbol": order.trading_symbol,
            "transaction_type": "B" if side_val == "BUY" else "S",
            "price": f"{float(modifications.get('price', order.price)):.2f}",
            "quantity": str(int(modifications.get("quantity", order.quantity))),
            "trigger_price": f"{float(modifications.get('trigger_price', order.trigger_price)):.2f}",
        }

        if self._is_mock():
            time.sleep(0.02)
            return {
                "stat": "Ok",
                "nOrdNo": order.broker_order_id,
                "message": "Order modified successfully (simulated)",
                "raw_response": {"stat": "Ok", "nOrdNo": order.broker_order_id},
            }

        try:
            raw_response = self.client.modify_order(**payload)
            return self._normalize_placement_response(raw_response)
        except Exception as e:
            logger.error(f"Error during order modification: {str(e)}", exc_info=True, event="WIRE_MODIFY_ERROR")
            raise BrokerException(f"Kotak Neo order modification failed: {str(e)}") from e

    # 3. Cancel Order
    def cancel_order(self, order: Order, credentials: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Cancel an open or trigger-pending order resting on the exchange."""
        if not order.broker_order_id:
            raise BrokerException("Cannot cancel order without a broker_order_id")

        logger.info(
            f"Cancelling broker order {order.broker_order_id}",
            event="WIRE_ORDER_CANCEL",
            broker_order_id=order.broker_order_id,
        )

        if self._is_mock():
            time.sleep(0.02)
            return {
                "stat": "Ok",
                "nOrdNo": order.broker_order_id,
                "message": "Order cancelled successfully (simulated)",
                "raw_response": {"stat": "Ok", "nOrdNo": order.broker_order_id},
            }

        try:
            raw_response = self.client.cancel_order(
                order_id=str(order.broker_order_id),
                exchange_segment=order.exchange_segment,
            )
            return self._normalize_placement_response(raw_response)
        except Exception as e:
            logger.error(f"Error during order cancellation: {str(e)}", exc_info=True, event="WIRE_CANCEL_ERROR")
            raise BrokerException(f"Kotak Neo order cancellation failed: {str(e)}") from e

    # 4. Get Order Report
    def get_order_report(
        self, broker_order_id: str, credentials: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Query execution report for a specific broker order number."""
        with self._lock:
            if str(broker_order_id) in self._simulated_orders:
                return [dict(self._simulated_orders[str(broker_order_id)])]

        if self._is_mock():
            # Default simulated report for unregistered mock lookups
            return [
                {
                    "nOrdNo": str(broker_order_id),
                    "ordSt": "complete",
                    "avgPrc": "2450.05",
                    "fldQty": "1",
                    "rejRsn": "",
                }
            ]

        try:
            report = self.client.order_report(order_id=str(broker_order_id))
            records: List[Dict[str, Any]] = []
            if isinstance(report, list):
                records = report
            elif isinstance(report, dict):
                extracted = report.get("data") or report.get("result") or []
                records = [extracted] if isinstance(extracted, dict) else extracted
            return records
        except Exception as e:
            logger.warning(f"Error fetching order report for {broker_order_id}: {str(e)}")
            return []

    # 5. Order Book
    def get_order_book(self, credentials: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Retrieve daily order book from Kotak Neo."""
        if self._is_mock():
            return []
        try:
            resp = self.client.order_report()
            if isinstance(resp, list):
                return resp
            if isinstance(resp, dict):
                extracted = resp.get("data") or resp.get("result") or []
                return [extracted] if isinstance(extracted, dict) else extracted
            return []
        except Exception as e:
            logger.error(f"Error fetching order book: {str(e)}", exc_info=True)
            raise BrokerException(f"Failed to fetch broker order book: {str(e)}") from e

    # 6. Trade Book
    def get_trade_book(self, credentials: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Retrieve daily trade book (executed fills) from Kotak Neo."""
        if self._is_mock():
            return []
        try:
            resp = self.client.trade_report()
            if isinstance(resp, list):
                return resp
            if isinstance(resp, dict):
                extracted = resp.get("data") or resp.get("result") or []
                return [extracted] if isinstance(extracted, dict) else extracted
            return []
        except Exception as e:
            logger.error(f"Error fetching trade book: {str(e)}", exc_info=True)
            raise BrokerException(f"Failed to fetch broker trade book: {str(e)}") from e

    # Internal normalization
    def _normalize_placement_response(self, raw_resp: Any) -> Dict[str, Any]:
        """Normalize polymorphic Kotak Neo SDK response into consistent dictionary."""
        if not isinstance(raw_resp, dict):
            return {"stat": "Not_Ok", "nOrdNo": None, "message": str(raw_resp), "raw_response": raw_resp}

        stat = raw_resp.get("stat") or ("Ok" if raw_resp.get("nOrdNo") else "Not_Ok")
        n_ord_no = raw_resp.get("nOrdNo") or raw_resp.get("ordNo") or raw_resp.get("order_id")
        rejection_reason = raw_resp.get("rejRsn") or raw_resp.get("errMsg") or raw_resp.get("cancelRejectReason") or ""

        return {
            "stat": stat,
            "nOrdNo": str(n_ord_no) if n_ord_no else None,
            "rejection_reason": str(rejection_reason) if rejection_reason else None,
            "raw_response": raw_resp,
        }


# Global singleton instance
kotak_order_adapter = KotakOrderAdapter()
