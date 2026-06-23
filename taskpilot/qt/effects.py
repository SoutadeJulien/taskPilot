"""Petits effets visuels partages (ombres douces).

Une ombre portee subtile remplace avantageusement les bordures pour detacher
un element : elle donne de la profondeur sans alourdir l'interface de traits.
"""

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGraphicsDropShadowEffect


def add_shadow(widget, blur=26, dx=0, dy=4, alpha=120):
    """Applique une ombre portee douce a ``widget`` (carte / pilule en relief)."""
    eff = QGraphicsDropShadowEffect(widget)
    eff.setBlurRadius(blur)
    eff.setXOffset(dx)
    eff.setYOffset(dy)
    eff.setColor(QColor(0, 0, 0, alpha))
    widget.setGraphicsEffect(eff)
    return eff
