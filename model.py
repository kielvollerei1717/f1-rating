"""F1 1990-2026 driver / constructor rating model.

Pairwise Bradley-Terry fit:  logit P(i beats j) = d_i - d_j + c_i - c_j
  d = driver skill, c = car strength per (constructor, year).
Car effect cancels inside a team -> teammate duels identify d.
Joint fit identifies c from cross-team results; multi-decade drivers bridge eras.

Outputs ratings.json for the report page.
"""
import sqlite3, json, math, sys
import numpy as np

DB = sys.argv[1] if len(sys.argv) > 1 else r'C:\Users\kielz\f1db-data\x\f1db.db'
OUT = sys.argv[2] if len(sys.argv) > 2 else 'ratings.json'
Y0, Y1 = 1990, 2026
MIN_STARTS = 10

con = sqlite3.connect(DB)
cur = con.cursor()

rows = cur.execute("""
select d.race_id, r.year, r.round, r.date, d.driver_id, d.constructor_id,
       d.position_number, d.position_text, d.race_points,
       d.race_grid_position_number, d.race_positions_gained, d.race_fastest_lap,
       d.race_reason_retired, d.race_laps
from race_data d join race r on r.id = d.race_id
where d.type='RACE_RESULT' and r.year between ? and ?
order by r.year, r.round
""", (Y0, Y1)).fetchall()

starts_by = {}
for r in rows:
    starts_by[r[4]] = starts_by.get(r[4], 0) + 1
# every driver who took a race start is rated. Sparse drivers are handled by the
# prior (a handful of duels barely moves them off the mean) and flagged as
# provisional in the output, rather than hidden.
pool = {d_ for d_, n in starts_by.items() if n >= 1}
rows_fit = rows

drivers = sorted(pool)
didx = {d: i for i, d in enumerate(drivers)}
cars = sorted({(r[5], r[1]) for r in rows_fit})
cidx = {c: i for i, c in enumerate(cars)}
ND, NC = len(drivers), len(cars)

by_race_fit = {}
for r in rows_fit:
    by_race_fit.setdefault(r[0], []).append(r)

pi, pj, py, pci, pcj = [], [], [], [], []
for rid, rl in by_race_fit.items():
    ys = rl[0][1]
    fin = [x for x in rl if x[6] is not None]
    for a in range(len(fin)):
        for b in range(a + 1, len(fin)):
            A, B = fin[a], fin[b]
            if A[6] == B[6]:
                continue
            pi.append(didx[A[4]]); pj.append(didx[B[4]])
            pci.append(cidx[(A[5], ys)]); pcj.append(cidx[(B[5], ys)])
            py.append(1.0 if A[6] < B[6] else 0.0)
pi = np.array(pi); pj = np.array(pj); py = np.array(py)
pci = np.array(pci); pcj = np.array(pcj)
n = len(pi)
print(f'pairs={n} drivers={ND} car-seasons={NC}')

theta = np.zeros(ND + NC)
L2D = 1 / 0.65 ** 2   # driver skill sd 0.65 logit ~ 113 Elo
L2C = 1 / 0.50 ** 2   # car sd 0.50 ~ 87 Elo
prior = np.concatenate([np.full(ND, L2D), np.full(NC, L2C)])
lr = 0.4
m = np.zeros_like(theta); v = np.zeros_like(theta)
for it in range(1, 15001):
    z = theta[pi] - theta[pj] + theta[ND + pci] - theta[ND + pcj]
    p = 1.0 / (1.0 + np.exp(-z))
    g = p - py
    grad = prior * theta
    np.add.at(grad, pi, g); np.add.at(grad, pj, -g)
    np.add.at(grad, ND + pci, g); np.add.at(grad, ND + pcj, -g)
    m = 0.9 * m + 0.1 * grad
    v = 0.999 * v + 0.001 * grad * grad
    theta -= lr * (m / (1 - 0.9 ** it)) / (np.sqrt(v / (1 - 0.999 ** it)) + 1e-8)
    if it % 5000 == 0:
        ll = -np.mean(py * np.log(p + 1e-12) + (1 - py) * np.log(1 - p + 1e-12))
        print(f'  it{it} logloss={ll:.4f} sd_d={theta[:ND].std():.3f} sd_c={theta[ND:].std():.3f}')

d = theta[:ND] - theta[:ND].mean()
c = theta[ND:] - theta[ND:].mean()
K = 400.0 / math.log(10)
elo_of = lambda x: 1500 + K * x

