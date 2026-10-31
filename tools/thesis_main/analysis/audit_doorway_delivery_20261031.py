"""Independent checks of delivered records, member paths, scores and headline statistics."""
import gzip
import io
import json
import math
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from shapely.geometry import Polygon

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'research/data/doorway_review_20261030/pro_delivery_independent_audit_20261031'
PREFIX='HOHONET_doorway_v21_20261031/'
DOWNLOADS=Path('C:/Users/ASUS/Downloads')

def native_probe(raw, pools, index, scores, refs):
    sys.path.insert(0,str(ROOT))
    from tools.thesis_main.analysis.consensus_delivery_20261008 import WORKING_GAP, fuse
    from tools.thesis_main.analysis.wall_consensus_v1_process_20261017 import cached_matching
    from tools.thesis_main.analysis.scope_quality_scoring_20261016 import scoring_engine
    from tools.thesis_main.analysis.wall_consensus_quality_20261015 import measured
    records=json.loads(gzip.decompress(raw('04','stage04_computation/design/FROZEN_RECORDS.json.gz')))
    lookup={(r.image,frozenset(r.member_object_ids.split('|'))):r for r in index.itertuples()}
    selected=[lookup[(p['image'],frozenset(p['records']))] for p in pools if p['family']=='overall_before' and not p.get('sensitivity')]
    # Full pools were chosen before seeing quality; supplement each observed geometry state at k=10.
    for _,g in scores[scores.k==10].groupby('geometry_status'):
        key=g.iloc[0].physical_team_key
        selected.append(next(r for r in index.itertuples() if r.physical_team_key==key))
    selected=list({r.physical_team_key:r for r in selected}.values())
    refmap={(r['image'],r['target']):r for r in refs}
    scoremap=scores.set_index('score_key');rows=[]
    engine_dir=ROOT/'research/statistics/b8l2_shared_v6_20261016/inputs'
    with cached_matching(),scoring_engine(engine_dir/'measurement_engine.zip',engine_dir/'working_models.py') as (engine,_):
        for r in selected:
            saved=next(json.loads(line) for line in gzip.decompress(raw('04',r.endpoint_file)).splitlines() if json.loads(line)['physical_team_key']==r.physical_team_key)
            state=fuse([records[oid] for oid in r.member_object_ids.split('|')],gap=WORKING_GAP)['automatic']
            candidate=state['candidate'];nodes=len(state['node_consensus']['nodes'])
            status=candidate.get('geometry_status','not_evaluable')
            complete=nodes>=4 and status=='ok'
            assert nodes==saved['nodes'] and complete==saved['complete_evaluable']
            assert status==saved['geometry_status']
            a=candidate['points'];b=saved['geometry']['points']
            point_error=float(np.max(np.abs(np.asarray(a)-np.asarray(b)))) if a is not None and b is not None else None
            assert (a is None)==(b is None) and (point_error is None or point_error<1e-8)
            errors={}
            if complete:
                for target in ('全部','空间1','空间2'):
                    sk=r.physical_team_key+'::'+target
                    if sk not in scoremap.index:continue
                    ref=refmap[(r.image,target)]
                    values=measured(engine,state,dict(floor=ref['floor_xz_h'],points=ref['points_1024x512']))
                    known=scoremap.loc[sk]
                    errors[target]={field:abs(float(values[field])-float(known[field])) for field in ['iou_2d','S_bottom_deg','dir','Hmean','Hcenter','IoU3D100']}
                    assert max(errors[target].values())<1e-7,(r.image,target,errors[target])
            rows.append(dict(physical_team_key=r.physical_team_key,image=r.image,k=r.k,nodes=nodes,
                geometry_status=status,complete_evaluable=complete,point_error=point_error,metric_errors=errors))
            print('native replay',r.image,r.k,status,flush=True)
    return rows

def paired_metric(a,b,images,hold_images):
    delta=pd.to_numeric(b).astype(float)-pd.to_numeric(a).astype(float)
    values=delta.groupby(images).mean().dropna()
    return dict(mean=float(values.mean()),positive=int((values>1e-9).sum()),negative=int((values< -1e-9).sum()),
        same=int((values.abs()<=1e-9).sum()),images=len(values),paired_finite=int(delta.notna().sum()),attempts=len(delta),
        clean_image_subset_mean=float(values[~values.index.isin(hold_images)].mean()),
        per_image={str(k):float(v) for k,v in values.items()})

