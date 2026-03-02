"""
SplitRenderer — Composites VTScreen (left) + ChatPanel (right) on real terminal.

Uses diff-based rendering: only redraws lines that changed since last frame.
Hides cursor during render, repositions it based on focus (terminal or chat).
"""
from __future__ import annotations

import sys
from typing import IO

from src.infrastructure.terminal_engine.vt_screen import VTScreen
from src.infrastructure.terminal_engine.chat_panel import ChatPanel


# Minimum terminal width to enable split
MIN_SPLIT_COLS = 60


class SplitRenderer:
    """Composites VTScreen + ChatPanel side by side."""

    def __init__(
        self,
        stdout: IO[bytes],
        total_rows: int,
        total_cols: int,
        chat_width: int = 30,
    ) -> None:
        self._stdout = stdout
        self._total_rows = total_rows
        self._total_cols = total_cols
        self._chat_width = chat_width
        self._vt: VTScreen | None = None
        self._chat: ChatPanel | None = None
        self._focus = "terminal"  # "terminal" | "chat"
        self._prev_frame: list[bytes] = []  # previous rendered lines for diff
        self._separator = b"\xe2\x94\x82"  # │ (UTF-8, 3 bytes, 1 display col)

    def attach(self, vt: VTScreen, chat: ChatPanel) -> None:
        """Attach VTScreen and ChatPanel for rendering."""
        self._vt = vt
        self._chat = chat
        self._prev_frame = []

    def detach(self) -> None:
        """Detach and clear split view, restore full-screen terminal."""
        self._vt = None
        self._chat = None
        self._prev_frame = []
        # Clear screen and reset cursor
        buf = b"\033[2J\033[H"
        self._stdout.write(buf)
        self._stdout.flush()

    @property
    def left_cols(self) -> int:
        """Width available for the PTY (left pane). Accounts for ' │' separator (2 cols)."""
        return max(1, self._total_cols - self._chat_width - 2)

    def set_focus(self, focus: str) -> None:
        """Set focus to 'terminal' or 'chat'."""
        self._focus = focus

    def resize(self, total_rows: int, total_cols: int) -> None:
        self._total_rows = total_rows
        self._total_cols = total_cols
        self._prev_frame = []  # force full redraw

    def render(self, force: bool = False) -> None:
        """Render the composite frame to stdout.

        Uses diff-based approach: only emits lines that changed.
        """
        if self._vt is None or self._chat is None:
            return

        if not force and not self._vt.dirty and not self._chat.dirty:
            return

        left_w = self.left_cols
        right_w = self._chat_width
        rows = self._total_rows

        # Get left pane content from VTScreen, clipped to left_w columns
        vt_lines = self._vt.get_display_ansi(max_cols=left_w)
        # Plain text lines for width calculation (clipped)
        vt_plain = [line[:left_w] for line in self._vt.get_display()]

        # Get right pane content from ChatPanel
        chat_lines = self._chat.render_lines()

        # Build composite frame
        frame: list[bytes] = []
        for r in range(rows):
            # Left side: VTScreen line with ANSI colors
            if r < len(vt_lines):
                left_ansi = vt_lines[r]
                left_text_len = len(vt_plain[r]) if r < len(vt_plain) else 0
            else:
                left_ansi = b""
                left_text_len = 0

            # Pad to left_w (add spaces after reset)
            if left_text_len < left_w:
                padding = b" " * (left_w - left_text_len)
                left_padded = left_ansi + b"\033[0m" + padding
            else:
                left_padded = left_ansi + b"\033[0m"

            # Right side: ChatPanel line
            if r < len(chat_lines):
                right = chat_lines[r]
            else:
                right = b""

            # Compose: left (ANSI) + separator + right (ANSI bytes)
            line = (left_padded
                    + b" "  # space before separator
                    + self._separator
                    + right)
            frame.append(line)

        # Build output buffer
        buf = bytearray()
        buf.extend(b"\033[?25l")  # hide cursor

        if force or len(self._prev_frame) != len(frame):
            # Full redraw
            for r, line in enumerate(frame):
                buf.extend(f"\033[{r + 1};1H".encode())
                buf.extend(b"\033[2K")  # clear line
                buf.extend(line)
        else:
            # Diff: only redraw changed lines
            for r, (new_line, old_line) in enumerate(zip(frame, self._prev_frame)):
                if new_line != old_line:
                    buf.extend(f"\033[{r + 1};1H".encode())
                    buf.extend(b"\033[2K")
                    buf.extend(new_line)

        # Position cursor based on focus
        buf.extend(self._cursor_position())
        buf.extend(b"\033[?25h")  # show cursor

        self._stdout.write(bytes(buf))
        self._stdout.flush()

        self._prev_frame = frame
        self._vt.mark_clean()
        self._chat.mark_clean()

    def _cursor_position(self) -> bytes:
        """Generate ANSI escape to position cursor based on focus."""
        if self._focus == "chat" and self._chat is not None:
            # Cursor at input line of chat panel
            row = self._total_rows  # last row (1-based)
            col = self.left_cols + 2 + self._chat.input_cursor_col  # +2 for " │"
            return f"\033[{row};{col}H".encode()
        elif self._vt is not None:
            # Cursor at VTScreen cursor position, clamped to left pane
            vt_row, vt_col = self._vt.get_cursor()
            vt_col = min(vt_col, self.left_cols - 1)
            return f"\033[{vt_row + 1};{vt_col + 1}H".encode()
        return b""
