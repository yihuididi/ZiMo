"""Concrete rulesets."""

from .singapore import (
    SingaporeRules,
    UnsupportedConfigurationError,
    rules_for_version,
)

__all__ = ["SingaporeRules", "UnsupportedConfigurationError", "rules_for_version"]
