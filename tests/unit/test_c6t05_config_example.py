"""
C6-T-05 — config.yaml exemplo gerado na primeira execução
DADO ~/.sym_shell/ não existe
QUANDO ConfigLoader.ensure_config_dir() é chamado
ENTÃO ~/.sym_shell/ é criado
ENTÃO ~/.sym_shell/config.yaml.example é criado com conteúdo válido YAML
"""
import pytest
import yaml
from pathlib import Path
from src.infrastructure.config.loader import ConfigLoader


class TestConfigExample:
    def test_ensure_config_dir_creates_directory(self, tmp_path) -> None:
        cfg_dir = tmp_path / ".sym_shell"
        assert not cfg_dir.exists()
        loader = ConfigLoader(config_path=cfg_dir / "config.yaml")
        loader.ensure_config_dir()
        assert cfg_dir.exists()

    def test_ensure_config_dir_creates_example_file(self, tmp_path) -> None:
        cfg_dir = tmp_path / ".sym_shell"
        loader = ConfigLoader(config_path=cfg_dir / "config.yaml")
        loader.ensure_config_dir()
        example = cfg_dir / "config.yaml.example"
        assert example.exists(), "config.yaml.example deve ser criado"

    def test_example_file_is_valid_yaml(self, tmp_path) -> None:
        cfg_dir = tmp_path / ".sym_shell"
        loader = ConfigLoader(config_path=cfg_dir / "config.yaml")
        loader.ensure_config_dir()
        example = cfg_dir / "config.yaml.example"
        data = yaml.safe_load(example.read_text())
        assert isinstance(data, dict)

    def test_example_file_contains_key_sections(self, tmp_path) -> None:
        cfg_dir = tmp_path / ".sym_shell"
        loader = ConfigLoader(config_path=cfg_dir / "config.yaml")
        loader.ensure_config_dir()
        data = yaml.safe_load((cfg_dir / "config.yaml.example").read_text())
        assert "llm" in data
        assert "relay" in data
        assert "nl_mode" in data

    def test_ensure_config_dir_idempotent(self, tmp_path) -> None:
        cfg_dir = tmp_path / ".sym_shell"
        loader = ConfigLoader(config_path=cfg_dir / "config.yaml")
        loader.ensure_config_dir()
        loader.ensure_config_dir()  # segunda chamada não deve lançar

    def test_load_calls_ensure_config_dir(self, tmp_path) -> None:
        cfg_dir = tmp_path / ".sym_shell"
        loader = ConfigLoader(config_path=cfg_dir / "config.yaml")
        loader.load()  # load() deve chamar ensure_config_dir()
        assert cfg_dir.exists()
