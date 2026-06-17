"""Lanceur de l'application CRM (interface Flet).

Variante navigateur : crm_web.py.

Option `--reset` : remise a zero de la base et des notes generees (utilisable
depuis l'exe distribue, sans Python installe). Reutilise crm.reset (confirmation
comprise) ; passer aussi `--yes` pour ne pas demander de confirmation.
"""

import os
import sys

# Assure que la racine du projet (dossier de ce script) est sur sys.path, meme
# avec un Python "embeddable" (fichier ._pth) qui n'ajoute pas le dossier du
# script automatiquement -- sinon "import crm" echoue (No module named 'crm').
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    if "--reset" in sys.argv[1:]:
        from crm.reset import main as reset_main

        # Transmet les autres options (ex. --yes) a crm.reset.
        rest = [a for a in sys.argv[1:] if a != "--reset"]
        sys.exit(reset_main(rest))

    from crm.app import run

    run()
