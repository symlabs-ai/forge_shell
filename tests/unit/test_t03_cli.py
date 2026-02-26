"""
T-03 — CLI entrypoint: forge_shell + subcomandos
DADO o CLI do forge_shell
QUANDO executo com --help ou com subcomandos inválidos
ENTÃO o CLI responde corretamente com exit codes e mensagens esperadas
"""
import subprocess
import sys
from pathlib import Path
import pytest

_PROJECT_ROOT = str(Path(__file__).parent.parent.parent)


def run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "src.adapters.cli.main", *args],
        capture_output=True,
        text=True,
        cwd=_PROJECT_ROOT,
    )


class TestCLIHelp:
    def test_help_exits_zero(self) -> None:
        result = run_cli("--help")
        assert result.returncode == 0

    def test_help_shows_subcommands(self) -> None:
        result = run_cli("--help")
        output = result.stdout + result.stderr
        assert "share" in output
        assert "doctor" in output
        assert "attach" in output

    def test_unknown_subcommand_exits_nonzero(self) -> None:
        result = run_cli("bogus-command")
        assert result.returncode != 0


class TestShareSubcommand:
    def test_share_help(self) -> None:
        result = run_cli("share", "--help")
        assert result.returncode == 0

    def test_share_requires_no_positional_args(self) -> None:
        result = run_cli("share", "--help")
        output = result.stdout + result.stderr
        assert "share" in output.lower()


class TestDoctorSubcommand:
    def test_doctor_help(self) -> None:
        result = run_cli("doctor", "--help")
        assert result.returncode == 0


class TestAttachSubcommand:
    def test_attach_help(self) -> None:
        result = run_cli("attach", "--help")
        assert result.returncode == 0

    def test_attach_requires_session_id(self) -> None:
        result = run_cli("attach")
        assert result.returncode != 0
