"""
C4-T-01 — RelayConfig em SymShellConfig
DADO ConfigLoader
QUANDO relay não está no config.yaml
ENTÃO defaults são carregados (url=ws://localhost:8765, port=8765)
QUANDO relay está no config.yaml
ENTÃO valores custom são carregados
"""
import pytest
from unittest.mock import patch, mock_open
from src.infrastructure.config.loader import ConfigLoader, SymShellConfig


class TestRelayConfigDefaults:
    def test_relay_config_exists_in_symshellconfig(self) -> None:
        config = ConfigLoader().load()
        assert hasattr(config, "relay")

    def test_relay_default_url(self) -> None:
        config = ConfigLoader().load()
        assert config.relay.url == "ws://localhost:8765"

    def test_relay_default_port(self) -> None:
        config = ConfigLoader().load()
        assert config.relay.port == 8765

    def test_relay_default_tls_false(self) -> None:
        config = ConfigLoader().load()
        assert config.relay.tls is False


class TestRelayConfigFromFile:
    def test_relay_url_from_yaml(self, tmp_path) -> None:
        cfg = tmp_path / "config.yaml"
        cfg.write_text("relay:\n  url: ws://relay.example.com:9000\n  port: 9000\n")
        loader = ConfigLoader(config_path=cfg)
        config = loader.load()
        assert config.relay.url == "ws://relay.example.com:9000"
        assert config.relay.port == 9000

    def test_relay_tls_from_yaml(self, tmp_path) -> None:
        cfg = tmp_path / "config.yaml"
        cfg.write_text("relay:\n  tls: true\n")
        loader = ConfigLoader(config_path=cfg)
        config = loader.load()
        assert config.relay.tls is True

    def test_relay_partial_config_uses_defaults(self, tmp_path) -> None:
        cfg = tmp_path / "config.yaml"
        cfg.write_text("relay:\n  port: 9999\n")
        loader = ConfigLoader(config_path=cfg)
        config = loader.load()
        assert config.relay.port == 9999
        assert config.relay.url == "ws://localhost:8765"  # default mantido

    def test_non_relay_config_unaffected(self, tmp_path) -> None:
        cfg = tmp_path / "config.yaml"
        cfg.write_text("nl_mode:\n  default_active: false\n")
        loader = ConfigLoader(config_path=cfg)
        config = loader.load()
        assert config.nl_mode.default_active is False
        assert config.relay.url == "ws://localhost:8765"  # default relay
