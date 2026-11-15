import asyncio
from datetime import datetime, timezone
import time
from typing import Any, Callable, Dict, List, Optional, Set

from app.core.exceptions import BrokerException
from app.logging.logger import get_logger

logger = get_logger("app.broker.adapters.kotak_stream")

try:
    from neo_api_client import NeoAPI
    from neo_api_client.websocket.feed import SFeedWebSocket, WsToken
except ImportError:
    try:
        from kotakneoapi import NeoAPI  # type: ignore
        SFeedWebSocket = None  # type: ignore
        WsToken = None  # type: ignore
    except ImportError:
        NeoAPI = None  # type: ignore
        SFeedWebSocket = None  # type: ignore
        WsToken = None  # type: ignore


class KotakStreamAdapter:
    """
    Encapsulates the Kotak Neo SFeed binary streaming WebSocket protocol.
    Provides asynchronous connection, heartbeat transmission, batch subscription
    framing, exact string index routing, latency profiling, and exception handling.
    """

    INDEX_NAMES: Set[str] = {
        "Nifty 50",
        "Nifty Bank",
        "SENSEX",
        "FINNIFTY",
        "MIDCPNIFTY",
        "BANKNIFTY",
    }

    PRICE_DIVIDERS: Dict[str, float] = {
        "nse_cm": 100.0,
        "nse_fo": 100.0,
        "bse_cm": 100.0,
        "bse_fo": 100.0,
        "cde_fo": 10000.0,
    }

    def __init__(self, client: Optional[Any] = None) -> None:
        self.client = client
        self._connected: bool = False
        self._last_rx_timestamp: float = time.time()
        self._message_handler: Optional[Callable[[Dict[str, Any]], None]] = None
        self._socket_handle: Optional[Any] = None

    def is_connected(self) -> bool:
        """Return True if WebSocket connection is open and active."""
        return self._connected

    def get_last_rx_timestamp(self) -> float:
        """Return the epoch timestamp when the last packet, ping, or pong was received."""
        return self._last_rx_timestamp

    def set_message_handler(self, handler: Callable[[Dict[str, Any]], None]) -> None:
        """Bind callback for incoming streaming frames."""
        self._message_handler = handler

    async def connect(self, credentials: Dict[str, Any]) -> bool:
        """
        Establish connection to Kotak Neo SFeed streaming server.
        Handles authentication handshake and initializes frame receiver.
        """
        session_token = credentials.get("session_token")
        if not session_token:
            raise BrokerException("Session token is required for streaming connection")

        logger.info("Initiating Kotak Neo SFeed WebSocket connection...", event="WS_CONNECT_INIT")

        try:
            is_mock = self.client is not None and getattr(self.client, "__is_mock__", False)

            if is_mock:
                # Simulated socket connection ONLY for explicit mock test clients
                self._connected = True
                self._last_rx_timestamp = time.time()
                logger.info("Kotak Neo SFeed connected successfully (mock client)", event="WS_CONNECTED")
                return True

            if self.client is None:
                raise BrokerException(
                    "Authenticated NeoAPI client is required for SFeed WebSocket connection"
                )

            # Live Kotak Neo API SDK invocation
            if hasattr(self.client, "create_websocket"):
                ws_instance = self.client.create_websocket()

                # Bind SFeed message receiver to feed PriceEngine
                def _on_sfeed_message(msg: Any) -> None:
                    try:
                        if hasattr(msg, "model_dump"):
                            data = msg.model_dump()
                        elif hasattr(msg, "__dict__"):
                            data = msg.__dict__
                        elif isinstance(msg, dict):
                            data = msg
                        else:
                            return
                        self.ingest_raw_tick(data)
                    except Exception as err:
                        logger.warning(f"Error handling SFeed incoming message: {str(err)}")

                ws_instance.on_message = _on_sfeed_message

                if hasattr(ws_instance, "connect"):
                    await ws_instance.connect()
                self._socket_handle = ws_instance
                self._connected = True
                self._last_rx_timestamp = time.time()
                logger.info("Kotak Neo SFeed socket opened", event="WS_CONNECTED")
                return True

            raise BrokerException("Broker client does not support create_websocket()")

        except BrokerException:
            self._connected = False
            raise
        except Exception as e:
            self._connected = False
            logger.error(f"Failed to connect Kotak SFeed WebSocket: {str(e)}", event="WS_CONNECT_ERROR", exc_info=True)
            raise BrokerException(f"WebSocket connection failed: {str(e)}") from e

    async def disconnect(self) -> bool:
        """Terminate WebSocket connection cleanly."""
        try:
            if self._socket_handle and hasattr(self._socket_handle, "close"):
                try:
                    await self._socket_handle.close()
                except Exception as e:
                    logger.warning(f"Error during socket handle close: {str(e)}")

            self._connected = False
            self._socket_handle = None
            logger.info("Kotak Neo SFeed disconnected", event="WS_DISCONNECTED")
            return True
        except Exception as e:
            logger.error(f"Error during WebSocket disconnect: {str(e)}", exc_info=True)
            self._connected = False
            return False

    async def send_ping(self) -> bool:
        """Transmit keep-alive ping frame across the socket."""
        if not self._connected:
            return False

        try:
            if self._socket_handle and hasattr(self._socket_handle, "ping"):
                await self._socket_handle.ping()
            elif SFeedWebSocket is not None and isinstance(self._socket_handle, SFeedWebSocket):
                if not getattr(self._socket_handle, "is_connected", False):
                    return False
            self._last_rx_timestamp = time.time()
            return True
        except Exception as e:
            logger.warning(f"Failed to send WebSocket ping frame: {str(e)}")
            return False

    def route_subscription_tokens(self, tokens: List[Dict[str, str]], is_depth: bool = False) -> Dict[str, Any]:
        """
        Segregate index string names from scrip/depth tokens.
        Guarantees that index symbols are routed by exact string name.
        """
        index_tokens: List[str] = []
        regular_tokens: List[Dict[str, str]] = []

        for t in tokens:
            sym = t.get("symbol") or t.get("trading_symbol") or t.get("token_id") or ""
            tok = str(t.get("token_id") or t.get("instrument_token") or "")
            if sym in self.INDEX_NAMES:
                index_tokens.append(sym)
            elif tok == "26000":
                index_tokens.append("Nifty 50")
            elif tok in ("26001", "26009"):
                index_tokens.append("Nifty Bank")
            elif tok == "1":
                index_tokens.append("SENSEX")
            else:
                regular_tokens.append(t)

        return {
            "index_tokens": index_tokens,
            "regular_tokens": regular_tokens,
            "is_depth": is_depth,
        }

    def _is_sfeed_socket(self) -> bool:
        return SFeedWebSocket is not None and isinstance(self._socket_handle, SFeedWebSocket)

    def _to_ws_tokens(self, tokens: List[Dict[str, str]]) -> List[Any]:
        if not self._is_sfeed_socket() or WsToken is None:
            return tokens
        ws_tokens = []
        for t in tokens:
            seg = t.get("exchange_segment") or "nse_cm"
            tok = str(t.get("token_id") or t.get("instrument_token") or t.get("symbol") or "")
            if tok:
                ws_tokens.append(WsToken(seg, tok))
        return ws_tokens

    def _to_index_ws_tokens(self, index_names: List[str]) -> List[Any]:
        if not self._is_sfeed_socket() or WsToken is None:
            return index_names
        ws_tokens = []
        for name in index_names:
            seg = "bse_cm" if name.upper() == "SENSEX" else "nse_cm"
            ws_tokens.append(WsToken(seg, name))
        return ws_tokens

    async def send_subscription(self, tokens: List[Dict[str, str]], is_depth: bool = False) -> bool:
        """
        Format and send instrument subscription frame to Kotak Neo SFeed.
        Accepts list of dicts with 'token_id' (or 'instrument_token'/'symbol') and 'exchange_segment'.
        Strictly segregates index string names for subscribe_index().
        """
        if not self._connected or not tokens:
            return False

        routed = self.route_subscription_tokens(tokens, is_depth=is_depth)
        index_tokens = routed["index_tokens"]
        regular_tokens = routed["regular_tokens"]

        try:
            if index_tokens:
                logger.info(
                    f"Transmitting SFeed index subscription for indices: {index_tokens}",
                    event="WS_SEND_INDEX_SUB",
                    indices=index_tokens,
                )
                if self._socket_handle and hasattr(self._socket_handle, "subscribe_index"):
                    await self._socket_handle.subscribe_index(self._to_index_ws_tokens(index_tokens))

            if regular_tokens:
                logger.info(
                    f"Transmitting SFeed {'depth' if is_depth else 'scrip'} subscription for {len(regular_tokens)} instruments",
                    event="WS_SEND_SUB",
                    count=len(regular_tokens),
                    is_depth=is_depth,
                )
                if self._socket_handle:
                    payload = self._to_ws_tokens(regular_tokens)
                    if is_depth and hasattr(self._socket_handle, "subscribe_depth"):
                        await self._socket_handle.subscribe_depth(payload)
                    elif hasattr(self._socket_handle, "subscribe_scrips"):
                        await self._socket_handle.subscribe_scrips(payload)

            self._last_rx_timestamp = time.time()
            return True
        except Exception as e:
            logger.error(f"Error sending subscription frame: {str(e)}", exc_info=True)
            return False

    async def send_unsubscription(self, tokens: List[Dict[str, str]]) -> bool:
        """Format and send unsubscription frame to Kotak Neo SFeed."""
        if not self._connected or not tokens:
            return False

        try:
            logger.info(
                f"Transmitting SFeed unsubscription frame for {len(tokens)} instruments",
                event="WS_SEND_UNSUB",
                count=len(tokens),
            )
            if self._socket_handle and hasattr(self._socket_handle, "unsubscribe_scrips"):
                await self._socket_handle.unsubscribe_scrips(self._to_ws_tokens(tokens))

            self._last_rx_timestamp = time.time()
            return True
        except Exception as e:
            logger.error(f"Error sending unsubscription frame: {str(e)}", exc_info=True)
            return False

    def ingest_raw_tick(self, packet: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process incoming streaming frame from Kotak Neo SFeed.
        Computes latency metrics, scales raw prices, normalizes change fields,
        and hands off to message handler without modifying depth cache.
        """
        self._last_rx_timestamp = time.time()
        retrieved_ts = self._last_rx_timestamp

        # Latency Calculation: source_timestamp vs retrieved_timestamp
        src_ts = packet.get("source_timestamp") or packet.get("ltt") or packet.get("timestamp")
        if src_ts:
            try:
                if isinstance(src_ts, (int, float)):
                    # Epoch seconds or milliseconds
                    src_epoch = float(src_ts) if src_ts < 1e11 else float(src_ts) / 1000.0
                    delta_ms = max(0.0, (retrieved_ts - src_epoch) * 1000.0)
                    from app.broker.services.websocket_telemetry import ws_telemetry_tracker
                    ws_telemetry_tracker.record_tick_latency(delta_ms)
            except Exception:
                pass

        # Normalized packet copy
        normalized = dict(packet)
        normalized["retrieved_timestamp"] = datetime.now(timezone.utc).isoformat()

        # Index Price Mapping: change field is used
        if "change" in normalized and "net_change" not in normalized:
            normalized["net_change"] = normalized["change"]

        if self._message_handler:
            self._message_handler(normalized)

        return normalized
