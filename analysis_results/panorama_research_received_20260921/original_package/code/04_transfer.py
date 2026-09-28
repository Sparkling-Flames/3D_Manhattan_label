"""Direct audited room relations, common-worker controls, and held-building image-feature predictions."""
import common as c
import itertools,collections,json
import numpy as np,pandas as pd
from scipy.stats import spearmanr
from scipy.spatial.distance import jensenshannon
from sklearn.linear_model import Ridge
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler

def main():
    args=c.main_parser().parse_args();c.configure(args.source_root)
    from tools.thesis_main.analysis.audit_collection_plan_20260921 import blocks
    _,_,views,registry,_=c.load()
    candidates=[x for x in registry['candidates'] if x['physical_same_supported']]
    family=blocks(candidates)
    meta={x['image_id']:x for x in c.read('analysis_results/spatial_dimensions_review_20260913_v2/空间描述与历轮人工记录.json')['images']}
    scene={i:r.get('current_coarse_review',{}).get('value') or '主空间待定' for i,r in meta.items()}
    scene_known={'卧室','卫浴','厨房与用餐','工作与学习','起居与休闲','通行与连接','储藏与家务辅助','特殊用途'}
    adj=collections.defaultdict(set);comp=collections.defaultdict(set);exposed=collections.defaultdict(set);links=collections.defaultdict(list)
    inv=[]
    for ca in candidates:
        ids=[i for i in ca['image_ids'] if i in views]
        inv.append(dict(candidate=ca['candidate_id'],building=ca['building'],comparable=ca['comparable_for_prediction'],
            outcome_exposure=ca.get('outcome_exposure'),review_state=ca.get('review_state'),physical_supported=True,
            all_codes=';'.join(f'{ca["building"]}-{n:02d}' for n in ca['numbers']),
            observed_codes=';'.join(views[i]['code'] for i in ids),counts=';'.join(str(views[i]['N']) for i in ids),
            hold_reasons=ca.get('selection_hold_reasons'),source_group_codes=ca.get('source_group_codes')))
        for a,b in itertools.combinations(ids,2):
            adj[a].add(b);adj[b].add(a);links[tuple(sorted([a,b]))].append(ca['candidate_id'])
            if ca['comparable_for_prediction']:comp[a].add(b);comp[b].add(a)
            if ca.get('outcome_exposure'):exposed[a].add(b);exposed[b].add(a)
    c.save('room_inventory.csv',pd.DataFrame(inv))
    im=pd.read_csv(c.ROOT/'results/image_metrics.csv').set_index('image_id')
    def value(i,metric,k=0,ix=None):
        v=views[i];d=v['d'] if ix is None else v['d'][np.ix_(ix,ix)]
        if metric=='uncovered':return c.next_uncovered(d,k)
        if len(d)<2:return np.nan
        if metric=='pair_disagreement':return float(np.mean(d[np.triu_indices(len(d),1)]>c.CUT))
        counts=[r['effective_point_count'] for r in v['rows']]
        if ix is not None:counts=[counts[j] for j in ix]
        a=np.array(counts);return np.mean((a[:,None]!=a[None,:])[np.triu_indices(len(a),1)])
    def mean_sources(ids,vals):
        x=pd.DataFrame([dict(building=views[i]['building'],family=family.get(i,'unconfirmed:'+i),v=vals[i]) for i in ids])
        return x.groupby(['building','family']).v.mean().groupby('building').mean().mean()
    preds=[];paircontrols=[]
    specs=[('pair_disagreement',0,4),('count_disagreement',0,4)]+[('uncovered',k,k+3) for k in [3,5,8,12,15,18,20]]
    for metric,k,minN in specs:
        vals={i:value(i,metric,k) for i,v in views.items() if v['N']>=minN}
        for i,y in vals.items():
            outside=[j for j in vals if views[j]['building']!=views[i]['building']]
            if not outside:continue
            baseline=mean_sources(outside,vals)
            others=[j for j in vals if views[j]['building']==views[i]['building'] and family.get(j,'unconfirmed:'+j)!=family.get(i,'unconfirmed:'+i)]
            for label,sources in [('same_room_broad',adj[i]),('same_room_comparable',comp[i]),
                ('same_scene_other_building',set(j for j in outside if scene[j]==scene[i] and scene[i] in scene_known))]:
                src=sorted(j for j in sources if j in vals)
                if not src:continue
                pred=np.mean([vals[j] for j in src]) if label.startswith('same_room') else mean_sources(src,vals)
                preds.append(dict(image_id=i,code=views[i]['code'],building=views[i]['building'],family=family.get(i,'unconfirmed:'+i),
                    N=views[i]['N'],scene=scene[i],metric=metric,k=k,minN=minN,kind=label,value=y,prediction=pred,baseline=baseline,
                    building_other_room_baseline=mean_sources(others,vals) if others else np.nan,
                    source_ids=';'.join(src),source_codes=';'.join(views[j]['code'] for j in src),
                    source_N=';'.join(str(views[j]['N']) for j in src),source_buildings=len(set(views[j]['building'] for j in src)),
                    source_outcome_exposed=any(j in exposed[i] for j in src)))
        if metric!='uncovered':continue
        for a,b in links:
            va,vb=views[a],views[b];wa={w:j for j,w in enumerate(va['workers'])};wb={w:j for j,w in enumerate(vb['workers'])}
            common=sorted(set(wa)&set(wb))
            if len(common)<minN:continue
            ia=[wa[w] for w in common];ib=[wb[w] for w in common]
            ya,yb=value(a,metric,k,ia),value(b,metric,k,ib)
            all_a,all_b=value(a,metric,k),value(b,metric,k)
            ca=[va['rows'][j]['effective_point_count'] for j in ia];cb=[vb['rows'][j]['effective_point_count'] for j in ib]
            support=sorted(set(ca+cb));ac=collections.Counter(ca);bc=collections.Counter(cb)
            paircontrols.append(dict(a_id=a,b_id=b,a_code=va['code'],b_code=vb['code'],building=va['building'],family=family.get(a,a),k=k,
                common_N=len(common),a_N=va['N'],b_N=vb['N'],workers=';'.join(common),comparable=b in comp[a],
                common_a=ya,common_b=yb,common_absolute_gap=abs(ya-yb),all_a=all_a,all_b=all_b,all_absolute_gap=abs(all_a-all_b),
                same_person_same_count=np.mean(np.array(ca)==np.array(cb)),
                count_JS_distance=jensenshannon([ac[s] for s in support],[bc[s] for s in support],base=2),
                candidates=';'.join(links[a,b])))
    pr=pd.DataFrame(preds);pr['absolute_error']=abs(pr.value-pr.prediction);pr['baseline_absolute_error']=abs(pr.value-pr.baseline)
    pr['gain']=pr.baseline_absolute_error-pr.absolute_error
    c.save('room_scene_predictions.csv',pr);c.save('same_room_identical_workers.csv',pd.DataFrame(paircontrols))
    summaries=[]
    for (kind,metric,k),z in pr.groupby(['kind','metric','k']):
        for scope,zz in [('all',z),('without_uNb',z[z.building!='uNb9QFRL6hY'])]:
            if not len(zz):continue
            agg=zz.groupby(['building','family'])[['absolute_error','baseline_absolute_error']].mean().groupby('building').mean()
            summaries.append(dict(kind=kind,metric=metric,k=k,scope=scope,images=len(zz),families=zz.family.nunique(),buildings=zz.building.nunique(),
                MAE=agg.absolute_error.mean(),baseline_MAE=agg.baseline_absolute_error.mean(),
                gain=c.building_summary(zz,'gain',room='family')))
    c.save('room_scene_summary.json',summaries)
    # Simple model-only image features; published frozen features, NO target annotation derived predictors.
    feat=pd.read_csv(c.SOURCE/'analysis_results/clustering_release_local_20260920/current/input/supplement/model_image_features.csv').set_index('image_id')
    feature_sets={'model_corner_counts':['bi_enclosed_corners','bi_extended_corners','hohonet_corners'],
        'model_corners_and_gaps':['bi_enclosed_corners','bi_extended_corners','hohonet_corners']+[z for z in feat.columns if z.startswith('gap_')]}
    fp=[]
    for metric,k,minN in [('pair_disagreement',0,4),('uncovered',5,8),('uncovered',8,11)]:
        ids=[i for i,v in views.items() if v['N']>=minN and i in feat.index];buildings=np.array([views[i]['building'] for i in ids]);y=np.array([value(i,metric,k) for i in ids])
        for b in sorted(set(buildings)):
            tr=buildings!=b;te=~tr
            if tr.sum()<10:continue
            baseline=np.mean([y[tr&(buildings==other)].mean() for other in set(buildings[tr])])
            for name,cols in feature_sets.items():
                X=feat.loc[ids,cols].to_numpy();imp=SimpleImputer(strategy='median');Xt=imp.fit_transform(X[tr]);Xe=imp.transform(X[te]);sc=StandardScaler();Xt=sc.fit_transform(Xt);Xe=sc.transform(Xe)
                weights=np.array([1./sum(buildings[tr]==z) for z in buildings[tr]]);weights*=len(weights)/weights.sum()
                model=Ridge(alpha=10.).fit(Xt,y[tr],sample_weight=weights);pred=model.predict(Xe).clip(0,1)
                for i,yi,pi in zip(np.array(ids)[te],y[te],pred):fp.append(dict(image_id=i,code=views[i]['code'],building=b,family=family.get(i,'unconfirmed:'+i),N=views[i]['N'],
                    metric=metric,k=k,feature_set=name,value=yi,prediction=pi,baseline=baseline))
    ff=pd.DataFrame(fp);ff['error']=abs(ff.value-ff.prediction);ff['base_error']=abs(ff.value-ff.baseline);ff['gain']=ff.base_error-ff.error
    c.save('model_feature_lobo_predictions.csv',ff)
    fs=[]
    for key,z in ff.groupby(['metric','k','feature_set']):
        fs.append(dict(metric=key[0],k=key[1],feature_set=key[2],MAE=z.groupby('building').error.mean().mean(),baseline_MAE=z.groupby('building').base_error.mean().mean(),gain=c.building_summary(z,'gain')))
    c.save('model_feature_summary.json',fs)
    print(json.dumps(c.clean(summaries),ensure_ascii=False,indent=2));print('FEATURES',json.dumps(c.clean(fs),ensure_ascii=False,indent=2))

if __name__=='__main__':main()
