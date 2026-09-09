from pathlib import Path
p = Path('src/app.py')
s = p.read_text(encoding='utf-8')

# Fix/strengthen OSRS window detection.
start = s.index('def find_osrs_window():')
end = s.index('\n\nclass Navigator:', start)
replacement = '''def find_osrs_window():
    """Find the OSRS game window despite Jagex/RuneLite title variations."""
    if os.name != 'nt':
        return None
    matches = []
    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def callback(hwnd, _):
        try:
            if not user32.IsWindowVisible(hwnd):
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return True
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            title = buf.value.strip()
            low = title.lower()
            if not title or 'osrs quest navigator' in low:
                return True

            title_match = any(x in low for x in (
                'old school runescape', 'old school', 'runelite', 'runescape', 'jagex client'
            ))
            process_match = False
            pid = ctypes.wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            hproc = user32.OpenProcess(0x1000, False, pid.value)
            if hproc:
                try:
                    size = ctypes.wintypes.DWORD(1024)
                    exe_buf = ctypes.create_unicode_buffer(1024)
                    if user32.QueryFullProcessImageNameW(hproc, 0, exe_buf, ctypes.byref(size)):
                        exe = exe_buf.value.lower()
                        process_match = any(x in exe for x in ('runelite', 'rs2client', 'osrs', 'jagex'))
                finally:
                    user32.CloseHandle(hproc)

            if not (title_match or process_match):
                return True
            rect = ctypes.wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            if rect.right - rect.left < 400 or rect.bottom - rect.top < 300:
                return True
            matches.append((hwnd, title, rect.left, rect.top, rect.right, rect.bottom))
        except Exception:
            pass
        return True

    user32.EnumWindows(EnumWindowsProc(callback), 0)
    if not matches:
        return None
    def score(item):
        t = item[1].lower()
        if 'old school runescape' in t: return 0
        if 'runelite' in t: return 1
        if 'runescape' in t: return 2
        return 3
    matches.sort(key=score)
    return matches[0]
'''
s = s[:start] + replacement + s[end:]

# Make the separate route overlay non-interactive. Layered + transparent keeps
# mouse input going to the game underneath and prevents the overlay taking focus.
old = """    def make_clickthrough(self,win):\n        if os.name!='nt':return\n        hwnd=win.winfo_id(); ex=user32.GetWindowLongW(hwnd,-20); user32.SetWindowLongW(hwnd,-20,ex|0x80000|0x20)\n"""
new = """    def make_clickthrough(self, win):\n        if os.name != 'nt':\n            return\n        hwnd = win.winfo_id()\n        GWL_EXSTYLE = -20\n        WS_EX_LAYERED = 0x00080000\n        WS_EX_TRANSPARENT = 0x00000020\n        WS_EX_NOACTIVATE = 0x08000000\n        WS_EX_TOOLWINDOW = 0x00000080\n        ex = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)\n        ex |= WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW\n        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex)\n        SWP_NOSIZE = 0x0001\n        SWP_NOMOVE = 0x0002\n        SWP_NOACTIVATE = 0x0010\n        SWP_NOOWNERZORDER = 0x0200\n        user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0,\n                            SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE | SWP_NOOWNERZORDER)\n"""
if old not in s:
    raise SystemExit('Expected make_clickthrough block was not found')
s = s.replace(old, new, 1)

p.write_text(s, encoding='utf-8')
print('Patched OSRS detection and click-through overlay')
