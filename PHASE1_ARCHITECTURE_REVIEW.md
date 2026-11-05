# Phase 1: Architectural Review Document

## Overview
This document serves as the formal architecture audit record for **Phase 1: Project Skeleton & Architectural Foundation** of the Kotak Neo Personal Trading Terminal. It contains the complete repository structure and source code implementations for the architectural frameworks created.

---

## 1. Repository Structure

```
ND_Kotak_Neo_Personal_Trading_Terminal/
├── .env
├── .env.example
├── .gitignore
├── alembic.ini
├── PHASE1_ARCHITECTURE_REVIEW.md
├── PROJECT_CONSTITUTION.md
├── README.md
├── requirements.txt
├── run.py
│
├── app/
│   ├── __init__.py
│   ├── auth/
│   │   ├── __init__.py
│   │   └── routes.py
│   ├── basket/
│   │   ├── __init__.py
│   │   └── routes.py
│   ├── broker/
│   │   ├── __init__.py
│   │   ├── adapters/
│   │   │   ├── __init__.py
│   │   │   └── base.py
│   │   ├── cache/
│   │   │   └── __init__.py
│   │   └── interfaces/
│   │       ├── __init__.py
│   │       └── broker_interface.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── audit.py
│   │   ├── exceptions.py
│   │   ├── feature_flags.py
│   │   └── response.py
│   ├── dashboard/
│   │   ├── __init__.py
│   │   └── routes.py
│   ├── events/
│   │   ├── __init__.py
│   │   ├── event_bus.py
│   │   └── event_types.py
│   ├── holdings/
│   │   ├── __init__.py
│   │   └── routes.py
│   ├── logging/
│   │   ├── __init__.py
│   │   ├── formatters.py
│   │   └── logger.py
│   ├── market_watch/
│   │   ├── __init__.py
│   │   └── routes.py
│   ├── middleware/
│   │   ├── __init__.py
│   │   ├── error_handler.py
│   │   └── request_logger.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   └── db.py
│   ├── option_chain/
│   │   ├── __init__.py
│   │   └── routes.py
│   ├── orders/
│   │   ├── __init__.py
│   │   └── routes.py
│   ├── paper_trading/
│   │   ├── __init__.py
│   │   └── routes.py
│   ├── positions/
│   │   ├── __init__.py
│   │   └── routes.py
│   ├── repositories/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── holding_repository.py
│   │   ├── order_repository.py
│   │   ├── position_repository.py
│   │   └── watchlist_repository.py
│   ├── risk/
│   │   └── __init__.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── basket_service/
│   │   │   └── __init__.py
│   │   ├── market_data_service/
│   │   │   └── __init__.py
│   │   ├── notification_service/
│   │   │   └── __init__.py
│   │   ├── order_service/
│   │   │   └── __init__.py
│   │   └── portfolio_service/
│   │       └── __init__.py
│   ├── settings/
│   │   ├── __init__.py
│   │   └── routes.py
│   └── websocket/
│       ├── __init__.py
│       └── socket_manager.py
│
├── config/
│   ├── __init__.py
│   ├── base.py
│   ├── development.py
│   ├── production.py
│   └── testing.py
│
├── docs/
│   ├── architecture_decisions.md
│   ├── broker_findings.md
│   ├── known_issues.md
│   ├── lessons_learned.md
│   ├── README.md
│   └── adr/
│       ├── ADR-001-SQLite.md
│       ├── ADR-002-Broker-Adapter.md
│       └── ADR-003-Paper-Trading.md
│
├── migrations/
│   ├── env.py
│   ├── README.md
│   ├── script.py.mako
│   └── versions/
│       └── .gitkeep
│
├── static/
│   ├── css/
│   │   └── style.css
│   └── js/
│       └── main.js
│
├── templates/
│   ├── base.html
│   └── index.html
│
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── integration/
    │   ├── __init__.py
    │   ├── test_app_factory.py
    │   └── test_database.py
    ├── system/
    │   ├── __init__.py
    │   └── test_system_health.py
    └── unit/
        ├── __init__.py
        ├── test_config.py
        ├── test_event_bus.py
        ├── test_exceptions.py
        ├── test_feature_flags.py
        └── test_repositories.py
```

---

## 2. Core Framework (`app/core/`)

