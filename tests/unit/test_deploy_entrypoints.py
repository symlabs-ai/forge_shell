"""
Testes de deploy: isolamento de imports, entrypoints e specs.

Verifica que relay_main e host_main NÃO puxam forge_llm/httpx/pyte
para sys.modules, garantindo binários standalone leves.
"""
from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


# ===================================================================
# intercept_types — importável sem forge_llm
# ===================================================================

class TestInterceptTypes:
    """intercept_types deve ser importável sem dependências pesadas."""

    def test_import_standalone(self):
        """intercept_types não requer forge_llm, pyte, httpx."""
        mod = importlib.import_module("src.application.usecases.intercept_types")
        assert hasattr(mod, "InterceptAction")
        assert hasattr(mod, "InterceptResult")

    def test_action_values(self):
        from src.application.usecases.intercept_types import InterceptAction
        expected = {"toggle", "exec_bash", "show_suggestion", "explain", "help", "risk", "noop"}
        assert {a.value for a in InterceptAction} == expected

    def test_result_defaults(self):
        from src.application.usecases.intercept_types import InterceptAction, InterceptResult
        r = InterceptResult(action=InterceptAction.NOOP)
        assert r.bash_command is None
        assert r.suggestion is None
        assert r.requires_double_confirm is False
        assert r.risk_level is None

    def test_result_accepts_any_suggestion(self):
        """suggestion e risk_level aceitam Any (não só NLResponse/RiskLevel)."""
        from src.application.usecases.intercept_types import InterceptAction, InterceptResult
        r = InterceptResult(
            action=InterceptAction.SHOW_SUGGESTION,
            suggestion={"fake": True},
            risk_level="HIGH",
        )
        assert r.suggestion == {"fake": True}
        assert r.risk_level == "HIGH"

    def test_backward_compat_via_nl_interceptor(self):
        """nl_interceptor re-exporta InterceptAction e InterceptResult."""
        from src.application.usecases.nl_interceptor import InterceptAction, InterceptResult
        assert InterceptAction.TOGGLE.value == "toggle"
        assert InterceptResult is not None


# ===================================================================
# Import isolation — subprocess para evitar contaminação
# ===================================================================

class TestImportIsolation:
    """Verifica que entrypoints leves não importam deps pesadas."""

    @pytest.fixture(autouse=True)
    def _skip_if_no_src(self):
        """Skip se o pacote src não estiver instalado."""
        try:
            importlib.import_module("src.infrastructure.config.loader")
        except ImportError:
            pytest.skip("src package not available")

    def test_relay_main_no_forge_llm(self):
        """relay_main não puxa forge_llm para sys.modules."""
        code = (
            "import sys; "
            "from src.adapters.cli.relay_main import main; "
            "heavy = [m for m in sys.modules if m.startswith(('forge_llm', 'httpx', 'pyte'))]; "
            "print(','.join(heavy) if heavy else 'CLEAN')"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True, text=True, timeout=15,
            cwd=str(REPO_ROOT),
        )
        assert result.stdout.strip() == "CLEAN", f"Heavy deps loaded: {result.stdout.strip()}"

    def test_host_main_no_forge_llm(self):
        """host_main não puxa forge_llm para sys.modules."""
        code = (
            "import sys; "
            "from src.adapters.cli.host_main import main; "
            "heavy = [m for m in sys.modules if m.startswith(('forge_llm', 'httpx', 'pyte'))]; "
            "print(','.join(heavy) if heavy else 'CLEAN')"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True, text=True, timeout=15,
            cwd=str(REPO_ROOT),
        )
        assert result.stdout.strip() == "CLEAN", f"Heavy deps loaded: {result.stdout.strip()}"

    def test_intercept_types_no_forge_llm(self):
        """intercept_types não puxa forge_llm."""
        code = (
            "import sys; "
            "from src.application.usecases.intercept_types import InterceptAction; "
            "heavy = [m for m in sys.modules if m.startswith(('forge_llm', 'httpx', 'pyte'))]; "
            "print(','.join(heavy) if heavy else 'CLEAN')"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True, text=True, timeout=15,
            cwd=str(REPO_ROOT),
        )
        assert result.stdout.strip() == "CLEAN", f"Heavy deps loaded: {result.stdout.strip()}"


