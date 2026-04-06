import sys
import types
from unittest.mock import MagicMock


def pytest_configure(config):
    tk_mock = types.ModuleType("tkinter")
    tk_mock.Tk = MagicMock
    tk_mock.Label = MagicMock
    tk_mock.TclError = Exception
    sys.modules["tkinter"] = tk_mock

    pil_mock = types.ModuleType("PIL")
    image_mock = types.ModuleType("PIL.Image")
    imagetk_mock = types.ModuleType("PIL.ImageTk")

    mock_image = MagicMock()
    mock_image.convert.return_value = mock_image
    mock_image.resize.return_value = mock_image
    mock_image.open = MagicMock(return_value=mock_image)
    image_mock.Image = MagicMock
    image_mock.open = MagicMock(return_value=mock_image)
    image_mock.Resampling = MagicMock(LANCZOS=1)
    image_mock.LANCZOS = 1

    imagetk_mock.PhotoImage = MagicMock

    pil_mock.Image = image_mock
    pil_mock.ImageTk = imagetk_mock

    sys.modules["PIL"] = pil_mock
    sys.modules["PIL.Image"] = image_mock
    sys.modules["PIL.ImageTk"] = imagetk_mock