### `app/core/__init__.py`
```python
from app.core.exceptions import (
    ApplicationException,
    ValidationException,
    BrokerException,
    ConfigurationException,
)
from app.core.response import api_response, api_error
from app.core.feature_flags import FeatureFlags, feature_flags
from app.core.audit import AuditCategory, AuditRecord, AuditLogger, audit_logger

__all__ = [
    "ApplicationException",
    "ValidationException",
    "BrokerException",
    "ConfigurationException",
    "api_response",
    "api_error",
    "FeatureFlags",
    "feature_flags",
    "AuditCategory",
    "AuditRecord",
    "AuditLogger",
    "audit_logger",
]
```

### `app/core/audit.py`
```python
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import uuid
from typing import Any, Dict, Optional

from app.logging.logger import get_logger

logger = get_logger("app.core.audit")


class AuditCategory(str, Enum):
    """Categories of auditable events per project constitution."""

    AUTH = "AUTH"
    ORDER = "ORDER"
    SESSION = "SESSION"
    BASKET = "BASKET"
    SYSTEM = "SYSTEM"


@dataclass(frozen=True)
class AuditRecord:
    """Immutable audit record structure."""

    category: AuditCategory
    action: str
    actor: str = "system"
    details: Dict[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class AuditLogger:
    """
    Central Audit Framework.
    Guarantees every critical business action has an immutable log trace.
    """

    def record(
        self,
        category: AuditCategory | str,
        action: str,
        actor: str = "system",
        details: Optional[Dict[str, Any]] = None,
    ) -> AuditRecord:
        """Record an audit trail event."""
        cat_enum = (
            category if isinstance(category, AuditCategory) else AuditCategory(str(category).upper())
        )
        record = AuditRecord(
            category=cat_enum,
            action=action,
            actor=actor,
            details=details or {},
        )

        logger.info(
            f"[AUDIT:{cat_enum.value}] {action} by {actor}",
            event="AUDIT_RECORD",
            audit_category=cat_enum.value,
            audit_action=action,
            actor=actor,
            audit_id=record.event_id,
            details=record.details,
        )
        return record


# Global Audit Logger Singleton
audit_logger = AuditLogger()
```

### `app/core/exceptions.py`
```python
from typing import Any, Dict, Optional


class ApplicationException(Exception):
    """Base application exception for all domain and operational errors."""

    def __init__(
        self,
        message: str,
        error_code: str = "APPLICATION_ERROR",
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": "error",
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details,
        }


class ValidationException(ApplicationException):
    """Raised when data validation fails before domain processing."""

    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        error_code: str = "VALIDATION_ERROR",
    ) -> None:
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=400,
            details=details,
        )


class BrokerException(ApplicationException):
    """Raised when an error occurs in downstream broker communications or execution."""

    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        error_code: str = "BROKER_ERROR",
        status_code: int = 502,
    ) -> None:
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=status_code,
            details=details,
        )


class ConfigurationException(ApplicationException):
    """Raised when configuration values are missing, invalid, or inconsistent."""

    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        error_code: str = "CONFIGURATION_ERROR",
    ) -> None:
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=500,
            details=details,
        )
```

### `app/core/feature_flags.py`
```python
from typing import Any, Dict, Optional


class FeatureFlags:
    """Centralized feature flag evaluator and registry."""

    PAPER_TRADING = "PAPER_TRADING"
    GTT = "GTT"
    SCANNER_ENGINE = "SCANNER_ENGINE"
    STRATEGY_ENGINE = "STRATEGY_ENGINE"
    NOTIFICATIONS = "NOTIFICATIONS"

    DEFAULT_FLAGS = {
        PAPER_TRADING: True,
        GTT: False,
        SCANNER_ENGINE: False,
        STRATEGY_ENGINE: False,
        NOTIFICATIONS: False,
    }

    def __init__(self, initial_flags: Optional[Dict[str, bool]] = None) -> None:
        self._flags: Dict[str, bool] = dict(self.DEFAULT_FLAGS)
        if initial_flags:
            self.load(initial_flags)

    def load(self, flags_dict: Dict[str, Any]) -> None:
        """Load or merge flag values from configuration dictionary."""
        for key, value in flags_dict.items():
            normalized_key = key.upper()
            if isinstance(value, bool):
                self._flags[normalized_key] = value
            elif isinstance(value, str):
                self._flags[normalized_key] = value.lower() in ("true", "1", "yes", "on")
            elif isinstance(value, (int, float)):
                self._flags[normalized_key] = bool(value)

    def is_enabled(self, flag_name: str, default: bool = False) -> bool:
        """Check if a specific feature flag is currently active."""
        return self._flags.get(flag_name.upper(), default)

    def enable(self, flag_name: str) -> None:
        """Enable a feature flag in-memory."""
        self._flags[flag_name.upper()] = True

    def disable(self, flag_name: str) -> None:
        """Disable a feature flag in-memory."""
        self._flags[flag_name.upper()] = False

    def get_all(self) -> Dict[str, bool]:
        """Return an immutable snapshot copy of all flags."""
        return dict(self._flags)


# Global Singleton
feature_flags = FeatureFlags()
```

