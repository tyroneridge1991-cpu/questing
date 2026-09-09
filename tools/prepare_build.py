from pathlib import Path
p = Path('src/app.py')
s = p.read_text(encoding='utf-8')
needle = "self.overlay=tk.Toplevel(self.root); self.overlay.overrideredirect(True); self.overlay.attributes('-topmost',True); self.overlay.configure(bg='#010101');"
replacement = "self.overlay=tk.Toplevel(self.root); self.overlay.overrideredirect(True); self.overlay.attributes('-topmost',True); self.overlay.attributes('-transparentcolor','#010101'); self.overlay.configure(bg='#010101');"
if needle not in s:
    raise SystemExit('Expected overlay initialization was not found')
p.write_text(s.replace(needle, replacement, 1), encoding='utf-8')
print('Prepared transparent click-through overlay build')
