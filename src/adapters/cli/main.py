"""
sym_shell — CLI entrypoint.

Uso:
    sym_shell               Inicia sessão local (NL Mode ativo por padrão)
    sym_shell share         Inicia sessão compartilhada via relay e exibe token
    sym_shell doctor        Diagnóstico do terminal engine
    sym_shell attach <id>   Reconecta a uma sessão existente pelo session-id
    sym_shell --passthrough Liga PTY puro sem NL Mode, collab ou auditoria.
                            Útil para diagnosticar se um bug é da engine PTY ou
                            das camadas superiores. Comportamento idêntico a um
                            terminal Bash puro — nenhuma funcionalidade do
                            sym_shell é ativada neste modo.
"""
import argparse
import asyncio
import sys

from src.application.usecases.terminal_session import TerminalSession
from src.application.usecases.doctor_runner import DoctorRunner, CheckStatus
from src.application.usecases.share_session import ShareSession
from src.application.usecases.nl_interceptor import NLInterceptor
from src.application.usecases.nl_mode_engine import NLModeEngine
from src.infrastructure.config.loader import ConfigLoader
from src.infrastructure.collab.session_manager import SessionManager
from src.infrastructure.collab.viewer_client import ViewerClient
from src.infrastructure.intelligence.forge_llm_adapter import ForgeLLMAdapter
from src.infrastructure.intelligence.risk_engine import RiskEngine
from src.infrastructure.audit.audit_logger import AuditLogger
from src.infrastructure.collab.relay_handler import RelayHandler
from src.infrastructure.collab.relay_bridge import RelayBridge


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sym_shell",
        description=(
            "sym_shell — terminal Bash nativo com NL Mode, colaboração remota e auditoria.\n"
            "NL Mode está ativo por padrão. Use ! para alternar para Bash direto."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--passthrough",
        action="store_true",
        help=(
            "Liga o PTY puro (Bash nativo) desativando completamente NL Mode, "
            "colaboração e auditoria. Use para diagnosticar se um bug é da engine "
            "PTY ou de camadas superiores do sym_shell. Comportamento idêntico ao "
            "Bash padrão — nenhuma feature do sym_shell é ativada."
        ),
    )

    subparsers = parser.add_subparsers(dest="command", metavar="<command>")

    # share
    share_parser = subparsers.add_parser(
        "share",
        help="Iniciar sessão compartilhada via relay e exibir token de acesso",
        description=(
            "Inicia o sym_shell em modo compartilhado. Conecta ao relay intermediário, "
            "registra a sessão e exibe o token/link para participantes remotos. "
            "Indicador 'Sessão compartilhada: ATIVA' é exibido no terminal enquanto ativo."
        ),
    )
    share_parser.add_argument(
        "--relay",
        metavar="URL",
        help="URL do relay intermediário (padrão: valor de config.yaml)",
    )
    share_parser.add_argument(
        "--expire",
        metavar="MINUTOS",
        type=int,
        default=60,
        help="Tempo de expiração do token em minutos (padrão: 60)",
    )

    # doctor
    subparsers.add_parser(
        "doctor",
        help="Diagnóstico do terminal engine (PTY, termios, sinais, resize)",
        description=(
            "Executa uma bateria de verificações no terminal engine: "
            "spawn de PTY, modo raw/cooked, repasse de sinais e resize. "
            "Útil para detectar incompatibilidades antes de reportar bugs."
        ),
    )

    # attach
    attach_parser = subparsers.add_parser(
        "attach",
        help="Reconectar a uma sessão sym_shell existente pelo session-id",
        description=(
            "Reconecta a uma sessão sym_shell em execução identificada pelo session-id. "
            "O estado da sessão é mantido no host; o relay recupera e transmite ao client. "
            "Use 'sym_shell share' para obter o session-id de uma sessão ativa."
        ),
    )
    attach_parser.add_argument(
        "session_id",
        metavar="SESSION_ID",
        help="ID da sessão a reconectar (fornecido pelo 'sym_shell share')",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "doctor":
        runner = DoctorRunner()
        report = runner.run()
        print(report.to_text())
        return 0 if report.overall.value != CheckStatus.FAIL.value else 1

    if args.command == "share":
        config = ConfigLoader().load()
        sm = SessionManager()
        uc = ShareSession(session_manager=sm)
        expire = getattr(args, "expire", 60) or 60
        result = uc.run(host_id="local", expire_minutes=expire)

        relay_url = getattr(args, "relay", None) or config.relay.url
        session_id = result["session_id"]
        token = result["token"]

        print(f"[sym_shell] Sessão compartilhada iniciada")
        print(f"  Session ID : {session_id}")
        print(f"  Token      : {token}")
        print(f"  Expira em  : {result['expires_at']}")
        print(f"  Relay URL  : {relay_url}")

        # Iniciar RelayHandler em thread background
        relay = RelayHandler(host="0.0.0.0", port=config.relay.port)
        import threading
        relay_thread = threading.Thread(
            target=lambda: asyncio.run(relay.start()), daemon=True
        )
        relay_thread.start()

        # RelayBridge conecta o TerminalSession ao relay
        bridge = RelayBridge(relay_url=relay_url, session_id=session_id, token=token)
        bridge.start()

        # Iniciar sessão normal com relay_bridge injetado
        session = TerminalSession(config=config, passthrough=False)
        adapter = ForgeLLMAdapter(
            provider=config.llm.provider,
            model=config.llm.model,
            api_key=config.llm.api_key,
            timeout_seconds=config.llm.timeout_seconds,
            max_retries=config.llm.max_retries,
        )
        engine = NLModeEngine(llm_adapter=adapter, risk_engine=RiskEngine())
        session._interceptor = NLInterceptor(nl_engine=engine)
        session._auditor = AuditLogger()
        session._relay_bridge = bridge

        session._write_startup_hint()
        rc = session.run()
        bridge.stop()
        relay.stop()
        return rc

    if args.command == "attach":
        config = ConfigLoader().load()
        print(f"[sym_shell] Conectando à sessão: {args.session_id}")
        print(f"[sym_shell] Use Ctrl+C para encerrar a visualização")
        viewer = ViewerClient(
            relay_url=config.relay.url,
            session_id=args.session_id,
            token="",  # token fornecido via flag em ciclo futuro
        )

        async def _viewer_loop() -> None:
            await viewer.connect(
                on_output=lambda data: sys.stdout.buffer.write(data) or sys.stdout.buffer.flush()
            )
            try:
                # aguarda até relay fechar a conexão
                await viewer.wait()
            except (KeyboardInterrupt, asyncio.CancelledError):
                pass
            finally:
                await viewer.close()

        try:
            asyncio.run(_viewer_loop())
        except KeyboardInterrupt:
            pass
        return 0

    # --passthrough ou modo padrão (NL Mode)
    config = ConfigLoader().load()
    session = TerminalSession(config=config, passthrough=args.passthrough)

    if not args.passthrough:
        # injetar NLInterceptor com ForgeLLMAdapter real
        adapter = ForgeLLMAdapter(
            provider=config.llm.provider,
            model=config.llm.model,
            api_key=config.llm.api_key,
            timeout_seconds=config.llm.timeout_seconds,
            max_retries=config.llm.max_retries,
        )
        engine = NLModeEngine(llm_adapter=adapter, risk_engine=RiskEngine())
        session._interceptor = NLInterceptor(nl_engine=engine)
        # injetar AuditLogger
        session._auditor = AuditLogger()

    session._write_startup_hint()
    return session.run()


if __name__ == "__main__":
    sys.exit(main())
