"""Unit tests for _ViewerSession — chat split in forge_shell attach."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.adapters.cli.main import _ViewerSession


@pytest.fixture
def mock_viewer():
    viewer = AsyncMock()
    viewer.send_input = AsyncMock()
    viewer.send_chat = AsyncMock()
    return viewer


@pytest.fixture
def stdout_buf():
    return MagicMock()


@pytest.fixture
def session(mock_viewer, stdout_buf):
    return _ViewerSession(mock_viewer, stdout_buf)


class TestViewerSessionChatToggle:
    """F4 activates chat split."""

    def test_initial_state_no_chat(self, session):
        assert session._chat_active is False
        assert session._vt is None
        assert session._chat is None
        assert session._renderer is None

    @patch("src.adapters.cli.main.os.get_terminal_size")
    def test_f4_activates_chat(self, mock_size, session):
        mock_size.return_value = MagicMock(lines=24, columns=80)
        # F4 = \x1bOS
        asyncio.run(session.handle_input(b"\x1bOS"))
        assert session._chat_active is True
        assert session._vt is not None
        assert session._chat is not None
        assert session._renderer is not None

    @patch("src.adapters.cli.main.os.get_terminal_size")
    def test_second_f4_toggles_focus(self, mock_size, session):
        mock_size.return_value = MagicMock(lines=24, columns=80)
        # First F4 → activate chat, focus stays on terminal
        asyncio.run(session.handle_input(b"\x1bOS"))
        assert session._chat_active is True
        assert session._router.focus.value == "terminal"

        # Second F4 → toggle focus to chat
        asyncio.run(session.handle_input(b"\x1bOS"))
        assert session._chat_active is True
        assert session._router.focus.value == "chat"


class TestViewerSessionInputRouting:
    """Input routing through _ViewerSession."""

    @patch("src.adapters.cli.main.os.get_terminal_size")
    def test_terminal_mode_sends_input(self, mock_size, session, mock_viewer):
        mock_size.return_value = MagicMock(lines=24, columns=80)
        # Without chat, input goes to send_input
        asyncio.run(session.handle_input(b"ls\r"))
        mock_viewer.send_input.assert_called_with(b"ls\r")

    @patch("src.adapters.cli.main.os.get_terminal_size")
    def test_chat_mode_routes_to_chat_panel(self, mock_size, session, mock_viewer):
        mock_size.return_value = MagicMock(lines=24, columns=80)
        # Activate chat and toggle focus to chat
        asyncio.run(session.handle_input(b"\x1bOS"))  # activate
        asyncio.run(session.handle_input(b"\x1bOS"))  # focus → chat

        # Type "hi" + Enter
        asyncio.run(session.handle_input(b"hi\r"))
        # Should send chat, not terminal input
        mock_viewer.send_chat.assert_called_once_with("hi", sender="viewer")
        # send_input should NOT be called for "hi\r"
        mock_viewer.send_input.assert_not_called()

    @patch("src.adapters.cli.main.os.get_terminal_size")
    def test_chat_mode_adds_local_message(self, mock_size, session, mock_viewer):
        mock_size.return_value = MagicMock(lines=24, columns=80)
        asyncio.run(session.handle_input(b"\x1bOS"))  # activate
        asyncio.run(session.handle_input(b"\x1bOS"))  # focus → chat
        asyncio.run(session.handle_input(b"hi\r"))
        # Local echo: "eu" message added to chat panel
        assert session._chat.message_count == 1


class TestViewerSessionOutput:
    """on_output routes to VTScreen or stdout."""

    def test_no_chat_writes_stdout(self, session, stdout_buf):
        session.on_output(b"hello world")
        stdout_buf.write.assert_called_once_with(b"hello world")
        stdout_buf.flush.assert_called_once()

    @patch("src.adapters.cli.main.os.get_terminal_size")
    def test_chat_active_feeds_vt_screen(self, mock_size, session, stdout_buf):
        mock_size.return_value = MagicMock(lines=24, columns=80)
        # Activate chat
        asyncio.run(session.handle_input(b"\x1bOS"))
        stdout_buf.reset_mock()

        session.on_output(b"some output")
        # VTScreen was fed (dirty=True, render is deferred to stdin loop)
        assert session._vt.dirty is True
        # Batch render clears dirty
        session.render_if_dirty()
        assert session._vt.dirty is False


class TestViewerSessionOnChat:
    """on_chat adds messages and auto-activates chat."""

    @patch("src.adapters.cli.main.os.get_terminal_size")
    def test_on_chat_auto_activates(self, mock_size, session):
        mock_size.return_value = MagicMock(lines=24, columns=80)
        assert session._chat_active is False
        session.on_chat({"sender": "host", "text": "hello"})
        assert session._chat_active is True
        assert session._chat.message_count == 1

    @patch("src.adapters.cli.main.os.get_terminal_size")
    def test_on_chat_adds_message(self, mock_size, session):
        mock_size.return_value = MagicMock(lines=24, columns=80)
        session.on_chat({"sender": "host", "text": "msg1"})
        session.on_chat({"sender": "viewer", "text": "msg2"})
        assert session._chat.message_count == 2


class TestViewerSessionDisconnect:
    """Ctrl+] disconnects even with chat active."""

    @patch("src.adapters.cli.main.os.get_terminal_size")
    def test_ctrl_bracket_in_data_not_routed(self, mock_size, session, mock_viewer):
        """Ctrl+] (0x1d) is handled in the _viewer_loop, not in handle_input.
        _ViewerSession.handle_input passes it through to send_input.
        The caller (_viewer_loop) checks for 0x1d before calling handle_input."""
        mock_size.return_value = MagicMock(lines=24, columns=80)
        # Activate chat
        asyncio.run(session.handle_input(b"\x1bOS"))
        # Ctrl+] should be routed to terminal (send_input) since it's a regular byte
        # The _viewer_loop handles the disconnect logic before reaching handle_input
        asyncio.run(session.handle_input(b"\x1d"))
        mock_viewer.send_input.assert_called_with(b"\x1d")