### `app/core/response.py`
```python
from typing import Any, Dict, Optional
from flask import jsonify, Response


def api_response(
    data: Any = None,
    message: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
    status_code: int = 200,
) -> tuple[Response, int]:
    """Generate a consistent, structured success API response."""
    payload: Dict[str, Any] = {
        "status": "success",
        "data": data if data is not None else {},
    }
    if message:
        payload["message"] = message
    if meta:
        payload["meta"] = meta
    return jsonify(payload), status_code


def api_error(
    error_code: str,
    message: str,
    details: Optional[Dict[str, Any]] = None,
    status_code: int = 400,
) -> tuple[Response, int]:
    """Generate a consistent, structured error API response."""
    payload: Dict[str, Any] = {
        "status": "error",
        "error_code": error_code,
        "message": message,
        "details": details or {},
    }
    return jsonify(payload), status_code
```

---

## 3. Events Framework (`app/events/`)

### `app/events/__init__.py`
```python
from app.events.event_bus import (
    EventBus,
    event_bus,
    publish,
    subscribe,
    unsubscribe,
)
from app.events.event_types import (
    Event,
    LOGIN_SUCCESS,
    ORDER_CREATED,
    ORDER_FILLED,
    WEBSOCKET_CONNECTED,
    SYSTEM_INITIALIZED,
    RISK_BREACH_DETECTED,
)

__all__ = [
    "EventBus",
    "event_bus",
    "publish",
    "subscribe",
    "unsubscribe",
    "Event",
    "LOGIN_SUCCESS",
    "ORDER_CREATED",
    "ORDER_FILLED",
    "WEBSOCKET_CONNECTED",
    "SYSTEM_INITIALIZED",
    "RISK_BREACH_DETECTED",
]
```

### `app/events/event_bus.py`
```python
from collections import defaultdict
import threading
from typing import Any, Callable, Dict, List

from app.events.event_types import Event
from app.logging.logger import get_logger

logger = get_logger("app.events.event_bus")


class EventBus:
    """
    Thread-safe in-memory publish-subscribe event broker.
    Ensures safe decoupling between modules without direct cross-dependency.
    """

    def __init__(self) -> None:
        self._subscribers: Dict[str, List[Callable[[Event], None]]] = defaultdict(list)
        self._lock = threading.RLock()

    def subscribe(self, event_type: str, handler: Callable[[Event], None]) -> None:
        """Register a handler callback for a specific event type."""
        with self._lock:
            if handler not in self._subscribers[event_type]:
                self._subscribers[event_type].append(handler)
                logger.debug(
                    f"Subscribed handler '{handler.__name__}' to event '{event_type}'",
                    event="EVENT_SUBSCRIBE",
                    event_type=event_type,
                )

    def unsubscribe(self, event_type: str, handler: Callable[[Event], None]) -> bool:
        """Unregister a handler callback for an event type."""
        with self._lock:
            if event_type in self._subscribers and handler in self._subscribers[event_type]:
                self._subscribers[event_type].remove(handler)
                logger.debug(
                    f"Unsubscribed handler '{handler.__name__}' from event '{event_type}'",
                    event="EVENT_UNSUBSCRIBE",
                    event_type=event_type,
                )
                return True
            return False

    def publish(self, event_type: str, data: Any = None) -> Event:
        """
        Publish an event to all registered subscribers.
        Catches subscriber exceptions to prevent handler failures from corrupting publisher flow.
        """
        payload_data = data if isinstance(data, dict) else {"payload": data}
        event = Event(event_type=event_type, data=payload_data)

        with self._lock:
            handlers = list(self._subscribers.get(event_type, []))

        logger.info(
            f"Dispatching event '{event_type}' to {len(handlers)} handler(s)",
            event="EVENT_DISPATCH",
            event_type=event_type,
            handler_count=len(handlers),
        )

        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(
                    f"Error executing event handler '{handler.__name__}' for '{event_type}': {str(e)}",
                    event="EVENT_HANDLER_ERROR",
                    exc_info=True,
                    event_type=event_type,
                )

        return event

    def clear(self) -> None:
        """Remove all subscriptions (primarily used for unit test teardown)."""
        with self._lock:
            self._subscribers.clear()


# Default Global Singleton EventBus
event_bus = EventBus()


# Shorthand API
def publish(event_name: str, data: Any = None) -> Event:
    return event_bus.publish(event_name, data)


def subscribe(event_name: str, handler: Callable[[Event], None]) -> None:
    event_bus.subscribe(event_name, handler)


def unsubscribe(event_name: str, handler: Callable[[Event], None]) -> bool:
    return event_bus.unsubscribe(event_name, handler)
```

