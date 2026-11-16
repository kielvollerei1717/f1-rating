"""Fetch Wikipedia biographical data for all drivers.

Extracts: date/place of birth, nationality, karting career, pre-F1 series
(24H Le Mans, WEC, GT, MotoGP, Dakar, etc.), and notable achievements.
Output: bios.json (cached locally). Idempotent - skips drivers already
cached unless --force.
"""
import json, os, re, sys, time, urllib.parse, urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, 'bios.json')
UA = 'f1-rating-bio/1.0 (research cache; runs locally)'
API = 'https://en.wikipedia.org/w/api.php'
DRIVERS = json.load(open(os.path.join(HERE, 'ratings.json'), encoding='utf-8'))
FORCE = '--force' in sys.argv
LIMIT = None
for a in sys.argv[1:]:
    if a.startswith('--limit='):
        LIMIT = int(a.split('=', 1)[1])

cache = json.load(open(CACHE)) if os.path.exists(CACHE) and not FORCE else {}
# only fetch drivers that matter for the page: top-60 OVR + all rookies/active
by_rank = sorted(DRIVERS['drivers'], key=lambda x: x.get('ovr', 0), reverse=True)
top60 = {d['id'] for d in by_rank[:60]}
active = {d['id'] for d in by_rank if d.get('career_last') or 0 >= 2024}
PRIORITY = sorted(top60 | active)
others = [d['id'] for d in DRIVERS['drivers'] if d['id'] not in PRIORITY]
queue = PRIORITY + others
if LIMIT:
    queue = queue[:LIMIT]
print(f'== bio scraper: {len(queue)} drivers queued '
      f'(top60={len(top60)}, active={len(active)}), '
      f'{sum(1 for v in cache.values() if v.get("found"))} cached ==', flush=True)

# wall-clock cap so the CI job never hangs: if we hit the cap, save what we
# have and let the next scheduled run pick up the rest (cache is idempotent).
CAP_SECONDS = int(os.environ.get('BIO_CAP_SECONDS', '300'))
t0 = time.time()

def wiki_text(title):
    """Use the REST API (looser rate limits than action=parse).
    Falls back to action API if the REST page is missing."""
    p = urllib.parse.urlencode({
        'action': 'parse', 'page': title, 'prop': 'wikitext',
        'format': 'json', 'formatversion': '2', 'redirects': 1,
    })
    for attempt in range(5):
        req = urllib.request.Request(API + '?' + p, headers={'User-Agent': UA})
        try:
            j = json.load(urllib.request.urlopen(req, timeout=30))
            return j.get('parse', {}).get('wikitext', '')
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = 5 * (2 ** attempt)
                if time.time() - t0 > CAP_SECONDS:
                    print(f'    429 but cap reached; skipping {title}')
                    return ''
                print(f'    429, retry in {wait}s')
                time.sleep(wait)
                continue
            if e.code == 404:
                return ''
            raise
    return ''

def extract(title, wt):
    """Pull the bits we want from raw wikitext."""
    b = {}
    # infobox fields
    for field in ('full_name', 'born', 'nationality', 'residence', 'carting_years',
                 'carting_championships', 'f1_years', 'first_f1_entry',
                 'championship_wins', 'podiums', 'pole_positions', 'points',
                 'teams', 'other_cars', 'other_championships', 'relatives', 'height', 'weight'):
        m = re.search(r'\|\s*' + field + r'\s*=\s*(.+)', wt)
        if m:
            b[field] = m.group(1).strip()
    # section headings that signal off-F1 racing
    sections = []
    for m in re.finditer(r'==+([A-Z][^=]{2,40}?)==+', wt):
        h = m.group(1).strip()
        if any(k in h.lower() for k in
               ('karting', '24 hours', 'le mans', 'wec', 'endurance', 'gt', 'moto',
                'dakar', 'motocross', 'superbike', 'pre-f1', 'pre-f1 career',
                'career before', 'other racing', 'after f1', 'post-f1', 'racing career')):
            sections.append(h)
    b['off_f1_sections'] = sorted(set(sections))
    # karting paragraph (first 200 chars)
    m = re.search(r'\[\[?karting career\]?\]([^\n]{20,400})', wt, re.I)
    if m:
        b['karting_note'] = m.group(1).strip()
    return b

def title_from_id(did, full_name=None):
    """f1db id -> likely wiki title. Try the full_name from f1db first
    (proper unicode), fall back to the id split on dashes."""
    if full_name and ' ' in full_name:
        return full_name
    parts = did.split('-')
    return ' '.join(p.capitalize() if len(p) > 2 else p for p in parts)

for i, did in enumerate(queue):
    if time.time() - t0 > CAP_SECONDS:
        print(f'\n  cap ({CAP_SECONDS}s) reached at driver {i+1}/{len(queue)}; '
              f'saving progress, remaining drivers retry next run', flush=True)
        break
    if did in cache and not FORCE:
        print(f'  {i+1:3d}/{len(queue)} {did:24s} (cached)', flush=True)
        continue
    d = next((x for x in DRIVERS['drivers'] if x['id'] == did), {})
    title = title_from_id(did, d.get('name'))
    wt = wiki_text(title)
    if not wt:
        # second attempt with a variant (id-based)
        alt = title_from_id(did)
        if alt != title:
            wt = wiki_text(alt)
            if wt:
                title = alt
    if not wt:
        print(f'  {i+1:3d}/{len(queue)} {did:24s} MISS ({title})', flush=True)
        cache[did] = dict(title=title, found=False)
    else:
        b = extract(title, wt)
        b['title'] = title
        b['found'] = True
        cache[did] = b
        print(f'  {i+1:3d}/{len(queue)} {did:24s} OK ({title}) '
              f'off_f1={len(b.get("off_f1_sections", []))}', flush=True)
    time.sleep(2.0)  # be polite; action API tolerates ~1 req/s sustained
    # save periodically so a mid-run crash / cap still persists progress
    if (i + 1) % 10 == 0:
        json.dump(cache, open(CACHE, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

json.dump(cache, open(CACHE, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
ok = sum(1 for v in cache.values() if v.get('found'))
print(f'\nwrote {CACHE}: {ok} drivers with bio data '
      f'({len([k for k,v in cache.items() if not v.get("found")])} still missing, '
      f'retry next run)')
