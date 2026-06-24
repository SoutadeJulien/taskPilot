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

    # -- Couleur par projet (reperage des consoles) --------------------------
    def _project_colors_map(self):
        colors = self._data.get("project_colors", {})
        return colors if isinstance(colors, dict) else {}

    def get_project_color(self, project):
        """Couleur (hex) choisie pour reperer les consoles de ``project``.

        Chaine vide si aucune couleur n'a ete definie. Sert a distinguer d'un
        coup d'oeil les consoles de deux worktrees (memes labels de tasks).
        """
        color = self._project_colors_map().get(project)
        return color if isinstance(color, str) else ""

    def set_project_color(self, project, color):
        """Definit la couleur d'un projet (chaine vide / None => la retire)."""
        project = (project or "").strip()
        if not project:
            return
        colors = dict(self._project_colors_map())
        if color:
            colors[project] = color
        else:
            colors.pop(project, None)
        self._data["project_colors"] = colors
        self._save()

    # -- Couleur par groupe (consoles d'une task composite) ------------------
    def _group_colors_map(self):
        colors = self._data.get("group_colors", {})
        return colors if isinstance(colors, dict) else {}

    def get_group_colors(self):
        """Couleurs (hex) memorisees pour chaque groupe, par label.

        Permet de retrouver la meme couleur d'une session a l'autre plutot que
        de re-cycler la palette a chaque lancement.
        """
        return {
            k: v for k, v in self._group_colors_map().items()
            if isinstance(k, str) and isinstance(v, str)
        }

    def set_group_color(self, group, color):
        """Memorise la couleur d'un groupe (chaine vide / None => la retire)."""
        group = (group or "").strip()
        if not group:
            return
        colors = dict(self._group_colors_map())
        if color:
            colors[group] = color
        else:
            colors.pop(group, None)
        self._data["group_colors"] = colors
        self._save()

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

    @property
    def theme(self):
        """Nom du theme d'interface Qt actif."""
        value = self._data.get("theme", "")
        return value if isinstance(value, str) and value else "Ardoise indigo"

    @theme.setter
    def theme(self, value):
        self._data["theme"] = (value or "").strip()
        self._save()

    @property
    def radius(self):
        """Facteur d'arrondi des bordures (0 = carré, 1 = défaut, ~1.8 = rond)."""
        value = self._data.get("radius", 1.0)
        try:
            return min(2.0, max(0.0, float(value)))
        except (TypeError, ValueError):
            return 1.0

    @radius.setter
    def radius(self, value):
        try:
            self._data["radius"] = min(2.0, max(0.0, float(value)))
        except (TypeError, ValueError):
            self._data["radius"] = 1.0
        self._save()

    def _get_float(self, key, default, lo, hi):
        try:
            return min(hi, max(lo, float(self._data.get(key, default))))
        except (TypeError, ValueError):
            return default

    def _set_float(self, key, value, default, lo, hi):
        try:
            self._data[key] = min(hi, max(lo, float(value)))
        except (TypeError, ValueError):
            self._data[key] = default
        self._save()

    @property
    def density(self):
        """Densité d'espacement de l'UI (0.7 compact … 1.5 confortable)."""
        return self._get_float("density", 1.0, 0.7, 1.5)

    @density.setter
    def density(self, value):
        self._set_float("density", value, 1.0, 0.7, 1.5)

    @property
    def ui_font_family(self):
        v = self._data.get("ui_font_family", "")
        return v if isinstance(v, str) and v else "Segoe UI"

    @ui_font_family.setter
    def ui_font_family(self, value):
        self._data["ui_font_family"] = (value or "").strip()
        self._save()

    @property
    def ui_font_size(self):
        return int(self._get_float("ui_font_size", 13, 9, 22))

    @ui_font_size.setter
    def ui_font_size(self, value):
        self._set_float("ui_font_size", value, 13, 9, 22)

    @property
    def mono_font_family(self):
        v = self._data.get("mono_font_family", "")
        return v if isinstance(v, str) and v else "Cascadia Mono, Consolas"

    @mono_font_family.setter
    def mono_font_family(self, value):
        self._data["mono_font_family"] = (value or "").strip()
        self._save()

    @property
    def mono_font_size(self):
        return int(self._get_float("mono_font_size", 10, 7, 22))

    @mono_font_size.setter
    def mono_font_size(self, value):
        self._set_float("mono_font_size", value, 10, 7, 22)

    @property
    def accent_override(self):
        """Couleur d'accent personnalisée (hex) ou "" pour suivre le thème."""
        v = self._data.get("accent_override", "")
        return v if isinstance(v, str) else ""

    @accent_override.setter
    def accent_override(self, value):
        self._data["accent_override"] = (value or "").strip()
        self._save()

    @property
    def opacity(self):
        """Opacité de la fenêtre (0.5 … 1.0)."""
        return self._get_float("opacity", 1.0, 0.5, 1.0)

    @opacity.setter
    def opacity(self, value):
        self._set_float("opacity", value, 1.0, 0.5, 1.0)

    @property
    def alt_rows(self):
        """Lignes alternées dans les arbres/listes."""
        return bool(self._data.get("alt_rows", True))

    @alt_rows.setter
    def alt_rows(self, value):
        self._data["alt_rows"] = bool(value)
        self._save()

    @property
    def tab_align(self):
        """Alignement des onglets principaux : left / center / right."""
        v = self._data.get("tab_align", "left")
        return v if v in ("left", "center", "right") else "left"

    @tab_align.setter
    def tab_align(self, value):
        self._data["tab_align"] = value if value in (
            "left", "center", "right") else "left"
        self._save()

    @property
    def show_statusbar(self):
        return bool(self._data.get("show_statusbar", True))

    @show_statusbar.setter
    def show_statusbar(self, value):
        self._data["show_statusbar"] = bool(value)
        self._save()

    @property
    def log_dir(self):
        """Dossier où enregistrer les logs (vide => dossier temporaire par défaut)."""
        value = self._data.get("log_dir", "")
        return value if isinstance(value, str) else ""

    @log_dir.setter
    def log_dir(self, value):
        self._data["log_dir"] = (value or "").strip()
        self._save()
