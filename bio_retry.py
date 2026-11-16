"""Re-attempt the MISS drivers with hand-tuned Wikipedia titles."""
import json, os, time, urllib.parse, urllib.request, urllib.error, re

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, 'bios.json')
UA = 'f1-rating-bio/1.0 (research cache; runs locally)'
API = 'https://en.wikipedia.org/w/api.php'
cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
ratings = json.load(open(os.path.join(HERE, 'ratings.json'), encoding='utf-8'))
by_id = {d['id']: d for d in ratings['drivers']}

OVERRIDES = {
    'allan-mcnish': 'Allan McNish',
    'carlos-sainz-jr': 'Carlos Sainz Jr.',
    'jarno-trulli': 'Jarno Trulli',
    'kimi-raikkonen': 'Kimi Räikkönen',
    'mika-hakkinen': 'Mika Häkkinen',
    'nikita-mazepin': 'Nikita Mazepin',
    'sergey-sirotkin': 'Sergey Sirotkin',
    'toranosuke-takagi': 'Toranosuke Takagi',
    'ukyo-katayama': 'Ukyo Katayama',
    'valtteri-bottas': 'Valtteri Bottas',
    'yuki-tsunoda': 'Yuki Tsunoda',
    'daniil-kvyat': 'Daniil Kvyat',
    'nyck-de-vries': 'Nyck de Vries',
    'jack-doohan': 'Jack Doohan',
    'eric-van-de-poele': 'Eric van de Poele',
    'ricardo-zonta': 'Ricardo Zonta',
    'tarso-marques': 'Tarso Marques',
    'robert-kubica': 'Robert Kubica',
    'romain-grosjean': 'Romain Grosjean',
    'esteban-gutierrez': 'Esteban Gutiérrez',
    'juan-pablo-montoya': 'Juan Pablo Montoya',
    'rubens-barrichello': 'Rubens Barrichello',
    'heinz-harald-frentzen': 'Heinz-Harald Frentzen',
    'giovanni-lavaggi': 'Giovanni Lavaggi',
    'marco-apicella': 'Marco Apicella',
    'vincenzo-sospiri': 'Vincenzo Sospiri',
}

def wiki_text(title):
    p = urllib.parse.urlencode({'action': 'parse', 'page': title, 'prop': 'wikitext',
                               'format': 'json', 'formatversion': '2', 'redirects': 1})
    for attempt in range(6):
        req = urllib.request.Request(API + '?' + p, headers={'User-Agent': UA})
        try:
            j = json.load(urllib.request.urlopen(req, timeout=30))
            return j.get('parse', {}).get('wikitext', '')
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(2 ** attempt * 3); continue
            raise
    return ''

def extract(title, wt):
    b = {}
    for field in ('full_name', 'born', 'nationality', 'residence', 'carting_years',
                 'carting_championships', 'f1_years', 'first_f1_entry',
                 'championship_wins', 'podiums', 'pole_positions', 'points',
                 'teams', 'other_cars', 'other_championships', 'relatives', 'height', 'weight'):
        m = re.search(r'\|\s*' + field + r'\s*=\s*(.+)', wt)
        if m:
            b[field] = m.group(1).strip()
    sections = []
    for m in re.finditer(r'==+([A-Z][^=]{2,40}?)==+', wt):
        h = m.group(1).strip()
        if any(k in h.lower() for k in
               ('karting', '24 hours', 'le mans', 'wec', 'endurance', 'gt', 'moto',
                'dakar', 'motocross', 'superbike', 'pre-f1', 'pre-f1 career',
                'career before', 'other racing', 'after f1', 'post-f1', 'racing career')):
            sections.append(h)
    b['off_f1_sections'] = sorted(set(sections))
    m = re.search(r'\[\[?karting career\]?\]([^\n]{20,400})', wt, re.I)
    if m:
        b['karting_note'] = m.group(1).strip()
    return b

missing = [i for i in cache if not cache[i].get('found')]
print('retrying', len(missing), 'missing:', missing)
for did in missing:
    title = OVERRIDES.get(did) or (by_id[did].get('name') if did in by_id else None)
    if not title:
        print('  no override for', did)
        continue
    wt = wiki_text(title)
    if wt:
        b = extract(title, wt); b['title'] = title; b['found'] = True
        cache[did] = b
        print(f'  fixed {did} -> {title}')
    else:
        print(f'  still MISS {did} ({title})')
    time.sleep(1.5)
json.dump(cache, open(CACHE, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
ok = sum(1 for v in cache.values() if v.get('found'))
print(f'retry done: {ok}/{len(cache)} found')
