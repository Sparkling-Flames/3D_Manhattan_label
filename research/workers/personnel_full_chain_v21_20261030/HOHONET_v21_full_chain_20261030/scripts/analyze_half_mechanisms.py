"""All latest half-team exceptions, complete local votes and exact backgrounds.

Numerical descriptors never imply a visual/semantic diagnosis. All unselected
groups, original observations and projected source rings are retained.
"""
from pathlib import Path
import collections,gzip,itertools,json,math,sys,types
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'stage01_half_team'
sys.path[:0]=[str(ROOT/'source'),str(ROOT/'scripts/vendor')]
from export_ac_mechanisms import diagnose_case
from complete_half_traces import read,clean,write
from prepare_half_team import aggregate
from tools.thesis_main.analysis.fixed_identity_location_20261007 import median_pair
RT=types.SimpleNamespace(clean=clean,workers=lambda x:sorted(set(x if isinstance(x,list) else str(x).split('|'))))
def save(d,name):
    (d if isinstance(d,pd.DataFrame) else pd.DataFrame(d)).to_csv(OUT/name,index=False,encoding='utf-8-sig')
def spherical(a,b):
    def rays(x):
        x=np.asarray(x,float);az=x[:,0]*2*np.pi/1024;el=(.5-x[:,1]/512)*np.pi
        return np.column_stack([-np.sin(az)*np.cos(el),np.sin(el),np.cos(az)*np.cos(el)])
    return np.rad2deg(np.arccos(np.clip(rays(a)@rays(b).T,-1,1)))
def grouped_summary(frame,keys,metrics):
    rows=[]
    for key,g in frame.groupby(keys,dropna=False):
        if not isinstance(key,tuple):key=(key,)
        for met in metrics:
            x=g[met].dropna()
            rows.append(dict(zip(keys,key),metric=met,registered_images=len(g),valid_images=len(x),valid_buildings=g.loc[g[met].notna(),'building'].nunique(),mean=x.mean(),mean_absolute=x.abs().mean(),median=x.median(),p10=x.quantile(.1),p90=x.quantile(.9),positive_images=int(x.gt(1e-10).sum()),negative_images=int(x.lt(-1e-10).sum()),zero_images=int(x.abs().le(1e-10).sum())))
    return pd.DataFrame(rows)