def source_reference_checks(refs):
    current=json.loads((ROOT/'research/data/releases/v2.1/reference_catalog.json').read_text(encoding='utf8'))
    current={r['target_id']:r for r in current}
    adopted=json.loads((ROOT/'research/data/scope_quality_rescore_20261016/vertical_cut_audit_20261028/extension_v1/adopted_references_20261028/ceiling_adopted_20261028/ADOPTED_REFERENCES.json').read_text(encoding='utf8'))
    adopted={r['image_id']:r for r in adopted};rows=[]
    with zipfile.ZipFile(ROOT/'data/external/label_data.zip') as original:
        for ref in refs:
            if ref['target']=='全部':
                expected=current[ref['parent_reference_id']]
                error=float(np.max(np.abs(np.asarray(expected['points_1024x512'])-np.asarray(ref['points_1024x512']))))
                assert error<1e-8,(ref['image'],error)
                rows.append(dict(image=ref['image'],target=ref['target'],source=expected['reference_version'],point_error=error))
            else:
                if ref['parent_reference_version']=='user_ceiling_adopted_20261028':
                    height=np.asarray(adopted[ref['image_id']]['geometry']['top3d'])[:,1].mean();source='local_user_adopted_ceiling'
                else:
                    label=json.loads(original.read('label_data/'+ref['image_id']+'_label.json'))
                    height=(label['layoutHeight']-label['cameraHeight'])/label['cameraHeight'];source='local_original_label_data'
                top=np.asarray(ref['reference_geometry']['top3d'])
                error=float(np.max(np.abs(top[:,1]-height)))
                assert error<1e-8,(ref['image'],error)
                rows.append(dict(image=ref['image'],target=ref['target'],source=source,height=float(height),height_error=error))
    return rows

def whole_reference_scope_probe(refs):
    sys.path.insert(0,str(ROOT))
    from tools.thesis_main.analysis.supplement_doorway_preparation_20261031 import classify
    final=json.loads((ROOT/'research/data/doorway_review_20261030/curve_preparation_v21/full_review_20261031/ALIGNMENT_DECISIONS.json').read_text(encoding='utf8'))
    cuts={r['image']:r['cuts'] for r in final};rows=[]
    for ref in refs:
        if ref['target']!='全部':continue
        label,fractions=classify(ref['floor_xz_h'],cuts[ref['image']])
        rows.append(dict(image=ref['image'],automatic_class=label,fractions=fractions))
    return rows

