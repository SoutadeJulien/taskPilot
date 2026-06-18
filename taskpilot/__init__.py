"""TaskPilot — pilote tes tasks VS Code et tes process.

Application graphique (Tkinter, sans dependance externe) qui :
  - lance les tasks VS Code d'un projet avec leurs consoles integrees,
    puis les tue PROPREMENT avec tout leur arbre de process (ce que la
    poubelle de VS Code ne fait pas) ;
  - liste, surveille et tue les process Node.

Le package est decoupe en deux couches :
  - ``taskpilot.core`` : logique metier, sans aucune dependance a Tkinter ;
  - ``taskpilot.ui``   : couche de presentation (Tkinter).
"""

__version__ = "2.0.0"
