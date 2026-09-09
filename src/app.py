import ctypes
import ctypes.wintypes as wt
import json
import os
import tkinter as tk
from tkinter import ttk, messagebox

try:
    from PIL import ImageGrab
except Exception:
    ImageGrab = None

APP_NAME = 'OSRS Quest Navigator'
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if getattr(__import__('sys'), '_MEIPASS', None):
    ROOT = __import__('sys')._MEIPASS
DATA = os.path.join(ROOT, 'data', 'quests.json')
ROUTES = os.path.join(ROOT, 'data', 'routes.json')
CONFIG = os.path.join(os.path.expanduser('~'), '.osrs_quest_navigator.json')
SKILLS = ['attack','strength','defence','ranged','prayer','magic','runecraft','construction','hitpoints','agility','herblore','thieving','crafting','fletching','slayer','hunter','mining','smithing','fishing','cooking','firemaking','woodcutting','farming']

user32 = ctypes.windll.user32 if os.name == 'nt' else None
if user32:
    user32.GetWindowTextW.argtypes=[wt.HWND,wt.LPWSTR,ctypes.c_int]; user32.GetWindowTextW.restype=ctypes.c_int
    user32.GetWindowTextLengthW.argtypes=[wt.HWND]; user32.GetWindowTextLengthW.restype=ctypes.c_int
    user32.IsWindowVisible.argtypes=[wt.HWND]; user32.IsWindowVisible.restype=wt.BOOL
    user32.GetWindowRect.argtypes=[wt.HWND,ctypes.POINTER(wt.RECT)]; user32.GetWindowRect.restype=wt.BOOL
    user32.IsWindow.argtypes=[wt.HWND]; user32.IsWindow.restype=wt.BOOL
    user32.GetWindowLongW.argtypes=[wt.HWND,ctypes.c_int]; user32.GetWindowLongW.restype=ctypes.c_long
    user32.SetWindowLongW.argtypes=[wt.HWND,ctypes.c_int,ctypes.c_long]; user32.SetWindowLongW.restype=ctypes.c_long
    user32.SetWindowPos.argtypes=[wt.HWND,wt.HWND,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_uint]; user32.SetWindowPos.restype=wt.BOOL
GWL_EXSTYLE=-20; WS_EX_LAYERED=0x80000; WS_EX_TRANSPARENT=0x20; WS_EX_NOACTIVATE=0x8000000; WS_EX_TOOLWINDOW=0x80
HWND_TOPMOST=wt.HWND(-1); SWP_NOSIZE=1; SWP_NOMOVE=2; SWP_NOACTIVATE=16; SWP_SHOWWINDOW=64

def load(path, fallback):
    try:
        with open(path,'r',encoding='utf-8') as f:return json.load(f)
    except Exception:return fallback

def save(path,obj):
    try:
        with open(path,'w',encoding='utf-8') as f:json.dump(obj,f,indent=2,ensure_ascii=False)
    except Exception:pass

def windows():
    if not user32:return []
    out=[]; CB=ctypes.WINFUNCTYPE(wt.BOOL,wt.HWND,wt.LPARAM)
    def cb(hwnd,_):
        if not user32.IsWindowVisible(hwnd):return True
        n=user32.GetWindowTextLengthW(hwnd)
        if n<=0:return True
        b=ctypes.create_unicode_buffer(n+1); user32.GetWindowTextW(hwnd,b,n+1); title=b.value.strip()
        if not title:return True
        r=wt.RECT()
        if user32.GetWindowRect(hwnd,ctypes.byref(r)) and r.right>r.left and r.bottom>r.top:out.append((int(hwnd),title,r.left,r.top,r.right,r.bottom))
        return True
    fn=CB(cb); user32.EnumWindows(fn,0); return out

def game_windows():
    return [w for w in windows() if any(x in w[1].lower() for x in ('runelite','old school runescape','oldschool runescape','osrs','jagex'))]

