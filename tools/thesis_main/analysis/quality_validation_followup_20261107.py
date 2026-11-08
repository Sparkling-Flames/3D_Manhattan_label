"""Fixed-output score sensitivity and measured geometry controls; never refit Q."""
from pathlib import Path
from dataclasses import replace, asdict
import argparse
import gzip
import json
import math

import numpy as np
import pandas as pd

from .scope_quality_scoring_20261016 import scoring_engine
from .audit_image_response_20261101 import onset
from .quality_independent_validation_20261024 import geometry_to_cor, evaluate_geometry

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'research/quality/validation_followup_20261107'
ENGINE = ROOT / 'research/statistics/b8l2_shared_v6_20261016/inputs'
RESPONSE = ROOT / 'research/workers/image_response_v21_20261101/HOHONET_v21_image_response_20261101'
ACCEPT = ROOT / 'research/fusion/manual_order_acceptance_20261104'
IMPACT = ROOT / 'research/fusion/manual_order_impact_20261104'
COMP = ['iou_2d', 'S_bottom_deg', 'dir', 'Hmean', 'Hcenter']


def variants(models):
    b = models.MODELS['B8L2']
    result = {'B8L2': b, 'D10': replace(b, direction_scale_deg=10.)}
    # Fixed one-factor changes; all variants are reported, never selected by outcome.
    for field in ['global_height_scale', 'local_height_scale', 'direction_scale_deg']:
        for factor in [.75, 1.25]:
            result[f'{field}_x{factor}'] = replace(b, **{field: getattr(b, field)*factor})
    for factor in [.75, 1.25]:
        result[f'bottom_scale_x{factor}'] = replace(b, bottom_scale_squared_deg2=b.bottom_scale_squared_deg2*factor**2)
    return result


def scores(frame, models, parameters):
    valid = frame[COMP].notna().all(axis=1) & frame.B8L2.notna()
    out = pd.DataFrame(np.nan, index=frame.index, columns=list(parameters)+['IoU3D100'])
    for name, parameter in parameters.items():
        out.loc[valid, name] = models.score(*[frame.loc[valid, c].to_numpy() for c in COMP], parameter)
    if valid.any():
        assert np.allclose(out.loc[valid, 'B8L2'], frame.loc[valid, 'B8L2'], atol=1e-7)
        assert np.allclose(out.loc[valid, 'D10'], frame.loc[valid, 'D10'], atol=1e-7)
    out['IoU3D100'] = frame['IoU3D100'].where(valid)
    # Exact common metric support, including the independent volume proxy.
    out.loc[~out.notna().all(axis=1), :] = np.nan
    return out


def save(frame, name):
    OUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(frame).to_csv(OUT/name, index=False, encoding='utf-8-sig')


def natural(models, parameters):
    idx = pd.read_csv(RESPONSE/'stage03_response/manual/ANALYSIS_POOL_INDEX.csv')
    idx = idx[idx.domain.eq('ordinary_manual_main')]
    assert len(idx) == 206
    changes, starts, support = [], [], []
    for i, entry in enumerate(idx.itertuples()):
        f = pd.read_csv(RESPONSE/entry.source_file, usecols=['k','replicate_id','team_key','B8L2','D10','IoU3D100']+COMP)
        assert not f.duplicated(['replicate_id','k']).any()
        q = scores(f, models, parameters)
        base = dict(pool_id=entry.pool_id, image=entry.image, building=entry.building,
                    difficulty=entry.difficulty_en, N=entry.N, version='automatic_current_main')
        for name in q:
            x = pd.DataFrame({'k':f.k, 'replicate_id':f.replicate_id, 'q':q[name]})
            stat = x.groupby('k').q.agg(['count','mean','std',lambda v:v.quantile(.1)]).reindex(range(1,entry.N+1))
            stat.columns = ['valid','mean','sd','p10']
            for tolerance in [1.,2.,3.,5.]:
                starts.append({**base,'metric':name,'tolerance':tolerance,
                    'onset_k':onset(stat['mean'].to_numpy(),stat.valid.to_numpy(),entry.N,tolerance,64),
                    'threshold_semantics':'numeric points in this metric; not perceptually equivalent'})
            for lo,hi in [(3,6),(20,30)]:
                if entry.N < hi: continue
                p = x[x.k.isin([lo,hi])].pivot(index='replicate_id',columns='k',values='q').dropna()
                # Same path IDs at both sizes and for all score variants.
                for what, fn in [('mean',lambda v:v.mean()),('p10',lambda v:v.quantile(.1)),('sd',lambda v:v.std(ddof=1))]:
                    changes.append({**base,'metric':name,'interval':f'{lo}->{hi}','statistic':what,
                        'paired_paths':len(p),'start':fn(p[lo]),'end':fn(p[hi]),'delta':fn(p[hi])-fn(p[lo])})
        for k,g in f.groupby('k'):
            support.append({**base,'k':int(k),'attempted_paths':len(g),'common_scored':int(q.loc[g.index].B8L2.notna().sum()),
                            'original_Q_scored':int(g.B8L2.notna().sum())})
        if i%30==0: print('natural',i+1,len(idx),flush=True)
    save(changes,'NATURAL_FIXED_PATH_CHANGES.csv');save(starts,'SMALL_CHANGE_ONSETS.csv');save(support,'NATURAL_SUPPORT.csv')
    c=pd.DataFrame(changes)
    summary=[]
    for dif in ['ALL','Easy','Medium','Hard']:
        part=c if dif=='ALL' else c[c.difficulty.eq(dif)]
        for keys,g in part.groupby(['metric','interval','statistic']):
            summary.append(dict(zip(['metric','interval','statistic'],keys),difficulty=dif,images=g.image.nunique(),
                buildings=g.building.nunique(),mean_delta=g.delta.mean(),positive=int((g.delta>1e-9).sum()),negative=int((g.delta< -1e-9).sum())))
    save(summary,'NATURAL_SUMMARY.csv')
    s=pd.DataFrame(starts);summary=[]
    for keys,g in s.groupby(['metric','difficulty','tolerance']):
        summary.append(dict(zip(['metric','difficulty','tolerance'],keys),registered_images=len(g),
                            found=int(g.onset_k.notna().sum()),median_onset=g.onset_k.median()))
    save(summary,'ONSET_SUMMARY.csv')


