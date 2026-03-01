"""Tests for SondaTool — silent shell execution."""
import pytest
from pathlib import Path

from forge_llm.domain.entities import ToolCall

from src.infrastructure.agent.tools.shell import SondaTool, _DEFAULT_DENY_PATTERNS


class TestSondaDenyPatterns:
    def _call(self, tool: SondaTool, command: str) -> tuple[str, bool]:
        result = tool.execute(ToolCall(id="t1", name="sonda", arguments={"command": command}))
        return result.content, result.is_error

    def test_blocks_rm_rf(self) -> None:
        tool = SondaTool()
        content, is_err = self._call(tool, "rm -rf /")
        assert is_err
        assert "blocked" in content.lower()

    def test_blocks_rm_r(self) -> None:
        tool = SondaTool()
        content, is_err = self._call(tool, "rm -r /tmp/stuff")
        assert is_err
        assert "blocked" in content.lower()

    def test_blocks_dd(self) -> None:
        tool = SondaTool()
        content, is_err = self._call(tool, "dd if=/dev/zero of=/dev/sda")
        assert is_err
        assert "blocked" in content.lower()

    def test_blocks_shutdown(self) -> None:
        tool = SondaTool()
        content, is_err = self._call(tool, "shutdown -h now")
        assert is_err

    def test_blocks_reboot(self) -> None:
        tool = SondaTool()
        content, is_err = self._call(tool, "reboot")
        assert is_err

    def test_blocks_fork_bomb(self) -> None:
        tool = SondaTool()
        content, is_err = self._call(tool, ":(){ :|:& };:")
        assert is_err

    def test_allows_safe_commands(self) -> None:
        tool = SondaTool()
        content, is_err = self._call(tool, "echo hello")
        assert not is_err
        assert "hello" in content

    def test_extra_deny_patterns(self) -> None:
        tool = SondaTool(extra_deny_patterns=[r"\bcurl\b"])
        content, is_err = self._call(tool, "curl http://example.com")
        assert is_err
        assert "blocked" in content.lower()


class TestSondaExecution:
    def _call(self, tool: SondaTool, command: str, **kwargs) -> tuple[str, bool]:
        args = {"command": command, **kwargs}
        result = tool.execute(ToolCall(id="t1", name="sonda", arguments=args))
        return result.content, result.is_error

    def test_captures_stdout(self) -> None:
        tool = SondaTool()
        content, is_err = self._call(tool, "echo 'test output'")
        assert not is_err
        assert "test output" in content

    def test_captures_stderr(self) -> None:
        tool = SondaTool()
        content, is_err = self._call(tool, "echo 'err' >&2")
        assert "STDERR" in content
        assert "err" in content

    def test_reports_exit_code(self) -> None:
        tool = SondaTool()
        content, is_err = self._call(tool, "exit 42")
        assert "Exit code: 42" in content

    def test_timeout(self) -> None:
        tool = SondaTool(timeout=1)
        content, is_err = self._call(tool, "sleep 30")
        assert is_err
        assert "timed out" in content.lower()

    def test_working_dir(self, tmp_path: Path) -> None:
        tool = SondaTool()
        content, is_err = self._call(tool, "pwd", working_dir=str(tmp_path))
        assert not is_err
        assert str(tmp_path) in content

    def test_no_output(self) -> None:
        tool = SondaTool()
        content, is_err = self._call(tool, "true")
        assert not is_err
        assert content == "(no output)"

    def test_truncation(self) -> None:
        tool = SondaTool()
        # Generate output > 10000 chars
        content, is_err = self._call(tool, "python3 -c \"print('x' * 15000)\"")
        assert not is_err
        assert "truncated" in content.lower()


class TestSondaDefinition:
    def test_definition_name(self) -> None:
        tool = SondaTool()
        assert tool.definition.name == "sonda"

    def test_definition_has_command_param(self) -> None:
        tool = SondaTool()
        params = tool.definition.parameters
        assert "command" in params["properties"]
        assert "command" in params["required"]
