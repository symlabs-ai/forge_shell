"""
VTScreen — Virtual terminal screen backed by pyte.

Processes raw PTY output bytes through a VT100/xterm parser (pyte),
maintaining a virtual screen buffer that can be queried for display lines,
cursor position, and dirty state.

Fallback: if pyte is not installed, the module exposes PYTE_AVAILABLE = False
and VTScreen should not be instantiated.
"""
from __future__ import annotations

try:
    import pyte
    PYTE_AVAILABLE = True
except ImportError:
    pyte = None  # type: ignore
    PYTE_AVAILABLE = False


class VTScreen:
    """Wraps pyte.Screen + pyte.Stream for virtual terminal emulation."""

    def __init__(self, rows: int, cols: int) -> None:
        if not PYTE_AVAILABLE:
            raise RuntimeError("pyte is not installed")
        self._screen = pyte.Screen(cols, rows)
        self._stream = pyte.Stream(self._screen)
        self._dirty = False

    def feed(self, data: bytes) -> None:
        """Process raw PTY output bytes through the VT parser."""
        self._stream.feed(data.decode("utf-8", errors="replace"))
        self._dirty = True

    def resize(self, rows: int, cols: int) -> None:
        """Resize the virtual screen."""
        self._screen.resize(rows, cols)
        self._dirty = True

    def get_display(self) -> list[str]:
        """Return plain-text lines from the virtual screen buffer."""
        return list(self._screen.display)

    def get_buffer(self):
        """Access the pyte Screen.buffer (dict of {row: {col: Char}})."""
        return self._screen.buffer

    def get_cursor(self) -> tuple[int, int]:
        """Return (row, col) cursor position in the virtual screen."""
        return (self._screen.cursor.y, self._screen.cursor.x)

    @property
    def dirty(self) -> bool:
        return self._dirty

    def mark_clean(self) -> None:
        self._dirty = False

    @property
    def rows(self) -> int:
        return self._screen.lines

    @property
    def cols(self) -> int:
        return self._screen.columns
