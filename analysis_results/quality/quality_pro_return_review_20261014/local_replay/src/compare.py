"""Transparent, mechanism-led comparisons; exposed human evidence is developmental.
No automatic score target, optimum claim, holdout resplit or cohort expansion.
"""
from __future__ import annotations
import argparse,csv,math
from collections import defaultdict
import numpy as np
from scipy.stats import spearmanr
from core import *

def csv_dump(path,rows):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader()
        for r in rows:w.writerow({k:json.dumps(clean(v),ensure_ascii=False) if isinstance(v,(list,dict)) else v for k,v in r.items()})

def configurations():
    b=BASE
    cs={'current_hill08':dict(b), 'historical_tail12_g1':dict(b,family='hill_tail',tail_scale=12.,global_scale=1.),
        'historical_simple8_g1':dict(b,family='power',direction_scale=8.,global_scale=1.),
        'hill_g1':dict(b,global_scale=1.),
        'loss_sum':dict(b,combine='loss_sum'),
        'max_floor':dict(b,combine='max_floor'),
        'product_height':dict(b,combine='product_height'),
        'product_all':dict(b,combine='product_all'),
        'weaker_D_cap1':dict(b,direction_cap=1.),
        'wider_boundary8':dict(b,boundary_scale=8.),
        'nearest_normal_hill':dict(b,direction_metric='N_nearest_deg'),
        'ray_normal_hill':dict(b,direction_metric='N_ray_deg')}
    # Exact single-mechanism ablations of the proposed combination.
    for field in ['direction','boundary','global','local','overlap']:
        cs['loss_sum_no_'+field]=dict(b,combine='loss_sum',**{field+'_disabled':True})
    # These neutral single-factor scales are not learned anew; explore sensitivity
    # sufficiently wide to expose failures, without turning weak evidence into targets.
    for parameter,values in [('direction_cap',[.75,1.,2.,3.]),('direction_scale',[4.,8.,12.]),
                             ('boundary_scale',[4.,8.,12.]),('global_scale',[.5,.65,1.,1.2]),('local_scale',[.15,.20,.30,.4])]:
        for v in values:cs[f'loss_sum_{parameter}_{v:g}']=dict(b,combine='loss_sum',**{parameter:v})
    return {n:dict(c,name=n) for n,c in cs.items()}

def quant(x):
    a=np.array(x,dtype=float)
    return dict(n=len(a),mean=float(np.mean(a)),min=float(a.min()),p10=float(np.quantile(a,.1)),median=float(np.median(a)),p90=float(np.quantile(a,.9)),max=float(a.max())) if len(a) else dict(n=0)

def score_set(measurements,cs):
    return {r['record_id']:{name:components(r['metrics'],c,r.get('diagnostics')) for name,c in cs.items()} for r in measurements}

def evidence_summary(out,rows,evidence,name):
    by={r['record_id']:r for r in rows}
    def q(rid):return out[rid][name]['score'] if rid in out else None
    groups=[]
    for g in evidence['question_groups']:
        ids=[b['record_id'] for b in g['bindings']];scores=[q(x) for x in ids]
        groups.append(dict(group=g['group'],ids=ids,scores=scores,signed_A_minus_B=scores[0]-scores[1] if len(scores)==2 and all(x is not None for x in scores) else None,
            use=g['use'],source_layer=[by.get(x,{}).get('source_layer','not_in_this_snapshot') for x in ids]))
    grades=evidence['existing_weak_grades'];good=[x for x in grades if q(x['id']) is not None]
    weak=[(a,b) for a in good for b in good if a['grade']<b['grade']]
    inversions=[dict(better=a['id'],worse=b['id'],difference=q(a['id'])-q(b['id'])) for a,b in weak if q(a['id'])<q(b['id'])-1e-9]
    severe=[r['record_id'] for r in rows if r['source_layer']=='severe' and q(r['record_id']) is not None]
    # Severe labels constrain broad separation, not an invented threshold or
    # within-severe ordering. Show all cross-record comparisons and image balancing.
    lighter=[g['id'] for g in good if g['grade']==1]
    sinv=[dict(severe=s,light=l,delta=q(s)-q(l)) for s in severe for l in lighter if q(s)>q(l)]
    loto=[]
    for b in sorted({g['building_id'] for g in good}):
        pairs=[(a,z) for a,z in weak if a['building_id']!=b and z['building_id']!=b]
        loto.append(dict(excluded_building=b,pairs=len(pairs),inversions=sum(q(a['id'])<q(z['id'])-1e-9 for a,z in pairs)))
    return dict(question_groups=groups,P01_margin=q('R02015')-q('R00637') if None not in [q('R02015'),q('R00637')] else None,
        weak_grade_pairs=len(weak),weak_grade_inversions=inversions,severe_vs_light_comparisons=len(severe)*len(lighter),
        severe_vs_light_inversions=sinv,leave_one_evidence_building_out=loto)