def load_lines(path):
    with gzip.open(path,'rt',encoding='utf-8-sig') as f:return [json.loads(s) for s in f if s.strip()]


def half(models, parameters):
    original={r['team_key']:r for r in load_lines(ACCEPT/'inputs/q_only/ENDPOINTS.jsonl.gz')}
    auxiliary={r['team_key']:r for r in load_lines(IMPACT/'endpoints/ENDPOINTS.jsonl.gz')}
    events=pd.read_csv(IMPACT/'half_qonly/HALF_ASSISTED_EVENTS.csv.gz')
    events=events[events.updated_class_legal].copy(); assert len(events)==208
    hier=['n','building','image','pool_id','block_id','background_id']
    images=[]; rows=[]
    for version,endpoints in [('automatic',original),('manual_assisted',{**original,**auxiliary})]:
        ep=pd.DataFrame(endpoints.values()).set_index('team_key');sq=scores(ep,models,parameters)
        for metric in sq:
            values=[sq[metric].reindex(events[f'{arm}_team_key']).to_numpy() for arm in 'ABC']
            a,b,c=values; common=np.isfinite(a)&np.isfinite(b)&np.isfinite(c)
            # All metrics use the same three-endpoint support, including C-B here.
            e=events[hier+['event_id']].copy()
            e['GA']=np.where(common,abs(c-a)-abs(b-a),np.nan)
            e['GS']=np.where(common,(abs(c-a)+abs(c-b))/2-abs(b-a),np.nan)
            e['CB']=np.where(common,c-b,np.nan)
            e['metric']=metric;e['version']=version;rows.extend(e.to_dict('records'))
            for effect in ['GA','GS','CB']:
                g=e.groupby(hier,dropna=False)[effect].mean().reset_index()
                for keys in [hier[:-1],hier[:-2],hier[:3]]:g=g.groupby(keys,dropna=False)[effect].mean().reset_index()
                g=g.rename(columns={effect:'effect'});g['estimand']=effect;g['metric']=metric;g['version']=version
                images.extend(g.to_dict('records'))
    save(rows,'HALF_COMMON_EVENTS.csv.gz');save(images,'HALF_IMAGE_EFFECTS.csv')
    s=pd.DataFrame(images);r=[]
    for keys,g in s.groupby(['version','n','metric','estimand']):
        ok=g.dropna(subset=['effect'])
        r.append(dict(zip(['version','n','metric','estimand'],keys),images=len(ok),buildings=ok.building.nunique(),
                      mean=ok.effect.mean(),positive=int((ok.effect>1e-9).sum()),negative=int((ok.effect< -1e-9).sum())))
    save(r,'HALF_SUMMARY.csv')


def make_geometry(floor, heights):
    return {'bottom3d':[[float(x),-1.,float(z)] for x,z in floor],
            'top3d':[[float(x),float(h),float(z)] for (x,z),h in zip(floor,heights)]}


