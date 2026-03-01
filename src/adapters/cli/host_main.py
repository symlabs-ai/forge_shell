"""
forge_host — entrypoint standalone do host PTY (passthrough).

Binário ultra-leve (~5MB) que NÃO importa forge_llm, pyte, httpx etc.
Usado pelo cliente que recebe suporte: compartilha o terminal via relay
sem NL Mode, LLM ou qualquer dependência pesada.

Uso:
    forge_host                  PTY puro local (passthrough)
    forge_host share            Compartilha terminal via relay
    forge_host share --regen    Regenera machine code antes de compartilhar
"""
import argparse
import ssl as _ssl
import sys

from src.infrastructure.config.loader import ConfigLoader
from src.application.usecases.terminal_session import TerminalSession


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="forge_host",
        description="forge_host — terminal PTY com compartilhamento via relay",
    )

    subparsers = parser.add_subparsers(dest="command", metavar="<command>")

    share_parser = subparsers.add_parser(
        "share",
        help="Compartilhar terminal via relay (exibe código + senha)",
    )
    share_parser.add_argument(
        "--regen",
        action="store_true",
        help="Regenerar o código da máquina (novo código permanente)",
    )

    return parser


def _relay_url_with_tls(url: str, tls: bool) -> str:
    if tls and url.startswith("ws://"):
        return "wss://" + url[5:]
    return url


def _build_ssl_client_context(tls: bool):
    if not tls:
        return None
    return _ssl.create_default_context()


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    config = ConfigLoader().load()

    if args.command == "share":
        from src.infrastructure.collab import machine_id as _machine_id
        from src.infrastructure.collab.session_manager import SessionManager
        from src.infrastructure.collab.relay_bridge import RelayBridge
        from src.application.usecases.share_session import ShareSession

        if getattr(args, "regen", False):
            machine_code = _machine_id.regenerate()
            print("[forge_host] Código da máquina regenerado.")
        else:
            machine_code = _machine_id.load_or_create()

        sm = SessionManager()
        password = sm.generate_password(config.collab.permanent_password)
        uc = ShareSession(session_manager=sm)
        result = uc.run(host_id="local", machine_code=machine_code, password=password)

        relay_url = _relay_url_with_tls(config.relay.url, config.relay.tls)

        print(f"[forge_host] Sessão compartilhada iniciada")
        print(f"  Código da máquina : {result['machine_code']}")
        print(f"  Senha de sessão   : {result['password']}")
        print(f"  Relay URL         : {relay_url}")

        ssl_client_ctx = _build_ssl_client_context(config.relay.tls)
        bridge = RelayBridge(
            relay_url=relay_url,
            session_id=result["machine_code"],
            token=result["password"],
            ssl=ssl_client_ctx,
        )
        bridge.start()

        session = TerminalSession(config=config, passthrough=True, relay_bridge=bridge)
        rc = session.run()
        bridge.stop()
        return rc

    # Modo padrão: PTY puro local
    session = TerminalSession(config=config, passthrough=True)
    return session.run()


if __name__ == "__main__":
    sys.exit(main())
