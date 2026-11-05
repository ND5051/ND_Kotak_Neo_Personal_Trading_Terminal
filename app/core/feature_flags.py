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

