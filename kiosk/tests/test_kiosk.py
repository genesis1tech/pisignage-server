from unittest.mock import MagicMock, patch

import pytest

from tsv6_pisignage.kiosk import PiSignageKiosk
from tsv6_pisignage.overlay_manager import OverlayState


@pytest.fixture
def kiosk():
    return PiSignageKiosk(
        pisignage_server_url="http://localhost:3000",
        pisignage_user="admin",
        pisignage_password="secret",
        event_images_dir="/tmp/event_images",
    )


@pytest.fixture
def kiosk_no_server():
    return PiSignageKiosk(
        pisignage_server_url="",
        pisignage_user="",
        pisignage_password="",
    )


class TestInit:
    def test_creates_overlay(self, kiosk):
        assert kiosk.overlay is not None

    def test_creates_pisignage_client_when_creds_provided(self, kiosk):
        assert kiosk.pisignage is not None

    def test_no_pisignage_client_without_creds(self, kiosk_no_server):
        assert kiosk_no_server.pisignage is None

    def test_no_image_manager_without_tsv6(self, kiosk):
        assert kiosk.image_manager is None

    def test_aws_manager_stored(self):
        mock_aws = MagicMock()
        k = PiSignageKiosk(aws_manager=mock_aws)
        assert k.aws_manager is mock_aws

    def test_barcode_scanner_default_none(self, kiosk):
        assert kiosk.barcode_scanner is None

    def test_root_default_none(self, kiosk):
        assert kiosk.root is None


class TestSetup:
    @patch("tkinter.Tk")
    @patch("tkinter.Label")
    def test_setup_calls_overlay_setup(self, mock_label, mock_tk, kiosk):
        mock_root = MagicMock()
        mock_tk.return_value = mock_root
        with patch("tsv6_pisignage.kiosk.time.sleep"):
            kiosk.setup()
        assert kiosk.root is mock_root

    @patch("tkinter.Tk")
    @patch("tkinter.Label")
    def test_setup_starts_discovery_async(self, mock_label, mock_tk, kiosk):
        with patch.object(kiosk.pisignage, "discover_player_async") as mock_discover:
            with patch("tsv6_pisignage.kiosk.time.sleep"):
                kiosk.setup()
                mock_discover.assert_called_once()

    @patch("tkinter.Tk")
    @patch("tkinter.Label")
    def test_setup_no_discovery_without_client(
        self, mock_label, mock_tk, kiosk_no_server
    ):
        kiosk_no_server.setup()
        assert kiosk_no_server.root is not None


