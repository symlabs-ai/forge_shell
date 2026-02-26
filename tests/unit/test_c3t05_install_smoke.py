"""
C3-T-05 — pip install -e . smoke
DADO pyproject.toml com entry_point configurado
QUANDO valido a instalabilidade do pacote
ENTÃO o módulo é importável como pacote e o entry_point é configurado
"""
import subprocess
import sys
from pathlib import Path
import pytest

PYTHON = sys.executable
ROOT = Path(__file__).parent.parent.parent


class TestInstallSmoke:
    def test_pyproject_has_scripts_section(self) -> None:
        content = (ROOT / "pyproject.toml").read_text()
        assert "[project.scripts]" in content

    def test_entry_point_maps_to_main_function(self) -> None:
        content = (ROOT / "pyproject.toml").read_text()
        assert "src.adapters.cli.main:main" in content

    def test_main_function_callable(self) -> None:
        result = subprocess.run(
            [PYTHON, "-c",
             "from src.adapters.cli.main import main; assert callable(main); print('ok')"],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
        assert "ok" in result.stdout

    def test_package_structure_valid(self) -> None:
        """Todos os __init__.py existem nos pacotes declarados."""
        packages = [
            ROOT / "src" / "__init__.py",
            ROOT / "src" / "adapters" / "__init__.py",
            ROOT / "src" / "application" / "__init__.py",
            ROOT / "src" / "infrastructure" / "__init__.py",
        ]
        for p in packages:
            assert p.exists(), f"Missing {p}"

    def test_sym_shell_module_runs_help(self) -> None:
        result = subprocess.run(
            [PYTHON, "-m", "src.adapters.cli.main", "--help"],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0

    def test_pyproject_has_requires_python(self) -> None:
        content = (ROOT / "pyproject.toml").read_text()
        assert "requires-python" in content

    def test_pyproject_version_format(self) -> None:
        import re
        content = (ROOT / "pyproject.toml").read_text()
        match = re.search(r'version\s*=\s*"(\d+\.\d+\.\d+)"', content)
        assert match is not None, "Versão não encontrada no pyproject.toml"
        assert match.group(1) == "0.3.2"
