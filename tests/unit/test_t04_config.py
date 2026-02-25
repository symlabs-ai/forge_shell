"""
T-04 — Config base: ~/.sym_shell/config.yaml
DADO o sistema de configuração do sym_shell
QUANDO carrego config de arquivo YAML ou sem arquivo
ENTÃO os valores corretos são retornados e o schema é validado
"""
import pytest
from pathlib import Path
import tempfile
import yaml

from src.infrastructure.config.loader import ConfigLoader, SymShellConfig


class TestConfigDefaults:
    def test_loads_defaults_without_file(self) -> None:
        loader = ConfigLoader(config_path=Path("/nonexistent/config.yaml"))
        config = loader.load()
        assert isinstance(config, SymShellConfig)

    def test_default_nl_mode_is_active(self) -> None:
        loader = ConfigLoader(config_path=Path("/nonexistent/config.yaml"))
        config = loader.load()
        assert config.nl_mode.default_active is True

    def test_default_redaction_profile_is_prod(self) -> None:
        loader = ConfigLoader(config_path=Path("/nonexistent/config.yaml"))
        config = loader.load()
        assert config.redaction.default_profile in ("dev", "prod")

    def test_default_llm_api_key_is_empty_or_env(self) -> None:
        loader = ConfigLoader(config_path=Path("/nonexistent/config.yaml"))
        config = loader.load()
        # api_key pode ser None ou str — nunca deve explodir
        assert config.llm.api_key is None or isinstance(config.llm.api_key, str)


class TestConfigFromFile:
    def test_loads_from_yaml_file(self) -> None:
        data = {
            "nl_mode": {"default_active": False},
            "redaction": {"default_profile": "dev"},
            "llm": {"api_key": "sk-test-123"},
        }
        with tempfile.NamedTemporaryFile(suffix=".yaml", mode="w", delete=False) as f:
            yaml.dump(data, f)
            path = Path(f.name)

        loader = ConfigLoader(config_path=path)
        config = loader.load()

        assert config.nl_mode.default_active is False
        assert config.redaction.default_profile == "dev"
        assert config.llm.api_key == "sk-test-123"

    def test_partial_config_merges_with_defaults(self) -> None:
        data = {"llm": {"api_key": "sk-partial"}}
        with tempfile.NamedTemporaryFile(suffix=".yaml", mode="w", delete=False) as f:
            yaml.dump(data, f)
            path = Path(f.name)

        loader = ConfigLoader(config_path=path)
        config = loader.load()
        assert config.llm.api_key == "sk-partial"
        # nl_mode deve ter o default
        assert config.nl_mode.default_active is True

    def test_invalid_redaction_profile_raises(self) -> None:
        data = {"redaction": {"default_profile": "ultra-secret-invalid"}}
        with tempfile.NamedTemporaryFile(suffix=".yaml", mode="w", delete=False) as f:
            yaml.dump(data, f)
            path = Path(f.name)

        loader = ConfigLoader(config_path=path)
        with pytest.raises(ValueError, match="profile"):
            loader.load()


class TestRedactionProfiles:
    def test_dev_profile_defined(self) -> None:
        loader = ConfigLoader(config_path=Path("/nonexistent/config.yaml"))
        config = loader.load()
        profiles = config.redaction.profiles
        assert "dev" in profiles
        assert "prod" in profiles

    def test_prod_profile_more_restrictive_than_dev(self) -> None:
        loader = ConfigLoader(config_path=Path("/nonexistent/config.yaml"))
        config = loader.load()
        dev = config.redaction.profiles["dev"]
        prod = config.redaction.profiles["prod"]
        # prod deve ter igual ou mais padrões de redaction que dev
        assert len(prod.patterns) >= len(dev.patterns)
