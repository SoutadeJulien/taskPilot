"""Icones dessinees a la volee (aucun fichier image embarque)."""

import math
import tkinter as tk

from taskpilot.ui import theme


def build_node_icon(root: tk.Misc, size: int = 16) -> tk.PhotoImage:
    """Dessine un petit hexagone facon logo Node, a la couleur d'accent."""
    img = tk.PhotoImage(master=root, width=size, height=size)
    cx = cy = (size - 1) / 2.0
    r = size / 2.0
    pts = []
    for k in range(6):
        ang = math.radians(60 * k - 90)
        pts.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))

    def inside(px, py):
        n = len(pts)
        c = False
        j = n - 1
        for i in range(n):
            xi, yi = pts[i]
            xj, yj = pts[j]
            if ((yi > py) != (yj > py)) and \
               (px < (xj - xi) * (py - yi) / (yj - yi + 1e-9) + xi):
                c = not c
            j = i
        return c

    for y in range(size):
        for x in range(size):
            if inside(x, y):
                img.put(theme.ACCENT, (x, y))
    return img


def build_status_dot(root: tk.Misc, color: str, size: int = 12) -> tk.PhotoImage:
    """Petite pastille ronde pleine (fond transparent), pour l'etat d'une task.

    Sert d'icone dans la colonne arbre du Treeview : vert = en cours,
    gris = au repos.
    """
    img = tk.PhotoImage(master=root, width=size, height=size)
    cx = cy = (size - 1) / 2.0
    r = size / 2.0 - 0.5
    for y in range(size):
        for x in range(size):
            if (x - cx) ** 2 + (y - cy) ** 2 <= r * r:
                img.put(color, (x, y))
    return img


def build_logo(root: tk.Misc, size: int = 64) -> tk.PhotoImage:
    """Logo TaskPilot : pastille arrondie a l'accent + triangle "play" sombre.

    Dessine pixel par pixel (PhotoImage) ; le fond hors-pastille reste
    transparent. Evoque un lanceur de tasks.
    """
    img = tk.PhotoImage(master=root, width=size, height=size)
    r = size * 0.24                      # rayon des coins de la pastille
    lo, hi = r, size - 1 - r             # bornes du rectangle interne

    def in_badge(x, y):
        dx = (lo - x) if x < lo else (x - hi if x > hi else 0)
        dy = (lo - y) if y < lo else (y - hi if y > hi else 0)
        return dx * dx + dy * dy <= r * r

    # Triangle "play" oriente a droite, centre dans la pastille.
    ax, ay = size * 0.38, size * 0.30
    bx, by = size * 0.38, size * 0.70
    cx2, cy2 = size * 0.70, size * 0.50

    def sign(px, py, x1, y1, x2, y2):
        return (px - x2) * (y1 - y2) - (x1 - x2) * (py - y2)

    def in_triangle(px, py):
        d1 = sign(px, py, ax, ay, bx, by)
        d2 = sign(px, py, bx, by, cx2, cy2)
        d3 = sign(px, py, cx2, cy2, ax, ay)
        neg = d1 < 0 or d2 < 0 or d3 < 0
        pos = d1 > 0 or d2 > 0 or d3 > 0
        return not (neg and pos)

    for y in range(size):
        for x in range(size):
            if not in_badge(x, y):
                continue
            img.put(theme.ACCENT_FG if in_triangle(x, y) else theme.ACCENT,
                    (x, y))
    return img
