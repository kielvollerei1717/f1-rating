"""Fetch latest f1db SQLite release and rebuild ratings.json + data.js."""
import json, os, subprocess, sys, tempfile, time, urllib.request, urllib.error, zipfile

REL = 'https://api.github.com/repos/f1db/f1db/releases/latest'
HDRS = {'User-Agent': 'f1-rating-updater'}
# In GitHub Actions the GITHUB_TOKEN env var lets us avoid the 60/hour
# unauthenticated rate limit. Locally, fall back to the public API.
tok = os.environ.get('GITHUB_TOKEN') or os.environ.get('GH_TOKEN')
if tok:
    HDRS['Authorization'] = f'token {tok}'

def gh_get(url, timeout=30):
    for attempt in range(5):
        req = urllib.request.Request(url, headers=HDRS)
        try:
            return json.load(urllib.request.urlopen(req, timeout=timeout))
        except urllib.error.HTTPError as e:
            if e.code == 403:
                reset = e.headers.get('X-RateLimit-Reset')
                wait = int(reset) - int(time.time()) if reset else 30 * (2 ** attempt)
                print(f'    403 rate limit, retry in {wait}s')
                time.sleep(max(wait, 0))
                continue
            if e.code == 404:
                return None
            raise
    raise SystemExit('GitHub API rate limit not lifted after retries')

rel = gh_get(REL)
tag = rel['tag_name']
asset = next(a for a in rel['assets'] if a['name'] == 'f1db-sqlite.zip')
print(f'latest f1db release: {tag} ({asset["size"] // 1048576} MB)')

with tempfile.TemporaryDirectory() as tmp:
    zpath = os.path.join(tmp, 'f1db-sqlite.zip')
    req = urllib.request.Request(asset['browser_download_url'], headers=HDRS)
    open(zpath, 'wb').write(urllib.request.urlopen(req, timeout=300).read())
    with zipfile.ZipFile(zpath) as z:
        z.extractall(tmp)
    db = os.path.join(tmp, 'f1db.db')
    subprocess.check_call([sys.executable, 'model.py', db, 'ratings.json'])
    # prep.py runs here (ratings only); the workflow re-runs it after bio.py
    # so the committed data.js always has the freshest bios merged in
    subprocess.check_call([sys.executable, 'prep.py'])

# Stamp the release tag into the page source footer/method line if present
if os.path.exists('index.html'):
    import re
    h = open('index.html', encoding='utf-8').read()
    h2 = re.sub(r'release v\d+\.\d+\.\d+', f'release {tag}', h)
    if h2 != h:
        open('index.html', 'w', encoding='utf-8').write(h2)
print('updated for', tag)
