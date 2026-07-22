"""Dialogue d'edition d'un script utilitaire (Python / Node).

Un *script* est un bout de code nomme, lance en un clic dans une console. Ce
dialogue en edite le nom, le langage, le dossier de travail (optionnel) et le
code, avec des modeles de demarrage prets a l'emploi.
"""

import os

from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFileDialog, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPlainTextEdit, QPushButton, QVBoxLayout)

from taskpilot.core.scripts import LANGUAGES
from taskpilot.qt import theme

#: Modeles de demarrage par langage : de quoi partir sur une base fonctionnelle
#: (le dossier de travail est le projet courant, aussi dans TASKPILOT_PROJECT).
TEMPLATES = {
    "python": '''"""Script TaskPilot — le dossier de travail est le projet courant.

Le chemin du projet est aussi dans la variable d'environnement TASKPILOT_PROJECT.
"""
import os
import shutil

root = os.getcwd()
print(f"Dossier : {root}\\n")

# Exemple : supprimer tous les node_modules sous le projet.
removed = 0
for dirpath, dirnames, filenames in os.walk(root, topdown=True):
    if "node_modules" in dirnames:
        target = os.path.join(dirpath, "node_modules")
        print("Suppression :", target)
        shutil.rmtree(target, ignore_errors=True)
        removed += 1
        dirnames.remove("node_modules")  # ne pas descendre dedans

print(f"\\n{removed} dossier(s) node_modules supprime(s).")
''',
    "node": '''// Script TaskPilot — le dossier de travail est le projet courant.
// Le chemin du projet est aussi dans la variable d'environnement TASKPILOT_PROJECT.

const fs = require("fs");
const path = require("path");

const root = process.cwd();
console.log(`Dossier : ${root}\\n`);

// Exemple : lister les dossiers vides sous le projet.
function walk(dir) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (!entry.isDirectory()) continue;
    if (entry.name === "node_modules" || entry.name === ".git") continue;
    const p = path.join(dir, entry.name);
    if (fs.readdirSync(p).length === 0) console.log("Vide :", p);
    else walk(p);
  }
}
walk(root);
''',
}


class ScriptDialog(QDialog):
    """Cree ou edite un script ``{name, language, code, cwd}``."""

    def __init__(self, parent, script=None):
        super().__init__(parent)
        self.setWindowTitle("Script" if script else "Nouveau script")
        self.resize(680, 560)
        script = script or {}

        v = QVBoxLayout(self)

        row = QHBoxLayout()
        row.addWidget(QLabel("Nom :"))
        self._name = QLineEdit(script.get("name", ""))
        row.addWidget(self._name, 1)
        row.addWidget(QLabel("Langage :"))
        self._lang = QComboBox()
        for key, meta in LANGUAGES.items():
            self._lang.addItem(meta["label"], key)
        idx = self._lang.findData(script.get("language", "python"))
        self._lang.setCurrentIndex(max(0, idx))
        row.addWidget(self._lang)
        v.addLayout(row)

        cwd_row = QHBoxLayout()
        cwd_row.addWidget(QLabel("Dossier :"))
        self._cwd = QLineEdit(script.get("cwd", ""))
        self._cwd.setPlaceholderText("(projet courant par défaut)")
        cwd_row.addWidget(self._cwd, 1)
        browse = QPushButton("Parcourir…")
        browse.clicked.connect(self._browse)
        cwd_row.addWidget(browse)
        v.addLayout(cwd_row)

        code_row = QHBoxLayout()
        code_row.addWidget(QLabel("Code :"))
        code_row.addStretch(1)
        tmpl = QPushButton("Insérer un modèle")
        tmpl.setToolTip("Remplace le code par un exemple pour le langage choisi")
        tmpl.clicked.connect(self._insert_template)
        code_row.addWidget(tmpl)
        v.addLayout(code_row)

        self._code = QPlainTextEdit(script.get("code", ""))
        self._code.setFont(theme.mono_font())
        self._code.setTabChangesFocus(False)
        self._code.setPlaceholderText(
            "Écris ton script ici, ou clique « Insérer un modèle ».")
        v.addWidget(self._code, 1)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self._accept)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)

        if not script:
            self._insert_template(confirm=False)

    def _browse(self):
        start = self._cwd.text().strip() or os.path.expanduser("~")
        path = QFileDialog.getExistingDirectory(self, "Dossier de travail", start)
        if path:
            self._cwd.setText(path.replace("/", os.sep))

    def _insert_template(self, confirm=True):
        language = self._lang.currentData()
        code = TEMPLATES.get(language, "")
        if confirm and self._code.toPlainText().strip():
            if QMessageBox.question(
                    self, "Insérer un modèle",
                    "Remplacer le code actuel par le modèle ?") \
                    != QMessageBox.Yes:
                return
        self._code.setPlainText(code)

    def _accept(self):
        if not self._name.text().strip():
            QMessageBox.information(self, "Nom requis",
                                    "Donne un nom à ton script.")
            return
        self.accept()

    def result_script(self):
        return {
            "name": self._name.text().strip(),
            "language": self._lang.currentData(),
            "code": self._code.toPlainText(),
            "cwd": self._cwd.text().strip(),
        }
