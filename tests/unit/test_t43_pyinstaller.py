"""
T-43 — Build pipeline PyInstaller
DADO o arquivo sym_shell.spec e o script de build
QUANDO valido a configuração
ENTÃO o spec existe com entrypoint correto e o script de build existe
"""
import pytest
from pathlib import Path


REPO_ROOT = Path(__file__).parent.parent.parent


class TestPyInstallerConfig:
    def test_spec_file_exists(self) -> None:
        spec = REPO_ROOT / "sym_shell.spec"
        assert spec.exists(), f"sym_shell.spec não encontrado em {REPO_ROOT}"

    def test_spec_references_main_entrypoint(self) -> None:
        spec = REPO_ROOT / "sym_shell.spec"
        content = spec.read_text()
        assert "main.py" in content or "main" in content

    def test_spec_sets_binary_name(self) -> None:
        spec = REPO_ROOT / "sym_shell.spec"
        content = spec.read_text()
        assert "sym_shell" in content

    def test_spec_onefile_mode(self) -> None:
        spec = REPO_ROOT / "sym_shell.spec"
        content = spec.read_text()
        assert "EXE" in content

    def test_build_script_exists(self) -> None:
        script = REPO_ROOT / "scripts" / "build.sh"
        assert script.exists(), f"scripts/build.sh não encontrado"

    def test_build_script_is_executable(self) -> None:
        script = REPO_ROOT / "scripts" / "build.sh"
        assert script.stat().st_mode & 0o111, "scripts/build.sh não é executável"

    def test_build_script_references_pyinstaller(self) -> None:
        script = REPO_ROOT / "scripts" / "build.sh"
        content = script.read_text()
        assert "pyinstaller" in content.lower()

    def test_requirements_includes_pyinstaller_in_dev(self) -> None:
        req = REPO_ROOT / "env" / "requirements-dev.txt"
        assert req.exists(), "env/requirements-dev.txt não encontrado"
        content = req.read_text()
        assert "pyinstaller" in content.lower()
