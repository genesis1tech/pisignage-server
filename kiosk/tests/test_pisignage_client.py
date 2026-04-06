import time
from unittest.mock import MagicMock, patch

import pytest
import requests

from tsv6_pisignage.pisignage_client import PiSignageClient


@pytest.fixture
def client():
    c = PiSignageClient(
        server_url="http://localhost:3000",
        username="admin",
        password="secret",
        timeout=3.0,
    )
    return c


def _mock_players_response(players):
    resp = MagicMock()
    resp.ok = True
    resp.status_code = 200
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {"data": {"objects": players}}
    return resp


class TestInit:
    def test_strips_trailing_slash(self):
        c = PiSignageClient("http://host/", "u", "p")
        assert c._base_url == "http://host"

    def test_creates_session(self, client):
        assert client._session is not None
        assert client._session.auth == ("admin", "secret")

    def test_default_timeout(self):
        c = PiSignageClient("http://host", "u", "p")
        assert c._timeout == 5.0

    def test_custom_timeout(self):
        c = PiSignageClient("http://host", "u", "p", timeout=10)
        assert c._timeout == 10

    def test_initial_state(self, client):
        assert client.player_id is None
        assert client._player_name is None


class TestGetCpuSerial:
    @patch("builtins.open", side_effect=FileNotFoundError)
    def test_returns_empty_when_no_cpuinfo(self, mock_open):
        assert PiSignageClient.get_cpu_serial() == ""

    @patch("builtins.open")
    def test_extracts_serial(self, mock_open):
        mock_open.return_value.__enter__ = MagicMock(
            return_value=[
                "processor\t: 0\n",
                "Serial\t\t: 1234abcd\n",
            ]
        )
        mock_open.return_value.__exit__ = MagicMock(return_value=False)
        result = PiSignageClient.get_cpu_serial()
        assert result == "1234abcd"

    @patch("builtins.open")
    def test_returns_empty_when_no_serial_line(self, mock_open):
        mock_open.return_value.__enter__ = MagicMock(
            return_value=[
                "processor\t: 0\n",
                "model name\t: ARMv7\n",
            ]
        )
        mock_open.return_value.__exit__ = MagicMock(return_value=False)
        assert PiSignageClient.get_cpu_serial() == ""


class TestDiscoverPlayer:
    @patch.object(PiSignageClient, "get_cpu_serial", return_value="")
    def test_returns_none_when_no_cpu_serial(self, mock_serial, client):
        assert client.discover_player() is None

    @patch.object(PiSignageClient, "get_cpu_serial", return_value="abc123")
    def test_discovers_player_by_serial(self, mock_serial, client):
        client._session.get = MagicMock(
            return_value=_mock_players_response(
                [
                    {"_id": "p1", "cpuSerialNumber": "other"},
                    {"_id": "p2", "cpuSerialNumber": "abc123", "name": "MyPi"},
                ]
            )
        )
        result = client.discover_player()
        assert result == "p2"
        assert client.player_id == "p2"

    @patch.object(PiSignageClient, "get_cpu_serial", return_value="abc123")
    def test_returns_none_when_no_matching_player(self, mock_serial, client):
        client._session.get = MagicMock(
            return_value=_mock_players_response(
                [{"_id": "p1", "cpuSerialNumber": "other"}]
            )
        )
        assert client.discover_player() is None

    @patch.object(PiSignageClient, "get_cpu_serial", return_value="abc123")
    def test_returns_none_on_network_error(self, mock_serial, client):
        client._session.get = MagicMock(side_effect=requests.ConnectionError("fail"))
        assert client.discover_player() is None

    @patch.object(PiSignageClient, "get_cpu_serial", return_value="abc123")
    def test_caches_result(self, mock_serial, client):
        mock_get = MagicMock(
            return_value=_mock_players_response(
                [{"_id": "p1", "cpuSerialNumber": "abc123", "name": "Pi"}]
            )
        )
        client._session.get = mock_get
        client.discover_player()
        client.discover_player()
        assert mock_get.call_count == 1

    def test_returns_cached_player_id(self, client):
        client.player_id = "cached"
        client._session.get = MagicMock()
        assert client.discover_player() == "cached"
        client._session.get.assert_not_called()


class TestDiscoverPlayerAsync:
    @patch.object(PiSignageClient, "discover_player")
    def test_async_discovers_on_first_try(self, mock_discover, client):
        mock_discover.return_value = "p1"
        client.discover_player_async(max_retries=3)
        time.sleep(0.2)
        assert mock_discover.call_count == 1

    @patch.object(PiSignageClient, "discover_player", return_value=None)
    def test_async_retries_on_failure(self, mock_discover, client):
        client.discover_player_async(max_retries=2, base_delay=0.01)
        time.sleep(0.2)
        assert mock_discover.call_count == 2