### `app/events/event_types.py`
```python
from dataclasses import dataclass, field
from datetime import datetime, timezone
import uuid
from typing import Any, Dict


# Predefined Event Constants for Future Expansion
ORDER_CREATED = "ORDER_CREATED"
ORDER_FILLED = "ORDER_FILLED"
LOGIN_SUCCESS = "LOGIN_SUCCESS"
WEBSOCKET_CONNECTED = "WEBSOCKET_CONNECTED"
SYSTEM_INITIALIZED = "SYSTEM_INITIALIZED"
RISK_BREACH_DETECTED = "RISK_BREACH_DETECTED"


@dataclass(frozen=True)
class Event:
    """Immutable event payload container."""

    event_type: str
    data: Dict[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
```

---

## 4. Logging Framework (`app/logging/`)

### `app/logging/__init__.py`
```python
from app.logging.logger import AppLogger, get_logger, setup_logging
from app.logging.formatters import JSONFormatter

__all__ = ["AppLogger", "get_logger", "setup_logging", "JSONFormatter"]
```

### `app/logging/formatters.py`
```python
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict


class JSONFormatter(logging.Formatter):
    """
    Structured JSON log formatter conforming to:
    {
        "timestamp": "...",
        "event": "...",
        "module": "...",
        "level": "...",
        "message": "..."
    }
    """

    def format(self, record: logging.LogRecord) -> str:
        # Standard timestamp format ISO 8601 UTC
        timestamp = datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat()

        # Extract event name from record attributes or fallback to record funcName / GENERAL
        event_name = getattr(record, "event", None)
        if not event_name:
            event_name = getattr(record, "event_name", "GENERAL")

        log_payload: Dict[str, Any] = {
            "timestamp": timestamp,
            "event": str(event_name),
            "module": record.name,
            "level": record.levelname,
            "message": record.getMessage(),
        }

        # Include exception traceback if present
        if record.exc_info:
            log_payload["exception"] = self.formatException(record.exc_info)

        # Include any additional extra attributes passed by caller
        extra_data = getattr(record, "extra_data", None)
        if isinstance(extra_data, dict):
            log_payload["details"] = extra_data

        return json.dumps(log_payload, default=str)
```

