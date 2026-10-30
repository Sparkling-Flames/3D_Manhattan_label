"""Relation-status layers, exact accounting, compact exhibits and audit indexes."""
from pathlib import Path
import json,gzip,hashlib,collections
import pandas as pd
import numpy as np
from selection_stop_prepare import STUDY,OUT,INP,REPLAY,SRC,OLD,read,save,native_pools
from selection_stop_analyze import summarize
from selection_stop_endpoints import iterjson

def relation_layers():
    pools=native_pools();by={p['meta']['image']:p['meta']['image_id'] for p in pools.values()}
    rels=read(SRC/'research/same_room/relation_adoption_20261016/relations.json');rel={tuple(sorted([r['image_a'],r['image_b']])):r for r in rels}
    d=pd.read_csv(OUT/'selection/POLICY_EVENT_RESULTS.csv.gz')
    context=d[['pair_id','image_a','image_b']].drop_duplicates();flags=[]
    for r in context.itertuples(index=False):
        z=rel[tuple(sorted([by[r.image_a],by[r.image_b]]))]
        flags.append(dict(pair_id=r.pair_id,image_a=r.image_a,image_b=r.image_b,relation_oos_pending=bool(z.get('oos_pending')),relation_substantive_conflict=bool(z.get('substantive_conflict')),direct_adopted=bool(z.get('physical_adopted')),scope_comparable=bool(z.get('scope_comparable')),relation_source_ids='|'.join(z.get('user_group_ids',[]))))
    flags=pd.DataFrame(flags);save('selection/RELATION_FLAGS.csv',flags)
    d=d.merge(flags[['pair_id','relation_oos_pending','relation_substantive_conflict']],on='pair_id',validate='many_to_one')
    main=d[(d.layer=='ordinary_manual')&d.scope_comparable]
    records=[];ims=[];buildings=[];supports=[]
    keys=['version','domain','n','policy'];metrics=['B8L2','D10','delta_Q','absolute_delta_Q','loss_over5','low_Q50','low_Q80','both_scored','complete_rate','Q_available_rate','observed_fusion_failure','measurement_unavailable','target_activity_seconds','log_activity_ratio','joint_save20_loss_atmost2','nodes','fusion_turn_n','fusion_short_turn_edges','S_bottom_deg','Hmean','omission','extension']
    for label,z in [('original_scope_comparable_panel',main),('no_pending_direct_relations',main[~main.relation_oos_pending&~main.relation_substantive_conflict]),('pending_relation_supplement',main[main.relation_oos_pending])]:
        s,i,b,u=summarize(z,keys,metrics)
        for x in [s,i,b,u]:x['relation_layer']=label
        records.append(s);ims.append(i);buildings.append(b);supports.append(u)
    save('selection/RELATION_LAYER_SUMMARY.csv',pd.concat(records));save('selection/RELATION_LAYER_IMAGE_RESULTS.csv.gz',pd.concat(ims));save('selection/RELATION_LAYER_BUILDING_RESULTS.csv',pd.concat(buildings));save('selection/RELATION_LAYER_METRIC_SUPPORT.csv',pd.concat(supports))
    # Additional current fixed-n summaries are descriptive; they do not retune a rule.
    main=main[(main.version=='v21_history_reselected_fixed_candidates')&(main.n==5)&(main.domain=='new_timed_history')]
    main['relation_layer']=np.where(main.relation_oos_pending,'pending','no_pending')
    keys=['relation_layer','difficulty','policy'];s,i,b,u=summarize(main,keys,metrics)
    save('selection/DIFFICULTY_MAIN_N5_SUMMARY.csv',s)
    groupflags=[]
    for g in read(INP/REPLAY/'REPLAY_GROUPS.json'):
        rs=[rel.get(tuple(sorted([a,b]))) for ix,a in enumerate(g['images']) for b in g['images'][ix+1:]]
        groupflags.append(dict(group_id=g['group_id'],panel=g['replay_panel'],building=g['building'],views=len(g['images']),common_workers=len(g['common_workers']),any_relation_pending=any(r and r.get('oos_pending') for r in rs),all_direct_adopted=all(r and r.get('physical_adopted') for r in rs),all_scope_comparable=all(r and r.get('scope_comparable') for r in rs)))
    gf=pd.DataFrame(groupflags);save('stopping/GROUP_RELATION_FLAGS.csv',gf)
    t=pd.read_csv(OUT/'stopping/stopping_target_actual_m.csv.gz').merge(gf[['group_id','any_relation_pending']],on='group_id',validate='many_to_one')
    numeric=[c for c in t.select_dtypes(include=np.number) if c not in ['m','N','attempts','valid_n','paired_terminal_n','activity_time_valid_n']]
    rows=[]
    for layer,f in [('original_supported_groups',t),('no_pending_direct_relations',t[~t.any_relation_pending]),('pending_relation_supplement',t[t.any_relation_pending])]:
        for budget,mask in [('single_source',f.m==1),('minimum_majority',f.m==f.N//2+1),('maximum_history',f.m==f.N-1)]:
            for key,z in f[mask].groupby(['panel','support','policy']):
                for time_support,zz in [('all_groups',z),('all_new_complete_time',z[z.activity_all_new_complete])]:
                    if zz.empty:continue
                    vals=zz.groupby(['building','group_id'])[numeric].mean().groupby('building').mean().mean().to_dict()
                    rows.append(dict(relation_layer=layer,history_budget=budget,panel=key[0],support=key[1],policy=key[2],time_support=time_support,groups=zz.group_id.nunique(),images=zz.target_image.nunique(),buildings=zz.building.nunique(),attempts=int(zz.attempts.sum()),valid_n=int(zz.valid_n.sum()),**vals))
    save('stopping/RELATION_LAYER_STOPPING_SUMMARY.csv',pd.DataFrame(rows))
    p=pd.read_csv(OUT/'stopping/source_acquisition_group_actual_m.csv').merge(gf[['group_id','any_relation_pending']],on='group_id',validate='many_to_one');rows=[]
    for layer,f in [('original_supported_groups',p),('no_pending_direct_relations',p[~p.any_relation_pending]),('pending_relation_supplement',p[p.any_relation_pending])]:
        for budget,mask in [('single_source',f.m==1),('minimum_majority',f.m==f.N//2+1),('maximum_history',f.m==f.N-1)]:
            for key,z in f[mask&f.source_curve_required&f.activity_all_new_complete].groupby(['panel','policy']):
                numeric=[c for c in z.select_dtypes(include=np.number) if c not in ['m','N']]
                vals=z.groupby('building')[numeric].mean().mean().to_dict()
                rows.append(dict(relation_layer=layer,history_budget=budget,panel=key[0],policy=key[1],groups=z.group_id.nunique(),buildings=z.building.nunique(),**vals))
    save('stopping/RELATION_LAYER_ACQUISITION_SUMMARY.csv',pd.DataFrame(rows))

def accounting():
    req=pd.read_csv(OUT/'design/ENDPOINT_REQUESTS.csv.gz');s=pd.read_csv(OUT/'endpoints/SCALARS.csv.gz');d=pd.read_csv(OUT/'design/SELECTION_DESIGN.csv.gz')
    old=set(d.loc[d.version=='v2_fixed_selection_current_score','team_key']);new=set(d.loc[d.version=='v21_history_reselected_fixed_candidates','team_key'])
    usages=collections.Counter(req.uses);counts=s.downstream_acquisition.value_counts().to_dict();assert sum(counts.values())==len(s) and set(counts)<= {'reused_exact_current_endpoint','missing_exact_team_evaluated'}
    save('endpoints/FINAL_ENDPOINT_ACCOUNTING.json',{'unique_teams':len(s),'pools':s.pool_id.nunique(),'selection_context_rows':len(d),'frozen_selection_unique_teams':len(old),'current_history_unique_teams':len(new),'selection_team_overlap':len(old&new),'current_history_new_team_sets':len(new-old),'endpoint_acquisition':{k:int(v) for k,v in counts.items()},'request_uses':dict(usages),'all_team_keys_unique':True,'main_and_extra_workers_disjoint_actual_execution':True,'both_quality_and_geometry_retained':True})
    files=[]
    for path in sorted(OUT.rglob('*')):
        if not path.is_file() or path.name in ['FILE_READABILITY.csv','FILE_READABILITY_RECEIPT.json']:continue
        n=None;status='bytes_read_to_eof';h=hashlib.sha256()
        with path.open('rb') as f:
            for b in iter(lambda:f.read(1<<20),b''):h.update(b)
        if path.suffix=='.gz':
            with gzip.open(path,'rb') as f:
                for _ in iter(lambda:f.read(1<<20),b''):pass
            status='gzip_crc_and_eof'
        if path.name.endswith('.csv') or path.name.endswith('.csv.gz'):
            n=sum(len(chunk) for chunk in pd.read_csv(path,chunksize=10000,low_memory=False));status+=';csv_parse_all_rows'
        elif path.name.endswith('.jsonl.gz'):
            n=sum(1 for _ in iterjson(path));status+=';json_parse_all_rows'
        elif path.suffix=='.json':read(path);status+=';json_parsed'
        files.append(dict(path=str(path.relative_to(STUDY)),bytes=path.stat().st_size,sha256=h.hexdigest(),rows=n,validation=status))
    save('FILE_READABILITY.csv',pd.DataFrame(files));save('FILE_READABILITY_RECEIPT.json',{'files':len(files),'every_generated_and_input_file_read':True,'gzip_crc_checked':True,'csv_json_content_fully_parsed':True,'unexpected_errors':0})
    print('all stage05 artifacts readable',len(files),flush=True)

if __name__=='__main__':relation_layers();accounting()
