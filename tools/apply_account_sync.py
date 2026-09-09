from pathlib import Path

p = Path('src/app.py')
s = p.read_text(encoding='utf-8')

# Replace any older bridge integration with the read-only screen synchronizer.
s = s.replace('from account_sync import read_snapshot\n', '')
if 'from screen_sync import ScreenSync\n' not in s:
    s = s.replace('from tkinter import ttk, messagebox\n', 'from tkinter import ttk, messagebox\nfrom screen_sync import ScreenSync\n', 1)

needle = "self.calibrating=False; self.player=None\n"
if 'self.screen_sync=ScreenSync()' not in s:
    s = s.replace(needle, needle + "        self.screen_sync=ScreenSync(); self.sync_busy=False\n", 1)

old = "tk.Label(self.account_tab,text='Enter levels and mark quests complete. This stays local to your PC.',bg='#15171a',fg='#bfc5cc').pack(anchor='w',padx=12)"
new = "tk.Label(self.account_tab,text='Read-only screen sync. The Navigator reads visible RuneLite information without clicking, moving the mouse, typing, or controlling the game.',bg='#15171a',fg='#bfc5cc',wraplength=650,justify='left').pack(anchor='w',padx=12)"
s = s.replace(old, new, 1)

needle = "self.button(self.account_tab,'Save levels',self.save_skills,True).pack(anchor='w',padx=12,pady=5); self.button(self.account_tab,'Reset completed quests',self.reset_completed).pack(anchor='w',padx=12,pady=5)"
if 'Scan RuneLite screen' not in s:
    repl = "self.sync_label=tk.Label(self.account_tab,text='Screen sync: ready',bg='#15171a',fg='#e5b95c',justify='left',wraplength=650); self.sync_label.pack(anchor='w',padx=12,pady=5); self.button(self.account_tab,'Scan RuneLite screen',self.sync_screen,True).pack(anchor='w',padx=12,pady=5); " + needle
    s = s.replace(needle, repl, 1)

marker = '    def build_dashboard(self):\n'
if '    def sync_screen(self):\n' not in s:
    method = '''    def sync_screen(self):\n        if self.sync_busy:\n            return\n        if not self.client:\n            self.sync_label.config(text='Screen sync: attach to RuneLite first.',fg='#e5b95c')\n            return\n        if not self.screen_sync.available():\n            self.sync_label.config(text='Screen sync: OCR component is unavailable. Rebuild the latest Windows EXE.',fg='#e57373')\n            return\n        self.sync_busy=True\n        self.sync_label.config(text='Screen sync: scanning RuneLite…',fg='#e5b95c')\n        rect=(self.client[2],self.client[3],self.client[4],self.client[5])\n        names=[q['name'] for q in self.quests]\n        def worker():\n            try:\n                data=self.screen_sync.sync(rect,names)\n                self.root.after(0,lambda:self.apply_screen_sync(data))\n            except Exception as exc:\n                self.root.after(0,lambda:self.finish_screen_sync_error(str(exc)))\n        import threading\n        threading.Thread(target=worker,daemon=True).start()\n\n    def finish_screen_sync_error(self, error):\n        self.sync_busy=False\n        self.sync_label.config(text='Screen sync failed: '+error[:180],fg='#e57373')\n\n    def apply_screen_sync(self, data):\n        self.sync_busy=False\n        skills=data.get('skills',{})\n        changed=[]\n        for name,value in skills.items():\n            if name in self.cfg.get('skills',{}):\n                try:\n                    n=max(1,min(126,int(value)))\n                    if self.cfg['skills'].get(name)!=n:\n                        changed.append(f'{name.title()} {n}')\n                    self.cfg['skills'][name]=n\n                    if hasattr(self,'skill_vars') and name in self.skill_vars:\n                        self.skill_vars[name].set(str(n))\n                except Exception:\n                    pass\n        acct=self.cfg.setdefault('screen_sync',{})\n        acct['timestamp']=data.get('timestamp',0)\n        acct['sources']=data.get('sources',[])\n        acct['quests_seen']=data.get('quests_seen',[])\n        acct['inventory_text']=data.get('inventory_text',[])\n        acct['equipment_text']=data.get('equipment_text',[])\n        acct['bank_text']=data.get('bank_text',[])\n        acct['raw_text']=data.get('raw_text','')\n        self.persist()\n        found=', '.join(changed[:8]) if changed else 'No skill changes detected'\n        if len(changed)>8: found += f' (+{len(changed)-8} more)'\n        seen=len(data.get('quests_seen',[]))\n        sources=', '.join(data.get('sources',[])) or 'screen'\n        self.sync_label.config(text=f'Screen sync: complete\\nRead: {sources}\\nSkills: {found}\\nQuest names visible: {seen}\\nNo clicks or game input were sent.',fg='#79d279')\n        self.refresh_all()\n\n'''
    s = s.replace(marker, method + marker, 1)

# Remove any legacy bridge polling injected by older builds.
s = s.replace('            self.sync_account(False)\n', '')

p.write_text(s, encoding='utf-8')
print('Replaced RuneLite bridge integration with read-only screen sync')
