"""Dialogues de gestion des profils (groupes de tasks multi-projets).

Un *profil* est une liste ordonnee de tasks (chacune ``{project, label}``)
lancables ensemble. Les tasks peuvent provenir de projets differents — c'est
tout l'interet : reunir « backend » d'un projet, « frontend » d'un autre, etc.
"""

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFileDialog, QHBoxLayout,
    QInputDialog, QLabel, QListWidget, QListWidgetItem, QMessageBox,
    QPushButton, QVBoxLayout)

from taskpilot.core.vscode_tasks import load_vscode_tasks, task_label


def _proj_name(path):
    return os.path.basename(os.path.normpath(path)) or path


class AddTaskDialog(QDialog):
    """Choisir un projet puis une ou plusieurs tasks a ajouter au profil."""

    def __init__(self, parent, recent):
        super().__init__(parent)
        self.setWindowTitle("Ajouter des tasks au profil")
        self.resize(480, 440)
        self._selected = []      # liste de (project, label)

        v = QVBoxLayout(self)
        row = QHBoxLayout()
        row.addWidget(QLabel("Projet :"))
        self._combo = QComboBox()
        self._combo.setEditable(False)
        self._combo.addItems(list(recent))
        self._combo.activated.connect(lambda _i: self._load())
        row.addWidget(self._combo, 1)
        browse = QPushButton("Parcourir…")
        browse.clicked.connect(self._browse)
        row.addWidget(browse)
        v.addLayout(row)

        self._list = QListWidget()
        self._list.setSelectionMode(QListWidget.ExtendedSelection)
        self._list.itemDoubleClicked.connect(lambda _i: self.accept())
        v.addWidget(self._list, 1)

        self._info = QLabel("")
        v.addWidget(self._info)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)

        if self._current_project():
            self._load()

    def _current_project(self):
        return self._combo.currentText().strip()

    def _browse(self):
        start = self._current_project() or os.path.expanduser("~")
        path = QFileDialog.getExistingDirectory(self, "Choisir un projet", start)
        if not path:
            return
        path = path.replace("/", os.sep)
        idx = self._combo.findText(path)
        if idx < 0:
            self._combo.insertItem(0, path)
            idx = 0
        self._combo.setCurrentIndex(idx)
        self._load()

    def _load(self):
        self._list.clear()
        project = self._current_project()
        if not project:
            self._info.setText("")
            return
        try:
            tasks = load_vscode_tasks(project)
        except FileNotFoundError:
            self._info.setText("⚠ Aucun .vscode/tasks.json dans ce projet.")
            return
        except Exception as e:  # noqa: BLE001
            self._info.setText(f"⚠ {e}")
            return
        for t in tasks:
            label = task_label(t)
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, label)
            self._list.addItem(item)
        self._info.setText(f"{self._list.count()} task(s) — "
                           "sélection multiple possible.")

    def accept(self):
        project = self._current_project()
        self._selected = [(project, it.data(Qt.UserRole))
                          for it in self._list.selectedItems()]
        super().accept()

    def selected(self):
        return self._selected


