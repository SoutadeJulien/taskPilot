"""Themes (palettes) et feuille de style (QSS) de l'interface Qt.

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
from PySide6.QtGui import QColor, QFont, QPalette


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

    "Graphene": Palette(
        name="Graphene",
        APP_BG="#1e1e1e", SURFACE="#232323", SURFACE_2="#2a2a2a",
        SURFACE_3="#363636", ALT_ROW="#212121", BORDER="#333333",
        FG="#d4d4d4", FG_DIM="#a0a0a0", MUTED="#808080",
        CONSOLE_BG="#1a1a1a", CONSOLE_HEAD="#232323", CONSOLE_PROMPT="#b5cea8",
        LV_ERROR="#d16969", LV_WARN="#d7ba7d", LV_INFO="#9cdcfe",
        LV_SUCCESS="#88d169",
        ACCENT="#808080", ACCENT_HOVER="#9a9a9a", ACCENT_FG="#1e1e1e",
        RED="#d16969", RED_HOVER="#e64545",
        DOT_RUNNING="#58cc27", DOT_IDLE="#606060", SELECTION="#404040"),

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

    "Gruvbox sombre": Palette(
        name="Gruvbox sombre",
        APP_BG="#282828", SURFACE="#32302f", SURFACE_2="#3c3836",
        SURFACE_3="#504945", ALT_ROW="#2f2c2b", BORDER="#504945",
        FG="#ebdbb2", FG_DIM="#d5c4a1", MUTED="#928374",
        CONSOLE_BG="#1d2021", CONSOLE_HEAD="#32302f", CONSOLE_PROMPT="#b8bb26",
        LV_ERROR="#fb4934", LV_WARN="#fabd2f", LV_INFO="#83a598",
        LV_SUCCESS="#b8bb26",
        ACCENT="#fabd2f", ACCENT_HOVER="#ffd152", ACCENT_FG="#282828",
        RED="#fb4934", RED_HOVER="#ff6149",
        DOT_RUNNING="#b8bb26", DOT_IDLE="#928374", SELECTION="#504945"),

    "Tokyo Night": Palette(
        name="Tokyo Night",
        APP_BG="#1a1b26", SURFACE="#1f2335", SURFACE_2="#24283b",
        SURFACE_3="#2f344d", ALT_ROW="#1d1f2e", BORDER="#2f344d",
        FG="#c0caf5", FG_DIM="#a9b1d6", MUTED="#565f89",
        CONSOLE_BG="#16161e", CONSOLE_HEAD="#1f2335", CONSOLE_PROMPT="#9ece6a",
        LV_ERROR="#f7768e", LV_WARN="#e0af68", LV_INFO="#7aa2f7",
        LV_SUCCESS="#9ece6a",
        ACCENT="#7aa2f7", ACCENT_HOVER="#8fb3f9", ACCENT_FG="#16161e",
        RED="#f7768e", RED_HOVER="#ff8da0",
        DOT_RUNNING="#9ece6a", DOT_IDLE="#565f89", SELECTION="#283457"),

    "Catppuccin Mocha": Palette(
        name="Catppuccin Mocha",
        APP_BG="#1e1e2e", SURFACE="#252535", SURFACE_2="#313244",
        SURFACE_3="#45475a", ALT_ROW="#232336", BORDER="#45475a",
        FG="#cdd6f4", FG_DIM="#a6adc8", MUTED="#6c7086",
        CONSOLE_BG="#181825", CONSOLE_HEAD="#252535", CONSOLE_PROMPT="#a6e3a1",
        LV_ERROR="#f38ba8", LV_WARN="#f9e2af", LV_INFO="#89b4fa",
        LV_SUCCESS="#a6e3a1",
        ACCENT="#cba6f7", ACCENT_HOVER="#d6b9f9", ACCENT_FG="#1e1e2e",
        RED="#f38ba8", RED_HOVER="#f7a0b8",
        DOT_RUNNING="#a6e3a1", DOT_IDLE="#6c7086", SELECTION="#3a3a52"),

    "One Dark": Palette(
        name="One Dark",
        APP_BG="#282c34", SURFACE="#2c313a", SURFACE_2="#353b45",
        SURFACE_3="#3e4451", ALT_ROW="#2f343e", BORDER="#3e4451",
        FG="#abb2bf", FG_DIM="#9aa1ad", MUTED="#5c6370",
        CONSOLE_BG="#21252b", CONSOLE_HEAD="#2c313a", CONSOLE_PROMPT="#98c379",
        LV_ERROR="#e06c75", LV_WARN="#e5c07b", LV_INFO="#61afef",
        LV_SUCCESS="#98c379",
        ACCENT="#61afef", ACCENT_HOVER="#7abdf2", ACCENT_FG="#1b1d23",
        RED="#e06c75", RED_HOVER="#e8838b",
        DOT_RUNNING="#98c379", DOT_IDLE="#5c6370", SELECTION="#3e4451"),

    "Monokai": Palette(
        name="Monokai",
        APP_BG="#272822", SURFACE="#2d2e27", SURFACE_2="#383830",
        SURFACE_3="#49483e", ALT_ROW="#31322b", BORDER="#49483e",
        FG="#f8f8f2", FG_DIM="#cfd0c2", MUTED="#75715e",
        CONSOLE_BG="#1e1f1a", CONSOLE_HEAD="#2d2e27", CONSOLE_PROMPT="#a6e22e",
        LV_ERROR="#f92672", LV_WARN="#e6db74", LV_INFO="#66d9ef",
        LV_SUCCESS="#a6e22e",
        ACCENT="#66d9ef", ACCENT_HOVER="#82e0f2", ACCENT_FG="#102825",
        RED="#f92672", RED_HOVER="#fb4a8c",
        DOT_RUNNING="#a6e22e", DOT_IDLE="#75715e", SELECTION="#49483e"),

    "Rosé Pine": Palette(
        name="Rosé Pine",
        APP_BG="#191724", SURFACE="#1f1d2e", SURFACE_2="#26233a",
        SURFACE_3="#393552", ALT_ROW="#211f30", BORDER="#393552",
        FG="#e0def4", FG_DIM="#908caa", MUTED="#6e6a86",
        CONSOLE_BG="#15131f", CONSOLE_HEAD="#1f1d2e", CONSOLE_PROMPT="#9ccfd8",
        LV_ERROR="#eb6f92", LV_WARN="#f6c177", LV_INFO="#c4a7e7",
        LV_SUCCESS="#9ccfd8",
        ACCENT="#c4a7e7", ACCENT_HOVER="#d0b8ec", ACCENT_FG="#1f1d2e",
        RED="#eb6f92", RED_HOVER="#f084a3",
        DOT_RUNNING="#9ccfd8", DOT_IDLE="#6e6a86", SELECTION="#393552"),

    "Ayu sombre": Palette(
        name="Ayu sombre",
        APP_BG="#0d1017", SURFACE="#131721", SURFACE_2="#1c212c",
        SURFACE_3="#273340", ALT_ROW="#11151e", BORDER="#1c212c",
        FG="#bfbdb6", FG_DIM="#9b9892", MUTED="#565b66",
        CONSOLE_BG="#090c12", CONSOLE_HEAD="#131721", CONSOLE_PROMPT="#aad94c",
        LV_ERROR="#f07178", LV_WARN="#ffb454", LV_INFO="#59c2ff",
        LV_SUCCESS="#aad94c",
        ACCENT="#e6b450", ACCENT_HOVER="#f0c265", ACCENT_FG="#0d1017",
        RED="#f07178", RED_HOVER="#f78a90",
        DOT_RUNNING="#aad94c", DOT_IDLE="#565b66", SELECTION="#1f2a35"),

    "GitHub sombre": Palette(
        name="GitHub sombre",
        APP_BG="#0d1117", SURFACE="#161b22", SURFACE_2="#21262d",
        SURFACE_3="#30363d", ALT_ROW="#11161d", BORDER="#30363d",
        FG="#c9d1d9", FG_DIM="#adbac7", MUTED="#8b949e",
        CONSOLE_BG="#010409", CONSOLE_HEAD="#161b22", CONSOLE_PROMPT="#3fb950",
        LV_ERROR="#f85149", LV_WARN="#d29922", LV_INFO="#58a6ff",
        LV_SUCCESS="#3fb950",
        ACCENT="#58a6ff", ACCENT_HOVER="#79b8ff", ACCENT_FG="#0d1117",
        RED="#f85149", RED_HOVER="#ff6a5f",
        DOT_RUNNING="#3fb950", DOT_IDLE="#8b949e", SELECTION="#163356"),

    "Everforest": Palette(
        name="Everforest",
        APP_BG="#2d353b", SURFACE="#343f44", SURFACE_2="#3d484d",
        SURFACE_3="#475258", ALT_ROW="#313a40", BORDER="#475258",
        FG="#d3c6aa", FG_DIM="#bdc3af", MUTED="#859289",
        CONSOLE_BG="#232a2e", CONSOLE_HEAD="#343f44", CONSOLE_PROMPT="#a7c080",
        LV_ERROR="#e67e80", LV_WARN="#dbbc7f", LV_INFO="#7fbbb3",
        LV_SUCCESS="#a7c080",
        ACCENT="#a7c080", ACCENT_HOVER="#b6cc92", ACCENT_FG="#2d353b",
        RED="#e67e80", RED_HOVER="#ec9395",
        DOT_RUNNING="#a7c080", DOT_IDLE="#859289", SELECTION="#475258"),

    "Night Owl": Palette(
        name="Night Owl",
        APP_BG="#011627", SURFACE="#0b2942", SURFACE_2="#13344f",
        SURFACE_3="#1d3b53", ALT_ROW="#082035", BORDER="#1d3b53",
        FG="#d6deeb", FG_DIM="#aeb9d0", MUTED="#637777",
        CONSOLE_BG="#010f1c", CONSOLE_HEAD="#0b2942", CONSOLE_PROMPT="#22da6e",
        LV_ERROR="#ef5350", LV_WARN="#ecc48d", LV_INFO="#82aaff",
        LV_SUCCESS="#22da6e",
        ACCENT="#82aaff", ACCENT_HOVER="#9bbcff", ACCENT_FG="#011627",
        RED="#ef5350", RED_HOVER="#f56b68",
        DOT_RUNNING="#22da6e", DOT_IDLE="#637777", SELECTION="#1d3b53"),

    "Palenight": Palette(
        name="Palenight",
        APP_BG="#292d3e", SURFACE="#2f3447", SURFACE_2="#3a3f58",
        SURFACE_3="#444a66", ALT_ROW="#2d3142", BORDER="#444a66",
        FG="#a6accd", FG_DIM="#8c92b3", MUTED="#676e95",
        CONSOLE_BG="#21222f", CONSOLE_HEAD="#2f3447", CONSOLE_PROMPT="#c3e88d",
        LV_ERROR="#f07178", LV_WARN="#ffcb6b", LV_INFO="#82aaff",
        LV_SUCCESS="#c3e88d",
        ACCENT="#82aaff", ACCENT_HOVER="#9bbcff", ACCENT_FG="#1b1d29",
        RED="#f07178", RED_HOVER="#f78a90",
        DOT_RUNNING="#c3e88d", DOT_IDLE="#676e95", SELECTION="#3a3f58"),
}

DEFAULT_THEME = "Ardoise indigo"

#: Facteur d'arrondi global (0 = carre, 1 = design d'origine, ~1.8 = tres rond).
#: Applique par ``radius()`` a tous les rayons du QSS et des styles inline.
RADIUS = 1.0
RADIUS_MIN, RADIUS_MAX = 0.0, 2.0

#: Presets proposes dans le menu « Options › Arrondis » (libelle -> facteur).
RADIUS_PRESETS = {
    "Carré": 0.0,
    "Léger": 0.5,
    "Normal": 1.0,
    "Arrondi": 1.4,
    "Très arrondi": 1.8,
}

#: Densite : facteur d'espacement applique aux paddings du QSS (compacite).
DENSITY = 1.0
DENSITY_MIN, DENSITY_MAX = 0.7, 1.5
DENSITY_PRESETS = {"Compact": 0.82, "Normal": 1.0, "Confortable": 1.25}

#: Police d'interface (utilisee par le QSS). Reglable via les options.
UI_FONT = "Segoe UI"
UI_FONT_SIZE = 13

#: Surcouche d'accent personnalise (hex) ou ``None`` pour suivre le theme.
ACCENT_OVERRIDE = None

#: Choix proposes dans les menus de police / taille.
UI_FONT_CHOICES = ("Segoe UI", "Inter", "Roboto", "Calibri", "Verdana", "Tahoma")
MONO_FONT_CHOICES = ("Cascadia Mono, Consolas", "Cascadia Code", "Consolas",
                     "JetBrains Mono", "Fira Code", "Courier New")
UI_FONT_SIZES = (11, 12, 13, 14, 15, 16)
MONO_FONT_SIZES = (9, 10, 11, 12, 13, 14)

#: Palette d'accents proposes (en plus du choix libre par QColorDialog).
ACCENT_CHOICES = ("#7c8cf8", "#3fb6b6", "#e0a64e", "#4cc98a", "#3d8bf0",
                  "#a771ee", "#e0556b", "#e87bb0", "#58a6ff", "#f7768e")

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
    fonts_changed = Signal()  # police monospace des consoles modifiee


notifier = _Notifier()


# ---------------------------------------------------------------------------
# Helpers couleur
# ---------------------------------------------------------------------------
def radius(px):
    """Rayon ``px`` (rayon « de base » du design) mis a l'echelle par ``RADIUS``.

    ``RADIUS`` est un facteur global (0 = coins carres, 1 = design d'origine,
    >1 = plus arrondi). Utilise par le QSS *et* par les styles « inline » des
    widgets pour rester coherent quand l'utilisateur change l'arrondi a chaud.
    """
    return max(0, round(px * RADIUS))


def pad(px):
    """Espacement ``px`` de base mis a l'echelle par la densite ``DENSITY``."""
    return max(0, round(px * DENSITY))


