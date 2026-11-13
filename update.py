"""Fetch latest f1db SQLite release and rebuild ratings.json + data.js."""
import json, os, subprocess, sys, tempfile, urllib.request, zipfile

REL = 'https://api.github.com/repos/f1db/f1db/releases/latest'

req = urllib.request.Request(REL, headers={'User-Agent': 'f1-rating-updater'})
rel = json.load(urllib.request.urlopen(req, timeout=30))
tag = rel['tag_name']
asset = next(a for a in rel['assets'] if a['name'] == 'f1db-sqlite.zip')
print(f'latest f1db release: {tag} ({asset["size"] // 1048576} MB)')

with tempfile.TemporaryDirectory() as tmp:
    zpath = os.path.join(tmp, 'f1db-sqlite.zip')
    urllib.request.urlretrieve(asset['browser_download_url'], zpath)
    with zipfile.ZipFile(zpath) as z:
        z.extractall(tmp)
    db = os.path.join(tmp, 'f1db.db')
    subprocess.check_call([sys.executable, 'model.py', db, 'ratings.json'])
    subprocess.check_call([sys.executable, 'prep.py'])

# Stamp the release tag into the page source footer/method line if present
if os.path.exists('index.html'):
    import re
    h = open('index.html', encoding='utf-8').read()
    h2 = re.sub(r'release v\d+\.\d+\.\d+', f'release {tag}', h)
    if h2 != h:
        open('index.html', 'w', encoding='utf-8').write(h2)
print('updated for', tag)
