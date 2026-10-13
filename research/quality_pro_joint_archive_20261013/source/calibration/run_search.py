#!/usr/bin/env python3
"""Broad joint formula search with explicit evidence layers, then local refinement.

All labels are development evidence. No numeric human target scores, no exact ties,
no unreviewed-screen negatives, and no reference maximization enter this search.
"""
from __future__ import annotations
import argparse, copy, csv, gzip, hashlib, io, json, math, time
from pathlib import Path
import numpy as np
from scipy.stats import qmc
from score import BASELINE,evaluate_arrays,direction_loss,normalized_metrics

HERE=Path(__file__).resolve().parent
FAMILIES=['hill','power','accelerated','hill_tail','moment4','supported_tail','joint_hinge']
COMBINATIONS=['additive','product_height','product_all','max_floor']
BOUNDS={'iou_power':[.5,2.], 'boundary_scale':[2.,20.],
        'direction_scale':[2.,20.], 'direction_cap':[.5,16.], 'tail_scale':[6.,48.],
        'global_scale':[.15,3.], 'local_scale':[.05,.8]}
CATEGORICAL={'boundary_power':[1.,2.,3.], 'direction_power':[1.5,2.,3.,4.,6.],
             'global_power':[1.5,2.,3.], 'local_power':[1.5,2.,3.], 'tail_threshold':[2.,5.,10.,15.]}

