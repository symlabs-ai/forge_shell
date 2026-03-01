"""Tests for AgentConfig — defaults and YAML parsing."""
import tempfile
from pathlib import Path

import yaml
import pytest

from src.infrastructure.config.loader import ConfigLoader, ForgeShellConfig, AgentConfig


class TestAgentConfigDefaults:
    def test_default_agent_disabled(self) -> None:
        loader = ConfigLoader(config_path=Path("/nonexistent/config.yaml"))
        config = loader.load()
        assert config.agent.enabled is False

    def test_default_max_tool_rounds(self) -> None:
        loader = ConfigLoader(config_path=Path("/nonexistent/config.yaml"))
        config = loader.load()
        assert config.agent.max_tool_rounds == 15

    def test_default_exec_timeout(self) -> None:
        loader = ConfigLoader(config_path=Path("/nonexistent/config.yaml"))
        config = loader.load()
        assert config.agent.exec_timeout == 60

    def test_default_memory_enabled(self) -> None:
        loader = ConfigLoader(config_path=Path("/nonexistent/config.yaml"))
        config = loader.load()
        assert config.agent.memory_enabled is True

    def test_default_brave_api_key_none(self) -> None:
        loader = ConfigLoader(config_path=Path("/nonexistent/config.yaml"))
        config = loader.load()
        assert config.agent.brave_api_key is None

    def test_default_web_fetch_max_chars(self) -> None:
        loader = ConfigLoader(config_path=Path("/nonexistent/config.yaml"))
        config = loader.load()
        assert config.agent.web_fetch_max_chars == 50000

    def test_default_consolidate_every(self) -> None:
        loader = ConfigLoader(config_path=Path("/nonexistent/config.yaml"))
        config = loader.load()
        assert config.agent.memory_consolidate_every == 10


class TestAgentConfigFromYaml:
    def test_enables_agent(self) -> None:
        data = {"agent": {"enabled": True}}
        with tempfile.NamedTemporaryFile(suffix=".yaml", mode="w", delete=False) as f:
            yaml.dump(data, f)
            path = Path(f.name)
        config = ConfigLoader(config_path=path).load()
        assert config.agent.enabled is True

    def test_custom_values(self) -> None:
        data = {
            "agent": {
                "enabled": True,
                "max_tool_rounds": 5,
                "exec_timeout": 30,
                "exec_deny_patterns": [r"\bsudo\b"],
                "memory_enabled": False,
                "brave_api_key": "BSA-test123",
                "web_fetch_max_chars": 10000,
            }
        }
        with tempfile.NamedTemporaryFile(suffix=".yaml", mode="w", delete=False) as f:
            yaml.dump(data, f)
            path = Path(f.name)
        config = ConfigLoader(config_path=path).load()
        assert config.agent.max_tool_rounds == 5
        assert config.agent.exec_timeout == 30
        assert config.agent.exec_deny_patterns == [r"\bsudo\b"]
        assert config.agent.memory_enabled is False
        assert config.agent.brave_api_key == "BSA-test123"
        assert config.agent.web_fetch_max_chars == 10000

    def test_partial_agent_merges_defaults(self) -> None:
        data = {"agent": {"enabled": True}}
        with tempfile.NamedTemporaryFile(suffix=".yaml", mode="w", delete=False) as f:
            yaml.dump(data, f)
            path = Path(f.name)
        config = ConfigLoader(config_path=path).load()
        assert config.agent.enabled is True
        assert config.agent.max_tool_rounds == 15  # default preserved

    def test_agent_config_does_not_affect_other_sections(self) -> None:
        data = {"agent": {"enabled": True}, "llm": {"model": "gpt-4o"}}
        with tempfile.NamedTemporaryFile(suffix=".yaml", mode="w", delete=False) as f:
            yaml.dump(data, f)
            path = Path(f.name)
        config = ConfigLoader(config_path=path).load()
        assert config.llm.model == "gpt-4o"
        assert config.nl_mode.default_active is True
