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


class BrokerCircuitBreakerOpenException(BrokerException):
    """Raised when broker circuit breaker is OPEN, failing fast to prevent outage cascade."""

    def __init__(
        self,
        message: str = "Broker circuit breaker is OPEN; request rejected to prevent cascade.",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message=message,
            details=details,
            error_code="CIRCUIT_BREAKER_OPEN",
            status_code=503,
        )


class SubscriptionQuotaExceededException(BrokerException):
    """Raised when subscription count exceeds broker quota limit (e.g. 3,000 scrips)."""

    def __init__(
        self,
        message: str = "Broker subscription quota exceeded (limit: 3,000 scrips).",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message=message,
            details=details,
            error_code="SUBSCRIPTION_QUOTA_EXCEEDED",
            status_code=429,
        )


class IllegalOrderStateTransitionException(ApplicationException):
    """Raised when an illegal order state transition is attempted."""

    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message=message,
            error_code="ILLEGAL_ORDER_STATE_TRANSITION",
            status_code=400,
            details=details,
        )


class OrderValidationException(ValidationException):
    """Raised when pre-flight order syntax or parameter validation fails."""

    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message=message,
            error_code="ORDER_VALIDATION_ERROR",
            details=details,
        )


class OrderRiskException(ApplicationException):
    """Raised when an order violates pre-trade risk controls."""

    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message=message,
            error_code="ORDER_RISK_VIOLATION",
            status_code=400,
            details=details,
        )


class ExecutionModeException(ApplicationException):
    """Raised when order execution is attempted while execution mode is DISABLED."""

    def __init__(
        self,
        message: str = "Order execution is DISABLED. Wire submissions are refused.",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message=message,
            error_code="EXECUTION_MODE_DISABLED",
            status_code=403,
            details=details,
        )


