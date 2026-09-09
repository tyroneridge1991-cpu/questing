from pathlib import Path
p = Path('src/app.py')
s = p.read_text(encoding='utf-8')
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
p.write_text(s[:start] + replacement + s[end:], encoding='utf-8')
print('Patched OSRS window detection')
