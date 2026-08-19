# TaskPilot

Graphical tool (PySide6 / Qt) to drive VS Code tasks and monitor Node
processes. Runs on **Windows, Linux and macOS** — each platform-specific piece
(PTY, process inventory, tree kill, notifications, shells) has a native backend
behind a single abstraction layer, `taskpilot/core/system.py`.

## Features

- **Tasks tab** — pick a project containing a `.vscode/tasks.json`, list its
  tasks and run them (including compound `dependsOn` tasks, in parallel or in
  sequence), with **one embedded console per command**.
- **Profiles** — group tasks from **several projects** (the "backend" of one,
  the "frontend" of another…) and launch everything in one click from the
  *★ Profiles* button (managed via *Tasks ▸ Manage profiles…*). Tick a task in
  the profile editor to make it **blocking**: the profile waits for it to exit
  before starting the next ones, so a build can complete before the servers
  that consume its output start. Only tick tasks that actually terminate
  (builds, migrations) — never a server or a watcher.
- **Scripts** — a third *⚙ Scripts* sub-tab (next to Tasks / Profiles) to write,
  name and run small **Python or Node** utility scripts (purge `node_modules`,
  list empty folders…) in an embedded console. Scripts run with the current
  project as working directory (also exposed as `TASKPILOT_PROJECT`); starter
  templates are provided for both languages.
- **Search in a console** — `Ctrl+F` opens an inline find bar over the current
  console: every match is highlighted, the current one stands out, `Enter` /
  `Shift+Enter` (or `F3` / `Shift+F3`) walk through them, with *match case* and
  *whole words* toggles and a `3 / 12` counter. The search follows live output
  (matches are rescanned as new lines arrive), and `Esc` closes it.
- **Structured output highlighting** — when a console line contains JSON
  (`console.log(obj)`, single-line or pretty-printed over several lines), a
  YAML document (starting with `---`) or an XML/HTML tag, keys, strings,
  numbers and literals are syntax-coloured with the current theme. Detection is
  automatic (JSON is validated by a real parser, so a `[12:00:03]` log prefix
  is not mistaken for an array); when it is not enough, tag the payload
  explicitly with `console.log("#json", obj)` — the marker is stripped from the
  display and forces the mode for the whole block (`#json`, `#yaml`, `#xml`).
  Toggle in *Console ▸ Colour data*.
- **Reliable tree kill** — stopping a task kills its whole child process tree,
  where the VS Code trash can often leaves orphan processes behind. On Windows
  each task runs in a *Job Object* configured with `KILL_ON_JOB_CLOSE`; on
  Unix it gets its own session (`start_new_session`) and the whole process
  group is signalled. Killing an arbitrary PID from the *Process* tab walks the
  process tree instead — an unrelated PID is not necessarily alone in its group.
- **Native notifications** — a desktop notification when a task finishes (or
  fails), handy when the window is in the background; configurable in *Options ▸
  Behavior*. Routed through the notification area when the desktop has one, and
  through `notify-send` otherwise (GNOME/Wayland no longer expose a tray).
- **Process tab** — real-time list of Node processes (port, PID, CPU %,
  memory, command line), with a **trend sparkline** (area = CPU, line = memory)
  per process, sorting by column, selective or global kill.
- **Customizable appearance** — ~30 hot-swappable themes, custom accent,
  rounded corners, density, UI/console fonts, window opacity, alternating rows
  and tab alignment.

## Running

```sh
python main.py          # or double-click start.bat / run ./start.sh
python -m taskpilot     # equivalent
```

`start.bat` (Windows) and `start.sh` (Unix) create the `.venv` and install the
dependencies on first run.

Requirements: **Python ≥ 3.9** (tested with 3.13) and the dependencies from
`requirements.txt` — `PySide6`, `pyte`, plus the PTY backend for the platform
(`pywinpty` on Windows, `ptyprocess` elsewhere; both are guarded by an
environment marker, so `pip install -r requirements.txt` installs only the
right one).

### Linux specifics

- **Desktop entry** — `./packaging/install-desktop.sh` adds TaskPilot to the
  application menu (and installs the icon) for the current user. It targets
  `dist/TaskPilot` if you built it, `start.sh` otherwise.
- **Optional tools** — the *Process* tab reads `/proc` directly, so no external
  tool is needed for the process list. Listening ports come from `ss`
  (iproute2, present on every mainstream distribution) with `lsof` as a
  fallback; without either, the *Port* column stays empty and nothing else is
  affected. `xdg-open` powers *Open the logs folder* / *Open the project
  folder*, and `notify-send` (libnotify) the notifications under GNOME.
- **Fonts** — the defaults are per-platform lists of fallbacks (Cantarell, Noto
  Sans, DejaVu Sans… for the UI; JetBrains Mono, Noto Sans Mono, DejaVu Sans
  Mono… for consoles): the first family actually installed wins. Override them
  in *Appearance ▸ Font*.

## Building the standalone executable

```sh
build.bat               # Windows -> dist\TaskPilot.exe   (PyInstaller, taskpilot.spec)
./build.sh              # Unix    -> dist/TaskPilot        (same spec)
```

The binary is self-contained (PySide6 + the platform PTY + `pyte` bundled in),
no installation required on the user's side. `taskpilot.spec` collects only the
PTY backend of the machine it builds on.