def controls(engine, models, parameters):
    rows=[];geometries=[]
    # Camera height is one; same physical perturbation families at three room sizes.
    for scale in [1.,2.,4.]:
        floor=np.array([[-2,-2],[2,-2],[2,2],[.5,2],[.5,1],[-2,1]],float)*scale
        ref=make_geometry(floor,np.ones(len(floor)))
        refpoints=geometry_to_cor(ref)+.5; rg=engine.geometry(refpoints.tolist())
        for family in ['translation','global_height','local_height','wall_shift','corner_omission','spurious_corner','rotation','collinear_split']:
            for severity in [0.,.05,.15,.30]:
                p=floor.copy();h=np.ones(len(p))
                if family=='translation':p[:,0]+=severity
                elif family=='global_height':h+=severity
                elif family=='local_height':h[0]+=severity;h[1]-=severity
                elif family=='wall_shift':p[[1,2],0]+=severity
                elif family=='rotation':
                    a=severity; p=p@np.array([[math.cos(a),-math.sin(a)],[math.sin(a),math.cos(a)]])
                elif family=='corner_omission':p[4]=(1-severity/.30)*p[4]+(severity/.30)*(p[3]+p[5])/2
                elif family=='spurious_corner':
                    p=np.insert(p,1,(p[0]+p[1])/2+[0,-severity],axis=0);h=np.ones(len(p))
                elif family=='collinear_split':
                    p=np.insert(p,1,(p[0]+p[1])/2,axis=0);h=np.ones(len(p))
                geom=make_geometry(p,h);points=geometry_to_cor(geom)+.5;result=engine.measure(engine.geometry(points.tolist()),rg)
                assert result['status']=='complete',(family,scale,severity,result)
                measured=result['metrics']
                f=pd.DataFrame([measured]);f['B8L2']=models.score(*[f[c].to_numpy() for c in COMP],parameters['B8L2']);f['D10']=models.score(*[f[c].to_numpy() for c in COMP],parameters['D10'])
                legacy=evaluate_geometry(geom,ref);f['IoU3D100']=100*legacy['legacy_iou3d_mean_height'] if legacy.get('legacy_iou3d_mean_height') is not None else np.nan
                q=scores(f,models,parameters).iloc[0].to_dict()
                key=f'{family}_size{scale}_level{severity}'
                rows.append(dict(case_id=key,family=family,room_scale=scale,severity=severity,**{c:measured[c] for c in COMP},**q,**legacy))
                geometries.append(dict(case_id=key,reference=ref,annotation=geom,points=points.tolist(),reference_points=refpoints.tolist()))
    save(rows,'CONTROL_RESPONSE_MATRIX.csv')
    with gzip.open(OUT/'CONTROL_GEOMETRIES.json.gz','wt',encoding='utf-8') as f:json.dump(geometries,f)
    r=pd.DataFrame(rows)
    baseline=r[r.severity.eq(0)]
    assert np.allclose(baseline.B8L2,100,atol=1e-6)
    # Equal vertex-mean heights need not imply zero sampled/global residual.
    local=r[r.family.eq('local_height')]
    assert np.allclose(local.IoU3D100,100,atol=1e-4)
    assert local[local.severity.gt(0)].Hcenter.gt(0).all()
    summary=[]
    for (family,scale),g in r.groupby(['family','room_scale']):
        g=g.sort_values('severity')
        for metric in ['B8L2','D10','IoU3D100',*COMP,'layout_depth_rmse_camera_h']:
            v=g[metric].to_numpy();summary.append(dict(family=family,room_scale=scale,metric=metric,
                start=v[0],end=v[-1],delta=v[-1]-v[0],nonincreasing=bool(np.all(np.diff(v)<=1e-7)),nondecreasing=bool(np.all(np.diff(v)>=-1e-7))))
    save(summary,'CONTROL_RESPONSE_SUMMARY.csv')


def main():
    p=argparse.ArgumentParser();p.add_argument('--part',choices=['all','natural','half','controls'],default='all');args=p.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    with scoring_engine(ENGINE/'measurement_engine.zip',ENGINE/'working_models.py') as (engine,models):
        params=variants(models)
        (OUT/'SENSITIVITY_DESIGN.json').write_text(json.dumps({'parameters':{k:asdict(v) for k,v in params.items()},
            'fixed_before_results':True,'selection':'all 206 ordinary Manual main pools; frozen 208 half/background events',
            'support':'same metric and paired-path support; half C-B here also requires ABC common',
            'onset':'at least 64 common scored paths at each k, tail >= max(5,ceil(.15*N)); tolerances 1/2/3/5',
            'formal_score_changed':False},ensure_ascii=False,indent=2),encoding='utf-8')
        if args.part in ['all','half']:half(models,params)
        if args.part in ['all','controls']:controls(engine,models,params)
        if args.part in ['all','natural']:natural(models,params)
    print('completed',args.part,flush=True)


if __name__=='__main__':main()