def main(phase):
    if phase=='ordinary':
        cs=configurations();measurements=read(ROOT/'results/ordinary_reconstruction.json')['records']
    else:
        freeze=read(ROOT/'configs/ordinary_frozen.json');b=freeze['config']
        cs={'ordinary_frozen':b,'old_current':BASE}
        for par,values in [('direction_cap',[1.25,1.75]),('boundary_scale',[5.,6.5]),('global_scale',[.75,.85]),('local_scale',[.225,.275])]:
            for v in values:cs[f'fine_{par}_{v:g}']=dict(b,**{par:v})
        measurements=read(ROOT/'results/doorway_reconstruction.json')['records']
    co=read(INPUT/'data/cohorts.json');allrows={r['record_id']:r for k in ['ordinary','severe','historical_only','doorway'] for r in co[k]}
    evidence=read(INPUT/'preparation/EVIDENCE.json');out=score_set(measurements,cs)
    summary={};flat=[];groups=[]
    reference_name='current_hill08' if phase=='ordinary' else 'old_current'
    for r in measurements:
        src=allrows[r['record_id']]
        for name,v in out[r['record_id']].items():
            flat.append(dict(record_id=r['record_id'],layer=r['source_layer'],image_id=src['image_id'],building_id=src.get('building_id',src['image_id'].split('_')[0]),
                worker_id=src['worker_id'],image_code=src.get('image_code',src.get('scene_layer',{}).get('image_code')),
                reference_object_id=r['reference_object_id'],candidate=name,**{k:v.get(k) for k in ['status','score','floor_score','boundary_loss','direction_loss','global_height_loss','local_height_loss','height_loss','height_score_drop']},
                current_score=out[r['record_id']][reference_name]['score'],
                delta_vs_current=v['score']-out[r['record_id']][reference_name]['score'] if v['score'] is not None else None,
                iou3d_pct=100*r['metrics']['iou_3d_corner_mean'],**{k:r['metrics'][k] for k in METRICS}))
    for name,c in cs.items():
        layerstats={}
        for layer in ['ordinary','ordinary_explicit','ordinary_conditional','severe','historical_only','doorway']:
            rr=[r for r in measurements if r['source_layer']==layer or layer.startswith('ordinary_') and r['source_layer']=='ordinary' and bool(allrows[r['record_id']]['scene_layer']['ordinary_status_is_explicit'])==(layer=='ordinary_explicit')]
            validr=[r for r in rr if out[r['record_id']][name]['score'] is not None]
            ds=[out[r['record_id']][name]['score']-out[r['record_id']][reference_name]['score'] for r in validr]
            layerstats[layer]=dict(requested=len(rr),available=len(validr),score=quant([out[r['record_id']][name]['score'] for r in validr]),delta=quant(ds),
                increase_ge5=sum(x>=5 for x in ds),decrease_ge5=sum(x<=-5 for x in ds))
        summary[name]=dict(layers=layerstats)
        if phase=='ordinary':summary[name]['evidence']=evidence_summary(out,measurements,evidence,name)
        for level in ('image_id','building_id'):
            bins=defaultdict(list)
            for r in measurements:
                if r['source_layer'] not in (('ordinary','severe') if phase=='ordinary' else ('doorway',)):continue
                src=allrows[r['record_id']];key=(r['source_layer'],src.get(level,src['image_id'].split('_')[0]))
                if out[r['record_id']][name]['score'] is not None:bins[key].append(r)
            for (layer,key),rr in bins.items():
                vals=[out[r['record_id']][name]['score'] for r in rr];old=[out[r['record_id']][reference_name]['score'] for r in rr]
                groups.append(dict(candidate=name,layer=layer,level=level,group=key,n=len(rr),mean=float(np.mean(vals)),median=float(np.median(vals)),min=min(vals),max=max(vals),mean_delta=float(np.mean(np.asarray(vals)-old)),iou3d_mean=100*np.mean([r['metrics']['iou_3d_corner_mean'] for r in rr])))
    dump(ROOT/f'results/{phase}_candidate_summary.json',summary)
    dump(ROOT/f'results/{phase}_candidate_components.json',out)
    dump(ROOT/f'configs/{phase}_candidates.json',cs)
    csv_dump(ROOT/f'results/{phase}_scores_long.csv',flat);csv_dump(ROOT/f'results/{phase}_by_image_building.csv',groups)
    if phase=='ordinary':
        cc=read(ROOT/'results/control_reconstruction.json')['records'];controlout=score_set(cc,cs);dump(ROOT/'results/control_candidate_components.json',controlout)
        controls=[]
        for r in cc:
            for name,v in controlout[r['record_id']].items():controls.append(dict(case_id=r['record_id'],candidate=name,**{k:v.get(k) for k in ['score','floor_score','boundary_loss','direction_loss','height_loss','height_score_drop']},**{k:r['metrics'][k] for k in METRICS},iou3d_pct=100*r['metrics']['iou_3d_corner_mean']))
        csv_dump(ROOT/'results/control_scores_long.csv',controls)
        for name in ['current_hill08','historical_tail12_g1','historical_simple8_g1','loss_sum','max_floor','nearest_normal_hill','ray_normal_hill','loss_sum_no_direction']:
            s=summary[name];print(name, 'ordinary',s['layers']['ordinary']['available'],s['layers']['ordinary']['delta'], 'P01',s['evidence']['P01_margin'],'weak_inv',len(s['evidence']['weak_grade_inversions']), 'sev_inv',len(s['evidence']['severe_vs_light_inversions']))
    print('wrote',phase,len(cs),'candidates',len(measurements),'rows')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--phase',choices=['ordinary','doorway'],required=True);main(p.parse_args().phase)