class TestDisplayCallbacks:
    @staticmethod
    def _setup_kiosk(kiosk_instance):
        mock_root = MagicMock()
        with patch("tkinter.Tk", return_value=mock_root):
            with patch("tkinter.Label", return_value=MagicMock()):
                with patch("tsv6_pisignage.kiosk.time.sleep"):
                    kiosk_instance.setup()
        kiosk_instance.root = mock_root
        kiosk_instance.overlay._image_label = MagicMock()
        kiosk_instance.overlay._text_label = MagicMock()
        return kiosk_instance

    def test_display_processing_image(self, kiosk):
        kiosk = self._setup_kiosk(kiosk)
        kiosk.display_processing_image()
        kiosk.root.after.assert_called()

    def test_display_processing_image_pauses_pisignage(self, kiosk):
        kiosk = self._setup_kiosk(kiosk)
        with patch.object(kiosk.pisignage, "toggle_pause") as mock_pause:
            kiosk.display_processing_image()
            mock_pause.assert_called_once()

    def test_display_processing_image_no_client(self, kiosk_no_server):
        kiosk_no_server = self._setup_kiosk(kiosk_no_server)
        kiosk_no_server.display_processing_image()

    def test_display_no_match_image(self, kiosk):
        kiosk = self._setup_kiosk(kiosk)
        kiosk.display_no_match_image()
        kiosk.root.after.assert_called()

    def test_display_qr_not_allowed_image(self, kiosk):
        kiosk = self._setup_kiosk(kiosk)
        kiosk.display_qr_not_allowed_image()
        kiosk.root.after.assert_called()

    def test_display_deposit_waiting(self, kiosk):
        kiosk = self._setup_kiosk(kiosk)
        kiosk.display_deposit_waiting()
        kiosk.root.after.assert_called()

    def test_hide_deposit_waiting(self, kiosk):
        kiosk = self._setup_kiosk(kiosk)
        kiosk.hide_deposit_waiting()

    def test_display_recycle_failure(self, kiosk):
        kiosk = self._setup_kiosk(kiosk)
        kiosk.display_recycle_failure()
        kiosk.root.after.assert_called()

    def test_display_product_image_with_url_no_image_manager(self, kiosk):
        kiosk = self._setup_kiosk(kiosk)
        kiosk.display_product_image(
            {"productImage": "http://img.jpg", "productName": "Widget"}
        )
        kiosk.root.after.assert_called()

    def test_display_product_image_without_url(self, kiosk):
        kiosk = self._setup_kiosk(kiosk)
        kiosk.display_product_image({"productName": "Widget"})
        kiosk.root.after.assert_called()

    def test_display_product_image_with_image_manager(self, kiosk):
        kiosk = self._setup_kiosk(kiosk)
        kiosk.image_manager = MagicMock()
        kiosk.display_product_image(
            {
                "productImage": "http://img.jpg",
                "productName": "Widget",
            }
        )
        kiosk.image_manager.download_image.assert_called_once()

    def test_display_product_image_download_callback_success(self, kiosk):
        kiosk = self._setup_kiosk(kiosk)
        kiosk.image_manager = MagicMock()

        captured_callback = None

        def capture_download(url, cb):
            nonlocal captured_callback
            captured_callback = cb

        kiosk.image_manager.download_image.side_effect = capture_download
        kiosk.display_product_image(
            {
                "productImage": "http://img.jpg",
                "productName": "Widget",
            }
        )

        assert captured_callback is not None
        captured_callback("/path/to/img.jpg", True)
        kiosk.root.after.assert_called()

    def test_display_product_image_download_callback_failure(self, kiosk):
        kiosk = self._setup_kiosk(kiosk)
        kiosk.image_manager = MagicMock()

        captured_callback = None

        def capture_download(url, cb):
            nonlocal captured_callback
            captured_callback = cb

        kiosk.image_manager.download_image.side_effect = capture_download
        kiosk.display_product_image(
            {
                "productImage": "http://img.jpg",
                "productName": "Widget",
            }
        )

        captured_callback(None, False)
        kiosk.root.after.assert_called()


class TestStartNfc:
    def test_nfc_with_scanner(self, kiosk):
        mock_scanner = MagicMock()
        mock_scanner.nfc_emulator = MagicMock()
        kiosk.barcode_scanner = mock_scanner
        kiosk.start_nfc_for_transaction("https://nfc.example.com/txn123", "txn-123")
        mock_scanner.nfc_emulator.start_emulation_with_url.assert_called_once_with(
            "https://nfc.example.com/txn123", "txn-123"
        )

    def test_nfc_without_scanner(self, kiosk):
        kiosk.barcode_scanner = None
        kiosk.start_nfc_for_transaction("https://nfc.example.com/txn123")

    def test_nfc_without_nfc_emulator(self, kiosk):
        mock_scanner = MagicMock()
        mock_scanner.nfc_emulator = None
        kiosk.barcode_scanner = mock_scanner
        kiosk.start_nfc_for_transaction("https://nfc.example.com/txn123")

    def test_nfc_exception_caught(self, kiosk):
        mock_scanner = MagicMock()
        mock_scanner.nfc_emulator = MagicMock()
        mock_scanner.nfc_emulator.start_emulation_with_url.side_effect = RuntimeError(
            "boom"
        )
        kiosk.barcode_scanner = mock_scanner
        kiosk.start_nfc_for_transaction("https://nfc.example.com/txn123")

    def test_nfc_scanner_no_nfc_attr(self, kiosk):
        mock_scanner = MagicMock(spec=[])
        kiosk.barcode_scanner = mock_scanner
        kiosk.start_nfc_for_transaction("https://nfc.example.com/txn123")


class TestRun:
    @patch("tkinter.Tk")
    @patch("tkinter.Label")
    def test_run_calls_setup_if_needed(self, mock_label, mock_tk, kiosk_no_server):
        mock_root = MagicMock()
        mock_tk.return_value = mock_root
        kiosk_no_server.run()
        mock_root.mainloop.assert_called_once()

    def test_run_raises_when_setup_fails(self, kiosk):
        kiosk.root = None
        with patch.object(kiosk.overlay, "setup", return_value=None):
            with pytest.raises(RuntimeError, match="setup.*failed"):
                kiosk.run()

    @patch("tkinter.Tk")
    @patch("tkinter.Label")
    def test_run_keyboard_interrupt(self, mock_label, mock_tk, kiosk_no_server):
        mock_root = MagicMock()
        mock_root.mainloop.side_effect = KeyboardInterrupt()
        mock_tk.return_value = mock_root
        kiosk_no_server.setup()
        kiosk_no_server.root = mock_root
        kiosk_no_server.run()


