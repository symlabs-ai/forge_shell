"""
forge_shell — CLI entrypoint.

Uso:
    forge_shell               Inicia sessão local (NL Mode ativo por padrão)
    forge_shell -p "query"    Modo one-shot: traduz NL→bash, executa e sai
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
logging.getLogger("src").setLevel(logging.CRITICAL)  # AgentService, adapters internos
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
from src.infrastructure.terminal_engine.vt_screen import VTScreen
from src.infrastructure.terminal_engine.chat_panel import ChatPanel
from src.infrastructure.terminal_engine.split_renderer import SplitRenderer
from src.infrastructure.terminal_engine.input_router import InputRouter


import re
import time

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]|\x1b\].*?\x07|\x1b\[.*?[@-~]")

def _strip_ansi(text: str) -> str:
    """Remove escape sequences ANSI do texto."""
    return _ANSI_RE.sub("", text)


# ANSI colors for status messages
_YELLOW = "\033[33m"
_GREEN = "\033[32m"
_RED = "\033[31m"
_RESET = "\033[0m"
_BOLD = "\033[1m"


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
    parser.add_argument(
        "-p", "--prompt",
        type=str,
        help="Executa query NL one-shot (traduz → executa → sai)",
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
    agent_parser.add_argument(
        "--text",
        action="store_true",
        help="Modo texto simples: stdin = comandos, stdout = output sem ANSI",
    )

    # exec
    exec_parser = subparsers.add_parser(
        "exec",
        help="Executar comando remoto one-shot e imprimir output",
        description=(
            "Conecta como viewer, envia o comando, captura output e desconecta. "
            "Útil para automação e scripts."
        ),
    )
    exec_parser.add_argument(
        "machine_code",
        metavar="MACHINE_CODE",
        help="Código da máquina host (ex: 497-051-961)",
    )
    exec_parser.add_argument(
        "password",
        metavar="SENHA",
        help="Senha de sessão (6 dígitos)",
    )
    exec_parser.add_argument(
        "command_str",
        metavar="COMMAND",
        help="Comando a executar no host remoto",
    )
    exec_parser.add_argument(
        "--timeout",
        type=int,
        default=10,
        help="Segundos para aguardar output completo (padrão: 10)",
    )
    exec_parser.add_argument(
        "--strip-ansi",
        action="store_true",
        help="Remove escape sequences ANSI do output",
    )

    # message
    message_parser = subparsers.add_parser(
        "message",
        help="Enviar chat message para sessão remota",
        description=(
            "Envia uma mensagem de chat para a sessão e opcionalmente "
            "aguarda resposta do host."
        ),
    )
    message_parser.add_argument(
        "machine_code",
        metavar="MACHINE_CODE",
        help="Código da máquina host (ex: 497-051-961)",
    )
    message_parser.add_argument(
        "password",
        metavar="SENHA",
        help="Senha de sessão (6 dígitos)",
    )
    message_parser.add_argument(
        "text",
        metavar="TEXT",
        help="Texto da mensagem a enviar",
    )
    message_parser.add_argument(
        "--wait",
        type=int,
        default=0,
        help="Segundos para aguardar resposta (0 = fire-and-forget, padrão: 0)",
    )

    # ping
    ping_parser = subparsers.add_parser(
        "ping",
        help="Verificar se o host está online no relay",
        description=(
            "Faz HTTP GET ao relay para checar se o host está online. "
            "Não requer senha."
        ),
    )
    ping_parser.add_argument(
        "machine_code",
        metavar="MACHINE_CODE",
        help="Código da máquina host (ex: 497-051-961)",
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


class _ViewerSession:
    """Manages viewer attach state with optional chat split (F4)."""

    def __init__(self, viewer, stdout):
        self._viewer = viewer
        self._stdout = stdout
        self._chat_active = False
        self._vt: VTScreen | None = None
        self._chat: ChatPanel | None = None
        self._renderer: SplitRenderer | None = None
        self._router: InputRouter = InputRouter()
        self._buffering = False
        self._buffer: list[bytes] = []

    def _ensure_vt(self) -> None:
        """Lazily create VTScreen at full terminal width to capture output."""
        if self._vt is None:
            rows, cols = self._get_terminal_size()
            self._vt = VTScreen(rows, cols)

    # -- callbacks for ViewerClient --

    def on_output(self, data: bytes) -> None:
        # Always feed VTScreen to keep it in sync with host PTY
        self._ensure_vt()
        self._vt.feed(data)
        if self._buffering:
            self._buffer.append(data)
            return
        if not self._chat_active:
            self._stdout.write(data)
            self._stdout.flush()
        # Don't render here — let the stdin loop batch renders to avoid
        # cursor flicker from readline's CR+redraw sequences.

    def flush_buffer(self) -> None:
        """Flush buffered output to stdout."""
        self._buffering = False
        for chunk in self._buffer:
            if not self._chat_active:
                self._stdout.write(chunk)
        if self._buffer:
            self._stdout.flush()
        self._buffer.clear()

    def on_chat(self, payload: dict) -> None:
        if not self._chat_active:
            self._activate_chat()
        sender = payload.get("sender", "?")
        text = payload.get("text", "")
        role = payload.get("sender", "viewer")
        if self._chat:
            self._chat.add_message(sender, text, role)
        if self._renderer:
            self._renderer.render()

    # -- chat split management --

    def _get_terminal_size(self) -> tuple[int, int]:
        try:
            size = os.get_terminal_size()
            return (size.lines, size.columns)
        except OSError:
            return (24, 80)

    def _activate_chat(self) -> None:
        rows, cols = self._get_terminal_size()
        chat_width = 30
        # Reuse existing VTScreen (already has host terminal state)
        self._ensure_vt()
        self._chat = ChatPanel(rows, chat_width)
        self._renderer = SplitRenderer(self._stdout, rows, cols, chat_width=chat_width)
        self._renderer.attach(self._vt, self._chat)
        self._renderer.set_focus("terminal")
        self._chat_active = True
        self._renderer.render(force=True)

    def _deactivate_chat(self) -> None:
        if self._renderer:
            self._renderer.detach()
        # Keep self._vt alive to stay in sync with host PTY
        self._chat = None
        self._renderer = None
        self._chat_active = False

    def handle_resize(self) -> None:
        if not self._chat_active:
            return
        rows, cols = self._get_terminal_size()
        chat_width = 30
        if self._vt:
            self._vt.resize(rows, cols)  # full width to match host PTY
        if self._chat:
            self._chat.resize(rows, chat_width)
        if self._renderer:
            self._renderer.resize(rows, cols)
            self._renderer.render(force=True)

    # -- input routing --

    async def handle_input(self, data: bytes) -> None:
        for target, chunk in self._router.feed(data):
            if target == "toggle":
                if not self._chat_active:
                    self._activate_chat()
                else:
                    self._router.toggle_focus()
                    if self._renderer:
                        self._renderer.set_focus(self._router.focus.value)
                        self._renderer.render(force=True)
            elif target == "terminal":
                await self._viewer.send_input(chunk)
            elif target == "chat":
                if self._chat:
                    # handle_key expects individual keystrokes, feed byte by byte
                    for i in range(len(chunk)):
                        key = chunk[i:i + 1]
                        msg = self._chat.handle_key(key)
                        if msg is not None:
                            await self._viewer.send_chat(msg, sender="viewer")
                            self._chat.add_message("eu", msg, "viewer")
                if self._renderer:
                    self._renderer.render()

    def flush_esc_buffer(self) -> list[tuple[str, bytes]]:
        return self._router.flush_esc_buffer()

    def render_if_dirty(self) -> None:
        """Render if VTScreen or ChatPanel has pending changes. Called from stdin loop."""
        if self._chat_active and self._renderer:
            self._renderer.render()


def _run_prompt(config, prompt: str) -> int:
    """Modo -p: traduz NL → bash, executa e sai."""
    from src.application.usecases.prompt_runner import PromptRunner

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
    risk_engine = RiskEngine()
    engine = NLModeEngine(
        llm_adapter=adapter,
        risk_engine=risk_engine,
        agent_service=agent_service,
        default_active=True,
    )
    runner = PromptRunner(engine, risk_engine=risk_engine)
    return runner.run(prompt)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.prompt:
        config = ConfigLoader().load()
        return _run_prompt(config, args.prompt)

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
        import select as _select
        import signal
        import termios
        import tty

        config = ConfigLoader().load()
        relay_url = _relay_url_with_tls(config.relay.url, config.relay.tls)
        ssl_ctx = _build_ssl_client_context(config.relay.tls)
        viewer = ViewerClient(
            relay_url=relay_url,
            session_id=args.machine_code,
            token=args.password,
            ssl=ssl_ctx,
        )

        is_tty = sys.stdin.isatty()
        session = _ViewerSession(viewer, sys.stdout.buffer)

        def _status(msg: str, color: str = _YELLOW) -> None:
            """Print status message to stderr (avoids raw mode issues)."""
            sys.stderr.write(f"{color}[forge_shell]{_RESET} {msg}\r\n")
            sys.stderr.flush()

        def _read_stdin_with_timeout(fd: int, timeout: float = 0.05):
            """Read stdin using select+read. Returns bytes or None on timeout."""
            ready, _, _ = _select.select([fd], [], [], timeout)
            if ready:
                return os.read(fd, 1024)
            return None

        async def _viewer_loop() -> None:
            _status(f"Conectando à máquina {_BOLD}{args.machine_code}{_RESET}...")

            # Buffer output during handshake so status messages aren't interleaved
            session._buffering = True

            try:
                await viewer.connect(
                    on_output=session.on_output,
                    on_chat=session.on_chat,
                )
            except Exception as exc:
                session._buffering = False
                _status(f"Falha ao conectar ao relay: {exc}", _RED)
                return

            _status("Conectado ao relay. Aguardando resposta do host...")

            # Send Enter to trigger host prompt (host only sends output on PTY activity)
            await viewer.send_input(b"\r")

            # Wait for host to respond (first terminal_output)
            host_alive = await viewer.wait_for_host(timeout=10.0)
            if not host_alive:
                session._buffering = False
                _status(
                    "Host não respondeu em 10s. Verifique se a máquina está "
                    "online e o código/senha estão corretos.",
                    _RED,
                )
                await viewer.close()
                return

            _status(f"Conectado! Use {_BOLD}Ctrl+]{_RESET} para sair | {_BOLD}F4{_RESET} para chat", _GREEN)

            # Flush buffered output and show host terminal
            session.flush_buffer()

            # SIGWINCH handler for terminal resize
            if is_tty:
                loop = asyncio.get_event_loop()
                loop.add_signal_handler(signal.SIGWINCH, session.handle_resize)

            if is_tty:
                loop = asyncio.get_event_loop()
                fd = sys.stdin.fileno()
                try:
                    while True:
                        data = await loop.run_in_executor(
                            None, lambda: _read_stdin_with_timeout(fd),
                        )
                        if data is None:
                            # Timeout — flush escape buffer (lone ESC)
                            for target, chunk in session.flush_esc_buffer():
                                if target == "terminal":
                                    await viewer.send_input(chunk)
                                elif target == "chat" and session._chat:
                                    session._chat.handle_key(chunk)
                            # Batch render: all output since last cycle
                            session.render_if_dirty()
                            # Detect host disconnect (receive task exited)
                            if viewer._task and viewer._task.done():
                                break
                            continue
                        if not data:
                            break
                        # Ctrl+] (0x1d) — escape to disconnect
                        if b"\x1d" in data:
                            break
                        await session.handle_input(data)
                        # Batch render after processing input
                        session.render_if_dirty()
                except (KeyboardInterrupt, asyncio.CancelledError, OSError):
                    pass
            else:
                try:
                    await viewer.wait()
                except (KeyboardInterrupt, asyncio.CancelledError):
                    pass
            await viewer.close()

        old_settings = None
        exit_reason = "disconnect"
        try:
            if is_tty:
                old_settings = termios.tcgetattr(sys.stdin)
                tty.setraw(sys.stdin)
            asyncio.run(_viewer_loop())
        except KeyboardInterrupt:
            exit_reason = "interrupt"
        finally:
            if old_settings is not None:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
            if viewer._task and viewer._task.done():
                _status("Host desconectou.", _YELLOW)
            else:
                _status("Desconectado.", _YELLOW)
        return 0

    if args.command == "agent":
        config = ConfigLoader().load()
        relay_url = _relay_url_with_tls(config.relay.url, config.relay.tls)
        ssl_ctx = _build_ssl_client_context(config.relay.tls)

        agent = AgentClient(
            relay_url=relay_url,
            session_id=args.machine_code,
            token=args.password,
            ssl=ssl_ctx,
        )

        if getattr(args, "text", False):
            # P4: Modo texto simplificado
            print(f"[forge_shell agent] Modo texto — máquina: {args.machine_code}", file=sys.stderr)
            print(f"[forge_shell agent] stdin: comandos texto (um por linha)", file=sys.stderr)
            print(f"[forge_shell agent] stdout: output sem ANSI", file=sys.stderr)
            print(f"[forge_shell agent] Ctrl+C para encerrar", file=sys.stderr)

            def _on_text_output(data: bytes) -> None:
                clean = _strip_ansi(data.decode(errors="replace"))
                if clean:
                    sys.stdout.write(clean)
                    sys.stdout.flush()

            async def _agent_text_loop() -> None:
                await agent.connect(on_output=_on_text_output)
                try:
                    loop = asyncio.get_event_loop()
                    while True:
                        line = await loop.run_in_executor(None, sys.stdin.readline)
                        if not line:
                            break
                        await agent.send_input(line.encode())
                except (KeyboardInterrupt, asyncio.CancelledError):
                    pass
                finally:
                    await agent.close()

            try:
                asyncio.run(_agent_text_loop())
            except KeyboardInterrupt:
                pass
            return 0

        # Modo JSON padrão
        print(f"[forge_shell agent] Conectando à máquina: {args.machine_code}", file=sys.stderr)
        print(f"[forge_shell agent] stdin: JSON (uma linha por comando)", file=sys.stderr)
        print(f'[forge_shell agent]   input:   {{"type":"input","data":"base64..."}}', file=sys.stderr)
        print(f'[forge_shell agent]   suggest: {{"commands":[...],"explanation":"...","risk_level":"LOW"}}', file=sys.stderr)
        print(f"[forge_shell agent] stdout: PTY output (raw bytes)", file=sys.stderr)
        print(f"[forge_shell agent] Ctrl+C para encerrar", file=sys.stderr)

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
                        import base64 as _b64
                        payload = json.loads(line)
                    except (ValueError, TypeError):
                        print(f"[forge_shell agent] JSON inválido: {line}", file=sys.stderr)
                        continue
                    msg_type = payload.get("type", "suggest")
                    if msg_type == "input":
                        data = _b64.b64decode(payload.get("data", ""))
                        if data:
                            await agent.send_input(data)
                    else:
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

    if args.command == "exec":
        config = ConfigLoader().load()
        relay_url = _relay_url_with_tls(config.relay.url, config.relay.tls)
        ssl_ctx = _build_ssl_client_context(config.relay.tls)
        command = args.command_str  # usar field renomeado para evitar conflito
        timeout = args.timeout
        strip = getattr(args, "strip_ansi", False)

        viewer = ViewerClient(
            relay_url=relay_url,
            session_id=args.machine_code,
            token=args.password,
            ssl=ssl_ctx,
        )
        output_buf = bytearray()

        def _on_exec_output(data: bytes) -> None:
            output_buf.extend(data)

        async def _exec_loop() -> None:
            await viewer.connect(on_output=_on_exec_output)
            host_alive = await viewer.wait_for_host(timeout=5.0)
            if not host_alive:
                sys.stderr.write(f"{_RED}[forge_shell exec] Host não respondeu.{_RESET}\n")
                await viewer.close()
                return

            # Enviar comando + Enter
            await viewer.send_input(f"{command}\n".encode())

            # Aguardar output estabilizar (sem novos dados por 1s)
            last_len = 0
            deadline = time.time() + timeout
            while time.time() < deadline:
                await asyncio.sleep(0.3)
                if len(output_buf) > last_len:
                    last_len = len(output_buf)
                else:
                    break

            await viewer.close()

            result = output_buf.decode(errors="replace")
            if strip:
                result = _strip_ansi(result)
            sys.stdout.write(result)

        try:
            asyncio.run(_exec_loop())
        except KeyboardInterrupt:
            pass
        return 0

    if args.command == "message":
        config = ConfigLoader().load()
        relay_url = _relay_url_with_tls(config.relay.url, config.relay.tls)
        ssl_ctx = _build_ssl_client_context(config.relay.tls)
        text = args.text
        wait_seconds = args.wait

        viewer = ViewerClient(
            relay_url=relay_url,
            session_id=args.machine_code,
            token=args.password,
            ssl=ssl_ctx,
        )

        async def _message_loop() -> None:
            reply = None
            reply_event = asyncio.Event()

            def _on_msg_chat(payload: dict) -> None:
                nonlocal reply
                reply = payload
                reply_event.set()

            await viewer.connect(on_chat=_on_msg_chat)
            await viewer.send_chat(text, sender="cli")

            if wait_seconds > 0:
                try:
                    await asyncio.wait_for(reply_event.wait(), timeout=wait_seconds)
                except asyncio.TimeoutError:
                    pass

            await viewer.close()

            if reply:
                sender = reply.get("sender", "?")
                sys.stdout.write(f"[{sender}] {reply['text']}\n")

        try:
            asyncio.run(_message_loop())
        except KeyboardInterrupt:
            pass
        return 0

    if args.command == "ping":
        import json as _json
        import urllib.request

        config = ConfigLoader().load()
        relay_url = _relay_url_with_tls(config.relay.url, config.relay.tls)
        # Converter WS URL para HTTP para o endpoint REST
        http_url = relay_url.replace("wss://", "https://").replace("ws://", "http://")
        http_url = f"{http_url}/session/{args.machine_code}"

        try:
            resp = urllib.request.urlopen(http_url, timeout=5)
            data = _json.loads(resp.read())
            if data.get("host_online"):
                sys.stderr.write(f"{_GREEN}Host {args.machine_code} está online{_RESET}\n")
                return 0
            else:
                sys.stderr.write(f"{_YELLOW}Host {args.machine_code} não encontrado no relay{_RESET}\n")
                return 1
        except Exception as exc:
            sys.stderr.write(f"{_RED}Erro ao contactar relay: {exc}{_RESET}\n")
            return 1

    # --passthrough ou modo padrão (NL Mode)
    config = ConfigLoader().load()
    session = _build_session(config, passthrough=args.passthrough)

    session._write_startup_hint()
    return session.run()


if __name__ == "__main__":
    sys.exit(main())
