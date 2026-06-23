"""Onglet Process : arbre des process des tasks, surveillance et destruction.

On affiche, groupé par task, l'intégralité de l'arbre de process lancé par
chaque console (quel que soit l'exécutable : node, python, npm, shell…) — pas
seulement les process Node.
"""

import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox

from taskpilot.core.processes import (
    find_processes, format_memory, kill_process)
from taskpilot.core.system import NCPU
from taskpilot.ui import theme
from taskpilot.ui.rounded import RoundedFrame
from taskpilot.ui.widgets import make_button

REFRESH_MS = 1500
#: Libelle du groupe des process Node non rattaches a une task en cours.
ORPHAN_LABEL = "Node (hors tasks)"
COLUMNS = ("port", "pid", "cpu", "mem", "cmd")
HEADINGS = {"port": "Port", "pid": "PID", "cpu": "CPU %",
            "mem": "Mémoire", "cmd": "Ligne de commande"}


class ProcessTab(ttk.Frame):
    """Tableau temps reel des process Node, avec tri et kill d'arbre."""

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self._items = {}             # pid -> {"item_id", "proc"}
        self._task_items = {}        # label de task -> item_id (ligne parent)
        self._prev_cpu = {}          # pid -> (cpu_time, timestamp)
        self._after_id = None
        self._sort_col = "cpu"
        self._sort_reverse = True
        self._loading = False
        self._flash = None
        self._activated = False      # collecte demarree au 1er affichage (lazy)

        self._build_toolbar()
        self._build_table()
        self._build_statusbar()

    # -- Construction de l'UI ------------------------------------------------
    def _build_toolbar(self):
        bar = tk.Frame(self, bg=theme.BG)
        bar.pack(fill="x", padx=10, pady=(10, 6))
        make_button(bar, "↻  Rafraîchir", self.refresh).pack(side="left")
        make_button(bar, "✕  Tuer la sélection", self.kill_selected).pack(
            side="left", padx=6)
        make_button(bar, "⊗  Tuer TOUS", self.kill_all,
                    danger=True).pack(side="left")

        self.live = tk.BooleanVar(value=True)
        tk.Checkbutton(
            bar, text="◷  Temps réel", variable=self.live,
            command=self._on_live_toggle,
            bg=theme.BG, fg=theme.FG, selectcolor=theme.HEAD,
            activebackground=theme.BG, activeforeground=theme.FG,
            font=theme.FONT_UI).pack(side="left", padx=(14, 0))

    def _build_table(self):
        card = RoundedFrame(self, bg=theme.BG, border=theme.CONSOLE_BORDER,
                            inset=10)
        card.pack(fill="both", expand=True, padx=10, pady=(0, 6))
        container = card.inner
        container.rowconfigure(0, weight=1)
        container.columnconfigure(0, weight=1)

        self.tree = ttk.Treeview(container, columns=COLUMNS,
                                 show="tree headings", selectmode="extended")
        for col, label in HEADINGS.items():
            self.tree.heading(col, text=label,
                              command=lambda c=col: self._sort_by(c))
        self.tree.heading("#0", text="Task")
        self.tree.column("#0", width=200, minwidth=120, stretch=False,
                         anchor="w")
        self.tree.column("port", width=80, minwidth=60, stretch=False, anchor="e")
        self.tree.column("pid", width=80, minwidth=60, stretch=False, anchor="e")
        self.tree.column("cpu", width=80, minwidth=60, stretch=False, anchor="e")
        self.tree.column("mem", width=100, minwidth=70, stretch=False, anchor="e")
        self.tree.column("cmd", width=480, minwidth=200, stretch=True, anchor="w")
        self.tree.tag_configure("odd", background=theme.BG)
        self.tree.tag_configure("even", background=theme.BG_ALT)
        self.tree.tag_configure("task", background=theme.HEAD, foreground=theme.FG)

        scroll = ttk.Scrollbar(container, orient="vertical",
                               command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")

    def _build_statusbar(self):
        self.status = tk.Label(self, text="", anchor="w", bg=theme.HEAD,
                               fg=theme.FG, font=theme.FONT_UI, padx=10, pady=4)
        self.status.pack(fill="x", side="bottom")

    def on_shown(self):
        """Demarre la collecte au premier affichage de l'onglet (lazy).

        Evite de lancer les sous-process de listing (lourds) au demarrage de
        l'application si l'utilisateur reste sur l'onglet Tasks.
        """
        if self._activated:
            return
        self._activated = True
        self.refresh()
        self._on_live_toggle()

    # -- Collecte (thread) ---------------------------------------------------
    def refresh(self):
        if self._loading:
            return
        self._loading = True
        # Les racines sont lues ici (thread UI) : elles touchent aux consoles.
        roots = self.app.tasks_tab.running_task_roots()
        threading.Thread(target=self._worker, args=(roots,),
                         daemon=True).start()

    def _worker(self, roots):
        try:
            procs, err = find_processes(roots), None
        except Exception as e:  # noqa: BLE001
            procs, err = None, e
        self.after(0, self._render, procs, err)

    def _compute_cpu(self, procs):
        now = time.time()
        for p in procs:
            p.cpu = None
            if p.cpu_time is not None:
                prev = self._prev_cpu.get(p.pid)
                if prev:
                    prev_time, prev_ts = prev
                    dt = now - prev_ts
                    if dt > 0:
                        p.cpu = max(0.0,
                                    (p.cpu_time - prev_time) / dt / NCPU * 100.0)
                self._prev_cpu[p.pid] = (p.cpu_time, now)
        live = {p.pid for p in procs}
        for pid in list(self._prev_cpu):
            if pid not in live:
                self._prev_cpu.pop(pid, None)

    # -- Rendu ---------------------------------------------------------------
    def _render(self, procs, err):
        self._loading = False
        if err is not None:
            if self.live.get():
                self.status.config(text=f"⚠ Erreur : {err}")
            else:
                messagebox.showerror(
                    "Erreur", f"Impossible de lister les process :\n{err}")
            return

        self._compute_cpu(procs)

        # Regroupement par task, en conservant l'ordre d'apparition.
        by_task, order = {}, []
        for p in procs:
            if p.task not in by_task:
                by_task[p.task] = []
                order.append(p.task)
            by_task[p.task].append(p)

        # Retire les process disparus, puis les lignes de task devenues vides.
        current = {p.pid for p in procs}
        for pid in list(self._items):
            if pid not in current:
                self._safe_delete(self._items.pop(pid)["item_id"])
        for label in list(self._task_items):
            if label not in by_task:
                self._safe_delete(self._task_items.pop(label))

        # (Re)crée les lignes parentes (tasks) et leurs process enfants.
        for label in order:
            parent = self._task_items.get(label)
            if parent is None or not self.tree.exists(parent):
                display = label if label is not None else ORPHAN_LABEL
                parent = self.tree.insert(
                    "", "end", text=f"  {display}", open=True,
                    image=self.app.node_icon, tags=("task",))
                self._task_items[label] = parent
            for p in by_task[label]:
                vals = self._row_values(p)
                entry = self._items.get(p.pid)
                if entry and self.tree.exists(entry["item_id"]):
                    self.tree.item(entry["item_id"], values=vals)
                    if self.tree.parent(entry["item_id"]) != parent:
                        self.tree.move(entry["item_id"], parent, "end")
                else:
                    entry = {"item_id": self.tree.insert(parent, "end",
                                                         values=vals)}
                entry["proc"] = p
                self._items[p.pid] = entry

        self._apply_sort()
        self._update_status(procs, len(order))

    def _safe_delete(self, item_id):
        try:
            self.tree.delete(item_id)
        except tk.TclError:
            pass

    @staticmethod
    def _row_values(p):
        if p.cpu is None:
            cpu = "-"
        elif 0 < p.cpu < 0.01:
            cpu = "<0.01"
        else:
            cpu = f"{p.cpu:.2f}"
        port = ", ".join(str(x) for x in p.ports) if p.ports else "-"
        return (port, p.pid, cpu, format_memory(p.mem), p.cmd)

    def _update_status(self, procs, ntasks):
        if not procs and not self._flash:
            self.status.config(
                text="  Aucun process Node détecté sur la machine.")
            return
        total_mem = sum(p.mem for p in procs)
        total_cpu = sum(p.cpu for p in procs if p.cpu is not None)
        text = (f"  {len(procs)} process   •   {ntasks} groupe(s)"
                f"   •   CPU total ≈ {total_cpu:.1f} %"
                f"   •   Mémoire totale {format_memory(total_mem)}")
        if self._flash:
            text = f"  {self._flash}   —  {text.strip()}"
            self._flash = None
        self.status.config(text=text)

    # -- Tri -----------------------------------------------------------------
    def _sort_by(self, col):
        if self._sort_col == col:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_col = col
            self._sort_reverse = col in ("cpu", "mem")
        self._apply_sort()

    def _apply_sort(self):
        col = self._sort_col

        def key(pid):
            p = self._items[pid]["proc"]
            if col == "port":
                return p.ports[0] if p.ports else -1
            if col == "pid":
                return p.pid
            if col == "cpu":
                return p.cpu or -1
            if col == "mem":
                return p.mem or -1
            return str(p.cmd).lower()

        # Tri appliqué indépendamment aux enfants de chaque task.
        kids_by_parent = {}
        for pid, entry in self._items.items():
            parent = self.tree.parent(entry["item_id"])
            kids_by_parent.setdefault(parent, []).append(pid)
        for parent, pids in kids_by_parent.items():
            for idx, pid in enumerate(sorted(pids, key=key,
                                             reverse=self._sort_reverse)):
                item_id = self._items[pid]["item_id"]
                self.tree.move(item_id, parent, idx)
                self.tree.item(item_id, tags=("even" if idx % 2 else "odd",))

        for col_, base in HEADINGS.items():
            mark = ("  ▼" if self._sort_reverse else "  ▲") if col_ == col else ""
            self.tree.heading(col_, text=base + mark)

    # -- Temps reel ----------------------------------------------------------
    def _on_live_toggle(self):
        if self._after_id is not None:
            self.after_cancel(self._after_id)
            self._after_id = None
        if self.live.get():
            self._tick()

    def _tick(self):
        self.refresh()
        if self.live.get():
            self._after_id = self.after(REFRESH_MS, self._tick)

    # -- Kill ----------------------------------------------------------------
    def _selected_pids(self):
        pids = []
        parents = set(self._task_items.values())
        for item in self.tree.selection():
            # Sélectionner une ligne de task vise tous ses process enfants.
            targets = self.tree.get_children(item) if item in parents else (item,)
            for it in targets:
                vals = self.tree.item(it, "values")
                if vals and str(vals[1]).isdigit():
                    pids.append(int(vals[1]))
        return pids

    def kill_selected(self):
        pids = self._selected_pids()
        if not pids:
            messagebox.showinfo("Info", "Aucun process sélectionné.")
            return
        self._kill_pids(pids)

    def kill_all(self):
        pids = [pid for pid in self._items]
        if not pids:
            messagebox.showinfo("Info", "Aucun process Node à tuer.")
            return
        if not messagebox.askyesno(
                "Confirmer",
                f"Tuer les {len(pids)} process Node listés ?"):
            return
        self._kill_pids(pids)

    def _kill_pids(self, pids):
        ok = sum(kill_process(pid) for pid in pids)
        failed = len(pids) - ok
        msg = f"{ok} process tué(s)."
        if failed:
            msg += f" {failed} échec(s) (droits insuffisants ?)."
        self._flash = msg
        self.refresh()
