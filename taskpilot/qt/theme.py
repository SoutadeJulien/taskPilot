"""Themes (palettes) et feuille de style (QSS) du POC Qt.

Chaque theme est une ``Palette`` (jeu de tokens de couleur). Le theme actif est
« installe » dans les attributs de module (``theme.ACCENT``, ``theme.SURFACE``…)
pour que tout le reste du code continue d'y acceder simplement ; changer de
theme reinstalle ces attributs, reconstruit le QSS et **emet ``notifier.changed``**
pour que les composants a style « inline » se rafraichissent a chaud.

Philosophie visuelle : separation par l'ELEVATION (niveaux de fond) et l'ESPACE
plutot que par des bordures ; arrondis reserves aux controles.
"""

from dataclasses import dataclass, fields

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QColor, QPalette


# ---------------------------------------------------------------------------
# Modele d'un theme
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Palette:
    name: str
    APP_BG: str
    SURFACE: str
    SURFACE_2: str
    SURFACE_3: str
    ALT_ROW: str
    BORDER: str
    FG: str
    FG_DIM: str
    MUTED: str
    CONSOLE_BG: str
    CONSOLE_HEAD: str
    CONSOLE_PROMPT: str
    LV_ERROR: str
    LV_WARN: str
    LV_INFO: str
    LV_SUCCESS: str
    ACCENT: str
    ACCENT_HOVER: str
    ACCENT_FG: str
    RED: str
    RED_HOVER: str
    DOT_RUNNING: str
    DOT_IDLE: str
    SELECTION: str


THEMES = {
    "Ardoise indigo": Palette(
        name="Ardoise indigo",
        APP_BG="#1f242c", SURFACE="#272d36", SURFACE_2="#313844",
        SURFACE_3="#3c4350", ALT_ROW="#2c323b", BORDER="#414956",
        FG="#e8ebf1", FG_DIM="#b2b9c5", MUTED="#838c9a",
        CONSOLE_BG="#171a20", CONSOLE_HEAD="#2b313b", CONSOLE_PROMPT="#8fd9ad",
        LV_ERROR="#ef8585", LV_WARN="#e4c279", LV_INFO="#7fb9e6",
        LV_SUCCESS="#76cba0",
        ACCENT="#7c8cf8", ACCENT_HOVER="#909dfb", ACCENT_FG="#0d1130",
        RED="#e87078", RED_HOVER="#f0858c",
        DOT_RUNNING="#4fd067", DOT_IDLE="#69707d", SELECTION="#39426a"),

    "Nuit teal": Palette(
        name="Nuit teal",
        APP_BG="#181c22", SURFACE="#1f242b", SURFACE_2="#29303a",
        SURFACE_3="#353d48", ALT_ROW="#242a32", BORDER="#39424d",
        FG="#e6eaef", FG_DIM="#aab3bf", MUTED="#7c8693",
        CONSOLE_BG="#12151a", CONSOLE_HEAD="#232a33", CONSOLE_PROMPT="#7fd6c0",
        LV_ERROR="#ef8585", LV_WARN="#e4c279", LV_INFO="#7fb9e6",
        LV_SUCCESS="#76cba0",
        ACCENT="#3fb6b6", ACCENT_HOVER="#52c8c8", ACCENT_FG="#04211f",
        RED="#e87078", RED_HOVER="#f0858c",
        DOT_RUNNING="#4fd067", DOT_IDLE="#69707d", SELECTION="#1f4a48"),

    "Ambre sombre": Palette(
        name="Ambre sombre",
        APP_BG="#211f1c", SURFACE="#2a2723", SURFACE_2="#34302a",
        SURFACE_3="#403b33", ALT_ROW="#2e2b26", BORDER="#463f36",
        FG="#ece8e1", FG_DIM="#c1b8aa", MUTED="#908676",
        CONSOLE_BG="#1a1814", CONSOLE_HEAD="#2d2a24", CONSOLE_PROMPT="#a8c98a",
        LV_ERROR="#e88a7a", LV_WARN="#e0bd72", LV_INFO="#8bb6d6",
        LV_SUCCESS="#9cc47a",
        ACCENT="#e0a64e", ACCENT_HOVER="#edb863", ACCENT_FG="#231605",
        RED="#e07a6a", RED_HOVER="#ec8d7d",
        DOT_RUNNING="#6cc24a", DOT_IDLE="#7a7163", SELECTION="#4a3a1c"),

    "Brouillard clair": Palette(
        name="Brouillard clair",
        APP_BG="#2b3038", SURFACE="#333944", SURFACE_2="#3d4450",
        SURFACE_3="#49515e", ALT_ROW="#383f4a", BORDER="#515a68",
        FG="#eef1f5", FG_DIM="#c3cad4", MUTED="#99a2b0",
        CONSOLE_BG="#20242b", CONSOLE_HEAD="#373e49", CONSOLE_PROMPT="#92ddb0",
        LV_ERROR="#f09090", LV_WARN="#e8c884", LV_INFO="#8cc0ee",
        LV_SUCCESS="#84d2ab",
        ACCENT="#5b9ef0", ACCENT_HOVER="#71acf4", ACCENT_FG="#07142e",
        RED="#e8727a", RED_HOVER="#f0878e",
        DOT_RUNNING="#54d06b", DOT_IDLE="#7e8794", SELECTION="#34466e"),
}

