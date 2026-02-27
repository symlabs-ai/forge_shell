"""Unit tests for ChatPanel — chat message state, input buffer, rendering."""
import pytest

from src.infrastructure.terminal_engine.chat_panel import ChatPanel, ChatMessage


class TestChatPanel:
    def test_initial_state(self):
        cp = ChatPanel(10, 30)
        assert cp.message_count == 0
        assert cp.dirty  # initial state is dirty

    def test_add_message(self):
        cp = ChatPanel(10, 30)
        cp.mark_clean()
        cp.add_message("host", "hello", "host")
        assert cp.message_count == 1
        assert cp.dirty

    def test_render_lines_count(self):
        cp = ChatPanel(10, 30)
        lines = cp.render_lines()
        # header + (rows - 2) message area + input = rows
        assert len(lines) == 10

    def test_render_header_contains_count(self):
        cp = ChatPanel(10, 30)
        cp.add_message("host", "hi", "host")
        cp.add_message("viewer", "oi", "viewer")
        lines = cp.render_lines()
        header = lines[0].decode("utf-8", errors="replace")
        assert "Chat (2)" in header

    def test_render_messages_visible(self):
        cp = ChatPanel(10, 30)
        cp.add_message("host", "hello", "host")
        lines = cp.render_lines()
        # Find the message in rendered output
        found = any(b"[host]" in line and b"hello" in line for line in lines)
        assert found

    def test_render_input_line(self):
        cp = ChatPanel(10, 30)
        lines = cp.render_lines()
        last = lines[-1]
        assert b"> " in last

    def test_handle_key_normal(self):
        cp = ChatPanel(10, 30)
        result = cp.handle_key(b"a")
        assert result is None
        result = cp.handle_key(b"b")
        assert result is None

    def test_handle_key_enter_returns_text(self):
        cp = ChatPanel(10, 30)
        cp.handle_key(b"h")
        cp.handle_key(b"i")
        result = cp.handle_key(b"\r")
        assert result == "hi"

    def test_handle_key_enter_empty_returns_none(self):
        cp = ChatPanel(10, 30)
        result = cp.handle_key(b"\r")
        assert result is None

    def test_handle_key_backspace(self):
        cp = ChatPanel(10, 30)
        cp.handle_key(b"a")
        cp.handle_key(b"b")
        cp.handle_key(b"\x7f")  # backspace
        result = cp.handle_key(b"\r")
        assert result == "a"

    def test_handle_key_ctrl_c_clears(self):
        cp = ChatPanel(10, 30)
        cp.handle_key(b"a")
        cp.handle_key(b"b")
        cp.handle_key(b"\x03")  # Ctrl-C
        result = cp.handle_key(b"\r")
        assert result is None  # buffer was cleared

    def test_handle_key_escape_ignored(self):
        cp = ChatPanel(10, 30)
        result = cp.handle_key(b"\x1b[A")  # arrow up
        assert result is None

    def test_resize(self):
        cp = ChatPanel(10, 30)
        cp.mark_clean()
        cp.resize(20, 50)
        assert cp.dirty
        lines = cp.render_lines()
        assert len(lines) == 20

    def test_dirty_tracking(self):
        cp = ChatPanel(10, 30)
        cp.mark_clean()
        assert not cp.dirty
        cp.add_message("host", "test", "host")
        assert cp.dirty
        cp.mark_clean()
        assert not cp.dirty

    def test_input_cursor_col(self):
        cp = ChatPanel(10, 30)
        assert cp.input_cursor_col == 2  # just after "> "
        cp.handle_key(b"a")
        assert cp.input_cursor_col == 3
        cp.handle_key(b"b")
        assert cp.input_cursor_col == 4

    def test_message_roles_colored(self):
        cp = ChatPanel(10, 40)
        cp.add_message("host", "hi", "host")
        cp.add_message("viewer", "oi", "viewer")
        cp.add_message("agent", "sugestão", "agent")
        lines = cp.render_lines()
        # Check that role colors appear in output
        rendered = b"".join(lines)
        assert b"\033[1;32m" in rendered   # host green
        assert b"\033[1;36m" in rendered   # viewer cyan
        assert b"\033[1;35m" in rendered   # agent magenta

    def test_long_message_wraps(self):
        cp = ChatPanel(10, 20)
        cp.add_message("h", "a" * 50, "host")
        lines = cp.render_lines()
        # Message should wrap across multiple lines
        msg_lines = [l for l in lines if b"a" in l]
        assert len(msg_lines) >= 2
