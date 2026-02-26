"""
C2-T-01 a C2-T-02 — Packaging + .gitattributes
DADO pyproject.toml e .gitattributes
QUANDO valido configuração do pacote
ENTÃO entry point, versão e line endings estão corretos
"""
from pathlib import Path
import pytest

ROOT = Path(__file__).parent.parent.parent


class TestPyprojectToml:
    def test_pyproject_exists(self) -> None:
        assert (ROOT / "pyproject.toml").exists()

    def test_has_version(self) -> None:
        content = (ROOT / "pyproject.toml").read_text()
        assert 'version' in content

    def test_version_is_0_3_2(self) -> None:
        content = (ROOT / "pyproject.toml").read_text()
        assert '0.3.3' in content

    def test_has_entry_point(self) -> None:
        content = (ROOT / "pyproject.toml").read_text()
        assert 'forge_shell' in content

    def test_entry_point_points_to_main(self) -> None:
        content = (ROOT / "pyproject.toml").read_text()
        assert 'main' in content

    def test_has_project_name(self) -> None:
        content = (ROOT / "pyproject.toml").read_text()
        assert 'forge-shell' in content or 'forge_shell' in content

    def test_has_python_requires(self) -> None:
        content = (ROOT / "pyproject.toml").read_text()
        assert 'python' in content.lower()


class TestGitattributes:
    def test_gitattributes_exists(self) -> None:
        assert (ROOT / ".gitattributes").exists()

    def test_has_text_auto(self) -> None:
        content = (ROOT / ".gitattributes").read_text()
        assert 'text=auto' in content or 'text auto' in content

    def test_sh_files_lf(self) -> None:
        content = (ROOT / ".gitattributes").read_text()
        assert '*.sh' in content and 'lf' in content

    def test_py_files_lf(self) -> None:
        content = (ROOT / ".gitattributes").read_text()
        assert '*.py' in content and 'lf' in content
