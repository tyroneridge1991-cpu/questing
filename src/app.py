import ctypes
import ctypes.wintypes as wt
import json
import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox

APP_NAME = 'OSRS Quest Navigator'
ROOT = getattr(sys, '_MEIPASS', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA = os.path.join(ROOT, 'data', 'quests.json')
CONFIG = os.path.join(os.path.expanduser('~'), '.osrs_quest_navigator.json')

user32 = ctypes.windll.user32 if os.name == 'nt' else None

if user32:
    user32.GetWindowTextW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
    user32.GetWindowTextW.restype = ctypes.c_int
    user32.GetWindowTextLengthW.argtypes = [wt.HWND]
    user32.GetWindowTextLengthW.restype = ctypes.c_int
    user32.IsWindowVisible.argtypes = [wt.HWND]
    user32.IsWindowVisible.restype = wt.BOOL
    user32.GetWindowRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]
    user32.GetWindowRect.restype = wt.BOOL
    user32.IsWindow.argtypes = [wt.HWND]
    user32.IsWindow.restype = wt.BOOL
    user32.GetWindowLongW.argtypes = [wt.HWND, ctypes.c_int]
    user32.GetWindowLongW.restype = ctypes.c_long
    user32.SetWindowLongW.argtypes = [wt.HWND, ctypes.c_int, ctypes.c_long]
    user32.SetWindowLongW.restype = ctypes.c_long
    user32.SetWindowPos.argtypes = [wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
    user32.SetWindowPos.restype = wt.BOOL

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_NOACTIVATE = 0x08000000
HWND_TOPMOST = wt.HWND(-1)
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040


def load_json(path, fallback):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return fallback


def save_json(path, value):
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(value, f, indent=2)
    except Exception:
        pass


def window_title(hwnd):
    n = user32.GetWindowTextLengthW(hwnd)
    if n <= 0:
        return ''
    buf = ctypes.create_unicode_buffer(n + 1)
    user32.GetWindowTextW(hwnd, buf, n + 1)
    return buf.value.strip()


def all_windows():
    if os.name != 'nt':
        return []
    result = []
    CALLBACK = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)

    def callback(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            title = window_title(hwnd)
            if title:
                rect = wt.RECT()
                if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                    if rect.right > rect.left and rect.bottom > rect.top:
                        result.append((int(hwnd), title, rect.left, rect.top, rect.right, rect.bottom))
        return True

    cb = CALLBACK(callback)
    user32.EnumWindows(cb, 0)
    return result


def likely_osrs(w):
    low = w[1].lower()
    return any(x in low for x in ('runelite', 'old school runescape', 'oldschool runescape', 'jagex launcher', 'osrs'))


def find_osrs_windows():
    return [w for w in all_windows() if likely_osrs(w)]


def find_osrs_window():
    matches = find_osrs_windows()
    return matches[0] if matches else None


class Navigator:
    def __init__(self, root):
        self.root = root
        data = load_json(DATA, {'quests': []})
        self.quests = data.get('quests', [])
        self.cfg = load_json(CONFIG, {'x': 80, 'y': 80, 'ironman': True, 'completed': [], 'route_points': {}, 'overlay_enabled': True})
        self.selected = self.quests[0] if self.quests else {'name': 'No quest data', 'steps': []}
        self.step = 0
        self.client = None
        self.overlay = None
        self.canvas = None
        self.points = []
        self.iron = tk.BooleanVar(value=self.cfg.get('ironman', True))
        self.overlay_enabled = tk.BooleanVar(value=self.cfg.get('overlay_enabled', True))
        self.root.overrideredirect(False)
        self.root.title(APP_NAME)
        self.root.geometry('620x720')
        self.root.minsize(500, 560)
        self.root.attributes('-topmost', True)
        self.root.configure(bg='#15171a')
        self.build_ui()
        self.load_points()
        self.root.after(300, self.tick)
        self.root.protocol('WM_DELETE_WINDOW', self.close)

    def build_ui(self):
        header = tk.Frame(self.root, bg='#20242a', height=42)
        header.pack(fill='x')
        tk.Label(header, text='OSRS QUEST NAVIGATOR', bg='#20242a', fg='white', font=('Segoe UI', 11, 'bold')).pack(side='left', padx=12, pady=8)
        self.client_label = tk.Label(header, text='OSRS: searching…', bg='#20242a', fg='#e5b95c', font=('Segoe UI', 9, 'bold'))
        self.client_label.pack(side='right', padx=10)

        tabs = ttk.Notebook(self.root)
        tabs.pack(fill='both', expand=True, padx=7, pady=7)
        self.dashboard = tk.Frame(tabs, bg='#15171a')
        self.quest_tab = tk.Frame(tabs, bg='#15171a')
        self.route_tab = tk.Frame(tabs, bg='#15171a')
        self.overlay_tab = tk.Frame(tabs, bg='#15171a')
        self.settings_tab = tk.Frame(tabs, bg='#15171a')
        for tab, name in ((self.dashboard, 'Dashboard'), (self.quest_tab, 'Quests'), (self.route_tab, 'Route'), (self.overlay_tab, 'Overlay'), (self.settings_tab, 'Settings')):
            tabs.add(tab, text=name)

        self.build_dashboard(); self.build_quests(); self.build_route(); self.build_overlay_tab(); self.build_settings()

        footer = tk.Frame(self.root, bg='#20242a'); footer.pack(fill='x')
        tk.Checkbutton(footer, text='Ironman', variable=self.iron, command=self.persist, bg='#20242a', fg='white', selectcolor='#20242a', activebackground='#20242a', activeforeground='white').pack(side='left', padx=8, pady=5)
        tk.Button(footer, text='F8 Hide', command=self.toggle_visible, bg='#30353b', fg='white', relief='flat').pack(side='right', padx=4, pady=5)
        tk.Button(footer, text='F9 Click-through', command=self.toggle_clickthrough, bg='#30353b', fg='white', relief='flat').pack(side='right', padx=4, pady=5)

    def build_dashboard(self):
        tk.Label(self.dashboard, text='Progress', bg='#15171a', fg='white', font=('Segoe UI', 18, 'bold')).pack(anchor='w', padx=14, pady=(16, 6))
        self.progress = tk.Label(self.dashboard, text='', bg='#15171a', fg='#c8cdd3', justify='left'); self.progress.pack(anchor='w', padx=14, pady=6)
        card = tk.Frame(self.dashboard, bg='#20242a'); card.pack(fill='x', padx=14, pady=12)
        self.next_text = tk.Label(card, text='', bg='#20242a', fg='white', justify='left', anchor='w'); self.next_text.pack(fill='x', padx=12, pady=12)
        tk.Button(self.dashboard, text='Attach / find RuneLite', command=self.open_window_picker, bg='#3f6685', fg='white', relief='flat').pack(anchor='w', padx=14, pady=5)
        tk.Button(self.dashboard, text='Recommend next quest', command=self.recommend, bg='#30353b', fg='white', relief='flat').pack(anchor='w', padx=14, pady=5)

    def build_quests(self):
        top = tk.Frame(self.quest_tab, bg='#15171a'); top.pack(fill='x', padx=8, pady=8)
        self.search = tk.StringVar()
        ent = tk.Entry(top, textvariable=self.search, bg='#282d33', fg='white', insertbackground='white', relief='flat'); ent.pack(fill='x', ipady=7); ent.bind('<KeyRelease>', lambda e: self.refresh_quests())
        body = tk.Frame(self.quest_tab, bg='#15171a'); body.pack(fill='both', expand=True, padx=8)
        self.listbox = tk.Listbox(body, bg='#20242a', fg='white', selectbackground='#466984', relief='flat', activestyle='none'); self.listbox.pack(side='left', fill='both', expand=True); self.listbox.bind('<<ListboxSelect>>', self.select_quest)
        sb = tk.Scrollbar(body, command=self.listbox.yview); sb.pack(side='right', fill='y'); self.listbox.config(yscrollcommand=sb.set)
        self.refresh_quests()

    def refresh_quests(self):
        q = self.search.get().lower().strip(); done = set(self.cfg.get('completed', [])); self.listbox.delete(0, 'end')
        for quest in sorted(self.quests, key=lambda x: x.get('name', '')):
            name = quest.get('name', '')
            if q and q not in name.lower(): continue
            self.listbox.insert('end', ('✓ ' if name in done else '  ') + name + ('  [F2P]' if not quest.get('members', True) else ''))

    def select_quest(self, _=None):
        sel = self.listbox.curselection()
        if not sel: return
        raw = self.listbox.get(sel[0]).replace('✓ ', '', 1).replace('  ', '', 1)
        raw = raw.replace('  [F2P]', '')
        q = next((x for x in self.quests if x.get('name') == raw), None)
        if q:
            self.selected = q; self.step = 0; self.load_points(); self.refresh_route(); self.update_dashboard()

    def build_route(self):
        self.route_title = tk.Label(self.route_tab, text='', bg='#15171a', fg='white', font=('Segoe UI', 16, 'bold')); self.route_title.pack(anchor='w', padx=12, pady=12)
        self.route_info = tk.Label(self.route_tab, text='', bg='#15171a', fg='#c8cdd3', justify='left', anchor='w', wraplength=560); self.route_info.pack(fill='x', padx=12)
        self.steps = tk.Listbox(self.route_tab, bg='#20242a', fg='white', selectbackground='#3f6685', relief='flat'); self.steps.pack(fill='both', expand=True, padx=12, pady=10)
        bar = tk.Frame(self.route_tab, bg='#15171a'); bar.pack(fill='x', padx=12, pady=8)
        tk.Button(bar, text='← Previous', command=self.prev_step, bg='#30353b', fg='white', relief='flat').pack(side='left')
        tk.Button(bar, text='Complete step →', command=self.advance_step, bg='#3f6685', fg='white', relief='flat').pack(side='right')
        self.refresh_route()

    def refresh_route(self):
        q = self.selected; steps = q.get('steps') or [{'title': 'Route not mapped', 'destination': 'Quest guide', 'notes': 'Detailed route data is not yet available.'}]
        idx = min(self.step, len(steps)-1)
        self.route_title.config(text=q.get('name', 'Quest'))
        self.route_info.config(text=f"{q.get('difficulty','Unknown')} • {'Members' if q.get('members', True) else 'Free-to-play'} • {'Ironman-aware' if self.iron.get() else 'Standard'}\nPrerequisites: {', '.join(q.get('prerequisites', [])) or 'None'}\nNEXT: {steps[idx].get('destination','Unknown')}\n{steps[idx].get('notes','')}")
        self.steps.delete(0, 'end')
        for i, s in enumerate(steps):
            mark = '✓' if i < self.step else ('→' if i == self.step else '○')
            self.steps.insert('end', f"{mark}  {i+1}. {s.get('title','Objective')} — {s.get('destination','Unknown')}")
        self.steps.selection_set(idx); self.steps.see(idx)

    def advance_step(self):
        if self.step < len(self.selected.get('steps', [])): self.step += 1
        self.refresh_route(); self.update_dashboard()

    def prev_step(self):
        self.step = max(0, self.step - 1); self.refresh_route(); self.update_dashboard()

    def recommend(self):
        done = set(self.cfg.get('completed', [])); candidates=[]
        for q in self.quests:
            if q.get('name') in done: continue
            if set(q.get('prerequisites', [])) <= done:
                candidates.append(q)
        if candidates:
            self.selected = sorted(candidates, key=lambda x:(x.get('members', True), not bool(x.get('steps')), len(x.get('prerequisites', []))))[0]
            self.step=0; self.load_points(); self.refresh_route(); self.update_dashboard()

    def update_dashboard(self):
        done=len(set(self.cfg.get('completed', []))); total=len(self.quests); steps=self.selected.get('steps') or []
        nxt=steps[min(self.step,len(steps)-1)].get('destination','Quest guide') if steps else 'Detailed route pending'
        self.progress.config(text=f'Quest catalog: {total}\nCompleted: {done}\n\nClient: {"attached" if self.client else "not detected"}\nOverlay: {"ON" if self.overlay_enabled.get() else "OFF"}')
        self.next_text.config(text=f"CURRENT QUEST\n{self.selected.get('name','Quest')}\n\nNEXT DESTINATION\n{nxt}")

    def build_overlay_tab(self):
        tk.Label(self.overlay_tab, text='RuneLite connection', bg='#15171a', fg='white', font=('Segoe UI',16,'bold')).pack(anchor='w', padx=12, pady=12)
        self.client_status=tk.Label(self.overlay_tab,text='Searching for RuneLite…',bg='#20242a',fg='#c8cdd3',justify='left',anchor='w'); self.client_status.pack(fill='x',padx=12,pady=8)
        tk.Button(self.overlay_tab,text='Select RuneLite window',command=self.open_window_picker,bg='#3f6685',fg='white',relief='flat').pack(anchor='w',padx=12,pady=5)
        tk.Checkbutton(self.overlay_tab,text='Show route overlay',variable=self.overlay_enabled,command=self.toggle_overlay,bg='#15171a',fg='white',selectcolor='#15171a',activebackground='#15171a',activeforeground='white').pack(anchor='w',padx=12,pady=5)
        tk.Label(self.overlay_tab,text='The route layer is click-through, while this Navigator window remains clickable. It does not send clicks or keyboard input to RuneLite.',bg='#15171a',fg='#bfc5cc',justify='left',wraplength=560).pack(anchor='w',padx=12,pady=10)

    def open_window_picker(self):
        wins = all_windows()
        if not wins:
            messagebox.showerror('Window selection','No visible Windows were found.')
            return
        dlg=tk.Toplevel(self.root); dlg.title('Select RuneLite / OSRS window'); dlg.geometry('650x430'); dlg.transient(self.root); dlg.grab_set(); dlg.configure(bg='#15171a')
        tk.Label(dlg,text='Select the game window',bg='#15171a',fg='white',font=('Segoe UI',13,'bold')).pack(anchor='w',padx=12,pady=10)
        frame=tk.Frame(dlg,bg='#15171a'); frame.pack(fill='both',expand=True,padx=12)
        lb=tk.Listbox(frame,bg='#20242a',fg='white',selectbackground='#466984',relief='flat'); lb.pack(side='left',fill='both',expand=True)
        sb=tk.Scrollbar(frame,command=lb.yview); sb.pack(side='right',fill='y'); lb.config(yscrollcommand=sb.set)
        for w in wins:
            tag='  ← likely OSRS' if likely_osrs(w) else ''
            lb.insert('end',f'{w[1]}{tag}')
        likely=[i for i,w in enumerate(wins) if likely_osrs(w)]
        if likely: lb.selection_set(likely[0]); lb.see(likely[0])
        def select():
            s=lb.curselection()
            if not s:return
            self.client=wins[s[0]]; self.on_client_attached(); dlg.destroy()
        tk.Button(dlg,text='Use selected window',command=select,bg='#3f6685',fg='white',relief='flat').pack(side='right',padx=12,pady=10)
        tk.Button(dlg,text='Cancel',command=dlg.destroy,bg='#30353b',fg='white',relief='flat').pack(side='right',pady=10)

    def on_client_attached(self):
        self.client_label.config(text='OSRS: attached',fg='#79d279')
        self.client_status.config(text=f'Attached to: {self.client[1]}\nSize: {self.client[4]-self.client[2]} × {self.client[5]-self.client[3]}')
        self.ensure_overlay(); self.position_overlay(); self.raise_navigator(); self.update_dashboard()

    def ensure_overlay(self):
        if self.overlay and self.overlay.winfo_exists():
            self.make_clickthrough(self.overlay)
            return
        self.overlay=tk.Toplevel(self.root); self.overlay.overrideredirect(True); self.overlay.attributes('-topmost',True); self.overlay.configure(bg='#010101')
        try:self.overlay.attributes('-transparentcolor','#010101')
        except tk.TclError:self.overlay.attributes('-alpha',0.01)
        self.canvas=tk.Canvas(self.overlay,bg='#010101',highlightthickness=0); self.canvas.pack(fill='both',expand=True); self.make_clickthrough(self.overlay)

    def make_clickthrough(self,win):
        if os.name!='nt':return
        hwnd=win.winfo_id()
        ex=user32.GetWindowLongW(hwnd,GWL_EXSTYLE)
        ex |= WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_NOACTIVATE
        user32.SetWindowLongW(hwnd,GWL_EXSTYLE,ex)
        user32.SetWindowPos(hwnd,HWND_TOPMOST,0,0,0,0,SWP_NOMOVE|SWP_NOSIZE|SWP_NOACTIVATE|SWP_SHOWWINDOW)

    def raise_navigator(self):
        if os.name!='nt': return
        hwnd=self.root.winfo_id()
        ex=user32.GetWindowLongW(hwnd,GWL_EXSTYLE)
        ex &= ~WS_EX_TRANSPARENT
        user32.SetWindowLongW(hwnd,GWL_EXSTYLE,ex)
        user32.SetWindowPos(hwnd,HWND_TOPMOST,0,0,0,0,SWP_NOMOVE|SWP_NOSIZE|SWP_NOACTIVATE|SWP_SHOWWINDOW)
        self.root.lift()

    def position_overlay(self):
        if not self.client or not self.overlay:return
        _,_,l,t,r,b=self.client; self.overlay.geometry(f'{max(1,r-l)}x{max(1,b-t)}+{l}+{t}'); self.overlay.deiconify(); self.draw_overlay(); self.raise_navigator()

    def draw_overlay(self):
        if not self.canvas:return
        self.canvas.delete('all')
        if not self.overlay_enabled.get():return
        pts=[(int(x),int(y)) for x,y in self.points]
        if len(pts)>1:self.canvas.create_line(*[v for p in pts for v in p],fill='#ffd34e',width=4,smooth=True)
        for i,(x,y) in enumerate(pts,1):
            self.canvas.create_oval(x-7,y-7,x+7,y+7,outline='#ffd34e',width=3); self.canvas.create_text(x+13,y,text=str(i),fill='white',anchor='w')

    def build_settings(self):
        tk.Label(self.settings_tab,text='Window controls',bg='#15171a',fg='white',font=('Segoe UI',16,'bold')).pack(anchor='w',padx=12,pady=12)
        tk.Label(self.settings_tab,text='Use the normal Windows title bar buttons to minimize, maximize/restore, and close the Navigator.\nF8 hides/shows it. F9 toggles click-through on the Navigator window.',bg='#15171a',fg='#bfc5cc',justify='left').pack(anchor='w',padx=12,pady=8)
        tk.Button(self.settings_tab,text='Select RuneLite / OSRS window',command=self.open_window_picker,bg='#3f6685',fg='white',relief='flat').pack(anchor='w',padx=12,pady=8)

    def load_points(self):
        self.points=[tuple(p) for p in self.cfg.get('route_points',{}).get(self.selected.get('name',''),[])]

    def toggle_overlay(self):
        if self.overlay_enabled.get(): self.ensure_overlay(); self.position_overlay()
        elif self.overlay:self.overlay.withdraw()
        self.persist()

    def tick(self):
        if self.client and not user32.IsWindow(self.client[0]): self.client=None
        if not self.client:
            found=find_osrs_window()
            if found:
                self.client=found; self.on_client_attached()
            else:
                self.client_label.config(text='OSRS: not found',fg='#df7b6e')
                self.update_dashboard()
        else:
            rect=wt.RECT()
            if user32.GetWindowRect(self.client[0],ctypes.byref(rect)):
                self.client=(self.client[0],self.client[1],rect.left,rect.top,rect.right,rect.bottom); self.position_overlay()
        self.root.after(1000,self.tick)

    def toggle_visible(self): self.root.withdraw() if self.root.state()!='withdrawn' else self.root.deiconify()
    def toggle_clickthrough(self):
        if os.name!='nt':return
        hwnd=self.root.winfo_id(); ex=user32.GetWindowLongW(hwnd,GWL_EXSTYLE)
        if ex & WS_EX_TRANSPARENT:
            ex &= ~WS_EX_TRANSPARENT
        else:
            ex |= WS_EX_TRANSPARENT
        user32.SetWindowLongW(hwnd,GWL_EXSTYLE,ex)
        self.raise_navigator()
    def persist(self):
        self.cfg['ironman']=self.iron.get(); self.cfg['overlay_enabled']=self.overlay_enabled.get(); self.cfg['x']=self.root.winfo_x(); self.cfg['y']=self.root.winfo_y(); save_json(CONFIG,self.cfg)
    def close(self):
        self.persist()
        if self.overlay:self.overlay.destroy()
        self.root.destroy()


if __name__ == '__main__':
    root=tk.Tk(); Navigator(root); root.bind('<F8>',lambda e:root.event_generate('<<ToggleVisible>>')); root.mainloop()
