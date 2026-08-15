import json, os, shutil, sqlite3, subprocess, sys, time, zipfile, logging
from pathlib import Path
from datetime import datetime
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import *
from PySide6.QtGui import QPixmap

APP = Path(os.getenv('LOCALAPPDATA') or Path.home()) / 'OpenGameLauncher'
APP.mkdir(parents=True, exist_ok=True)
(APP/'backups').mkdir(exist_ok=True)
logging.basicConfig(filename=APP/'launcher.log', level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(message)s')
DB = APP/'launcher.db'

class DBStore:
    def __init__(self):
        self.c = sqlite3.connect(DB)
        self.c.row_factory = sqlite3.Row
        self.c.execute('PRAGMA foreign_keys=ON')
        self.c.executescript('''
        CREATE TABLE IF NOT EXISTS profiles(id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, avatar TEXT DEFAULT '👤');
        CREATE TABLE IF NOT EXISTS games(id INTEGER PRIMARY KEY, profile_id INTEGER NOT NULL, name TEXT NOT NULL,
          exe TEXT NOT NULL, install_dir TEXT, platform TEXT DEFAULT 'Local', save_dir TEXT, cover TEXT,
          args TEXT DEFAULT '', favorite INTEGER DEFAULT 0, play_seconds INTEGER DEFAULT 0, last_played TEXT,
          FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS backups(id INTEGER PRIMARY KEY, game_id INTEGER NOT NULL, archive TEXT NOT NULL,
          created TEXT NOT NULL, size INTEGER DEFAULT 0, FOREIGN KEY(game_id) REFERENCES games(id) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS sessions(id INTEGER PRIMARY KEY, game_id INTEGER, started TEXT, seconds INTEGER);
        ''')
        if self.c.execute('SELECT COUNT(*) FROM profiles').fetchone()[0] == 0:
            self.c.execute("INSERT INTO profiles(name) VALUES('Default')"); self.c.commit()
    def profiles(self): return self.c.execute('SELECT * FROM profiles ORDER BY id').fetchall()
    def add_profile(self,n): self.c.execute('INSERT INTO profiles(name) VALUES(?)',(n,)); self.c.commit()
    def del_profile(self,i): self.c.execute('DELETE FROM profiles WHERE id=?',(i,)); self.c.commit()
    def games(self,p): return self.c.execute('SELECT * FROM games WHERE profile_id=? ORDER BY favorite DESC,name',(p,)).fetchall()
    def add_game(self,g):
        self.c.execute('''INSERT INTO games(profile_id,name,exe,install_dir,platform,save_dir,cover,args)
          VALUES(?,?,?,?,?,?,?,?)''',g); self.c.commit()
    def update_game(self,g):
        self.c.execute('''UPDATE games SET name=?,exe=?,install_dir=?,platform=?,save_dir=?,cover=?,args=?,favorite=?,play_seconds=?,last_played=? WHERE id=?''',g); self.c.commit()
    def del_game(self,i): self.c.execute('DELETE FROM games WHERE id=?',(i,)); self.c.commit()
    def backups(self,g): return self.c.execute('SELECT * FROM backups WHERE game_id=? ORDER BY created DESC',(g,)).fetchall()
    def add_backup(self,g,a,size):
        self.c.execute('INSERT INTO backups(game_id,archive,created,size) VALUES(?,?,?,?)',(g,a,datetime.now().isoformat(timespec='seconds'),size)); self.c.commit()
    def export_json(self,path,pid):
        data={'profiles':[dict(x) for x in self.profiles()], 'games':[dict(x) for x in self.games(pid)]}
        Path(path).write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf8')
    def import_json(self,path,pid):
        data=json.loads(Path(path).read_text(encoding='utf8'))
        for g in data.get('games',[]):
            self.add_game((pid,g['name'],g['exe'],g.get('install_dir',''),g.get('platform','Local'),g.get('save_dir',''),g.get('cover',''),g.get('args','')))

class BackupManager:
    def __init__(self,db): self.db=db
    def make(self,game):
        src=game['save_dir']
        if not src or not os.path.isdir(src): raise ValueError('Le dossier de sauvegarde n’est pas configuré ou n’existe plus.')
        safe=lambda s: ''.join(c if c.isalnum() or c in ' ._-()' else '_' for c in s).strip() or 'Game'
        out=APP/'backups'/safe(str(game['profile_id']))/safe(game['name']); out.mkdir(parents=True,exist_ok=True)
        archive=out/(datetime.now().strftime('%Y%m%d_%H%M%S')+'.zip')
        with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
            for p in Path(src).rglob('*'):
                if p.is_file(): z.write(p,p.relative_to(src))
        self.db.add_backup(game['id'],str(archive),archive.stat().st_size); return archive
    def restore(self,game,archive):
        dst=game['save_dir']
        if not dst: raise ValueError('Configure le dossier de sauvegarde avant restauration.')
        Path(dst).mkdir(parents=True,exist_ok=True)
        with zipfile.ZipFile(archive) as z: z.extractall(dst)

class GameDialog(QDialog):
    def __init__(self,parent=None,g=None):
        super().__init__(parent); self.setWindowTitle('Jeu'); self.resize(600,420)
        self.name=QLineEdit(g['name'] if g else '')
        self.exe=QLineEdit(g['exe'] if g else ''); self.install=QLineEdit(g['install_dir'] if g else '')
        self.platform=QLineEdit(g['platform'] if g else 'Local'); self.save=QLineEdit(g['save_dir'] if g else '')
        self.cover=QLineEdit(g['cover'] if g else ''); self.args=QLineEdit(g['args'] if g else '')
        form=QFormLayout(); form.addRow('Nom',self.name)
        for label,w,folder in [('Exécutable',self.exe,False),('Dossier d’installation',self.install,True),('Dossier des sauvegardes',self.save,True),('Jaquette',self.cover,False),('Arguments',self.args,False)]:
            row=QHBoxLayout(); row.addWidget(w); b=QPushButton('Choisir'); row.addWidget(b)
            if folder: b.clicked.connect(lambda _,x=w:self.pick_folder(x))
            else: b.clicked.connect(lambda _,x=w:self.pick_file(x))
            form.addRow(label,row)
        form.addRow('Plateforme',self.platform)
        ok=QPushButton('Enregistrer'); ok.clicked.connect(self.accept); form.addRow('',ok); self.setLayout(form)
    def pick_file(self,w):
        p,_=QFileDialog.getOpenFileName(self,'Choisir',filter='Programmes (*.exe);;Tous (*.*)');
        if p:w.setText(p)
    def pick_folder(self,w):
        p=QFileDialog.getExistingDirectory(self,'Choisir un dossier');
        if p:w.setText(p)
    def data(self): return [self.name.text().strip(),self.exe.text().strip(),self.install.text().strip(),self.platform.text().strip() or 'Local',self.save.text().strip(),self.cover.text().strip(),self.args.text().strip()]

class Main(QMainWindow):
    def __init__(self):
        super().__init__(); self.db=DBStore(); self.back=BackupManager(self.db); self.profile=None; self.current=None; self.started=0
        self.setWindowTitle('OpenGameLauncher'); self.resize(1180,760); self.build(); self.load_profiles()
    def build(self):
        central=QWidget(); root=QHBoxLayout(central); self.setCentralWidget(central)
        side=QVBoxLayout(); title=QLabel('OPEN GAME\nLAUNCHER'); title.setObjectName('title'); side.addWidget(title)
        side.addWidget(QLabel('PROFIL')); self.profiles=QComboBox(); side.addWidget(self.profiles)
        for text,fn in [('+ Nouveau profil',self.new_profile),('Supprimer le profil',self.delete_profile),('💾 Sauvegardes',self.backups_page),('⚙ Paramètres',self.settings)]:
            b=QPushButton(text); b.clicked.connect(fn); side.addWidget(b)
        side.addStretch(); side.addWidget(QLabel('V1.0 • Open source')); root.addLayout(side,1)
        main=QVBoxLayout(); header=QHBoxLayout(); h=QLabel('Ma bibliothèque'); h.setObjectName('heading'); header.addWidget(h); self.search=QLineEdit(); self.search.setPlaceholderText('Rechercher…'); header.addWidget(self.search); add=QPushButton('+ Ajouter un jeu'); add.clicked.connect(self.add_game); header.addWidget(add); main.addLayout(header)
        self.list=QListWidget(); self.list.itemSelectionChanged.connect(self.selected); main.addWidget(self.list)
        actions=QHBoxLayout()
        for t,fn in [('▶ Lancer',self.launch),('⭐ Favori',self.favorite),('💾 Backup',self.backup),('♻ Restaurer',self.restore),('✏ Modifier',self.edit),('🗑 Supprimer',self.delete_game)]:
            b=QPushButton(t); b.clicked.connect(fn); actions.addWidget(b)
        main.addLayout(actions); self.status=QLabel(''); main.addWidget(self.status); root.addLayout(main,4)
        self.profiles.currentIndexChanged.connect(self.profile_changed); self.search.textChanged.connect(self.refresh)
        self.setStyleSheet('''QWidget{background:#1d2026;color:#e8eaed;font-size:14px} QLineEdit,QComboBox,QListWidget{background:#252932;border:1px solid #3b4048;border-radius:7px;padding:8px} QPushButton{background:#303640;border:0;border-radius:7px;padding:9px} QPushButton:hover{background:#3b4350} #title{font-size:25px;font-weight:700} #heading{font-size:28px;font-weight:700} QListWidget::item{padding:18px;margin:5px;background:#252932;border-radius:8px} QListWidget::item:selected{background:#33415a}''')
    def load_profiles(self):
        self.profiles.clear()
        for p in self.db.profiles(): self.profiles.addItem(f"{p['avatar']} {p['name']}",p['id'])
        if self.profiles.count(): self.profiles.setCurrentIndex(0)
    def profile_changed(self):
        self.profile=self.profiles.currentData(); self.refresh()
    def refresh(self):
        self.list.clear(); self.current=None
        if not self.profile:return
        q=self.search.text().lower(); games=[dict(x) for x in self.db.games(self.profile)]
        for g in games:
            if q and q not in g['name'].lower():continue
            it=QListWidgetItem(('⭐ ' if g['favorite'] else '')+g['name']+f"\n{g['platform']}  •  {g['play_seconds']//3600}h {(g['play_seconds']%3600)//60}min")
            it.setData(Qt.UserRole,g); self.list.addItem(it)
        self.status.setText(f'{self.list.count()} jeu(x)')
    def selected(self): self.current=self.list.currentItem().data(Qt.UserRole) if self.list.currentItem() else None
    def add_game(self):
        if not self.profile:return
        d=GameDialog(self)
        if d.exec() and d.exe.text(): self.db.add_game((self.profile,*d.data())); self.refresh()
    def edit(self):
        if not self.current:return
        d=GameDialog(self,self.current)
        if d.exec():
            x=d.data(); self.db.update_game((x[0],x[1],x[2],x[3],x[4],x[5],x[6],self.current['favorite'],self.current['play_seconds'],self.current['last_played'],self.current['id'])); self.refresh()
    def delete_game(self):
        if self.current and QMessageBox.question(self,'Supprimer','Retirer ce jeu du launcher ?')==QMessageBox.Yes:self.db.del_game(self.current['id']); self.refresh()
    def favorite(self):
        if self.current:
            self.current['favorite']=0 if self.current['favorite'] else 1; self.db.update_game((self.current['name'],self.current['exe'],self.current['install_dir'],self.current['platform'],self.current['save_dir'],self.current['cover'],self.current['args'],self.current['favorite'],self.current['play_seconds'],self.current['last_played'],self.current['id'])); self.refresh()
    def launch(self):
        g=self.current
        if not g:return
        if not os.path.isfile(g['exe']): QMessageBox.warning(self,'Jeu introuvable','L’exécutable n’existe plus. Modifie le jeu après réinstallation.'); return
        try:
            if g['save_dir'] and os.path.isdir(g['save_dir']): self.back.make(g)
            cmd=[g['exe']]+([x for x in g['args'].split(' ') if x] if g['args'] else [])
            start=time.time(); p=subprocess.Popen(cmd,cwd=g['install_dir'] or os.path.dirname(g['exe'])); self.status.setText(f'{g["name"]} lancé.')
            def finished():
                sec=int(time.time()-start); fresh=dict(g); fresh['play_seconds']+=sec; fresh['last_played']=datetime.now().isoformat(timespec='seconds')
                self.db.update_game((fresh['name'],fresh['exe'],fresh['install_dir'],fresh['platform'],fresh['save_dir'],fresh['cover'],fresh['args'],fresh['favorite'],fresh['play_seconds'],fresh['last_played'],fresh['id']))
                try:
                    if fresh['save_dir'] and os.path.isdir(fresh['save_dir']): self.back.make(fresh)
                except Exception as e: logging.exception(e)
                self.refresh()
            QTimer.singleShot(500,lambda:self.watch(p,finished))
        except Exception as e: QMessageBox.critical(self,'Erreur',str(e))
    def watch(self,p,fn):
        if p.poll() is None: QTimer.singleShot(500,lambda:self.watch(p,fn))
        else: fn()
    def backup(self):
        if not self.current:return
        try:self.back.make(self.current); QMessageBox.information(self,'Backup','Sauvegarde créée dans les données du launcher.')
        except Exception as e: QMessageBox.warning(self,'Backup',str(e))
    def restore(self):
        if not self.current:return
        bs=self.db.backups(self.current['id'])
        if not bs: QMessageBox.information(self,'Restaurer','Aucune sauvegarde disponible.'); return
        items=[f"{b['created']} • {b['size']/1024/1024:.2f} MB" for b in bs]; x,ok=QInputDialog.getItem(self,'Restaurer','Choisir une sauvegarde',items,0,False)
        if ok:
            try:self.back.restore(self.current,bs[items.index(x)]['archive']); QMessageBox.information(self,'Restaurer','Sauvegarde restaurée.')
            except Exception as e: QMessageBox.warning(self,'Restaurer',str(e))
    def new_profile(self):
        n,ok=QInputDialog.getText(self,'Nouveau profil','Nom :')
        if ok and n.strip():
            try:self.db.add_profile(n.strip()); self.load_profiles()
            except Exception as e: QMessageBox.warning(self,'Profil',str(e))
    def delete_profile(self):
        if self.profiles.count()<=1:return
        if QMessageBox.question(self,'Supprimer','Supprimer ce profil et sa bibliothèque ?')==QMessageBox.Yes:self.db.del_profile(self.profile); self.load_profiles()
    def backups_page(self):
        if not self.profile:return
        total=sum(len(self.db.backups(g['id'])) for g in map(dict,self.db.games(self.profile)))
        QMessageBox.information(self,'Sauvegardes',f'{total} backup(s).\n\nStockage : {APP / "backups"}')
    def settings(self):
        path,_=QFileDialog.getSaveFileName(self,'Exporter la bibliothèque',filter='JSON (*.json)')
        if path:
            self.db.export_json(path,self.profile); QMessageBox.information(self,'Export','Bibliothèque exportée.')

def main():
    app=QApplication(sys.argv); app.setApplicationName('OpenGameLauncher'); w=Main(); w.show(); sys.exit(app.exec())
if __name__=='__main__': main()
