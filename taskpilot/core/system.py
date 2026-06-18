"""Constantes et indicateurs lies a la plateforme."""

import os
import subprocess

#: Vrai sous Windows.
IS_WIN = os.name == "nt"

#: Nombre de coeurs logiques (au moins 1), utilise pour le calcul du CPU%.
NCPU = os.cpu_count() or 1

#: Drapeau de creation de process empechant l'ouverture d'une console
#: (Windows uniquement ; 0 ailleurs).
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if IS_WIN else 0
