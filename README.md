# TaskPilot

Outil graphique (PySide6 / Qt) pour piloter des tasks VS Code et surveiller les
process Node sous Windows.

## Fonctionnalités

- **Onglet Tasks** — choisir un projet contenant un `.vscode/tasks.json`,
  lister ses tasks, les lancer (y compris les tasks composées `dependsOn`,
  en parallèle ou en séquence), avec **une console intégrée par commande**.
- **Kill d'arbre fiable** — chaque task tourne dans un *Job Object* Windows
  configuré avec `KILL_ON_JOB_CLOSE` : l'arrêter tue tout l'arbre de process
  enfants, là où la poubelle de VS Code laisse souvent des process orphelins.
- **Onglet Process** — liste temps réel des process Node (port, PID, CPU %,
  mémoire, ligne de commande), tri par colonne, kill sélectif ou global.
- **Apparence personnalisable** — ~30 thèmes interchangeables à chaud, accent
  custom, arrondis, densité, polices UI/console, opacité de la fenêtre, lignes
  alternées et alignement des onglets.

## Lancer

```sh
python main.py          # ou double-clic sur start.bat (crée le venv .venv au besoin)
python -m taskpilot     # équivalent
```

Prérequis : **Python ≥ 3.9** (testé avec 3.13) et les dépendances de
`requirements.txt` (`PySide6`, `pywinpty`, `pyte`). La partie kill d'arbre
utilise `ctypes` (stdlib) et n'est pleinement effective que sous Windows ; un
repli par groupes de process existe pour Linux/macOS.

## Construire l'exécutable autonome

```sh
build.bat               # génère dist\TaskPilot.exe via PyInstaller (taskpilot.spec)
```

L'exe est autonome (PySide6 + le PTY `pywinpty`/`pyte` embarqués), aucune
installation côté utilisateur. La CI (`.github/workflows/build-release.yml`) le
construit et publie une release à chaque push sur `master`.

## Architecture

Séparation stricte entre logique métier et présentation :

```
taskpilot/
├── config.py            Persistance de la config utilisateur (~/.taskpilot.json)
├── core/                Logique métier — AUCUNE dépendance à l'UI
│   ├── system.py        Indicateurs plateforme (IS_WIN, NCPU, NO_WINDOW)
│   ├── processes.py     Détection / kill des process Node (modèle NodeProcess)
│   ├── jobobject.py     Job Object Windows (kill d'arbre via ctypes)
│   ├── vscode_tasks.py  Parsing tasks.json + modèles CommandSpec / TaskNode
│   └── task_runner.py   TaskConsole : process + capture de sortie + kill
└── qt/                  Présentation (PySide6 / Qt)
    ├── theme.py         Palettes, QSS, live-switch des thèmes
    ├── main_window.py   Fenêtre principale, menus, barre d'état
    ├── tasks_tab.py     Onglet Tasks
    ├── process_tab.py   Onglet Process
    ├── console_view.py  Console (lecture seule) d'une task
    └── terminal_view.py Terminal interactif (émulateur VT pyte + PTY)
```

La couche `core` est testable et réutilisable indépendamment de l'UI : elle ne
communique avec elle que via des objets simples (dataclasses) et une
`queue.Queue` pour le flux de sortie des consoles.
