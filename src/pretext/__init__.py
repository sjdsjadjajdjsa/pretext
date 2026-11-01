"""pretext: labeled social-engineering simulations for authorized training."""

from .client import Client
from .models import (
    APIError,
    ConfigError,
    EscalationStep,
    PretextError,
    Profile,
    ProfileError,
    RedFlag,
    Settings,
    Simulation,
    load_profile,
    resolve_settings,
)

__version__ = "0.3.0"

__all__ = [
    "APIError",
    "Client",
    "ConfigError",
    "EscalationStep",
    "PretextError",
    "Profile",
    "ProfileError",
    "RedFlag",
    "Settings",
    "Simulation",
    "__version__",
    "load_profile",
    "resolve_settings",
]
