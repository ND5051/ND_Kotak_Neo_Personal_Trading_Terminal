"""
Watchlist Management Service.
Phase 5: Market Watch Foundation.
Coordinates multi-watchlist persistence, default watchlist initialization,
quota enforcement (<= 10 lists, <= 50 items/list), and automated SubscriptionManager wire hooks.
"""

from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session as DbSession

from app.broker.services.subscription_manager import (
    SubscriptionManager,
    subscription_manager,
)
from app.core.audit import AuditCategory, audit_logger
from app.core.exceptions import (
    ApplicationException,
    ValidationException,
)
from app.core.request_context import get_correlation_id, get_request_id
from app.events.event_bus import publish
from app.events.event_types import (
    WATCHLIST_CREATED,
    WATCHLIST_DELETED,
    WATCHLIST_ITEM_ADDED,
    WATCHLIST_ITEM_REMOVED,
)
from app.logging.logger import get_logger
from app.market_watch.models.watchlist import Watchlist, WatchlistItem
from app.market_watch.repositories.watchlist_repository import (
    WatchlistRepository,
    watchlist_repository,
)
from app.market_watch.services.price_engine import (
    MarketWatchPriceEngine,
    price_engine,
)

logger = get_logger("app.market_watch.services.watchlist_service")


class WatchlistQuotaExceededException(ApplicationException):
    """Raised when user exceeds allowed watchlist count or scrip count."""

    def __init__(
        self,
        message: str = "Watchlist quota exceeded",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message=message,
            error_code="WATCHLIST_QUOTA_EXCEEDED",
            status_code=400,
            details=details,
        )


