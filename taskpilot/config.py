"""Persistance de la configuration utilisateur (chemin du projet, etc.)."""

import json
import os


class Config:
    """Petit conteneur JSON persiste dans le repertoire personnel.

    L'acces se fait par attributs (ex. ``config.project``) ; toute ecriture
    est immediatement sauvegardee sur disque.
    """

    PATH = os.path.join(os.path.expanduser("~"), ".taskpilot.json")

    def __init__(self, path=None):
        self.path = path or self.PATH
        self._data = self._load()

    # -- I/O -----------------------------------------------------------------
    def _load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except (OSError, ValueError):
            pass
        return {}

    def _save(self):
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2)
        except OSError:
            pass

    #: Nombre maximum de chemins de projets conserves dans l'historique.
    MAX_RECENT = 10

    # -- Champs --------------------------------------------------------------
    @property
    def project(self):
        return self._data.get("project", "")

    @project.setter
    def project(self, value):
        self._data["project"] = value
        self._remember_project(value)
        self._save()

    @property
    def recent_projects(self):
        """Liste des derniers chemins de projets utilises (recent en tete)."""
        recent = self._data.get("recent_projects", [])
        return recent if isinstance(recent, list) else []

    def _remember_project(self, value):
        """Ajoute ``value`` en tete de l'historique, sans doublon ni vide."""
        value = (value or "").strip()
        if not value:
            return
        recent = [p for p in self.recent_projects if p != value]
        recent.insert(0, value)
        self._data["recent_projects"] = recent[:self.MAX_RECENT]

    @property
    def confirm_bulk(self):
        """Demander confirmation avant les actions groupées (Tout fermer…)."""
        return bool(self._data.get("confirm_bulk", True))

    @confirm_bulk.setter
    def confirm_bulk(self, value):
        self._data["confirm_bulk"] = bool(value)
        self._save()

    @property
    def save_logs(self):
        """Enregistrer la sortie des consoles dans le dossier temporaire."""
        return bool(self._data.get("save_logs", True))

    @save_logs.setter
    def save_logs(self, value):
        self._data["save_logs"] = bool(value)
        self._save()
