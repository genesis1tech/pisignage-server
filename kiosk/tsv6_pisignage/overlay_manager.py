#!/usr/bin/env python3
"""
Overlay Manager — Server-side API bridge

Replaces the previous tkinter-based overlay with a lightweight HTTP bridge
that POSTs state changes to the piSignage server's overlay API.

The actual overlay rendering now happens inside the piSignage player's
Chromium browser via a custom layout (public/overlay/custom_layout_overlay.html).
The server pushes state changes to the player via socket.io.

State machine (unchanged):
  IDLE -> PROCESSING -> DEPOSIT_WAITING -> PRODUCT_DISPLAY / RECYCLE_FAILURE -> IDLE
  IDLE -> PROCESSING -> NO_MATCH -> IDLE
"""

import enum
import logging
import threading
from typing import Any, Callable, Optional

import requests

logger = logging.getLogger(__name__)


class OverlayState(enum.Enum):
    IDLE = "idle"
    PROCESSING = "processing"
    DEPOSIT_WAITING = "deposit_waiting"
    PRODUCT_DISPLAY = "product_display"
    RECYCLE_FAILURE = "recycle_failure"
    NO_MATCH = "no_match"
    QR_NOT_ALLOWED = "qr_not_allowed"


class OverlayManager:
    """
    Headless overlay manager that communicates with piSignage server overlay API.

    Instead of rendering a tkinter window, it POSTs state changes to:
      POST /api/overlay/:playerid  { state: '...', data: {...} }

    The server then pushes the command to the player's custom layout via socket.io,
    where the in-browser overlay renders it.
    """

    STATE_DURATIONS: dict[OverlayState, float] = {
        OverlayState.NO_MATCH: 5.0,
        OverlayState.QR_NOT_ALLOWED: 5.0,
        OverlayState.PRODUCT_DISPLAY: 10.0,
        OverlayState.RECYCLE_FAILURE: 5.0,
    }

    def __init__(
        self,
        server_url: str,
        player_id: str = "",
        username: str = "",
        password: str = "",
        timeout: float = 5.0,
    ) -> None:
        self._state = OverlayState.IDLE
        self._state_lock = threading.Lock()
        self._server_url = server_url.rstrip("/")
        self._player_id = player_id
        self._auth = (username, password) if username else None
        self._timeout = timeout

        # Callbacks
        self.on_state_change: Optional[
            Callable[[OverlayState, OverlayState], None]
        ] = None

    @property
    def player_id(self) -> str:
        return self._player_id

    @player_id.setter
    def player_id(self, value: str) -> None:
        self._player_id = value

    # ------------------------------------------------------------------
    # State machine
    # ------------------------------------------------------------------

    @property
    def state(self) -> OverlayState:
        with self._state_lock:
            return self._state

    def _transition(self, new_state: OverlayState) -> None:
        with self._state_lock:
            old_state = self._state
            self._state = new_state
        if self.on_state_change:
            try:
                self.on_state_change(old_state, new_state)
            except Exception:
                logger.exception("State change callback error")

    def _push_state(self, state: OverlayState, data: Optional[dict[str, Any]] = None) -> None:
        """Push overlay state to server via REST API (non-blocking)."""
        if not self._player_id:
            logger.warning("No player ID set — cannot push overlay state")
            return

        def _do() -> None:
            try:
                url = f"{self._server_url}/api/overlay/{self._player_id}"
                payload: dict[str, Any] = {"state": state.value}
                if data:
                    payload["data"] = data
                resp = requests.post(
                    url,
                    json=payload,
                    auth=self._auth,
                    timeout=self._timeout,
                )
                if resp.ok:
                    logger.info("Overlay state pushed: %s", state.value)
                else:
                    logger.warning(
                        "Overlay push failed (%d): %s",
                        resp.status_code,
                        resp.text[:200],
                    )
            except requests.RequestException as e:
                logger.warning("Overlay push error: %s", e)

        threading.Thread(target=_do, daemon=True).start()

    # ------------------------------------------------------------------
    # Public API — same interface as the old tkinter OverlayWindowManager
    # ------------------------------------------------------------------

    def setup(self) -> None:
        """No-op for headless mode. Kept for interface compatibility."""
        with self._state_lock:
            self._state = OverlayState.IDLE
        logger.info("OverlayManager ready (headless, API bridge mode)")

    def show_processing(self) -> None:
        self._transition(OverlayState.PROCESSING)
        self._push_state(OverlayState.PROCESSING)

    def show_deposit_waiting(self) -> None:
        self._transition(OverlayState.DEPOSIT_WAITING)
        self._push_state(OverlayState.DEPOSIT_WAITING)

    def show_product_image(
        self,
        image_path: str,
        product_name: str = "",
        duration: float = 10.0,
    ) -> None:
        self._transition(OverlayState.PRODUCT_DISPLAY)
        self._push_state(
            OverlayState.PRODUCT_DISPLAY,
            {
                "productImage": image_path,
                "productName": product_name,
                "duration": duration,
            },
        )

    def show_no_match(self) -> None:
        self._transition(OverlayState.NO_MATCH)
        self._push_state(OverlayState.NO_MATCH)

    def show_qr_not_allowed(self) -> None:
        self._transition(OverlayState.QR_NOT_ALLOWED)
        self._push_state(OverlayState.QR_NOT_ALLOWED)

    def show_recycle_failure(self) -> None:
        self._transition(OverlayState.RECYCLE_FAILURE)
        self._push_state(OverlayState.RECYCLE_FAILURE)

    def hide(self) -> None:
        self._transition(OverlayState.IDLE)
        self._push_state(OverlayState.IDLE)

    def destroy(self) -> None:
        """Clean up — ensure we return to idle."""
        if self._state != OverlayState.IDLE:
            self.hide()


# Backward compatibility alias
OverlayWindowManager = OverlayManager
