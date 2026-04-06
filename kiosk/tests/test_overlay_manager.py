from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tsv6_pisignage.overlay_manager import OverlayWindowManager, OverlayState


@pytest.fixture
def manager():
    mgr = OverlayWindowManager(
        event_images_dir="/tmp/event_images",
        screen_width=800,
        screen_height=480,
        mute_audio=True,
    )
    return mgr


@pytest.fixture
def setup_manager(manager):
    mock_root = MagicMock()
    mock_label = MagicMock()
    with patch("tkinter.Tk", return_value=mock_root):
        with patch("tkinter.Label", return_value=mock_label):
            manager.setup()
    manager.root = mock_root
    manager._image_label = mock_label
    manager._text_label = MagicMock()
    return manager


class TestInit:
    def test_default_state_is_idle(self, manager):
        assert manager.state == OverlayState.IDLE

    def test_screen_dimensions(self, manager):
        assert manager._screen_width == 800
        assert manager._screen_height == 480

    def test_mute_audio_default(self, manager):
        assert manager._mute_audio is True

    def test_custom_dimensions(self):
        mgr = OverlayWindowManager(screen_width=1920, screen_height=1080)
        assert mgr._screen_width == 1920
        assert mgr._screen_height == 1080


class TestStateTransitions:
    def test_initial_state_idle(self, setup_manager):
        assert setup_manager.state == OverlayState.IDLE

    def test_do_show_processing(self, setup_manager):
        setup_manager._do_show_processing()
        assert setup_manager.state == OverlayState.PROCESSING
        setup_manager.root.deiconify.assert_called()
        setup_manager.root.lift.assert_called()

    def test_do_show_deposit_waiting(self, setup_manager):
        setup_manager._do_show_deposit_waiting()
        assert setup_manager.state == OverlayState.DEPOSIT_WAITING

    def test_do_show_no_match(self, setup_manager):
        setup_manager._do_show_no_match()
        assert setup_manager.state == OverlayState.NO_MATCH
        setup_manager.root.after.assert_called()

    def test_do_show_qr_not_allowed(self, setup_manager):
        setup_manager._do_show_qr_not_allowed()
        assert setup_manager.state == OverlayState.QR_NOT_ALLOWED

    def test_do_show_recycle_failure(self, setup_manager):
        setup_manager._do_show_recycle_failure()
        assert setup_manager.state == OverlayState.RECYCLE_FAILURE

    def test_do_hide_returns_to_idle(self, setup_manager):
        setup_manager._do_show_processing()
        assert setup_manager.state == OverlayState.PROCESSING
        setup_manager._do_hide()
        assert setup_manager.state == OverlayState.IDLE
        setup_manager.root.withdraw.assert_called()

    def test_state_change_callback(self, setup_manager):
        callback = MagicMock()
        setup_manager.on_state_change = callback
        setup_manager._do_show_processing()
        callback.assert_called_once_with(OverlayState.IDLE, OverlayState.PROCESSING)

    def test_state_change_callback_exception_caught(self, setup_manager):
        setup_manager.on_state_change = MagicMock(side_effect=RuntimeError("boom"))
        setup_manager._do_show_processing()
        assert setup_manager.state == OverlayState.PROCESSING


class TestAutoHide:
    def test_no_match_schedules_auto_hide(self, setup_manager):
        setup_manager._do_show_no_match()
        setup_manager.root.after.assert_called()

    def test_product_display_schedules_auto_hide(self, setup_manager):
        with patch.object(setup_manager, "_do_show_product_image"):
            pass
        setup_manager._schedule_auto_hide(10.0)
        setup_manager.root.after.assert_called_with(10000, setup_manager._do_hide)

    def test_cancel_hide_timer(self, setup_manager):
        setup_manager._hide_timer = "timer-id"
        setup_manager._cancel_hide_timer()
        setup_manager.root.after_cancel.assert_called_with("timer-id")
        assert setup_manager._hide_timer is None

    def test_cancel_hide_timer_none(self, setup_manager):
        setup_manager._cancel_hide_timer()

    def test_cancel_timer_on_hide(self, setup_manager):
        setup_manager._hide_timer = "timer-id"
        setup_manager._do_hide()
        setup_manager.root.after_cancel.assert_called_with("timer-id")