### `app/logging/logger.py`
```python
import os
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Optional

from app.logging.formatters import JSONFormatter


class AppLogger:
    """Wrapper around standard Python logging to enforce structured log payloads."""

    def __init__(self, logger: logging.Logger):
        self._logger = logger

    @property
    def name(self) -> str:
        return self._logger.name

    def _log(
        self,
        level: int,
        message: str,
        event: Optional[str] = None,
        exc_info: bool = False,
        **extra: Any,
    ) -> None:
        extra_dict = {
            "event": event or "SYSTEM",
            "extra_data": extra if extra else None,
        }
        self._logger.log(level, message, exc_info=exc_info, extra=extra_dict)

    def debug(self, message: str, event: Optional[str] = None, **extra: Any) -> None:
        self._log(logging.DEBUG, message, event=event, **extra)

    def info(self, message: str, event: Optional[str] = None, **extra: Any) -> None:
        self._log(logging.INFO, message, event=event, **extra)

    def warning(self, message: str, event: Optional[str] = None, **extra: Any) -> None:
        self._log(logging.WARNING, message, event=event, **extra)

    def error(self, message: str, event: Optional[str] = None, exc_info: bool = False, **extra: Any) -> None:
        self._log(logging.ERROR, message, event=event, exc_info=exc_info, **extra)

    def critical(self, message: str, event: Optional[str] = None, exc_info: bool = True, **extra: Any) -> None:
        self._log(logging.CRITICAL, message, event=event, exc_info=exc_info, **extra)


def setup_logging(
    log_level: str = "INFO",
    log_dir: Optional[Path | str] = None,
    log_filename: str = "terminal.log",
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
) -> None:
    """Initialize system-wide structured logging with rotating file and console handlers."""
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    formatter = JSONFormatter()

    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Avoid adding duplicate handlers on multiple setup calls
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    # Console Handler (stdout/stderr)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File Handler with Rotation (if directory is specified or defaults to logs/)
    if log_dir is not None:
        target_dir = Path(log_dir)
        target_dir.mkdir(parents=True, exist_ok=True)
        file_path = target_dir / log_filename

        file_handler = RotatingFileHandler(
            file_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)


def get_logger(name: str) -> AppLogger:
    """Obtain a structured logger for a specific module."""
    return AppLogger(logging.getLogger(name))
```

---

## 5. Repository Framework (`app/repositories/`)

### `app/repositories/__init__.py`
```python
from app.repositories.base import BaseRepository
from app.repositories.order_repository import OrderRepository
from app.repositories.watchlist_repository import WatchlistRepository
from app.repositories.position_repository import PositionRepository
from app.repositories.holding_repository import HoldingRepository

__all__ = [
    "BaseRepository",
    "OrderRepository",
    "WatchlistRepository",
    "PositionRepository",
    "HoldingRepository",
]
```

### `app/repositories/base.py`
```python
from typing import Generic, List, Optional, Type, TypeVar
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.base import BaseModel
from app.models.db import db_session

T = TypeVar("T", bound=BaseModel)


class BaseRepository(Generic[T]):
    """
    Generic Base Repository providing standardized CRUD operations
    following the Repository Pattern and Data Mapper architecture.
    """

    def __init__(self, model_class: Type[T], session: Optional[Session] = None) -> None:
        self.model_class = model_class
        self._session_override = session

    @property
    def session(self) -> Session:
        """Obtain current active session (either custom or scoped session)."""
        if self._session_override is not None:
            return self._session_override
        if db_session is None:
            raise RuntimeError("Database session not initialized. Call init_db() first.")
        return db_session()

    def get_by_id(self, entity_id: int) -> Optional[T]:
        """Fetch a single record by its primary key."""
        stmt = select(self.model_class).where(self.model_class.id == entity_id)
        return self.session.execute(stmt).scalar_one_or_none()

    def list_all(self, limit: int = 100, offset: int = 0) -> List[T]:
        """Fetch records with pagination."""
        stmt = select(self.model_class).offset(offset).limit(limit)
        return list(self.session.execute(stmt).scalars().all())

    def add(self, entity: T) -> T:
        """Persist a new entity to the database."""
        self.session.add(entity)
        self.session.commit()
        self.session.refresh(entity)
        return entity

    def update(self, entity: T) -> T:
        """Update and commit modifications to an existing entity."""
        self.session.commit()
        self.session.refresh(entity)
        return entity

    def delete(self, entity: T) -> None:
        """Remove an entity from the database."""
        self.session.delete(entity)
        self.session.commit()

    def count(self) -> int:
        """Count total entities in table."""
        stmt = select(func.count()).select_from(self.model_class)
        return self.session.execute(stmt).scalar_one() or 0
```

### `app/repositories/order_repository.py`
```python
from typing import Optional
from sqlalchemy.orm import Session
from app.repositories.base import BaseRepository


class OrderRepository(BaseRepository):
    """Repository skeleton for Order persistence and state recovery."""

    def __init__(self, session: Optional[Session] = None) -> None:
        # Model class will be injected in Phase 2 / Phase 3 once domain models are defined
        super().__init__(model_class=None, session=session)  # type: ignore
```

