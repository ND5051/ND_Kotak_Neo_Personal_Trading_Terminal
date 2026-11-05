from app.core.feature_flags import FeatureFlags


def test_feature_flags_defaults():
    """Verify default feature flag evaluations."""
    flags = FeatureFlags()
    assert flags.is_enabled("PAPER_TRADING") is True
    assert flags.is_enabled("GTT") is False
    assert flags.is_enabled("SCANNER_ENGINE") is False
    assert flags.is_enabled("STRATEGY_ENGINE") is False
    assert flags.is_enabled("NOTIFICATIONS") is False


def test_feature_flags_toggle():
    """Verify programmatic enable and disable."""
    flags = FeatureFlags()
    flags.enable("GTT")
    assert flags.is_enabled("GTT") is True

    flags.disable("GTT")
    assert flags.is_enabled("GTT") is False


def test_feature_flags_load_dict():
    """Verify loading from config dictionary."""
    flags = FeatureFlags()
    flags.load({"SCANNER_ENGINE": True, "PAPER_TRADING": False})

    assert flags.is_enabled("SCANNER_ENGINE") is True
    assert flags.is_enabled("PAPER_TRADING") is False

