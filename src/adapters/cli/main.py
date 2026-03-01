"""
forge_shell — CLI entrypoint.

Uso:
    forge_shell               Inicia sessão local (NL Mode ativo por padrão)
    forge_shell share         Inicia sessão compartilhada via relay e exibe token
    forge_shell doctor        Diagnóstico do terminal engine
    forge_shell attach <id>   Reconecta a uma sessão existente pelo session-id
    forge_shell --passthrough Liga PTY puro sem NL Mode, collab ou auditoria.
                            Útil para diagnosticar se um bug é da engine PTY ou
                            das camadas superiores. Comportamento idêntico a um
                            terminal Bash puro — nenhuma funcionalidade do
                            forge_shell é ativada neste modo.
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
logging.getLogger("websockets").setLevel(logging.CRITICAL)
logging.getLogger("websockets.server").setLevel(logging.CRITICAL)
logging.getLogger("websockets.legacy").setLevel(logging.CRITICAL)
logging.getLogger().handlers = []  # remove root StreamHandler → sem ruído no PTY

from src.application.usecases.terminal_session import TerminalSession
from src.application.usecases.doctor_runner import DoctorRunner, CheckStatus
from src.application.usecases.share_session import ShareSession
from src.application.usecases.nl_interceptor import NLInterceptor
from src.application.usecases.nl_mode_engine import NLModeEngine
from src.infrastructure.config.loader import ConfigLoader
from src.infrastructure.collab.session_manager import SessionManager
from src.infrastructure.collab.viewer_client import ViewerClient
from src.infrastructure.agent.agent_service import AgentService
from src.infrastructure.intelligence.forge_llm_adapter import ForgeLLMAdapter
from src.infrastructure.intelligence.risk_engine import RiskEngine
from src.infrastructure.audit.audit_logger import AuditLogger
from src.infrastructure.collab.relay_handler import RelayHandler
from src.infrastructure.collab.relay_bridge import RelayBridge
from src.infrastructure.collab.agent_client import AgentClient
from src.infrastructure.intelligence.redaction import Redactor


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="forge_shell",
        description=(
            "forge_shell — terminal Bash nativo com NL Mode, colaboração remota e auditoria.\n"
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
            "PTY ou de camadas superiores do forge_shell. Comportamento idêntico ao "
            "Bash padrão — nenhuma feature do forge_shell é ativada."
        ),
    )

    subparsers = parser.add_subparsers(dest="command", metavar="<command>")

    # share
    share_parser = subparsers.add_parser(
        "share",
        help="Iniciar sessão compartilhada via relay e exibir código + senha",
        description=(
            "Inicia o forge_shell em modo compartilhado. Exibe o código da máquina "
            "(persistente) e a senha de sessão (efêmera) para o viewer conectar. "
            "Viewer usa: forge_shell attach <código> <senha>."
        ),
    )
    share_parser.add_argument(
        "--regen",
        action="store_true",
        help="Regenerar o código da máquina (novo código permanente)",
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
        help="Conectar como viewer a uma sessão forge_shell em andamento",
        description=(
            "Conecta ao terminal remoto de uma sessão forge_shell ativa. "
            "Use o código da máquina e a senha exibidos pelo 'forge_shell share' no host."
        ),
    )
    attach_parser.add_argument(
        "machine_code",
        metavar="MACHINE_CODE",
        help="Código da máquina host (ex: 497-051-961)",
    )
    attach_parser.add_argument(
        "password",
        metavar="SENHA",
        help="Senha de sessão (6 dígitos, exibida pelo 'forge_shell share')",
    )

    # agent
    agent_parser = subparsers.add_parser(
        "agent",
        help="Conectar como agent de IA a uma sessão forge_shell em andamento",
        description=(
            "Conecta ao terminal remoto como agent. Recebe output do PTY em stdout "
            "(raw bytes) e lê sugestões de stdin como JSON (uma por linha). "
            "Formato: {\"commands\":[\"cmd\"],\"explanation\":\"...\",\"risk_level\":\"LOW\"}"
        ),
    )
    agent_parser.add_argument(
        "machine_code",
        metavar="MACHINE_CODE",
        help="Código da máquina host (ex: 497-051-961)",
    )
    agent_parser.add_argument(
        "password",
        metavar="SENHA",
        help="Senha de sessão (6 dígitos, exibida pelo 'forge_shell share')",
    )

    # relay
    relay_parser = subparsers.add_parser(
        "relay",
        help="Iniciar servidor relay standalone (deploy em servidor público)",
        description=(
            "Inicia o RelayHandler como serviço standalone. "
            "Faça deploy em um servidor com IP público para que 'forge_shell share' "
            "e 'forge_shell attach' conectem sem precisar de NAT ou porta aberta no host. "
            "Configure relay.url no config.yaml para apontar para este servidor."
        ),
    )
    relay_parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Interface de bind (padrão: 0.0.0.0 — todas as interfaces)",
    )
    relay_parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Porta de escuta (padrão: relay.port do config, normalmente 8060)",
    )

    # config
    config_parser = subparsers.add_parser(
        "config",
        help="Exibir ou editar a configuração do forge_shell",
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


def _build_session(
    config,
    passthrough: bool = False,
    relay_bridge=None,
) -> TerminalSession:
    """Constrói TerminalSession com todas as dependências injetadas."""
    interceptor = None
    auditor = None
    redactor = None
    if not passthrough:
        adapter = ForgeLLMAdapter(
            provider=config.llm.provider,
            model=config.llm.model,
            api_key=config.llm.api_key,
            timeout_seconds=config.llm.timeout_seconds,
            max_retries=config.llm.max_retries,
        )
        agent_service = None
        if config.agent.enabled:
            agent_service = AgentService(
                provider=config.llm.provider,
                model=config.llm.model,
                api_key=config.llm.api_key,
                agent_config=config.agent,
            )
        engine = NLModeEngine(
            llm_adapter=adapter,
            risk_engine=RiskEngine(),
            agent_service=agent_service,
            default_active=config.nl_mode.default_active,
        )
        interceptor = NLInterceptor(nl_engine=engine)
        auditor = AuditLogger()
        redactor = Redactor.from_profile_name(config.redaction.default_profile)
    return TerminalSession(
        config=config,
        passthrough=passthrough,
        interceptor=interceptor,
        auditor=auditor,
        redactor=redactor,
        relay_bridge=relay_bridge,
    )


def _config_show() -> int:
    """Exibe a configuração atual como YAML."""
    config = ConfigLoader().load()
    cfg_path = ConfigLoader()._path
    print(f"# forge_shell config — {cfg_path}")
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
            print(f"[forge_shell] Criado {cfg_path} a partir do exemplo.")
        else:
            cfg_path.write_text("# forge_shell config\n", encoding="utf-8")
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

    if args.command == "relay":
        config = ConfigLoader().load()
        port = args.port if args.port is not None else config.relay.port
        bind_host = args.host
        ssl_ctx = _build_ssl_server_context(
            getattr(config.relay, "cert_file", None),
            getattr(config.relay, "key_file", None),
        )
        relay = RelayHandler(host=bind_host, port=port, ssl_context=ssl_ctx)
        print(f"[forge_shell relay] Escutando em ws://{bind_host}:{port}")
        print(f"[forge_shell relay] Ctrl+C para encerrar")
        try:
            asyncio.run(relay.start())
        except KeyboardInterrupt:
            pass
        return 0

    if args.command == "share":
        config = ConfigLoader().load()
        from src.infrastructure.collab import machine_id as _machine_id
        if getattr(args, "regen", False):
            machine_code = _machine_id.regenerate()
            print(f"[forge_shell] Código da máquina regerado.")
        else:
            machine_code = _machine_id.load_or_create()
        sm = SessionManager()
        password = sm.generate_password(config.collab.permanent_password)
        uc = ShareSession(session_manager=sm)
        result = uc.run(host_id="local", machine_code=machine_code, password=password)

        relay_url = _relay_url_with_tls(config.relay.url, config.relay.tls)

        print(f"[forge_shell] Sessão compartilhada iniciada")
        print(f"  Código da máquina : {result['machine_code']}")
        print(f"  Senha de sessão   : {result['password']}")
        print(f"  Relay URL         : {relay_url}")

        # RelayBridge conecta o TerminalSession ao relay externo
        # Use 'forge_shell relay' para subir o servidor relay separadamente
        ssl_client_ctx = _build_ssl_client_context(config.relay.tls)
        bridge = RelayBridge(
            relay_url=relay_url,
            session_id=result["machine_code"],
            token=result["password"],
            ssl=ssl_client_ctx,
        )
        bridge.start()

        # Iniciar sessão normal com relay_bridge injetado
        session = _build_session(config, relay_bridge=bridge)

        session._write_startup_hint()
        rc = session.run()
        bridge.stop()
        return rc

    if args.command == "attach":
        import termios
        import tty

        config = ConfigLoader().load()
        relay_url = _relay_url_with_tls(config.relay.url, config.relay.tls)
        print(f"[forge_shell] Conectando à máquina: {args.machine_code}")
        print(f"[forge_shell] Use Ctrl+] para desconectar")
        ssl_ctx = _build_ssl_client_context(config.relay.tls)
        viewer = ViewerClient(
            relay_url=relay_url,
            session_id=args.machine_code,
            token=args.password,
            ssl=ssl_ctx,
        )

        def _on_viewer_output(data: bytes) -> None:
            sys.stdout.buffer.write(data)
            sys.stdout.buffer.flush()

        is_tty = sys.stdin.isatty()

        async def _viewer_loop() -> None:
            await viewer.connect(on_output=_on_viewer_output)
            if is_tty:
                loop = asyncio.get_event_loop()
                try:
                    while True:
                        data = await loop.run_in_executor(None, lambda: os.read(sys.stdin.fileno(), 1024))
                        if not data:
                            break
                        # Ctrl+] (0x1d) — escape to disconnect (telnet convention)
                        if b"\x1d" in data:
                            break
                        await viewer.send_input(data)
                except (KeyboardInterrupt, asyncio.CancelledError, OSError):
                    pass
            else:
                # non-TTY (tests, piped stdin): fallback to wait-only mode
                try:
                    await viewer.wait()
                except (KeyboardInterrupt, asyncio.CancelledError):
                    pass
            await viewer.close()

        old_settings = None
        try:
            if is_tty:
                old_settings = termios.tcgetattr(sys.stdin)
                tty.setraw(sys.stdin)
            asyncio.run(_viewer_loop())
        except KeyboardInterrupt:
            pass
        finally:
            if old_settings is not None:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
        return 0

    if args.command == "agent":
        config = ConfigLoader().load()
        relay_url = _relay_url_with_tls(config.relay.url, config.relay.tls)
        ssl_ctx = _build_ssl_client_context(config.relay.tls)

        print(f"[forge_shell agent] Conectando à máquina: {args.machine_code}", file=sys.stderr)
        print(f"[forge_shell agent] stdin: JSON suggest (uma linha por sugestão)", file=sys.stderr)
        print(f"[forge_shell agent] stdout: PTY output (raw bytes)", file=sys.stderr)
        print(f"[forge_shell agent] Ctrl+C para encerrar", file=sys.stderr)

        agent = AgentClient(
            relay_url=relay_url,
            session_id=args.machine_code,
            token=args.password,
            ssl=ssl_ctx,
        )

        def _on_agent_output(data: bytes) -> None:
            sys.stdout.buffer.write(data)
            sys.stdout.buffer.flush()

        async def _agent_loop() -> None:
            await agent.connect(on_output=_on_agent_output)
            try:
                loop = asyncio.get_event_loop()
                while True:
                    line = await loop.run_in_executor(None, sys.stdin.readline)
                    if not line:
                        break
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        import json
                        payload = json.loads(line)
                    except (ValueError, TypeError):
                        print(f"[forge_shell agent] JSON inválido: {line}", file=sys.stderr)
                        continue
                    commands = payload.get("commands", [])
                    explanation = payload.get("explanation", "")
                    risk_level = payload.get("risk_level", "LOW")
                    await agent.send_suggest(commands, explanation, risk_level)
            except (KeyboardInterrupt, asyncio.CancelledError):
                pass
            finally:
                await agent.close()

        try:
            asyncio.run(_agent_loop())
        except KeyboardInterrupt:
            pass
        return 0

    # --passthrough ou modo padrão (NL Mode)
    config = ConfigLoader().load()
    session = _build_session(config, passthrough=args.passthrough)

    session._write_startup_hint()
    return session.run()


if __name__ == "__main__":
    sys.exit(main())