def main():
    e=pd.read_csv(OUT/'EVENTS_WITH_ENDPOINTS.csv.gz',low_memory=False)
    scalars=pd.read_csv(OUT/'SAVED_ENDPOINT_SCALARS.csv.gz',low_memory=False).set_index('team_key')
    pools={p['pool_id']:p for p in read(ROOT/'source/research/data/releases/v2.1/pools/INPUT_SNAPSHOT.json')['images']}
    for k in ['difficulty','reference_id','reference_version']:
        e[k]=e.pool_id.map(lambda p:pools[p]['meta'][k])
    metrics=['B8L2','D10','IoU3D100','S_bottom_deg','dir','Hmean','omission','extension','fusion_turn_n','fusion_short_turn_edges','fusion_redundancy_n','ref_node_recall_5','ref_edge_recall_5','geometry_area_h2','height_mean_h','centroid_x_h','centroid_z_h','boundary_loss','direction_loss','height_loss','selected_support_min','half_vote_nodes']
    computed={}
    for met in metrics:
        vals={a:e[a+'_team_key'].map(scalars[met]) for a in 'ABC'}
        ok=pd.concat(vals,axis=1).notna().all(axis=1)
        for pair in ['BA','CA','CB']:computed[met+'__delta_'+pair]=vals[pair[0]]-vals[pair[1]]
        within=(vals['B']-vals['A']).abs();ac=(vals['C']-vals['A']).abs();bc=(vals['C']-vals['B']).abs()
        for name,z in [('within',within),('cross_direct',ac),('cross_symmetric',(ac+bc)/2),('gap_A',ac-within),('gap_S',(ac+bc)/2-within)]:computed[met+'__'+name]=z.where(ok)
    e=pd.concat([e,pd.DataFrame(computed)],axis=1)
    metcols=list(computed)+['gap_A','gap_sym','CB','C_between_A_B','opposed_CB_loss_components','all_Q_at_least_90','all_Q_at_least_95','record_time_CA_pct_source_matched','record_time_BA_pct_source_matched','record_time_CB_pct_source_matched']
    im=aggregate(e,metcols);im['difficulty']=im.image.map(e.drop_duplicates('image').set_index('image').difficulty)
    save(e,'EVENTS_METRIC_SPECIFIC_SUPPORT.csv.gz');save(im,'IMAGES_METRIC_SPECIFIC_SUPPORT.csv.gz')
    summary=grouped_summary(im,['n'],metcols);save(summary,'ALL_METRICS_IMAGE_SUMMARY.csv')
    save(grouped_summary(im,['n','difficulty'],metcols),'DIFFICULTY_METRIC_SUMMARY.csv')
    building=im.groupby(['n','building'])[metcols].mean().reset_index();save(building,'BUILDING_RESULTS.csv')
    bs=grouped_summary(building,['n'],metcols).drop(columns=['valid_buildings']).rename(columns={c:c.replace('images','buildings') for c in ['registered_images','valid_images','positive_images','negative_images','zero_images']})
    save(bs,'BUILDING_EQUAL_SUMMARY.csv')
    events=pd.read_csv(OUT/'ALL_EXCEPTION_EVENTS_AND_20_7_CONTEXT.csv.gz',low_memory=False)
    tables=collections.defaultdict(list);extra=[];positions=[];rawrows=[];rosterrows=[]
    labels=pd.read_csv(ROOT/'source/research/data/releases/v2.1/final_classification_downstream/USED_FINAL_LOBO_LABELS.csv.gz');labels=labels[labels.method=='TARGET_DSTRUCT_K3']
    lm={(r.heldout_building,r.worker_id):r.class_id for r in labels.itertuples() if str(r.known).lower()=='true'}
    for pid,g in events.groupby('pool_id'):
        pool=pools[pid]
        for r in pool['records']:
            rawrows.append({'pool_id':pid,'image':pool['meta']['image'],'worker_id':r['worker_id'],'object_id':r['object_id'],'class_id':lm.get((pool['meta']['building'],r['worker_id'])),'B8L2':r.get('B8L2'),'D10':r.get('D10'),'source_time_seconds':r.get('source_time_seconds'),'time_source_kind':r.get('time_source_kind'),'full_points_json':json.dumps(r['points'],separators=(',',':')),'original_order_used':r.get('order_used'),'ring_confirmed':r.get('ring_confirmed')})
    for ev in events.to_dict('records'):
        pool=pools[ev['pool_id']];arms={a:read(OUT/'trace_endpoints'/(ev[a+'_team_key']+'.json.gz')) for a in 'ABC'}
        blocksets={b:set(ev[b].split('|')) for b in 'DXYZ'}
        for b in 'DXYZ':
            for worker in sorted(blocksets[b]):rosterrows.append({'event_id':ev['event_id'],'n':ev['n'],'image':ev['image'],'building':ev['building'],'block':b,'worker_id':worker,'fold_class':lm.get((ev['building'],worker)),'source_class':ev['source_class'],'target_class':ev['target_class']})
        for other,replace in [('C','Z'),('B','Y')]:
            case={'event':{**ev,'D_workers':ev['D'],'X_workers':ev['X'],'Z_workers':ev[replace]},'pool':pool,'reference':pool['reference'],'arms':{'A':arms['A'],'C':arms[other]}}
            diag=diagnose_case(case,median_pair,RT)
            for name,rows in diag.items():
                for row in rows:
                    if 'arm' in row:
                        if other=='B' and row['arm']=='A':continue
                        if other=='B':
                            row['arm']='B'
                            if row.get('block')=='Z':row['block']='Y'
                    else:
                        row['comparison']='A'+other
                        for key in list(row):
                            if key.startswith('C_'):row['other_'+key[2:]]=row.pop(key)
                    row.update(image=ev['image'],building=ev['building'],n=ev['n'],m=ev['m'])
                    tables[name].append(row)
        for arm in 'ABC':
            r=arms[arm];fs=r['full_state'];ref=np.array(pool['reference']['points_1024x512']).reshape(-1,2,2)
            groups=fs['identity_groups'];sel=[g for g in groups if g['selected']];support={g['feature_id']:{x['worker'] for x in g['members']} for g in sel}
            valid=[g for g in groups if g.get('center') is not None]
            refs=[]
            for ri in range(len(ref)):
                dist=spherical([g['center'][1] for g in valid],ref[ri:ri+1,1,:]).ravel()
                best=int(np.argmin(dist));gr=valid[best]
                positions.append({'event_id':ev['event_id'],'image':ev['image'],'n':ev['n'],'arm':arm,'reference_corner_1based':ri+1,'nearest_group':gr['feature_id'],'nearest_group_bottom_deg':dist[best],'nearest_group_support':gr['support'],'nearest_group_selected':gr['selected'],'minimum_support':fs['minimum_support'],'nearest_group_center_json':json.dumps(gr['center']),'reference_point_pair_json':json.dumps(ref[ri].tolist()),'diagnostic_only_not_new_quality_or_identity':True})
                refs.append((dist[best]<=5 and not gr['selected']))
            b='XYZ'['ABC'.index(arm)];threshold=fs['minimum_support']
            coverage=[x for x in fs['assignments'] if len([k for k in x['feature_ids'] if k in support])==len(support) and set(k for k in x['feature_ids'] if k in support)==set(support) and len(support)>=3]
            extra.append({'event_id':ev['event_id'],'image':ev['image'],'building':ev['building'],'n':ev['n'],'arm':arm,'score_status':r['score_status'],'minimum_support':threshold,'selected_groups':len(sel),'all_groups':len(groups),'unselected_groups':sum(not x['selected'] for x in groups),'exact_threshold_selected_groups':sum(x['support']==threshold for x in sel),'one_vote_below_groups':sum(x['support']==threshold-1 for x in groups),'replacement_alone_reaches_groups':sum(len(support[g['feature_id']]&blocksets[b])>=threshold for g in sel),'background_alone_reaches_groups':sum(len(support[g['feature_id']]&blocksets['D'])>=threshold for g in sel),'selected_disjoint_support_pairs':sum(not support[x]&support[y] for x,y in itertools.combinations(support,2)),'source_complete_projected_rings':len(coverage),'reference_near_group_below_threshold_n':sum(refs),'reference_corners':len(ref),'loss_boundary':r.get('boundary_loss'),'loss_direction':r.get('direction_loss'),'loss_height':r.get('height_loss'),'Q':r.get('B8L2'),'native_ring_reason':fs.get('ring_diagnostics',{}).get('reason'),'native_candidate_reason':fs.get('candidate',{}).get('reason'),'selected_unresolved_locations':sum(g.get('center') is None for g in sel)})
    for name,rows in tables.items():save(rows,'mechanism_tables/'+name+'.csv.gz')
    save(extra,'mechanism_tables/ARM_MECHANISM_FACTS.csv')
    save(positions,'mechanism_tables/REFERENCE_NEAR_GROUP_DIAGNOSTIC.csv')
    save(rawrows,'FULL_RAW_ANSWERS_AND_LOBO_LABELS.csv.gz');save(rosterrows,'EVENT_DXYZ_ROSTERS.csv.gz')
    facts=pd.DataFrame(extra);eventfacts=events[['event_id','n','building','image','pool_id','block_id','background_id']].copy()
    numeric=[x for x in facts.select_dtypes(include='number') if x!='n']
    for arm in 'ABC':
        v=facts[facts.arm==arm].set_index('event_id')
        for col in numeric:eventfacts[arm+'__'+col]=eventfacts.event_id.map(v[col])
    imgfacts=aggregate(eventfacts,[a+'__'+c for a in 'ABC' for c in numeric]);save(imgfacts,'IMAGE_TRACE_FACTS.csv')
    exc=pd.read_csv(OUT/'LATEST_HALF_ALL_EXCEPTION_IMAGES.csv')
    exc=exc.merge(imgfacts[imgfacts.n==14],on=['n','building','image'],validate='one_to_one',suffixes=('','_trace'))
    exc['difficulty']=exc.image.map(e.drop_duplicates('image').set_index('image').difficulty)
    save(exc,'ALL_36_EXCEPTION_NUMERIC_AND_MECHANISM_INDEX.csv')
    checks={'complete_events':len(events),'complete_arms':len(facts),'images':events.image.nunique(),'raw_answers':len(rawrows),'all_unselected_groups_retained':True,'all_reference_corners_diagnosed':len(positions),'table_rows':{k:len(v) for k,v in tables.items()},'mechanism_scope':'These are exact local trace facts. Full block cardinality is never substituted for per-group support. Disjoint supporters do not by themselves prove physically mutually exclusive walls. Nearest-reference diagnostics are not rescoring.'}
    write(OUT/'MECHANISM_ANALYSIS_CHECKS.json',checks);print(json.dumps(checks,ensure_ascii=False))

if __name__=='__main__':
    (OUT/'mechanism_tables').mkdir(exist_ok=True,parents=True)
    main()
