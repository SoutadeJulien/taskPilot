# TaskPilot

Graphical tool (PySide6 / Qt) to drive VS Code tasks and monitor Node
processes on Windows.

## Features

- **Tasks tab** — pick a project containing a `.vscode/tasks.json`, list its
  tasks and run them (including compound `dependsOn` tasks, in parallel or in
  sequence), with **one embedded console per command**.
- **Profiles** — group tasks from **several projects** (the "backend" of one,
  the "frontend" of another…) and launch everything in one click from the
  *★ Profiles* button (managed via *Tasks ▸ Manage profiles…*).
- **Reliable tree kill** — each task runs in a Windows *Job Object* configured
  with `KILL_ON_JOB_CLOSE`: stopping it kills the whole child process tree,
  where the VS Code trash can often leaves orphan processes behind.
- **Native notifications** — Windows toast when a task finishes (or fails),
  handy when the window is in the background; configurable in *Options ▸
  Behavior*.
- **Process tab** — real-time list of Node processes (port, PID, CPU %,
  memory, command line), with a **trend sparkline** (area = CPU, line = memory)
  per process, sorting by column, selective or global kill.
- **Customizable appearance** — ~30 hot-swappable themes, custom accent,
  rounded corners, density, UI/console fonts, window opacity, alternating rows
  and tab alignment.

## Running

```sh
python main.py          # or double-click start.bat (creates the .venv if needed)
python -m taskpilot     # equivalent
```

Requirements: **Python ≥ 3.9** (tested with 3.13) and the dependencies from
`requirements.txt` (`PySide6`, `pywinpty`, `pyte`). The tree-kill feature uses
`ctypes` (stdlib) and is fully effective only on Windows; a process-group
fallback exists for Linux/macOS.

## Building the standalone executable

```sh
build.bat               # produces dist\TaskPilot.exe via PyInstaller (taskpilot.spec)
```

The exe is self-contained (PySide6 + the `pywinpty`/`pyte` PTY bundled in), no
installation required on the user's side. CI
(`.github/workflows/build-release.yml`) builds it and publishes a release on
every push to `master`.

## Logs MCP server

A small read-only [MCP](https://modelcontextprotocol.io) server lets an AI
assistant (Zed, Claude Code…) inspect the current session's logs. It is **not**
integrated into the application: it is launched over stdio by the client *on
demand*, which acts as an on/off switch — present in the client config = active,
removed = inactive. No option in TaskPilot, no open port, nothing running
permanently.

```sh
py -V:3.13 -m pip install -r requirements-mcp.txt   # the `mcp` SDK (Python ≥ 3.10)
py -V:3.13 -m taskpilot.mcp                          # manual launch (debug)
```

The logs directory is resolved exactly as in the app (see `Config.log_dir`,
default `%TEMP%\taskpilot-logs`). Exposed tools: `list_logs`, `read_log`,
`tail_log`, `search_logs` (literal or regex).

Declaration in **Zed**'s `settings.json`:

```json
{
  "context_servers": {
    "taskpilot-logs": {
      "command": "C:\\path\\to\\python.exe",
      "args": ["-m", "taskpilot.mcp"],
      "env": { "PYTHONPATH": "C:\\path\\to\\taskPilot" }
    }
  }
}
```

Replace both paths with your own:

- `command` — the Python interpreter **≥ 3.10** to use (the one that has the
  `mcp` SDK installed), e.g. `C:\\Python313\\python.exe`. To find it:
  `py -V:3.13 -c "import sys; print(sys.executable)"`.
- `env.PYTHONPATH` — the **repository root** of TaskPilot (the folder
  containing `main.py` and the `taskpilot/` package), so that `-m taskpilot.mcp`
  can be resolved.

> In Zed's *Add MCP Server* dialog, paste only the `"taskpilot-logs": { … }`
> entry (a single key/value pair, without the `context_servers` wrapper). When
> editing `settings.json` by hand, keep the full wrapper shown above.

> The `mcp` SDK requires Python ≥ 3.10: use the 3.13 interpreter, not a
> 3.7/3.9 one.

## Architecture

Strict separation between business logic and presentation:

```
taskpilot/
├── config.py            Persistence of the user config (~/.taskpilot.json)
├── core/                Business logic — NO dependency on the UI
│   ├── system.py        Platform flags (IS_WIN, NCPU, NO_WINDOW)
│   ├── processes.py     Detection / kill of Node processes (NodeProcess model)
│   ├── jobobject.py     Windows Job Object (tree kill via ctypes)
│   ├── vscode_tasks.py  tasks.json parsing + CommandSpec / TaskNode models
│   └── task_runner.py   TaskConsole: process + output capture + kill
├── mcp/                 Logs MCP server (read-only, launched separately)
└── qt/                  Presentation (PySide6 / Qt)
    ├── theme.py         Palettes, QSS, live theme switching
    ├── main_window.py   Main window, menus, status bar
    ├── tasks_tab.py     Tasks tab
    ├── process_tab.py   Process tab
    ├── console_view.py  Read-only console of a task
    └── terminal_view.py Interactive terminal (pyte VT emulator + PTY)
```

The `core` layer is testable and reusable independently of the UI: it
communicates with the UI only through plain objects (dataclasses) and a
`queue.Queue` for the console output stream.
