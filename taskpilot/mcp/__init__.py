"""Serveur MCP (lecture seule) exposant les logs de session de TaskPilot.

Conçu pour être lancé en stdio par un client MCP (Zed, Claude Code…) :

    python -m taskpilot.mcp

Il ne tourne **que** pendant qu'un client l'utilise ; il n'y a donc aucune
option d'activation côté application : la présence (ou l'absence) de la
déclaration dans la config du client suffit à l'activer / le désactiver.
"""