### `app/repositories/watchlist_repository.py`
```python
from typing import Optional
from sqlalchemy.orm import Session
from app.repositories.base import BaseRepository


class WatchlistRepository(BaseRepository):
    """Repository skeleton for Watchlist and Market Watch symbol sets."""

    def __init__(self, session: Optional[Session] = None) -> None:
        super().__init__(model_class=None, session=session)  # type: ignore
```

### `app/repositories/position_repository.py`
```python
from typing import Optional
from sqlalchemy.orm import Session
from app.repositories.base import BaseRepository


class PositionRepository(BaseRepository):
    """Repository skeleton for Trading Position persistence and snapshot reconciliation."""

    def __init__(self, session: Optional[Session] = None) -> None:
        super().__init__(model_class=None, session=session)  # type: ignore
```

### `app/repositories/holding_repository.py`
```python
from typing import Optional
from sqlalchemy.orm import Session
from app.repositories.base import BaseRepository


class HoldingRepository(BaseRepository):
    """Repository skeleton for Demat / Long-term Holding portfolio storage."""

    def __init__(self, session: Optional[Session] = None) -> None:
        super().__init__(model_class=None, session=session)  # type: ignore
```

---

## 6. Configuration Framework (`config/`)

### `config/__init__.py`
```python
import os
from typing import Type

from config.base import BaseConfig
from config.development import DevelopmentConfig
from config.testing import TestingConfig
from config.production import ProductionConfig

CONFIG_MAP = {
    "development": DevelopmentConfig,
    "dev": DevelopmentConfig,
    "testing": TestingConfig,
    "test": TestingConfig,
    "production": ProductionConfig,
    "prod": ProductionConfig,
}


def get_config(env_name: str | None = None) -> Type[BaseConfig]:
    """Retrieve the configuration class matching the requested environment."""
    target_env = (env_name or os.getenv("APP_ENV", "development")).lower()
    return CONFIG_MAP.get(target_env, DevelopmentConfig)


__all__ = [
    "BaseConfig",
    "DevelopmentConfig",
    "TestingConfig",
    "ProductionConfig",
    "get_config",
]
```

### `config/base.py`
```python
import os
from pathlib import Path
from dotenv import load_dotenv

# Base directory of the repository
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env if present
load_dotenv(BASE_DIR / ".env")


class BaseConfig:
    """Base Configuration with default settings and environment fallbacks."""

    APP_ENV = os.getenv("APP_ENV", "development").lower()
    SECRET_KEY = os.getenv("SECRET_KEY", "insecure-default-key-change-in-prod")

    # Paths
    BASE_DIR = BASE_DIR
    DATA_DIR = BASE_DIR / "data"
    LOG_DIR = BASE_DIR / os.getenv("LOG_DIR", "logs")

    # Database
    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{BASE_DIR / 'data' / 'kotak_terminal.db'}"
    )

    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

    # Feature Flags Framework Defaults
    FEATURE_FLAGS = {
        "PAPER_TRADING": os.getenv("FEATURE_PAPER_TRADING", "true").lower() in ("true", "1", "yes"),
        "GTT": os.getenv("FEATURE_GTT", "false").lower() in ("true", "1", "yes"),
        "SCANNER_ENGINE": os.getenv("FEATURE_SCANNER_ENGINE", "false").lower() in ("true", "1", "yes"),
        "STRATEGY_ENGINE": os.getenv("FEATURE_STRATEGY_ENGINE", "false").lower() in ("true", "1", "yes"),
        "NOTIFICATIONS": os.getenv("FEATURE_NOTIFICATIONS", "false").lower() in ("true", "1", "yes"),
    }

    # Security & Server defaults
    TESTING = False
    DEBUG = False
    JSON_SORT_KEYS = False
```

### `config/development.py`
```python
from config.base import BaseConfig


class DevelopmentConfig(BaseConfig):
    """Configuration for local development."""

    DEBUG = True
    APP_ENV = "development"
    LOG_LEVEL = "DEBUG"
```

### `config/testing.py`
```python
from config.base import BaseConfig


class TestingConfig(BaseConfig):
    """Configuration for automated test execution."""

    TESTING = True
    DEBUG = False
    APP_ENV = "testing"
    DATABASE_URL = "sqlite:///:memory:"
    LOG_LEVEL = "WARNING"

    FEATURE_FLAGS = {
        "PAPER_TRADING": True,
        "GTT": True,
        "SCANNER_ENGINE": True,
        "STRATEGY_ENGINE": True,
        "NOTIFICATIONS": True,
    }
```

