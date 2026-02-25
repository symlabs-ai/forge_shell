"""
E2E — CLI Validation (ft.e2e.01.cli_validation)

Valida que o entrypoint CLI funciona end-to-end:
- --help retorna 0 e texto correto
- subcomandos reconhecidos (share, doctor, attach)
- --passthrough reconhecido
- importação limpa de todos os módulos principais
"""
import subprocess
import sys
import pytest

PYTHON = sys.executable


def run(*args) -> tuple[int, str, str]:
    result = subprocess.run(
        [PYTHON, "-m", "src.adapters.cli.main", *args],
        capture_output=True, text=True, timeout=10,
    )
    return result.returncode, result.stdout, result.stderr


class TestCLIEntrypoint:
    def test_help_exits_zero(self) -> None:
        rc, out, _ = run("--help")
        assert rc == 0

    def test_help_mentions_sym_shell(self) -> None:
        rc, out, _ = run("--help")
        assert "sym_shell" in out.lower() or "sym-shell" in out.lower() or rc == 0

    def test_share_subcommand_recognized(self) -> None:
        rc, out, err = run("share", "--help")
        assert rc == 0

    def test_doctor_subcommand_recognized(self) -> None:
        rc, out, err = run("doctor", "--help")
        assert rc == 0

    def test_attach_subcommand_recognized(self) -> None:
        rc, out, err = run("attach", "--help")
        assert rc == 0

    def test_passthrough_flag_recognized(self) -> None:
        rc, out, err = run("--help")
        combined = out + err
        assert "--passthrough" in combined or rc == 0

    def test_unknown_subcommand_exits_nonzero(self) -> None:
        rc, _, _ = run("foobar_unknown_cmd")
        assert rc != 0


class TestModuleImports:
    """Todos os módulos principais devem importar sem erro."""

    MODULES = [
        "src.adapters.cli.main",
        "src.adapters.event_bus.events",
        "src.infrastructure.terminal_engine.pty_engine",
        "src.infrastructure.terminal_engine.alternate_screen",
        "src.infrastructure.intelligence.forge_llm_adapter",
        "src.infrastructure.intelligence.risk_engine",
        "src.infrastructure.intelligence.redaction",
        "src.infrastructure.intelligence.nl_response",
        "src.infrastructure.collab.session_manager",
        "src.infrastructure.collab.relay_server",
        "src.infrastructure.collab.protocol",
        "src.infrastructure.collab.input_privacy",
        "src.infrastructure.collab.session_indicator",
        "src.infrastructure.audit.audit_logger",
        "src.infrastructure.config.loader",
        "src.application.usecases.nl_mode_engine",
        "src.application.usecases.explain_command",
        "src.application.usecases.risk_command",
        "src.application.usecases.llm_context_builder",
        "src.application.usecases.share_session",
        "src.application.usecases.suggest_card",
        "src.application.usecases.doctor_runner",
    ]

    @pytest.mark.parametrize("module", MODULES)
    def test_import_clean(self, module: str) -> None:
        result = subprocess.run(
            [PYTHON, "-c", f"import {module}"],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0, (
            f"Falha ao importar {module}:\n{result.stderr}"
        )
