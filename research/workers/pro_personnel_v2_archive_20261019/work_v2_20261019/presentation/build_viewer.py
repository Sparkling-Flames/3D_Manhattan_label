#!/usr/bin/env python3
"""Build a self-contained, read-only Chinese v2 research viewer.

Includes all eligible annotation pools, all 9/12-degree partitions, profiles,
and a declared browsing subset of genuine saved teams. Full experiment outputs
are in the replication archives. Browsing selection never changes an analysis.
"""
from pathlib import Path
import argparse,base64,gzip,hashlib,io,json,math,time
import numpy as np
import pandas as pd
from PIL import Image

HERE=Path(__file__).resolve().parent; WORK=HERE.parent;ROOT=WORK.parent
RF='request_id team_id k request_family strategy scheme composition draw_id path_id added_worker threshold selection_metric selection_origin candidate_pool B8L2 D10 IoU3D100 iou_2d omission extension Hmean Hcenter complete_evaluable connection_available score_status geometry_status geometry_reason order_status nodes selected_node_n reference_node_shortfall source_time_known_n source_time_missing_n source_time_known_sum_seconds source_time_total_seconds target_time_known_n target_time_missing_n target_time_known_sum_seconds target_time_total_seconds R_union_normalized R_valid_pairs R_possible_pairs member_workers ordered_workers seed_decimal seed_hex'.split()
CF='request_a request_b comparison_family k k_a k_b background_id entrant_a entrant_b B8L2_change D10_change abs_B8L2_change quality_comparable complete_a complete_b both_complete floor_jaccard_difference structure_bound_cyclic_deg structure_reverse_allowed_deg structure_available structure_reason node_count_difference node_count_change mean_height_prism_pair_iou changed_coidentity_pairs common_pair_comparisons edge_relation_jaccard_difference selected_shared_observation_difference shared_workers same_subset source_time_change_seconds target_time_change_seconds complete_to_incomplete incomplete_to_complete joint_stable_main joint_with_shared_connections_and_retention path_id k_from k_to added_worker threshold_increased'.split()

def load(p):
    with (gzip.open(p,'rt') if str(p).endswith('.gz') else open(p)) as f:return json.load(f)
def clean(x):
    if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [clean(v) for v in x]
    if isinstance(x,np.generic):return clean(x.item())
    if isinstance(x,float) and not math.isfinite(x):return None
    return x
def dumps(x):return json.dumps(clean(x),ensure_ascii=False,separators=(',',':'),allow_nan=False)
def csv(p):
    try:return pd.read_csv(p,low_memory=False)
    except pd.errors.EmptyDataError:return pd.DataFrame()
def pack_for_viewer(data):
    """Lossless row-column encoding reduces transient offline JSON memory."""
    data['row_encoding']={'requests':RF,'comparisons':CF+['same_cluster_9'],'node_members':['worker','pair_index']}
    for p in data['pools'].values():
        for group in ['requests','comparisons']:
            cols=data['row_encoding'][group]
            rows=p[group]
            packed=[[r.get(k) for k in cols] for r in rows]
            assert all({k:v for k,v in zip(cols,row)}==original for row,original in zip(packed,rows))
            p[group]=packed
        for s in p['states'].values():
            for n in s['nodes']:
                n['members']=[[m['worker'],m['pair_index']]for m in n['members']]
    return data
def keep(r):
    fam=r['request_family'];k=r['k'];draw=r.get('draw_id',0)
    if fam=='uniform_prefix':return draw==0
    if fam=='cluster_oracle_prefix':return r.get('threshold')==9
    if k not in [8,12,16,24]:return False
    if fam=='independent_random_team':return draw<=2
    if fam=='profile_policy':return r.get('selection_metric')=='B8L2' and r.get('selection_origin')=='all' and (r.get('strategy')!='eligible_random' or draw<=1)
    if fam=='profile_composition':return r.get('selection_metric')=='B8L2' and r.get('scheme') in ['QT','QTD_dtype']
    if fam=='cluster_oracle':return r.get('threshold')==9 and draw==0
    if fam=='behavior_policy':return True
    return False