class WatchlistService:
    """
    Business service orchestrating user watchlists, scrip management, and live price bindings.
    """

    MAX_WATCHLISTS_PER_USER = 10
    MAX_SCRIPS_PER_WATCHLIST = 50

    def __init__(
        self,
        repository: Optional[WatchlistRepository] = None,
        sub_manager: Optional[SubscriptionManager] = None,
        prices: Optional[MarketWatchPriceEngine] = None,
    ) -> None:
        self.repository = repository or watchlist_repository
        self.sub_manager = sub_manager or subscription_manager
        self.price_engine = prices or price_engine

    def get_user_watchlists(self, user_id: int) -> List[Watchlist]:
        """Fetch all watchlists for user, creating default if none exist."""
        watchlists = self.repository.get_by_user(user_id)
        if not watchlists:
            default_wl = self.ensure_default_watchlist(user_id)
            return [default_wl]
        return watchlists

    def get_watchlists_with_quotes(self, user_id: int) -> List[Dict[str, Any]]:
        """Fetch user watchlists with real-time quotes attached to each instrument item."""
        watchlists = self.get_user_watchlists(user_id)
        result: List[Dict[str, Any]] = []

        for wl in watchlists:
            wl_dict = wl.to_dict(include_items=False)
            items_data: List[Dict[str, Any]] = []

            for item in wl.items:
                item_dict = item.to_dict()
                # Attach real-time quote snapshot from price engine
                quote = self.price_engine.get_quote(
                    item.instrument_token, item.exchange_segment
                )
                item_dict["quote"] = quote.to_dict() if quote else None
                items_data.append(item_dict)

            wl_dict["items"] = items_data
            wl_dict["item_count"] = len(items_data)
            result.append(wl_dict)

        return result

    def create_watchlist(
        self, user_id: int, name: str, is_default: bool = False
    ) -> Watchlist:
        """Create a new user watchlist with quota and uniqueness checks."""
        clean_name = str(name).strip()
        if not clean_name or len(clean_name) < 2:
            raise ValidationException("Watchlist name must be at least 2 characters long")

        count = self.repository.count_by_user(user_id)
        if count >= self.MAX_WATCHLISTS_PER_USER:
            raise WatchlistQuotaExceededException(
                f"Maximum of {self.MAX_WATCHLISTS_PER_USER} watchlists allowed per user"
            )

        existing = self.repository.find_by_name(user_id, clean_name)
        if existing:
            raise ValidationException(f"Watchlist with name '{clean_name}' already exists")

        # Position at the end
        watchlist = Watchlist(
            user_id=user_id,
            name=clean_name,
            position=count,
            is_default=is_default,
        )
        saved = self.repository.add(watchlist)

        logger.info(
            f"Created watchlist '{clean_name}' (id: {saved.id}) for user {user_id}",
            event="WATCHLIST_CREATED",
            watchlist_id=saved.id,
            user_id=user_id,
        )

        publish(
            WATCHLIST_CREATED,
            {"watchlist_id": saved.id, "user_id": user_id, "name": clean_name},
        )

        audit_logger.record(
            category=AuditCategory.BROKER,
            action="WATCHLIST_CREATED",
            actor=f"user_{user_id}",
            correlation_id=get_correlation_id(),
            request_id=get_request_id(),
            details={"watchlist_id": saved.id, "name": clean_name},
        )

        return saved

    def delete_watchlist(self, user_id: int, watchlist_id: int) -> bool:
        """Delete watchlist, automatically unsubscribing orphaned instruments."""
        wl = self.repository.get_by_id(watchlist_id)
        if not wl or wl.user_id != user_id:
            raise ValidationException("Watchlist not found or unauthorized")

        # Unsubscribe child items from streaming
        for item in wl.items:
            try:
                self.sub_manager.unsubscribe(
                    item.instrument_token, item.exchange_segment
                )
            except Exception as e:
                logger.warning(
                    f"Error unsubscribing item {item.instrument_token} during watchlist delete: {str(e)}"
                )

        self.repository.delete(wl)

        logger.info(
            f"Deleted watchlist {watchlist_id} for user {user_id}",
            event="WATCHLIST_DELETED",
            watchlist_id=watchlist_id,
            user_id=user_id,
        )

        publish(
            WATCHLIST_DELETED,
            {"watchlist_id": watchlist_id, "user_id": user_id},
        )

        audit_logger.record(
            category=AuditCategory.BROKER,
            action="WATCHLIST_DELETED",
            actor=f"user_{user_id}",
            correlation_id=get_correlation_id(),
            request_id=get_request_id(),
            details={"watchlist_id": watchlist_id},
        )

        return True

    def add_item(
        self,
        user_id: int,
        watchlist_id: int,
        instrument_token: str,
        exchange_segment: str,
        trading_symbol: str,
        display_name: Optional[str] = None,
    ) -> WatchlistItem:
        """Add an instrument to a watchlist, triggering SubscriptionManager registration."""
        wl = self.repository.get_by_id(watchlist_id)
        if not wl or wl.user_id != user_id:
            raise ValidationException("Watchlist not found or unauthorized")

        token = str(instrument_token).strip()
        segment = str(exchange_segment).strip().lower()
        symbol = str(trading_symbol).strip()

        if not token or not segment or not symbol:
            raise ValidationException("Missing instrument token, exchange segment, or symbol")

        # Quota check
        current_items = len(wl.items)
        if current_items >= self.MAX_SCRIPS_PER_WATCHLIST:
            raise WatchlistQuotaExceededException(
                f"Maximum of {self.MAX_SCRIPS_PER_WATCHLIST} scrips allowed per watchlist"
            )

        # Duplicate check
        existing = self.repository.find_item(watchlist_id, token, segment)
        if existing:
            raise ValidationException(f"Instrument '{symbol}' already in watchlist")

        item = WatchlistItem(
            watchlist_id=watchlist_id,
            instrument_token=token,
            exchange_segment=segment,
            trading_symbol=symbol,
            display_name=display_name or symbol,
            position=current_items,
        )
        saved_item = self.repository.add_item(item)

        # Wire subscription hook
        try:
            self.sub_manager.subscribe(token, segment)
        except Exception as e:
            logger.warning(
                f"Failed to register streaming subscription for {token} ({segment}): {str(e)}",
                event="SUB_WIRE_HOOK_FAILED",
            )

        logger.info(
            f"Added instrument {token} ({symbol}) to watchlist {watchlist_id}",
            event="WATCHLIST_ITEM_ADDED",
            item_id=saved_item.id,
            watchlist_id=watchlist_id,
            token=token,
        )

        publish(
            WATCHLIST_ITEM_ADDED,
            {
                "watchlist_id": watchlist_id,
                "item_id": saved_item.id,
                "instrument_token": token,
                "exchange_segment": segment,
                "trading_symbol": symbol,
            },
        )

        audit_logger.record(
            category=AuditCategory.BROKER,
            action="WATCHLIST_ITEM_ADDED",
            actor=f"user_{user_id}",
            correlation_id=get_correlation_id(),
            request_id=get_request_id(),
            details={"watchlist_id": watchlist_id, "token": token, "symbol": symbol},
        )

        return saved_item

    def remove_item(
        self, user_id: int, watchlist_id: int, item_id: int
    ) -> bool:
        """Remove instrument from watchlist and decrement SubscriptionManager reference count."""
        wl = self.repository.get_by_id(watchlist_id)
        if not wl or wl.user_id != user_id:
            raise ValidationException("Watchlist not found or unauthorized")

        item = self.repository.get_item_by_id(item_id)
        if not item or item.watchlist_id != watchlist_id:
            raise ValidationException("Watchlist item not found")

        token = item.instrument_token
        segment = item.exchange_segment

        self.repository.delete_item(item)

        # Wire unsubscription hook
        try:
            self.sub_manager.unsubscribe(token, segment)
        except Exception as e:
            logger.warning(
                f"Failed to unsubscribe {token} ({segment}) on item removal: {str(e)}"
            )

        logger.info(
            f"Removed item {item_id} ({token}) from watchlist {watchlist_id}",
            event="WATCHLIST_ITEM_REMOVED",
            item_id=item_id,
            watchlist_id=watchlist_id,
            token=token,
        )

        publish(
            WATCHLIST_ITEM_REMOVED,
            {
                "watchlist_id": watchlist_id,
                "item_id": item_id,
                "instrument_token": token,
                "exchange_segment": segment,
            },
        )

        audit_logger.record(
            category=AuditCategory.BROKER,
            action="WATCHLIST_ITEM_REMOVED",
            actor=f"user_{user_id}",
            correlation_id=get_correlation_id(),
            request_id=get_request_id(),
            details={"watchlist_id": watchlist_id, "item_id": item_id, "token": token},
        )

        return True

    def reorder_items(
        self, user_id: int, watchlist_id: int, ordered_item_ids: List[int]
    ) -> bool:
        """Reorder items within a watchlist according to provided list of item IDs."""
        wl = self.repository.get_by_id(watchlist_id)
        if not wl or wl.user_id != user_id:
            raise ValidationException("Watchlist not found or unauthorized")

        item_map = {item.id: item for item in wl.items}
        for idx, item_id in enumerate(ordered_item_ids):
            if item_id in item_map:
                item_map[item_id].position = idx

        self.repository.session.commit()
        return True

    def ensure_default_watchlist(self, user_id: int) -> Watchlist:
        """Create and populate default watchlist with core benchmark instruments if none exists."""
        default_wl = self.repository.get_default(user_id)
        if default_wl:
            return default_wl

        # Create default watchlist
        default_wl = Watchlist(
            user_id=user_id,
            name="Default Watchlist",
            position=0,
            is_default=True,
        )
        saved = self.repository.add(default_wl)

        # Seed core benchmark scrips
        seed_scrips = [
            ("26000", "nse_cm", "Nifty 50", "Nifty 50 Index"),
            ("26001", "nse_cm", "Nifty Bank", "Nifty Bank Index"),
            ("2885", "nse_cm", "RELIANCE-EQ", "Reliance Industries Limited"),
            ("11536", "nse_cm", "TCS-EQ", "Tata Consultancy Services Ltd"),
        ]

        for pos, (token, seg, sym, disp) in enumerate(seed_scrips):
            item = WatchlistItem(
                watchlist_id=saved.id,
                instrument_token=token,
                exchange_segment=seg,
                trading_symbol=sym,
                display_name=disp,
                position=pos,
            )
            self.repository.add_item(item)
            try:
                self.sub_manager.subscribe(token, seg)
            except Exception:
                pass

        logger.info(
            f"Initialized Default Watchlist for user {user_id} with {len(seed_scrips)} benchmark scrips",
            event="DEFAULT_WATCHLIST_INITIALIZED",
            watchlist_id=saved.id,
        )
        return saved


# Global Singleton Watchlist Service
watchlist_service = WatchlistService()