class ProfilesDialog(QDialog):
    """Creer / editer les profils ; persiste chaque modification."""

    def __init__(self, parent, settings):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Profils — groupes de tasks")
        self.resize(660, 470)
        self._profiles = settings.get_profiles()
        self._build()
        self._refresh_profiles()

    # -- Construction --------------------------------------------------------
    def _build(self):
        outer = QVBoxLayout(self)
        intro = QLabel("Regroupe des tasks de n'importe quels projets pour les "
                       "lancer ensemble en un clic.")
        intro.setWordWrap(True)
        outer.addWidget(intro)

        cols = QHBoxLayout()
        cols.addLayout(self._build_profiles_col(), 2)
        cols.addLayout(self._build_items_col(), 3)
        outer.addLayout(cols, 1)

        bb = QDialogButtonBox(QDialogButtonBox.Close)
        bb.rejected.connect(self.accept)
        close_btn = bb.button(QDialogButtonBox.Close)
        close_btn.clicked.connect(self.accept)
        outer.addWidget(bb)

    def _build_profiles_col(self):
        col = QVBoxLayout()
        col.addWidget(QLabel("Profils"))
        self._plist = QListWidget()
        self._plist.currentRowChanged.connect(lambda _i: self._refresh_items())
        col.addWidget(self._plist, 1)
        bar = QHBoxLayout()
        for text, slot in (("Nouveau", self._new_profile),
                           ("Renommer", self._rename_profile),
                           ("Supprimer", self._delete_profile)):
            b = QPushButton(text)
            b.clicked.connect(slot)
            bar.addWidget(b)
        col.addLayout(bar)
        return col

    def _build_items_col(self):
        col = QVBoxLayout()
        col.addWidget(QLabel("Tasks du profil"))
        self._ilist = QListWidget()
        col.addWidget(self._ilist, 1)
        bar = QHBoxLayout()
        add = QPushButton("Ajouter des tasks…")
        add.clicked.connect(self._add_items)
        rem = QPushButton("Retirer")
        rem.clicked.connect(self._remove_item)
        up = QPushButton("↑")
        up.clicked.connect(lambda: self._move(-1))
        down = QPushButton("↓")
        down.clicked.connect(lambda: self._move(1))
        for b in (add, rem, up, down):
            bar.addWidget(b)
        col.addLayout(bar)
        return col

    # -- Persistance ---------------------------------------------------------
    def _save(self):
        self.settings.set_profiles(self._profiles)

    # -- Profils -------------------------------------------------------------
    def _current_profile(self):
        row = self._plist.currentRow()
        if 0 <= row < len(self._profiles):
            return self._profiles[row]
        return None

    def _refresh_profiles(self, select=None):
        self._plist.blockSignals(True)
        self._plist.clear()
        for prof in self._profiles:
            self._plist.addItem(f"{prof['name']}   ({len(prof['items'])})")
        self._plist.blockSignals(False)
        if self._profiles:
            row = select if select is not None else 0
            self._plist.setCurrentRow(max(0, min(row, len(self._profiles) - 1)))
        self._refresh_items()

    def _new_profile(self):
        name, ok = QInputDialog.getText(self, "Nouveau profil", "Nom :")
        name = (name or "").strip()
        if not ok or not name:
            return
        self._profiles.append({"name": name, "items": []})
        self._save()
        self._refresh_profiles(select=len(self._profiles) - 1)

    def _rename_profile(self):
        prof = self._current_profile()
        if prof is None:
            return
        name, ok = QInputDialog.getText(
            self, "Renommer le profil", "Nom :", text=prof["name"])
        name = (name or "").strip()
        if not ok or not name:
            return
        prof["name"] = name
        self._save()
        self._refresh_profiles(select=self._plist.currentRow())

    def _delete_profile(self):
        row = self._plist.currentRow()
        prof = self._current_profile()
        if prof is None:
            return
        if QMessageBox.question(
                self, "Supprimer", f"Supprimer le profil « {prof['name']} » ?") \
                != QMessageBox.Yes:
            return
        self._profiles.pop(row)
        self._save()
        self._refresh_profiles(select=row)

    # -- Tasks d'un profil ---------------------------------------------------
    def _refresh_items(self):
        self._ilist.clear()
        prof = self._current_profile()
        if prof is None:
            return
        for it in prof["items"]:
            text = f"{_proj_name(it['project'])}  ›  {it['label']}"
            row = QListWidgetItem(text)
            row.setToolTip(it["project"])
            self._ilist.addItem(row)

    def _add_items(self):
        prof = self._current_profile()
        if prof is None:
            QMessageBox.information(
                self, "Aucun profil",
                "Crée d'abord un profil, puis ajoute-lui des tasks.")
            return
        dlg = AddTaskDialog(self, self.settings.recent_projects)
        if dlg.exec() != QDialog.Accepted:
            return
        existing = {(i["project"], i["label"]) for i in prof["items"]}
        for project, label in dlg.selected():
            if (project, label) not in existing:
                prof["items"].append({"project": project, "label": label})
                existing.add((project, label))
        self._save()
        self._refresh_items()
        self._refresh_profile_counts()

    def _remove_item(self):
        prof = self._current_profile()
        row = self._ilist.currentRow()
        if prof is None or not (0 <= row < len(prof["items"])):
            return
        prof["items"].pop(row)
        self._save()
        self._refresh_items()
        self._ilist.setCurrentRow(min(row, len(prof["items"]) - 1))
        self._refresh_profile_counts()

    def _move(self, delta):
        prof = self._current_profile()
        row = self._ilist.currentRow()
        if prof is None:
            return
        new = row + delta
        if not (0 <= row < len(prof["items"])) or not (0 <= new < len(prof["items"])):
            return
        prof["items"][row], prof["items"][new] = \
            prof["items"][new], prof["items"][row]
        self._save()
        self._refresh_items()
        self._ilist.setCurrentRow(new)

    def _refresh_profile_counts(self):
        """Met a jour le compteur affiche sans perdre la selection courante."""
        row = self._plist.currentRow()
        for i, prof in enumerate(self._profiles):
            self._plist.item(i).setText(f"{prof['name']}   ({len(prof['items'])})")
        self._plist.setCurrentRow(row)
