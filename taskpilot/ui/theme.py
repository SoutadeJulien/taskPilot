"""Palette de couleurs, polices et application du theme ttk."""

import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

# -- Palette ----------------------------------------------------------------
BG = "#1e1e1e"
BG_ALT = "#252526"
FG = "#d4d4d4"
HEAD = "#2d2d30"
SEL = "#37506b"

# Console : fond plus profond + barre de titre dediee + cadre, pour la
# detacher nettement du reste de l'interface.
CONSOLE_BG = "#121212"
CONSOLE_HEAD = "#202124"
CONSOLE_BORDER = "#3a3a40"
# Barre d'en-tete du panneau Consoles (titre + actions groupees), facon liste.
CONSOLE_BAR = "#262626"
CONSOLE_PROMPT = "#7cba96"   # lignes "$ commande"
CONSOLE_MUTED = "#8a8a8a"    # texte secondaire (terminé, etc.)

# Onglets facon terminal (haut arrondi, bandeau serre).
CONSOLE_TAB_IDLE = "#191919"
CONSOLE_TAB_SEL = "#33333b"   # nettement plus clair = onglet actif bien visible

# Coloriage par niveau de log (heuristique sur le contenu de la ligne).
CONSOLE_ERROR = "#e07a7a"
CONSOLE_WARN = "#d6b36a"
CONSOLE_INFO = "#6fa8d6"
CONSOLE_SUCCESS = "#6aa884"

# Vert adouci (au lieu du vert lime trop vif)
ACCENT = "#6aa884"
ACCENT_HOVER = "#7cba96"
ACCENT_FG = "#0e1a14"

# Boutons neutres
BTN = "#34343a"
BTN_HOVER = "#41414a"

# Rouge adouci
RED = "#d07a7a"
RED_HOVER = "#dd8a8a"

# Pastilles d'etat dans la liste des tasks (vert = en cours, gris = au repos).
# Le vert alterne entre vif et attenue pour un effet de pulsation discret.
DOT_RUNNING = "#46c25a"
DOT_RUNNING_DIM = "#2c6e38"
DOT_IDLE = "#4a4a4a"

# Liste des tasks (tableau custom soude a son bouton d'action).
TASKLIST_BG = "#1c1c1c"          # fond des lignes
TASKLIST_HEAD = "#383838"        # bandeau d'en-tete (Task / Type)
TASKLIST_HEAD_FG = "#e0e0e0"
TASKLIST_HOVER = "#2a2a2a"       # survol d'une ligne
TASKLIST_SEL = "#33503c"         # ligne selectionnee (vert assombri)
TASKLIST_SEP = "#2a2a2a"         # filets (header, lignes)
TASKLIST_BORDER = "#3c3c3c"      # liseré du cadre (gris neutre, non bleute)
TYPE_FG = "#6f9c74"              # colonne Type (vert adouci)

# Couleurs de groupe : consoles issues d'une meme task composite (dependsOn).
# Cyclees dans l'ordre ; servent de barre verticale sur les onglets concernes.
GROUP_COLORS = ("#6fa8d6", "#d6b36a", "#c98fd0", "#7bc0c0", "#d07a7a", "#9ec46a")

# Bouton « Lancer la task » soude sous la liste (vert profond du design).
RUN_BG = "#2e5a3a"
RUN_HOVER = "#356a44"
RUN_FG = "#cdeccf"

# -- Geometrie / polices ----------------------------------------------------
BTN_RADIUS = 9
CARD_RADIUS = 12
TAB_RADIUS = 10
FONT_UI = ("Segoe UI", 9)
FONT_UI_BOLD = ("Segoe UI", 9, "bold")
FONT_MONO = ("Consolas", 9)
FONT_MONO_BOLD = ("Consolas", 9, "bold")

#: Cache des objets ``tkfont.Font`` partages (un par specification de police).
#: Evite de recreer un Font Tcl pour chaque bouton/onglet construit.
_FONT_CACHE = {}


def get_font(spec) -> tkfont.Font:
    """Retourne un ``tkfont.Font`` mis en cache pour la spec ``(family, size[, weight])``.

    A appeler une fois la racine Tk creee (les widgets sont construits apres).
    """
    key = tuple(spec)
    font = _FONT_CACHE.get(key)
    if font is None:
        font = tkfont.Font(
            family=spec[0], size=spec[1],
            weight=spec[2] if len(spec) > 2 else "normal")
        _FONT_CACHE[key] = font
    return font


def apply_theme(root: tk.Misc):
    """Applique le theme sombre a tous les widgets ttk de l'application."""
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    # Facteur DPI (1.0 a 100 %) pour les dimensions en pixels du theme : sans
    # cela, a 125 % la hauteur de ligne fixe tronquerait le texte agrandi.
    scaling = getattr(root, "scaling", 1.0)

    style.configure("Treeview", background=BG, fieldbackground=BG,
                    foreground=FG, rowheight=round(24 * scaling), borderwidth=0)
    style.configure("Treeview.Heading", background=HEAD, foreground=FG,
                    relief="flat", font=FONT_UI_BOLD)
    style.map("Treeview.Heading", background=[("active", "#3e3e42")])
    style.map("Treeview", background=[("selected", SEL)],
              foreground=[("selected", "#ffffff")])

    style.configure("TNotebook", background=BG, borderwidth=0)
    style.configure("TNotebook.Tab", background=HEAD, foreground=FG,
                    padding=(14, 6), font=FONT_UI_BOLD)
    style.map("TNotebook.Tab",
              background=[("selected", BG)],
              foreground=[("selected", ACCENT)])

    style.configure("TFrame", background=BG)
    style.configure("TPanedwindow", background=BG)

    # Combobox totalement aplati : la bordure visible est celle du RoundedFrame
    # qui l'enveloppe (voir TasksTab._build_top).
    style.configure("Flat.TCombobox", fieldbackground=BG_ALT, background=BG_ALT,
                    foreground=FG, arrowcolor=FG, relief="flat", borderwidth=0,
                    bordercolor=BG_ALT, lightcolor=BG_ALT, darkcolor=BG_ALT,
                    insertcolor=FG, padding=4)
    style.map("Flat.TCombobox",
              fieldbackground=[("readonly", BG_ALT), ("focus", BG_ALT)],
              background=[("readonly", BG_ALT), ("active", BG_ALT)],
              bordercolor=[("focus", BG_ALT), ("active", BG_ALT)],
              foreground=[("readonly", FG)],
              arrowcolor=[("active", ACCENT)])
    # Liste deroulante (widget Listbox sous-jacent, hors ttk).
    root.option_add("*TCombobox*Listbox.background", BG_ALT)
    root.option_add("*TCombobox*Listbox.foreground", FG)
    root.option_add("*TCombobox*Listbox.selectBackground", SEL)
    root.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")
    root.option_add("*TCombobox*Listbox.font", FONT_UI)
