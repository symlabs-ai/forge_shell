"""
TmuxTerminal — E2E test harness for interactive CLIs using tmux.

Uses tmux as a real terminal emulator instead of pyte:
- `tmux send-keys -l` for literal keystrokes
- `tmux capture-pane -p` for rendered screen
- `tmux display-message -p '#{cursor_x} #{cursor_y}'` for real cursor position
"""
from __future__ import annotations

import subprocess
import time
import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class CursorSnapshot:
    """Snapshot of terminal state after a keystroke."""

    screen: list[str]
    cursor_x: int
    cursor_y: int
    char_typed: str


class TmuxTerminal:
    """Drives an interactive CLI inside a real tmux session."""

    def __init__(self, rows: int = 24, cols: int = 80):
        self.rows = rows
        self.cols = cols
        self.session_name: str | None = None
        self.keystroke_delay = 0.08  # 80ms between keystrokes

    # ── Lifecycle ──────────────────────────────────────────────

    def start(self, command: str) -> None:
        self.session_name = f"forge_test_{uuid.uuid4().hex[:8]}"
        self._run_tmux(
            "new-session", "-d",
            "-s", self.session_name,
            "-x", str(self.cols),
            "-y", str(self.rows),
            command,
        )

    def close(self) -> None:
        if self.session_name is None:
            return
        try:
            self._run_tmux("kill-session", "-t", self.session_name)
        except subprocess.CalledProcessError:
            pass
        self.session_name = None

    # ── Input ──────────────────────────────────────────────────

    def send_key(self, key: str) -> None:
        """Send a named key (Enter, F4, C-c, etc.) WITHOUT -l."""
        self._run_tmux("send-keys", "-t", self.session_name, key)

    def send_literal(self, char: str) -> None:
        """Send a literal character WITH -l (no name expansion)."""
        self._run_tmux("send-keys", "-t", self.session_name, "-l", char)

    def type_string(self, text: str) -> list[CursorSnapshot]:
        """Type text char-by-char, capturing a snapshot after each.

        After the base keystroke_delay, polls briefly for cursor movement
        to handle deferred rendering (split view).
        """
        snapshots: list[CursorSnapshot] = []
        for ch in text:
            prev_x, prev_y = self.cursor_position() if snapshots else (None, None)
            self.send_literal(ch)
            time.sleep(self.keystroke_delay)
            x, y = self.cursor_position()
            # If cursor didn't move, poll briefly for deferred render
            if prev_x is not None and x == prev_x and y == prev_y:
                deadline = time.monotonic() + 0.3
                while time.monotonic() < deadline:
                    time.sleep(0.05)
                    x, y = self.cursor_position()
                    if x != prev_x or y != prev_y:
                        break
            screen = self.capture_screen()
            snapshots.append(CursorSnapshot(
                screen=screen, cursor_x=x, cursor_y=y, char_typed=ch,
            ))
        return snapshots

    def press_enter(self) -> None:
        self.send_key("Enter")
        time.sleep(0.3)

    def press_f4(self) -> None:
        self.send_key("F4")
        time.sleep(0.3)

    def press_ctrl_close(self) -> None:
        self.send_key("C-]")
        time.sleep(0.3)

    # ── Screen reading ─────────────────────────────────────────

    def capture_screen(self) -> list[str]:
        """Return rendered screen lines via tmux capture-pane."""
        result = self._run_tmux(
            "capture-pane", "-t", self.session_name, "-p",
        )
        return result.stdout.splitlines()

    def cursor_position(self) -> tuple[int, int]:
        """Return (cursor_x, cursor_y) — 0-based."""
        result = self._run_tmux(
            "display-message", "-t", self.session_name,
            "-p", "#{cursor_x} #{cursor_y}",
        )
        parts = result.stdout.strip().split()
        return int(parts[0]), int(parts[1])

    # ── Wait helpers ───────────────────────────────────────────

    def wait_for_text(self, text: str, timeout: float = 10, poll: float = 0.2) -> None:
        """Poll until text appears on screen or timeout."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            screen = self.capture_screen()
            if any(text in line for line in screen):
                return
            time.sleep(poll)
        screen = self.capture_screen()
        raise TimeoutError(
            f"Text {text!r} not found within {timeout}s. Screen:\n"
            + "\n".join(screen)
        )

    def wait_for_cursor_stable(self, timeout: float = 2, poll: float = 0.1) -> None:
        """Poll until cursor stops moving."""
        prev = self.cursor_position()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            time.sleep(poll)
            curr = self.cursor_position()
            if curr == prev:
                return
            prev = curr
        raise TimeoutError("Cursor did not stabilize within {timeout}s")

    # ── Internal ───────────────────────────────────────────────

    def _run_tmux(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["tmux", *args],
            capture_output=True, text=True, check=True, timeout=5,
        )


# ── Assertion helpers ──────────────────────────────────────────


def assert_cursor_advances_monotonically(
    snapshots: list[CursorSnapshot],
    clamp_x: int | None = None,
    strict: bool = True,
) -> None:
    """Assert cursor_x advances monotonically, skipping line wraps.

    Args:
        snapshots: List of cursor snapshots after each keystroke.
        clamp_x: If set, cursor_x is expected to be clamped at this value
                 (e.g., split view right edge). Characters beyond this column
                 are skipped.
        strict: If True (default), cursor must advance exactly +1 per char.
                If False, cursor must only advance (no backward jumps), allowing
                batched rendering to produce +2 or more per snapshot.

    Detects two types of line wrap:
    - cursor_y changed (normal wrap)
    - cursor_x dropped to near 0 while cursor_y stayed the same (scroll-wrap
      at the bottom of the terminal — the screen scrolls up but cursor_y remains
      on the last visible row)
    """
    for i in range(1, len(snapshots)):
        prev = snapshots[i - 1]
        curr = snapshots[i]
        # Skip line wraps (cursor_y changed)
        if curr.cursor_y != prev.cursor_y:
            continue
        # Skip scroll-wraps (cursor_x dropped significantly on the same row)
        if curr.cursor_x < prev.cursor_x and prev.cursor_x - curr.cursor_x > 4:
            continue
        # Skip clamped region (cursor stuck at edge of visible pane)
        if clamp_x is not None and curr.cursor_x >= clamp_x and prev.cursor_x >= clamp_x:
            continue
        if strict:
            expected_x = prev.cursor_x + 1
            assert curr.cursor_x == expected_x, (
                f"Cursor jump at char {curr.char_typed!r} (index {i}): "
                f"expected x={expected_x}, got x={curr.cursor_x}. "
                f"Sequence: {[s.char_typed for s in snapshots[:i+1]]}"
            )
        else:
            assert curr.cursor_x > prev.cursor_x, (
                f"Cursor went backwards at char {curr.char_typed!r} (index {i}): "
                f"x {prev.cursor_x} -> {curr.cursor_x}. "
                f"Sequence: {[s.char_typed for s in snapshots[:i+1]]}"
            )


def assert_screen_contains(terminal: TmuxTerminal, text: str) -> None:
    """Assert text is visible on the terminal screen."""
    screen = terminal.capture_screen()
    assert any(text in line for line in screen), (
        f"Text {text!r} not found on screen:\n" + "\n".join(screen)
    )


def assert_screen_not_contains(terminal: TmuxTerminal, text: str) -> None:
    """Assert text is NOT visible on the terminal screen."""
    screen = terminal.capture_screen()
    assert not any(text in line for line in screen), (
        f"Text {text!r} unexpectedly found on screen:\n" + "\n".join(screen)
    )


def assert_screen_line(terminal: TmuxTerminal, row: int, pattern: str) -> None:
    """Assert that a specific screen line contains the pattern."""
    screen = terminal.capture_screen()
    assert row < len(screen), f"Row {row} out of range (screen has {len(screen)} lines)"
    assert pattern in screen[row], (
        f"Pattern {pattern!r} not found in row {row}: {screen[row]!r}"
    )
