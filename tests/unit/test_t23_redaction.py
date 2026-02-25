"""
T-23 — Redaction com perfis dev/prod
DADO o sistema de redaction
QUANDO processo texto com segredos antes de enviar ao LLM
ENTÃO os segredos são mascarados conforme o perfil ativo
"""
import pytest
from src.infrastructure.intelligence.redaction import Redactor, RedactionProfile


class TestRedactorProdProfile:
    def setup_method(self) -> None:
        self.redactor = Redactor(profile=RedactionProfile.PROD)

    def test_masks_api_key(self) -> None:
        text = "export API_KEY=sk-abc123xyz"
        result = self.redactor.redact(text)
        assert "sk-abc123xyz" not in result
        assert "[REDACTED]" in result

    def test_masks_password(self) -> None:
        text = "password=super_secret_123"
        result = self.redactor.redact(text)
        assert "super_secret_123" not in result

    def test_masks_token(self) -> None:
        text = "TOKEN=ghp_AbCdEfGhIjKlMnOpQrStUvWxYz1234567890"
        result = self.redactor.redact(text)
        assert "ghp_" not in result

    def test_masks_aws_key(self) -> None:
        text = "AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE"
        result = self.redactor.redact(text)
        assert "AKIAIOSFODNN7EXAMPLE" not in result

    def test_plain_text_unchanged(self) -> None:
        text = "ls -la /home/user"
        result = self.redactor.redact(text)
        assert result == text

    def test_masks_ip_in_prod(self) -> None:
        text = "connecting to 192.168.1.100"
        result = self.redactor.redact(text)
        assert "192.168.1.100" not in result


class TestRedactorDevProfile:
    def setup_method(self) -> None:
        self.redactor = Redactor(profile=RedactionProfile.DEV)

    def test_masks_api_key_in_dev(self) -> None:
        text = "api_key=sk-test-12345"
        result = self.redactor.redact(text)
        assert "sk-test-12345" not in result

    def test_dev_allows_ip(self) -> None:
        """Perfil dev não mascara IPs (apenas prod faz isso)."""
        text = "connecting to 192.168.1.100"
        result = self.redactor.redact(text)
        assert "192.168.1.100" in result

    def test_multiple_secrets_all_masked(self) -> None:
        text = "password=abc TOKEN=xyz api_key=qrs"
        result = self.redactor.redact(text)
        assert "abc" not in result
        assert "xyz" not in result
        assert "qrs" not in result


class TestRedactorFromConfig:
    def test_create_from_profile_name(self) -> None:
        r = Redactor.from_profile_name("prod")
        assert r.profile == RedactionProfile.PROD

    def test_invalid_profile_raises(self) -> None:
        with pytest.raises(ValueError):
            Redactor.from_profile_name("nonexistent")