class TestPlayerIdProperty:
    def test_setter(self, client):
        client.player_id = "manual-id"
        assert client.player_id == "manual-id"


class TestPlaybackActions:
    def test_toggle_pause(self, client):
        client._session.post = MagicMock(return_value=MagicMock(ok=True))
        client._player_id = "p1"
        client.toggle_pause()
        time.sleep(0.1)
        client._session.post.assert_called_once_with(
            "http://localhost:3000/api/playlistmedia/p1/pause",
        )

    def test_forward(self, client):
        client._session.post = MagicMock(return_value=MagicMock(ok=True))
        client._player_id = "p1"
        client.forward()
        time.sleep(0.1)
        client._session.post.assert_called_once_with(
            "http://localhost:3000/api/playlistmedia/p1/forward",
        )

    def test_backward(self, client):
        client._session.post = MagicMock(return_value=MagicMock(ok=True))
        client._player_id = "p1"
        client.backward()
        time.sleep(0.1)
        client._session.post.assert_called_once_with(
            "http://localhost:3000/api/playlistmedia/p1/backward",
        )

    def test_actions_skip_when_no_player_id(self, client):
        client._session.post = MagicMock()
        client.toggle_pause()
        client.forward()
        client.backward()
        time.sleep(0.1)
        client._session.post.assert_not_called()

    def test_action_logs_on_failure(self, client):
        client._session.post = MagicMock(
            return_value=MagicMock(ok=False, status_code=500)
        )
        client._player_id = "p1"
        client.toggle_pause()
        time.sleep(0.1)

    def test_action_handles_exception(self, client):
        client._session.post = MagicMock(side_effect=requests.RequestException("err"))
        client._player_id = "p1"
        client.toggle_pause()
        time.sleep(0.1)


class TestSetPlaylist:
    def test_set_playlist(self, client):
        client._session.post = MagicMock(return_value=MagicMock(ok=True))
        client._player_id = "p1"
        client.set_playlist("my-list")
        time.sleep(0.1)
        client._session.post.assert_called_once_with(
            "http://localhost:3000/api/setplaylist/p1/my-list",
        )

    def test_set_playlist_skips_when_no_player_id(self, client):
        client._session.post = MagicMock()
        client.set_playlist("my-list")
        time.sleep(0.1)
        client._session.post.assert_not_called()


class TestGetPlayerStatus:
    def test_returns_status_data(self, client):
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {"data": {"name": "Pi", "status": "playing"}}
        client._session.get = MagicMock(return_value=resp)
        client._player_id = "p1"
        result = client.get_player_status()
        assert result == {"name": "Pi", "status": "playing"}

    def test_returns_none_when_no_player_id(self, client):
        assert client.get_player_status() is None

    def test_returns_none_on_error(self, client):
        client._session.get = MagicMock(side_effect=requests.RequestException("err"))
        client._player_id = "p1"
        assert client.get_player_status() is None


class TestListPlaylists:
    def test_returns_playlists(self, client):
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {"data": [{"name": "default"}, {"name": "ads"}]}
        client._session.get = MagicMock(return_value=resp)
        result = client.list_playlists()
        assert len(result) == 2

    def test_returns_empty_on_error(self, client):
        client._session.get = MagicMock(side_effect=requests.RequestException("err"))
        assert client.list_playlists() == []


class TestListAssets:
    def test_returns_assets(self, client):
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {"data": [{"name": "video.mp4"}]}
        client._session.get = MagicMock(return_value=resp)
        result = client.list_assets()
        assert len(result) == 1

    def test_returns_empty_on_error(self, client):
        client._session.get = MagicMock(side_effect=requests.RequestException("err"))
        assert client.list_assets() == []


class TestEnsurePlayerId:
    @patch.object(PiSignageClient, "discover_player")
    def test_discovers_if_missing(self, mock_discover, client):
        def fake_discover():
            client._player_id = "p1"
            return "p1"

        mock_discover.side_effect = fake_discover
        assert client._ensure_player_id() == "p1"

    def test_returns_existing(self, client):
        client._player_id = "existing"
        assert client._ensure_player_id() == "existing"

    @patch.object(PiSignageClient, "discover_player", return_value=None)
    def test_returns_none_when_discovery_fails(self, mock_discover, client):
        assert client._ensure_player_id() is None
