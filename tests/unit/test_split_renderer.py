"""Unit tests for SplitRenderer — composite VTScreen + ChatPanel rendering."""
import io
import pytest

from src.infrastructure.terminal_engine.vt_screen import VTScreen, PYTE_AVAILABLE
from src.infrastructure.terminal_engine.chat_panel import ChatPanel
from src.infrastructure.terminal_engine.split_renderer import SplitRenderer, MIN_SPLIT_COLS

pytestmark = pytest.mark.skipif(not PYTE_AVAILABLE, reason="pyte not installed")


class TestSplitRenderer:
    def _make_renderer(self, rows=24, cols=100, chat_width=30):
        out = io.BytesIO()
        vt = VTScreen(rows, cols - chat_width - 1)
        chat = ChatPanel(rows, chat_width)
        renderer = SplitRenderer(out, rows, cols, chat_width=chat_width)
        renderer.attach(vt, chat)
        return renderer, vt, chat, out

    def test_left_cols(self):
        renderer, _, _, _ = self._make_renderer(cols=100, chat_width=30)
        # 100 - 30 - 2 = 68  (separator " │" takes 2 cols)
        assert renderer.left_cols == 68

    def test_render_produces_output(self):
        renderer, vt, chat, out = self._make_renderer()
        vt.feed(b"hello")
        renderer.render(force=True)
        output = out.getvalue()
        assert len(output) > 0
        # Should contain hide/show cursor
        assert b"\033[?25l" in output
        assert b"\033[?25h" in output

    def test_render_contains_separator(self):
        renderer, vt, chat, out = self._make_renderer()
        vt.feed(b"test")
        renderer.render(force=True)
        output = out.getvalue()
        # UTF-8 box drawing: │
        assert b"\xe2\x94\x82" in output

    def test_render_contains_vt_content(self):
        renderer, vt, chat, out = self._make_renderer()
        vt.feed(b"unique_text_xyz")
        renderer.render(force=True)
        output = out.getvalue()
        assert b"unique_text_xyz" in output

    def test_render_contains_chat_header(self):
        renderer, vt, chat, out = self._make_renderer()
        chat.add_message("host", "hi", "host")
        renderer.render(force=True)
        output = out.getvalue()
        assert b"Chat (1)" in output

    def test_diff_rendering_skips_unchanged(self):
        renderer, vt, chat, out = self._make_renderer()
        vt.feed(b"hello")
        renderer.render(force=True)
        first_len = len(out.getvalue())

        # Mark clean, render again without changes
        out.seek(0)
        out.truncate()
        renderer.render(force=False)
        second_len = len(out.getvalue())
        # No output on second render (nothing dirty)
        assert second_len == 0

    def test_diff_rendering_updates_changed_lines(self):
        renderer, vt, chat, out = self._make_renderer()
        vt.feed(b"hello")
        renderer.render(force=True)

        out.seek(0)
        out.truncate()
        vt.feed(b"\r\nworld")
        renderer.render(force=False)
        output = out.getvalue()
        assert b"world" in output

    def test_set_focus_terminal(self):
        renderer, vt, chat, out = self._make_renderer()
        renderer.set_focus("terminal")
        vt.feed(b"abc")
        renderer.render(force=True)
        output = out.getvalue()
        # Cursor should be positioned at VTScreen cursor (row 1, col 4)
        assert b"\033[1;4H" in output

    def test_set_focus_chat(self):
        renderer, vt, chat, out = self._make_renderer(rows=10)
        renderer.set_focus("chat")
        renderer.render(force=True)
        output = out.getvalue()
        # Cursor should be on last row, in chat area
        # Chat input col = left_cols + 2 + cursor_col_in_chat
        # input_cursor_col is 2 (after "> "), left_cols = 69, so col = 69 + 2 + 2 = 73
        assert b"\033[10;" in output

    def test_resize_forces_full_redraw(self):
        renderer, vt, chat, out = self._make_renderer()
        vt.feed(b"hello")
        renderer.render(force=True)

        out.seek(0)
        out.truncate()
        renderer.resize(20, 90)
        vt.feed(b" ")  # dirty it
        renderer.render(force=False)
        output = out.getvalue()
        # After resize, prev_frame cleared → full redraw
        assert len(output) > 0

    def test_detach_clears_screen(self):
        renderer, vt, chat, out = self._make_renderer()
        renderer.render(force=True)
        out.seek(0)
        out.truncate()
        renderer.detach()
        output = out.getvalue()
        # Should contain clear screen
        assert b"\033[2J" in output

    def test_min_split_cols_constant(self):
        assert MIN_SPLIT_COLS == 60