# ---- driver metadata ----
meta = {}
for r in cur.execute('select id, full_name, first_name, last_name, nationality_country_id, '
                     'date_of_birth, total_championship_wins, total_race_starts, '
                     'total_pole_positions, total_podiums, total_race_wins, total_grand_slams, '
                     'total_driver_of_the_day, best_championship_position, total_race_entries, '
                     'total_fastest_laps, total_race_laps, best_starting_grid_position, '
                     'best_race_result, permanent_number, place_of_birth, date_of_death '
                     'from driver'):
    meta[r[0]] = dict(full=r[1], first=r[2], last=r[3], nat=r[4], dob=r[5], titles=r[6] or 0,
                      db_starts=r[7], db_poles=r[8], db_podiums=r[9], db_wins=r[10],
                      slams=r[11], dotd=r[12], best_champ=r[13], entries=r[14], db_fl=r[15],
                      db_laps=r[16], db_bestgrid=r[17], db_bestres=r[18], perma=r[19],
                      pob=r[20], dod=r[21])

MECH = ('engine', 'gearbox', 'gears', 'transmission', 'clutch', 'hydraulic', 'electrical', 'suspension',
        'brake', 'exhaust', 'oil', 'water', 'fuel', 'radiator', 'turbo', 'throttle', 'steering',
        'wheel', 'driveshaft', 'differential', 'battery', 'alternator', 'ignition', 'misfire',
        'vibration', 'overheat', 'pneumatic', 'halfshaft', 'axle', 'spark plug', 'distributor',
        'carburettor', 'power unit', 'ers', 'mg', 'energy', 'drivetrain', 'cooling', 'injector',
        'sensor', 'pressure', 'fire', 'damper', 'chassis', 'underweight', 'undertray', 'oil pressure')
DRV = ('accident', 'collision', 'spun', 'off track', 'driver error', 'withdrew', 'injury', 'ill',
       'black flag', 'crashed', 'damage', 'excluded')

agg = {d_: dict(starts=0, wins=0, podiums=0, poles=0, fl=0, points=0.0, dnf=0, mech=0, drv=0,
                finishes=0, pos_sum=0, best=99, seasons=set(), cars=[], gained=[], finpos=[],
                quali_pos=[], quali_beats=0, quali_cnt=0, top10=0, dnfs_drv_years=set())
       for d_ in drivers}

for r in rows:
    _, yr, rnd, dt, drv, cons, pos, ptxt, pts, grid, gained, fl, ret, laps = r
    if drv not in agg:
        continue
    a = agg[drv]
    a['starts'] += 1
    a['seasons'].add(yr)
    a['cars'].append((cons, yr))
    if pts:
        a['points'] += pts
    if pos is not None:
        a['finishes'] += 1
        a['pos_sum'] += pos
        a['finpos'].append(pos)
        a['best'] = min(a['best'], pos)
        if pos <= 10:
            a['top10'] += 1
        if pos <= 3:
            a['podiums'] += 1
        if pos == 1:
            a['wins'] += 1
    if grid == 1:
        a['poles'] += 1
    if fl:
        a['fl'] += 1
    if gained is not None:
        a['gained'].append(gained)
    if ret or ptxt in ('DNF', 'DSQ', 'EX', 'NC', 'DNQ', 'DNPQ', 'DNS', 'DNP'):
        a['dnf'] += 1
        rl = (ret or '').lower()
        if any(k in rl for k in MECH):
            a['mech'] += 1
        elif any(k in rl for k in DRV):
            a['drv'] += 1
    if grid is not None and pos is not None:
        a['quali_pos'].append((grid, pos))

# quali head-to-head per driver (all pairs of classified quali, cheap proxy: beat field rate)
qrows = cur.execute("""
select r.year, r.round, d.driver_id, d.constructor_id, d.position_number, d.race_id
from race_data d join race r on r.id=d.race_id
where d.type='QUALIFYING_RESULT' and r.year between ? and ? and d.position_number is not null
""", (Y0, Y1)).fetchall()
qrace = {}
for yr, rnd, drv, cons, qp, rid in qrows:
    qrace.setdefault(rid, []).append((drv, cons, qp))
qbeat = {}
for rid, mem in qrace.items():
    nf = len(mem)
    if nf < 4:
        continue
    for drv, cons, qp in mem:
        if drv in agg:
            qbeat.setdefault(drv, []).append((nf - qp) / (nf - 1))

