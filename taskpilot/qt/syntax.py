"""Reconnaissance des donnees structurees (JSON / YAML / XML) dans la sortie.

Une console n'affiche que du texte, mais les programmes y deversent souvent des
donnees structurees (``console.log(obj)``, dump de config, reponse d'API...).
Ce module repere ces fragments **ligne a ligne** et renvoie des *spans*
``(debut, fin, jeton)`` que la vue console traduit en formats Qt.

Deux voies de reconnaissance :

* **automatique** — un fragment JSON valide quelque part dans la ligne (verifie
  par un vrai ``json.raw_decode``, pas par une regex), un objet **JavaScript**
  tel que Node le rend (``console.log(obj)`` passe par ``util.inspect`` : clefs
  non quotees, chaines en apostrophes — ce n'est *pas* du JSON), une
  accolade/crochet ouvrant en fin de ligne (dump indente sur plusieurs lignes)
  ou un document YAML introduit par ``---`` ;
* **explicite** — un marqueur ``#json`` / ``#yaml`` / ``#xml`` pose par
  l'appelant (``console.log("#json", obj)``). Le marqueur est **retire** de
  l'affichage et force le mode pour tout le bloc : c'est l'echappatoire quand
  l'heuristique ne suffit pas (YAML sans ``---``, XML multi-lignes...).

L'analyse est incrementale : l'etat (mode courant, profondeur) est conserve
d'une ligne a l'autre. La vue console reconstruit la ligne partielle en cours a
chaque arrivee d'octets : elle l'analyse avec ``commit=False``, qui rend le
resultat **sans faire avancer l'etat**.
"""

import json
import re

from taskpilot.qt import theme

# -- Jetons ------------------------------------------------------------------
KEY, STR, NUM, KW = "key", "str", "num", "kw"
PUNCT, COMMENT, TAG, ATTR = "punct", "comment", "tag", "attr"

#: Jeton -> token de couleur du theme (resolu a chaud, suit le theme actif).
COLORS = {
    KEY: "LV_INFO", STR: "LV_SUCCESS", NUM: "LV_WARN", KW: "ACCENT",
    PUNCT: "MUTED", COMMENT: "MUTED", TAG: "LV_INFO", ATTR: "LV_WARN",
}

#: Garde-fou : au-dela, on considere qu'on n'est plus dans un bloc structure.
MAX_BLOCK_LINES = 2000

#: Nb max de candidats ``{``/``[`` testes par ligne (cout de ``raw_decode``).
MAX_JSON_CANDIDATES = 12


def token_color(kind):
    """Couleur (hex) d'un jeton pour le theme actif, ou ``None``."""
    return getattr(theme, COLORS.get(kind, ""), None)


# ---------------------------------------------------------------------------
# Marqueur explicite
# ---------------------------------------------------------------------------
#: « #json » en debut de ligne ou precede d'un espace (+ l'espace qui suit).
_TAG_RE = re.compile(r"(?<![^\s])#(json|yaml|yml|xml|html)\b[ \t]?",
                     re.IGNORECASE)
_TAG_MODES = {"json": "json", "yaml": "yaml", "yml": "yaml",
              "xml": "xml", "html": "xml"}


def _strip_tag(line):
    """``(texte sans le marqueur, mode)`` ou ``(line, None)``."""
    m = _TAG_RE.search(line)
    if not m:
        return line, None
    return line[:m.start()] + line[m.end():], _TAG_MODES[m.group(1).lower()]


# ---------------------------------------------------------------------------
# Tokenizers
# ---------------------------------------------------------------------------
#: Les groupes nommes portent directement le nom du jeton (cf. ``_tokenize``).
#:
#: Un seul tokenizer couvre le JSON **et** le rendu ``util.inspect`` de Node
#: (``console.log(obj)``), qui n'est pas du JSON : clefs non quotees, chaines en
#: apostrophes, ``undefined``, ``[Function: f]``... Les alternatives quotees
#: passent avant le reste, ce qui neutralise le contenu des chaines (une
#: accolade dans ``'**/*.{js,ts}'`` n'est donc pas prise pour de la structure).
_OBJ_TOKEN = re.compile(r"""
      (?P<kw>\[(?:Function|Getter|Setter|Class|Circular|Object|Array)[^\]]*\]
            | <(?:ref|Buffer)[^>]*>
            | \b(?:true|false|null|undefined|NaN|Infinity)\b)
    | (?P<key>"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'|[A-Za-z_$][\w$]*)(?=\s*:)
    | (?P<str>"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'|`(?:[^`\\]|\\.)*`)
    | (?P<num>-?\b\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\b)
    | (?P<punct>[{}\[\],:])
""", re.VERBOSE)

