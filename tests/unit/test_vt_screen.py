"""Unit tests for VTScreen — virtual terminal backed by pyte."""
import pytest

from src.infrastructure.terminal_engine.vt_screen import VTScreen, PYTE_AVAILABLE

pytestmark = pytest.mark.skipif(not PYTE_AVAILABLE, reason="pyte not installed")


class TestVTScreen:
    def test_initial_state(self):
        vt = VTScreen(24, 80)
        assert vt.rows == 24
        assert vt.cols == 80
        assert vt.get_cursor() == (0, 0)
        assert len(vt.get_display()) == 24

    def test_feed_simple_text(self):
        vt = VTScreen(24, 80)
        vt.feed(b"hello world")
        display = vt.get_display()
        assert display[0].startswith("hello world")
        assert vt.get_cursor() == (0, 11)

    def test_feed_newline(self):
        vt = VTScreen(24, 80)
        vt.feed(b"line1\r\nline2")
        display = vt.get_display()
        assert display[0].startswith("line1")
        assert display[1].startswith("line2")
        assert vt.get_cursor() == (1, 5)

    def test_feed_ansi_color(self):
        vt = VTScreen(24, 80)
        vt.feed(b"\033[31mred text\033[0m normal")
        display = vt.get_display()
        assert "red text" in display[0]
        assert "normal" in display[0]

    def test_dirty_tracking(self):
        vt = VTScreen(24, 80)
        # Initial state is not dirty (no feed yet)
        vt.mark_clean()
        assert not vt.dirty
        vt.feed(b"x")
        assert vt.dirty
        vt.mark_clean()
        assert not vt.dirty

    def test_resize(self):
        vt = VTScreen(24, 80)
        vt.feed(b"hello")
        vt.resize(10, 40)
        assert vt.rows == 10
        assert vt.cols == 40
        assert len(vt.get_display()) == 10

    def test_feed_cursor_movement(self):
        vt = VTScreen(24, 80)
        vt.feed(b"abc\033[1;5H")  # move cursor to row 1, col 5
        row, col = vt.get_cursor()
        assert row == 0  # pyte is 0-based
        assert col == 4  # pyte is 0-based

    def test_get_buffer(self):
        vt = VTScreen(24, 80)
        vt.feed(b"A")
        buf = vt.get_buffer()
        assert buf is not None
        # Buffer should have data at position (0, 0)
        assert buf[0][0].data == "A"

    def test_feed_multiple_chunks(self):
        vt = VTScreen(24, 80)
        vt.feed(b"hel")
        vt.feed(b"lo")
        display = vt.get_display()
        assert display[0].startswith("hello")
