"""
T-22 — Risk engine: detectar padrões destrutivos
DADO o risk engine
QUANDO analiso um comando
ENTÃO recebo a classificação de risco correta
"""
import pytest
from src.infrastructure.intelligence.risk_engine import RiskEngine, RiskLevel


class TestRiskEngine:
    def setup_method(self) -> None:
        self.engine = RiskEngine()

    # --- HIGH risk ---
    @pytest.mark.parametrize("cmd", [
        "rm -rf /",
        "rm -rf /*",
        "rm -rf /home/user",
        "sudo rm -rf /tmp/teste",
        "dd if=/dev/zero of=/dev/sda",
        "dd if=/dev/urandom of=/dev/nvme0n1",
        "mkfs.ext4 /dev/sda1",
        "mkfs -t xfs /dev/sdb",
        "chmod -R 777 /",
        "chmod -R 000 /etc",
        "> /etc/passwd",
        "cat /dev/null > /etc/shadow",
        ":(){ :|:& };:",   # fork bomb
    ])
    def test_high_risk_commands(self, cmd: str) -> None:
        assert self.engine.classify(cmd) == RiskLevel.HIGH, f"Expected HIGH for: {cmd}"

    # --- MEDIUM risk ---
    @pytest.mark.parametrize("cmd", [
        "rm -rf /tmp/mydir",
        "sudo apt-get remove python3",
        "kill -9 1234",
        "pkill -f myprocess",
        "chmod 600 /etc/hosts",
        "mv /etc/nginx/nginx.conf /tmp/backup",
        "systemctl stop nginx",
        "service apache2 stop",
    ])
    def test_medium_risk_commands(self, cmd: str) -> None:
        level = self.engine.classify(cmd)
        assert level in (RiskLevel.MEDIUM, RiskLevel.HIGH), f"Expected MEDIUM+ for: {cmd}"

    # --- LOW risk ---
    @pytest.mark.parametrize("cmd", [
        "ls -la",
        "pwd",
        "echo hello",
        "cat /etc/hostname",
        "ps aux",
        "df -h",
        "top -bn1",
        "git status",
        "python3 --version",
    ])
    def test_low_risk_commands(self, cmd: str) -> None:
        assert self.engine.classify(cmd) == RiskLevel.LOW, f"Expected LOW for: {cmd}"

    def test_empty_command_is_low(self) -> None:
        assert self.engine.classify("") == RiskLevel.LOW

    def test_double_confirm_required_for_high(self) -> None:
        assert self.engine.requires_double_confirm("rm -rf /") is True

    def test_double_confirm_not_required_for_low(self) -> None:
        assert self.engine.requires_double_confirm("ls -la") is False