# teammate duels split by session type; matchup detail for the page (a<b alphabetically)
tq = {}; tr = {}
mup = {}
def _pair(a, b, year, cons):
    lo, hi = (a, b) if a < b else (b, a)
    return mup.setdefault((lo, hi, year, cons), dict(a=lo, b=hi, year=year, cons=cons,
                                                     qn=0, qw=0, rn=0, rw=0))
qrace_year = {}
for yr, rnd, drv, cons, qp, rid in qrows:
    qrace_year[rid] = yr
for rid, mem in qrace.items():
    yr = qrace_year.get(rid, 0)
    g = {}
    for drv, cons, qp in mem:
        g.setdefault(cons, []).append((drv, qp))
    for cons, mm in g.items():
        if len(mm) != 2:
            continue
        (d1, p1), (d2, p2) = mm
        if p1 == p2:
            continue
        w, l = (d1, d2) if p1 < p2 else (d2, d1)
        tq.setdefault(w, [0, 0]); tq.setdefault(l, [0, 0])
        tq[w][0] += 1; tq[l][1] += 1
        m = _pair(d1, d2, yr, cons)
        m['qn'] += 1; m['qw'] += 1 if w == m['a'] else 0

for rid, rl in by_race_fit.items():
    yr = rl[0][1]
    g = {}
    for x in rl:
        g.setdefault(x[5], []).append(x)
    for cons, mem in g.items():
        if len(mem) != 2:
            continue
        A, B = mem
        if A[6] is None or B[6] is None or A[6] == B[6]:
            continue
        w, l = (A[4], B[4]) if A[6] < B[6] else (B[4], A[4])
        tr.setdefault(w, [0, 0]); tr.setdefault(l, [0, 0])
        tr[w][0] += 1; tr[l][1] += 1
        m = _pair(A[4], B[4], yr, cons)
        m['rn'] += 1; m['rw'] += 1 if w == m['a'] else 0

# comparison count per driver -> Elo standard error
cmp_n = np.zeros(ND, dtype=np.int64)
np.add.at(cmp_n, pi, 1); np.add.at(cmp_n, pj, 1)

# per driver-season skill: beat-rate vs classified field, minus that season's car effect
car_of = {}
for r in rows_fit:
    car_of.setdefault((r[4], r[1]), cidx[(r[5], r[1])])
beat = {}
for rid, rl in by_race_fit.items():
    ys = rl[0][1]
    fin = [x for x in rl if x[6] is not None]
    if len(fin) < 4:
        continue
    nf = len(fin)
    for x in fin:
        beat.setdefault((x[4], ys), []).append((nf - x[6]) / (nf - 1))
season_pts = {}
for r in cur.execute('select driver_id, year, position_display_order, points, championship_won '
                     'from season_driver_standing where year between ? and ?', (Y0, Y1)):
    season_pts[(r[0], r[1])] = dict(pos=r[2], pts=r[3], won=r[4])
seasonskill = {}
for (drv, ys), bs in beat.items():
    b = min(max(float(np.mean(bs)), 1e-3), 1 - 1e-3)
    sk = math.log(b / (1 - b)) - c[car_of[(drv, ys)]]
    st = season_pts.get((drv, ys), {})
    seasonskill.setdefault(drv, []).append(dict(year=ys, skill=sk, pos=st.get('pos'),
                                                points=st.get('pts'), champion=bool(st.get('won'))))

# era density: how many drivers overlap each season (for honest era comparison)
era_field_sum = {}
field_skill = {}
for drv, ss in seasonskill.items():
    for s in ss:
        field_skill.setdefault(s['year'], []).append(s['skill'])
era_mean = {y: float(np.mean(v)) for y, v in field_skill.items()}
era_sd = {y: float(np.std(v)) or 1.0 for y, v in field_skill.items()}
era_n = {y: len(v) for y, v in field_skill.items()}

# constructor-season ratings: EVERY car that raced in the window, not only the ones
# the championship table lists. Rows the WCC table omits (non-classified / no-score
# entrants like Simtek 1994, Forti 1995-96, Minardi 1996-98) still get a car rating.
cs = cur.execute("""
select s.year, s.constructor_id, s.position_display_order, s.points, s.championship_won
from season_constructor_standing s where s.year between ? and ?
""", (Y0, Y1)).fetchall()
stand_of = {(yr, cons): dict(standing=pos, points=pts, champion=bool(won))
            for yr, cons, pos, pts, won in cs}
