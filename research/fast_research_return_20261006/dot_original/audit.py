import csv, json, math, itertools, sys
from pathlib import Path
from functools import lru_cache
from collections import Counter, defaultdict
import numpy as np

ROOT=Path('D:/Work/HOHONET')
OUT=Path(__file__).parent
BASE=ROOT/'analysis_results/worker_count_composition_20261006'
def read(p):
    return list(csv.DictReader(p.open(encoding='utf-8-sig',newline='')))
rows=read(BASE/'per_image.csv'); summaries=read(BASE/'summary.csv')
data=json.loads((BASE/'input.json').read_text(encoding='utf-8'))
panels=json.loads((BASE/'panels.json').read_text(encoding='utf-8'))
bases=np.load(BASE/'integration_bases.npz')
assignments=read(BASE/'assignments.csv')
matrices={p:read(ROOT/f'analysis_results/worker_profiles_20261003/matrix_{p}_iou.csv') for p in ('original','revised_where_available')}
workers=[x for x in matrices['original'][0] if x.startswith('P')]
train_buildings={r['building'] for r in matrices['original']}
groups={(g['image'],g['condition']):g for g in data['groups'] if g['status']=='selected'}
assert len(groups)==57
assert all(len(g['records'])==len({r['worker'] for r in g['records']}) for g in groups.values())
assert all(len(g['records'])==len({r['id'] for r in g['records']}) for g in groups.values())
akeys=[(r['image'],r['policy'],r['worker']) for r in assignments]
assert len(akeys)==len(set(akeys))
labels={}
for r in assignments:
    train=[x for x in matrices[r['policy']] if x['building']!=r['building']]
    assert set(r['train_images'].split('|'))=={x['image'] for x in train}
    assert all(x['building']!=r['building'] for x in train)
    scores={w:sum(float(x[w]) for x in train)/len(train) for w in workers}
    ordered=sorted(scores.values()); cut=(ordered[11]+ordered[12])/2
    assert (r['higher']=='True')==(scores[r['worker']]>cut)
    labels[r['image'],r['policy'],r['worker']]=r['higher']=='True'

@lru_cache(None)
def pmf(n,c,k):
    return tuple((j,math.comb(c,j)*math.comb(n-c,k-j)/math.comb(n,k)) for j in range(max(0,k-n+c),min(c,k)+1))
@lru_cache(None)
def qcalc(ns,cs,ks,strict):
    k=sum(ks);t=k//2+1 if strict else (k+1)//2
    return sum(math.prod(x[1] for x in a) for a in itertools.product(*(pmf(n,c,z) for n,c,z in zip(ns,cs,ks))) if sum(x[0] for x in a)>=t)

