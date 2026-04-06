#!/usr/bin/env python3
"""
piSignage REST API Client

Lightweight client for the self-hosted piSignage server.
Used by TSV6 kiosk to:
  - Discover this player's ID by CPU serial number
  - Pause/resume video playback during barcode flow (optional)
  - Switch playlists remotely

All calls are non-blocking with short timeouts -- failures are non-critical
since the local tkinter overlay handles all latency-sensitive display.
"""

import logging
import threading
import time
from typing import Any, Optional

import requests

logger = logging.getLogger(__name__)


class PiSignageClient:
    """
    Client for the piSignage server REST API.

    Args:
        server_url: Base URL of the piSignage server (e.g. "https://signage.example.com")
        username: HTTP Basic auth username
        password: HTTP Basic auth password
        timeout: Request timeout in seconds (default: 5)
    """

    def __init__(
        self,
        server_url: str,
        username: str,
        password: str,
        timeout: float = 5.0,
    ) -> None:
        self._base_url = server_url.rstrip("/")
        self._timeout = timeout
        self._player_id: Optional[str] = None
        self._player_name: Optional[str] = None
        self._discovery_lock = threading.Lock()
        self._session = requests.Session()
        self._session.auth = (username, password)
        self._session.timeout = timeout

    # ------------------------------------------------------------------
    # Player discovery
    # ------------------------------------------------------------------

    @staticmethod
    def get_cpu_serial() -> str:
        """Read the Raspberry Pi CPU serial number from /proc/cpuinfo."""
        try:
            with open("/proc/cpuinfo", "r") as f:
                for line in f:
                    if line.startswith("Serial"):
                        return line.split(":")[1].strip()
        except (FileNotFoundError, IndexError):
            pass
        return ""

    def discover_player(self) -> Optional[str]:
        """
        Find this Pi's player ID on the piSignage server by matching cpuSerialNumber.
        Thread-safe — concurrent calls will not trigger duplicate network requests.

        Returns:
            Player ID string, or None if not found.
        """
        with self._discovery_lock:
            if self._player_id:
                return self._player_id

            cpu_serial = self.get_cpu_serial()
            if not cpu_serial:
                logger.warning("Could not read CPU serial -- player discovery skipped")
                return None

            try:
                resp = self._session.get(
                    f"{self._base_url}/api/players",
                )
                resp.raise_for_status()
                data = resp.json()

                players = data.get("data", {}).get("objects", [])
                for player in players:
                    if player.get("cpuSerialNumber", "") == cpu_serial:
                        self._player_id = str(player.get("_id", ""))
                        self._player_name = player.get("name", "unknown")
                        logger.info(
                            "Discovered piSignage player: %s (%s)",
                            self._player_name,
                            self._player_id,
                        )
                        return self._player_id

                logger.warning(
                    "No piSignage player found for CPU serial: %s", cpu_serial
                )
                return None

            except requests.RequestException as e:
                logger.warning("piSignage player discovery failed: %s", e)
                return None

    def discover_player_async(
        self, max_retries: int = 5, base_delay: float = 5.0
    ) -> None:
        """
        Discover player in a background thread with exponential backoff.
        Non-blocking — returns immediately, discovery continues until success or max_retries.
        """

        def _retry_loop() -> None:
            for attempt in range(max_retries):
                result = self.discover_player()
                if result:
                    return
                if attempt < max_retries - 1:
                    delay = base_delay * (2**attempt)
                    logger.info(
                        "Player discovery retry %d/%d in %.0fs",
                        attempt + 1,
                        max_retries,
                        delay,
                    )
                    time.sleep(delay)
            logger.warning("Player discovery failed after %d attempts", max_retries)

        threading.Thread(target=_retry_loop, daemon=True).start()

    @property
    def player_id(self) -> Optional[str]:
        return self._player_id

    @player_id.setter
    def player_id(self, value: str) -> None:
        """Allow manual player ID override (e.g. from config)."""
        self._player_id = value

    # ------------------------------------------------------------------
    # Playback control
    # ------------------------------------------------------------------

    def toggle_pause(self) -> None:
        """Toggle pause/resume on this player. piSignage pause is a toggle action."""
        self._playlist_media_action("pause")

    def forward(self) -> None:
        """Skip to next item in playlist."""
        self._playlist_media_action("forward")

    def backward(self) -> None:
        """Go to previous item in playlist."""
        self._playlist_media_action("backward")

    def set_playlist(self, playlist_name: str) -> None:
        """Switch the player to a different playlist."""
        player_id = self._ensure_player_id()
        if not player_id:
            return

        def _do() -> None:
            try:
                resp = self._session.post(
                    f"{self._base_url}/api/setplaylist/{player_id}/{playlist_name}",
                )
                if resp.ok:
                    logger.info("Playlist switched to: %s", playlist_name)
                else:
                    logger.warning("Playlist switch failed: %s", resp.status_code)
            except requests.RequestException as e:
                logger.warning("Playlist switch error: %s", e)

        threading.Thread(target=_do, daemon=True).start()

    def _playlist_media_action(self, action: str) -> None:
        """Send a playlist media action (pause/forward/backward). Non-blocking."""
        player_id = self._ensure_player_id()
        if not player_id:
            return

        def _do() -> None:
            try:
                resp = self._session.post(
                    f"{self._base_url}/api/playlistmedia/{player_id}/{action}",
                )
                if resp.ok:
                    logger.info("piSignage action: %s", action)
                else:
                    logger.warning(
                        "piSignage action %s failed: %s",
                        action,
                        resp.status_code,
                    )
            except requests.RequestException as e:
                logger.warning("piSignage action %s error: %s", action, e)

        threading.Thread(target=_do, daemon=True).start()

    # ------------------------------------------------------------------
    # Player info
    # ------------------------------------------------------------------

    def get_player_status(self) -> Optional[dict[str, Any]]:
        """Get the player's current status from the server."""
        player_id = self._ensure_player_id()
        if not player_id:
            return None

        try:
            resp = self._session.get(
                f"{self._base_url}/api/players/{player_id}",
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("data", {})
        except requests.RequestException as e:
            logger.warning("Failed to get player status: %s", e)
            return None

    # ------------------------------------------------------------------
    # Asset / playlist management
    # ------------------------------------------------------------------

    def list_playlists(self) -> list[dict[str, Any]]:
        """Get all playlists from the server."""
        try:
            resp = self._session.get(
                f"{self._base_url}/api/playlists",
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("data", [])
        except requests.RequestException as e:
            logger.warning("Failed to list playlists: %s", e)
            return []

    def list_assets(self) -> list[dict[str, Any]]:
        """Get all assets from the server."""
        try:
            resp = self._session.get(
                f"{self._base_url}/api/files",
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("data", [])
        except requests.RequestException as e:
            logger.warning("Failed to list assets: %s", e)
            return []

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _ensure_player_id(self) -> Optional[str]:
        """Ensure player ID is available, attempting discovery if needed."""
        if not self._player_id:
            self.discover_player()
        if not self._player_id:
            logger.warning("piSignage player ID not available -- action skipped")
        return self._player_id