class TestShowMethodsScheduleOnMainThread:
    def test_show_processing_schedules(self, setup_manager):
        setup_manager.show_processing()
        setup_manager.root.after.assert_called_with(
            0, setup_manager._do_show_processing
        )

    def test_show_deposit_waiting_schedules(self, setup_manager):
        setup_manager.show_deposit_waiting()
        setup_manager.root.after.assert_called_with(
            0, setup_manager._do_show_deposit_waiting
        )

    def test_show_no_match_schedules(self, setup_manager):
        setup_manager.show_no_match()
        setup_manager.root.after.assert_called_with(0, setup_manager._do_show_no_match)

    def test_show_qr_not_allowed_schedules(self, setup_manager):
        setup_manager.show_qr_not_allowed()
        setup_manager.root.after.assert_called_with(
            0, setup_manager._do_show_qr_not_allowed
        )

    def test_show_recycle_failure_schedules(self, setup_manager):
        setup_manager.show_recycle_failure()
        setup_manager.root.after.assert_called_with(
            0, setup_manager._do_show_recycle_failure
        )

    def test_hide_schedules(self, setup_manager):
        setup_manager.hide()
        setup_manager.root.after.assert_called_with(0, setup_manager._do_hide)

    def test_show_methods_noop_when_no_root(self, manager):
        manager.root = None
        manager.show_processing()
        manager.show_deposit_waiting()
        manager.show_no_match()
        manager.show_qr_not_allowed()
        manager.show_recycle_failure()
        manager.hide()

    def test_show_product_image_schedules(self, setup_manager):
        setup_manager.show_product_image("/path/to/img.jpg", "Product", 10.0)
        setup_manager.root.after.assert_called_once()
        call_args = setup_manager.root.after.call_args
        assert call_args[0][0] == 0


class TestShowCachedImage:
    def test_shows_when_cached(self, setup_manager):
        mock_photo = MagicMock()
        setup_manager._photo_cache["processing"] = mock_photo
        setup_manager._show_cached_image("processing")
        setup_manager._image_label.configure.assert_called_with(image=mock_photo)
        assert setup_manager._current_photo == mock_photo

    def test_noop_when_not_cached(self, setup_manager):
        setup_manager._show_cached_image("nonexistent")
        setup_manager._text_label.configure.assert_called_with(text="")

    def test_noop_when_no_label(self, setup_manager):
        setup_manager._image_label = None
        setup_manager._photo_cache["processing"] = MagicMock()
        setup_manager._show_cached_image("processing")

    def test_shows_fallback_text_when_image_missing(self, setup_manager):
        setup_manager._show_cached_image("processing")
        setup_manager._text_label.configure.assert_called_with(text="Verifying...")
        setup_manager._text_label.lift.assert_called()

    def test_fallback_text_for_all_states(self, setup_manager):
        for key, expected_text in OverlayWindowManager.FALLBACK_TEXT.items():
            setup_manager._text_label.reset_mock()
            setup_manager._show_cached_image(key)
            setup_manager._text_label.configure.assert_called_with(text=expected_text)

    def test_cached_image_hides_text_label(self, setup_manager):
        mock_photo = MagicMock()
        setup_manager._photo_cache["processing"] = mock_photo
        setup_manager._show_cached_image("processing")
        setup_manager._text_label.configure.assert_called_with(text="")
        setup_manager._image_label.lift.assert_called()


class TestDoShowProductImage:
    def test_loads_and_displays_product_image(self, setup_manager):
        with patch("tsv6_pisignage.overlay_manager.PIL_AVAILABLE", True):
            with patch("tsv6_pisignage.overlay_manager.Image") as mock_img:
                mock_image = MagicMock()
                mock_img.open.return_value.convert.return_value.resize.return_value = (
                    mock_image
                )
                with patch("tsv6_pisignage.overlay_manager.ImageTk") as mock_itk:
                    mock_photo = MagicMock()
                    mock_itk.PhotoImage.return_value = mock_photo
                    setup_manager._do_show_product_image("/img.jpg", "Widget", 10.0)
        assert setup_manager.state == OverlayState.PRODUCT_DISPLAY

    def test_handles_exception(self, setup_manager):
        with patch("tsv6_pisignage.overlay_manager.PIL_AVAILABLE", True):
            with patch("tsv6_pisignage.overlay_manager.Image") as mock_img:
                mock_img.open.side_effect = OSError("bad file")
                setup_manager._do_show_product_image("/bad.jpg", "Bad", 5.0)

    def test_noop_when_no_pil(self, setup_manager):
        with patch("tsv6_pisignage.overlay_manager.PIL_AVAILABLE", False):
            setup_manager._do_show_product_image("/img.jpg", "Widget", 10.0)

    def test_noop_when_no_label(self, setup_manager):
        setup_manager._image_label = None
        setup_manager._do_show_product_image("/img.jpg", "Widget", 10.0)


