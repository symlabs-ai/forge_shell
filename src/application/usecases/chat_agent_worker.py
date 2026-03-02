"""
ChatAgentWorker — processa mensagens de chat via AgentService em background thread.

Recebe mensagens do chat (relay), roda AgentService.process() em thread daemon,
e enfileira resultado para polling pelo main loop do TerminalSession.
"""
from __future__ import annotations

import logging
import queue
import threading
from collections.abc import Callable
from dataclasses import dataclass

from src.application.ports.agent_port import AgentPort
from src.domain.value_objects import NLResponse

log = logging.getLogger(__name__)


@dataclass
class ChatAgentResult:
    response: NLResponse | None
    original_sender: str


class ChatAgentWorker:
    """Worker que processa chat → AgentService em thread daemon."""

    def __init__(
        self,
        agent: AgentPort,
        build_context: Callable[[], dict],
    ) -> None:
        self._agent = agent
        self._build_context = build_context
        self._result_queue: queue.Queue[ChatAgentResult] = queue.Queue()
        self._busy = False

    def submit(self, sender: str, text: str) -> None:
        """Submete mensagem para processamento. Non-blocking."""
        if self._busy:
            return  # ignora enquanto processando (evita flood)
        self._busy = True
        threading.Thread(
            target=self._run, args=(sender, text), daemon=True,
        ).start()

    def _run(self, sender: str, text: str) -> None:
        """Roda em thread daemon. Chama AgentService.process()."""
        context = self._build_context()
        context["chat_sender"] = sender
        try:
            response = self._agent.process(text=text, context=context)
        except Exception:
            log.debug("ChatAgentWorker: agent.process() failed", exc_info=True)
            response = None
        self._result_queue.put(ChatAgentResult(response=response, original_sender=sender))
        self._busy = False

    def poll(self) -> ChatAgentResult | None:
        """Non-blocking poll. Chamado pelo main loop."""
        try:
            return self._result_queue.get_nowait()
        except queue.Empty:
            return None