_XML_TOKEN = re.compile(r"""
      (?P<comment><!--.*?(?:-->|$))
    | (?P<punct></?)(?P<tag>[A-Za-z_?!][\w:.\-]*)
    | (?P<punct2>/?>)
    | (?P<attr>[A-Za-z_][\w:.\-]*)(?=\s*=)
    | (?P<str>"[^"]*"|'[^']*')
""", re.VERBOSE)

#: Groupes techniques (doublons de nom impossibles en regex) -> vrai jeton.
_ALIASES = {"punct2": PUNCT}


def _tokenize(text, pattern, start=0, end=None):
    """Spans ``(debut, fin, jeton)`` de ``text[start:end]`` selon ``pattern``."""
    end = len(text) if end is None else end
    spans = []
    for m in pattern.finditer(text, start, end):
        for name, value in m.groupdict().items():
            if value is None:
                continue
            a, b = m.span(name)
            if b > a:
                spans.append((a, b, _ALIASES.get(name, name)))
    spans.sort(key=lambda s: s[0])
    return spans


# ---------------------------------------------------------------------------
# JSON et objets JavaScript (rendu ``util.inspect`` de Node)
# ---------------------------------------------------------------------------
_DECODER = json.JSONDecoder()

#: Une ligne au milieu d'un bloc d'objet commence forcement par ceci : une
#: ponctuation de structure, une chaine, un nombre, un litteral, ou une clef
#: non quotee **immediatement** suivie de ``:`` (``file to add in db C:`` n'en
#: est donc pas une, et la prose ne prolonge pas un bloc).
_BLOCK_LINEISH = re.compile(
    r"""^\s*(?:[\[\]{}(),]|["'`]|-?\d|true|false|null|undefined|NaN|Infinity"""
    r"""|[A-Za-z_$][\w$.\-]*\s*:)""")

#: Indice qu'une zone entre accolades est un objet et non du texte : au moins
#: une paire ``clef: valeur``. Le blanc apres ``:`` exclut ``C:/dev`` et
#: ``18:32:19``.
_OBJ_KEY_HINT = re.compile(
    r"""[{,\s](?:[A-Za-z_$][\w$]*|'[^']*'|"[^"]*")\s*:(?:\s|$)""")


def _walk(text, start=0, stop_at_zero=False):
    """Parcourt ``text`` en suivant les chaines ; renvoie ``(profondeur, fin)``.

    Les trois sortes de quotes de JS sont suivies (et les echappements), pour
    qu'une accolade **dans une chaine** ne compte pas comme de la structure.
    Avec ``stop_at_zero``, s'arrete des que la structure ouverte a ``start`` se
    referme et renvoie la position juste apres ; ``fin`` vaut ``None`` si elle
    ne se referme pas sur cette ligne.
    """
    depth, quote, esc = 0, "", False
    for i in range(start, len(text)):
        ch = text[i]
        if quote:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == quote:
                quote = ""
        elif ch in "\"'`":
            quote = ch
        elif ch in "{[":
            depth += 1
        elif ch in "}]":
            depth -= 1
            if stop_at_zero and depth <= 0:
                return depth, (i + 1 if depth == 0 else None)
    return depth, None


def _depth_delta(text):
    """Variation de profondeur ``{[`` / ``]}`` de la ligne, hors chaines."""
    return _walk(text)[0]


def _json_inline(text):
    """Spans du premier fragment JSON complet de ``text``, ou ``None``.

    Le fragment est valide par ``raw_decode`` : un prefixe de log (``[12:00:03]``)
    ne declenche donc pas de faux positif, et le texte qui suit le fragment
    reste non colore.
    """
    for i in _candidates(text):
        try:
            obj, end = _DECODER.raw_decode(text, i)
        except ValueError:
            continue
        if isinstance(obj, (dict, list)):
            return _tokenize(text, _OBJ_TOKEN, i, end)
    return None


