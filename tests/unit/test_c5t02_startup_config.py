"""
C5-T-02 — Config default e hint de startup
DADO ConfigLoader com arquivo ausente
QUANDO model padrão é ollama
ENTÃO model default é "llama3.2" (não "llama3" que pode não existir)
DADO TerminalSession com NL Mode ativo
QUANDO run() inicia (hint mode)
ENTÃO stdout recebe hint "NL Mode | ! para bash | !<cmd> bash direto"
"""
import pytest
from unittest.mock import MagicMock, patch
from src.infrastructure.config.loader import ConfigLoader


class TestDefaultConfig:
    def test_default_model_is_llama32(self) -> None:
        """Default model deve ser llama3.2 quando não há config file."""
        from pathlib import Path
        config = ConfigLoader(config_path=Path("/nonexistent/no_config.yaml")).load()
        assert config.llm.model == "llama3.2"

    def test_default_provider_is_ollama(self) -> None:
        from pathlib import Path
        config = ConfigLoader(config_path=Path("/nonexistent/no_config.yaml")).load()
        assert config.llm.provider == "ollama"

    def test_default_relay_url(self) -> None:
        from pathlib import Path
        config = ConfigLoader(config_path=Path("/nonexistent/no_config.yaml")).load()
        assert config.relay.url == "wss://relay.palhano.services"


class TestStartupHint:
    def test_terminal_session_has_startup_hint(self) -> None:
        """TerminalSession deve ter método _write_startup_hint."""
        from src.application.usecases.terminal_session import TerminalSession
        from src.infrastructure.config.loader import ForgeShellConfig
        session = TerminalSession(config=ForgeShellConfig())
        assert hasattr(session, "_write_startup_hint")

    def test_startup_hint_writes_nl_mode_info(self) -> None:
        """_write_startup_hint deve mencionar NL Mode e atalhos."""
        from src.application.usecases.terminal_session import TerminalSession
        from src.infrastructure.config.loader import ForgeShellConfig, NLModeConfig
        session = TerminalSession(config=ForgeShellConfig(nl_mode=NLModeConfig(default_active=True)))
        out = MagicMock()
        session._stdout = out
        session._write_startup_hint()
        written = b"".join(
            call.args[0] for call in out.write.call_args_list if call.args
        )
        assert b"NL" in written or b"forge_shell" in written
        assert b"!" in written

    def test_no_hint_in_passthrough_mode(self) -> None:
        """Modo --passthrough não deve exibir hint de NL Mode."""
        from src.application.usecases.terminal_session import TerminalSession
        from src.infrastructure.config.loader import ForgeShellConfig
        session = TerminalSession(config=ForgeShellConfig(), passthrough=True)
        out = MagicMock()
        session._stdout = out
        session._write_startup_hint()
        # sem hint no passthrough
        assert not out.write.called
