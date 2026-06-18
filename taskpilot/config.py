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

    # -- Favoris (par projet) ------------------------------------------------
    def _favorites_map(self):
        fav = self._data.get("favorites", {})
        return fav if isinstance(fav, dict) else {}

    def get_favorites(self, project):
        """Liste des labels de tasks marquées favorites pour ``project``."""
        labels = self._favorites_map().get(project, [])
        return labels if isinstance(labels, list) else []

    def toggle_favorite(self, project, label):
        """Ajoute/retire ``label`` des favoris de ``project``. Retourne l'état."""
        fav = dict(self._favorites_map())
        labels = [x for x in fav.get(project, []) if isinstance(x, str)]
        if label in labels:
            labels.remove(label)
            is_fav = False
        else:
            labels.append(label)
            is_fav = True
        if labels:
            fav[project] = labels
        else:
            fav.pop(project, None)
        self._data["favorites"] = fav
        self._save()
        return is_fav

    # -- Etat replié des sections de la liste des tasks ----------------------
    @property
    def fav_collapsed(self):
        return bool(self._data.get("fav_collapsed", False))

    @fav_collapsed.setter
    def fav_collapsed(self, value):
        self._data["fav_collapsed"] = bool(value)
        self._save()

    @property
    def all_collapsed(self):
        return bool(self._data.get("all_collapsed", False))

    @all_collapsed.setter
    def all_collapsed(self, value):
        self._data["all_collapsed"] = bool(value)
        self._save()

    @property
    def save_logs(self):
        """Enregistrer la sortie des consoles dans le dossier temporaire."""
        return bool(self._data.get("save_logs", True))

    @save_logs.setter
    def save_logs(self, value):
        self._data["save_logs"] = bool(value)
        self._save()
