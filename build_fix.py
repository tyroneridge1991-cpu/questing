from pathlib import Path

p = Path('src/app.py')
s = p.read_text(encoding='utf-8')

# Strengthen the overlay so the separate overlay window never receives mouse input.
start = s.index('    def make_clickthrough(self, win):')
end = s.index('\n\n    def position_overlay', start)
replacement = '''    def make_clickthrough(self, win):
        """Make the overlay visible but completely non-interactive on Windows."""
        if os.name != 'nt':
            return

        # Tk does not always have the final native HWND ready until it has
        # processed pending geometry/layout work.
        win.update_idletasks()
        hwnd = win.winfo_id()

        GWL_EXSTYLE = -20
        WS_EX_LAYERED = 0x00080000
        WS_EX_TRANSPARENT = 0x00000020
        WS_EX_NOACTIVATE = 0x08000000
        WS_EX_TOOLWINDOW = 0x00000080
        LWA_COLORKEY = 0x00000001
        SWP_NOSIZE = 0x0001
        SWP_NOMOVE = 0x0002
        SWP_NOACTIVATE = 0x0010
        SWP_NOOWNERZORDER = 0x0200
        HWND_TOPMOST = ctypes.c_void_p(-1)

        # Preserve Tk's existing styles and add the documented top-level
        # layered-window click-through/no-activate styles.
        ex = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        ex |= WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex)

        # Black is the overlay's transparent background. The route itself is
        # drawn in non-black pixels. This also gives Windows a real layered
        # window for hit testing rather than relying only on Tk transparency.
        try:
            user32.SetLayeredWindowAttributes(hwnd, 0x00010101, 0, LWA_COLORKEY)
        except Exception:
            pass

        user32.SetWindowPos(
            hwnd, HWND_TOPMOST, 0, 0, 0, 0,
            SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE | SWP_NOOWNERZORDER
        )
'''
s = s[:start] + replacement + s[end:]

# Make sure the overlay itself is prepared after Tk has created its native HWND.
s = s.replace(
    "self.overlay=tk.Toplevel(self.root); self.overlay.overrideredirect(True); self.overlay.attributes('-topmost',True); self.overlay.configure(bg='#010101')",
    "self.overlay=tk.Toplevel(self.root); self.overlay.overrideredirect(True); self.overlay.attributes('-topmost',True); self.overlay.configure(bg='#010101'); self.overlay.update_idletasks()",
    1,
)

p.write_text(s, encoding='utf-8')
print('Patched overlay to be reliably click-through and non-activating')
