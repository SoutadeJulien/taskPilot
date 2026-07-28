"""Verifie qu'un binaire du serveur MCP repond bien sur stdio.

    python tools/smoke_mcp.py dist/TaskPilotMcp.exe

Le build PyInstaller peut reussir alors que l'executable meurt au demarrage
(module collecte de travers, stdin/stdout absents si ``console=False``...).
On rejoue donc la sequence d'un vrai client : ``initialize``, la notification
``initialized``, ``tools/list``, puis un appel reel a ``list_logs``. Sort en
code 1 au moindre ecart — c'est ce qui bloque la publication en CI.
"""

import json
import os
import subprocess
import sys
import threading

EXPECTED_TOOLS = {"list_logs", "read_log", "tail_log", "search_logs"}
TIMEOUT = 60


def _fail(message: str) -> None:
    print(f"ECHEC : {message}", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    if len(sys.argv) != 2:
        _fail("usage : smoke_mcp.py <chemin de l'executable>")
    # Absolutise : sous Windows, CreateProcess rejette un chemin relatif ecrit
    # avec des `/` (« dist/TaskPilotMcp.exe »), forme pourtant naturelle en CI.
    exe = os.path.abspath(sys.argv[1])
    if not os.path.isfile(exe):
        _fail(f"executable introuvable : {exe}")

    proc = subprocess.Popen(
        [exe], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, encoding="utf-8", bufsize=1)

    # Chien de garde : un binaire qui lit stdin sans jamais repondre bloquerait
    # `readline` indefiniment (et donc le job CI). Le tuer ferme le pipe, ce qui
    # fait retourner `readline` a vide et bascule sur l'erreur « aucune reponse ».
    watchdog = threading.Timer(TIMEOUT, proc.kill)
    watchdog.daemon = True
    watchdog.start()

    def send(payload: dict) -> None:
        proc.stdin.write(json.dumps(payload) + "\n")
        proc.stdin.flush()

    def receive(step: str) -> dict:
        line = proc.stdout.readline()
        if not line:
            # Le process est mort : sa stderr porte la vraie cause (traceback
            # d'import, le plus souvent).
            proc.kill()
            _fail(f"{step} : aucune reponse.\n{proc.stderr.read()}")
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            _fail(f"{step} : reponse illisible : {line!r}")
        if "error" in message:
            _fail(f"{step} : {message['error']}")
        return message["result"]

    try:
        send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2024-11-05", "capabilities": {},
            "clientInfo": {"name": "smoke", "version": "0"}}})
        info = receive("initialize")["serverInfo"]
        print(f"initialize  -> {info['name']} {info['version']}")

        send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        send({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        names = {t["name"] for t in receive("tools/list")["tools"]}
        print(f"tools/list  -> {sorted(names)}")
        missing = EXPECTED_TOOLS - names
        if missing:
            _fail(f"outils manquants : {sorted(missing)}")

        # Appel reel : valide que le code metier (resolution du dossier de logs)
        # survit au gel, pas seulement la couche protocole.
        send({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
              "params": {"name": "list_logs", "arguments": {}}})
        result = receive("tools/call list_logs")
        if result.get("isError"):
            _fail(f"list_logs a renvoye une erreur : {result}")
        print("list_logs   -> ok")

        proc.stdin.close()
        proc.wait(timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        proc.kill()
        _fail("le serveur ne s'est pas arrete apres fermeture de stdin")
    finally:
        watchdog.cancel()
        if proc.poll() is None:
            proc.kill()

    print("Serveur MCP conforme.")


if __name__ == "__main__":
    main()
