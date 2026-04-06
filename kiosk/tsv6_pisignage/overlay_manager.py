#!/usr/bin/env python3
"""
Overlay Window Manager for TSV6-piSignage Integration

Manages a tkinter overlay window that sits on top of the piSignage Chromium player.
Hidden during normal operation (piSignage plays videos). Raised instantly when a
barcode is scanned to show event images (processing, product, deposit-waiting, etc.).

State machine:
  IDLE -> PROCESSING -> DEPOSIT_WAITING -> PRODUCT_DISPLAY / RECYCLE_FAILURE -> IDLE
  IDLE -> PROCESSING -> NO_MATCH -> IDLE
"""

import enum
import logging
import subprocess
import threading
import tkinter as tk
from pathlib import Path
from typing import Optional, Callable

try:
    from PIL import Image, ImageTk

    PIL_AVAILABLE = True
    try:
        _LANCZOS = Image.Resampling.LANCZOS
    except AttributeError:
        _LANCZOS = Image.LANCZOS  # type: ignore[attr-defined]  # Pillow < 9.1
except ImportError:
    PIL_AVAILABLE = False
    _LANCZOS = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


class OverlayState(enum.Enum):
    IDLE = "idle"
    PROCESSING = "processing"
    DEPOSIT_WAITING = "deposit_waiting"
    PRODUCT_DISPLAY = "product_display"
    RECYCLE_FAILURE = "recycle_failure"
    NO_MATCH = "no_match"
    QR_NOT_ALLOWED = "qr_not_allowed"