DEFAULT_THEME = "Ardoise indigo"

# -- Constantes independantes du theme --------------------------------------
GROUP_COLORS = ("#6fa8d6", "#d6b36a", "#c98fd0", "#7bc0c0", "#d07a7a", "#9ec46a")
PROJECT_PALETTE = ("#3b9eff", "#3fb950", "#f0b400", "#f85149", "#bf5af2",
                   "#1abc9c", "#56d364", "#ff7b29", "#6e7bf2", "#ff5fa8")
MONO_FAMILY = "Cascadia Mono, Consolas"
MONO_SIZE = 10

#: Entrees ANSI colorees (semantiques) communes a tous les themes ; le noir et
#: le blanc sont derives du theme (fond console / texte).
_ANSI_BASE = {
    "red": "#e87078", "green": "#8fd9ad", "brown": "#e4c279", "blue": "#7fb9e6",
    "magenta": "#c98fd0", "cyan": "#7bc0c0",
    "brightred": "#f0858c", "brightgreen": "#9fe2bd", "brightbrown": "#ecd194",
    "brightblue": "#9ccbef", "brightmagenta": "#dba8e0", "brightcyan": "#9ad6d6",
    "brightwhite": "#ffffff",
}


# ---------------------------------------------------------------------------
# Notifieur de changement de theme (pour le live-switch)
# ---------------------------------------------------------------------------
class _Notifier(QObject):
    changed = Signal()


notifier = _Notifier()


# ---------------------------------------------------------------------------
# Helpers couleur
# ---------------------------------------------------------------------------
def _lighten(hexstr, amt):
    """Eclaircit une couleur ``#rrggbb`` vers le blanc (``amt`` dans [0,1])."""
    h = hexstr.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    r = min(255, int(r + (255 - r) * amt))
    g = min(255, int(g + (255 - g) * amt))
    b = min(255, int(b + (255 - b) * amt))
    return f"#{r:02x}{g:02x}{b:02x}"


def ansi_colors(pal=None):
    pal = pal or current
    d = dict(_ANSI_BASE)
    d["black"] = pal.CONSOLE_BG
    d["white"] = pal.FG
    d["brightblack"] = pal.MUTED
    return d


