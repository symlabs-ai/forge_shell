"""
ChatPanel — Chat message state, input buffer, and ANSI rendering.

Maintains a list of chat messages and an input line buffer.
Renders the panel as a list of ANSI-formatted byte lines ready
to be composited by SplitRenderer.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


# ANSI color codes per role
_ROLE_COLORS = {
    "host": b"\033[1;32m",    # green
    "viewer": b"\033[1;36m",  # cyan
    "agent": b"\033[1;35m",   # magenta
}
_RESET = b"\033[0m"
_DIM = b"\033[2m"
_BORDER_COLOR = b"\033[90m"  # dark gray


@dataclass
class ChatMessage:
    sender: str
    text: str
    role: str


class ChatPanel:
    """Chat panel state: messages, input buffer, rendering."""

    def __init__(self, rows: int, cols: int) -> None:
        self._rows = rows
        self._cols = cols
        self._messages: List[ChatMessage] = []
        self._input_buffer: bytearray = bytearray()
        self._dirty = True
        self._scroll_offset = 0  # for future scrolling

    def add_message(self, sender: str, text: str, role: str = "host") -> None:
        """Add a chat message and mark dirty."""
        self._messages.append(ChatMessage(sender=sender, text=text, role=role))
        self._dirty = True

    def handle_key(self, data: bytes) -> str | None:
        """Process a keypress in chat input mode.

        Returns the completed text on Enter, None otherwise.
        """
        # Enter
        if data in (b"\r", b"\n"):
            if self._input_buffer:
                text = self._input_buffer.decode("utf-8", errors="replace")
                self._input_buffer.clear()
                self._dirty = True
                return text
            return None

        # Backspace / DEL
        if data in (b"\x7f", b"\x08"):
            if self._input_buffer:
                self._input_buffer = self._input_buffer[:-1]
                self._dirty = True
            return None

        # Ctrl-C — clear input
        if data == b"\x03":
            if self._input_buffer:
                self._input_buffer.clear()
                self._dirty = True
            return None

        # Ignore other control chars and escape sequences
        if data[0:1] == b"\x1b" or (len(data) == 1 and data[0] < 0x20):
            return None

        # Normal character — append
        self._input_buffer.extend(data)
        self._dirty = True
        return None

    def resize(self, rows: int, cols: int) -> None:
        self._rows = rows
        self._cols = cols
        self._dirty = True

    def render_lines(self) -> list[bytes]:
        """Render the chat panel as a list of ANSI byte lines.

        Layout:
          Line 0:   ── Chat (N) ──────
          Lines 1..N-2: messages (bottom-aligned)
          Line N-1: > input_buffer_
        """
        w = self._cols
        lines: list[bytes] = []

        # Header
        count = len(self._messages)
        header_text = f" Chat ({count}) "
        pad = w - len(header_text)
        left_pad = 1
        right_pad = max(0, pad - left_pad)
        header = (_BORDER_COLOR
                  + b"\xe2\x94\x80" * left_pad
                  + header_text.encode()
                  + b"\xe2\x94\x80" * right_pad
                  + _RESET)
        lines.append(header)

        # Message area: rows - 2 (header + input line)
        msg_area = self._rows - 2
        if msg_area < 0:
            msg_area = 0

        # Wrap messages to fit width, collect rendered lines
        rendered_msgs: list[bytes] = []
        for msg in self._messages:
            color = _ROLE_COLORS.get(msg.role, b"\033[37m")
            prefix = color + f"[{msg.sender}]".encode() + _RESET + b" "
            # prefix display length (without ANSI)
            prefix_len = len(f"[{msg.sender}] ")
            text_width = max(1, w - prefix_len)
            # Simple word-wrap
            text = msg.text
            while text:
                chunk = text[:text_width]
                text = text[text_width:]
                if rendered_msgs:
                    # continuation lines have indent instead of prefix
                    rendered_msgs.append(b"  " + chunk.encode().ljust(w - 2))
                else:
                    rendered_msgs.append(prefix + chunk.encode())
                if not rendered_msgs[-1:]:
                    break
            # First line always has prefix
            if len(rendered_msgs) == 0:
                rendered_msgs.append(prefix)
            # Reset: the last append was a continuation, fix first line
            # Actually let's simplify: re-do properly
        # Redo: simpler approach
        rendered_msgs = []
        for msg in self._messages:
            color = _ROLE_COLORS.get(msg.role, b"\033[37m")
            tag = f"[{msg.sender}]"
            prefix_display_len = len(tag) + 1  # +1 for space
            text_width = max(1, w - prefix_display_len)
            first_line = True
            remaining = msg.text
            while remaining:
                chunk = remaining[:text_width]
                remaining = remaining[text_width:]
                if first_line:
                    line = color + tag.encode() + _RESET + b" " + chunk.encode()
                    first_line = False
                else:
                    line = b" " * prefix_display_len + chunk.encode()
                rendered_msgs.append(line)
            if first_line:
                # empty text
                rendered_msgs.append(color + tag.encode() + _RESET)

        # Take last msg_area lines (bottom-aligned)
        visible = rendered_msgs[-msg_area:] if msg_area > 0 else []
        # Pad with empty lines if fewer messages
        while len(visible) < msg_area:
            visible.insert(0, b"")
        lines.extend(visible)

        # Input line
        input_text = self._input_buffer.decode("utf-8", errors="replace")
        prompt = "> "
        visible_input = input_text[-(w - len(prompt) - 1):] if len(input_text) > w - len(prompt) - 1 else input_text
        input_line = _DIM + prompt.encode() + _RESET + visible_input.encode()
        lines.append(input_line)

        return lines

    @property
    def input_cursor_col(self) -> int:
        """Column position of cursor in the input line (0-based within panel)."""
        prompt_len = 2  # "> "
        input_len = len(self._input_buffer.decode("utf-8", errors="replace"))
        max_visible = self._cols - prompt_len - 1
        if input_len > max_visible:
            return prompt_len + max_visible
        return prompt_len + input_len

    @property
    def dirty(self) -> bool:
        return self._dirty

    def mark_clean(self) -> None:
        self._dirty = False

    @property
    def message_count(self) -> int:
        return len(self._messages)