def norm(q):
    q=dict(q); q.setdefault('name','Unknown'); q.setdefault('difficulty','Unknown'); q.setdefault('members',True); q.setdefault('prerequisites',[]); q.setdefault('steps',[]); q.setdefault('skill_requirements',{}); return q

class Navigator:
    def __init__(self,root):
        self.root=root; raw=load(DATA,{'quests':[]}); self.quests=[norm(q) for q in raw.get('quests',[])]
        self.routes=load(ROUTES,{'routes':{}}).get('routes',{})
        default={'ironman':True,'completed':[],'skills':{s:1 for s in SKILLS},'overlay':True,'tracking':True,'route_points':{}}
        self.cfg=load(CONFIG,default); self.cfg.setdefault('completed',[]); self.cfg.setdefault('skills',{}); self.cfg.setdefault('route_points',{})
        for s in SKILLS:self.cfg['skills'].setdefault(s,1)
        self.selected=self.quests[0] if self.quests else norm({}); self.step=0; self.client=None; self.overlay=None; self.oc=None; self.interactive=False; self.calibrating=False; self.player=None
        self.iron=tk.BooleanVar(value=self.cfg.get('ironman',True)); self.show_overlay=tk.BooleanVar(value=self.cfg.get('overlay',True)); self.tracking=tk.BooleanVar(value=self.cfg.get('tracking',True))
        root.title(APP_NAME); root.geometry('720x780'); root.minsize(620,650); root.attributes('-topmost',True); root.configure(bg='#15171a'); self.build_ui(); self.refresh_all(); root.after(400,self.tick); root.protocol('WM_DELETE_WINDOW',self.close); root.bind('<F8>',lambda e:self.toggle_visible()); root.bind('<F9>',lambda e:self.toggle_clickthrough())

    def button(self,parent,text,cmd,primary=False):return tk.Button(parent,text=text,command=cmd,bg='#3f6685' if primary else '#30353b',fg='white',relief='flat')
    def build_ui(self):
        h=tk.Frame(self.root,bg='#20242a'); h.pack(fill='x'); tk.Label(h,text='OSRS QUEST NAVIGATOR',bg='#20242a',fg='white',font=('Segoe UI',11,'bold')).pack(side='left',padx=12,pady=8); self.client_label=tk.Label(h,text='OSRS: searching…',bg='#20242a',fg='#e5b95c',font=('Segoe UI',9,'bold')); self.client_label.pack(side='right',padx=10)
        tabs=ttk.Notebook(self.root); tabs.pack(fill='both',expand=True,padx=7,pady=7)
        self.dashboard=tk.Frame(tabs,bg='#15171a'); self.quest_tab=tk.Frame(tabs,bg='#15171a'); self.route_tab=tk.Frame(tabs,bg='#15171a'); self.account_tab=tk.Frame(tabs,bg='#15171a'); self.overlay_tab=tk.Frame(tabs,bg='#15171a'); self.settings_tab=tk.Frame(tabs,bg='#15171a')
        for x,n in ((self.dashboard,'Dashboard'),(self.quest_tab,'Quests'),(self.route_tab,'Route'),(self.account_tab,'Account'),(self.overlay_tab,'Overlay'),(self.settings_tab,'Settings')):tabs.add(x,text=n)
        self.build_dashboard(); self.build_quests(); self.build_route(); self.build_account(); self.build_overlay(); self.build_settings()
        f=tk.Frame(self.root,bg='#20242a'); f.pack(fill='x'); tk.Checkbutton(f,text='Ironman',variable=self.iron,command=self.persist,bg='#20242a',fg='white',selectcolor='#20242a',activebackground='#20242a',activeforeground='white').pack(side='left',padx=8,pady=5); tk.Button(f,text='F8 Hide',command=self.toggle_visible,bg='#30353b',fg='white',relief='flat').pack(side='right',padx=4,pady=5); tk.Button(f,text='F9 Click-through',command=self.toggle_clickthrough,bg='#30353b',fg='white',relief='flat').pack(side='right',padx=4,pady=5)

    def build_dashboard(self):
        tk.Label(self.dashboard,text='Ironman Quest Planner',bg='#15171a',fg='white',font=('Segoe UI',19,'bold')).pack(anchor='w',padx=14,pady=(15,4)); self.progress=tk.Label(self.dashboard,text='',bg='#15171a',fg='#c8cdd3',justify='left',anchor='w'); self.progress.pack(fill='x',padx=14,pady=7); c=tk.Frame(self.dashboard,bg='#20242a'); c.pack(fill='x',padx=14,pady=10); self.next_text=tk.Label(c,text='',bg='#20242a',fg='white',justify='left',anchor='w'); self.next_text.pack(fill='x',padx=12,pady=12); b=tk.Frame(self.dashboard,bg='#15171a'); b.pack(fill='x',padx=14); self.button(b,'Recommend best next quest',self.recommend,True).pack(side='left',padx=(0,6),pady=5); self.button(b,'Mark selected complete',self.mark_complete).pack(side='left',pady=5); self.warn=tk.Label(self.dashboard,text='',bg='#15171a',fg='#e5b95c',justify='left',wraplength=650); self.warn.pack(anchor='w',padx=14,pady=8)

    def build_quests(self):
        top=tk.Frame(self.quest_tab,bg='#15171a'); top.pack(fill='x',padx=8,pady=8); self.search=tk.StringVar(); e=tk.Entry(top,textvariable=self.search,bg='#282d33',fg='white',insertbackground='white',relief='flat'); e.pack(fill='x',ipady=7); e.bind('<KeyRelease>',lambda _:self.refresh_quests()); body=tk.Frame(self.quest_tab,bg='#15171a'); body.pack(fill='both',expand=True,padx=8); self.lb=tk.Listbox(body,bg='#20242a',fg='white',selectbackground='#466984',relief='flat',activestyle='none'); self.lb.pack(side='left',fill='both',expand=True); self.lb.bind('<<ListboxSelect>>',self.select_quest); sb=tk.Scrollbar(body,command=self.lb.yview); sb.pack(side='right',fill='y'); self.lb.config(yscrollcommand=sb.set); self.quest_hint=tk.Label(self.quest_tab,text='',bg='#15171a',fg='#bfc5cc'); self.quest_hint.pack(anchor='w',padx=12,pady=6)
    def refresh_quests(self):
        q=self.search.get().lower().strip(); done=set(self.cfg.get('completed',[])); self.lb.delete(0,'end')
        for x in sorted(self.quests,key=lambda z:z['name'].lower()):
            if q and q not in x['name'].lower():continue
            self.lb.insert('end',('✓ ' if x['name'] in done else '  ')+x['name']+(' [F2P]' if not x.get('members',True) else ''))
        self.quest_hint.config(text=f'{len(self.quests)} quests • {len(done)} completed')
    def select_quest(self,_=None):
        s=self.lb.curselection()
        if not s:return
        name=self.lb.get(s[0]).replace('✓ ','',1).replace('  ','',1).replace(' [F2P]',''); q=next((x for x in self.quests if x['name']==name),None)
        if q:self.selected=q; self.step=0; self.refresh_all()

    def stages(self):
        r=self.routes.get(self.selected['name'],{}); return r.get('stages') or [{'title':s.get('title','Objective'),'destination':s.get('destination','Unknown'),'transport':'Walk','items':[],'notes':s.get('notes','')} for s in self.selected.get('steps',[])]
    def reqs(self):
        r=self.selected.get('skill_requirements',{}).copy(); r.update(self.routes.get(self.selected['name'],{}).get('skill_requirements',{})); return r
    def build_route(self):
        self.route_title=tk.Label(self.route_tab,text='',bg='#15171a',fg='white',font=('Segoe UI',17,'bold')); self.route_title.pack(anchor='w',padx=12,pady=(12,4)); self.route_meta=tk.Label(self.route_tab,text='',bg='#15171a',fg='#c8cdd3',justify='left',wraplength=650); self.route_meta.pack(fill='x',padx=12,pady=4); self.steps=tk.Listbox(self.route_tab,bg='#20242a',fg='white',selectbackground='#3f6685',relief='flat'); self.steps.pack(fill='both',expand=True,padx=12,pady=8); bar=tk.Frame(self.route_tab,bg='#15171a'); bar.pack(fill='x',padx=12,pady=8); self.button(bar,'← Previous',self.prev_step).pack(side='left'); self.button(bar,'Complete step →',self.advance_step,True).pack(side='right')
    def refresh_route(self):
        st=self.stages(); idx=min(self.step,max(0,len(st)-1)) if st else 0; req=self.reqs(); miss=[f'{k.title()} {v} (you: {self.cfg["skills"].get(k,1)})' for k,v in req.items() if self.cfg['skills'].get(k,1)<v]
        self.route_title.config(text=self.selected['name']); self.route_meta.config(text=f"{'Members' if self.selected.get('members',True) else 'F2P'} • {self.selected.get('difficulty','Unknown')} • {'Ironman-aware' if self.iron.get() else 'Standard'}\nPrerequisites: {', '.join(self.selected.get('prerequisites',[])) or 'None'}\nSkill gates: {', '.join(f'{k.title()} {v}' for k,v in req.items()) or 'None'}"+(f"\n⚠ Missing: {', '.join(miss)}" if miss else ''))
        self.steps.delete(0,'end')
        for i,s in enumerate(st):
            mark='✓' if i<self.step else ('→' if i==self.step else '○'); self.steps.insert('end',f"{mark}  {i+1}. {s.get('title','Objective')} — {s.get('destination','Unknown')} | {s.get('transport','Walk')} | Prep: {', '.join(s.get('items',[])) or 'None'}")
        if st:self.steps.selection_set(idx); self.steps.see(idx)

    def build_account(self):
        tk.Label(self.account_tab,text='Account state',bg='#15171a',fg='white',font=('Segoe UI',17,'bold')).pack(anchor='w',padx=12,pady=12); tk.Label(self.account_tab,text='Enter levels and mark quests complete. This stays local to your PC.',bg='#15171a',fg='#bfc5cc').pack(anchor='w',padx=12)
        frame=tk.Frame(self.account_tab,bg='#15171a'); frame.pack(fill='both',expand=True,padx=12,pady=8); self.skill_vars={}
        for i,s in enumerate(SKILLS):
            p=tk.Frame(frame,bg='#15171a'); p.grid(row=i%12,column=i//12,sticky='ew',padx=8,pady=2); tk.Label(p,text=s.title(),width=13,anchor='w',bg='#15171a',fg='#c8cdd3').pack(side='left'); v=tk.StringVar(value=str(self.cfg['skills'].get(s,1))); self.skill_vars[s]=v; tk.Entry(p,textvariable=v,width=6,bg='#282d33',fg='white',insertbackground='white',relief='flat').pack(side='left')
        self.button(self.account_tab,'Save levels',self.save_skills,True).pack(anchor='w',padx=12,pady=5); self.button(self.account_tab,'Reset completed quests',self.reset_completed).pack(anchor='w',padx=12,pady=5)
    def save_skills(self):
        for s,v in self.skill_vars.items():
            try:self.cfg['skills'][s]=max(1,int(v.get()))
            except:self.cfg['skills'][s]=1
        self.persist(); self.refresh_all()
    def reset_completed(self):
        if messagebox.askyesno('Reset','Clear all completed quest flags?'):self.cfg['completed']=[]; self.persist(); self.refresh_all()
    def mark_complete(self):
        if self.selected['name'] not in self.cfg['completed']:self.cfg['completed'].append(self.selected['name'])
        self.persist(); self.refresh_all()

    def build_overlay(self):
        tk.Label(self.overlay_tab,text='Live route overlay',bg='#15171a',fg='white',font=('Segoe UI',17,'bold')).pack(anchor='w',padx=12,pady=12); self.client_status=tk.Label(self.overlay_tab,text='',bg='#20242a',fg='#c8cdd3',justify='left',anchor='w'); self.client_status.pack(fill='x',padx=12,pady=8); b=tk.Frame(self.overlay_tab,bg='#15171a'); b.pack(fill='x',padx=12); self.button(b,'Attach / find RuneLite',self.open_picker,True).pack(side='left',padx=(0,6),pady=5); self.button(b,'Calibrate current step',self.start_calibration).pack(side='left',pady=5); tk.Checkbutton(self.overlay_tab,text='Show route overlay',variable=self.show_overlay,command=self.toggle_overlay,bg='#15171a',fg='white',selectcolor='#15171a',activebackground='#15171a',activeforeground='white').pack(anchor='w',padx=12,pady=5); tk.Checkbutton(self.overlay_tab,text='Track player highlight',variable=self.tracking,command=self.persist,bg='#15171a',fg='white',selectcolor='#15171a',activebackground='#15171a',activeforeground='white').pack(anchor='w',padx=12,pady=5); self.track_info=tk.Label(self.overlay_tab,text='',bg='#15171a',fg='#bfc5cc',justify='left',wraplength=650); self.track_info.pack(anchor='w',padx=12,pady=8); tk.Label(self.overlay_tab,text='For external live tracking, enable RuneLite Player Indicators → Highlight own player → Draw tiles under players. The app detects the cyan tile highlight; it does not send clicks or keyboard input.',bg='#15171a',fg='#bfc5cc',justify='left',wraplength=650).pack(anchor='w',padx=12,pady=8)
    def open_picker(self):
        wins=game_windows() or windows(); dlg=tk.Toplevel(self.root); dlg.title('Select RuneLite / OSRS window'); dlg.geometry('700x430'); dlg.transient(self.root); dlg.grab_set(); dlg.configure(bg='#15171a'); tk.Label(dlg,text='Select the game window',bg='#15171a',fg='white',font=('Segoe UI',13,'bold')).pack(anchor='w',padx=12,pady=10); lb=tk.Listbox(dlg,bg='#20242a',fg='white',selectbackground='#466984',relief='flat'); lb.pack(fill='both',expand=True,padx=12,pady=5)
        for w in wins:lb.insert('end',f'{w[1]} [{w[2]},{w[3]} - {w[4]},{w[5]}]')
        def use():
            s=lb.curselection()
            if not s:return
            self.client=wins[s[0]]; self.ensure_overlay(); self.update_client(); dlg.destroy()
        self.button(dlg,'Use selected window',use,True).pack(pady=10)
        if wins:lb.selection_set(0)

    def build_settings(self):
        tk.Label(self.settings_tab,text='Settings',bg='#15171a',fg='white',font=('Segoe UI',17,'bold')).pack(anchor='w',padx=12,pady=12); self.status=tk.Label(self.settings_tab,text='',bg='#20242a',fg='#c8cdd3',justify='left',anchor='w'); self.status.pack(fill='x',padx=12,pady=8); tk.Label(self.settings_tab,text='F8 hides the Navigator. F9 toggles click-through for the route overlay. The overlay is guidance-only and never controls the game.',bg='#15171a',fg='#bfc5cc',justify='left',wraplength=650).pack(anchor='w',padx=12,pady=8)

    def ensure_overlay(self):
        if not self.client or not self.show_overlay.get():return
        if not self.overlay:
            self.overlay=tk.Toplevel(self.root); self.overlay.overrideredirect(True); self.overlay.attributes('-topmost',True); self.overlay.configure(bg='#010101'); self.oc=tk.Canvas(self.overlay,bg='#010101',highlightthickness=0); self.oc.pack(fill='both',expand=True); self.apply_overlay_style()
        self.position_overlay()
    def apply_overlay_style(self):
        if not self.overlay or not user32:return
        h=self.overlay.winfo_id(); st=user32.GetWindowLongW(h,GWL_EXSTYLE); st|=WS_EX_LAYERED|WS_EX_NOACTIVATE|WS_EX_TOOLWINDOW
        if not self.interactive:st|=WS_EX_TRANSPARENT
        else:st&=~WS_EX_TRANSPARENT
        user32.SetWindowLongW(h,GWL_EXSTYLE,st); user32.SetWindowPos(h,HWND_TOPMOST,0,0,0,0,SWP_NOMOVE|SWP_NOSIZE|SWP_NOACTIVATE|SWP_SHOWWINDOW)
    def position_overlay(self):
        if not self.overlay or not self.client:return
        _,_,l,t,r,b=self.client; self.overlay.geometry(f'{r-l}x{b-t}+{l}+{t}'); self.apply_overlay_style(); self.draw_overlay()
    def toggle_overlay(self):
        self.persist()
        if self.show_overlay.get():self.ensure_overlay()
        elif self.overlay:self.overlay.withdraw()
    def toggle_clickthrough(self):self.interactive=not self.interactive; self.apply_overlay_style()
    def start_calibration(self):
        if not self.client:self.open_picker(); return
        self.ensure_overlay(); self.interactive=True; self.calibrating=True; self.apply_overlay_style(); self.oc.bind('<Button-1>',self.capture); messagebox.showinfo('Calibrate','Click the destination inside RuneLite. The click is captured for calibration only and is not sent to the game.')
    def capture(self,e):
        if not self.client:return
        key=f'{self.selected["name"]}::{self.step}'; self.cfg.setdefault('route_points',{})[key]={'x':e.x,'y':e.y}; self.persist(); self.calibrating=False; self.interactive=False; self.oc.unbind('<Button-1>'); self.apply_overlay_style(); self.draw_overlay()
    def detect_player(self):
        if not self.client or not self.tracking.get() or ImageGrab is None:return None
        _,_,l,t,r,b=self.client
        try:
            img=ImageGrab.grab(bbox=(l,t,r,b),all_screens=True).convert('RGB'); w,h=img.size; stride=max(1,int(min(w,h)/450)); pts=[]
            for y in range(0,h,stride):
                for x in range(0,w,stride):
                    R,G,B=img.getpixel((x,y))
                    if G>145 and B>145 and B>R*1.25 and G>R*1.15 and G+B-R>390:pts.append((x,y))
            if len(pts)<8:return None
            cx,cy=w/2,h*.58; return min(pts,key=lambda p:(p[0]-cx)**2+(p[1]-cy)**2)
        except Exception:return None
    def draw_overlay(self):
        if not self.overlay or not self.oc or not self.client:return
        self.oc.delete('all'); self.player=self.detect_player(); st=self.stages(); idx=min(self.step,len(st)-1) if st else 0; key=f'{self.selected["name"]}::{idx}'; dest=self.cfg.get('route_points',{}).get(key)
        if self.player:
            px,py=self.player; self.oc.create_oval(px-7,py-7,px+7,py+7,outline='#00ffff',width=2)
            if dest:self.oc.create_line(px,py,dest['x'],dest['y'],fill='#ffff00',width=4,arrow='last'); self.oc.create_oval(dest['x']-8,dest['y']-8,dest['x']+8,dest['y']+8,outline='#ffff00',width=3)
        elif dest:self.oc.create_oval(dest['x']-8,dest['y']-8,dest['x']+8,dest['y']+8,outline='#ffff00',width=3)
        destname=st[idx].get('destination','Complete') if st and idx<len(st) else 'Complete'; self.oc.create_rectangle(12,12,350,88,fill='#11151a',outline='#4f6f86'); self.oc.create_text(22,25,anchor='w',text=self.selected['name'],fill='white',font=('Segoe UI',11,'bold')); self.oc.create_text(22,48,anchor='w',text=f'Next: {destname}',fill='white',font=('Segoe UI',9)); self.oc.create_text(22,70,anchor='w',text=f"{'PLAYER TRACKED' if self.player else 'PLAYER NOT FOUND'} • Step {idx+1 if st else 0}/{len(st)}",fill='#9fe6ff',font=('Segoe UI',9))

    def update_client(self):
        self.client_label.config(text='OSRS: attached' if self.client else 'OSRS: searching…',fg='#79d279' if self.client else '#e5b95c'); self.client_status.config(text=(f'Attached: {self.client[1]}\nWindow: {self.client[2]},{self.client[3]} → {self.client[4]},{self.client[5]}' if self.client else 'No game window attached.'))
    def tick(self):
        try:
            if not self.client or not user32 or not user32.IsWindow(self.client[0]):self.client=game_windows()[0] if game_windows() else None
            if self.client:
                r=wt.RECT(); user32.GetWindowRect(wt.HWND(self.client[0]),ctypes.byref(r)); self.client=(self.client[0],self.client[1],r.left,r.top,r.right,r.bottom); self.ensure_overlay(); self.update_client(); self.track_info.config(text=f'Player highlight: {"detected" if self.detect_player() else "not detected"}\nCurrent step: {self.step+1 if self.stages() else 0}'); self.draw_overlay()
            else:self.update_client()
            self.status.config(text=f'Client: {"attached" if self.client else "not attached"}\nQuest: {self.selected["name"]}\nSaved calibration points: {len(self.cfg.get("route_points",{}))}')
        except Exception:pass
        self.root.after(700,self.tick)
    def recommend(self):
        done=set(self.cfg.get('completed',[])); choices=[]
        for q in self.quests:
            if q['name'] in done or set(q.get('prerequisites',[]))-done:continue
            req=q.get('skill_requirements',{}).copy(); req.update(self.routes.get(q['name'],{}).get('skill_requirements',{})); gap=sum(max(0,int(v)-self.cfg['skills'].get(k,1)) for k,v in req.items()); score=(5000+gap*20) if gap else ((len(q.get('steps',[])) or len(self.routes.get(q['name'],{}).get('stages',[])) or 8)+len(q.get('prerequisites',[]))*2+(1 if self.iron.get() and q.get('members',True) else 0)); choices.append((score,q))
        if choices:self.selected=min(choices,key=lambda x:(x[0],x[1]['name']))[1]; self.step=0; self.refresh_all()
    def update_dashboard(self):
        done=set(self.cfg.get('completed',[])); st=self.stages(); idx=min(self.step,len(st)-1) if st else 0; nxt=st[idx].get('destination','Detailed route pending') if st else 'Detailed route pending'; self.progress.config(text=f'Quest catalog: {len(self.quests)}\nCompleted: {len(done)}\nClient: {"attached" if self.client else "not detected"}\nOverlay: {"ON" if self.show_overlay.get() else "OFF"}\nPlayer tracking: {"ON" if self.tracking.get() else "OFF"}'); self.next_text.config(text=f'CURRENT QUEST\n{self.selected["name"]}\n\nNEXT DESTINATION\n{nxt}\n\nPREP\n{", ".join(st[idx].get("items",[])) if st else "No route data"}'); missing=[p for p in self.selected.get('prerequisites',[]) if p not in done]; self.warn.config(text=('⚠ Missing quest prerequisites: '+', '.join(missing)) if missing else '')
    def advance_step(self):
        if self.step<len(self.stages()):self.step+=1
        if self.step>=len(self.stages()) and self.stages():self.mark_complete()
        else:self.refresh_all()
    def prev_step(self):self.step=max(0,self.step-1); self.refresh_all()
    def refresh_all(self):self.refresh_quests(); self.refresh_route(); self.update_dashboard(); self.persist()
    def persist(self):self.cfg['ironman']=self.iron.get(); self.cfg['overlay']=self.show_overlay.get(); self.cfg['tracking']=self.tracking.get(); save(CONFIG,self.cfg)
    def toggle_visible(self):self.root.withdraw() if self.root.state()!='withdrawn' else self.root.deiconify()
    def close(self):
        self.persist()
        if self.overlay:
            try:self.overlay.destroy()
            except:pass
        self.root.destroy()

if __name__=='__main__':
    root=tk.Tk(); Navigator(root); root.mainloop()
