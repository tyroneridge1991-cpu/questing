import asyncio
import json
import os
import re
import tempfile
import threading
import time

try:
    from PIL import ImageGrab, Image
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
    """Read-only RuneLite screen synchronizer.

    It never moves the mouse, clicks, types, or sends input to RuneLite.
    It captures the selected window and uses Windows OCR where available.
    """
    def __init__(self):
        self.engine = None
        self.lock = threading.Lock()
        self.last = {'timestamp': 0, 'skills': {}, 'quests_seen': [], 'inventory_text': [],
                     'equipment_text': [], 'bank_text': [], 'raw_text': '', 'sources': []}
        self.running = False
        self.thread = None
        self.interval = 4.0

    def available(self):
        return ImageGrab is not None and WinRTOCR is not None

    def _ocr(self, image):
        if not self.available():
            return ''
        fd, path = tempfile.mkstemp(suffix='.png', prefix='osrs_sync_')
        os.close(fd)
        try:
            image.save(path, 'PNG')
            if self.engine is None:
                self.engine = WinRTOCR()
            lines = asyncio.run(self.engine.ocr(path, lang='en-US', detail_level='line'))
            out=[]
            for line in lines or []:
                if isinstance(line, str):
                    out.append(line)
                elif isinstance(line, dict):
                    out.append(str(line.get('text','')))
                else:
                    text=getattr(line,'text',None)
                    if text: out.append(str(text))
            return '\n'.join(x.strip() for x in out if x and x.strip())
        except Exception:
            return ''
        finally:
            try: os.remove(path)
            except Exception: pass

    def capture(self, rect):
        if ImageGrab is None or not rect:
            return None
        try:
            l,t,r,b=rect
            return ImageGrab.grab(bbox=(l,t,r,b), all_screens=True).convert('RGB')
        except Exception:
            return None

    def parse_skills(self, text):
        found={}
        lines=text.splitlines()
        for skill in SKILLS:
            label=skill.replace('defence','defence').title()
            # OCR often returns either "Attack 20" or separate lines with the number nearby.
            pat=re.compile(r'\b'+re.escape(label)+r'\b[^0-9]{0,12}(\d{1,3})\b', re.I)
            for line in lines:
                m=pat.search(line)
                if m:
                    try:
                        n=int(m.group(1))
                        if 1 <= n <= 126: found[skill]=n
                    except Exception: pass
                    break
        return found

    def known_quests(self, text, quest_names):
        low=text.lower()
        return [q for q in quest_names if q.lower() in low]

    def classify(self, text):
        low=text.lower()
        source=[]
        if any(x in low for x in ('attack','strength','defence','ranged','prayer','magic')): source.append('skills')
        if 'quest' in low or 'completed' in low: source.append('quests')
        if 'inventory' in low: source.append('inventory')
        if 'equipment' in low: source.append('equipment')
        if 'bank' in low: source.append('bank')
        return source

    def sync(self, rect, quest_names):
        image=self.capture(rect)
        if image is None:
            return self.last
        text=self._ocr(image)
        skills=self.parse_skills(text)
        sources=self.classify(text)
        result={
            'timestamp': int(time.time()*1000),
            'skills': skills,
            'quests_seen': self.known_quests(text, quest_names),
            'inventory_text': [],
            'equipment_text': [],
            'bank_text': [],
            'raw_text': text[:12000],
            'sources': sources,
        }
        with self.lock:
            self.last=result
        return result

    def snapshot(self):
        with self.lock:
            return dict(self.last)
