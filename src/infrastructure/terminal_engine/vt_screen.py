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


_NAMED_FG = {
    "black": b"30", "red": b"31", "green": b"32", "yellow": b"33",
    "blue": b"34", "magenta": b"35", "cyan": b"36", "white": b"37",
}
_NAMED_BG = {
    "black": b"40", "red": b"41", "green": b"42", "yellow": b"43",
    "blue": b"44", "magenta": b"45", "cyan": b"46", "white": b"47",
}


def _color_to_ansi(color: str, is_bg: bool = False) -> bytes | None:
    """Convert pyte color string to ANSI escape parameter bytes."""
    if color == "default":
        return None
    named = _NAMED_BG if is_bg else _NAMED_FG
    if color in named:
        return named[color]
    # pyte stores 256-color and RGB as hex strings (e.g. "ff8700")
    if len(color) == 6:
        try:
            r, g, b = int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)
            prefix = b"48;2;" if is_bg else b"38;2;"
            return prefix + f"{r};{g};{b}".encode()
        except ValueError:
            return None
    return None


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

    def get_display_ansi(self, max_cols: int | None = None) -> list[bytes]:
        """Return ANSI-formatted byte lines preserving colors and attributes.

        Args:
            max_cols: If set, clip each line to this many visible columns.
        """
        result: list[bytes] = []
        buf = self._screen.buffer
        cols = self._screen.columns if max_cols is None else min(max_cols, self._screen.columns)
        rows = self._screen.lines
        default_char = self._screen.default_char

        for row in range(rows):
            line = bytearray()
            prev_style: tuple | None = None

            for col in range(cols):
                char = buf[row].get(col, default_char)
                style = (char.fg, char.bg, char.bold, char.italics,
                         char.underscore, char.reverse)

                if style != prev_style:
                    # Emit reset + new style
                    params: list[bytes] = []
                    if char.bold:
                        params.append(b"1")
                    if char.italics:
                        params.append(b"3")
                    if char.underscore:
                        params.append(b"4")
                    if char.reverse:
                        params.append(b"7")
                    fg = _color_to_ansi(char.fg, is_bg=False)
                    if fg:
                        params.append(fg)
                    bg = _color_to_ansi(char.bg, is_bg=True)
                    if bg:
                        params.append(bg)

                    if params:
                        line.extend(b"\033[0;" + b";".join(params) + b"m")
                    elif prev_style is not None:
                        line.extend(b"\033[0m")
                    prev_style = style

                line.extend(char.data.encode("utf-8", errors="replace"))

            # Reset at end of line
            if prev_style is not None and prev_style != (
                "default", "default", False, False, False, False
            ):
                line.extend(b"\033[0m")

            result.append(bytes(line))
        return result

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