# ===================================================================
# Argument parsers
# ===================================================================

class TestRelayParser:
    """forge_relay argument parser."""

    def test_default_args(self):
        from src.adapters.cli.relay_main import build_parser
        args = build_parser().parse_args([])
        assert args.host == "0.0.0.0"
        assert args.port is None

    def test_custom_port(self):
        from src.adapters.cli.relay_main import build_parser
        args = build_parser().parse_args(["--port", "9000"])
        assert args.port == 9000

    def test_custom_host(self):
        from src.adapters.cli.relay_main import build_parser
        args = build_parser().parse_args(["--host", "127.0.0.1"])
        assert args.host == "127.0.0.1"

    def test_combined_args(self):
        from src.adapters.cli.relay_main import build_parser
        args = build_parser().parse_args(["--host", "10.0.0.1", "--port", "8070"])
        assert args.host == "10.0.0.1"
        assert args.port == 8070


class TestHostParser:
    """forge_host argument parser."""

    def test_default_no_command(self):
        from src.adapters.cli.host_main import build_parser
        args = build_parser().parse_args([])
        assert args.command is None

    def test_share_command(self):
        from src.adapters.cli.host_main import build_parser
        args = build_parser().parse_args(["share"])
        assert args.command == "share"
        assert args.regen is False

    def test_share_regen(self):
        from src.adapters.cli.host_main import build_parser
        args = build_parser().parse_args(["share", "--regen"])
        assert args.command == "share"
        assert args.regen is True


# ===================================================================
# Spec files
# ===================================================================

class TestSpecFiles:
    """Verifica que os .spec existem e excluem deps pesadas."""

    def test_forge_relay_spec_exists(self):
        assert (REPO_ROOT / "forge_relay.spec").is_file()

    def test_forge_host_spec_exists(self):
        assert (REPO_ROOT / "forge_host.spec").is_file()

    def test_forge_shell_spec_exists(self):
        assert (REPO_ROOT / "forge_shell.spec").is_file()

    def test_relay_spec_excludes_forge_llm(self):
        content = (REPO_ROOT / "forge_relay.spec").read_text()
        assert "'forge_llm'" in content
        # forge_llm deve estar na lista de excludes
        assert "excludes" in content

    def test_host_spec_excludes_forge_llm(self):
        content = (REPO_ROOT / "forge_host.spec").read_text()
        assert "'forge_llm'" in content
        assert "excludes" in content

    def test_shell_spec_includes_intercept_types(self):
        content = (REPO_ROOT / "forge_shell.spec").read_text()
        assert "intercept_types" in content

    def test_relay_spec_entry_is_relay_main(self):
        content = (REPO_ROOT / "forge_relay.spec").read_text()
        assert "relay_main.py" in content

    def test_host_spec_entry_is_host_main(self):
        content = (REPO_ROOT / "forge_host.spec").read_text()
        assert "host_main.py" in content


# ===================================================================
# Build script
# ===================================================================

class TestBuildScript:
    """Verifica que build.sh suporta targets individuais."""

    def test_build_script_exists(self):
        assert (REPO_ROOT / "scripts" / "build.sh").is_file()

    def test_build_script_supports_relay(self):
        content = (REPO_ROOT / "scripts" / "build.sh").read_text()
        assert "relay)" in content

    def test_build_script_supports_host(self):
        content = (REPO_ROOT / "scripts" / "build.sh").read_text()
        assert "host)" in content

    def test_build_script_supports_shell(self):
        content = (REPO_ROOT / "scripts" / "build.sh").read_text()
        assert "shell)" in content

    def test_build_script_supports_clean(self):
        content = (REPO_ROOT / "scripts" / "build.sh").read_text()
        assert "--clean" in content


# ===================================================================
# pyproject.toml entry points
# ===================================================================

class TestEntryPoints:
    """Verifica entry points no pyproject.toml."""

    def test_forge_relay_entry(self):
        content = (REPO_ROOT / "pyproject.toml").read_text()
        assert "forge_relay" in content
        assert "relay_main:main" in content

    def test_forge_host_entry(self):
        content = (REPO_ROOT / "pyproject.toml").read_text()
        assert "forge_host" in content
        assert "host_main:main" in content