cmeta = {r[0]: dict(name=r[1], country=r[2], titles=r[3])
         for r in cur.execute('select id, name, country_id, total_championship_wins from constructor')}
# points actually scored that season across all races (works even with no WCC row)
season_pts_team = {}
season_res_team = {}
for r in rows_fit:
    k = (r[5], r[1])
    if r[8]:
        season_pts_team[k] = season_pts_team.get(k, 0.0) + r[8]
for (cons, yr) in cars:
    k = (cons, yr)
    rr = [x for x in rows_fit if x[5] == cons and x[1] == yr]
    season_res_team[k] = len(rr)
carstat = {}
for (cons, yr) in cars:
    ci_ = cidx[(cons, yr)]
    st = stand_of.get((yr, cons), {})
    cm = cmeta.get(cons, {})
    races_n = len({x[0] for x in rows_fit if x[5] == cons and x[1] == yr})
    carstat[(cons, yr)] = dict(year=yr, constructor=cons, name=cm.get('name', cons.replace('-', ' ').title()),
                               country=cm.get('country'), standing=st.get('standing'),
                               points=round(season_pts_team.get((cons, yr), 0.0), 1),
                               champion=st.get('champion', False), classified=bool(st),
                               races=races_n, team_titles=cm.get('titles', 0), elo=elo_of(c[ci_]))

# era-normalized points: points are scored on wildly different systems across the
# window (9-6-4 to 25-18-15, plus fastest-lap and sprint points), so raw totals are
# not comparable. Each season's points are divided by the champion's haul that year,
# giving "share of the best possible" - a number that means the same in 1994 and 2024.
season_max_pts = {}
for (drv, yr), v in season_pts.items():
    if v.get('pts'):
        season_max_pts[yr] = max(season_max_pts.get(yr, 0.0), v['pts'])
for drv, ss in seasonskill.items():
    for s in ss:
        mx = season_max_pts.get(s['year']) or 0.0
        s['points_pct'] = round(s['points'] / mx, 4) if (mx and s['points']) else 0.0

# real career span (all years in DB, incl. pre-1990), not just the fitted window
career = {}
for drv, yr in cur.execute('select driver_id, year from season_driver_standing'):
    c_ = career.setdefault(drv, dict(first=9999, last=0, n=0))
    c_['first'] = min(c_['first'], yr); c_['last'] = max(c_['last'], yr); c_['n'] += 1
for drv in drivers:
    if drv in career:
        career[drv]['titles'] = meta.get(drv, {}).get('titles', 0)

# ---------------- assemble ----------------
K_ = K
def pct(vals):
    order = np.argsort(np.argsort(np.asarray(vals, float)))
    return 40 + 59 * order / max(len(vals) - 1, 1)

