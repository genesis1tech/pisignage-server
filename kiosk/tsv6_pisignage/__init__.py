"""TSV6-piSignage Integration — overlay API bridge and piSignage client for recycling kiosks."""

from .overlay_manager import OverlayManager, OverlayState, OverlayWindowManager
from .pisignage_client import PiSignageClient
from .kiosk import PiSignageKiosk

__all__ = [
    "OverlayManager",
    "OverlayWindowManager",  # backward compat alias
    "OverlayState",
    "PiSignageClient",
    "PiSignageKiosk",
]