# ---------------------------------------------------------------------------
# Construction du QSS et de la QPalette pour un theme
# ---------------------------------------------------------------------------
def build_qss(pal):
    APP_BG, SURFACE, SURFACE_2, SURFACE_3 = (
        pal.APP_BG, pal.SURFACE, pal.SURFACE_2, pal.SURFACE_3)
    ALT_ROW, FG, FG_DIM, MUTED = pal.ALT_ROW, pal.FG, pal.FG_DIM, pal.MUTED
    CONSOLE_BG, ACCENT, ACCENT_FG = pal.CONSOLE_BG, pal.ACCENT, pal.ACCENT_FG
    ACCENT_HOVER, RED, SELECTION = pal.ACCENT_HOVER, pal.RED, pal.SELECTION
    scroll = SURFACE_3
    scroll_hover = _lighten(SURFACE_3, 0.18)
    check_hover = _lighten(SURFACE_3, 0.12)
    return f"""
* {{ font-family: "Segoe UI"; font-size: 13px; color: {FG}; }}
QMainWindow, QWidget {{ background: {APP_BG}; }}
QToolTip {{
    background: {SURFACE_3}; color: {FG};
    border: none; border-radius: 7px; padding: 6px 9px;
}}

QMenuBar {{ background: {APP_BG}; color: {FG_DIM}; padding: 4px 6px; }}
QMenuBar::item {{ padding: 6px 13px; border-radius: 7px; background: transparent; }}
QMenuBar::item:selected {{ background: {SURFACE_2}; color: {FG}; }}
QMenu {{ background: {SURFACE_2}; border: none; border-radius: 9px; padding: 4px; }}
QMenu::item {{ padding: 5px 22px 5px 18px; border-radius: 6px; }}
QMenu::item:selected {{ background: {ACCENT}; color: {ACCENT_FG}; }}
QMenu::item:disabled {{ color: {MUTED}; }}
QMenu::separator {{ height: 1px; background: {SURFACE_3}; margin: 4px 8px; }}
QMenu::icon {{ padding-left: 6px; }}

QTabWidget::pane {{ border: none; background: {SURFACE}; }}
QTabBar {{ qproperty-drawBase: 0; background: transparent; }}
QTabBar::tab {{
    background: transparent; color: {MUTED};
    padding: 6px 15px; margin-right: 3px; border: none;
    border-top-left-radius: 9px; border-top-right-radius: 9px;
}}
QTabBar::tab:hover {{ color: {FG}; background: {SURFACE}; }}
QTabBar::tab:selected {{ background: {SURFACE}; color: {FG}; border-top: 2px solid {ACCENT}; }}

QTabWidget#consoleTabs QTabBar::tab {{
    padding: 5px 11px; margin-right: 2px; font-size: 12px;
    border-top-left-radius: 8px; border-top-right-radius: 8px;
}}
QTabWidget#consoleTabs QTabBar::tab:selected {{ border-top: 2px solid {ACCENT}; }}

QPushButton {{
    background: {SURFACE_2}; border: none; border-radius: 8px;
    padding: 6px 13px; color: {FG};
}}
QPushButton:hover {{ background: {SURFACE_3}; }}
QPushButton:pressed {{ background: {SURFACE}; }}
QPushButton:disabled {{ color: {MUTED}; background: {SURFACE}; }}
QPushButton[accent="true"] {{ background: {ACCENT}; color: {ACCENT_FG}; font-weight: 600; }}
QPushButton[accent="true"]:hover {{ background: {ACCENT_HOVER}; }}
QPushButton[accent="true"]:disabled {{ background: {SURFACE}; color: {MUTED}; }}
QPushButton[danger="true"] {{ background: {SURFACE_2}; color: {RED}; }}
QPushButton[danger="true"]:hover {{ background: {RED}; color: {ACCENT_FG}; }}
QPushButton[danger="true"]:disabled {{ background: {SURFACE}; color: {MUTED}; }}

QComboBox, QLineEdit {{
    background: {SURFACE_2}; border: 1px solid transparent;
    border-radius: 8px; padding: 6px 11px; selection-background-color: {ACCENT};
}}
QComboBox:hover, QLineEdit:hover {{ background: {SURFACE_3}; }}
QComboBox:focus, QLineEdit:focus {{ border: 1px solid {ACCENT}; }}
QComboBox::drop-down {{ border: none; width: 26px; }}
QComboBox::down-arrow {{ width: 11px; height: 11px; }}
QComboBox QAbstractItemView {{
    background: {SURFACE_2}; border: none; border-radius: 9px; padding: 5px;
    selection-background-color: {ACCENT}; selection-color: {ACCENT_FG}; outline: 0;
}}

/* Carte arrondie enveloppant la liste des tasks (coins ronds sans encoche :
   c'est la carte qui porte le rayon, l'arbre est en retrait dedans). */
QFrame#taskCard {{ background: {SURFACE}; border-radius: 12px; }}

QTreeWidget, QTreeView, QListWidget {{
    background: {SURFACE}; border: none;
    alternate-background-color: {ALT_ROW}; outline: 0; show-decoration-selected: 1;
}}
QTreeView::item, QTreeWidget::item, QListWidget::item {{
    padding: 5px 3px; border: none; border-radius: 6px;
}}
QTreeView::item:hover, QTreeWidget::item:hover, QListWidget::item:hover {{ background: {SURFACE_2}; }}
QTreeView::item:selected, QTreeWidget::item:selected, QListWidget::item:selected {{
    background: {SELECTION}; color: {FG};
}}
QHeaderView::section {{
    background: {SURFACE}; color: {MUTED};
    padding: 9px 10px; border: none; font-weight: 600;
}}
QHeaderView::section:hover {{ color: {FG}; }}

QPlainTextEdit {{
    background: {CONSOLE_BG}; border: none; color: {FG};
    selection-background-color: {ACCENT}; selection-color: {ACCENT_FG};
}}

QCheckBox {{ spacing: 8px; padding: 3px; }}
QCheckBox::indicator {{
    width: 15px; height: 15px; border-radius: 5px; border: none; background: {SURFACE_3};
}}
QCheckBox::indicator:hover {{ background: {check_hover}; }}
QCheckBox::indicator:checked {{ background: {ACCENT}; }}

QScrollBar:vertical {{ background: transparent; width: 13px; margin: 3px; }}
QScrollBar::handle:vertical {{ background: {scroll}; border-radius: 5px; min-height: 32px; }}
QScrollBar::handle:vertical:hover {{ background: {scroll_hover}; }}
QScrollBar:horizontal {{ background: transparent; height: 13px; margin: 3px; }}
QScrollBar::handle:horizontal {{ background: {scroll}; border-radius: 5px; min-width: 32px; }}
QScrollBar::handle:horizontal:hover {{ background: {scroll_hover}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

QSplitter::handle {{ background: transparent; }}
QSplitter::handle:horizontal {{ width: 18px; }}
QLabel {{ background: transparent; }}
QStatusBar {{ background: {APP_BG}; color: {MUTED}; }}
QStatusBar::item {{ border: none; }}
"""


