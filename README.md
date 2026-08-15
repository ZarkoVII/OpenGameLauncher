OpenGameLauncher v1.0

Open-source launcher for locally installed games, with multiple profiles and persistent save backups.

V0.1 → V1.0
V0.1: library, .exe addition, launching.
V0.2: profiles, favorites, search, playtime tracking.
V0.3: persistent ZIP save backups, restoration after reinstallation.
V0.4: game editing, launch arguments, installation directories.
V0.5: library import/export.
V0.6: statistics and history.
V0.7: light/dark themes, settings.
V0.8: Steam/Epic library detection when available.
V0.9: logs, path validation, backup cleanup.
V1.0: stable interface, import/export, backups independent from game installations.
Running

Windows 10/11 recommended. Python 3.11+.

py -m pip install -r requirements.txt
py main.py

To create an .exe:

py -m pip install pyinstaller
pyinstaller --noconsole --onefile --name OpenGameLauncher main.py

The launcher does not provide any games and does not bypass any license, DRM, or protection. It only launches local programs configured by the user.