raw = []
for drv in drivers:
    a = agg[drv]
    ss = sorted(seasonskill.get(drv, []), key=lambda x: x['year'])
    sk = elo_of(d[  didx[drv]])
    # peak = best rolling 3-season mean skill, else best single season
    peak = max((s['skill'] for s in ss), default=0.0)
    if len(ss) >= 3:
        roll = [np.mean([s['skill'] for s in ss[i:i + 3]]) for i in range(len(ss) - 2)]
        peak = max(peak, max(roll))
    car_elo = float(np.mean([elo_of(c[cidx[k]]) for k in a['cars']])) if a['cars'] else 1500.0
    qq = tq.get(drv, [0, 0]); rr = tr.get(drv, [0, 0])
    qn, rn = qq[0] + qq[1], rr[0] + rr[1]
    qb = float(np.mean(qbeat.get(drv, [0.5])))
    grid_ok = sum(1 for g, p in a['quali_pos'] if g > p)
    grid_err = sum(1 for g, p in a['quali_pos'] if g < p)
    # Elo standard error from comparison count
    se = K / math.sqrt(2 * cmp_n[didx[drv]]) if cmp_n[didx[drv]] else 0.0
    ca = career.get(drv, {})
    raw.append(dict(
        id=drv, name=meta.get(drv, {}).get('full', drv.replace('-', ' ').title()),
        first=meta.get(drv, {}).get('first'), last=meta.get(drv, {}).get('last'),
        nat=meta.get(drv, {}).get('nat'), dob=meta.get(drv, {}).get('dob'),
        titles=meta.get(drv, {}).get('titles', 0),
        best_champ=meta.get(drv, {}).get('best_champ'),
        slams=meta.get(drv, {}).get('slams', 0), dotd=meta.get(drv, {}).get('dotd', 0),
        elo=elo_of(d[didx[drv]]), elo_se=round(se, 1),
        elo_lo=round(elo_of(d[didx[drv]]) - 1.96 * se), elo_hi=round(elo_of(d[didx[drv]]) + 1.96 * se),
        peak_elo=elo_of(peak),
        # career-window stats (1990-2026)
        starts=a['starts'], wins=a['wins'], podiums=a['podiums'], poles=a['poles'],
        fastest_laps=a['fl'], points=round(a['points'], 2), top10=a['top10'],
        dnf=a['dnf'], dnf_mech=a['mech'], dnf_drv=a['drv'],
        finish_rate=round(a['finishes'] / a['starts'], 3) if a['starts'] else 0,
        avg_finish=round(a['pos_sum'] / a['finishes'], 2) if a['finishes'] else None,
        best_finish=a['best'] if a['best'] < 99 else None,
        finish_sd=round(float(np.std(a['finpos'])), 2) if len(a['finpos']) > 1 else None,
        avg_gained=round(float(np.mean(a['gained'])), 2) if a['gained'] else None,
        gain_rate=round(float(np.mean([1 if g > 0 else 0 for g in a['gained']])), 3) if a['gained'] else None,
        # full-career stats (incl. pre-1990)
        career_starts=meta.get(drv, {}).get('db_starts'), career_wins=meta.get(drv, {}).get('db_wins'),
        career_podiums=meta.get(drv, {}).get('db_podiums'), career_poles=meta.get(drv, {}).get('db_poles'),
        career_seasons=ca.get("n"), career_first=ca.get('first'), career_last=ca.get('last'),
        career_titles=ca.get('titles'),
        career_entries=meta.get(drv, {}).get('entries'),
        career_fastest_laps=meta.get(drv, {}).get('db_fl'),
        career_laps=meta.get(drv, {}).get('db_laps'),
        career_best_grid=meta.get(drv, {}).get('db_bestgrid'),
        career_best_result=meta.get(drv, {}).get('db_bestres'),
        permanent_number=meta.get(drv, {}).get('perma'),
        place_of_birth=meta.get(drv, {}).get('pob'),
        grand_slams=meta.get(drv, {}).get('slams', 0),
        driver_of_the_day=meta.get(drv, {}).get('dotd', 0),
        quali_beat_field=round(qb, 3),
        grid_ok=grid_ok, grid_err=grid_err,
        quali_h2h_wins=qq[0], quali_h2h_losses=qq[1],
        quali_h2h_rate=round(qq[0] / qn, 3) if qn else None,
        race_h2h_wins=rr[0], race_h2h_losses=rr[1],
        race_h2h_rate=round(rr[0] / rn, 3) if rn else None,
        teammate_wins=qq[0] + rr[0], teammate_losses=qq[1] + rr[1],
        teammate_rate=round((qq[0] + rr[0]) / (qn + rn), 3) if (qn + rn) else None,
        seasons=ss, n_seasons=len(a['seasons']),
        first_season=min(a['seasons']), last_season=max(a['seasons']),
        avg_car_elo=round(car_elo, 1),
        driver_excess=round(elo_of(d[didx[drv]]) - car_elo, 1),
        win_rate=round(a['wins'] / a['starts'], 4) if a['starts'] else 0,
        podium_rate=round(a['podiums'] / a['starts'], 4) if a['starts'] else 0,
        pole_rate=round(a['poles'] / a['starts'], 4) if a['starts'] else 0,
        top10_rate=round(a['top10'] / a['starts'], 4) if a['starts'] else 0,
        points_per_start=round(a['points'] / a['starts'], 3) if a['starts'] else 0,
        era_points=round(float(np.mean([s.get('points_pct', 0) for s in ss])), 4) if ss else 0.0,
        era_z=round(float(np.mean([(s['skill'] - era_mean[s['year']]) / era_sd[s['year']]
                                   for s in ss])), 3) if ss else 0.0,
    ))

# per-season field rank (percentile within that season's rated field)
season_pool = {}
for drv, ss in seasonskill.items():
    for s in ss:
        season_pool.setdefault(s['year'], []).append((s['skill'], drv))