def build_palette(pal=None):
    """QPalette sombre coherente avec ``pal`` (couvre ce que le QSS n'atteint
    pas : zone branche des arbres, surbrillances natives, flashs clairs)."""
    pal = pal or current
    p = QPalette()
    p.setColor(QPalette.Window, QColor(pal.APP_BG))
    p.setColor(QPalette.WindowText, QColor(pal.FG))
    p.setColor(QPalette.Base, QColor(pal.SURFACE))
    p.setColor(QPalette.AlternateBase, QColor(pal.ALT_ROW))
    p.setColor(QPalette.Text, QColor(pal.FG))
    p.setColor(QPalette.Button, QColor(pal.SURFACE_2))
    p.setColor(QPalette.ButtonText, QColor(pal.FG))
    p.setColor(QPalette.ToolTipBase, QColor(pal.SURFACE_3))
    p.setColor(QPalette.ToolTipText, QColor(pal.FG))
    p.setColor(QPalette.PlaceholderText, QColor(pal.MUTED))
    p.setColor(QPalette.Highlight, QColor(pal.SELECTION))
    p.setColor(QPalette.HighlightedText, QColor(pal.FG))
    p.setColor(QPalette.Link, QColor(pal.ACCENT))
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        p.setColor(QPalette.Disabled, role, QColor(pal.MUTED))
    return p


# ---------------------------------------------------------------------------
# Installation du theme actif (met a jour les attributs de module + QSS)
# ---------------------------------------------------------------------------
def _install(pal):
    """Recopie les tokens de ``pal`` dans les attributs de module + alias + QSS."""
    g = globals()
    for f in fields(Palette):
        if f.name != "name":
            g[f.name] = getattr(pal, f.name)
    g["BG"] = pal.APP_BG
    g["BG_ALT"] = pal.SURFACE
    g["HEAD"] = pal.SURFACE_2
    g["CONSOLE_BORDER"] = pal.BORDER
    g["ANSI_COLORS"] = ansi_colors(pal)
    g["QSS"] = build_qss(pal)
    g["current"] = pal


def set_theme(name):
    """Installe le theme ``name`` (sans toucher a l'application Qt)."""
    pal = THEMES.get(name) or THEMES[DEFAULT_THEME]
    _install(pal)
    return pal


def apply_theme(app, name):
    """Applique le theme ``name`` a une ``QApplication`` (live-switch)."""
    set_theme(name)
    app.setPalette(build_palette())
    app.setStyleSheet(QSS)
    notifier.changed.emit()


# Theme par defaut installe au chargement du module.
current = None
set_theme(DEFAULT_THEME)
