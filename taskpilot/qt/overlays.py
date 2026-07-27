"""Calques de surlignage (``ExtraSelection``) partages d'un editeur.

Qt n'expose qu'une **liste plate** d'``extraSelections`` par editeur : le
dernier appelant ecrase le travail des autres. Or plusieurs fonctions d'une
console en veulent en meme temps (survol d'un lien, selection de lignes a la
poignee, resultats de recherche). Ce module les empile par calque nomme et
recompose la liste dans un ordre stable — les calques de fin de ``ORDER``
passent visuellement au-dessus des precedents.
"""

#: Ordre de composition (du fond vers le dessus).
ORDER = ("find", "find-current", "lines", "hover")

_ATTR = "_overlay_layers"


def set_layer(edit, layer, selections):
    """Remplace le contenu du calque ``layer`` et recompose l'affichage.

    ``selections`` vide (ou ``None``) retire simplement le calque.
    """
    layers = getattr(edit, _ATTR, None)
    if layers is None:
        layers = {}
        setattr(edit, _ATTR, layers)
    if selections:
        layers[layer] = list(selections)
    elif layer not in layers:
        return
    else:
        del layers[layer]
    edit.setExtraSelections(
        [sel for name in ORDER for sel in layers.get(name, ())])


def clear_layer(edit, layer):
    """Retire le calque ``layer`` (sans toucher aux autres)."""
    set_layer(edit, layer, None)