class OverlayWindowManager:
    """
    Manages a fullscreen tkinter overlay window above the piSignage player.

    The window is hidden (withdrawn) when idle and raised to front on barcode events.
    All event images are pre-loaded at startup for instant display (<50ms).
    """

    STATE_DURATIONS: dict[OverlayState, float] = {
        OverlayState.NO_MATCH: 5.0,
        OverlayState.QR_NOT_ALLOWED: 5.0,
        OverlayState.PRODUCT_DISPLAY: 10.0,
        OverlayState.RECYCLE_FAILURE: 5.0,
    }

    FALLBACK_TEXT: dict[str, str] = {
        "processing": "Verifying...",
        "no_match": "Cannot Accept",
        "qr_not_allowed": "QR Not Allowed",
        "deposit_waiting": "Please Deposit Item",
        "recycle_failure": "Item Not Detected",
    }

    def __init__(
        self,
        event_images_dir: str = "event_images",
        screen_width: int = 800,
        screen_height: int = 480,
        mute_audio: bool = True,
    ) -> None:
        self._state = OverlayState.IDLE
        self._state_lock = threading.Lock()
        self._hide_timer: Optional[str] = None  # tkinter after() identifier
        self._event_images_dir = Path(event_images_dir)
        self._screen_width = screen_width
        self._screen_height = screen_height
        self._mute_audio = mute_audio

        # Callbacks
        self.on_state_change: Optional[Callable[[OverlayState, OverlayState], None]] = (
            None
        )

        # Tkinter root and widgets
        self.root: Optional[tk.Tk] = None
        self._image_label: Optional[tk.Label] = None

        # Pre-loaded PhotoImage cache  {name: PhotoImage}
        self._photo_cache: dict[str, "ImageTk.PhotoImage"] = {}

        # Reference holders to prevent GC of PIL Image objects
        self._pil_refs: list["Image.Image"] = []
        self._current_photo: Optional["ImageTk.PhotoImage"] = None

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    def setup(self) -> tk.Tk:
        """
        Create the tkinter root window and pre-load event images.
        Must be called from the main thread before mainloop().
        Returns the root window so the caller can run root.mainloop().
        """
        self.root = tk.Tk()
        self.root.title("TSV6 Overlay")
        self.root.configure(bg="black")
        self.root.geometry(f"{self._screen_width}x{self._screen_height}+0+0")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.config(cursor="none")

        self._image_label = tk.Label(self.root, bg="black", highlightthickness=0)
        self._image_label.place(
            x=0, y=0, width=self._screen_width, height=self._screen_height
        )

        self._text_label = tk.Label(
            self.root,
            bg="black",
            fg="white",
            font=("Helvetica", 36, "bold"),
            wraplength=self._screen_width - 40,
            justify="center",
        )
        self._text_label.place(
            x=0, y=0, width=self._screen_width, height=self._screen_height
        )

        self._preload_images()

        # Start hidden — piSignage is visible underneath
        self.root.withdraw()
        with self._state_lock:
            self._state = OverlayState.IDLE

        logger.info(
            "OverlayWindowManager ready (%dx%d)",
            self._screen_width,
            self._screen_height,
        )
        return self.root

    def _preload_images(self) -> None:
        """Pre-load all event images as PhotoImage objects for instant display."""
        if not PIL_AVAILABLE:
            return

        image_map = {
            "processing": "image_verify.jpg",
            "no_match": "cannot_accept.jpg",
            "qr_not_allowed": "barcode_not_qr.jpg",
            "deposit_waiting": "deposit_waiting.jpg",
            "recycle_failure": "item_not_detected.jpg",
        }

        for name, filename in image_map.items():
            path = self._event_images_dir / filename
            if path.exists():
                try:
                    img = Image.open(str(path)).convert("RGB")
                    img = img.resize(
                        (self._screen_width, self._screen_height), _LANCZOS
                    )
                    photo = ImageTk.PhotoImage(img, master=self.root)
                    self._pil_refs.append(img)  # prevent GC
                    self._photo_cache[name] = photo
                    logger.info("Pre-loaded: %s", filename)
                except Exception:
                    logger.exception("Failed to pre-load %s", filename)
            else:
                logger.warning("Event image not found: %s", path)

        logger.info("Pre-loaded %d event images", len(self._photo_cache))

    # ------------------------------------------------------------------
    # State machine
    # ------------------------------------------------------------------

    @property
    def state(self) -> OverlayState:
        with self._state_lock:
            return self._state

    def _transition(self, new_state: OverlayState) -> None:
        """Transition to a new state, calling the on_state_change callback."""
        with self._state_lock:
            old_state = self._state
            self._state = new_state
        if self.on_state_change:
            try:
                self.on_state_change(old_state, new_state)
            except Exception:
                logger.exception("State change callback error")

    # ------------------------------------------------------------------
    # Public API — called from barcode/AWS threads, schedules on main thread
    # ------------------------------------------------------------------

    def show_processing(self) -> None:
        """Show processing/verification image. Called immediately on barcode scan."""
        if self.root:
            self.root.after(0, self._do_show_processing)

    def show_deposit_waiting(self) -> None:
        """Show deposit waiting screen. Called on openDoor AWS response."""
        if self.root:
            self.root.after(0, self._do_show_deposit_waiting)

    def show_product_image(
        self,
        image_path: str,
        product_name: str = "",
        duration: float = 10.0,
    ) -> None:
        """
        Show downloaded product image. Called after successful deposit verification.
        image_path: local path to the downloaded product image.
        """
        if self.root:
            self.root.after(
                0,
                lambda: self._do_show_product_image(image_path, product_name, duration),
            )

    def show_no_match(self) -> None:
        """Show no-match image. Called on noMatch AWS response."""
        if self.root:
            self.root.after(0, self._do_show_no_match)

    def show_qr_not_allowed(self) -> None:
        """Show QR-not-allowed image. Called when QR code scanned instead of barcode."""
        if self.root:
            self.root.after(0, self._do_show_qr_not_allowed)

    def show_recycle_failure(self) -> None:
        """Show recycle failure image. Called when ToF sensor did not detect item."""
        if self.root:
            self.root.after(0, self._do_show_recycle_failure)

    def hide(self) -> None:
        """Hide overlay and return to IDLE. Safe to call from any thread."""
        if self.root:
            self.root.after(0, self._do_hide)

    # ------------------------------------------------------------------
    # Internal — must run on main thread
    # ------------------------------------------------------------------

    def _raise_overlay(self) -> None:
        """Make the overlay window visible above piSignage."""
        if not self.root:
            return
        self._cancel_hide_timer()
        self.root.deiconify()
        self.root.lift()
        self.root.attributes("-topmost", True)
        self.root.focus_force()
        if self._mute_audio:
            self._set_audio_mute(True)

    def _do_hide(self) -> None:
        """Hide the overlay, returning to piSignage."""
        self._cancel_hide_timer()
        if self.root:
            self.root.withdraw()
        self._current_photo = None
        if self._text_label:
            self._text_label.configure(text="")
        if self._mute_audio:
            self._set_audio_mute(False)
        self._transition(OverlayState.IDLE)

    def _schedule_auto_hide(self, duration: float) -> None:
        """Schedule overlay auto-hide after duration seconds."""
        self._cancel_hide_timer()
        if self.root:
            self._hide_timer = self.root.after(int(duration * 1000), self._do_hide)

    def _cancel_hide_timer(self) -> None:
        if self._hide_timer and self.root:
            self.root.after_cancel(self._hide_timer)
            self._hide_timer = None

    def _show_cached_image(self, cache_key: str) -> None:
        """Display a pre-loaded image from cache, or fall back to text label."""
        photo = self._photo_cache.get(cache_key)
        if photo and self._image_label:
            self._image_label.configure(image=photo)
            self._current_photo = photo
            if self._text_label:
                self._text_label.configure(text="")
                self._image_label.lift()
        elif self._text_label:
            fallback = self.FALLBACK_TEXT.get(cache_key, "")
            self._text_label.configure(text=fallback)
            self._text_label.lift()

    def _do_show_processing(self) -> None:
        self._raise_overlay()
        self._show_cached_image("processing")
        self._transition(OverlayState.PROCESSING)

    def _do_show_deposit_waiting(self) -> None:
        self._raise_overlay()
        self._show_cached_image("deposit_waiting")
        self._transition(OverlayState.DEPOSIT_WAITING)

    def _do_show_product_image(
        self, image_path: str, product_name: str, duration: float
    ) -> None:
        """Load and display a downloaded product image."""
        if not PIL_AVAILABLE or not self._image_label:
            return
        try:
            img = Image.open(image_path).convert("RGB")
            img = img.resize((self._screen_width, self._screen_height), _LANCZOS)
            photo = ImageTk.PhotoImage(img, master=self.root)
            self._pil_refs = [img]  # replace refs with current image only
            self._current_photo = photo
            self._image_label.configure(image=photo)

            self._raise_overlay()
            self._transition(OverlayState.PRODUCT_DISPLAY)
            self._schedule_auto_hide(duration)
        except Exception:
            logger.exception("Failed to display product image")

    def _do_show_no_match(self) -> None:
        self._raise_overlay()
        self._show_cached_image("no_match")
        self._transition(OverlayState.NO_MATCH)
        self._schedule_auto_hide(self.STATE_DURATIONS[OverlayState.NO_MATCH])

    def _do_show_qr_not_allowed(self) -> None:
        self._raise_overlay()
        self._show_cached_image("qr_not_allowed")
        self._transition(OverlayState.QR_NOT_ALLOWED)
        self._schedule_auto_hide(self.STATE_DURATIONS[OverlayState.QR_NOT_ALLOWED])

    def _do_show_recycle_failure(self) -> None:
        self._raise_overlay()
        self._show_cached_image("recycle_failure")
        self._transition(OverlayState.RECYCLE_FAILURE)
        self._schedule_auto_hide(self.STATE_DURATIONS[OverlayState.RECYCLE_FAILURE])

    # ------------------------------------------------------------------
    # Audio control
    # ------------------------------------------------------------------

    @staticmethod
    def _set_audio_mute(mute: bool) -> None:
        """Mute/unmute system audio via amixer (non-blocking)."""
        try:
            cmd = ["amixer", "set", "Master", "mute" if mute else "unmute"]
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except FileNotFoundError:
            pass  # amixer not available (dev machine)

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def destroy(self) -> None:
        """Clean up resources."""
        self._cancel_hide_timer()
        self._photo_cache.clear()
        self._pil_refs.clear()
        self._current_photo = None
        if self.root:
            try:
                self.root.destroy()
            except tk.TclError as e:
                logger.warning("Error destroying overlay window: %s", e)
            self.root = None
