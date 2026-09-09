from pathlib import Path

p = Path('src/app.py')
s = p.read_text(encoding='utf-8')

# Keep the working Windows overlay behavior.
start = s.index('    def make_clickthrough(self, win):')
end = s.index('\n\n    def position_overlay', start)
replacement = '''    def make_clickthrough(self, win):
        """Make the overlay visible but completely non-interactive on Windows."""
        if os.name != 'nt':
            return
        win.update_idletasks()
        hwnd = win.winfo_id()
        GWL_EXSTYLE=-20
        WS_EX_LAYERED=0x00080000
        WS_EX_TRANSPARENT=0x00000020
        WS_EX_NOACTIVATE=0x08000000
        WS_EX_TOOLWINDOW=0x00000080
        LWA_COLORKEY=0x00000001
        SWP_NOSIZE=0x0001; SWP_NOMOVE=0x0002; SWP_NOACTIVATE=0x0010; SWP_NOOWNERZORDER=0x0200
        HWND_TOPMOST=ctypes.c_void_p(-1)
        ex=user32.GetWindowLongW(hwnd,GWL_EXSTYLE)
        ex |= WS_EX_LAYERED|WS_EX_TRANSPARENT|WS_EX_NOACTIVATE|WS_EX_TOOLWINDOW
        user32.SetWindowLongW(hwnd,GWL_EXSTYLE,ex)
        try:
            user32.SetLayeredWindowAttributes(hwnd,0x00010101,0,LWA_COLORKEY)
        except Exception:
            pass
        user32.SetWindowPos(hwnd,HWND_TOPMOST,0,0,0,0,SWP_NOSIZE|SWP_NOMOVE|SWP_NOACTIVATE|SWP_NOOWNERZORDER)
'''
s = s[:start] + replacement + s[end:]

# Imports for the fast passive sync and route projection helpers.
if 'import time\n' not in s:
    s = s.replace('import tkinter as tk\n', 'import tkinter as tk\nimport time\n', 1)
if 'from screen_sync import ScreenSync' not in s:
    s = s.replace('import tkinter as tk\n', 'import tkinter as tk\nfrom screen_sync import ScreenSync\n', 1)
if 'from pathing import screen_route, guidance_text' not in s:
    s = s.replace('from screen_sync import ScreenSync\n', 'from screen_sync import ScreenSync\nfrom pathing import screen_route, guidance_text\n', 1)

# Initialize the passive sync engine once. It is deliberately non-blocking.
needle = "self.client=None; self.overlay=None; self.oc=None; self.interactive=False; self.calibrating=False; self.player=None"
replacement_init = needle + "; self.screen_sync=ScreenSync(); self.sync_snapshot=self.screen_sync.snapshot(); self.last_sync_request=0"
if needle in s and 'self.screen_sync=ScreenSync()' not in s:
    s = s.replace(needle, replacement_init, 1)

# Add the non-blocking account sync method before tick.
if '    def _passive_sync(self):' not in s:
    marker = '    def tick(self):\n'
    method = '''    def _passive_sync(self):
        if not self.client or not hasattr(self, 'screen_sync'):
            return
        now=time.time()
        if now-self.last_sync_request < 1.0:
            self.sync_snapshot=self.screen_sync.snapshot()
            return
        self.last_sync_request=now
        try:
            r=wt.RECT()
            if not user32.GetWindowRect(wt.HWND(self.client[0]),ctypes.byref(r)):
                return
            names=[q.get('name','') for q in self.quests if q.get('name')]
            self.screen_sync.request_sync((r.left,r.top,r.right,r.bottom),names)
            self.sync_snapshot=self.screen_sync.snapshot()
            skills=self.sync_snapshot.get('skills',{})
            if skills:
                changed=False
                for name,value in skills.items():
                    value=max(1,int(value))
                    if self.cfg['skills'].get(name)!=value:
                        self.cfg['skills'][name]=value
                        changed=True
                if changed:
                    self.persist(); self.refresh_route()
        except Exception:
            pass

'''
    s = s.replace(marker, method + marker, 1)

# Ensure every tick invokes the passive scanner without relying on the exact
# formatting of the existing long tick line.
tick_marker = '    def tick(self):\n        try:\n'
if tick_marker in s and '            self._passive_sync()\n' not in s:
    s = s.replace(tick_marker, '    def tick(self):\n        try:\n            self._passive_sync()\n', 1)

# Draw a denser chain of guidance markers along the existing calibrated
# destination line. These are screen-space guidance markers, not game input.
needle_draw = "if dest:self.oc.create_line(px,py,dest['x'],dest['y'],fill='#ffff00',width=4,arrow='last'); self.oc.create_oval(dest['x']-8,dest['y']-8,dest['x']+8,dest['y']+8,outline='#ffff00',width=3)"
replacement_draw = """if dest:
                self.oc.create_line(px,py,dest['x'],dest['y'],fill='#ffff00',width=4,arrow='last')
                self.oc.create_oval(dest['x']-8,dest['y']-8,dest['x']+8,dest['y']+8,outline='#ffff00',width=3)
                markers=screen_route((px,py),(dest['x'],dest['y']),spacing=26.0,max_markers=48)
                for n,(mx,my) in enumerate(markers,1):
                    size=5 if n%4 else 7
                    self.oc.create_rectangle(mx-size,my-size,mx+size,my+size,outline='#ffcf33',width=2)
                self.oc.create_text(18,102,anchor='w',text=guidance_text(((dest['x']-px)**2+(dest['y']-py)**2)**0.5,len(markers)),fill='#ffcf33',font=('Segoe UI',8))"""
if needle_draw in s and 'markers=screen_route' not in s:
    s = s.replace(needle_draw, replacement_draw, 1)

p.write_text(s, encoding='utf-8')
print('Applied fast passive screen sync and live route guidance markers')
