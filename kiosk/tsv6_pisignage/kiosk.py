#!/usr/bin/env python3
"""
PiSignageKiosk -- Main integration class

Replaces TSV6's EnhancedVideoPlayer. piSignage handles all video/image playback.
This class manages:
  - Barcode scanning (reuses TSV6 OptimizedBarcodeScanner)
  - AWS IoT MQTT (reuses TSV6 ResilientAWSManager)
  - Tkinter overlay for barcode flow images (OverlayWindowManager)
  - piSignage API for optional pause/resume (PiSignageClient)
  - NFC emulator, servo control, ToF sensor (unchanged from TSV6)

Usage:
    This module is meant to be imported by TSV6's production_main.py as a
    drop-in replacement for EnhancedVideoPlayer. The overlay_manager and
    pisignage_client modules must be on PYTHONPATH (or installed).
"""

import logging
import threading
import time
import tkinter as tk
from typing import Any, Optional

from .overlay_manager import OverlayWindowManager, OverlayState
from .pisignage_client import PiSignageClient

# TSV6 imports -- these come from the tsrpi5 codebase on the Pi.
# They're imported at runtime; if unavailable, features degrade gracefully.
try:
    from tsv6.core.image_manager import ImageManager

    IMAGE_MANAGER_AVAILABLE = True
except ImportError:
    IMAGE_MANAGER_AVAILABLE = False

logger = logging.getLogger(__name__)


class PiSignageKiosk:
    """
    Drop-in replacement for TSV6 EnhancedVideoPlayer.

    piSignage handles video playback. This class provides the same interface
    that production_main.py expects for barcode flow callbacks.
    """

    def __init__(
        self,
        aws_manager: Any = None,
        memory_optimizer: Any = None,
        pisignage_server_url: str = "",
        pisignage_user: str = "",
        pisignage_password: str = "",
        event_images_dir: str = "event_images",
        screen_width: int = 800,
        screen_height: int = 480,
        mute_audio_on_overlay: bool = True,
    ) -> None:
        # Overlay manager (local tkinter, <50ms latency)
        self.overlay = OverlayWindowManager(
            event_images_dir=event_images_dir,
            screen_width=screen_width,
            screen_height=screen_height,
            mute_audio=mute_audio_on_overlay,
        )

        # piSignage API client (remote, non-critical)
        self.pisignage: Optional[PiSignageClient] = None
        if pisignage_server_url and pisignage_user and pisignage_password:
            self.pisignage = PiSignageClient(
                server_url=pisignage_server_url,
                username=pisignage_user,
                password=pisignage_password,
            )

        # Image manager for downloading product images
        self.image_manager: Any = ImageManager() if IMAGE_MANAGER_AVAILABLE else None

        # AWS manager reference (injected by production_main.py)
        self.aws_manager: Any = aws_manager
        self.memory_optimizer: Any = memory_optimizer

        # The tkinter root -- set after setup()
        self.root: Optional[tk.Tk] = None

        # Barcode scanner -- will be set by production_main.py or caller
        self.barcode_scanner: Any = None

    # ------------------------------------------------------------------
    # Setup -- called from main thread
    # ------------------------------------------------------------------

    def setup(self) -> None:
        """
        Initialize the overlay window and discover piSignage player.
        Must be called from the main thread.
        """
        self.root = self.overlay.setup()

        # Discover piSignage player in background
        if self.pisignage:
            threading.Thread(
                target=self._discover_pisignage_player,
                daemon=True,
            ).start()

        logger.info("PiSignageKiosk setup complete")

    def _discover_pisignage_player(self) -> None:
        """Background task to discover this Pi's player on the piSignage server."""
        time.sleep(10)
        if self.pisignage:
            player_id = self.pisignage.discover_player()
            if player_id:
                logger.info("piSignage player discovered: %s", player_id)
            else:
                logger.warning(
                    "piSignage player not found -- remote control disabled"
                )

    # ------------------------------------------------------------------
    # Display callbacks -- same interface as EnhancedVideoPlayer
    # ------------------------------------------------------------------

    def display_processing_image(self) -> None:
        """Show processing overlay. Called immediately after barcode published to AWS."""
        self.overlay.show_processing()
        if self.pisignage:
            self.pisignage.toggle_pause()

    def display_product_image(self, product_data: dict[str, Any]) -> None:
        """
        Display product image from AWS openDoor response.

        Args:
            product_data: Dict with productImage, productName, productBrand, nfcUrl, etc.
        """
        image_url = product_data.get("productImage")
        product_name = product_data.get("productName", "Product")

        if not image_url:
            logger.warning("No product image URL -- hiding overlay")
            self.overlay.hide()
            return

        if self.image_manager:

            def on_image_ready(image_path: Any, success: bool) -> None:
                if success and image_path:
                    self.overlay.show_product_image(str(image_path), product_name)
                else:
                    logger.warning("Product image download failed")
                    self.overlay.hide()

            self.image_manager.download_image(image_url, on_image_ready)
        else:
            self.overlay.hide()

    def display_no_match_image(self) -> None:
        """Show no-match overlay. Called on noMatch AWS response."""
        self.overlay.show_no_match()

    def display_qr_not_allowed_image(self) -> None:
        """Show QR-not-allowed overlay. Called when QR code scanned."""
        self.overlay.show_qr_not_allowed()

    def display_deposit_waiting(self) -> None:
        """Show deposit waiting screen. Called after openDoor before door opens."""
        self.overlay.show_deposit_waiting()

    def hide_deposit_waiting(self) -> None:
        """Hide deposit waiting -- next show_* call replaces the image."""
        pass

    def display_recycle_failure(self) -> None:
        """Show recycle failure overlay. Called when ToF sensor did not detect item."""
        self.overlay.show_recycle_failure()

    def start_nfc_for_transaction(
        self, nfc_url: str, transaction_id: str = ""
    ) -> None:
        """
        Start NFC URL broadcasting for a transaction.
        Delegates to barcode_scanner's NFC emulator if available.
        """
        if (
            self.barcode_scanner
            and hasattr(self.barcode_scanner, "nfc_emulator")
            and self.barcode_scanner.nfc_emulator
        ):
            try:
                self.barcode_scanner.nfc_emulator.start_emulation_with_url(
                    nfc_url, transaction_id
                )
                display_id = transaction_id[:8] if transaction_id else "N/A"
                logger.info(
                    "NFC broadcasting URL: %s... (txn: %s)",
                    nfc_url[:50],
                    display_id,
                )
            except Exception:
                logger.exception("NFC emulation failed")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def run(self) -> None:
        """
        Start the kiosk main loop.
        Blocks on tkinter mainloop -- call from the main thread.
        """
        if self.root is None:
            self.setup()

        if self.root is None:
            raise RuntimeError("setup() failed -- root window not created")

        logger.info("=" * 60)
        logger.info("TSV6-piSignage Kiosk -- RUNNING")
        logger.info("piSignage handles video playback")
        logger.info("Barcode scanning active")
        logger.info("AWS IoT integration active")
        logger.info("=" * 60)

        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            self.cleanup()

    def cleanup(self) -> None:
        """Clean up all resources."""
        logger.info("Cleaning up PiSignageKiosk...")

        # Resume piSignage video if it was paused
        if self.pisignage and self.overlay.state != OverlayState.IDLE:
            self.pisignage.toggle_pause()

        self.overlay.destroy()

        if self.barcode_scanner and hasattr(self.barcode_scanner, "stop_scanning"):
            self.barcode_scanner.stop_scanning()

        logger.info("PiSignageKiosk stopped")
