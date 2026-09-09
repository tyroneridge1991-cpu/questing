"""V2 launcher for the external OSRS Quest Navigator.

Adds faster passive screen synchronization and denser route guidance markers
without sending any input to RuneLite or OSRS.
"""
import time
import math
import tkinter as tk

from app import Navigator as BaseNavigator
from screen_sync import ScreenSync
from pathing import screen_route


class NavigatorV2(BaseNavigator):
    def __init__(self, root):
        self.sync_engine = ScreenSync()
        self.last_sync_request = 0.0
        self.sync_interval = 1.0
        self.last_sync_ts = 0
        self.sync_status = "Account sync: waiting"
        self.sync_initialized = False
        super().__init__(root)
        self.sync_initialized = True
        self._add_sync_status()

    def _add_sync_status(self):
        # Keep the existing UI intact; add a compact live status line to the
        # Overlay tab so the user can see when the passive reader is working.
        if hasattr(self, "track_info"):
            old = self.track_info.cget("text")
            self.track_info.config(text=old + "\n" + self.sync_status)

    def _quest_names(self):
        return [q.get("name", "") for q in self.quests]

    def _apply_sync(self, result):
        if not result:
            return
        changed = False
        skills = result.get("skills") or {}
        for skill, level in skills.items():
            try:
                level = int(level)
            except Exception:
                continue
            if 1 <= level <= 126 and self.cfg["skills"].get(skill, 1) != level:
                self.cfg["skills"][skill] = level
                changed = True

        # Never mark a quest complete merely because its name was visible.
        # Store observations separately; this avoids false completions when a
        # quest list is simply being browsed.
        seen = set(self.cfg.get("quests_observed", []))
        for name in result.get("quests_seen") or []:
            if name not in seen:
                seen.add(name)
                changed = True
        self.cfg["quests_observed"] = sorted(seen)
        self.last_sync_ts = result.get("timestamp", self.last_sync_ts)
        self.sync_status = "Account sync: live" if result.get("status") == "ready" else "Account sync: scanning…"
        if changed:
            self.persist()

    def _passive_sync(self, force=False):
        if not self.client or not self.sync_engine.available():
            self.sync_status = "Account sync: OCR unavailable"
            return
        now = time.monotonic()
        if not force and now - self.last_sync_request < self.sync_interval:
            return
        self.last_sync_request = now
        result = self.sync_engine.request_sync(self.client[2:6], self._quest_names(), force=force)
        self._apply_sync(result)

    def draw_overlay(self):
        # Reuse the working overlay/window mechanics from the base app, then
        # replace the single straight line with readable route markers.
        if not self.overlay or not self.oc or not self.client:
            return
        self.oc.delete("all")
        self.player = self.detect_player()
        stages = self.stages()
        idx = min(self.step, len(stages) - 1) if stages else 0
        key = f'{self.selected["name"]}::{idx}'
        dest = self.cfg.get("route_points", {}).get(key)

        if self.player:
            px, py = self.player
            self.oc.create_oval(px-7, py-7, px+7, py+7, outline="#00ffff", width=2)
            if dest:
                dx, dy = dest["x"], dest["y"]
                points = screen_route((px, py), (dx, dy), spacing=24.0, max_markers=55)
                # Direction line is deliberately subtle; diamonds provide the
                # easy-to-follow step markers.
                self.oc.create_line(px, py, dx, dy, fill="#e6c84a", width=2)
                prev = (px, py)
                for i, (x, y) in enumerate(points, 1):
                    # Small diamond marker, visually similar to a tile marker.
                    size = 5 if i < len(points) else 8
                    self.oc.create_polygon(x, y-size, x+size, y, x, y+size, x-size, y,
                                           outline="#f6df68", fill="#7b6820", width=2)
                    # Tiny direction segment helps when the line crosses scenery.
                    if i % 2 == 0:
                        self.oc.create_line(prev[0], prev[1], x, y, fill="#f6df68", width=2)
                    prev = (x, y)
                self.oc.create_oval(dx-9, dy-9, dx+9, dy+9, outline="#ffd84d", width=3)
                self.oc.create_text(dx, dy-15, text="NEXT", fill="#ffd84d", font=("Segoe UI", 8, "bold"))
        elif dest:
            dx, dy = dest["x"], dest["y"]
            self.oc.create_oval(dx-9, dy-9, dx+9, dy+9, outline="#ffd84d", width=3)

        destname = stages[idx].get("destination", "Complete") if stages and idx < len(stages) else "Complete"
        self.oc.create_rectangle(12, 12, 390, 94, fill="#11151a", outline="#4f6f86")
        self.oc.create_text(22, 25, anchor="w", text=self.selected["name"], fill="white", font=("Segoe UI", 11, "bold"))
        self.oc.create_text(22, 49, anchor="w", text=f"Next: {destname}", fill="white", font=("Segoe UI", 9))
        marker_text = "ROUTE MARKERS ON" if dest and self.player else "CALIBRATE DESTINATION"
        self.oc.create_text(22, 72, anchor="w", text=f"{marker_text} • Step {idx+1 if stages else 0}/{len(stages)}",
                            fill="#9fe6ff", font=("Segoe UI", 9))

    def tick(self):
        # Base class handles window attachment, overlay positioning and UI.
        super().tick()
        if self.sync_initialized:
            try:
                self._passive_sync()
                if hasattr(self, "track_info"):
                    tracked = "detected" if self.player else "not detected"
                    self.track_info.config(text=f"Player highlight: {tracked}\nCurrent step: {self.step+1 if self.stages() else 0}\n{self.sync_status}")
            except Exception:
                pass


if __name__ == "__main__":
    root = tk.Tk()
    NavigatorV2(root)
    root.mainloop()
