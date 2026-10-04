"""Reaggregate frozen GitHub output fields; this does not rerun 137-image fusion."""
import collections, json, pathlib
ROOT=pathlib.Path(__file__).parent
rows=json.loads((ROOT/'compact_sensitivity.json').read_text())
assert len(rows)==822
keys={(r['image'],r['threshold_deg'],r['method']) for r in rows}
assert len(keys)==822
settings=sorted({(r['threshold_deg'],r['method']) for r in rows})
assert len(settings)==6
valid=[r for r in rows if r['status']!='unavailable' and 'point_minus_lee_iou' in r]
sets=[{r['image'] for r in valid if (r['threshold_deg'],r['method'])==s} for s in settings]
common=set.intersection(*sets)
assert len(common)==61
expected=json.loads((ROOT/'independent_common_support.json').read_text())
def mean(seq): return sum(seq)/len(seq)
for s in settings:
    selected=[r for r in valid if r['image'] in common and (r['threshold_deg'],r['method'])==s]
    target=next(r['commonComplete'] for r in expected['summary'] if r['setting']==str(s[0]).replace('.0','')+'_'+s[1])
    actual=mean([r['point_minus_lee_iou'] for r in selected])
    assert abs(actual-target['point_minus_lee_iou_mean'])<1e-12
    print(s, 'common_n=',len(selected),'point_minus_lee=',actual,collections.Counter(r['status'] for r in selected))
for status in ['ok','geometry_review']:
    selected=[r for r in rows if r['threshold_deg']==5 and r['method']=='mv50' and r['status']==status]
    actual=mean([r['point_minus_lee_iou'] for r in selected])
    print('default',status,len(selected),actual)
print('PASS: 822 unique rows; 61 common images; all JS summaries agree with independent Python aggregation')