class TestCleanup:
    def test_cleanup_destroys_overlay(self, kiosk):
        kiosk.overlay = MagicMock()
        kiosk.cleanup()
        kiosk.overlay.destroy.assert_called_once()

    def test_cleanup_resumes_pisignage_if_not_idle(self, kiosk):
        kiosk.overlay = MagicMock()
        kiosk.overlay.state = OverlayState.PROCESSING
        kiosk.pisignage = MagicMock()
        kiosk.cleanup()
        kiosk.pisignage.toggle_pause.assert_called_once()

    def test_cleanup_does_not_resume_if_idle(self, kiosk):
        kiosk.overlay = MagicMock()
        kiosk.overlay.state = OverlayState.IDLE
        kiosk.pisignage = MagicMock()
        kiosk.cleanup()
        kiosk.pisignage.toggle_pause.assert_not_called()

    def test_cleanup_stops_barcode_scanner(self, kiosk):
        kiosk.overlay = MagicMock()
        mock_scanner = MagicMock()
        kiosk.barcode_scanner = mock_scanner
        kiosk.cleanup()
        mock_scanner.stop_scanning.assert_called_once()

    def test_cleanup_no_barcode_scanner(self, kiosk):
        kiosk.overlay = MagicMock()
        kiosk.barcode_scanner = None
        kiosk.cleanup()

    def test_cleanup_no_pisignage_client(self, kiosk_no_server):
        kiosk_no_server.overlay = MagicMock()
        kiosk_no_server.cleanup()


class TestWatchdog:
    @patch("tkinter.Tk")
    @patch("tkinter.Label")
    def test_setup_sends_ready(self, mock_label, mock_tk, kiosk_no_server):
        import tsv6_pisignage.kiosk as kiosk_mod

        mock_sd = MagicMock()
        kiosk_mod.SYSTEMD_AVAILABLE = True
        kiosk_mod.sd_notify = mock_sd
        try:
            with patch.object(kiosk_no_server, "_start_watchdog_heartbeat"):
                kiosk_no_server.setup()
                mock_sd.assert_any_call("READY=1")
        finally:
            kiosk_mod.SYSTEMD_AVAILABLE = False
            kiosk_mod.sd_notify = None

    @patch("tkinter.Tk")
    @patch("tkinter.Label")
    def test_no_watchdog_without_systemd(self, mock_label, mock_tk, kiosk_no_server):
        with patch("tsv6_pisignage.kiosk.SYSTEMD_AVAILABLE", False):
            kiosk_no_server.setup()

    def test_heartbeat_sends_watchdog(self, kiosk_no_server):
        import tsv6_pisignage.kiosk as kiosk_mod

        notify_calls = []

        def fake_notify(msg):
            notify_calls.append(msg)

        kiosk_mod.SYSTEMD_AVAILABLE = True
        kiosk_mod.sd_notify = fake_notify
        try:
            with patch.dict("os.environ", {"WATCHDOG_USEC": "200000"}):
                kiosk_no_server._start_watchdog_heartbeat()
                import time as t

                t.sleep(0.3)
        finally:
            kiosk_mod.SYSTEMD_AVAILABLE = False
            kiosk_mod.sd_notify = None
        assert "WATCHDOG=1" in notify_calls

    def test_heartbeat_noop_without_env(self, kiosk_no_server):
        import tsv6_pisignage.kiosk as kiosk_mod

        kiosk_mod.SYSTEMD_AVAILABLE = False
        kiosk_mod.sd_notify = None
        with patch.dict("os.environ", {}, clear=True):
            kiosk_no_server._start_watchdog_heartbeat()
            import time as t

            t.sleep(0.05)
        assert True

    def test_heartbeat_handles_notify_error(self, kiosk_no_server):
        import tsv6_pisignage.kiosk as kiosk_mod

        kiosk_mod.SYSTEMD_AVAILABLE = True
        kiosk_mod.sd_notify = MagicMock(side_effect=OSError("fail"))
        try:
            with patch.dict("os.environ", {"WATCHDOG_USEC": "200000"}):
                kiosk_no_server._start_watchdog_heartbeat()
                import time as t

                t.sleep(0.3)
        finally:
            kiosk_mod.SYSTEMD_AVAILABLE = False
            kiosk_mod.sd_notify = None
