"""Lanceur de la webapp CRM : demarre le serveur et ouvre le navigateur.

Double-cliquer sur Cabinet-CRM-Web.exe ouvre l'application dans le navigateur
par defaut (Chrome). Laisser la fenetre noire ouverte tant qu'on utilise l'app ;
la fermer arrete le serveur.

Variables d'environnement optionnelles :
    CRM_PORT  port d'ecoute (defaut 8550)
    CRM_HOST  0.0.0.0 pour acceder depuis un autre appareil du reseau local
"""

import os
import sys

# Assure que la racine du projet (dossier de ce script) est sur sys.path, meme
# avec un Python "embeddable" (fichier ._pth) qui n'ajoute pas le dossier du
# script automatiquement -- sinon "import crm" echoue (No module named 'crm').
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Active le mode web dans crm.app.run().
os.environ.setdefault("CRM_WEB", "1")

from crm.app import run

if __name__ == "__main__":
    print("=" * 56)
    print("  Cabinet Dr Aslem Gouiaa - Application CRM (web)")
    print("=" * 56)
    print("  Le navigateur va s'ouvrir automatiquement.")
    print("  Adresse : http://localhost:" + os.environ.get("CRM_PORT", "8550"))
    print("  GARDEZ CETTE FENETRE OUVERTE pendant l'utilisation.")
    print("  Fermez-la pour arreter l'application.")
    print("=" * 56)
    run()