class TestPreloadImages:
    def test_preloads_existing_images(self, manager):
        mock_root = MagicMock()
        with patch("tkinter.Tk", return_value=mock_root):
            with patch("tkinter.Label", return_value=MagicMock()):
                with patch("tsv6_pisignage.overlay_manager.PIL_AVAILABLE", True):
                    with patch("tsv6_pisignage.overlay_manager.Image") as mock_img:
                        with patch("tsv6_pisignage.overlay_manager.ImageTk"):
                            mock_img.LANCZOS = 1
                            mock_image = MagicMock()
                            mock_img.open.return_value.convert.return_value.resize.return_value = mock_image
                            with patch.object(Path, "exists", return_value=True):
                                manager.setup()
        assert len(manager._photo_cache) > 0

    def test_skips_missing_images(self, manager):
        mock_root = MagicMock()
        with patch("tkinter.Tk", return_value=mock_root):
            with patch("tkinter.Label", return_value=MagicMock()):
                with patch("tsv6_pisignage.overlay_manager.PIL_AVAILABLE", True):
                    with patch.object(Path, "exists", return_value=False):
                        manager.setup()
        assert len(manager._photo_cache) == 0


class TestAudioControl:
    @patch("subprocess.Popen")
    def test_mutes_audio(self, mock_popen, setup_manager):
        setup_manager._raise_overlay()
        mock_popen.assert_called()
        call_args = mock_popen.call_args[0][0]
        assert "mute" in call_args

    @patch("subprocess.Popen")
    def test_unmutes_on_hide(self, mock_popen, setup_manager):
        setup_manager._do_hide()
        call_args = mock_popen.call_args[0][0]
        assert "unmute" in call_args

    @patch("subprocess.Popen", side_effect=FileNotFoundError)
    def test_handles_missing_amixer(self, mock_popen, setup_manager):
        setup_manager._raise_overlay()

    def test_no_mute_when_disabled(self):
        mgr = OverlayWindowManager(mute_audio=False)
        mgr.root = MagicMock()
        mgr._image_label = MagicMock()
        mgr._raise_overlay()


class TestRaiseOverlay:
    def test_noop_when_no_root(self, manager):
        manager.root = None
        manager._raise_overlay()

    def test_cancels_existing_timer(self, setup_manager):
        setup_manager._hide_timer = "existing"
        setup_manager._raise_overlay()
        setup_manager.root.after_cancel.assert_called_with("existing")


class TestDestroy:
    def test_destroys_root(self, setup_manager):
        mock_root = setup_manager.root
        setup_manager.destroy()
        mock_root.destroy.assert_called()
        assert setup_manager.root is None

    def test_handles_tcl_error(self, setup_manager):
        import tkinter as tk

        setup_manager.root.destroy.side_effect = tk.TclError("already destroyed")
        setup_manager.destroy()
        assert setup_manager.root is None

    def test_clears_caches(self, setup_manager):
        setup_manager._photo_cache["test"] = MagicMock()
        setup_manager._pil_refs.append(MagicMock())
        setup_manager.destroy()
        assert len(setup_manager._photo_cache) == 0
        assert len(setup_manager._pil_refs) == 0
        assert setup_manager._current_photo is None

    def test_noop_when_no_root(self, manager):
        manager.root = None
        manager.destroy()


class TestOverlayStateEnum:
    def test_all_states(self):
        states = [s.value for s in OverlayState]
        assert "idle" in states
        assert "processing" in states
        assert "deposit_waiting" in states
        assert "product_display" in states
        assert "recycle_failure" in states
        assert "no_match" in states
        assert "qr_not_allowed" in states


class TestStateDurations:
    def test_state_durations_defined(self):
        durations = OverlayWindowManager.STATE_DURATIONS
        assert OverlayState.NO_MATCH in durations
        assert OverlayState.QR_NOT_ALLOWED in durations
        assert OverlayState.PRODUCT_DISPLAY in durations
        assert OverlayState.RECYCLE_FAILURE in durations
        assert durations[OverlayState.NO_MATCH] == 5.0
        assert durations[OverlayState.PRODUCT_DISPLAY] == 10.0
