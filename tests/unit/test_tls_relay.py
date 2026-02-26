"""
Testes — TLS no relay (Feature 7)
DADO configuração com relay.tls: true
QUANDO RelayHandler inicia ou clientes conectam
ENTÃO SSL context é criado e usado
"""
import ssl
from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from src.infrastructure.config.loader import RelayConfig, ConfigLoader, SymShellConfig
from src.infrastructure.collab.relay_handler import RelayHandler
from src.infrastructure.collab.host_relay_client import HostRelayClient
from src.infrastructure.collab.viewer_client import ViewerClient
from src.adapters.cli.main import (
    _relay_url_with_tls,
    _build_ssl_client_context,
    _build_ssl_server_context,
)


class TestRelayConfig:
    def test_relay_config_has_cert_file_field(self) -> None:
        cfg = RelayConfig()
        assert hasattr(cfg, "cert_file")
        assert cfg.cert_file is None

    def test_relay_config_has_key_file_field(self) -> None:
        cfg = RelayConfig()
        assert hasattr(cfg, "key_file")
        assert cfg.key_file is None

    def test_relay_config_cert_file_set(self) -> None:
        cfg = RelayConfig(cert_file="/etc/sym_shell/server.crt")
        assert cfg.cert_file == "/etc/sym_shell/server.crt"

    def test_relay_config_key_file_set(self) -> None:
        cfg = RelayConfig(key_file="/etc/sym_shell/server.key")
        assert cfg.key_file == "/etc/sym_shell/server.key"

    def test_config_loader_parses_cert_file(self, tmp_path) -> None:
        cfg_yaml = tmp_path / "config.yaml"
        cfg_yaml.write_text(
            "relay:\n  tls: true\n  cert_file: /tmp/server.crt\n  key_file: /tmp/server.key\n"
        )
        loader = ConfigLoader(config_path=cfg_yaml)
        config = loader.load()
        assert config.relay.cert_file == "/tmp/server.crt"
        assert config.relay.key_file == "/tmp/server.key"
        assert config.relay.tls is True

    def test_config_loader_cert_defaults_to_none(self, tmp_path) -> None:
        cfg_yaml = tmp_path / "config.yaml"
        cfg_yaml.write_text("relay:\n  port: 8765\n")
        loader = ConfigLoader(config_path=cfg_yaml)
        config = loader.load()
        assert config.relay.cert_file is None
        assert config.relay.key_file is None


class TestSslContextBuilders:
    def test_build_ssl_client_context_returns_none_when_no_tls(self) -> None:
        ctx = _build_ssl_client_context(False)
        assert ctx is None

    def test_build_ssl_client_context_returns_context_when_tls(self) -> None:
        ctx = _build_ssl_client_context(True)
        assert ctx is not None
        assert isinstance(ctx, ssl.SSLContext)

    def test_build_ssl_server_context_returns_none_without_cert(self) -> None:
        ctx = _build_ssl_server_context(None, None)
        assert ctx is None

    def test_build_ssl_server_context_returns_none_with_only_cert(self) -> None:
        ctx = _build_ssl_server_context("/etc/cert.pem", None)
        assert ctx is None

    def test_build_ssl_server_context_with_valid_files(self, tmp_path) -> None:
        """Cria um contexto SSL com arquivos de cert e key válidos (self-signed)."""
        # Gerar certificado self-signed para o teste
        try:
            from cryptography import x509
            from cryptography.x509.oid import NameOID
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import rsa
            import datetime

            key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            subject = issuer = x509.Name([
                x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
            ])
            cert = (
                x509.CertificateBuilder()
                .subject_name(subject)
                .issuer_name(issuer)
                .public_key(key.public_key())
                .serial_number(x509.random_serial_number())
                .not_valid_before(datetime.datetime.utcnow())
                .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=1))
                .sign(key, hashes.SHA256())
            )
            cert_file = tmp_path / "server.crt"
            key_file = tmp_path / "server.key"
            cert_file.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
            key_file.write_bytes(
                key.private_bytes(
                    serialization.Encoding.PEM,
                    serialization.PrivateFormat.TraditionalOpenSSL,
                    serialization.NoEncryption(),
                )
            )
            ctx = _build_ssl_server_context(str(cert_file), str(key_file))
            assert ctx is not None
            assert isinstance(ctx, ssl.SSLContext)
        except ImportError:
            pytest.skip("cryptography não instalado — teste de cert real ignorado")


class TestRelayUrlUpgrade:
    def test_ws_to_wss_upgrade(self) -> None:
        assert _relay_url_with_tls("ws://example.com:8765", True) == "wss://example.com:8765"

    def test_wss_stays_wss(self) -> None:
        assert _relay_url_with_tls("wss://example.com:8765", True) == "wss://example.com:8765"

    def test_no_upgrade_when_tls_false(self) -> None:
        assert _relay_url_with_tls("ws://example.com:8765", False) == "ws://example.com:8765"


class TestClientSslParam:
    def test_host_relay_client_stores_ssl(self) -> None:
        client = HostRelayClient("ws://localhost:8765", "s-test", "tok", ssl=True)
        assert client._ssl is True

    def test_host_relay_client_ssl_none_default(self) -> None:
        client = HostRelayClient("ws://localhost:8765", "s-test", "tok")
        assert client._ssl is None

    def test_viewer_client_stores_ssl(self) -> None:
        vc = ViewerClient("wss://localhost:8765", "s-test", "tok", ssl=True)
        assert vc._ssl is True

    def test_viewer_client_ssl_none_default(self) -> None:
        vc = ViewerClient("ws://localhost:8765", "s-test", "tok")
        assert vc._ssl is None


class TestRelayHandlerSsl:
    def test_relay_handler_stores_ssl_context(self) -> None:
        mock_ctx = MagicMock()
        handler = RelayHandler(ssl_context=mock_ctx)
        assert handler._ssl_context is mock_ctx

    def test_relay_handler_ssl_none_by_default(self) -> None:
        handler = RelayHandler()
        assert handler._ssl_context is None