def build(limit=0):
    started=time.monotonic();snap=load(WORK/'fusion/INPUT_SNAPSHOT.json.gz'); cp=load(WORK/'clusters/CLUSTER_API.json.gz')
    clusters={p['meta']['pool_id']:p for p in cp['pools']}
    ima={x['image_id']:x for x in load(WORK/'original_images/ORIGINAL_IMAGE_AUDIT.json')['images']}
    full=csv(WORK/'profiles/full_profiles.csv').to_dict('records');fold=csv(WORK/'profiles/fold_profiles.csv').to_dict('records')
    pe=csv(WORK/'audit/person_evidence_62.csv').to_dict('records')
    cases=load(HERE/'viewer_cases.json') if (HERE/'viewer_cases.json').exists() else []
    if isinstance(cases,dict):cases=cases.get('cases',[])
    extra_ids={c.get(k) for c in cases for k in ['request_a','request_b'] if c.get(k)}
    extra_pairs={frozenset((c['request_a'],c['request_b'])) for c in cases if c.get('request_a') and c.get('request_b')}
    ps={};images={};manifest=[];n_all=0;n_team=0
    for pi,po in enumerate(snap['images'][:limit or None]):
        pid=po['pool_id'];src=WORK/'fusion/pools'/pid
        allrows=load(src/'request_results.json.gz')['results'];n_all+=len(allrows)
        byid={r['request_id']:r for r in allrows};chosen={r['request_id'] for r in allrows if keep(r)} | (extra_ids & set(byid))
        assignments={}
        for part in clusters[pid]['partitions']:
            for algorithm in ['affinity','complete']:
                assignments[f'{int(part["threshold_deg"])}_{algorithm}']=part[algorithm]
        cm={oid:i for i,g in enumerate(assignments['9_affinity']) for oid in g}
        comps=[];compdenom={}
        compdir=WORK/'fusion/comparisons'/pid
        if not compdir.exists():compdir=WORK/'fusion/comparisons_initial'/pid
        for family in ['replacements','random_same_k','composition_comparisons','policy_comparisons','prefix_transitions']:
            path=compdir/(family+'.csv.gz')
            if not path.exists():continue
            f=csv(path);compdenom[family]=len(f)
            if not len(f):continue
            if family=='replacements':
                f=f[f.k.isin([8,12,16,24])].copy()
                f['same_cluster_9']=[cm.get(a)==cm.get(b) for a,b in zip(f.entrant_object_id_a,f.entrant_object_id_b)]
                indexes=[]
                for _,g in f.groupby(['k','same_cluster_9']):
                    valid=g[g.quality_comparable].sort_values(['abs_B8L2_change','request_a','request_b'])
                    if len(valid):indexes.extend([valid.index[0],valid.index[len(valid)//2],valid.index[-1]])
                    incomplete=g[~g.both_complete]
                    if len(incomplete):indexes.append(incomplete.index[0])
                indexes.extend(i for i,r in f.iterrows() if frozenset((r.request_a,r.request_b)) in extra_pairs)
                f=f.loc[sorted(set(indexes))]
            else:
                f=f[f.request_a.isin(chosen)&f.request_b.isin(chosen)]
                if family=='random_same_k':f=f.groupby('k',group_keys=False).head(6)
            for r in f.to_dict('records'):
                if r['request_a'] not in byid or r['request_b'] not in byid:continue
                chosen.update([r['request_a'],r['request_b']])
                comps.append({k:r.get(k) for k in CF}|{'same_cluster_9':r.get('same_cluster_9')})
        rows=[{k:r.get(k) for k in RF} for r in allrows if r['request_id'] in chosen]
        n_team+=len(rows)
        teamids={r['team_id'] for r in rows};states={}
        rawstates=load(src/'states.json.gz')['states']
        for s in rawstates:
            if s['team_id'] not in teamids:continue
            a=s['automatic'];cand=a.get('candidate') or {};nodes=(a.get('node_consensus') or {}).get('nodes') or []
            states[s['team_id']]={'points':cand.get('points'),'floor':cand.get('footprint'),'status':cand.get('status'),'ring_confirmed':cand.get('ring_confirmed'),
                 'order_status':cand.get('order_status'),'reason':cand.get('reason'),'minimum_support':a.get('minimum_support'),
                 'nodes':[{'id':n.get('feature_id'),'support':n.get('support'),'selected':n.get('feature_id') in (cand.get('feature_ids') or []),
                    'points':n.get('points'),'members':[{'worker':m.get('worker'),'pair_index':m.get('pair_index')} for m in n.get('members',[])]} for n in nodes]}
        assert len(states)==len(teamids)
        paths=[]
        paths_d={}
        for r in rows:
            if r.get('path_id'):paths_d.setdefault(r['path_id'],[]).append(r)
        for pathid,g in paths_d.items():
            g.sort(key=lambda r:r['k'])
            if [r['k'] for r in g]!=list(range(1,len(g)+1)):continue
            paths.append({'id':pathid,'strategy':g[0]['strategy'],'requests':[r['request_id'] for r in g]})
        baseline=[]
        for k,g in pd.DataFrame(allrows).query("request_family in ['uniform_prefix','independent_random_team']").groupby('k'):
            u=g.drop_duplicates('team_id')
            baseline.append({'k':int(k),'requests':len(g),'unique_teams':len(u),'complete':int(u.complete_evaluable.sum()),'Q_success_mean':u.B8L2.mean(),'Q_success_p10':u.B8L2.quantile(.1),'Q_success_p90':u.B8L2.quantile(.9)})
        iid=po['meta']['image_id'];imeta=ima[iid]
        if iid not in images:
            fp=Path(imeta['local_path'])
            if not fp.is_absolute():fp=ROOT/'repo_main_20261019'/fp
            if not fp.exists():fp=WORK/'original_images/images'/(iid+'.png')
            im=Image.open(fp).convert('RGB');im.thumbnail((1536,768),Image.Resampling.LANCZOS);buf=io.BytesIO();im.save(buf,format='JPEG',quality=85,optimize=True)
            images[iid]={'data':'data:image/jpeg;base64,'+base64.b64encode(buf.getvalue()).decode(),'status':imeta['status'],'source_sha256':hashlib.sha256(fp.read_bytes()).hexdigest(),'display_size':im.size}
        records=[]
        for r in po['records']:
            records.append({k:r.get(k) for k in ['object_id','worker_id','points','B8L2','D10','source_time_seconds','target_time_seconds','origin','order_status','ring_confirmed']})
        ps[pid]={'meta':po['meta'],'reference':po['reference'],'records':records,'clusters':assignments,'requests':rows,'states':states,'comparisons':comps,'paths':paths,'baseline':baseline}
        manifest.append({'pool_id':pid,'all_saved_requests':len(allrows),'viewer_requests':len(rows),'viewer_states':len(states),'viewer_comparisons':len(comps),'viewer_full_paths':len(paths),'available_comparisons':compdenom})
        if (pi+1)%25==0:print('assembled',pi+1,'pools',flush=True)
    cases=[c for c in cases if c.get('pool_id') in ps]
    data={'schema':'v2_personnel_team_offline_20261019_r1','pools':ps,'images':images,'full_profiles':full,'fold_profiles':fold,'evidence':pe,'cases':cases,'selection_manifest':manifest,
        'uncertainty':csv(WORK/'profiles/profile_stability_uncertainty.csv').to_dict('records'),
        'fine_stability':csv(WORK/'profiles/fine_dtype_stability.csv').to_dict('records'),
        'geometry_cases':csv(WORK/'clusters/geometry_case_candidates.csv').head(12).to_dict('records'),
        'notes':{'commit':snap['git_commit'],'B8_main':True,'D10_direction_scale_only':True,'N1':False,'all_saved_requests_at_build':n_all,'viewer_requests':n_team,'full_inventory':10439,'quality_records':7302,'ordinary_manual':5719}}
    raw=dumps(pack_for_viewer(data)).encode();gz=gzip.compress(raw,compresslevel=6,mtime=0);b64=base64.b64encode(gz).decode()
    html=(HERE/'viewer_template.html').read_text().replace('__DATA__',b64)
    out=HERE/('personnel_fusion_v2_viewer'+('_pilot' if limit else '')+'.html');out.write_text(html)
    rec={'schema':data['schema'],'pools':len(ps),'images':len(images),'workers':len(full),'annotation_records':sum(len(p['records']) for p in ps.values()),'saved_requests':n_all,'viewer_requests':n_team,'viewer_states':sum(len(p['states']) for p in ps.values()),'viewer_comparisons':sum(len(p['comparisons']) for p in ps.values()),'viewer_full_paths':sum(len(p['paths']) for p in ps.values()),'cases':len(cases),'raw_json_bytes':len(raw),'gzip_bytes':len(gz),'html_bytes':out.stat().st_size,'html_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'seconds':time.monotonic()-started,'offline_network_dependencies':[],
        'display_selection':'All eligible annotations and 4 cluster partitions. Uniform path draw0, 9degree oracle paths, B8 all-origin policies, QT/fine_dtype composition variants, finite fixed-k random examples and within/cross-cluster replacement min/median/max plus incomplete examples. Post-outcome display selection does not enter statistical estimates.',
        'projection':'ERP and wireframe reuse frozen continuous-pixel display convention; final scoring geometry unchanged. Spherical clustering retains its own audited +0.5 pixel-center definition. Wireframe is not the mean-height prism used for the 3D IoU diagnostic.',
        'photos':'Derived JPEG display previews from Release originals; two explicitly marked repository previews have no original in current Release. No claim of visual review of all assets.'}
    (HERE/('VIEWER_BUILD_RECEIPT'+('_pilot' if limit else '')+'.json')).write_text(json.dumps(rec,ensure_ascii=False,indent=2))
    (HERE/'VIEWER_SELECTION_MANIFEST.json').write_text(dumps(manifest));print(json.dumps(rec,ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--limit',type=int,default=0);args=ap.parse_args();build(args.limit)
