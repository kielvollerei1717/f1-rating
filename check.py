# runnable self-check: payload/pipeline invariants + the page contract
import json, re, pathlib
D = json.loads(pathlib.Path('data.js').read_text(encoding='utf-8').split('window.F1DATA=',1)[1].rstrip(';'))
h = pathlib.Path('index.html').read_text(encoding='utf-8')

# 1. every driver field the page reads must exist in the payload
used = set(re.findall(r'\bd\.([a-z_][a-z0-9_]*)', h))
used = {u for u in used if u not in ('d','s','y')}
missing = used - set(D['drivers'][0]) - {'bio'}   # bio is optional by design
assert not missing, f'page reads fields absent from data.js: {sorted(missing)}'

# 2. driver rows must not be <button>: the VS button sits inside and would be ejected
#    the Seasons tab row may stay a <button> (no nested control); the driver
#    card row may not, because the VS button lives inside it
assert "'<button class=\"row\" data-id='" not in h
assert "'<div class=\"row\" role=\"button\" tabindex=\"0\"" in h

# 3. run metadata is real, not a stub
assert D['n_races'] and D['n_pairs'] and D['logloss'] is not None
assert len(D['drivers']) == D['n_drivers'] and len(D['cars']) == D['n_cars']
assert '0.393' not in h          # stale hard-coded fit error must be gone

# 4. prose matches the model flag (provisional = under 10 starts, not 20)
assert '(under 10 starts)' in h and '(under 20 starts)' not in h

print(f"races={D['n_races']} pairs={D['n_pairs']} logloss={D['logloss']} "
      f"drivers={D['n_drivers']} cars={D['n_cars']} bios={sum(1 for d in D['drivers'] if d.get('bio'))} "
      f"prov={sum(1 for d in D['drivers'] if d.get('provisional'))}")
print('OK')
