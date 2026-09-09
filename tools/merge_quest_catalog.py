import json, os, re, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data', 'quests.json')
URL = 'https://raw.githubusercontent.com/jamescer/osrs-tools/master/src/runescape/model/quest/QuestList.ts'

try:
    text = urllib.request.urlopen(URL, timeout=20).read().decode('utf-8')
    names = re.findall(r"^\s*(['\"])(.*?)\1,?\s*$", text, re.M)
    names = [n[1] for n in names]
except Exception as exc:
    print('Quest catalog download failed; keeping bundled catalog:', exc)
    raise SystemExit(0)

with open(DATA, 'r', encoding='utf-8') as f:
    existing = json.load(f)
old = {q.get('name'): q for q in existing.get('quests', [])}
merged = []
for name in names:
    q = old.get(name, {
        'name': name,
        'difficulty': 'Unknown',
        'members': True,
        'prerequisites': [],
        'steps': []
    })
    merged.append(q)

with open(DATA, 'w', encoding='utf-8') as f:
    json.dump({'quests': merged, 'source': 'jamescer/osrs-tools QuestList; enriched route data maintained separately'}, f, indent=2, ensure_ascii=False)
print(f'Built quest catalog with {len(merged)} quests.')
