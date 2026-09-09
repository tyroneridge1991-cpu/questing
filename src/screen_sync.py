import asyncio
import hashlib
import os
import tempfile
import threading
import time

try:
    from PIL import ImageGrab, ImageEnhance, ImageOps
except Exception:
    ImageGrab = None

try:
    from winrtocr import WinRTOCR
except Exception:
    WinRTOCR = None

SKILLS = [
    'attack','strength','defence','ranged','prayer','magic','runecraft',
    'construction','hitpoints','agility','herblore','thieving','crafting',
    'fletching','slayer','hunter','mining','smithing','fishing','cooking',
    'firemaking','woodcutting','farming'
]

class ScreenSync:
    """Fast, read-only RuneLite screen synchronizer.

    OCR is moved to a worker thread, screenshots are fingerprinted before OCR,
    and the right-side client panel is preferred because it contains most
    account UI. The synchronizer never moves the mouse, clicks, types, or
    sends input to RuneLite.
    """
    def __init__(self):
        self.engine = None
        self.lock = threading.Lock()
        self.worker_lock = threading.Lock()
        self.last_hash = None
        self.last = {'timestamp': 0, 'skills': {}, 'quests_seen': [],
                     'inventory_text': [], 'equipment_text': [], 'bank_text': [],
                     'raw_text': '', 'sources': [], 'status': 'idle'}
        self.pending = False

    def available(self):
        return ImageGrab is not None and WinRTOCR is not None

    def _ocr(self, image):
        if not self.available():
            return []
        fd, path = tempfile.mkstemp(suffix='.png', prefix='osrs_sync_')
        os.close(fd)
        try:
            # Upscale a little and increase contrast: this improves small
            # RuneLite side-panel text without OCR-ing the whole game canvas.
            image = image.resize((image.width*2, image.height*2))
            image = ImageOps.grayscale(image)
            image = ImageEnhance.Contrast(image).enhance(1.6)
            image.save(path, 'PNG', optimize=True)
            if self.engine is None:
                self.engine = WinRTOCR()
            result = asyncio.run(self.engine.ocr(path, lang='en-US', detail_level='line'))
            return result or []
        except Exception:
            return []
        finally:
            try: os.remove(path)
            except Exception: pass

    def capture(self, rect, panel_only=True):
        if ImageGrab is None or not rect:
            return None
        try:
            l,t,r,b=rect
            if panel_only:
                # RuneLite's account interfaces normally live on the right.
                width=r-l
                l=max(l, r-min(360, max(260, width//3)))
            return ImageGrab.grab(bbox=(l,t,r,b), all_screens=True).convert('RGB')
        except Exception:
            return None

    def fingerprint(self, image):
        if image is None:
            return None
        # Tiny thumbnail hash is much cheaper than OCR and catches interface
        # changes such as opening Skills, Quests, Inventory or Bank.
        try:
            thumb=image.resize((64,64))
            return hashlib.blake2b(thumb.tobytes(), digest_size=8).hexdigest()
        except Exception:
            return None

    def parse_lines(self, ocr_lines):
        clean=[]
        for item in ocr_lines:
            if isinstance(item, (tuple,list)):
                text=str(item[0]).strip() if item else ''
                bbox=item[1] if len(item)>1 else None
            elif isinstance(item, dict):
                text=str(item.get('text','')).strip(); bbox=item.get('bbox')
            else:
                text=str(item).strip(); bbox=None
            if text:
                clean.append((text,bbox))
        return clean

    def parse_skills(self, lines):
        found={}
        for skill in SKILLS:
            label=skill.title()
            for text,_ in lines:
                # Accept the common RuneLite/OSRS forms: "Attack 42" and
                # "Attack 42/99" while rejecting implausible OCR numbers.
                import re
                pat=re.compile(r'\b'+re.escape(label)+r'\b[^0-9]{0,16}(\d{1,3})\b', re.I)
                m=pat.search(text)
                if m:
                    try:
                        n=int(m.group(1))
                        if 1 <= n <= 126:
                            found[skill]=n
                            break
                    except Exception:
                        pass
        return found

    def known_quests(self, text, quest_names):
        low=text.lower()
        return [q for q in quest_names if q.lower() in low]

    def classify(self, text):
        low=text.lower()
        source=[]
        if any(x in low for x in ('attack','strength','defence','ranged','prayer','magic','runecraft')):
            source.append('skills')
        if 'quest' in low or 'completed' in low:
            source.append('quests')
        if 'inventory' in low:
            source.append('inventory')
        if 'equipment' in low:
            source.append('equipment')
        if 'bank' in low:
            source.append('bank')
        return source

    def _do_sync(self, rect, quest_names, force=False):
        image=self.capture(rect, panel_only=True)
        fp=self.fingerprint(image)
        if not force and fp == self.last_hash:
            return self.snapshot()
        self.last_hash=fp
        with self.lock:
            self.last['status']='scanning'
        ocr_lines=self._ocr(image)
        lines=self.parse_lines(ocr_lines)
        text='\n'.join(x[0] for x in lines)
        result={
            'timestamp': int(time.time()*1000),
            'skills': self.parse_skills(lines),
            'quests_seen': self.known_quests(text, quest_names),
            'inventory_text': [], 'equipment_text': [], 'bank_text': [],
            'raw_text': text[:12000], 'sources': self.classify(text),
            'status': 'ready',
        }
        with self.lock:
            self.last=result
        return result

    def request_sync(self, rect, quest_names, force=False):
        """Queue a scan without blocking Tkinter's UI thread."""
        if self.pending:
            return self.snapshot()
        self.pending=True
        def worker():
            try:
                self._do_sync(rect, quest_names, force)
            finally:
                self.pending=False
        threading.Thread(target=worker, daemon=True, name='osrs-screen-sync').start()
        return self.snapshot()

    def sync(self, rect, quest_names, force=False):
        """Compatibility entry point; now non-blocking."""
        return self.request_sync(rect, quest_names, force)

    def snapshot(self):
        with self.lock:
            return dict(self.last)