def _object_inline(text):
    """Idem pour un objet **JavaScript** complet sur la ligne, ou ``None``.

    Pas de parseur de reference ici (ce n'est pas du JSON) : on exige une zone
    d'accolades equilibree contenant au moins une paire ``clef: valeur``, ce qui
    ecarte les crochets de log (``[DEBUG]``) sans rater le
    ``{ name: 'gt-2020' }`` de Node.
    """
    for i in _candidates(text):
        _depth, end = _walk(text, i, stop_at_zero=True)
        if end is None or end - i < 4:
            continue
        if _OBJ_KEY_HINT.search(text, i, end):
            return _tokenize(text, _OBJ_TOKEN, i, end)
    return None


def _candidates(text):
    """Index des ouvrants testables comme debut de structure (nombre borne)."""
    found = []
    for i, ch in enumerate(text):
        if ch in "{[":
            found.append(i)
            if len(found) >= MAX_JSON_CANDIDATES:
                break
    return found


def _block_open(text):
    """Index de l'ouvrant d'un objet **multi-lignes**, ou ``None``.

    L'ouvrant doit terminer la ligne — c'est la forme de tout dump indente
    (``JSON.stringify(obj, null, 2)``, ``console.log(obj)``, ``scripts: {``),
    eventuellement precede d'un prefixe de log ou d'un nom de constructeur
    (``Map(3) {``). Les lignes suivantes doivent ensuite ressembler a du
    contenu d'objet (cf. ``_BLOCK_LINEISH``), sinon le bloc est abandonne.
    """
    stripped = text.rstrip()
    return len(stripped) - 1 if stripped.endswith(("{", "[")) else None


# ---------------------------------------------------------------------------
# YAML
# ---------------------------------------------------------------------------
_YAML_DASH = re.compile(r"^\s*(-)(?=\s|$)")
_YAML_KEY = re.compile(
    r"""\s*(?P<key>"[^"]*"|'[^']*'|[\w.\-/][\w.\-/ ]*?)(?P<colon>:)(?=\s|$)""")
_YAML_COMMENT = re.compile(r"(?:(?<=\s)|^)(#.*)$")
_YAML_VALUE = re.compile(r"""
    ^(?P<lead>\s*)(?:(?P<str>"[^"]*"|'[^']*')
                  | (?P<num>-?\d+(?:\.\d+)?)
                  | (?P<kw>true|false|null|yes|no|on|off|~))\s*$
""", re.VERBOSE | re.IGNORECASE)


def _yaml_lineish(line):
    """``True`` si ``line`` peut appartenir a un document YAML en cours."""
    if not line.strip():
        return False
    if line[:1] in (" ", "\t"):     # contenu indente (mapping, scalaire bloc)
        return True
    stripped = line.strip()
    return (stripped in ("---", "...") or stripped.startswith(("#", "- "))
            or bool(_YAML_KEY.match(line)))


def _yaml_spans(text):
    """Spans d'une ligne YAML (cle, valeur scalaire, tiret, commentaire)."""
    stripped = text.strip()
    if stripped.startswith("#"):
        return [(text.index("#"), len(text), COMMENT)]
    if stripped in ("---", "..."):
        i = len(text) - len(text.lstrip())
        return [(i, i + 3, PUNCT)]
    spans, pos = [], 0
    dash = _YAML_DASH.match(text)
    if dash:
        spans.append((dash.start(1), dash.end(1), PUNCT))
        pos = dash.end()
    key = _YAML_KEY.match(text, pos)
    if key:
        spans.append((key.start("key"), key.end("key"), KEY))
        spans.append((key.start("colon"), key.end("colon"), PUNCT))
        pos = key.end()
    rest = text[pos:]
    comment = _YAML_COMMENT.search(rest)
    if comment:
        spans.append((pos + comment.start(1), pos + comment.end(1), COMMENT))
        rest = rest[:comment.start(1)]
    value = _YAML_VALUE.match(rest)
    if value:
        for name in (STR, NUM, KW):
            if value.group(name) is not None:
                a, b = value.span(name)
                spans.append((pos + a, pos + b, name))
    spans.sort(key=lambda s: s[0])
    return spans


