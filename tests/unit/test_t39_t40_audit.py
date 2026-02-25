"""
T-39/T-40 — Audit logger
DADO o sistema de auditoria
QUANDO registro eventos de sessão
ENTÃO o log contém todos os campos obrigatórios e é exportável
"""
import pytest
import json
import tempfile
from pathlib import Path
from src.infrastructure.audit.audit_logger import AuditLogger, AuditRecord


class TestAuditRecord:
    def test_creation(self) -> None:
        rec = AuditRecord(
            action="command_executed",
            origin="user",
            details={"command": "ls -la", "exit_code": 0},
        )
        assert rec.action == "command_executed"
        assert rec.origin == "user"
        assert rec.details["command"] == "ls -la"
        assert rec.timestamp is not None

    def test_to_dict_has_all_fields(self) -> None:
        rec = AuditRecord(action="x", origin="llm", details={"cmd": "rm"})
        d = rec.to_dict()
        assert "action" in d
        assert "origin" in d
        assert "details" in d
        assert "timestamp" in d

    def test_invalid_origin_raises(self) -> None:
        with pytest.raises(ValueError):
            AuditRecord(action="x", origin="unknown", details={})


class TestAuditLogger:
    def setup_method(self) -> None:
        self.tmp = tempfile.mkdtemp()
        self.logger = AuditLogger(log_dir=Path(self.tmp))

    def test_log_command_executed(self) -> None:
        self.logger.log_command(command="ls -la", origin="user", exit_code=0)
        records = self.logger.get_records()
        assert len(records) == 1
        assert records[0].action == "command_executed"
        assert records[0].origin == "user"

    def test_log_approval(self) -> None:
        self.logger.log_approval(command="rm -rf /tmp/test", approved_by="user", risk_level="high")
        records = self.logger.get_records()
        assert any(r.action == "command_approved" for r in records)

    def test_log_session_join(self) -> None:
        self.logger.log_session_join(session_id="s-123", participant="peer-1")
        records = self.logger.get_records()
        assert any(r.action == "session_join" for r in records)

    def test_log_session_leave(self) -> None:
        self.logger.log_session_leave(session_id="s-123", participant="peer-1")
        records = self.logger.get_records()
        assert any(r.action == "session_leave" for r in records)

    def test_export_json(self) -> None:
        self.logger.log_command(command="pwd", origin="user", exit_code=0)
        out_path = Path(self.tmp) / "audit.json"
        self.logger.export_json(out_path)
        data = json.loads(out_path.read_text())
        assert isinstance(data, list)
        assert len(data) >= 1
        assert "action" in data[0]

    def test_export_text(self) -> None:
        self.logger.log_command(command="pwd", origin="user", exit_code=0)
        out_path = Path(self.tmp) / "audit.txt"
        self.logger.export_text(out_path)
        content = out_path.read_text()
        assert "command_executed" in content
        assert "pwd" in content

    def test_multiple_records_ordered(self) -> None:
        self.logger.log_command(command="cmd1", origin="user", exit_code=0)
        self.logger.log_command(command="cmd2", origin="llm", exit_code=0)
        records = self.logger.get_records()
        assert len(records) == 2
        assert records[0].details["command"] == "cmd1"
        assert records[1].details["command"] == "cmd2"
