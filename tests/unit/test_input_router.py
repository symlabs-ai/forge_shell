"""Unit tests for InputRouter — F4 detection, focus toggle, escape buffering."""
import pytest

from src.infrastructure.terminal_engine.input_router import InputRouter, InputFocus


class TestInputRouter:
    def test_initial_focus_is_terminal(self):
        ir = InputRouter()
        assert ir.focus == InputFocus.TERMINAL

    def test_toggle_focus(self):
        ir = InputRouter()
        assert ir.toggle_focus() == InputFocus.CHAT
        assert ir.focus == InputFocus.CHAT
        assert ir.toggle_focus() == InputFocus.TERMINAL
        assert ir.focus == InputFocus.TERMINAL

    def test_f4_detection(self):
        ir = InputRouter()
        result = ir.feed(b"\x1bOS")
        assert len(result) == 1
        assert result[0] == ("toggle", b"")

    def test_f4_mixed_with_text(self):
        ir = InputRouter()
        result = ir.feed(b"abc\x1bOSdef")
        targets = [r[0] for r in result]
        assert "toggle" in targets
        # Should have text before and after F4
        assert ("terminal", b"abc") in result
        assert ("terminal", b"def") in result

    def test_normal_bytes_routed_to_focus(self):
        ir = InputRouter()
        result = ir.feed(b"hello")
        assert result == [("terminal", b"hello")]

        ir.toggle_focus()  # → chat
        result = ir.feed(b"world")
        assert result == [("chat", b"world")]

    def test_csi_escape_passthrough(self):
        ir = InputRouter()
        # Arrow up: \x1b[A
        result = ir.feed(b"\x1b[A")
        assert len(result) == 1
        assert result[0] == ("terminal", b"\x1b[A")

    def test_csi_with_params(self):
        ir = InputRouter()
        # \x1b[1;5H — cursor position
        result = ir.feed(b"\x1b[1;5H")
        assert len(result) == 1
        assert result[0] == ("terminal", b"\x1b[1;5H")

    def test_ss3_non_f4(self):
        ir = InputRouter()
        # F1: \x1bOP
        result = ir.feed(b"\x1bOP")
        assert len(result) == 1
        assert result[0] == ("terminal", b"\x1bOP")

    def test_lone_escape_buffered(self):
        ir = InputRouter()
        result = ir.feed(b"\x1b")
        # Should be buffered, nothing emitted
        assert result == []

    def test_lone_escape_then_more_data(self):
        ir = InputRouter()
        result = ir.feed(b"\x1b")
        assert result == []
        # Next feed completes the sequence
        result = ir.feed(b"OS")
        # Should be F4
        assert ("toggle", b"") in result

    def test_lone_escape_flush(self):
        ir = InputRouter()
        ir.feed(b"\x1b")
        result = ir.flush_esc_buffer()
        assert len(result) == 1
        assert result[0] == ("terminal", b"\x1b")

    def test_flush_empty(self):
        ir = InputRouter()
        result = ir.flush_esc_buffer()
        assert result == []

    def test_multiple_f4_in_sequence(self):
        ir = InputRouter()
        result = ir.feed(b"\x1bOS\x1bOS")
        toggles = [r for r in result if r[0] == "toggle"]
        assert len(toggles) == 2

    def test_two_byte_escape(self):
        ir = InputRouter()
        # \x1bM — reverse index (2-byte escape)
        result = ir.feed(b"\x1bM")
        assert len(result) == 1
        assert result[0] == ("terminal", b"\x1bM")

    def test_incomplete_csi_buffered(self):
        ir = InputRouter()
        # Incomplete CSI: \x1b[1
        result = ir.feed(b"\x1b[1")
        assert result == []  # buffered
        # Complete it
        result = ir.feed(b";5H")
        assert len(result) == 1
        assert result[0][1] == b"\x1b[1;5H"