# ---------------------------------------------------------------------------
# XML / HTML
# ---------------------------------------------------------------------------
_XML_START = re.compile(r"^</?[A-Za-z_?!]")


def _looks_like_xml(stripped):
    return (len(stripped) > 2 and stripped.endswith(">")
            and bool(_XML_START.match(stripped)))


# ---------------------------------------------------------------------------
# Analyseur incremental
# ---------------------------------------------------------------------------
class OutputParser:
    """Etat de l'analyse d'un flux de console (une instance par console)."""

    def __init__(self):
        self.reset()

    def reset(self):
        """Repart a zero (console videe, process relance)."""
        self._mode = None       # None | "json" | "yaml" | "xml"
        self._depth = 0         # profondeur JSON courante
        self._opened = False    # le bloc JSON a-t-il deja ouvert une accolade
        self._lines = 0         # lignes consommees dans le bloc courant

    def feed(self, line, commit=True):
        """Analyse ``line`` et renvoie ``(texte a afficher, spans)``.

        ``spans`` vaut ``None`` si la ligne n'est pas reconnue comme
        structuree (la vue applique alors sa coloration par niveau de log) ;
        une liste vide signifie « structuree, mais rien a colorer ici ».
        Le texte peut differer de ``line`` (marqueur ``#json`` retire).

        Avec ``commit=False``, l'etat interne est restaure apres l'analyse :
        c'est ce qui permet de reanalyser sans dommage la ligne partielle en
        cours de reception.
        """
        saved = (self._mode, self._depth, self._opened, self._lines)
        text, spans = self._scan(line)
        if not commit:
            self._mode, self._depth, self._opened, self._lines = saved
        return text, spans

    # -- Interne -------------------------------------------------------------
    def _scan(self, line):
        if self._mode:
            text, spans = self._continue(line)
            if spans is not None:
                return text, spans
            self.reset()        # bloc termine ou invalide : on repart a neuf
        return self._start(line)

    def _continue(self, line):
        """Ligne suivante d'un bloc en cours ; ``spans`` ``None`` = bloc fini."""
        self._lines += 1
        if self._lines > MAX_BLOCK_LINES:
            return line, None
        if self._mode == "json":
            if not _BLOCK_LINEISH.match(line):
                return line, None
            self._depth += _depth_delta(line)
            self._opened = self._opened or self._depth > 0
            spans = _tokenize(line, _OBJ_TOKEN)
            if self._opened and self._depth <= 0:
                self.reset()
            return line, spans
        if self._mode == "yaml":
            if not _yaml_lineish(line):
                return line, None
            return line, _yaml_spans(line)
        if not line.strip():        # xml : un bloc s'arrete sur une ligne vide
            return line, None
        return line, _tokenize(line, _XML_TOKEN)

    def _start(self, line):
        """Premiere ligne : marqueur explicite, sinon detection automatique."""
        text, mode = _strip_tag(line)
        if mode:
            return text, self._begin(mode, text)
        stripped = text.strip()
        if stripped == "---":                       # document YAML
            self._mode, self._lines = "yaml", 0
            return text, _yaml_spans(text)
        spans = _json_inline(text)
        if spans is None:
            spans = _object_inline(text)
        if spans is not None:
            return text, spans
        idx = _block_open(text)
        if idx is not None:
            self._mode, self._depth, self._opened, self._lines = (
                "json", 1, True, 0)
            return text, [(idx, idx + 1, PUNCT)]
        if _looks_like_xml(stripped):
            return text, _tokenize(text, _XML_TOKEN)
        return text, None

    def _begin(self, mode, text):
        """Ouvre un bloc explicitement marque et colorie sa premiere ligne."""
        if mode == "json":
            spans = _json_inline(text)
            if spans is None:
                spans = _object_inline(text)
            if spans is not None:                   # objet complet sur la ligne
                return spans
            self._mode, self._lines = "json", 0
            self._depth = _depth_delta(text)
            self._opened = self._depth > 0
            return _tokenize(text, _OBJ_TOKEN)
        self._mode, self._lines = mode, 0
        if mode == "yaml":
            return _yaml_spans(text)
        return _tokenize(text, _XML_TOKEN)
