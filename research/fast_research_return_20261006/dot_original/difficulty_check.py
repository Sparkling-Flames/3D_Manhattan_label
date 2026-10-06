import csv,json
from pathlib import Path
from collections import defaultdict,Counter
R=Path('D:/Work/HOHONET')
def read(p):return list(csv.DictReader((R/p).open(encoding='utf-8-sig',newline='')))
roster={r['image']:r for r in read('analysis_results/difficulty_consensus_20261006/difficulty_roster.csv')}
old=[dict(r,distance=float(r['omission_fraction'])+float(r['extension_fraction'])) for r in read('analysis_results/lee_expanded_20261003/image_curves.csv') if r['condition']=='manual' and r['version']=='original']
new=[dict(r,distance=float(r['ref_symdiff_ref'])) for r in read('analysis_results/worker_count_composition_20261006/per_image.csv') if r['condition']=='manual' and r['version']=='original' and r['scenario']=='uniform' and r['policy']=='none']
summary=read('analysis_results/difficulty_consensus_20261006/summary.csv');err=0;output=[]
for s in summary:
    source=old if s['panel_n']=='8' else new
    rs=[r for r in source if int(r['n'])>=int(s['panel_n']) and r['method']==s['method'] and r['k']==s['k'] and roster[r['image']]['difficulty']==s['difficulty'] and roster[r['image']]['scene'] in ('clear','unflagged') and (s['scope']=='all' or (roster[r['image']]['building'].startswith('uNb'))==(s['scope']=='within_uNb'))]
    assert len(rs)==int(s['image_count']) and len({r['image'] for r in rs})==len(rs)
    assert {r['image'] for r in rs}==set(s['images'].split('|'))
    v=sum(r['distance'] for r in rs)/len(rs);err=max(err,abs(v-float(s['mean_distance'])))
    if s['scope']=='all' and s['method']=='mv50' and s['k'] in ('1',s['panel_n']):output.append(s)
common=json.loads((R/'analysis_results/worker_profiles_20261003/block.json').read_text(encoding='utf-8'))['images']
result=dict(summary_rows=len(summary),max_mean_difference=err,common10_difficulty=dict(Counter(roster[i]['difficulty'] for i in common)),selected=output)
assert err<1e-12
Path(__file__).with_name('difficulty_check.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result))
