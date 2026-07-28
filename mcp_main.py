"""Point d'entree du serveur MCP des logs, packageable en executable.

Pendant : ``main.py`` (application Qt). Ici, ni Qt ni PTY : uniquement le
serveur MCP stdio, pour produire un ``TaskPilotMcp.exe`` autonome que le client
(Zed, Claude Code...) lance directement, sans Python ni SDK installes.

Lance avec :  python mcp_main.py   (equivalent a ``python -m taskpilot.mcp``)
"""

from taskpilot.mcp.__main__ import main

if __name__ == "__main__":
    main()