Every push to `master` publishes a release with **four assets**
(`.github/workflows/build-release.yml`): the app and the logs MCP server (see
below), each for Windows and Linux. They are built in separate jobs with
disjoint dependencies — neither carries the other's weight. A `portability` job
runs first on Linux: it byte-compiles the project and exercises the platform
layer (PTY backend resolvable, shells detected, process inventory non-empty),
so a Windows-only regression fails the build instead of shipping.

## Logs MCP server

A small read-only [MCP](https://modelcontextprotocol.io) server lets an AI
assistant (Zed, Claude Code…) inspect the current session's logs. It is **not**
integrated into the application: it is launched over stdio by the client *on
demand*, which acts as an on/off switch — present in the client config = active,
removed = inactive. No option in TaskPilot, no open port, nothing running
permanently.

The logs directory is resolved exactly as in the app (see `Config.log_dir`,
default `%TEMP%\taskpilot-logs`). Exposed tools: `list_logs`, `read_log`,
`tail_log`, `search_logs` (literal or regex).

### Install it: `TaskPilotMcp.exe` (recommended)

The MCP server ships as its **own asset**, separate from the application: every
push to `master` publishes `TaskPilotMcp.exe` alongside `TaskPilot.exe` (see
*Releases*). It is self-contained — no Python, no `mcp` SDK, no `PYTHONPATH` —
and carries none of the Qt stack (~17 MB against ~50 MB for the app).

Download it anywhere, then declare it in **Zed**'s `settings.json`:

```json
{
  "context_servers": {
    "taskpilot-logs": {
      "command": "C:\\path\\to\\TaskPilotMcp.exe",
      "args": []
    }
  }
}
```

The two executables are independent: you can use the MCP server without ever
installing the app (the logs directory is read from `~/.taskpilot.json`, falling
back to `%TEMP%\taskpilot-logs`).

> In Zed's *Add MCP Server* dialog, paste only the `"taskpilot-logs": { … }`
> entry (a single key/value pair, without the `context_servers` wrapper). When
> editing `settings.json` by hand, keep the full wrapper shown above.

### Run it from the sources instead

```sh
py -V:3.13 -m pip install -r requirements-mcp.txt   # the `mcp` SDK (Python ≥ 3.10)
py -V:3.13 -m taskpilot.mcp                          # manual launch (debug)
```

The corresponding client declaration needs the interpreter **≥ 3.10** that has
the `mcp` SDK (`py -V:3.13 -c "import sys; print(sys.executable)"` to find it),
plus `PYTHONPATH` pointing at the **repository root** so that `-m taskpilot.mcp`
resolves:

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

> `requirements-mcp.txt` pins `mcp<2`: the 2.0 SDK removed `mcp.server.fastmcp`
> (`FastMCP` became `MCPServer` in `mcp.server.mcpserver`). Lifting the pin
> requires porting `taskpilot/mcp/__main__.py` to the new API.

### Build it yourself

```sh
build-mcp.bat            # Windows -> dist\TaskPilotMcp.exe
./build-mcp.sh           # Unix    -> dist/TaskPilotMcp
```

Both then check the stdio handshake before declaring success.

`tools/smoke_mcp.py` replays a real client exchange (`initialize`, `tools/list`,
a `list_logs` call) against the produced binary. CI runs it before publishing:
a frozen server can build cleanly yet die on startup, and stdio gives no other
signal.

## Architecture

Strict separation between business logic and presentation:

```
taskpilot/
├── config.py            Persistence of the user config (~/.taskpilot.json)
├── core/                Business logic — NO dependency on the UI
│   ├── system.py        Platform layer: spawn flags, shells, kill, fonts, opener
│   ├── pty_backend.py   Uniform PTY (ConPTY/pywinpty vs Unix/ptyprocess)
│   ├── processes.py     Detection / kill of Node processes (NodeProcess model)
│   ├── jobobject.py     Windows Job Object (tree kill via ctypes)
│   ├── vscode_tasks.py  tasks.json parsing + CommandSpec / TaskNode models
│   └── task_runner.py   TaskConsole: process + output capture + kill
├── mcp/                 Logs MCP server (read-only, launched separately)
└── qt/                  Presentation (PySide6 / Qt)
    ├── assets.py        Embedded resources (application icon)
    ├── theme.py         Palettes, QSS, live theme switching
    ├── main_window.py   Main window, menus, status bar
    ├── tasks_tab.py     Tasks tab
    ├── process_tab.py   Process tab
    ├── console_view.py  Read-only console of a task
    ├── find_bar.py      Console search bar (Ctrl+F)
    ├── overlays.py      Layered ExtraSelection highlights (find/lines/hover)
    ├── syntax.py        JSON/YAML/XML detection in the output (spans)
    └── terminal_view.py Interactive terminal (pyte VT emulator + PTY)
```

The `core` layer is testable and reusable independently of the UI: it
communicates with the UI only through plain objects (dataclasses) and a
`queue.Queue` for the console output stream.

Platform differences are concentrated in **`core/system.py`** (and, for the two
cases too large to fit there, `core/pty_backend.py` and the per-OS backends of
`core/processes.py`). No other module tests the OS: porting to a new platform
means extending those three files, not hunting for `if IS_WIN` across the
codebase.
