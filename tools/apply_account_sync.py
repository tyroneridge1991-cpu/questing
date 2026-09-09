from pathlib import Path

p = Path('src/app.py')
s = p.read_text(encoding='utf-8')

if 'from account_sync import read_snapshot' not in s:
    s = s.replace('from tkinter import ttk, messagebox\n', 'from tkinter import ttk, messagebox\nfrom account_sync import read_snapshot\n', 1)

needle = "self.calibrating=False; self.player=None\n"
if 'self.sync_data=None' not in s:
    s = s.replace(needle, needle + "        self.sync_data=None; self.last_sync_timestamp=0\n", 1)

needle = "self.button(self.account_tab,'Save levels',self.save_skills,True).pack(anchor='w',padx=12,pady=5); self.button(self.account_tab,'Reset completed quests',self.reset_completed).pack(anchor='w',padx=12,pady=5)"
if 'Sync from RuneLite' not in s:
    repl = "self.sync_label=tk.Label(self.account_tab,text='RuneLite sync: waiting for bridge plugin',bg='#15171a',fg='#e5b95c',justify='left'); self.sync_label.pack(anchor='w',padx=12,pady=5); self.button(self.account_tab,'Sync from RuneLite',lambda:self.sync_account(True),True).pack(anchor='w',padx=12,pady=5); " + needle
    s = s.replace(needle, repl, 1)

marker = '    def build_dashboard(self):\n'
if '    def sync_account(self, refresh=True):\n' not in s:
    method = '''    def sync_account(self, refresh=True):\n        data=read_snapshot()\n        if not data:\n            if hasattr(self,'sync_label'): self.sync_label.config(text='RuneLite sync: no local snapshot found. Install/enable Quest Navigator Account Sync in RuneLite.')\n            return False\n        self.sync_data=data\n        ts=data.get('timestamp',0)\n        if ts <= self.last_sync_timestamp and not refresh:\n            return True\n        self.last_sync_timestamp=ts\n        skills=data.get('skills',{})\n        for name,value in skills.items():\n            if name in self.cfg.get('skills',{}):\n                try:self.cfg['skills'][name]=max(1,int(value.get('level',self.cfg['skills'][name])))\n                except Exception:pass\n        quest_states=data.get('quests',{})\n        finished=[name for name,state in quest_states.items() if str(state).upper()=='FINISHED']\n        if finished:\n            self.cfg['completed']=sorted(set(self.cfg.get('completed',[])) | set(finished))\n        self.cfg['account_sync']={\n            'username':data.get('username',''),\n            'location':data.get('location',{}),\n            'inventory':data.get('inventory',{}),\n            'equipment':data.get('equipment',{}),\n            'bank':data.get('bank',{}),\n            'bankAvailable':data.get('bankAvailable',False),\n            'account':data.get('account',{}),\n            'timestamp':ts\n        }\n        self.persist()\n        if hasattr(self,'sync_label'):\n            name=data.get('username') or 'character'\n            bank='available' if data.get('bankAvailable') else 'not currently available'\n            self.sync_label.config(text=f"RuneLite sync: {name}\\nSkills, quest states, inventory, equipment and bank snapshot synced.\\nBank: {bank} • Last update: {time.ctime(ts/1000) if ts else 'unknown'}",fg='#79d279')\n        if refresh:\n            self.refresh_all()\n        return True\n\n'''
    s = s.replace(marker, method + marker, 1)

# Add time import for the status line.
if 'import time\n' not in s:
    s = s.replace('import os\n', 'import os\nimport time\n', 1)

# Poll the local snapshot every tick without recursive refresh.
needle = '    def tick(self):\n        try:\n'
if 'self.sync_account(False)' not in s:
    s = s.replace(needle, '    def tick(self):\n        try:\n            self.sync_account(False)\n', 1)

p.write_text(s, encoding='utf-8')
print('Account sync patch applied')
