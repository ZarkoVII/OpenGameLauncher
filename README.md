# OpenGameLauncher v1.0

Launcher open source pour jeux installés localement, avec profils multiples et sauvegardes persistantes.

## V0.1 → V1.0
- V0.1 : bibliothèque, ajout d'un `.exe`, lancement.
- V0.2 : profils, favoris, recherche, temps de jeu.
- V0.3 : sauvegardes ZIP persistantes, restauration après réinstallation.
- V0.4 : édition des jeux, arguments, dossiers d'installation.
- V0.5 : import/export de bibliothèque.
- V0.6 : statistiques et historique.
- V0.7 : thèmes clair/sombre, paramètres.
- V0.8 : détection de bibliothèques Steam/Epic quand disponibles.
- V0.9 : logs, validation des chemins, nettoyage des backups.
- V1.0 : interface stable, export/import, backups indépendants des installations.

## Lancer
Windows 10/11 recommandé. Python 3.11+.

```powershell
py -m pip install -r requirements.txt
py main.py
```

Pour créer un `.exe` :
```powershell
py -m pip install pyinstaller
pyinstaller --noconsole --onefile --name OpenGameLauncher main.py
```

Le launcher ne fournit aucun jeu et ne contourne aucune licence, DRM ou protection. Il lance seulement les programmes locaux configurés par l'utilisateur.
