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

    "Forêt émeraude": Palette(
        name="Forêt émeraude",
        APP_BG="#1a211c", SURFACE="#222b25", SURFACE_2="#2c372f",
        SURFACE_3="#37443a", ALT_ROW="#27322a", BORDER="#3a4940",
        FG="#e7efe9", FG_DIM="#aebcb2", MUTED="#7e8d83",
        CONSOLE_BG="#141a16", CONSOLE_HEAD="#26302a", CONSOLE_PROMPT="#8fd9ad",
        LV_ERROR="#ef8585", LV_WARN="#e4c279", LV_INFO="#7fb9e6",
        LV_SUCCESS="#76cba0",
        ACCENT="#4cc98a", ACCENT_HOVER="#62d79b", ACCENT_FG="#04200f",
        RED="#e87078", RED_HOVER="#f0858c",
        DOT_RUNNING="#4fd067", DOT_IDLE="#69707d", SELECTION="#1f4a33"),

    "Océan profond": Palette(
        name="Océan profond",
        APP_BG="#141a24", SURFACE="#1b2230", SURFACE_2="#243044",
        SURFACE_3="#2f3d54", ALT_ROW="#1f2838", BORDER="#324158",
        FG="#e4eaf2", FG_DIM="#a8b4c6", MUTED="#7a879b",
        CONSOLE_BG="#0f141d", CONSOLE_HEAD="#1f2838", CONSOLE_PROMPT="#84c9e6",
        LV_ERROR="#ef8585", LV_WARN="#e4c279", LV_INFO="#7fb9e6",
        LV_SUCCESS="#76cba0",
        ACCENT="#3d8bf0", ACCENT_HOVER="#549af3", ACCENT_FG="#04122e",
        RED="#e87078", RED_HOVER="#f0858c",
        DOT_RUNNING="#4fd067", DOT_IDLE="#69707d", SELECTION="#1d3a6a"),

    "Violet améthyste": Palette(
        name="Violet améthyste",
        APP_BG="#201c28", SURFACE="#292333", SURFACE_2="#342c42",
        SURFACE_3="#403650", ALT_ROW="#2e2738", BORDER="#473c58",
        FG="#ece8f3", FG_DIM="#beb4cc", MUTED="#8c8298",
        CONSOLE_BG="#181420", CONSOLE_HEAD="#2b2436", CONSOLE_PROMPT="#c3a8e0",
        LV_ERROR="#ef8585", LV_WARN="#e4c279", LV_INFO="#7fb9e6",
        LV_SUCCESS="#76cba0",
        ACCENT="#a771ee", ACCENT_HOVER="#b487f1", ACCENT_FG="#1c0a33",
        RED="#e87078", RED_HOVER="#f0858c",
        DOT_RUNNING="#4fd067", DOT_IDLE="#69707d", SELECTION="#3d2a5e"),

    "Vin grenat": Palette(
        name="Vin grenat",
        APP_BG="#241a1c", SURFACE="#2e2225", SURFACE_2="#3a2b2f",
        SURFACE_3="#46353a", ALT_ROW="#322629", BORDER="#4d3a3f",
        FG="#f1e7e9", FG_DIM="#ccb4b8", MUTED="#9a8286",
        CONSOLE_BG="#1a1315", CONSOLE_HEAD="#2d2225", CONSOLE_PROMPT="#e0a8b0",
        LV_ERROR="#ef8585", LV_WARN="#e4c279", LV_INFO="#7fb9e6",
        LV_SUCCESS="#76cba0",
        ACCENT="#e0556b", ACCENT_HOVER="#ea6c80", ACCENT_FG="#2e0a12",
        RED="#e87078", RED_HOVER="#f0858c",
        DOT_RUNNING="#4fd067", DOT_IDLE="#7a7163", SELECTION="#5e1f2e"),

    "Cuivre crépuscule": Palette(
        name="Cuivre crépuscule",
        APP_BG="#221d19", SURFACE="#2c2620", SURFACE_2="#372f28",
        SURFACE_3="#433931", ALT_ROW="#302a23", BORDER="#4a3e34",
        FG="#f0e8df", FG_DIM="#c8bba9", MUTED="#968a78",
        CONSOLE_BG="#191510", CONSOLE_HEAD="#2c2620", CONSOLE_PROMPT="#b8c98a",
        LV_ERROR="#e88a7a", LV_WARN="#e0bd72", LV_INFO="#8bb6d6",
        LV_SUCCESS="#9cc47a",
        ACCENT="#e08a4e", ACCENT_HOVER="#ed9d63", ACCENT_FG="#2a1305",
        RED="#e07a6a", RED_HOVER="#ec8d7d",
        DOT_RUNNING="#6cc24a", DOT_IDLE="#7a7163", SELECTION="#5a3520"),

    "Menthe glaciale": Palette(
        name="Menthe glaciale",
        APP_BG="#222a2c", SURFACE="#2a3436", SURFACE_2="#344042",
        SURFACE_3="#3f4d4f", ALT_ROW="#2f3b3d", BORDER="#475759",
        FG="#e8f1f0", FG_DIM="#bccac9", MUTED="#92a09f",
        CONSOLE_BG="#19201f", CONSOLE_HEAD="#2c3637", CONSOLE_PROMPT="#7fd6c0",
        LV_ERROR="#ef8585", LV_WARN="#e4c279", LV_INFO="#7fb9e6",
        LV_SUCCESS="#76cba0",
        ACCENT="#4fd1c5", ACCENT_HOVER="#65dad0", ACCENT_FG="#042421",
        RED="#e87078", RED_HOVER="#f0858c",
        DOT_RUNNING="#4fd067", DOT_IDLE="#69707d", SELECTION="#1f4a46"),

    "Graphite neutre": Palette(
        name="Graphite neutre",
        APP_BG="#1d1f22", SURFACE="#26282c", SURFACE_2="#303338",
        SURFACE_3="#3b3e44", ALT_ROW="#2a2d31", BORDER="#41454c",
        FG="#e9ebee", FG_DIM="#b6bac1", MUTED="#868b93",
        CONSOLE_BG="#16181b", CONSOLE_HEAD="#292c30", CONSOLE_PROMPT="#9fd6b3",
        LV_ERROR="#ef8585", LV_WARN="#e4c279", LV_INFO="#7fb9e6",
        LV_SUCCESS="#76cba0",
        ACCENT="#7d8aa3", ACCENT_HOVER="#909cb3", ACCENT_FG="#13161c",
        RED="#e87078", RED_HOVER="#f0858c",
        DOT_RUNNING="#4fd067", DOT_IDLE="#69707d", SELECTION="#3a3f47"),

    "Nord polaire": Palette(
        name="Nord polaire",
        APP_BG="#2b303b", SURFACE="#323845", SURFACE_2="#3b4252",
        SURFACE_3="#434c5e", ALT_ROW="#363d4a", BORDER="#4c566a",
        FG="#eceff4", FG_DIM="#d8dee9", MUTED="#7e879c",
        CONSOLE_BG="#242933", CONSOLE_HEAD="#353c4a", CONSOLE_PROMPT="#a3be8c",
        LV_ERROR="#bf616a", LV_WARN="#ebcb8b", LV_INFO="#81a1c1",
        LV_SUCCESS="#a3be8c",
        ACCENT="#88c0d0", ACCENT_HOVER="#9ad0de", ACCENT_FG="#1c2530",
        RED="#bf616a", RED_HOVER="#cf737c",
        DOT_RUNNING="#a3be8c", DOT_IDLE="#7e879c", SELECTION="#3b4a5e"),

    "Dracula": Palette(
        name="Dracula",
        APP_BG="#21222c", SURFACE="#282a36", SURFACE_2="#343746",
        SURFACE_3="#44475a", ALT_ROW="#2d2f3d", BORDER="#44475a",
        FG="#f8f8f2", FG_DIM="#cdcee0", MUTED="#6272a4",
        CONSOLE_BG="#1a1b23", CONSOLE_HEAD="#2b2d3a", CONSOLE_PROMPT="#50fa7b",
        LV_ERROR="#ff5555", LV_WARN="#f1fa8c", LV_INFO="#8be9fd",
        LV_SUCCESS="#50fa7b",
        ACCENT="#bd93f9", ACCENT_HOVER="#caa6fa", ACCENT_FG="#1d1130",
        RED="#ff5555", RED_HOVER="#ff6e6e",
        DOT_RUNNING="#50fa7b", DOT_IDLE="#6272a4", SELECTION="#44475a"),

    "Solarized sombre": Palette(
        name="Solarized sombre",
        APP_BG="#002b36", SURFACE="#073642", SURFACE_2="#0d4150",
        SURFACE_3="#14505f", ALT_ROW="#093b48", BORDER="#1a5666",
        FG="#93a1a1", FG_DIM="#839496", MUTED="#586e75",
        CONSOLE_BG="#00212b", CONSOLE_HEAD="#073642", CONSOLE_PROMPT="#859900",
        LV_ERROR="#dc322f", LV_WARN="#b58900", LV_INFO="#268bd2",
        LV_SUCCESS="#859900",
        ACCENT="#268bd2", ACCENT_HOVER="#3a9bde", ACCENT_FG="#00171e",
        RED="#dc322f", RED_HOVER="#e8514e",
        DOT_RUNNING="#859900", DOT_IDLE="#586e75", SELECTION="#14505f"),

    "Rose poudré": Palette(
        name="Rose poudré",
        APP_BG="#241c20", SURFACE="#2e242a", SURFACE_2="#3a2e35",
        SURFACE_3="#463841", ALT_ROW="#32282e", BORDER="#4d3d46",
        FG="#f2e8ed", FG_DIM="#ccb4bf", MUTED="#988290",
        CONSOLE_BG="#1a1317", CONSOLE_HEAD="#2c2228", CONSOLE_PROMPT="#dba8c8",
        LV_ERROR="#ef8585", LV_WARN="#e4c279", LV_INFO="#7fb9e6",
        LV_SUCCESS="#76cba0",
        ACCENT="#e87bb0", ACCENT_HOVER="#ef90bf", ACCENT_FG="#2e0a1c",
        RED="#e87078", RED_HOVER="#f0858c",
        DOT_RUNNING="#4fd067", DOT_IDLE="#69707d", SELECTION="#5a2440"),

    "Cyberpunk néon": Palette(
        name="Cyberpunk néon",
        APP_BG="#15131c", SURFACE="#1d1a28", SURFACE_2="#272234",
        SURFACE_3="#332c44", ALT_ROW="#211d2e", BORDER="#3a3150",
        FG="#ece6f5", FG_DIM="#b4abc8", MUTED="#7f7596",
        CONSOLE_BG="#0e0c14", CONSOLE_HEAD="#1f1b2a", CONSOLE_PROMPT="#5ef2c6",
        LV_ERROR="#ff5d8f", LV_WARN="#ffd166", LV_INFO="#5ec8ff",
        LV_SUCCESS="#5ef2a0",
        ACCENT="#e84bd8", ACCENT_HOVER="#ef63e0", ACCENT_FG="#1a0418",
        RED="#ff5d8f", RED_HOVER="#ff7aa3",
        DOT_RUNNING="#5ef2a0", DOT_IDLE="#7f7596", SELECTION="#3a2152"),

    "Café moka": Palette(
        name="Café moka",
        APP_BG="#1e1a17", SURFACE="#27221e", SURFACE_2="#322b25",
        SURFACE_3="#3d342d", ALT_ROW="#2b2521", BORDER="#443a32",
        FG="#ece2d8", FG_DIM="#c2b3a4", MUTED="#8f8174",
        CONSOLE_BG="#161210", CONSOLE_HEAD="#28221e", CONSOLE_PROMPT="#bcd29a",
        LV_ERROR="#e88a7a", LV_WARN="#e0bd72", LV_INFO="#8bb6d6",
        LV_SUCCESS="#9cc47a",
        ACCENT="#c89a6a", ACCENT_HOVER="#d6ac7e", ACCENT_FG="#241809",
        RED="#e07a6a", RED_HOVER="#ec8d7d",
        DOT_RUNNING="#6cc24a", DOT_IDLE="#7a7163", SELECTION="#4a3a28"),

    "Ciel aurore": Palette(
        name="Ciel aurore",
        APP_BG="#1b1f2a", SURFACE="#232838", SURFACE_2="#2e3447",
        SURFACE_3="#3a4156", ALT_ROW="#282e3f", BORDER="#434b62",
        FG="#e9ecf5", FG_DIM="#b6bdd0", MUTED="#858da6",
        CONSOLE_BG="#141722", CONSOLE_HEAD="#252b3a", CONSOLE_PROMPT="#9fd6b3",
        LV_ERROR="#ef8585", LV_WARN="#e4c279", LV_INFO="#7fb9e6",
        LV_SUCCESS="#76cba0",
        ACCENT="#f08fb0", ACCENT_HOVER="#f4a3c0", ACCENT_FG="#1e0a16",
        RED="#e87078", RED_HOVER="#f0858c",
        DOT_RUNNING="#4fd067", DOT_IDLE="#69707d", SELECTION="#3a3560"),
}

DEFAULT_THEME = "Ardoise indigo"

# -- Constantes independantes du theme --------------------------------------
GROUP_COLORS = ("#6fa8d6", "#d6b36a", "#c98fd0", "#7bc0c0", "#d07a7a", "#9ec46a",
                "#e0915a", "#7d8af0", "#5ec8a8", "#d99ac0", "#b0c468", "#69b0e0",
                "#cf8f6a", "#8fb87a", "#b58fd0")
PROJECT_PALETTE = ("#3b9eff", "#3fb950", "#f0b400", "#f85149", "#bf5af2",
                   "#1abc9c", "#56d364", "#ff7b29", "#6e7bf2", "#ff5fa8",
                   "#00b8d4", "#8bc34a", "#ff9100", "#e91e63", "#9c27b0",
                   "#26c6da", "#cddc39", "#ff7043", "#5c6bc0", "#ec407a",
                   "#00bfa5", "#c0ca33", "#fb8c00", "#7e57c2", "#29b6f6")
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
