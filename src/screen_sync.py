import asyncio
import os
import re
import tempfile
import threading
import time

try:
    from PIL import ImageGrab
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

    Captures the selected game window and uses Windows OCR. It never moves
    the mouse, clicks, types, or sends input to RuneLite.
    """
    def __init__(self):
        self.engine = None
        self.lock = threading.Lock()
        self.last = {'timestamp': 0, 'skills': {}, 'quests_seen': [],
                     'inventory_text': [], 'equipment_text': [], 'bank_text': [],
                     'raw_text': '', 'sources': []}

    def available(self):
        return ImageGrab is not None and WinRTOCR is not None

    def _ocr(self, image):
        if not self.available():
            return []
        fd, path = tempfile.mkstemp(suffix='.png', prefix='osrs_sync_')
        os.close(fd)
        try:
            image.save(path, 'PNG')
            if self.engine is None:
                self.engine = WinRTOCR()
            result = asyncio.run(self.engine.ocr(path, lang='en-US', detail_level='line'))
            return result or []
        except Exception:
            return []
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
            pat=re.compile(r'\b'+re.escape(label)+r'\b[^0-9]{0,16}(\d{1,3})\b', re.I)
            for text,_ in lines:
                m=pat.search(text)
                if m:
                    try:
                        n=int(m.group(1))
                        if 1 <= n <= 126:
                            found[skill]=n
                            break
                    except Exception: pass
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

    def sync(self, rect, quest_names):
        image=self.capture(rect)
        if image is None:
            return self.snapshot()
        ocr_lines=self._ocr(image)
        lines=self.parse_lines(ocr_lines)
        text='\n'.join(x[0] for x in lines)
        result={
            'timestamp': int(time.time()*1000),
            'skills': self.parse_skills(lines),
            'quests_seen': self.known_quests(text, quest_names),
            'inventory_text': [],
            'equipment_text': [],
            'bank_text': [],
            'raw_text': text[:12000],
            'sources': self.classify(text),
        }
        with self.lock:
            self.last=result
        return result

    def snapshot(self):
        with self.lock:
            return dict(self.last)
