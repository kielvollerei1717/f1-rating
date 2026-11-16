"""Trim ratings.json into data.js for the artifact."""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
d = json.load(open(os.path.join(HERE, 'ratings.json'), encoding='utf-8'))
bios = json.load(open(os.path.join(HERE, 'bios.json'), encoding='utf-8')) if os.path.exists(os.path.join(HERE, 'bios.json')) else {}

keep_drv = ('id name nat dob titles best_champ slams dotd elo elo_se elo_lo elo_hi peak_elo '
            'starts wins podiums poles fastest_laps points top10 dnf dnf_mech dnf_drv finish_rate '
            'avg_finish best_finish finish_sd avg_gained gain_rate career_starts career_wins '
            'career_podiums career_poles career_seasons career_first career_last career_titles '
            'career_entries career_fastest_laps career_laps career_best_grid career_best_result '
            'permanent_number place_of_birth grand_slams driver_of_the_day '
            'quali_beat_field grid_ok grid_err quali_h2h_wins quali_h2h_losses quali_h2h_rate '
            'race_h2h_wins race_h2h_losses race_h2h_rate teammate_rate seasons teammates '
            'n_seasons first_season last_season avg_car_elo driver_excess win_rate podium_rate '
            'pole_rate points_per_start top10_rate era_points era_z exc_era consistency confidence '
            'provisional is_rookie low_sample tags ovr peak_ovr rank rank_peak').split()

drivers = []
for x in d['drivers']:
    y = {k: x.get(k) for k in keep_drv}
    y['seasons'] = [dict(year=s['year'], skill=round(s['skill'], 3), pos=s.get('pos'),
                         points=s.get('points'), champion=s.get('champion'),
                         field_pos=s.get('field_pos'), field_n=s.get('field_n')) for s in x['seasons']]
    y['teammates'] = [{k: t[k] for k in ('id', 'name', 'years', 'constructors', 'quali_won',
                                         'quali_n', 'race_won', 'race_n', 'quali_rate',
                                         'race_rate', 'combined_rate', 'elo_gap')} for t in x['teammates']]
    b = bios.get(x['id'])
    if b and b.get('found'):
        y['bio'] = {k: b[k] for k in ('karting_note', 'off_f1_sections', 'title',
                                      'born', 'nationality', 'other_cars', 'other_championships')
                    if k in b and b.get(k)}
    drivers.append(y)

cars = [{k: c[k] for k in ('year', 'constructor', 'name', 'country', 'standing', 'points',
                           'champion', 'classified', 'races', 'team_titles', 'elo', 'rating', 'rank')}
        for c in d['cars']]

out = dict(years=d['years'], n_pairs=d['n_pairs'], min_starts=d.get('min_starts', 1),
           n_races=d.get('n_races'), n_drivers=len(drivers), n_cars=len(cars), drivers=drivers, cars=cars,
           era_mean=d['era_mean'], era_n=d['era_n'])
txt = json.dumps(out, ensure_ascii=False, separators=(',', ':'))
open('data.js', 'w', encoding='utf-8').write('window.F1DATA=' + txt + ';')
print('data.js', len(txt) // 1024, 'KB,', len(drivers), 'drivers,', len(cars), 'cars')