### `config/production.py`
```python
import os
from config.base import BaseConfig


class ProductionConfig(BaseConfig):
    """Configuration for production environment."""

    DEBUG = False
    TESTING = False
    APP_ENV = "production"
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
```

---

## 7. `requirements.txt`
```txt
Flask>=3.0.0
Flask-SocketIO>=5.3.6
SQLAlchemy>=2.0.0
alembic>=1.13.0
python-dotenv>=1.0.0
pytest>=8.0.0
```

---

## 8. `run.py`
```python
import os
from app import create_app
from app.websocket.socket_manager import socket_manager
from app.logging.logger import get_logger

logger = get_logger("run")

app = create_app()

if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", 5000))
    debug = app.config.get("DEBUG", False)

    logger.info(
        f"Starting Kotak Neo Personal Trading Terminal on http://{host}:{port}",
        event="SERVER_START",
        host=host,
        port=port,
        debug=debug,
    )

    if socket_manager.socketio is not None:
        socket_manager.socketio.run(app, host=host, port=port, debug=debug)
    else:
        app.run(host=host, port=port, debug=debug)
```

---

## 9. `PROJECT_CONSTITUTION.md`
```markdown
# PROJECT CONSTITUTION: Kotak Neo Personal Trading Terminal

## Core Architecture Principles
The following architectural hierarchy is non-negotiable for all design, implementation, and operations:

```
Correctness > Features
Reliability > Speed
Recovery    > Elegance
Auditability> Convenience
State Consistency > Performance
```

---

## Non-Negotiable Tenets (Rules 1 to 10)

### Rule 1: No direct broker SDK calls outside Broker Adapter
Direct calls to the Kotak Neo API SDK (`kotakneoapi` / `neo-api-client` or any underlying HTTP/WebSocket endpoints) are strictly forbidden across UI, services, routes, or strategies. All communication must pass through an explicit implementation of `BrokerInterface` inside `app/broker/adapters/`.

### Rule 2: All order actions must pass through Order Engine
No module may place, modify, or cancel orders directly with the adapter. All order requests must go through the Order Engine and Order Service, undergoing state validation, risk validation, and audit recording.

### Rule 3: All critical actions must be auditable
Every state-altering operation—including authentication, order placement, order modification, order cancellation, risk boundary breach, system startup, and recovery—must be persistently logged via the Audit Framework (`app/core/audit.py`).

### Rule 4: All features require tests
No code reaches production without accompanying automated unit tests and integration tests covering positive paths, boundary conditions, and catastrophic failure modes.

### Rule 5: Every phase requires rollback instructions
Every development phase, migration, and deployment must come with explicit, tested rollback instructions to revert state safely without data loss or orphan orders.

### Rule 6: Every phase updates `lessons_learned.md`
At the conclusion of each development phase, architectural findings, unexpected behavior, and broker-specific idiosyncrasies must be documented in `docs/lessons_learned.md`.

### Rule 7: No phase proceeds without approval
Work proceeds strictly in gated phases. No subsequent phase may be started or suggested until the current phase is fully reviewed, tested, and explicitly approved by the system owner.

### Rule 8: State recovery is mandatory
The system must be capable of reconstructing its complete in-memory portfolio, open order state, and position state from local persistence and broker reconciliation upon restart or unhandled crash.

### Rule 9: Trading safety overrides convenience
Fail-safe mechanisms, kill switches, and circuit breakers take precedence over user convenience or uninterrupted execution. When in doubt or during state divergence, the system must halt new order flow and protect capital.

### Rule 10: Paper and Live trading must share architecture
Paper trading and live trading must execute through identical interfaces, pipelines, data contracts, and risk checks. Paper trading differs only by routing execution through a simulated broker adapter rather than the live broker adapter.

---

## Phase Lifecycle & Governance
- **Phase 1**: Project Skeleton Specification & Architectural Foundation
- **Phase Gate**: Verification of tests, linters, application startup, and architectural compliance.
- **Sign-off**: Explicit user approval required prior to embarking on Phase 2.
```
