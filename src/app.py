import json, os, sys, ctypes, tkinter as tk
from tkinter import ttk, messagebox

ROOT = getattr(sys, '_MEIPASS', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA = os.path.join(ROOT, 'data', 'quests.json')
CONFIG = os.path.join(os.path.expanduser('~'), '.osrs_quest_navigator.json')

def load_data():
    with open(DATA, 'r', encoding='utf-8') as f:
        return json.load(f)['quests']

def load_config():
    try:
        with open(CONFIG, 'r', encoding='utf-8') as f: return json.load(f)
    except Exception: return {'x':100,'y':100,'alpha':.94,'clickthrough':False,'ironman':True}

def save_config(cfg):
    try:
        with open(CONFIG,'w',encoding='utf-8') as f: json.dump(cfg,f,indent=2)
    except Exception: pass

class Navigator:
    def __init__(self, root):
        self.root=root; self.quests=load_data(); self.cfg=load_config()
        self.selected=self.quests[0]; self.step=0; self.waypoints=[]; self.drag_start=None
        # Create this before build_route(), because refresh_route() reads it.
        self.iron=tk.BooleanVar(value=self.cfg.get('ironman',True))
        self.build_ui(); self.apply_geometry()
        self.root.after(250,self.apply_clickthrough)
        self.root.bind('<F8>',lambda e:self.toggle_visible()); self.root.bind('<F9>',lambda e:self.toggle_clickthrough())
        self.root.protocol('WM_DELETE_WINDOW',self.close)

    def build_ui(self):
        self.root.title('OSRS Quest Navigator'); self.root.overrideredirect(True); self.root.attributes('-topmost',True)
        self.root.attributes('-alpha',self.cfg.get('alpha',.94)); self.root.configure(bg='#171717'); self.root.geometry('470x620')
        self.header=tk.Frame(self.root,bg='#202020',height=42); self.header.pack(fill='x')
        self.header.bind('<Button-1>',self.start_drag); self.header.bind('<B1-Motion>',self.drag)
        tk.Label(self.header,text='OSRS QUEST NAVIGATOR',bg='#202020',fg='white',font=('Segoe UI',11,'bold')).pack(side='left',padx=12,pady=10)
        tk.Label(self.header,text='● LIVE',bg='#202020',fg='#79d279',font=('Segoe UI',9,'bold')).pack(side='right',padx=12)
        tabs=ttk.Notebook(self.root); tabs.pack(fill='both',expand=True,padx=7,pady=7)
        self.quest_tab=tk.Frame(tabs,bg='#171717'); self.route_tab=tk.Frame(tabs,bg='#171717'); self.wp_tab=tk.Frame(tabs,bg='#171717')
        tabs.add(self.quest_tab,text='Quests'); tabs.add(self.route_tab,text='Route'); tabs.add(self.wp_tab,text='Waypoints')
        self.build_quests(); self.build_route(); self.build_waypoints()
        footer=tk.Frame(self.root,bg='#202020'); footer.pack(fill='x')
        tk.Checkbutton(footer,text='Ironman routing',variable=self.iron,command=self.refresh_route,bg='#202020',fg='white',selectcolor='#202020',activebackground='#202020',activeforeground='white').pack(side='left',padx=8,pady=5)
        tk.Button(footer,text='F8 Hide',command=self.toggle_visible,relief='flat',bg='#303030',fg='white').pack(side='right',padx=5,pady=5)
        tk.Button(footer,text='F9 Click-through',command=self.toggle_clickthrough,relief='flat',bg='#303030',fg='white').pack(side='right',padx=5,pady=5)

    def build_quests(self):
        top=tk.Frame(self.quest_tab,bg='#171717'); top.pack(fill='x',padx=8,pady=8); self.search=tk.StringVar()
        ent=tk.Entry(top,textvariable=self.search,bg='#282828',fg='white',insertbackground='white',relief='flat'); ent.pack(fill='x',ipady=6); ent.bind('<KeyRelease>',lambda e:self.refresh_quest_list())
        body=tk.Frame(self.quest_tab,bg='#171717'); body.pack(fill='both',expand=True,padx=8)
        self.listbox=tk.Listbox(body,bg='#202020',fg='white',selectbackground='#4d6d8a',relief='flat',activestyle='none'); self.listbox.pack(side='left',fill='both',expand=True); self.listbox.bind('<<ListboxSelect>>',self.select_quest)
        sb=tk.Scrollbar(body,command=self.listbox.yview); sb.pack(side='right',fill='y'); self.listbox.config(yscrollcommand=sb.set); self.refresh_quest_list()

    def refresh_quest_list(self):
        q=self.search.get().lower().strip(); self.listbox.delete(0,'end')
        for quest in self.quests:
            if q in quest['name'].lower(): self.listbox.insert('end',quest['name']+(' [F2P]' if not quest.get('members') else ''))

    def select_quest(self,_=None):
        sel=self.listbox.curselection()
        if not sel:return
        name=self.listbox.get(sel[0]).replace(' [F2P]',''); self.selected=next(q for q in self.quests if q['name']==name); self.step=0; self.refresh_route()

    def build_route(self):
        self.route_title=tk.Label(self.route_tab,text='',bg='#171717',fg='white',font=('Segoe UI',15,'bold')); self.route_title.pack(anchor='w',padx=12,pady=(12,4))
        self.route_info=tk.Label(self.route_tab,text='',bg='#171717',fg='#bbbbbb',justify='left',anchor='w',wraplength=420); self.route_info.pack(fill='x',padx=12,pady=5)
        self.steps=tk.Listbox(self.route_tab,bg='#202020',fg='white',selectbackground='#3c5f76',relief='flat',activestyle='none'); self.steps.pack(fill='both',expand=True,padx=12,pady=8)
        self.steps.bind('<Double-Button-1>',lambda e:self.advance_step()); btns=tk.Frame(self.route_tab,bg='#171717'); btns.pack(fill='x',padx=12,pady=8)
        tk.Button(btns,text='← Previous',command=self.prev_step,bg='#303030',fg='white',relief='flat').pack(side='left'); tk.Button(btns,text='Complete step →',command=self.advance_step,bg='#3c5f76',fg='white',relief='flat').pack(side='right'); self.refresh_route()

    def refresh_route(self):
        if not hasattr(self,'steps'): return
        q=self.selected; self.route_title.config(text=q['name']); prereq=', '.join(q.get('prerequisites',[])) or 'None'; mode='Ironman-aware' if self.iron.get() else 'Standard'
        idx=min(self.step,len(q['steps'])-1); nxt=q['steps'][idx]['destination'] if q['steps'] else 'No objectives'
        self.route_info.config(text=f'{q["difficulty"]} • {mode}\nPrerequisites: {prereq}\nNext: {nxt}')
        self.steps.delete(0,'end')
        for i,s in enumerate(q['steps']):
            mark='✓' if i<self.step else ('→' if i==self.step else '○'); self.steps.insert('end',f'{mark}  {i+1}. {s["title"]} — {s["destination"]}')
        if q['steps']: self.steps.selection_set(idx); self.steps.see(idx)

    def advance_step(self):
        if self.step<len(self.selected['steps']): self.step+=1; self.refresh_route()
        if self.step>=len(self.selected['steps']): messagebox.showinfo('Quest route',f'Route complete for {self.selected["name"]}.')
    def prev_step(self): self.step=max(0,self.step-1); self.refresh_route()

    def build_waypoints(self):
        tk.Label(self.wp_tab,text='Manual route calibration',bg='#171717',fg='white',font=('Segoe UI',13,'bold')).pack(anchor='w',padx=12,pady=12)
        tk.Label(self.wp_tab,text='External overlays cannot safely read OSRS world coordinates from the official client.\nUse this tab to store screen-space waypoints for a route.',bg='#171717',fg='#bbbbbb',justify='left').pack(anchor='w',padx=12)
        self.wp_list=tk.Listbox(self.wp_tab,bg='#202020',fg='white',relief='flat'); self.wp_list.pack(fill='both',expand=True,padx=12,pady=12)
        bar=tk.Frame(self.wp_tab,bg='#171717'); bar.pack(fill='x',padx=12,pady=8); tk.Button(bar,text='Add waypoint',command=self.add_waypoint,bg='#3c5f76',fg='white',relief='flat').pack(side='left'); tk.Button(bar,text='Clear',command=lambda:(self.waypoints.clear(),self.refresh_wp()),bg='#303030',fg='white',relief='flat').pack(side='right')
    def add_waypoint(self): self.waypoints.append({'name':f'Waypoint {len(self.waypoints)+1}','x':0,'y':0}); self.refresh_wp()
    def refresh_wp(self):
        if hasattr(self,'wp_list'):
            self.wp_list.delete(0,'end')
            for w in self.waypoints:self.wp_list.insert('end',f'{w["name"]}  ({w["x"]}, {w["y"]})')
    def start_drag(self,e): self.drag_start=(e.x_root,e.y_root,self.root.winfo_x(),self.root.winfo_y())
    def drag(self,e):
        if self.drag_start:
            sx,sy,ox,oy=self.drag_start; self.root.geometry(f'+{ox+e.x_root-sx}+{oy+e.y_root-sy}'); self.cfg['x'],self.cfg['y']=self.root.winfo_x(),self.root.winfo_y()
    def apply_geometry(self): self.root.geometry(f'470x620+{self.cfg.get("x",100)}+{self.cfg.get("y",100)}')
    def toggle_visible(self): self.root.withdraw() if self.root.state()!='withdrawn' else self.root.deiconify()
    def toggle_clickthrough(self): self.cfg['clickthrough']=not self.cfg.get('clickthrough',False); self.apply_clickthrough()
    def apply_clickthrough(self):
        if os.name!='nt':return
        hwnd=self.root.winfo_id(); GWL_EXSTYLE=-20; WS_EX_LAYERED=0x80000; WS_EX_TRANSPARENT=0x20; u=ctypes.windll.user32; style=u.GetWindowLongW(hwnd,GWL_EXSTYLE)
        style = (style|WS_EX_LAYERED|WS_EX_TRANSPARENT) if self.cfg.get('clickthrough',False) else (style&~WS_EX_TRANSPARENT); u.SetWindowLongW(hwnd,GWL_EXSTYLE,style)
    def close(self):
        self.cfg['x'],self.cfg['y']=self.root.winfo_x(),self.root.winfo_y(); self.cfg['ironman']=self.iron.get(); save_config(self.cfg); self.root.destroy()

if __name__=='__main__':
    root=tk.Tk(); Navigator(root); root.mainloop()
