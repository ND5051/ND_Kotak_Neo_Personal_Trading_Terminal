from app.core.exceptions import (
    ApplicationException,
    ValidationException,
    BrokerException,
    ConfigurationException,
)


def test_application_exception_defaults():
    exc = ApplicationException("Base application error")
    assert exc.status_code == 500
    assert exc.error_code == "APPLICATION_ERROR"
    payload = exc.to_dict()
    assert payload["status"] == "error"
    assert payload["message"] == "Base application error"


def test_validation_exception():
    exc = ValidationException("Invalid price", details={"field": "price"})
    assert exc.status_code == 400
    assert exc.error_code == "VALIDATION_ERROR"
    assert exc.details == {"field": "price"}


def test_broker_exception():
    exc = BrokerException("Order rejected by broker", details={"reason": "MARGIN_INSUFFICIENT"})
    assert exc.status_code == 502
    assert exc.error_code == "BROKER_ERROR"


def test_configuration_exception():
    exc = ConfigurationException("Missing API key")
    assert exc.status_code == 500
    assert exc.error_code == "CONFIGURATION_ERROR"