def _contrast_fg(hexstr):
    """Couleur de texte lisible (sombre/claire) a poser sur ``hexstr``."""
    h = hexstr.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    return "#12151b" if lum > 150 else "#f5f7fb"


def _effective_palette(pal):
    """Renvoie ``pal`` eventuellement modifie par l'accent personnalise."""
    if not ACCENT_OVERRIDE:
        return pal
    from dataclasses import replace
    acc = ACCENT_OVERRIDE
    return replace(pal, ACCENT=acc, ACCENT_HOVER=_lighten(acc, 0.14),
                   ACCENT_FG=_contrast_fg(acc))


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
    r = radius  # rayons mis a l'echelle par le facteur global RADIUS
    d = pad     # espacements mis a l'echelle par la densite DENSITY
    return f"""
/* La police d'interface est posee via QApplication.setFont (police par
   defaut, surchargeable par setFont) — surtout PAS via un selecteur * en QSS,
   qui ecraserait le setFont des consoles (police monospace + zoom). */
* {{ color: {FG}; }}
QMainWindow, QWidget {{ background: {APP_BG}; }}
QToolTip {{
    background: {SURFACE_3}; color: {FG};
    border: none; border-radius: {r(7)}px; padding: {d(6)}px {d(9)}px;
}}

QMenuBar {{ background: {APP_BG}; color: {FG_DIM}; padding: {d(4)}px 6px; }}
QMenuBar::item {{ padding: {d(6)}px {d(13)}px; border-radius: {r(7)}px; background: transparent; }}
QMenuBar::item:selected {{ background: {SURFACE_2}; color: {FG}; }}
QMenu {{ background: {SURFACE_2}; border: none; border-radius: {r(9)}px; padding: 4px; }}
QMenu::item {{ padding: {d(5)}px 22px {d(5)}px 18px; border-radius: {r(6)}px; }}
QMenu::item:selected {{ background: {ACCENT}; color: {ACCENT_FG}; }}
QMenu::item:disabled {{ color: {MUTED}; }}
QMenu::separator {{ height: 1px; background: {SURFACE_3}; margin: 4px 8px; }}
QMenu::icon {{ padding-left: 6px; }}

QTabWidget::pane {{ border: none; background: {SURFACE}; }}
QTabBar {{ qproperty-drawBase: 0; background: transparent; }}
QTabBar::tab {{
    background: transparent; color: {MUTED};
    padding: {d(6)}px {d(15)}px; margin-right: 3px; border: none;
    border-top-left-radius: {r(9)}px; border-top-right-radius: {r(9)}px;
}}
QTabBar::tab:hover {{ color: {FG}; background: {SURFACE}; }}
QTabBar::tab:selected {{ background: {SURFACE}; color: {FG}; border-top: 2px solid {ACCENT}; }}

QTabWidget#consoleTabs QTabBar::tab {{
    padding: {d(5)}px {d(11)}px; margin-right: 2px; font-size: {max(9, UI_FONT_SIZE - 1)}px;
    border-top-left-radius: {r(8)}px; border-top-right-radius: {r(8)}px;
}}
QTabWidget#consoleTabs QTabBar::tab:selected {{ border-top: 2px solid {ACCENT}; }}

QPushButton {{
    background: {SURFACE_2}; border: none; border-radius: {r(8)}px;
    padding: {d(6)}px {d(13)}px; color: {FG};
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
    border-radius: {r(8)}px; padding: {d(6)}px {d(11)}px; selection-background-color: {ACCENT};
}}
QComboBox:hover, QLineEdit:hover {{ background: {SURFACE_3}; }}
QComboBox:focus, QLineEdit:focus {{ border: 1px solid {ACCENT}; }}
QComboBox::drop-down {{ border: none; width: 26px; }}
QComboBox::down-arrow {{ width: 11px; height: 11px; }}
QComboBox QAbstractItemView {{
    background: {SURFACE_2}; border: none; border-radius: {r(9)}px; padding: 5px;
    selection-background-color: {ACCENT}; selection-color: {ACCENT_FG}; outline: 0;
}}

/* Carte arrondie enveloppant la liste des tasks (coins ronds sans encoche :
   c'est la carte qui porte le rayon, l'arbre est en retrait dedans). */
QFrame#taskCard {{ background: {SURFACE}; border-radius: {r(12)}px; }}

QTreeWidget, QTreeView, QListWidget {{
    background: {SURFACE}; border: none;
    alternate-background-color: {ALT_ROW}; outline: 0; show-decoration-selected: 1;
}}
QTreeView::item, QTreeWidget::item, QListWidget::item {{
    padding: {d(5)}px 3px; border: none; border-radius: {r(6)}px;
}}
QTreeView::item:hover, QTreeWidget::item:hover, QListWidget::item:hover {{ background: {SURFACE_2}; }}
QTreeView::item:selected, QTreeWidget::item:selected, QListWidget::item:selected {{
    background: {SELECTION}; color: {FG};
}}
QHeaderView::section {{
    background: {SURFACE}; color: {MUTED};
    padding: {d(9)}px {d(10)}px; border: none; font-weight: 600;
}}
QHeaderView::section:hover {{ color: {FG}; }}

QPlainTextEdit {{
    background: {CONSOLE_BG}; border: none; color: {FG};
    selection-background-color: {ACCENT}; selection-color: {ACCENT_FG};
}}

QCheckBox {{ spacing: 8px; padding: 3px; }}
QCheckBox::indicator {{
    width: 15px; height: 15px; border-radius: {r(5)}px; border: none; background: {SURFACE_3};
}}
QCheckBox::indicator:hover {{ background: {check_hover}; }}
QCheckBox::indicator:checked {{ background: {ACCENT}; }}

QScrollBar:vertical {{ background: transparent; width: 13px; margin: 3px; }}
QScrollBar::handle:vertical {{ background: {scroll}; border-radius: {r(5)}px; min-height: 32px; }}
QScrollBar::handle:vertical:hover {{ background: {scroll_hover}; }}
QScrollBar:horizontal {{ background: transparent; height: 13px; margin: 3px; }}
QScrollBar::handle:horizontal {{ background: {scroll}; border-radius: {r(5)}px; min-width: 32px; }}
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
    """Installe ``pal`` (theme de base) ; l'accent personnalise est applique
    par-dessus. Met a jour les attributs de module + alias + QSS."""
    g = globals()
    g["_base_pal"] = pal              # theme nu, re-utilise si l'accent change
    eff = _effective_palette(pal)     # avec l'accent personnalise eventuel
    for f in fields(Palette):
        if f.name != "name":
            g[f.name] = getattr(eff, f.name)
    g["BG"] = eff.APP_BG
    g["BG_ALT"] = eff.SURFACE
    g["HEAD"] = eff.SURFACE_2
    g["CONSOLE_BORDER"] = eff.BORDER
    g["ANSI_COLORS"] = ansi_colors(eff)
    g["QSS"] = build_qss(eff)
    g["current"] = eff


def set_theme(name):
    """Installe le theme ``name`` (sans toucher a l'application Qt)."""
    pal = THEMES.get(name) or THEMES[DEFAULT_THEME]
    _install(pal)
    return pal


def apply_theme(app, name):
    """Applique le theme ``name`` a une ``QApplication`` (live-switch)."""
    set_theme(name)
    app.setFont(app_font())
    app.setPalette(build_palette())
    app.setStyleSheet(QSS)
    notifier.changed.emit()


def set_radius(scale):
    """Fixe le facteur d'arrondi global (clampe) et reconstruit le QSS courant."""
    global RADIUS
    RADIUS = min(RADIUS_MAX, max(RADIUS_MIN, float(scale)))
    if current is not None:
        globals()["QSS"] = build_qss(current)
    return RADIUS


def apply_radius(app, scale):
    """Applique un nouvel arrondi a une ``QApplication`` (live-switch)."""
    set_radius(scale)
    app.setStyleSheet(QSS)
    notifier.changed.emit()


def _refresh_qss():
    """Reconstruit le QSS global a partir du theme effectif courant."""
    if current is not None:
        globals()["QSS"] = build_qss(current)


def set_density(scale):
    """Fixe la densite (compacite) globale, clampee, et reconstruit le QSS."""
    global DENSITY
    DENSITY = min(DENSITY_MAX, max(DENSITY_MIN, float(scale)))
    _refresh_qss()
    return DENSITY


def apply_density(app, scale):
    """Applique une nouvelle densite a une ``QApplication`` (live-switch)."""
    set_density(scale)
    app.setStyleSheet(QSS)
    notifier.changed.emit()


def set_ui_font(family=None, size=None):
    """Fixe la police d'interface (QSS) et reconstruit le QSS."""
    global UI_FONT, UI_FONT_SIZE
    if family:
        UI_FONT = family
    if size:
        UI_FONT_SIZE = int(size)
    _refresh_qss()


def apply_ui_font(app, family=None, size=None):
    """Applique la police d'interface a une ``QApplication`` (live-switch)."""
    set_ui_font(family, size)
    app.setFont(app_font())
    app.setStyleSheet(QSS)
    notifier.changed.emit()


def set_mono_font(family=None, size=None):
    """Fixe la police monospace des consoles et notifie les vues concernees."""
    global MONO_FAMILY, MONO_SIZE
    if family:
        MONO_FAMILY = family
    if size:
        MONO_SIZE = int(size)
    notifier.fonts_changed.emit()


def app_font():
    """Police par defaut de l'application (interface), en pixels pour coller
    a l'ancien dimensionnement QSS (``font-size: Npx``)."""
    f = QFont(UI_FONT)
    f.setPixelSize(UI_FONT_SIZE)
    return f


def mono_font(size=None):
    """``QFont`` monospace des consoles, avec liste de familles de repli
    (``MONO_FAMILY`` peut etre ``"Cascadia Mono, Consolas"``)."""
    fams = [f.strip() for f in MONO_FAMILY.split(",") if f.strip()]
    f = QFont(fams[0] if fams else "Consolas")
    if len(fams) > 1:
        f.setFamilies(fams)
    f.setPointSize(int(size or MONO_SIZE))
    return f


def set_accent_override(hexstr):
    """Force l'accent (hex) ou suit le theme si ``hexstr`` est vide ; reinstalle."""
    global ACCENT_OVERRIDE
    ACCENT_OVERRIDE = (hexstr or "").strip() or None
    if _base_pal is not None:
        _install(_base_pal)


def apply_accent_override(app, hexstr):
    """Applique un accent personnalise a une ``QApplication`` (live-switch)."""
    set_accent_override(hexstr)
    app.setPalette(build_palette())
    app.setStyleSheet(QSS)
    notifier.changed.emit()


# Theme par defaut installe au chargement du module.
current = None
_base_pal = None
set_theme(DEFAULT_THEME)