maxerr=defaultdict(float)
keys=[]
for r in rows:
    key=r['basis_key'];area=bases[key+'_area'];patterns=bases[key+'_patterns'];inside=bases[key+'_'+r['version']+'_overlap'];ga=float(bases[key+'_'+r['version']+'_area'])
    n=int(r['n']); k=int(r['k']); strict=r['method']=='mv_strict'; g=groups[r['image'],r['condition']]
    assert n==len(g['records'])
    keys.append(tuple(r[x] for x in ('image','condition','scenario','policy','strategy','method','k','version')))
    if r['scenario']=='uniform':
        qs=np.array([qcalc((n,),(int(p).bit_count(),),(k,),strict) for p in patterns])
    else:
        hm=sum(1<<j for j,x in enumerate(g['records']) if labels[r['image'],r['policy'],x['worker']]);nh=hm.bit_count();h=int(r['higher_n'])
        lo=max(0,k-(n-nh));hi=min(k,nh)
        assert h==dict(lower_rich=lo,balanced=min(hi,max(lo,k//2)),higher_rich=hi)[r['strategy']]
        qs=np.array([qcalc((nh,n-nh),((int(p)&hm).bit_count(),int(p).bit_count()-(int(p)&hm).bit_count()),(h,k-h),strict) for p in patterns])
    omit=ga-float(inside@qs);ext=float((area-inside)@qs);v=float(area@(qs*(1-qs)));ua=float(sum(area))
    expected=dict(ref_symdiff_ref=(omit+ext)/ga,member_symdiff_union=2*v/ua,squared_bias_union=(omit+ext-v)/ua)
    if r['scenario']=='uniform' and k<n:
        flips=[];loss=[]
        for p in patterns:
            c=int(p).bit_count();t=k//2+1 if strict else (k+1)//2;t2=(k+1)//2+1 if strict else (k+2)//2
            f=l=0.
            for j,prob in pmf(n,c,k):
                pu=(c-j)/(n-k);old=j>=t
                f+=prob*((1-pu)*(old!=(j>=t2))+pu*(old!=(j+1>=t2)))
                l+=prob*((1-pu) if old else pu)
            flips.append(f);loss.append(l)
        expected.update(add_one_symdiff_union=float(area@flips)/ua,next_person_loss_union=float(area@loss)/ua)
    for f,val in expected.items():maxerr[f]=max(maxerr[f],abs(val-float(r[f])))
assert len(keys)==len(set(keys))
assert max(maxerr.values())<1e-10

summary_error=0.
for s in summaries:
    panel=s['panel'];pname=panel.removesuffix('_dualref');condition='semi' if pname.startswith('semi_') else 'manual'
    ims=set(panels[pname]['images'])
    if panel.endswith('_dualref'):ims &= {r['image'] for r in rows if r['version']=='manual_revision' and r['condition']==condition}
    members=[r for r in rows if r['condition']==condition and r['image'] in ims and all(r[f]==s[f] for f in ('scenario','policy','method','version','k','strategy'))]
    assert set(r['image'] for r in members)==ims
    assert len(members)==len(ims)==int(s['image_n'])
    assert set(s['images'].split('|'))==ims
    for f in ('ref_symdiff_ref','member_symdiff_union','add_one_symdiff_union','next_person_loss_union'):
        valid=[r for r in members if r[f]!='']
        if not valid or len(valid)<len(members):assert s[f]=='';continue
        bybuilding=defaultdict(list)
        for r in valid:bybuilding[r['building']].append(float(r[f]))
        vals=[float(r[f]) for r in valid] if s['weighting']=='image' else [sum(v)/len(v) for v in bybuilding.values()]
        summary_error=max(summary_error,abs(sum(vals)/len(vals)-float(s[f])))
assert summary_error<1e-10

def select(panel,scenario,method,k,strategy='random'):
    return [r for r in rows if r['image'] in panels[panel]['images'] and r['condition']=='manual' and r['scenario']==scenario and r['method']==method and int(r['k'])==k and r['version']=='original' and r['strategy']==strategy and r['policy']==('none' if scenario=='uniform' else 'original')]
def contrast(panel,method,a,b):
    ra={r['image']:float(r['ref_symdiff_ref']) for r in select(panel,*a[:1],method,*a[1:])}
    rb={r['image']:float(r['ref_symdiff_ref']) for r in select(panel,*b[:1],method,*b[1:])}
    assert ra.keys()==rb.keys();ds=[ra[i]-rb[i] for i in ra]
    return dict(n=len(ds),mean_a=sum(ra.values())/len(ra),mean_b=sum(rb.values())/len(rb),difference=sum(ds)/len(ds),improved=sum(d<0 for d in ds),worsened=sum(d>0 for d in ds))
results={}
for method in ('mv50','mv_strict'):
    results[method]={
      'random20_vs8':contrast('manual_n20',method,('uniform',20),('uniform',8)),
      'higher8_vslower8':contrast('manual_n20',method,('composition',8,'higher_rich'),('composition',8,'lower_rich')),
      'higher8_vsrandom20':contrast('manual_n20',method,('composition',8,'higher_rich'),('uniform',20)),
      'external_higher8_vslower8':contrast('manual_external_n16',method,('composition',8,'higher_rich'),('composition',8,'lower_rich'))}
output=dict(group_n=len(groups),record_n=sum(len(g['records']) for g in groups.values()),coverage_counts=dict(Counter(r['condition']+':'+r['status'] for r in data['coverage'])),assignments_checked=len(assignments),per_image_checked=len(rows),summary_checked=len(summaries),max_numeric_error=dict(maxerr),max_summary_error=summary_error,contrasts=results,external_buildings=sorted({groups[i,'manual']['building'] for i in panels['manual_external_n16']['images']}),calibration_buildings=sorted(train_buildings))
(OUT/'audit_results.json').write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(output))
