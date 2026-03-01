"""
forge_relay — entrypoint standalone do servidor relay WebSocket.

Binário ultra-leve (~5MB) que NÃO importa forge_llm, pyte, httpx etc.
Deploy em servidor com IP público para intermediar forge_host ↔ forge_shell attach.

Uso:
    forge_relay                 Inicia na porta do config (padrão 8060)
    forge_relay --port 9000     Porta customizada
    forge_relay --host 127.0.0.1  Bind apenas localhost
"""
import argparse
import asyncio
import ssl as _ssl
import sys

from src.infrastructure.config.loader import ConfigLoader
from src.infrastructure.collab.relay_handler import RelayHandler


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="forge_relay",
        description="forge_relay — servidor relay WebSocket standalone",
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Interface de bind (padrão: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Porta de escuta (padrão: relay.port do config, normalmente 8060)",
    )
    return parser


def _build_ssl_server_context(cert_file: str | None, key_file: str | None):
    if not cert_file or not key_file:
        return None
    ctx = _ssl.SSLContext(_ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(certfile=cert_file, keyfile=key_file)
    return ctx


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    config = ConfigLoader().load()
    port = args.port if args.port is not None else config.relay.port
    bind_host = args.host

    ssl_ctx = _build_ssl_server_context(
        getattr(config.relay, "cert_file", None),
        getattr(config.relay, "key_file", None),
    )

    relay = RelayHandler(host=bind_host, port=port, ssl_context=ssl_ctx)

    proto = "wss" if ssl_ctx else "ws"
    print(f"[forge_relay] Escutando em {proto}://{bind_host}:{port}")
    print(f"[forge_relay] Ctrl+C para encerrar")

    try:
        asyncio.run(relay.start())
    except KeyboardInterrupt:
        pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
