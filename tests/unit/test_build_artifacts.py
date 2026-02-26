"""
Testes — Build distribuível (Feature 8)
DADO o repositório sym_shell
QUANDO verifico os artefatos de build
ENTÃO spec PyInstaller, script de build e deps standalone existem
"""
from pathlib import Path
import pytest

ROOT = Path(__file__).parent.parent.parent


class TestPyInstallerSpec:
    def test_spec_file_exists(self) -> None:
        assert (ROOT / "sym_shell.spec").exists()

    def test_spec_references_entry_point(self) -> None:
        content = (ROOT / "sym_shell.spec").read_text()
        assert "src/adapters/cli/main.py" in content

    def test_spec_has_console_true(self) -> None:
        content = (ROOT / "sym_shell.spec").read_text()
        assert "console=True" in content

    def test_spec_has_hidden_imports(self) -> None:
        content = (ROOT / "sym_shell.spec").read_text()
        assert "hiddenimports" in content

    def test_spec_includes_websockets(self) -> None:
        content = (ROOT / "sym_shell.spec").read_text()
        assert "websockets" in content

    def test_spec_excludes_pytest(self) -> None:
        content = (ROOT / "sym_shell.spec").read_text()
        assert "pytest" in content and "excludes" in content

    def test_spec_output_name_is_sym_shell(self) -> None:
        content = (ROOT / "sym_shell.spec").read_text()
        assert "name='sym_shell'" in content or 'name="sym_shell"' in content


class TestBuildScript:
    def test_build_script_exists(self) -> None:
        assert (ROOT / "scripts" / "build.sh").exists()

    def test_build_script_references_pyinstaller(self) -> None:
        content = (ROOT / "scripts" / "build.sh").read_text()
        assert "pyinstaller" in content.lower()

    def test_build_script_references_spec(self) -> None:
        content = (ROOT / "scripts" / "build.sh").read_text()
        assert "sym_shell.spec" in content

    def test_build_script_is_executable_or_has_shebang(self) -> None:
        content = (ROOT / "scripts" / "build.sh").read_text()
        assert content.startswith("#!/")


class TestPyprojectStandalone:
    def test_pyproject_has_standalone_dep(self) -> None:
        content = (ROOT / "pyproject.toml").read_text()
        assert "standalone" in content

    def test_pyproject_standalone_references_pyinstaller(self) -> None:
        content = (ROOT / "pyproject.toml").read_text()
        assert "pyinstaller" in content.lower()

    def test_pipx_install_possible(self) -> None:
        """pyproject.toml tem todos os campos necessários para pipx install."""
        content = (ROOT / "pyproject.toml").read_text()
        assert "[project.scripts]" in content
        assert "sym_shell" in content
        assert "name" in content
        assert "version" in content
