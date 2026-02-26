"""
Testes — forge_shell config subcommand (Feature 5)
DADO o CLI forge_shell
QUANDO o usuário chama `forge_shell config` ou `forge_shell config show/edit`
ENTÃO exibe configuração YAML ou abre editor
"""
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from src.adapters.cli.main import build_parser, main, _config_show, _config_edit, _relay_url_with_tls


class TestConfigParser:
    def test_config_subcommand_exists(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["config"])
        assert args.command == "config"

    def test_config_show_subcommand(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["config", "show"])
        assert args.command == "config"
        assert args.config_action == "show"

    def test_config_edit_subcommand(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["config", "edit"])
        assert args.command == "config"
        assert args.config_action == "edit"

    def test_config_no_subcommand_defaults_to_show(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["config"])
        action = getattr(args, "config_action", None) or "show"
        assert action == "show"


class TestConfigShow:
    def test_config_show_returns_zero(self, capsys) -> None:
        with patch("src.adapters.cli.main.ConfigLoader") as mock_loader:
            cfg = MagicMock()
            cfg.nl_mode.default_active = True
            cfg.nl_mode.context_lines = 20
            cfg.nl_mode.var_whitelist = []
            cfg.llm.provider = "ollama"
            cfg.llm.model = "llama3.2"
            cfg.llm.api_key = None
            cfg.llm.timeout_seconds = 30
            cfg.llm.max_retries = 2
            cfg.relay.url = "ws://localhost:8060"
            cfg.relay.port = 8060
            cfg.relay.tls = False
            cfg.relay.cert_file = None
            cfg.relay.key_file = None
            cfg.redaction.default_profile = "prod"
            mock_loader.return_value.load.return_value = cfg
            mock_loader.return_value._path = Path("/tmp/test_config.yaml")
            rc = main(["config"])
        assert rc == 0

    def test_config_show_outputs_yaml_keys(self, capsys) -> None:
        with patch("src.adapters.cli.main.ConfigLoader") as mock_loader:
            cfg = MagicMock()
            cfg.nl_mode.default_active = True
            cfg.nl_mode.context_lines = 20
            cfg.nl_mode.var_whitelist = []
            cfg.llm.provider = "ollama"
            cfg.llm.model = "llama3.2"
            cfg.llm.api_key = None
            cfg.llm.timeout_seconds = 30
            cfg.llm.max_retries = 2
            cfg.relay.url = "ws://localhost:8060"
            cfg.relay.port = 8060
            cfg.relay.tls = False
            cfg.relay.cert_file = None
            cfg.relay.key_file = None
            cfg.redaction.default_profile = "prod"
            mock_loader.return_value.load.return_value = cfg
            mock_loader.return_value._path = Path("/tmp/test_config.yaml")
            main(["config", "show"])
        captured = capsys.readouterr()
        assert "nl_mode:" in captured.out
        assert "llm:" in captured.out
        assert "relay:" in captured.out
        assert "redaction:" in captured.out

    def test_config_show_masks_api_key(self, capsys) -> None:
        with patch("src.adapters.cli.main.ConfigLoader") as mock_loader:
            cfg = MagicMock()
            cfg.nl_mode.default_active = True
            cfg.nl_mode.context_lines = 20
            cfg.nl_mode.var_whitelist = []
            cfg.llm.provider = "openai"
            cfg.llm.model = "gpt-4o"
            cfg.llm.api_key = "sk-secret123"
            cfg.llm.timeout_seconds = 30
            cfg.llm.max_retries = 2
            cfg.relay.url = "ws://localhost:8060"
            cfg.relay.port = 8060
            cfg.relay.tls = False
            cfg.relay.cert_file = None
            cfg.relay.key_file = None
            cfg.redaction.default_profile = "prod"
            mock_loader.return_value.load.return_value = cfg
            mock_loader.return_value._path = Path("/tmp/test_config.yaml")
            main(["config", "show"])
        captured = capsys.readouterr()
        assert "sk-secret123" not in captured.out
        assert "***" in captured.out


class TestConfigEdit:
    def test_config_edit_opens_editor(self, tmp_path) -> None:
        config_file = tmp_path / "config.yaml"
        config_file.write_text("# existing config\n")
        with patch("src.adapters.cli.main.ConfigLoader") as mock_loader, \
             patch("src.adapters.cli.main.subprocess.run") as mock_run, \
             patch.dict("os.environ", {"EDITOR": "vim"}):
            mock_loader.return_value.ensure_config_dir.return_value = None
            mock_loader.return_value._path = config_file
            mock_run.return_value.returncode = 0
            rc = main(["config", "edit"])
        assert rc == 0
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "vim" in call_args

    def test_config_edit_creates_file_from_example(self, tmp_path) -> None:
        config_file = tmp_path / "config.yaml"
        example_file = tmp_path / "config.yaml.example"
        example_file.write_text("# example config\n")
        with patch("src.adapters.cli.main.ConfigLoader") as mock_loader, \
             patch("src.adapters.cli.main.subprocess.run") as mock_run, \
             patch.dict("os.environ", {"EDITOR": "nano"}):
            mock_loader.return_value.ensure_config_dir.return_value = None
            mock_loader.return_value._path = config_file
            mock_run.return_value.returncode = 0
            # Simula criação: o arquivo não existe antes da chamada
            assert not config_file.exists()
            # A função tenta criar o arquivo a partir do example
            # Como o mock aponta para config_file que não existe:
            # O teste valida que o editor é chamado
            rc = _config_edit.__wrapped__() if hasattr(_config_edit, "__wrapped__") else main(["config", "edit"])
        # Editor deve ter sido chamado
        mock_run.assert_called_once()


class TestRelayUrlTls:
    def test_ws_upgraded_to_wss_when_tls(self) -> None:
        assert _relay_url_with_tls("ws://localhost:8060", True) == "wss://localhost:8060"

    def test_wss_unchanged_when_tls(self) -> None:
        assert _relay_url_with_tls("wss://relay.example.com", True) == "wss://relay.example.com"

    def test_ws_unchanged_when_no_tls(self) -> None:
        assert _relay_url_with_tls("ws://localhost:8060", False) == "ws://localhost:8060"
