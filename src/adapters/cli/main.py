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
import logging
import os
import subprocess
import sys

# Silencia logs de bibliotecas que usam stdout (forge_llm usa structlog → root handler)
logging.getLogger("forge_llm").setLevel(logging.CRITICAL)
logging.getLogger("httpx").setLevel(logging.CRITICAL)
logging.getLogger("httpcore").setLevel(logging.CRITICAL)
logging.getLogger().handlers = []  # remove root StreamHandler → sem ruído no PTY

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
from src.infrastructure.intelligence.redaction import Redactor


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
    attach_parser.add_argument(
        "--token",
        metavar="TOKEN",
        default="",
        help="Token de autenticação da sessão (fornecido pelo 'sym_shell share')",
    )

    # config
    config_parser = subparsers.add_parser(
        "config",
        help="Exibir ou editar a configuração do sym_shell",
        description=(
            "Sem subcomando: exibe a configuração atual (merged defaults + arquivo). "
            "Use 'config edit' para abrir o arquivo de configuração no $EDITOR."
        ),
    )
    config_subparsers = config_parser.add_subparsers(dest="config_action", metavar="<action>")
    config_subparsers.add_parser("show", help="Exibir configuração atual (padrão)")
    config_subparsers.add_parser("edit", help="Abrir config.yaml no $EDITOR")

    return parser


def _relay_url_with_tls(url: str, tls: bool) -> str:
    """Auto-upgrade ws:// → wss:// quando TLS está ativo."""
    if tls and url.startswith("ws://"):
        return "wss://" + url[5:]
    return url


def _build_ssl_client_context(tls: bool):
    """Retorna ssl=True (validação padrão) quando TLS ativo, None caso contrário."""
    if not tls:
        return None
    import ssl
    return ssl.create_default_context()


def _build_ssl_server_context(cert_file: str | None, key_file: str | None):
    """Cria SSLContext para o servidor relay. Requer cert_file e key_file."""
    if not cert_file or not key_file:
        return None
    import ssl
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(certfile=cert_file, keyfile=key_file)
    return ctx


def _config_show() -> int:
    """Exibe a configuração atual como YAML."""
    config = ConfigLoader().load()
    cfg_path = ConfigLoader()._path
    print(f"# sym_shell config — {cfg_path}")
    print(f"# (defaults mesclados com arquivo existente)\n")
    print(f"nl_mode:")
    print(f"  default_active: {str(config.nl_mode.default_active).lower()}")
    print(f"  context_lines: {config.nl_mode.context_lines}")
    print(f"  var_whitelist: {config.nl_mode.var_whitelist}")
    print(f"\nllm:")
    print(f"  provider: {config.llm.provider}")
    print(f"  model: {config.llm.model}")
    print(f"  api_key: {'***' if config.llm.api_key else 'null'}")
    print(f"  timeout_seconds: {config.llm.timeout_seconds}")
    print(f"  max_retries: {config.llm.max_retries}")
    print(f"\nrelay:")
    print(f"  url: {config.relay.url}")
    print(f"  port: {config.relay.port}")
    print(f"  tls: {str(config.relay.tls).lower()}")
    if config.relay.cert_file:
        print(f"  cert_file: {config.relay.cert_file}")
    if config.relay.key_file:
        print(f"  key_file: {config.relay.key_file}")
    print(f"\nredaction:")
    print(f"  default_profile: {config.redaction.default_profile}")
    return 0


def _config_edit() -> int:
    """Abre o config.yaml no $EDITOR."""
    loader = ConfigLoader()
    loader.ensure_config_dir()
    cfg_path = loader._path
    # Se não existe config.yaml, cria a partir do example
    if not cfg_path.exists():
        example = cfg_path.parent / "config.yaml.example"
        if example.exists():
            cfg_path.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
            print(f"[sym_shell] Criado {cfg_path} a partir do exemplo.")
        else:
            cfg_path.write_text("# sym_shell config\n", encoding="utf-8")
    editor = os.environ.get("EDITOR") or os.environ.get("VISUAL") or "nano"
    result = subprocess.run([editor, str(cfg_path)])
    return result.returncode


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "config":
        action = getattr(args, "config_action", None) or "show"
        if action == "edit":
            return _config_edit()
        return _config_show()

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
        ssl_server_ctx = _build_ssl_server_context(
            getattr(config.relay, "cert_file", None),
            getattr(config.relay, "key_file", None),
        )
        relay = RelayHandler(host="0.0.0.0", port=config.relay.port, ssl_context=ssl_server_ctx)
        import threading
        relay_thread = threading.Thread(
            target=lambda: asyncio.run(relay.start()), daemon=True
        )
        relay_thread.start()

        # RelayBridge conecta o TerminalSession ao relay
        relay_url_tls = _relay_url_with_tls(relay_url, config.relay.tls)
        ssl_client_ctx = _build_ssl_client_context(config.relay.tls)
        bridge = RelayBridge(
            relay_url=relay_url_tls,
            session_id=session_id,
            token=token,
            ssl=ssl_client_ctx,
        )
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
        session._redactor = Redactor.from_profile_name(config.redaction.default_profile)

        session._write_startup_hint()
        rc = session.run()
        bridge.stop()
        relay.stop()
        return rc

    if args.command == "attach":
        config = ConfigLoader().load()
        token = getattr(args, "token", "") or ""
        relay_url = _relay_url_with_tls(config.relay.url, config.relay.tls)
        print(f"[sym_shell] Conectando à sessão: {args.session_id}")
        print(f"[sym_shell] Use Ctrl+C para encerrar a visualização")
        ssl_ctx = _build_ssl_client_context(config.relay.tls)
        viewer = ViewerClient(
            relay_url=relay_url,
            session_id=args.session_id,
            token=token,
            ssl=ssl_ctx,
        )

        def _on_viewer_output(data: bytes) -> None:
            sys.stdout.buffer.write(data)
            sys.stdout.buffer.flush()

        async def _viewer_loop() -> None:
            await viewer.connect(on_output=_on_viewer_output)
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
        # injetar AuditLogger e Redactor
        session._auditor = AuditLogger()
        session._redactor = Redactor.from_profile_name(config.redaction.default_profile)

    session._write_startup_hint()
    return session.run()


if __name__ == "__main__":
    sys.exit(main())