def main():
    OUT.mkdir(exist_ok=True)
    archives={key:zipfile.ZipFile(next(DOWNLOADS.glob('DOORWAY_'+key+'*.zip'))) for key in ['01','02','04']}
    def raw(key,name):return archives[key].read(PREFIX+name)
    def js(key,name):return json.loads(raw(key,name))
    def table(key,name,**kw):
        data=raw(key,name)
        if name.endswith('.gz'):data=gzip.decompress(data)
        return pd.read_csv(io.BytesIO(data),**kw)
    def save(name,value):
        (OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf8')
    result={'archive_members':{key:len(z.namelist()) for key,z in archives.items()}}
    ledger=js('01','stage01_pools/FINAL_RECORD_LEDGER.json')
    assert isinstance(ledger,list)
    inv={r['object_id']:r for r in json.loads((ROOT/'research/data/releases/v2.1/quality_inventory.json').read_text(encoding='utf8'))}
    base=[r for r in ledger if r['base_candidate']]
    held=[r for r in base if not inv[r['object_id']]['current_quality_eligible']]
    assert len(base)==584 and len(held)==13
    assert all(inv[r['object_id']]['pool_analysis_eligible'] for r in base)
    previous=json.loads((ROOT/'research/data/doorway_review_20261030/curve_preparation_v21/supplement_20261031/UPDATED_RECORD_LEDGER.json').read_text(encoding='utf8'))
    assert {r['object_id'] for r in base}=={r['object_id'] for r in previous if r['base_candidate']}
    previous={r['object_id']:r for r in previous}
    protected=[r for r in base if r['protected_adjudication']]
    assert len(protected)==113 and all(r['final_scope']==previous[r['object_id']]['adopted_scope'] for r in protected)
    assert not any(r['worker'] in ['W019','W026'] for r in base)
    result['adjudication_parity']=dict(base_members_match_local=True,protected_adjudications=113,protected_scope_changes=0,W019_W026_in_base=0)
    hold_ids={r['object_id'] for r in held};hold_images={r['image'] for r in held}
    hold_details=[dict(object_id=r['object_id'],image=r['image'],worker=r['worker'],
        quality_eligible=inv[r['object_id']]['current_quality_eligible'],reasons=inv[r['object_id']]['quality_exclusion_reasons'],
        final_scope=r['final_scope']) for r in held]
    save('INDEPENDENT_HOLDS_13.json',hold_details)
    result['qualification']=dict(base=584,quality_eligible=571,holds=13,images=dict(Counter(r['image'] for r in held)),
        reason_groups=dict(Counter('|'.join(inv[r['object_id']]['quality_exclusion_reasons']) for r in held)))
    pools=js('04','stage04_computation/design/POOL_DEFINITIONS_WITH_SENSITIVITY.json')
    poolmap={r['pool_id']:r for r in pools}
    orders=table('02','stage04_computation/design/BASE_256_ORDERS.csv.gz').fillna('')
    links=table('02','stage04_computation/design/PREFIX_LINKS.csv.gz')
    index=table('04','stage04_computation/PHYSICAL_ENDPOINT_INDEX.csv.gz')
    cols=['score_key','physical_team_key','image','target','k','B8L2','D10','IoU3D100','complete_evaluable',
        'iou_2d','S_bottom_deg','dir','Hmean','Hcenter','score_status','geometry_status']
    scores=table('04','stage04_computation/ENDPOINT_TARGET_SCORES.csv.gz',usecols=cols)
    assert not index.physical_team_key.duplicated().any() and not scores.score_key.duplicated().any()
    physical={r.physical_team_key:frozenset(r.member_object_ids.split('|')) for r in index.itertuples()}
    cached={(r.image,frozenset(r.member_object_ids.split('|'))):r.physical_team_key for r in index.itertuples()}
    ordermap={};added=set();added_images=set()
    for r in orders.itertuples():
        members=r.base_member_object_ids.split('|');old=r.old_member_object_ids.split('|');oldset=set(old)
        assert len(members)==len(set(members))
        assert [x for x in members if x in oldset]==old
        extra=set(members)-oldset;added|=extra
        if extra:added_images.add(r.image)
        ordermap[(r.image,r.base_replicate)]=members
    assert added==hold_ids
    expected={}
    for r in links.itertuples():
        key=(r.pool_id,r.base_replicate)
        if key not in expected:
            members=set(poolmap[r.pool_id]['records'])
            expected[key]=[x for x in ordermap[(r.image,r.base_replicate)] if x in members]
        assert physical[r.physical_team_key]==frozenset(expected[key][:r.k])
    result['identity']=dict(orders=len(orders),prefix_links=len(links),physical_endpoints=len(index),score_rows=len(scores),
        added_records=len(added),images_with_additions=len(added_images),images_without_additions=17-len(added_images),prefix_member_mismatches=0)
    print('membership checked',result['identity'],flush=True)
    finite=scores[['iou_2d','S_bottom_deg','dir','Hmean','Hcenter','B8L2','D10']].notna().all(axis=1)
    s=scores.loc[finite];I=s.iou_2d.clip(0,1).to_numpy();Sb=s.S_bottom_deg.to_numpy();D=s.dir.to_numpy()
    H=(s.Hmean.to_numpy()/.8)**2+(s.Hcenter.to_numpy()/.25)**2
    errors={}
    for name,scale in [('B8L2',8),('D10',10)]:
        floor=1-I+I*Sb**2/32;direction=I*1.5*D**2/(D**2+scale**2)
        q=100*I/(I+np.hypot(floor,direction)+I*H)
        errors[name]=float(np.max(np.abs(q-s[name].to_numpy())))
        assert errors[name]<1e-8
    result['score_formula']=dict(rows=int(finite.sum()),max_absolute_errors=errors)
    exact=table('02','stage04_computation/design/EXACT_LINKS.csv.gz')
    for (pool_id,k),group in exact.groupby(['pool_id','k']):
        members=set(poolmap[pool_id]['records'])
        teams=[physical[x] for x in group.physical_team_key]
        assert len(teams)==len(set(teams))==math.comb(len(members),int(k))
        assert all(len(team)==k and team<=members for team in teams)
    result['exact_enumeration']=dict(links=len(exact),pool_k_groups=exact.groupby(['pool_id','k']).ngroups)
    merged=links.merge(scores,on='score_key',how='left',validate='many_to_one',suffixes=('','_score'),indicator=True)
    assert (merged['_merge']=='both').all()
    # Same image/path comparisons, then image equal weighting; invalid Q stays missing.
    def paired(fa,fb,ka,kb):
        a=merged[(merged.family==fa)&(merged.k==ka)]
        b=merged[(merged.family==fb)&(merged.k==kb)]
        p=a.merge(b,on=['image','base_replicate'],suffixes=('_a','_b'),validate='one_to_one')
        out={}
        for metric in ['B8L2','D10','IoU3D100','complete_evaluable']:
            out[metric]=paired_metric(p[metric+'_a'],p[metric+'_b'],p.image,hold_images)
        return out
    headlines={'screening_k10':paired('overall_before','overall_after',10,10),
        'whole_compatible_k10':paired('overall_after','whole_compatible',10,10),
        'screened_6_to_10':paired('overall_after','overall_after',6,10)}
    save('RECOMPUTED_HEADLINES.json',headlines)
    spread={}
    for field,fn in [('sd',lambda x:x.std(ddof=1)),('p10',lambda x:x.quantile(.1))]:
        groups=merged[(merged.k==10)&merged.family.isin(['overall_after','whole_compatible'])].groupby(['image','family']).B8L2.agg(fn).unstack()
        delta=groups.whole_compatible-groups.overall_after
        spread[field]=dict(mean=float(delta.mean()),positive=int((delta>1e-9).sum()),negative=int((delta< -1e-9).sum()),same=int((delta.abs()<=1e-9).sum()))
    result['whole_compatibility_spread_k10']=spread
    print('headline recomputation', {k:(v['B8L2']['mean'],v['complete_evaluable']['mean']) for k,v in headlines.items()},flush=True)
    # This checks missing cache coverage only; it is not a recomputed exclusion sensitivity.
    needed=defaultdict(set);path_counts=Counter()
    for pool in pools:
        if pool.get('sensitivity') or pool['image'] not in hold_images:continue
        allowed=set(pool['records'])-hold_ids
        for replicate in range(256):
            order=[x for x in ordermap[(pool['image'],replicate)] if x in allowed]
            for k in range(3,len(order)+1):
                key=(pool['image'],frozenset(order[:k]));needed[key].add(pool['target']);path_counts[pool['family']]+=1
    score_keys=set(scores.score_key);missing_physical=0;missing_score=0
    for key,targets in needed.items():
        phys=cached.get(key)
        if phys is None:missing_physical+=1;continue
        missing_score+=sum(phys+'::'+target not in score_keys for target in targets)
    result['exclude_13_cache_coverage']=dict(unique_teams_needed=len(needed),physical_teams_missing=missing_physical,
        missing_target_scores_for_existing_geometry=missing_score,prefix_attempts_by_family=dict(path_counts),full_sensitivity_computed=False)
    refs=js('04','stage04_computation/recovered_reference_scores/FINAL_REFERENCES.json')
    final=json.loads((ROOT/'research/data/doorway_review_20261030/curve_preparation_v21/full_review_20261031/ALIGNMENT_DECISIONS.json').read_text(encoding='utf8'))
    final={r['image']:r for r in final};reference_deltas=[]
    for ref in refs:
        if ref['target'] not in ['空间1','空间2']:continue
        expected=final[ref['image']]['space_polygons'][0 if ref['target']=='空间1' else 1]
        a=Polygon(expected);b=Polygon(ref['floor_xz_h'])
        delta=a.symmetric_difference(b).area
        reference_deltas.append(dict(image=ref['image'],target=ref['target'],area_delta=delta))
    result['reference_floor_match']=dict(side_references=len(reference_deltas),max_symmetric_difference=max(r['area_delta'] for r in reference_deltas),
        mismatches=[r for r in reference_deltas if r['area_delta']>1e-9])
    reference_checks=source_reference_checks(refs)
    save('SOURCE_REFERENCE_CHECKS_51.json',reference_checks)
    result['reference_source_checks']=dict(references=len(reference_checks),whole=17,sides_from_original_source=28,sides_from_user_adopted_plane=6)
    scope_probe=whole_reference_scope_probe(refs)
    save('WHOLE_REFERENCE_SCOPE_PROBE.json',scope_probe)
    result['whole_reference_auto_scope']=dict(Counter(r['automatic_class'] for r in scope_probe))
    native=native_probe(raw,pools,index,scores,refs)
    save('NATIVE_REPLAY_CHECKS.json',native)
    result['native_replay']=dict(teams=len(native),status_counts=dict(Counter(r['geometry_status'] for r in native)),
        reference_metric_comparisons=sum(len(r['metric_errors']) for r in native))
    result['limits']=['No full fusion rerun','No confidence interval resampling rerun','No independent physical closure semantic adoption','No package hash computation']
    save('CHECKS.json',result)
    save('SOURCE_FILES.json',dict(archives=[str(z.filename) for z in archives.values()],method='Direct ZIP reads; local inventory and final geometry used as independent authority'))
    print(json.dumps(result,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
