import json, os, time

SYNC_DIR = os.path.join(os.path.expanduser('~'), 'AppData', 'Local', 'OSRSQuestNavigator')
SYNC_FILE = os.path.join(SYNC_DIR, 'account.json')

def read_snapshot():
    try:
        with open(SYNC_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        data['_read_at'] = time.time()
        return data
    except Exception:
        return None
