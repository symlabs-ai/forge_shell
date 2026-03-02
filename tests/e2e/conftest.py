"""
Pytest fixtures for E2E tests using TmuxTerminal.

Includes cleanup of stale tmux sessions and relay health validation.
"""
import asyncio
import base64
import json
import ssl
import subprocess
import time

import pytest

from tests.e2e.tmux_harness import TmuxTerminal

MACHINE_CODE = "015-801-152"
PASSWORD = "831456"
RELAY_URL = "wss://relay.palhano.services"
_TMUX_PREFIX = "forge_test_"


def _kill_stale_tmux_sessions() -> int:
    """Kill any leftover forge_test_* tmux sessions from previous runs."""
    try:
        result = subprocess.run(
            ["tmux", "list-sessions", "-F", "#{session_name}"],
            capture_output=True, text=True, timeout=5,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return 0
    killed = 0
    for name in result.stdout.strip().splitlines():
        if name.startswith(_TMUX_PREFIX):
            try:
                subprocess.run(
                    ["tmux", "kill-session", "-t", name],
                    capture_output=True, timeout=5,
                )
                killed += 1
            except Exception:
                pass
    return killed


def _check_relay_echo_count() -> int:
    """Connect to relay, send one keystroke, count echoes. Returns echo count.

    Sends Enter (produces prompt echo), counts terminal_output messages.
    Returns -1 if relay is unreachable or websockets not installed.
    """

    async def _probe():
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        try:
            import websockets
        except ImportError:
            return -1

        try:
            ws = await asyncio.wait_for(
                websockets.connect(RELAY_URL, ssl=ctx), timeout=5,
            )
        except Exception:
            return -1

        await ws.send(json.dumps({
            "type": "session_join",
            "session_id": MACHINE_CODE,
            "payload": {"role": "viewer", "token": PASSWORD},
        }).encode())

        # Drain initial output (prompt, etc.)
        try:
            while True:
                await asyncio.wait_for(ws.recv(), timeout=2.0)
        except asyncio.TimeoutError:
            pass

        # Send Enter — always produces output (new prompt)
        await ws.send(json.dumps({
            "type": "terminal_input",
            "session_id": MACHINE_CODE,
            "payload": {"data": base64.b64encode(b"\r").decode()},
        }).encode())

        count = 0
        try:
            while True:
                raw = await asyncio.wait_for(ws.recv(), timeout=2.0)
                msg = json.loads(raw)
                if msg.get("type") == "terminal_output":
                    count += 1
        except asyncio.TimeoutError:
            pass

        await ws.close()
        return count

    return asyncio.run(_probe())


@pytest.fixture(scope="session", autouse=True)
def _cleanup_environment():
    """Session-scoped: clean stale tmux sessions and validate relay before any test."""
    killed = _kill_stale_tmux_sessions()
    if killed:
        print(f"\n[conftest] Killed {killed} stale forge_test_* tmux session(s)")

    echo_count = _check_relay_echo_count()
    if echo_count > 3:
        pytest.fail(
            f"Relay has {echo_count} output messages per Enter (expected 1-3). "
            f"Multiple forge_host processes may be sharing session {MACHINE_CODE}. "
            f"Fix: kill stale forge_host processes on the server and restart the relay."
        )
    if echo_count == 0:
        pytest.fail(
            f"Relay returned 0 echoes — no forge_host running for session {MACHINE_CODE}."
        )
    # echo_count == -1 means we couldn't check (no websockets, network issue) — proceed anyway


@pytest.fixture(scope="module")
def tmux_session():
    """Shared tmux session for all tests in the module."""
    terminal = TmuxTerminal(rows=24, cols=80)
    terminal.start(f"forge_shell attach {MACHINE_CODE} {PASSWORD}")

    try:
        terminal.wait_for_text("Ctrl+]", timeout=15)
    except TimeoutError as exc:
        terminal.close()
        pytest.fail(f"Failed to connect to host: {exc}")

    time.sleep(1.0)  # prompt settle

    yield terminal

    # Teardown: always kill the session
    try:
        terminal.press_ctrl_close()
        time.sleep(0.5)
    except Exception:
        pass
    terminal.close()
