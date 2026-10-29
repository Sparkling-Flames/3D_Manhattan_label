#!/usr/bin/env python3
"""Label-specific real members/capacity only. Does not select a method by outcomes."""
import os,sys,json,gzip,itertools,hashlib
from pathlib import Path
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1];WORK=ROOT.parent
def save(d,name):
    p=ROOT/name;raw=d.to_csv(index=False).encode('utf-8-sig')
    if p.suffix=='.gz':raw=gzip.compress(raw,compresslevel=6,mtime=0)
    t=p.with_name(p.name+'.partial')
    with t.open('wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    t.replace(p)
def main():
    labels=pd.read_csv(ROOT/'MAIN45_LABELS_ALL_LOBO.csv.gz',low_memory=False)
    assert labels.method.nunique()==45
    assert not labels.duplicated(['method','heldout_building','worker_id']).any()
    hist=pd.read_csv(ROOT/'HISTORY_FEATURES_ALL_LOBO.csv.gz',low_memory=False)
    metrics=['m_all_images','m_all_buildings','m_all_targets','m_challenge_images','m_hard_images','m_easy_images',
        'm_all_turn_n','m_hard_turn_n','m_challenge_turn_n','m_opp_slope_turn_n','m_all_short_turn_edges','m_challenge_short_turn_edges',
        'm_all_near_straight_nodes_5deg','m_all_unmatched_ref_9','m_all_matched_bottom_bias_deg','m_all_matched_top_bias_deg',
        'm_all_log_area_ratio','m_all_log_height','m_all_B8L2','m_hard_B8L2','m_easy_B8L2','m_all_B8L2_p20','m_all_log_time',
        's_all_images','s_all_buildings','s_all_turn_n','s_all_B8L2','s_all_log_time']
    j=labels[labels.known].merge(hist[['worker_id','heldout_building']+metrics],on=['worker_id','heldout_building'],validate='many_to_one')
    centers=[]
    for (method,fold,cl),g in j.groupby(['method','heldout_building','class_id']):
        input_condition=g.input_conditions.iloc[0]
        if pd.isna(input_condition) and method.startswith('V3_'): input_condition='manual (condition-specific V3 history)'
        r={'method':method,'heldout_building':fold,'class_id':cl,'workers':len(g),'members':'|'.join(sorted(g.worker_id)),'class_input_conditions':input_condition,
           'center_source':'shared target-aware v2.1 history for interpretation only; label input remains original method','feature_support':'metric-specific available history; not zero-imputed'}
        r.update({k:g[k].mean() for k in metrics});centers.append(r)
    cen=pd.DataFrame(centers)
    save(cen,'CLASS_MEMBERS_COMMON_HISTORY_CENTERS_ALL_LOBO.csv.gz')
    save(cen[cen.heldout_building.eq('ALL')],'CLASS_MEMBERS_COMMON_HISTORY_CENTERS_ALL.csv')
    selected=['DSTRUCT_K3','TARGET_DSTRUCT_K3','OPPSTRUCT_K3','OPPGEOM_K3','OPPJOINT_K3','RFUSE_GEOM_K2','RFUSE_GEOMQ_K3','TARGET_RFUSE_GEOM_K2','TARGET_RFUSE_GEOMQ_K3','MSDGEOM_SCOPE_K4','Q_MEDIAN2']
    compact=['method','class_id','workers','members','class_input_conditions','m_all_turn_n','m_hard_turn_n','m_challenge_turn_n','m_all_near_straight_nodes_5deg','m_all_matched_bottom_bias_deg','m_all_matched_top_bias_deg','m_all_log_area_ratio','m_all_B8L2','m_all_B8L2_p20','m_all_log_time','s_all_turn_n','s_all_B8L2','s_all_log_time','center_source']
    save(cen[cen.heldout_building.eq('ALL')&cen.method.isin(selected)][compact],'CLASS_MEMBER_CENTER_EXTRACT_FOR_MAIN_REPORT.csv')
    records=pd.read_csv(WORK/'targets/RECORD_TARGET_LINKS_AND_ALL_SUPPORT_WEIGHTS.csv.gz',low_memory=False)
    pools=pd.read_csv(WORK/'targets/POOL_TARGET_CONDITIONS.csv')
    lmap={(m,b):g.set_index('worker_id').class_id.to_dict() for (m,b),g in labels[labels.known&labels.heldout_building.ne('ALL')].groupby(['method','heldout_building'])}
    crows=[];dirs=[]
    for r in pools.itertuples():
        ws=set(records.loc[records.pool_id.eq(r.pool_id),'worker'])
        assert len(ws)==r.pool_n
        for method in sorted(labels.method.unique()):
            lm=lmap.get((method,r.building),{});groups={}
            for w in ws:groups.setdefault(lm.get(w,'unknown'),[]).append(w)
            for cl,members in groups.items():
                crows.append({'method':method,'pool_id':r.pool_id,'image_id':r.image_id,'image':r.image,'building':r.building,'condition':r.condition,'scope':r.scope,'layer':r.layer,'class_id':cl,'available_members':len(members),'members':'|'.join(sorted(members)),'pool_n':len(ws),'heldout_building':r.building})
            for src,tgt in itertools.permutations(sorted(set(groups)-{'unknown'}),2):
                S=len(groups[src]);T=len(groups[tgt]);N=len(ws);mm=min(S//2,T,N//3)
                row={'method':method,'pool_id':r.pool_id,'image':r.image,'image_id':r.image_id,'building':r.building,'condition':r.condition,'scope':r.scope,'layer':r.layer,'source_class':src,'target_class':tgt,'source_capacity':S,'target_capacity':T,'pool_n':N,'unknown_background_capacity':len(groups.get('unknown',[])),
                'max_strict_m_any_n':mm,'strict_n_min_at_max_m':mm if mm else np.nan,'strict_n_max_at_max_m':N-2*mm if mm else np.nan,
                'full_target_block_strict_possible':S>=2*T and N>=3*T,'full_target_block_m':T,'strict_n_max_for_full_target':N-2*T if S>=2*T and N>=3*T else np.nan,
                'direct_AC_max_m_any_n':min(S,T,N//2),'strict_requirement':'N>=n+2m;S>=2m;T>=m;X/Y/Z disjoint;D uses remaining actual eligible people',
                'capacity_only_not_computed_experiments':True}
                for m in [2,4,6,7,8,10,12]:
                    row[f'strict_n_max_m{m}']=N-2*m if m<=mm else np.nan
                for n in [6,8,10,12,14,16,18,20,22,24,26,28,30]:
                    row[f'strict_m_max_n{n}']=max(0,min(S//2,T,(N-n)//2,n))
                dirs.append(row)
    cap=pd.DataFrame(crows);d=pd.DataFrame(dirs)
    save(cap,'CLASS_CAPACITY_BY_CURRENT_POOL.csv.gz')
    save(d,'STRICT_DIRECTION_CAPACITY_BY_CURRENT_POOL.csv.gz')
    out=[]
    for (method,condition,scope,layer),g in d.groupby(['method','condition','scope','layer']):
        r={'method':method,'condition':condition,'scope':scope,'layer':layer,'pool_count':g.pool_id.nunique(),'building_count':g.building.nunique(),'directed_class_pairs':len(g),'max_strict_m':g.max_strict_m_any_n.max(),
        'pools_any_strict':g[g.max_strict_m_any_n.ge(1)].pool_id.nunique(),'pools_full_target_block':g[g.full_target_block_strict_possible].pool_id.nunique()}
        for m in [2,4,6,7,8,10,12]:
            z=g[g.max_strict_m_any_n.ge(m)];r[f'pools_possible_m{m}']=z.pool_id.nunique();r[f'buildings_possible_m{m}']=z.building.nunique()
        for n,m in [(10,7),(12,8),(18,7),(20,6),(24,4),(26,4),(28,3),(30,2)]:
            r[f'pools_n{n}_m{m}']=g[(g.source_capacity>=2*m)&(g.target_capacity>=m)&(g.pool_n>=n+2*m)].pool_id.nunique()
        out.append(r)
    save(pd.DataFrame(out),'METHOD_CAPACITY_SCOPE_SUMMARY.csv')
    (ROOT/'CAPACITY_INTERPRETATION.json').write_text(json.dumps({'methods':45,'actual_pools':int(pools.pool_id.nunique()),'class_capacity_rows':len(cap),'direction_capacity_rows':len(d),'source_labels':'MAIN45: BASE24+NEW13+TARGET_RFUSE4+V3_4','source_labels_sha256':hashlib.sha256((ROOT/'MAIN45_LABELS_ALL_LOBO.csv.gz').read_bytes()).hexdigest(),'data':'v2.1','background_unknowns':'may be used as shared D; never source/target labeled block','strict_space_math':'for chosen m, n in[m,N-2m], provided S>=2m,T>=m; theoretical only, actual experiment grid separately registered','not_claimed':'This table is legal capacity, not a record of completed fusion or exhaustive member sampling.'},ensure_ascii=False,indent=2)+'\n')
    print('saved',len(cen),'centers',len(cap),'class capacities',len(d),'directions')
if __name__=='__main__':main()