for yr, lst in season_pool.items():
    lst.sort(reverse=True)
    for pos, (sk, drv) in enumerate(lst, 1):
        for s in seasonskill[drv]:
            if s['year'] == yr:
                s['field_pos'] = pos
                s['field_n'] = len(lst)

# teammate matchups per driver, aggregated over all pairings
byteammate = {}
for (lo, hi, yr, cons), m in mup.items():
    for who, other in ((lo, hi), (hi, lo)):
        t = byteammate.setdefault(who, {})
        e = t.setdefault(other, dict(id=other, years=[], cons=set(), qw=0, qn=0, rw=0, rn=0))
        e['years'].append(yr); e['cons'].add(cons)
        if who == m['a']:
            e['qw'] += m['qw']; e['rw'] += m['rw']
        else:
            e['qw'] += m['qn'] - m['qw']; e['rw'] += m['rn'] - m['rw']
        e['qn'] += m['qn']; e['rn'] += m['rn']
for drv, x in [(v['id'], v) for v in raw]:
    tms = []
    for other, e in byteammate.get(drv, {}).items():
        oi = didx.get(other)
        gap = (elo_of(d[didx[drv]]) - elo_of(d[oi])) if oi is not None else None
        tms.append(dict(id=other, name=meta.get(other, {}).get('full', other.replace('-', ' ').title()),
                        years=sorted(set(e['years'])), constructors=sorted(e['cons']),
                        quali_won=e['qw'], quali_n=e['qn'], race_won=e['rw'], race_n=e['rn'],
                        quali_rate=round(e['qw'] / e['qn'], 3) if e['qn'] else None,
                        race_rate=round(e['rw'] / e['rn'], 3) if e['rn'] else None,
                        combined_rate=round((e['qw'] + e['rw']) / (e['qn'] + e['rn']), 3) if (e['qn'] + e['rn']) else None,
                        elo_gap=round(gap, 1) if gap is not None else None))
    tms.sort(key=lambda z: (min(z['years'])))
    x['teammates'] = tms

# composite rating (0-100), percentile-blended
def sc(key, vals, lo=None, hi=None):
    arr = np.asarray([v[key] if v[key] is not None else -999 for v in vals], float)
    return pct(arr)

R = {k: sc(k, raw) for k in ['elo', 'peak_elo', 'driver_excess', 'era_z', 'teammate_rate',
                             'points_per_start', 'podium_rate', 'finish_rate', 'top10_rate',
                             'era_points']}
# era-relative excess: driver_excess measured against the field of their own years
exc_era = np.array([x['driver_excess'] - (np.mean([era_mean[s['year']] for s in x['seasons']]) - 1500)
                    if x['seasons'] else x['driver_excess'] for x in raw])
R['exc_era'] = pct(exc_era)
# consistency = does he finish, and does he finish near the front. Raw position
# spread is deliberately NOT used: a backmarker who always brings it home P15 has
# a tiny spread and would otherwise score as "consistent".
cons_raw = np.array([0.60 * x['finish_rate'] + 0.40 * (x['top10_rate'] or 0) for x in raw])
R['consistency'] = pct(cons_raw)
# sample confidence, independent of the rating itself
ncomp = np.array([cmp_n[didx[x['id']]] for x in raw], float)
R['confidence'] = pct(ncomp)

