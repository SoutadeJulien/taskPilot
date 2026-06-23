# TaskPilot

Outil graphique (Tkinter, **sans dépendance externe**) pour piloter des tasks
VS Code et surveiller les process Node sous Windows.

## Fonctionnalités

- **Onglet Tasks** — choisir un projet contenant un `.vscode/tasks.json`,
  lister ses tasks, les lancer (y compris les tasks composées `dependsOn`,
  en parallèle ou en séquence), avec **une console intégrée par commande**.
- **Kill d'arbre fiable** — chaque task tourne dans un *Job Object* Windows
  configuré avec `KILL_ON_JOB_CLOSE` : l'arrêter tue tout l'arbre de process
  enfants, là où la poubelle de VS Code laisse souvent des process orphelins.
- **Onglet Process** — liste temps réel des process Node (port, PID, CPU %,
  mémoire, ligne de commande), tri par colonne, kill sélectif ou global.

## Lancer

```sh
python main.py          # ou double-clic sur taskpilot.bat
python -m taskpilot     # équivalent
```

Prérequis : **Python ≥ 3.6** avec `tkinter` (inclus dans les installeurs
python.org sous Windows). La partie kill d'arbre utilise `ctypes` (stdlib) et
n'est pleinement effective que sous Windows ; un repli par groupes de process
existe pour Linux/macOS.

## Architecture

Séparation stricte entre logique métier et présentation :

```
taskpilot/
├── config.py            Persistance de la config utilisateur (~/.taskpilot.json)
├── core/                Logique métier — AUCUNE dépendance à Tkinter
│   ├── system.py        Indicateurs plateforme (IS_WIN, NCPU, NO_WINDOW)
│   ├── processes.py     Détection / kill des process Node (modèle NodeProcess)
│   ├── jobobject.py     Job Object Windows (kill d'arbre via ctypes)
│   ├── vscode_tasks.py  Parsing tasks.json + modèles CommandSpec / TaskNode
│   └── task_runner.py   TaskConsole : process + capture de sortie + kill
└── ui/                  Présentation (Tkinter)
    ├── theme.py         Palette, polices, thème ttk
    ├── icons.py         Icône dessinée à la volée
    ├── widgets.py       RoundedButton (boutons à coins arrondis)
    ├── console_panel.py Panneau d'affichage d'une console
    ├── tasks_tab.py     Onglet Tasks
    ├── process_tab.py   Onglet Process
    └── app.py           Fenêtre principale + point d'entrée main()
```

La couche `core` est testable et réutilisable indépendamment de l'UI : elle ne
communique avec elle que via des objets simples (dataclasses) et une
`queue.Queue` pour le flux de sortie des consoles.
