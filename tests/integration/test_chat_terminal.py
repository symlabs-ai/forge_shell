"""Integration test: TerminalSession with split chat + mocked engine."""
import io
import queue
import pytest
from unittest.mock import MagicMock, patch, PropertyMock

from src.infrastructure.config.loader import ForgeShellConfig
from src.application.usecases.terminal_session import TerminalSession, SessionMode

try:
    from src.infrastructure.terminal_engine.vt_screen import PYTE_AVAILABLE
except ImportError:
    PYTE_AVAILABLE = False

pytestmark = pytest.mark.skipif(not PYTE_AVAILABLE, reason="pyte not installed")


def _make_session(cols=100, rows=24):
    """Create a TerminalSession with mocked engine and stdout."""
    config = ForgeShellConfig()
    session = TerminalSession(config, passthrough=False)

    # Mock engine
    engine = MagicMock()
    engine.is_alive = True
    engine.pid = 12345
    engine.master_fd = -1
    session._engine = engine

    # Mock stdout
    out = io.BytesIO()
    session._stdout = out

    # Mock terminal size
    session._get_terminal_size = MagicMock(return_value=(rows, cols))

    # Mock relay bridge
    bridge = MagicMock()
    bridge.get_suggest.return_value = None
    bridge.get_chat.return_value = None
    session._relay_bridge = bridge

    return session, engine, out, bridge


class TestChatActivation:
    def test_activate_chat_panel(self):
        session, engine, out, bridge = _make_session(cols=100)
        session._activate_chat_panel()

        assert session._chat_active
        assert session._vt_screen is not None
        assert session._chat_panel is not None
        assert session._split_renderer is not None
        assert session._input_router is not None
        # PTY resized to left pane
        engine.resize.assert_called()

    def test_activate_fails_narrow_terminal(self):
        session, engine, out, bridge = _make_session(cols=50)
        session._activate_chat_panel()

        assert not session._chat_active
        assert session._vt_screen is None

    def test_deactivate_chat_panel(self):
        session, engine, out, bridge = _make_session(cols=100)
        session._activate_chat_panel()
        assert session._chat_active

        session._deactivate_chat_panel()
        assert not session._chat_active
        assert session._vt_screen is None
        assert session._chat_panel is None
        assert session._split_renderer is None
        assert session._input_router is None

    def test_deactivate_restores_pty_size(self):
        session, engine, out, bridge = _make_session(cols=100, rows=24)
        session._activate_chat_panel()
        engine.resize.reset_mock()

        session._deactivate_chat_panel()
        # Should resize PTY to full terminal size
        engine.resize.assert_called_with(24, 100)


class TestChatMessages:
    def test_handle_chat_message(self):
        session, engine, out, bridge = _make_session()
        session._activate_chat_panel()

        session._handle_chat_message({"sender": "viewer", "text": "oi", "role": "viewer"})
        assert session._chat_panel.message_count == 1

    def test_send_chat_message(self):
        session, engine, out, bridge = _make_session()
        session._activate_chat_panel()

        session._send_chat_message("hello from host")
        assert session._chat_panel.message_count == 1
        bridge.send_chat.assert_called_once_with("hello from host", sender="host")

    def test_send_chat_without_bridge(self):
        session, engine, out, bridge = _make_session()
        session._relay_bridge = None
        session._activate_chat_panel()

        # Should not raise
        session._send_chat_message("hello")
        assert session._chat_panel.message_count == 1


class TestInputRoutingWithChat:
    def test_f4_toggles_focus(self):
        session, engine, out, bridge = _make_session()
        session._activate_chat_panel()

        from src.infrastructure.terminal_engine.input_router import InputFocus
        assert session._input_router.focus == InputFocus.TERMINAL

        # Send F4
        session._route_input(b"\x1bOS")
        assert session._input_router.focus == InputFocus.CHAT

    def test_terminal_focus_routes_to_pty(self):
        session, engine, out, bridge = _make_session()
        session._mode = SessionMode.BASH
        session._activate_chat_panel()
        session._pty_running = True  # simulate running command

        # In terminal focus, input should go to PTY
        session._route_input(b"x")
        engine.write.assert_called_with(b"x")

    def test_chat_focus_routes_to_chat(self):
        session, engine, out, bridge = _make_session()
        session._activate_chat_panel()

        # Switch to chat focus
        session._route_input(b"\x1bOS")  # F4 → toggle to chat
        engine.write.reset_mock()

        # Type in chat
        session._route_input(b"h")
        session._route_input(b"i")
        # Should NOT go to PTY
        engine.write.assert_not_called()

        # Enter should send chat message
        session._route_input(b"\r")
        bridge.send_chat.assert_called_once_with("hi", sender="host")

    def test_passthrough_mode_ignores_chat(self):
        session, engine, out, bridge = _make_session()
        session._mode = SessionMode.PASSTHROUGH
        session._activate_chat_panel()

        # Even with chat active, passthrough routes to PTY
        session._route_input(b"x")
        engine.write.assert_called_with(b"x")

    def test_alternate_screen_routes_directly(self):
        session, engine, out, bridge = _make_session()
        session._activate_chat_panel()
        session._detector._depth = 1  # simulate alternate screen active

        session._route_input(b"x")
        engine.write.assert_called_with(b"x")


class TestPtyOutputWithChat:
    def test_pty_output_feeds_vt_screen(self):
        session, engine, out, bridge = _make_session()
        session._activate_chat_panel()

        session._handle_pty_output(b"hello world")
        display = session._vt_screen.get_display()
        assert "hello world" in display[0]

    def test_pty_output_without_chat_writes_stdout(self):
        session, engine, out, bridge = _make_session()
        # No chat active
        session._handle_pty_output(b"direct output")
        assert b"direct output" in out.getvalue()

    def test_pty_output_still_relays(self):
        session, engine, out, bridge = _make_session()
        session._activate_chat_panel()

        session._handle_pty_output(b"relayed data")
        bridge.send.assert_called_with(b"relayed data")


class TestAlternateScreenTransition:
    def test_entering_alt_screen_hides_chat(self):
        session, engine, out, bridge = _make_session(cols=100, rows=24)
        session._activate_chat_panel()
        engine.resize.reset_mock()

        # Simulate entering alternate screen
        session._handle_pty_output(b"\x1b[?1049h")
        assert session._alt_screen_was_active
        # PTY should be resized to full width
        engine.resize.assert_called_with(24, 100)

    def test_exiting_alt_screen_restores_chat(self):
        session, engine, out, bridge = _make_session(cols=100, rows=24)
        session._activate_chat_panel()

        # Enter then exit alternate screen
        session._handle_pty_output(b"\x1b[?1049h")
        assert session._alt_screen_was_active

        session._handle_pty_output(b"\x1b[?1049l")
        assert not session._alt_screen_was_active
        # Split renderer should be restored
        assert session._split_renderer is not None