for i, x in enumerate(raw):
    for k, v in R.items():
        x[k + '_pct'] = round(float(v[i]), 1)
    x['exc_era'] = round(float(exc_era[i]), 1)
    x['consistency'] = round(float(R['consistency'][i]), 1)
    x['consistency_raw'] = round(float(cons_raw[i]), 3)
    x['confidence'] = round(float(R['confidence'][i]), 1)
    # OVR: skill, consistency and era-normalized points carry the weight. Volume
    # (starts, seasons, career totals) is deliberately absent - a long career is not
    # a rating input.
    ovr = (0.23 * R['elo'][i] + 0.16 * R['peak_elo'][i] + 0.13 * R['consistency'][i]
           + 0.13 * R['era_z'][i] + 0.11 * R['exc_era'][i] + 0.09 * R['teammate_rate'][i]
           + 0.09 * R['era_points'][i] + 0.03 * R['points_per_start'][i]
           + 0.03 * R['podium_rate'][i])
    x['ovr'] = round(float(ovr), 1)
    x['peak_ovr'] = round(float(0.40 * R['peak_elo'][i] + 0.30 * R['era_z'][i]
                                + 0.14 * R['elo'][i] + 0.09 * R['consistency'][i]
                                + 0.07 * R['era_points'][i]), 1)
    # rookie = still-new career (debuted in the last two seasons), so the rating is
    # early; low_sample = thin data regardless of era. Both are flagged, not penalised.
    x['is_rookie'] = bool((x['career_last'] or 0) >= Y1 - 1 and (x['career_first'] or 0) >= Y1 - 2)
    x['low_sample'] = bool(x['starts'] < 10)
    x['provisional'] = bool(x['is_rookie'] or x['low_sample'])
    # archetype from measurable behaviour (percentile thresholds within pool)
    ag = (x['dnf_drv'] / x['dnf']) if x['dnf'] else 0
    gain = x['gain_rate'] if x['gain_rate'] is not None else 0.5
    cons = x['finish_rate']
    qual = x['quali_beat_field']
    qh = x['quali_h2h_rate'] if x['quali_h2h_rate'] is not None else 0.5
    rh = x['race_h2h_rate'] if x['race_h2h_rate'] is not None else 0.5
    tags = []
    if qh - rh > 0.10 and qh > 0.55:
        tags.append('One-lap specialist (faster than race pace)')
    if rh - qh > 0.10 and rh > 0.55:
        tags.append('Race-day racer (beats teammate on Sunday)')
    if cons >= 0.85:
        tags.append('Reliable finisher')
    elif ag >= 0.40 and x['dnf'] >= 12:
        tags.append('Crash-prone / high variance')
    if (x['avg_gained'] or 0) >= 1.0:
        tags.append('Overtaker (big grid-to-flag gains)')
    elif (x['avg_gained'] or 0) <= -0.5:
        tags.append('Starts well, loses ground')
    if (x['avg_finish'] or 99) < 6.0:
        tags.append('Front-runner')
    x['tags'] = tags
ranked = sorted(raw, key=lambda x: -x['ovr'])
for i, x in enumerate(ranked):
    x['rank'] = i + 1
peakranked = sorted(raw, key=lambda x: -x['peak_ovr'])
for i, x in enumerate(peakranked):
    x['rank_peak'] = i + 1
elov = [x['elo'] for x in raw]
for x in raw:
    eps = 0.5
    beat_avg = 0
    x['elo_ci'] = round(float(K * (1 / math.sqrt(x['starts']))), 1)

csr = sorted(carstat.values(), key=lambda x: -x['elo'])
for i, x in enumerate(csr):
    x['rank'] = i + 1
cv = [x['elo'] for x in csr]
cr = pct(cv)
for x, r in zip(csr, cr):
    x['rating'] = round(float(r), 1)

json.dump(dict(years=[Y0, Y1], n_pairs=int(n), min_starts=1, n_races=len({r[0] for r in rows}),
               n_drivers=len(raw), n_cars=len(csr), drivers=raw, cars=csr,
               era_mean=era_mean, era_n=era_n), open(OUT, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
print(f'wrote {OUT}: {len(raw)} drivers, {len(csr)} car-seasons')

print('\n-- TOP 30 CAREER OVR --')
for x in ranked[:30]:
    print(f"{x['rank']:3d} {x['name'][:26]:26s} ovr={x['ovr']:5.1f} elo={x['elo']:6.0f} peak={x['peak_elo']:6.0f} "
          f"W{x['wins']:3d} T{x['titles']} car={x['avg_car_elo']:5.0f} exc={x['driver_excess']:+6.1f} "
          f"tm={x['teammate_rate']} ez={x['era_z']:+.2f}")
print('\n-- TOP 15 PEAK --')
for x in peakranked[:15]:
    print(f"{x['rank_peak']:3d} {x['name'][:26]:26s} pk={x['peak_ovr']:5.1f} peakelo={x['peak_elo']:6.0f} ez={x['era_z']:+.2f}")
print('\n-- TOP 15 CARS --')
for x in csr[:15]:
    print(f"{x['rank']:3d} {x['year']} {x['name'][:15]:15s} elo={x['elo']:6.0f} r={x['rating']:5.1f} st={x['standing']} pts={x['points']}")
print('\n-- bottom 5 drivers (sanity) --')
for x in ranked[-5:]:
    print(f"{x['rank']:3d} {x['name'][:26]:26s} ovr={x['ovr']:5.1f} elo={x['elo']:6.0f} starts={x['starts']}")