def dump(p,x):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def jload(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def gzjson(p,x):
    with gzip.GzipFile(filename=str(p),mode='wb',mtime=0) as f:f.write((json.dumps(x,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n').encode())
def csv_write(p,rows):
    keys=list(dict.fromkeys(k for r in rows for k in r))
    if str(p).endswith('.gz'):
        f=io.TextIOWrapper(gzip.GzipFile(filename=str(p),mode='wb',mtime=0),encoding='utf-8',newline='')
    else:f=open(p,'w',encoding='utf-8',newline='')
    with f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)
def choose(u,values):return values[min(int(u*len(values)),len(values)-1)]
def logrange(u,lo,hi):return float(math.exp(math.log(lo)+(math.log(hi)-math.log(lo))*u))

def configs_coarse(power=14):
    points=qmc.Sobol(d=17,scramble=True,seed=20261013).random_base2(power)
    out=[]
    for n,u in enumerate(points):
        c={'name':f'C{n:05d}','family':choose(u[0],FAMILIES),'combine':choose(u[1],COMBINATIONS)}
        c['iou_power']=float(.5+1.5*u[2]);c['boundary_scale']=logrange(u[3],2,20)
        c['boundary_power']=choose(u[4],CATEGORICAL['boundary_power'])
        c['direction_scale']=logrange(u[5],2,20);c['direction_power']=choose(u[6],CATEGORICAL['direction_power'])
        c['direction_cap']=logrange(u[7],.5,16);c['tail_scale']=logrange(u[8],6,48)
        c['tail_threshold']=choose(u[9],CATEGORICAL['tail_threshold'])
        c['hinge_weight']=choose(u[15],[.5,2.,8.])
        if c['family']=='joint_hinge':c['tail_threshold']=choose(u[9],[5.,10.,15.])
        c['global_scale']=logrange(u[10],.15,3);c['local_scale']=logrange(u[11],.05,.8)
        c['global_power']=choose(u[12],CATEGORICAL['global_power']);c['local_power']=choose(u[13],CATEGORICAL['local_power'])
        c['boundary_disabled']=bool(u[14]<.05)
        out.append(c)
    return out

def arrays(rows):
    return {k:np.array([normalized_metrics(r['metrics'])[k] for r in rows]) for k in ['I','Sb','D','Hm','Hc']}
def descriptors(rows):
    return dict(moment4=np.array([r['descriptor']['moment4'] for r in rows]),
                joint_hinge={f't{t:g}_g{g:g}':np.array([r['descriptor']['joint_hinge'][f't{t:g}_g{g:g}'] for r in rows]) for t in [5.,10.,15.] for g in [.5,2.,8.]},
                excess2={k:np.array([r['descriptor']['excess2'][k] for r in rows]) for k in ['2','5','10','15','20']})

def build_evidence(data, excluded_building=None, excluded_image=None):
    by={r['id']:i for i,r in enumerate(data['rows'])}; meta={r['id']:r for r in data['rows']}
    def allowed(rid):
        return meta[rid]['building_id']!=excluded_building and meta[rid]['image_id']!=excluded_image
    grades=[g for g in data['grades'] if allowed(g['id'])]
    sets={}
    for name,gg in [('old24',grades),('clean22',[g for g in grades if not g['scope_confounded_latest']])]:
        pairs=[]; groups=[]
        for ga,gb in [(0,1),(0,2),(1,2)]:
            aa=[g for g in gg if g['grade']==ga];bb=[g for g in gg if g['grade']==gb]
            group=[]
            for x in aa:
                for y in bb: group.append((by[x['id']],by[y['id']]))
            groups.append(group);pairs+=group
        sets[name]=dict(pairs=pairs,groups=groups,records=len(gg))
    overall=[];floor=[];conditional=[];close=[]
    for c in data['constraints']:
        ids=c.get('record_ids',[])
        if not ids or not all(r in by and allowed(r) for r in ids):continue
        if c['dimension']=='processed_overall_quality':
            if c['evidence_type'] in ('explicit_direction','explicit_direction_and_both_good'):
                overall.append((c['panel'],by[c['preferred_record_id']],by[c['other_record_id']]))
            elif c['evidence_type'] in ('uncertain_and_qualitatively_close','qualitatively_close'):
                close.append((c['panel'],by[ids[0]],by[ids[1]]))
        if c['dimension']=='floor_result' and c['evidence_type']=='explicit_component_direction':
            other=next(r for r in ids if r!=c['preferred_record_id']);floor.append((c['panel'],by[c['preferred_record_id']],by[other]))
        if c['dimension']=='top_height_penalty':
            conditional.append((c['panel'],by[c['preferred_record_id']],by[c['other_record_id']]))
    return dict(sets=sets,overall=overall,floor=floor,conditional=conditional,close=close)

def evidence_eval(q, fq, hloss, ev):
    out={}
    for name,s in ev['sets'].items():
        p=s['pairs']; inv=[float(q[i]<q[j]-1e-10)+.5*float(abs(q[i]-q[j])<=1e-10) for i,j in p]
        out[name+'_pairs']=len(p);out[name+'_inversions']=float(sum(inv))
        groupmeans=[]
        for group in s['groups']:
            if group:groupmeans.append(float(np.mean([float(q[i]<q[j]-1e-10)+.5*float(abs(q[i]-q[j])<=1e-10) for i,j in group])))
        out[name+'_macro_error']=float(np.mean(groupmeans)) if groupmeans else 0.
    out['overall_violations']=int(sum(q[i]<=q[j] for _,i,j in ev['overall']))
    out['floor_direction_violations']=int(sum(fq[i]<=fq[j] for _,i,j in ev['floor']))
    out['conditional_height_violations']=int(sum(hloss[i]<=hloss[j] for _,i,j in ev['conditional']))
    for group,i,j in ev['overall']:out[group+'_score_margin']=float(q[i]-q[j])
    for group,i,j in ev['floor']:out[group+'_floor_margin']=float(fq[i]-fq[j])
    for group,i,j in ev['conditional']:out[group+'_height_loss_margin']=float(hloss[i]-hloss[j])
    # Dimensionless display diagnostic; no numeric equivalence interval is asserted.
    gaps=[abs(math.log(max(q[i],1e-300)/max(q[j],1e-300))) for _,i,j in ev['close']]
    out['weak_close_mean_log_ratio']=float(np.mean(gaps)) if gaps else 0.
    for group,i,j in ev['close']:out[group+'_signed_score_gap']=float(q[i]-q[j])
    out['hard_sign_violations']=int(out['overall_violations']+out['floor_direction_violations']+out['conditional_height_violations'])
    return out

def scalar_response(c):
    ds=np.array([1.,2.,5.,10.,15.,20.,90/math.sqrt(12)])
    # Neutral uniform edge residuals are used for supported-family curve comparisons;
    # actual per-edge tests are exported separately, never confused with this curve.
    desc=dict(moment4=ds**4,excess2={str(k):np.maximum(ds-k,0)**2 for k in [2,5,10,15,20]})
    desc['joint_hinge']={f't{t:g}_g{g:g}':ds**2+g*np.maximum(ds-t,0)**2 for t in [5.,10.,15.] for g in [.5,2.,8.]}
    loss=direction_loss(ds,c,desc)
    out={f'D_{d:g}_loss':float(x) for d,x in zip(ds,loss)}
    out.update({f'D_{d:g}_isolated_Q':float(100/(1+x)) for d,x in zip(ds,loss)})
    out['D15_to_D5_loss_ratio']=float(loss[4]/max(loss[2],1e-30))
    for h in [.05,.1,.2,.4,.8,1.]:
        lm=(h/c['global_scale'])**c['global_power'];lc=(h/c['local_scale'])**c['local_power']
        out[f'Hm_{h:g}_loss']=lm;out[f'Hc_{h:g}_loss']=lc
    # These are engineering response requirements, not human class boundaries.
    # They instantiate "small skew not crushed, large skew grows substantially".
    out['response_design_violations']=int(loss[1]>.2)+int(loss[4]<2)+int(out['D15_to_D5_loss_ratio']<4)+int(out['Hm_0.2_loss']>.35)+int(out['Hm_1_loss']<.5)+int(out['Hc_0.2_loss']<out['Hm_0.2_loss'])
    return out

def selection_key(row):
    # No cardinal human-score fit. The final readable recommendation is assessed
    # alongside this numerical frontier and may select simpler rounded constants.
    return (row['hard_sign_violations'],row['response_design_violations'],
            row['clean22_macro_error'],row['weak_close_mean_log_ratio'])

def evaluate(c, m, d, ev):
    v=evaluate_arrays(m,c,d)
    z={'candidate':c['name'],'family':c['family'],'combine':c['combine'],**evidence_eval(v['score'],v['floor_score'],v['height_loss'],ev),**scalar_response(c)}
    z.update({k:c[k] for k in BOUNDS if k in c});z.update({k:c[k] for k in CATEGORICAL if k in c})
    z['boundary_disabled']=c.get('boundary_disabled',False)
    z['hinge_weight']=c.get('hinge_weight')
    return z

def fine_configs(best, count=4096):
    rng=np.random.default_rng(2026101301);out=[]
    keys=['iou_power','boundary_scale','direction_scale','direction_cap','tail_scale','global_scale','local_scale']
    for i in range(count):
        c=copy.deepcopy(best[i%len(best)]);c['name']=f'F{i:05d}'
        for k in keys:
            if k not in c:continue
            lo,hi=BOUNDS[k];c[k]=float(np.clip(c[k]*math.exp(rng.normal(0,.16)),lo,hi))
        # Refine continuous parameters; include rounded/exact power-2 neighbours.
        if i%4==0:c['global_power']=c['local_power']=2.
        if i%5==0:c['boundary_power']=2.
        out.append(c)
    return out

def readable_configs():
    out=[dict(BASELINE)]
    for ds in [5.,6.,7.,8.,9.,10.]:
      for gs in [.5,.6,.8,1.,1.25,1.5]:
       for ls in [.15,.2,.25,.3,.4]:
        for sb in [4.,math.sqrt(32),8.,12.]:
         c={**BASELINE,'name':f'R_power_d{ds:g}_g{gs:g}_l{ls:g}_s{sb:.4g}',
            'family':'power','direction_scale':ds,'global_scale':gs,'local_scale':ls,'boundary_scale':sb}
         out.append(c)
    for t in [8.,10.,12.,15.,18.,24.]:
      for gs in [.8,1.,1.25]:
       for ls in [.2,.25,.3]:
        out.append({**BASELINE,'name':f'R_hilltail_t{t:g}_g{gs:g}_l{ls:g}', 'family':'hill_tail','tail_scale':t,'global_scale':gs,'local_scale':ls})
        for ds in [6.,7.,8.,10.]:
          out.append({**BASELINE,'name':f'R_accel_d{ds:g}_t{t:g}_g{gs:g}_l{ls:g}','family':'accelerated','direction_scale':ds,'tail_scale':t,'global_scale':gs,'local_scale':ls})
    for t in [5.,10.,15.]:
     for w in [.5,2.,8.]:
      for ds in [6.,8.,10.]:
       for gs in [.8,1.,1.25]:
        for ls in [.2,.25,.3]:
          out.append({**BASELINE,'name':f'R_joint_t{t:g}_w{w:g}_d{ds:g}_g{gs:g}_l{ls:g}','family':'joint_hinge','tail_threshold':t,'hinge_weight':w,'direction_scale':ds,'global_scale':gs,'local_scale':ls})
    return out

def main():
    p=argparse.ArgumentParser();p.add_argument('--inputs',type=Path,default=HERE/'inputs/search_inputs.json')
    p.add_argument('--out',type=Path,default=HERE/'results');p.add_argument('--coarse-power',type=int,default=14)
    p.add_argument('--fine-count',type=int,default=4096);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    started=time.monotonic();data=jload(a.inputs);m=arrays(data['rows']);d=descriptors(data['rows']);ev=build_evidence(data)
    design=dict(schema='joint_search_design_v1',seed=20261013,coarse_count=2**a.coarse_power,
                bounds=BOUNDS,categorical=CATEGORICAL,families=FAMILIES,combinations=COMBINATIONS,
                evidence_policy='Explicit overall and conditional directions separate; no numeric target score or exact tie; all human cases are development.',
                uncertainty_policy='All old30 judgements remain hesitant; old24 grades are weak ordinal development evidence, not 164 independent labels.',
                scope_sensitivity='All24 preserved; T21/T22 omitted only from clean22 sensitivity because their small ranges were never accepted.',
                response_requirements={'D2_loss_max':.2,'D15_loss_min':2.,'D15_to_D5_loss_ratio_min':4.,'Hm_point2_loss_max':.35,'Hm1_loss_min':.5,'same_fraction_local_ge_global':True},
                response_requirements_are_model_design_not_human_grades=True,
                response_requirements_sensitivity='Report candidates without this screen and several expanded bounds; no claim that these exact endpoints are human-calibrated.',
                soft_closeness='Abs log score ratio is descriptive/Pareto tie-break only; no numerical equality tolerance is imposed.',
                input_sha256=sha(a.inputs),selection_key='hard signs; response requirements; clean22 macro error; weak log-closeness; full old24 is reported, not optimized because of latest scope confounding')
    dump(a.out/'SEARCH_DESIGN.json',design)
    configs=configs_coarse(a.coarse_power);results=[]
    for c in configs:results.append(evaluate(c,m,d,ev))
    coarse=list(results);bycfg={c['name']:c for c in configs}
    print(json.dumps({'stage':'coarse','count':len(coarse),'hard_feasible':sum(r['hard_sign_violations']==0 for r in coarse),'joint_feasible':sum(r['hard_sign_violations']==0 and r['response_design_violations']==0 for r in coarse),'seconds':time.monotonic()-started}),flush=True)
    # Seed each family/combination, including inferior families so refinement does
    # not silently discard an entire formula class after one coarse draw.
    seeds=[]
    for family in FAMILIES:
      for combine in COMBINATIONS:
        pool=[r for r in results if r['family']==family and r['combine']==combine]
        if pool:seeds.extend(bycfg[z['candidate']] for z in sorted(pool,key=selection_key)[:2])
    fine=fine_configs(seeds,a.fine_count)
    configs.extend(fine)
    results.extend(evaluate(c,m,d,ev) for c in fine)
    readable=readable_configs();configs.extend(readable);results.extend(evaluate(c,m,d,ev) for c in readable)
    # Boundary expansion: retain old proposals, then double ranges in any winner
    # direction. This diagnoses boundary pressure, never quietly clips an optimum.
    bycfg={c['name']:c for c in configs};pre=sorted(results,key=selection_key)[:60]
    extension=[]
    for z in pre:
      c=bycfg[z['candidate']]
      for k,(lo,hi) in BOUNDS.items():
       if k not in c:continue
       if k=='direction_cap' and c['family'] not in ('hill','hill_tail'):continue
       if k=='tail_scale' and c['family'] not in ('accelerated','hill_tail','moment4','supported_tail'):continue
       position=math.log(c[k]/lo)/math.log(hi/lo)
       if position<.1 or position>.9:
        n=copy.deepcopy(c);n['name']=f'X{len(extension):05d}';n[k]=c[k]*(.5 if position<.1 else 2.)
        extension.append(n)
    configs.extend(extension);results.extend(evaluate(c,m,d,ev) for c in extension)
    bycfg={c['name']:c for c in configs};ranked=sorted(results,key=selection_key)
    summaries=[]
    for family in FAMILIES:
      for combine in COMBINATIONS:
        pool=[r for r in results if r['family']==family and r['combine']==combine]
        if not pool:continue
        win=min(pool,key=selection_key)
        summaries.append(dict(family=family,combine=combine,count=len(pool),hard_feasible=sum(r['hard_sign_violations']==0 for r in pool),response_and_human_feasible=sum(r['hard_sign_violations']==0 and r['response_design_violations']==0 for r in pool),best=win,config=bycfg[win['candidate']]))
    feasible=[r for r in results if not r['hard_sign_violations'] and not r['response_design_violations']]
    near=[r for r in feasible if r['clean22_inversions']<=2 and r['old24_inversions']<=8]
    region={}
    for key in BOUNDS:
        vals=[r[key] for r in near if key in r]
        if vals:region[key]={'min':min(vals),'p10':float(np.quantile(vals,.1)),'median':float(np.median(vals)),'p90':float(np.quantile(vals,.9)),'max':max(vals)}
    gzjson(a.out/'all_search_configs.json.gz',dict(configs=configs))
    csv_write(a.out/'all_search_results.csv.gz',results)
    dump(a.out/'family_summary.json',summaries)
    dump(a.out/'top_candidates.json',dict(candidates=[dict(config=bycfg[r['candidate']],results=r) for r in ranked[:100]]))
    dump(a.out/'readable_candidates.json',dict(candidates=[dict(config=c,results=next(r for r in results if r['candidate']==c['name'])) for c in readable]))
    dump(a.out/'search_summary.json',dict(coarse=len(coarse),fine=len(fine),readable=len(readable),boundary_extensions=len(extension),total=len(results),
         hard_feasible=sum(r['hard_sign_violations']==0 for r in results),joint_feasible=len(feasible),
         near_region_count=len(near),near_region_definition='hard signs and response screen; clean22 inversions<=2 and old24 inversions<=8; these are sensitivity cutoffs, not independent accuracy.',
         effective_parameter_region=region,baseline=next(r for r in results if r['candidate']=='baseline_quad08'),
         numeric_frontier_best=ranked[0],boundary_pressure=[{k:z.get(k) for k in ['candidate','family','combine','direction_scale','direction_cap','global_scale','local_scale','boundary_scale','iou_power','clean22_inversions','old24_inversions']} for z in ranked[:10]],
         timing_seconds=time.monotonic()-started,input_sha256=sha(a.inputs),human_independent_validation=False,
         recommendation_not_automatically_equal_to_spurious_decimal_optimum=True))
    print(json.dumps({'stage':'done','total':len(results),'feasible':len(feasible),'near':len(near),'best':ranked[0],'seconds':time.monotonic()-started}),flush=True)

if __name__=='__main__':main()
