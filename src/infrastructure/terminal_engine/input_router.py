"""
InputRouter — Detects F4 keypress and routes input to terminal or chat.

F4 in raw mode is sent as \\x1bOS (3 bytes). The escape byte may arrive
alone due to select() timing, so we buffer \\x1b and wait for the next
feed() call (within 50ms select timeout) to determine if it's F4 or
a regular escape sequence.
"""
from __future__ import annotations

from enum import Enum
from typing import List, Tuple


class InputFocus(str, Enum):
    TERMINAL = "terminal"
    CHAT = "chat"


# F4 escape sequence in raw/application mode
_F4_SEQ = b"\x1bOS"


class InputRouter:
    """Routes raw stdin bytes to terminal, chat, or toggle actions."""

    def __init__(self) -> None:
        self._focus = InputFocus.TERMINAL
        self._esc_buf: bytes = b""  # buffered escape byte(s)

    @property
    def focus(self) -> InputFocus:
        return self._focus

    def toggle_focus(self) -> InputFocus:
        """Toggle between TERMINAL and CHAT focus."""
        if self._focus == InputFocus.TERMINAL:
            self._focus = InputFocus.CHAT
        else:
            self._focus = InputFocus.TERMINAL
        return self._focus

    def feed(self, data: bytes) -> List[Tuple[str, bytes]]:
        """Process raw input bytes and return routing decisions.

        Returns a list of (target, data) tuples where target is one of:
        - "toggle": F4 detected, data is empty
        - "terminal": bytes should go to PTY
        - "chat": bytes should go to ChatPanel
        """
        results: List[Tuple[str, bytes]] = []
        buf = self._esc_buf + data
        self._esc_buf = b""

        i = 0
        while i < len(buf):
            # Check for escape byte
            if buf[i:i + 1] == b"\x1b":
                remaining = buf[i:]
                # Check if we have enough bytes to determine the sequence
                if len(remaining) >= 3 and remaining[:3] == _F4_SEQ:
                    # F4 detected
                    results.append(("toggle", b""))
                    i += 3
                    continue
                elif len(remaining) >= 2:
                    # Some other escape sequence — pass through to current focus
                    if remaining[1:2] == b"[":
                        # CSI sequence: \x1b[<params><final_byte>
                        j = 2
                        while j < len(remaining):
                            b = remaining[j]
                            # Parameter bytes: 0x30-0x3F (digits, ;, <, =, >, ?)
                            if 0x30 <= b <= 0x3F:
                                j += 1
                            # Intermediate bytes: 0x20-0x2F
                            elif 0x20 <= b <= 0x2F:
                                j += 1
                            else:
                                break
                        if j < len(remaining):
                            # Final byte found — include it
                            seq = remaining[:j + 1]
                            target = self._focus.value
                            results.append((target, seq))
                            i += len(seq)
                            continue
                        else:
                            # Incomplete CSI — buffer it
                            self._esc_buf = remaining
                            break
                    elif remaining[1:2] == b"O":
                        # SS3 sequence: \x1bO + one byte
                        if len(remaining) >= 3:
                            # Already handled F4 above; other SS3 sequences
                            seq = remaining[:3]
                            target = self._focus.value
                            results.append((target, seq))
                            i += 3
                            continue
                        else:
                            # Need more bytes
                            self._esc_buf = remaining
                            break
                    else:
                        # Other 2-byte escape (e.g., \x1b + letter)
                        seq = remaining[:2]
                        target = self._focus.value
                        results.append((target, seq))
                        i += 2
                        continue
                else:
                    # Only escape byte — buffer and wait for next feed
                    self._esc_buf = remaining
                    break
            else:
                # Regular byte(s) — collect consecutive non-escape bytes
                j = i + 1
                while j < len(buf) and buf[j:j + 1] != b"\x1b":
                    j += 1
                chunk = buf[i:j]
                target = self._focus.value
                results.append((target, chunk))
                i = j

        return results

    def flush_esc_buffer(self) -> List[Tuple[str, bytes]]:
        """Flush any buffered escape bytes as regular input.

        Call this on timeout when no more data arrives after a lone \\x1b.
        """
        if self._esc_buf:
            data = self._esc_buf
            self._esc_buf = b""
            return [(self._focus.value, data)]
        return []
