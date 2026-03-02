"""
Smoke tests PTY — regressões de I/O interativo.

Verificam comportamento real do forge_shell num PTY via pexpect.
Requer: pip install pexpect

Cenários cobertos:
- Startup: hint aparece, bash prompt aparece
- Toggle: indicador "Bash Mode / NL Mode" aparece; prompt de bash surge automaticamente
  (regressão do bug de 9s de delay após toggle)
- Bash Escape (!cmd): comando executa, _pty_running=True → input interativo vai ao PTY
  (regressão do bug de senha do sudo exposta / enviada ao LLM)
- Bash Mode: comandos executam diretamente
- Passthrough: --passthrough liga PTY puro sem NL Mode
"""
import sys
import time
from pathlib import Path

import pytest

try:
    import pexpect
    PEXPECT_AVAILABLE = True
except ImportError:
    PEXPECT_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not PEXPECT_AVAILABLE, reason="pexpect não instalado"
)

PROJECT_DIR = str(Path(__file__).parent.parent.parent)
TIMEOUT = 10


def _noagent_config() -> str:
    """Cria config temporário com agent desabilitado. Retorna path."""
    import tempfile, os, yaml  # noqa: E401
    cfg_dir = tempfile.mkdtemp(prefix="forge_shell_test_")
    cfg_path = os.path.join(cfg_dir, "config.yaml")
    real_cfg = Path.home() / ".forge_shell" / "config.yaml"
    data: dict = {}
    if real_cfg.exists():
        with open(real_cfg) as f:
            data = yaml.safe_load(f) or {}
    data.setdefault("agent", {})["enabled"] = False
    with open(cfg_path, "w") as f:
        yaml.dump(data, f)
    return cfg_path


def _spawn(args: list[str] | None = None, env: dict[str, str] | None = None) -> "pexpect.spawn":
    """Spawna forge_shell num PTY real via pexpect."""
    import os as _os
    spawn_env = _os.environ.copy()
    if env:
        spawn_env.update(env)
    argv = ["-m", "src.adapters.cli.main"] + (args or [])
    return pexpect.spawn(
        sys.executable, argv,
        cwd=PROJECT_DIR,
        timeout=TIMEOUT,
        encoding="utf-8",
        env=spawn_env,
    )


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

class TestStartup:
    def test_startup_hint_appears(self):
        child = _spawn()
        try:
            child.expect("forge_shell", timeout=5)
        finally:
            child.close(force=True)

    def test_bash_prompt_appears(self):
        child = _spawn()
        try:
            child.expect(r"\$", timeout=10)
        finally:
            child.close(force=True)


# ---------------------------------------------------------------------------
# Toggle (!) — regressão do delay de 9s
# ---------------------------------------------------------------------------

class TestToggle:
    def test_toggle_shows_bash_mode_indicator(self):
        child = _spawn()
        try:
            child.expect(r"\$", timeout=10)
            child.sendline("!")
            child.expect("Bash Mode", timeout=5)
        finally:
            child.close(force=True)

    def test_toggle_prompt_appears_without_extra_enter(self):
        """Regressão: antes do fix o prompt de bash levava ~9s após toggle."""
        child = _spawn()
        try:
            child.expect(r"\$", timeout=10)
            t0 = time.monotonic()
            child.sendline("!")
            child.expect("Bash Mode", timeout=5)
            child.expect(r"\$", timeout=5)  # deve aparecer automaticamente
            elapsed = time.monotonic() - t0
            assert elapsed < 3.0, f"Toggle demorou {elapsed:.1f}s (esperado < 3s)"
        finally:
            child.close(force=True)

    def test_toggle_back_to_nl_mode(self):
        child = _spawn()
        try:
            child.expect(r"\$", timeout=10)
            child.sendline("!")       # → Bash Mode
            child.expect("Bash Mode", timeout=5)
            child.expect(r"\$", timeout=5)
            child.sendline("!")       # → NL Mode
            child.expect("NL Mode", timeout=5)
        finally:
            child.close(force=True)


# ---------------------------------------------------------------------------
# Bash Escape (!cmd) — regressão da senha exposta
# ---------------------------------------------------------------------------

class TestBashEscape:
    """Testa !cmd como bash escape direto (requer agent desabilitado)."""

    def test_bash_escape_executes_command(self):
        cfg = _noagent_config()
        child = _spawn(env={"FORGE_SHELL_CONFIG": cfg})
        try:
            child.expect(r"\$", timeout=10)
            child.sendline("!echo SMOKE_OK")
            child.expect("SMOKE_OK", timeout=5)
        finally:
            child.close(force=True)

    def test_pty_running_after_exec_bash(self):
        """
        Regressão: antes do fix, após !cmd o _pty_running ficava False.
        Input interativo (ex: senha do sudo) ia para o NL buffer → LLM.
        Agora deve ir direto ao PTY.
        """
        cfg = _noagent_config()
        child = _spawn(env={"FORGE_SHELL_CONFIG": cfg})
        try:
            child.expect(r"\$", timeout=10)
            # read -p exige input interativo; só completa se _pty_running=True
            child.sendline("!read -p 'INPUT_PROMPT: ' __SMOKE__")
            child.expect("INPUT_PROMPT:", timeout=10)
            child.sendline("smoke_value")
            child.expect(r"\$", timeout=5)
            # se _pty_running fosse False, "pensando" apareceria no output
            output = child.before or ""
            assert "pensando" not in output.lower(), (
                "LLM foi acionado para input interativo — _pty_running não estava True após EXEC_BASH"
            )
        finally:
            child.close(force=True)


# ---------------------------------------------------------------------------
# Bash Mode direto
# ---------------------------------------------------------------------------

class TestBashMode:
    def test_bash_mode_commands_execute(self):
        child = _spawn()
        try:
            child.expect(r"\$", timeout=10)
            child.sendline("!")       # → Bash Mode
            child.expect("Bash Mode", timeout=5)
            child.expect(r"\$", timeout=5)
            child.sendline("echo BASH_MODE_OK")
            child.expect("BASH_MODE_OK", timeout=5)
        finally:
            child.close(force=True)


# ---------------------------------------------------------------------------
# Passthrough
# ---------------------------------------------------------------------------

class TestPassthrough:
    def test_passthrough_executes_commands(self):
        child = _spawn(["--passthrough"])
        try:
            child.expect(r"\$", timeout=10)
            child.sendline("echo PASSTHROUGH_OK")
            child.expect("PASSTHROUGH_OK", timeout=5)
        finally:
            child.close(force=True)
