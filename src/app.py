import ctypes
import ctypes.wintypes
import json
import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

APP_NAME = 'OSRS Quest Navigator'
ROOT = getattr(sys, '_MEIPASS', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA = os.path.join(ROOT, 'data', 'quests.json')
CONFIG = os.path.join(os.path.expanduser('~'), '.osrs_quest_navigator.json')
user32 = ctypes.windll.user32 if os.name == 'nt' else None


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


def find_osrs_window():
    if os.name != 'nt':
        return None
    matches = []
    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def callback(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value
        low = title.lower()
        if 'old school runescape' in low or low == 'runelite':
            rect = ctypes.wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            matches.append((hwnd, title, rect.left, rect.top, rect.right, rect.bottom))
        return True

    user32.EnumWindows(EnumWindowsProc(callback), 0)
    return matches[0] if matches else None


class Navigator:
    def __init__(self, root):
        self.root = root
        self.quests = load_json(DATA, {'quests': []}).get('quests', [])
        self.cfg = load_json(CONFIG, {
            'x': 80, 'y': 80, 'alpha': .94, 'clickthrough': False,
            'ironman': True, 'auto_attach': True, 'overlay_enabled': True,
            'completed': [], 'route_points': {}
        })
        self.selected = self.quests[0] if self.quests else {'name': 'No quest data', 'steps': []}
        self.step = 0
        self.drag_start = None
        self.client = None
        self.overlay = None
        self.overlay_canvas = None
        self.overlay_points = []
        self.iron = tk.BooleanVar(value=self.cfg.get('ironman', True))
        self.auto_attach = tk.BooleanVar(value=self.cfg.get('auto_attach', True))
        self.overlay_enabled = tk.BooleanVar(value=self.cfg.get('overlay_enabled', True))
        self.build_ui()
        self.load_points_for_selected()
        self.apply_geometry()
        self.root.after(400, self.tick)
        self.root.bind('<F8>', lambda e: self.toggle_visible())
        self.root.bind('<F9>', lambda e: self.toggle_clickthrough())
        self.root.protocol('WM_DELETE_WINDOW', self.close)

    def build_ui(self):
        self.root.title(APP_NAME)
        self.root.overrideredirect(True)
        self.root.attributes('-topmost', True)
        self.root.attributes('-alpha', self.cfg.get('alpha', .94))
        self.root.configure(bg='#15171a')
        self.root.geometry('520x700')

        header = tk.Frame(self.root, bg='#20242a', height=44)
        header.pack(fill='x')
        header.bind('<Button-1>', self.start_drag)
        header.bind('<B1-Motion>', self.drag)
        tk.Label(header, text='OSRS QUEST NAVIGATOR', bg='#20242a', fg='white',
                 font=('Segoe UI', 11, 'bold')).pack(side='left', padx=12, pady=10)
        self.client_label = tk.Label(header, text='OSRS: searching…', bg='#20242a', fg='#e5b95c',
                                     font=('Segoe UI', 9, 'bold'))
        self.client_label.pack(side='right', padx=10)

        tabs = ttk.Notebook(self.root)
        tabs.pack(fill='both', expand=True, padx=7, pady=7)
        self.dashboard_tab = tk.Frame(tabs, bg='#15171a')
        self.quest_tab = tk.Frame(tabs, bg='#15171a')
        self.route_tab = tk.Frame(tabs, bg='#15171a')
        self.map_tab = tk.Frame(tabs, bg='#15171a')
        self.settings_tab = tk.Frame(tabs, bg='#15171a')
        for tab, name in [(self.dashboard_tab, 'Dashboard'), (self.quest_tab, 'Quests'),
                          (self.route_tab, 'Route'), (self.map_tab, 'Overlay'), (self.settings_tab, 'Settings')]:
            tabs.add(tab, text=name)

        self.build_dashboard(); self.build_quests(); self.build_route(); self.build_map(); self.build_settings()

        footer = tk.Frame(self.root, bg='#20242a'); footer.pack(fill='x')
        tk.Checkbutton(footer, text='Ironman', variable=self.iron, command=self.persist,
                       bg='#20242a', fg='white', selectcolor='#20242a', activebackground='#20242a',
                       activeforeground='white').pack(side='left', padx=8, pady=5)
        tk.Button(footer, text='F8 Hide', command=self.toggle_visible, relief='flat', bg='#30353b', fg='white').pack(side='right', padx=4, pady=5)
        tk.Button(footer, text='F9 Click-through', command=self.toggle_clickthrough, relief='flat', bg='#30353b', fg='white').pack(side='right', padx=4, pady=5)

    def build_dashboard(self):
        tk.Label(self.dashboard_tab, text='Progress', bg='#15171a', fg='white', font=('Segoe UI', 18, 'bold')).pack(anchor='w', padx=14, pady=(16, 6))
        self.progress_text = tk.Label(self.dashboard_tab, text='', bg='#15171a', fg='#c8cdd3', justify='left', font=('Segoe UI', 10))
        self.progress_text.pack(anchor='w', padx=14, pady=6)
        card = tk.Frame(self.dashboard_tab, bg='#20242a'); card.pack(fill='x', padx=14, pady=12)
        self.next_text = tk.Label(card, text='', bg='#20242a', fg='white', justify='left', anchor='w', font=('Segoe UI', 11))
        self.next_text.pack(fill='x', padx=12, pady=12)
        tk.Button(self.dashboard_tab, text='Attach overlay to OSRS', command=self.attach_overlay, bg='#3f6685', fg='white', relief='flat').pack(anchor='w', padx=14, pady=5)
        tk.Button(self.dashboard_tab, text='Recommend next quest', command=self.recommend_quest, bg='#30353b', fg='white', relief='flat').pack(anchor='w', padx=14, pady=5)

    def build_quests(self):
        top = tk.Frame(self.quest_tab, bg='#15171a'); top.pack(fill='x', padx=8, pady=8)
        self.search = tk.StringVar()
        ent = tk.Entry(top, textvariable=self.search, bg='#282d33', fg='white', insertbackground='white', relief='flat')
        ent.pack(fill='x', ipady=7); ent.bind('<KeyRelease>', lambda e: self.refresh_quest_list())
        body = tk.Frame(self.quest_tab, bg='#15171a'); body.pack(fill='both', expand=True, padx=8)
        self.listbox = tk.Listbox(body, bg='#20242a', fg='white', selectbackground='#466984', relief='flat', activestyle='none')
        self.listbox.pack(side='left', fill='both', expand=True); self.listbox.bind('<<ListboxSelect>>', self.select_quest)
        sb = tk.Scrollbar(body, command=self.listbox.yview); sb.pack(side='right', fill='y'); self.listbox.config(yscrollcommand=sb.set)
        self.refresh_quest_list()

    def refresh_quest_list(self):
        q = self.search.get().lower().strip(); completed = set(self.cfg.get('completed', [])); self.listbox.delete(0, 'end')
        for quest in sorted(self.quests, key=lambda x: x.get('name', '')):
            name = quest.get('name', '')
            if q not in name.lower(): continue
            prefix = '✓ ' if name in completed else '  '
            suffix = '  [F2P]' if not quest.get('members', True) else ''
            self.listbox.insert('end', prefix + name + suffix)

    def select_quest(self, _=None):
        sel = self.listbox.curselection()
        if not sel: return
        raw = self.listbox.get(sel[0]).lstrip('✓ ').replace('  [F2P]', '')
        found = next((q for q in self.quests if q.get('name') == raw), None)
        if found:
            self.selected = found; self.step = 0; self.load_points_for_selected(); self.refresh_route(); self.update_dashboard()

    def build_route(self):
        self.route_title = tk.Label(self.route_tab, text='', bg='#15171a', fg='white', font=('Segoe UI', 16, 'bold'))
        self.route_title.pack(anchor='w', padx=12, pady=(12, 3))
        self.route_info = tk.Label(self.route_tab, text='', bg='#15171a', fg='#bfc5cc', justify='left', anchor='w', wraplength=470)
        self.route_info.pack(fill='x', padx=12, pady=5)
        self.steps = tk.Listbox(self.route_tab, bg='#20242a', fg='white', selectbackground='#3f6685', relief='flat', activestyle='none')
        self.steps.pack(fill='both', expand=True, padx=12, pady=8); self.steps.bind('<Double-Button-1>', lambda e: self.advance_step())
        bar = tk.Frame(self.route_tab, bg='#15171a'); bar.pack(fill='x', padx=12, pady=8)
        tk.Button(bar, text='← Previous', command=self.prev_step, bg='#30353b', fg='white', relief='flat').pack(side='left')
        tk.Button(bar, text='Complete step →', command=self.advance_step, bg='#3f6685', fg='white', relief='flat').pack(side='right')
        tk.Button(bar, text='Mark quest complete', command=self.complete_quest, bg='#30353b', fg='white', relief='flat').pack(side='right', padx=6)
        self.refresh_route()

    def refresh_route(self):
        if not hasattr(self, 'steps'): return
        q = self.selected; steps = q.get('steps') or [{'title': 'Quest route not mapped yet', 'destination': 'Quest guide', 'notes': 'The quest is in the catalog; detailed objectives still need mapping.'}]
        self.route_title.config(text=q.get('name', 'Quest'))
        prereq = ', '.join(q.get('prerequisites', [])) or 'None recorded'
        idx = min(self.step, len(steps) - 1)
        nxt = steps[idx]
        self.route_info.config(text=f"{q.get('difficulty','Unknown')} • {'Members' if q.get('members', True) else 'Free-to-play'} • {'Ironman-aware' if self.iron.get() else 'Standard'}\n"
                                    f"Prerequisites: {prereq}\nNEXT: {nxt.get('destination','Unknown')}\n{nxt.get('notes','')}")
        self.steps.delete(0, 'end')
        for i, s in enumerate(steps):
            mark = '✓' if i < self.step else ('→' if i == self.step else '○')
            self.steps.insert('end', f"{mark}  {i+1}. {s.get('title','Objective')} — {s.get('destination','Unknown')}")
        self.steps.selection_set(idx); self.steps.see(idx)
        self.update_dashboard()

    def advance_step(self):
        steps = self.selected.get('steps') or []
        if self.step < len(steps): self.step += 1
        self.refresh_route()
        if steps and self.step >= len(steps): self.complete_quest(silent=True)

    def prev_step(self): self.step = max(0, self.step - 1); self.refresh_route()

    def complete_quest(self, silent=False):
        name = self.selected.get('name')
        if name and name not in self.cfg.setdefault('completed', []):
            self.cfg['completed'].append(name); self.persist(); self.refresh_quest_list(); self.update_dashboard()
        if not silent: messagebox.showinfo('Quest Navigator', f'{name} marked complete.')

    def recommend_quest(self):
        completed = set(self.cfg.get('completed', [])); candidates = []
        for q in self.quests:
            name = q.get('name')
            if not name or name in completed: continue
            if set(q.get('prerequisites', [])).issubset(completed):
                # Prefer F2P starter content and quests with route data; fewer prerequisites first.
                score = (0 if not q.get('members', True) else 1, 0 if q.get('steps') else 1, len(q.get('prerequisites', [])))
                candidates.append((score, q))
        if not candidates: return
        candidates.sort(key=lambda x: x[0]); self.selected = candidates[0][1]; self.step = 0; self.load_points_for_selected(); self.refresh_route()

    def update_dashboard(self):
        if not hasattr(self, 'progress_text'): return
        total = len(self.quests); done = len(set(self.cfg.get('completed', []))); mapped = sum(1 for q in self.quests if q.get('steps'))
        steps = self.selected.get('steps') or []; idx = min(self.step, len(steps)-1) if steps else 0
        nxt = steps[idx].get('destination', 'Quest guide') if steps else 'Detailed route pending'
        self.progress_text.config(text=f'Quest catalog: {total}\nDetailed routes: {mapped}\nCompleted: {done}\n\nClient: {"attached" if self.client else "not detected"}\nOverlay: {"ON" if self.overlay_enabled.get() else "OFF"}')
        self.next_text.config(text=f"CURRENT QUEST\n{self.selected.get('name','Quest')}\n\nNEXT DESTINATION\n{nxt}")

    # ---------- overlay ----------
    def build_map(self):
        tk.Label(self.map_tab, text='External route overlay', bg='#15171a', fg='white', font=('Segoe UI', 16, 'bold')).pack(anchor='w', padx=12, pady=(12,4))
        tk.Label(self.map_tab, text='The app automatically follows the official OSRS window. Calibrated points are drawn as a route over that window.\n'
                                  'The overlay never sends mouse/keyboard input to OSRS.', bg='#15171a', fg='#bfc5cc', justify='left', wraplength=470).pack(anchor='w', padx=12, pady=4)
        self.client_status = tk.Label(self.map_tab, text='', bg='#20242a', fg='#c8cdd3', justify='left', anchor='w')
        self.client_status.pack(fill='x', padx=12, pady=10)
        tk.Checkbutton(self.map_tab, text='Show route overlay', variable=self.overlay_enabled, command=self.toggle_overlay,
                       bg='#15171a', fg='white', selectcolor='#15171a', activebackground='#15171a', activeforeground='white').pack(anchor='w', padx=12)
        tk.Button(self.map_tab, text='Attach / refresh OSRS window', command=self.attach_overlay, bg='#3f6685', fg='white', relief='flat').pack(anchor='w', padx=12, pady=8)
        tk.Button(self.map_tab, text='Add route point', command=self.add_route_point, bg='#30353b', fg='white', relief='flat').pack(anchor='w', padx=12, pady=4)
        tk.Button(self.map_tab, text='Clear route points', command=self.clear_screen_waypoints, bg='#30353b', fg='white', relief='flat').pack(anchor='w', padx=12, pady=4)
        self.wp_label = tk.Label(self.map_tab, text='', bg='#15171a', fg='#bfc5cc', justify='left')
        self.wp_label.pack(anchor='w', padx=12, pady=8)
        self.refresh_waypoint_label()

    def attach_overlay(self):
        self.client = find_osrs_window()
        if not self.client:
            self.client_label.config(text='OSRS: not found', fg='#df7b6e')
            if hasattr(self, 'client_status'): self.client_status.config(text='OSRS window not found. Start the official client and try again.')
            return
        self.client_label.config(text='OSRS: attached', fg='#79d279')
        if hasattr(self, 'client_status'): self.client_status.config(text=f'Attached: {self.client[1]}\nWindow: {self.client[2]},{self.client[3]} → {self.client[4]},{self.client[5]}')
        self.ensure_overlay(); self.position_overlay()

    def ensure_overlay(self):
        if self.overlay is not None and self.overlay.winfo_exists(): return
        self.overlay = tk.Toplevel(self.root); self.overlay.overrideredirect(True); self.overlay.attributes('-topmost', True); self.overlay.configure(bg='#010101')
        try: self.overlay.attributes('-transparentcolor', '#010101')
        except tk.TclError: self.overlay.attributes('-alpha', .01)
        self.overlay_canvas = tk.Canvas(self.overlay, bg='#010101', highlightthickness=0); self.overlay_canvas.pack(fill='both', expand=True)
        # Always click-through so the external overlay cannot block OSRS input.
        self.make_clickthrough(self.overlay)

    def make_clickthrough(self, window):
        if os.name != 'nt': return
        hwnd = window.winfo_id(); GWL_EXSTYLE = -20; WS_EX_LAYERED = 0x80000; WS_EX_TRANSPARENT = 0x20
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE) | WS_EX_LAYERED | WS_EX_TRANSPARENT
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)

    def position_overlay(self):
        if not self.client or not self.overlay: return
        _, _, l, t, r, b = self.client
        self.overlay.geometry(f'{max(1,r-l)}x{max(1,b-t)}+{l}+{t}'); self.overlay.deiconify(); self.draw_overlay()

    def draw_overlay(self):
        if not self.overlay_canvas: return
        self.overlay_canvas.delete('all')
        if not self.overlay_enabled.get(): return
        pts = [(int(x), int(y)) for x,y in self.overlay_points]
        if len(pts) > 1:
            coords = [v for p in pts for v in p]; self.overlay_canvas.create_line(*coords, fill='#ffd34e', width=4, smooth=True)
        for i,(x,y) in enumerate(pts,1):
            self.overlay_canvas.create_oval(x-7,y-7,x+7,y+7, outline='#ffd34e', width=3)
            self.overlay_canvas.create_text(x+14,y,text=str(i),fill='white',anchor='w',font=('Segoe UI',10,'bold'))
        if pts:
            x,y=pts[-1]; self.overlay_canvas.create_text(x,max(12,y-18),text='NEXT',fill='white',font=('Segoe UI',9,'bold'))

    def add_route_point(self):
        if not self.client: self.attach_overlay()
        if not self.client: return
        _, _, l, t, r, b = self.client
        maxx, maxy = r-l, b-t
        x = simpledialog.askinteger('Route point', f'Enter X inside the OSRS window (0-{maxx}):', parent=self.root, minvalue=0, maxvalue=maxx)
        if x is None: return
        y = simpledialog.askinteger('Route point', f'Enter Y inside the OSRS window (0-{maxy}):', parent=self.root, minvalue=0, maxvalue=maxy)
        if y is None: return
        self.overlay_points.append((x,y)); self.save_points_for_selected(); self.draw_overlay(); self.refresh_waypoint_label()

    def clear_screen_waypoints(self):
        self.overlay_points=[]; self.save_points_for_selected(); self.draw_overlay(); self.refresh_waypoint_label()

    def save_points_for_selected(self):
        self.cfg.setdefault('route_points', {})[self.selected.get('name','Unknown')] = [list(p) for p in self.overlay_points]; self.persist()

    def load_points_for_selected(self):
        self.overlay_points = [tuple(p) for p in self.cfg.get('route_points', {}).get(self.selected.get('name',''), [])]
        if hasattr(self,'overlay_canvas'): self.draw_overlay()
        self.refresh_waypoint_label()

    def refresh_waypoint_label(self):
        if hasattr(self,'wp_label'): self.wp_label.config(text=f'Route points for {self.selected.get("name","Quest")}: {len(self.overlay_points)}')

    def toggle_overlay(self):
        if self.overlay_enabled.get(): self.ensure_overlay(); self.position_overlay()
        elif self.overlay: self.overlay.withdraw()
        self.persist(); self.update_dashboard()

    def destroy_overlay(self):
        if self.overlay: self.overlay.destroy()
        self.overlay=None; self.overlay_canvas=None

    # ---------- settings / window ----------
    def tick(self):
        if self.auto_attach.get():
            found=find_osrs_window()
            if found:
                self.client=found; self.client_label.config(text='OSRS: attached', fg='#79d279'); self.ensure_overlay(); self.position_overlay()
            else:
                self.client=None; self.client_label.config(text='OSRS: not found', fg='#df7b6e')
                if self.overlay: self.overlay.withdraw()
        self.root.after(700,self.tick)

    def build_settings(self):
        tk.Label(self.settings_tab,text='Settings',bg='#15171a',fg='white',font=('Segoe UI',16,'bold')).pack(anchor='w',padx=12,pady=(12,8))
        tk.Checkbutton(self.settings_tab,text='Automatically follow the OSRS window',variable=self.auto_attach,command=self.persist,
                       bg='#15171a',fg='white',selectcolor='#15171a',activebackground='#15171a',activeforeground='white').pack(anchor='w',padx=12,pady=5)
        tk.Label(self.settings_tab,text='F8 = hide/show navigator\nF9 = toggle click-through for the control window\n\n'
                                  'The overlay is always click-through. It never clicks or controls OSRS.',
                 bg='#15171a',fg='#bfc5cc',justify='left').pack(anchor='w',padx=12,pady=12)

    def start_drag(self,e): self.drag_start=(e.x_root,e.y_root,self.root.winfo_x(),self.root.winfo_y())
    def drag(self,e):
        if self.drag_start:
            sx,sy,ox,oy=self.drag_start; self.root.geometry(f'+{ox+e.x_root-sx}+{oy+e.y_root-sy}'); self.cfg['x'],self.cfg['y']=self.root.winfo_x(),self.root.winfo_y()
    def apply_geometry(self): self.root.geometry(f'520x700+{self.cfg.get("x",80)}+{self.cfg.get("y",80)}')
    def toggle_visible(self): self.root.withdraw() if self.root.state()!='withdrawn' else self.root.deiconify()
    def toggle_clickthrough(self):
        self.cfg['clickthrough']=not self.cfg.get('clickthrough',False)
        if os.name=='nt':
            hwnd=self.root.winfo_id(); GWL_EXSTYLE=-20; WS_EX_LAYERED=0x80000; WS_EX_TRANSPARENT=0x20; style=user32.GetWindowLongW(hwnd,GWL_EXSTYLE)
            if self.cfg['clickthrough']: style|=WS_EX_LAYERED|WS_EX_TRANSPARENT
            else: style&=~WS_EX_TRANSPARENT
            user32.SetWindowLongW(hwnd,GWL_EXSTYLE,style)
        self.persist()
    def persist(self):
        self.cfg['ironman']=self.iron.get(); self.cfg['auto_attach']=self.auto_attach.get(); self.cfg['overlay_enabled']=self.overlay_enabled.get(); self.cfg['x'],self.cfg['y']=self.root.winfo_x(),self.root.winfo_y(); save_json(CONFIG,self.cfg)
    def close(self): self.persist(); self.destroy_overlay(); self.root.destroy()


if __name__=='__main__':
    root=tk.Tk(); Navigator(root); root.mainloop()
