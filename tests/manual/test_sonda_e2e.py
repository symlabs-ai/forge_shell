"""
Teste E2E: agent conecta via relay, envia comandos, host executa com SondaTool,
output volta para o agent pelo relay.

Fluxo: agent.send_input() → relay → host.on_input() → SondaTool → host.send_output() → relay → agent.on_output()
"""
import asyncio
import ssl

from src.infrastructure.collab.host_relay_client import HostRelayClient
from src.infrastructure.collab.agent_client import AgentClient
from src.infrastructure.agent.tools.shell import SondaTool
from forge_llm import ToolCall

RELAY_URL = "wss://relay.palhano.services"
SSL_CTX = ssl.create_default_context()
SESSION_ID = "test-sonda-e2e-001"
TOKEN = "555555"

sonda = SondaTool(timeout=30)
host_received = []
agent_received = []


def on_host_input(data: bytes):
    host_received.append(data)


def on_agent_output(data: bytes):
    agent_received.append(data)


async def main():
    # --- Conectar host e agent ---
    host = HostRelayClient(RELAY_URL, SESSION_ID, TOKEN, ssl=SSL_CTX)
    await host.connect(on_input=on_host_input)
    print("[1] Host conectado ao relay")

    agent = AgentClient(RELAY_URL, SESSION_ID, TOKEN, ssl=SSL_CTX)
    await agent.connect(on_output=on_agent_output)
    print("[2] Agent conectado ao relay")
    await asyncio.sleep(0.3)

    # === TESTE A: comando seguro ===
    print("\n=== TESTE A: uname -a (comando seguro) ===")
    host_received.clear()
    agent_received.clear()

    await agent.send_input(b"uname -a")
    await asyncio.sleep(0.5)

    cmd = host_received[0].decode()
    print(f"[host]  recebeu: {cmd!r}")

    result = sonda.execute(ToolCall(id="t1", name="sonda", arguments={"command": cmd}))
    print(f"[sonda] is_error={result.is_error}")
    print(f"[sonda] output: {result.content.strip()!r}")

    await host.send_output(result.content.encode())
    await asyncio.sleep(0.5)

    out = agent_received[0].decode().strip()
    print(f"[agent] recebeu: {out!r}")
    assert not result.is_error
    assert len(agent_received) == 1
    print("[OK] agent -> relay -> host -> sonda -> relay -> agent")

    # === TESTE B: comando bloqueado ===
    print("\n=== TESTE B: rm -rf / (comando bloqueado) ===")
    host_received.clear()
    agent_received.clear()

    await agent.send_input(b"rm -rf /")
    await asyncio.sleep(0.5)

    cmd = host_received[0].decode()
    result = sonda.execute(ToolCall(id="t2", name="sonda", arguments={"command": cmd}))
    print(f"[sonda] is_error={result.is_error}")
    print(f"[sonda] content: {result.content!r}")
    assert result.is_error, "Deveria bloquear rm -rf!"

    await host.send_output(f"[BLOCKED] {result.content}".encode())
    await asyncio.sleep(0.5)

    print(f"[agent] recebeu: {agent_received[0].decode()!r}")
    print("[OK] comando destrutivo bloqueado pelo sonda")

    # === TESTE C: pipeline de investigação ===
    print("\n=== TESTE C: pipeline de investigação ===")
    commands = [
        "hostname",
        "df -h / | tail -1",
        "cat /etc/os-release | head -3",
        "ps aux | head -5",
        "uptime",
    ]
    for i, cmd_str in enumerate(commands):
        host_received.clear()
        agent_received.clear()

        await agent.send_input(cmd_str.encode())
        await asyncio.sleep(0.3)

        call = ToolCall(id=f"t{i+3}", name="sonda", arguments={"command": cmd_str})
        result = sonda.execute(call)
        await host.send_output(result.content.encode())
        await asyncio.sleep(0.3)

        out = agent_received[0].decode().strip() if agent_received else "(empty)"
        # truncar output para visualização
        first_line = out.split("\n")[0][:100]
        print(f"  {cmd_str:35s} -> {first_line}")

    print("[OK] pipeline de investigação completo")

    # === TESTE D: mais deny patterns ===
    print("\n=== TESTE D: deny patterns ===")
    blocked = ["dd if=/dev/zero of=/dev/sda", "mkfs.ext4 /dev/sda1", "shutdown -h now", ":(){ :|:& };:"]
    for cmd_str in blocked:
        result = sonda.execute(ToolCall(id="td", name="sonda", arguments={"command": cmd_str}))
        status = "BLOCKED" if result.is_error else "ALLOWED"
        print(f"  {cmd_str:40s} -> {status}")
        assert result.is_error, f"Deveria bloquear: {cmd_str}"
    print("[OK] todos os comandos destrutivos bloqueados")

    await host.close()
    await agent.close()

    print("\n" + "=" * 60)
    print("ALL SONDA E2E TESTS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
