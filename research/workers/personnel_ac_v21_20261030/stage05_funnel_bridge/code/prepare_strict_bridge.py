"""Normalize completed strict ABC for same-condition direct-AC comparisons.

No endpoint, clustering, qualification audit, or scoring is rerun. The old
integrated source already contains every completed stage03 ABC event.
"""
from pathlib import Path
from collections import defaultdict
import csv,gzip,hashlib,json
import numpy as np
import pandas as pd

OUT=Path(__file__).resolve().parents[1];BASE=OUT.parent;WORK=BASE.parent
CAP=BASE/'stage01_capacity'
COMMIT='ec0973ad46fcfa64d3cdbedfeeef1fee180c4cff'
OLD=WORK/'HOHONET_v21_reaudit_20261029/stage02_comparison/abc_integrated/COMBINED_UNION_EVENTS_WITH_ROLES.csv.gz'
COMPLETED=WORK/'HOHONET_v21_reaudit_20261029/stage03_completed_abc/EVENT_METRICS.csv.gz'
NEW=OUT/'inputs/STRICT_LARGE_EVENT_METRICS.csv.gz'
METHODS=['TARGET_DSTRUCT_K3','TARGET_DSTRUCT_K2','V21_DSTRUCT_RAW3_K3','OPPJOINT_K3','OPPJOINT_K4','RFUSE_GEOM_K2','OPPSTRUCT_K3']
SCALAR_METRICS=['B8L2','D10','IoU3D100','S_bottom_deg','omission','extension','fusion_turn_n',
    'fusion_short_turn_edges','fusion_redundancy_n','geometry_area_h2','height_mean_h',
    'matched_ref_top_abs_deg','matched_ref_bottom_abs_deg','matched_ref_horizontal_abs_deg',
    'boundary_loss','direction_loss','height_loss']
PAIR_METRICS=['geometry_pair_angle','geometry_bev_distance','geometry_centroid_distance','geometry_log_area_distance']
IDENTITY=['event_id','pool_id','image','building','condition','layer','scope','method','heldout_building',
    'source_class','target_class','n','m','pool_n','background_id','block_id','A_team_key','B_team_key','C_team_key',
    'A_members','B_members','C_members','D','X','Y','Z','reference_id','reference_version','analysis_scope','design','source_stage']

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def enc(x):return json.dumps(x,sort_keys=True,separators=(',',':'))
def digest(x):return hashlib.sha256(enc(x).encode()).hexdigest()
def save(d,name):
    p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True)
    tmp=p.with_name(p.name+'.partial')
    with (gzip.open(tmp,'wt',encoding='utf-8-sig',newline='') if p.name.endswith('.gz') else open(tmp,'w',encoding='utf-8-sig',newline='')) as f:
        d.to_csv(f,index=False)
    tmp.replace(p)

def load(path,which):
    header=pd.read_csv(path,nrows=0).columns.tolist()
    wanted=IDENTITY+['ABC_scored','A_failed','B_failed','C_failed']
    wanted += [metric+'_'+leg for metric in SCALAR_METRICS for leg in ['BA','CA','CB']]
    wanted += [metric+'_'+leg for metric in PAIR_METRICS for leg in ['AB','AC','BC']]
    wanted += ['record_time_'+leg+'_pct_source_matched' for leg in ['BA','CA','CB']]
    d=pd.read_csv(path,usecols=[c for c in dict.fromkeys(wanted) if c in header],low_memory=False)
    d=d[d.method.isin(METHODS)&d.m.isin([7,8] if which=='prior_m7_m8' else [9,10])].copy()
    d['strict_source_family']=which
    return d

def main():
    pools={p['pool_id']:p for p in json.loads((CAP/'SCORE_BLIND_POOL_INPUTS.json').read_text())['pools']}
    ordinary={pid for pid,p in pools.items() if p['meta']['condition']=='manual' and p['meta']['layer']=='ordinary_manual'}
    compact_old=OUT/'inputs/PRIOR_STRICT_M7_M8_INPUT_SUBSET.csv.gz'
    compact_new=OUT/'inputs/LATEST_STRICT_M9_M10_INPUT_SUBSET.csv.gz'
    old_path=OLD if OLD.exists() else compact_old
    new_path=compact_new if compact_new.exists() else NEW
    raw_old=load(old_path,'prior_m7_m8');raw_new=load(new_path,'latest_m9_m10')
    if OLD.exists() and COMPLETED.exists():
        old_ids=set(pd.read_csv(OLD,usecols=['event_id']).event_id)
        completed_ids=set(pd.read_csv(COMPLETED,usecols=['event_id']).event_id)
        assert completed_ids<=old_ids
        overlap_counts={'old_integrated_event_rows':len(old_ids),'completed_stage03_rows':len(completed_ids),'completed_stage03_already_in_integrated':len(completed_ids&old_ids)}
    else:
        # Minimal reproduction retains the prior identity-overlap proof;
        # it does not need all unrelated old experiment rows.
        provenance=json.loads((OUT/'inputs/COMPACT_STRICT_INPUT_PROVENANCE.json').read_text())
        overlap_counts=provenance['previous_full_identity_overlap_counts']
    raw_old=raw_old[raw_old.pool_id.isin(ordinary)];raw_new=raw_new[raw_new.pool_id.isin(ordinary)]
    # Compact selected-column subset, not a duplicate of the 251-column source.
    save(raw_old,'inputs/PRIOR_STRICT_M7_M8_INPUT_SUBSET.csv.gz')
    combined=pd.concat([raw_old,raw_new],ignore_index=True)
    assert not combined.event_id.duplicated().any()
    roles=pd.read_csv(CAP/'FROZEN_ROLE_PARENT_MAP_ALL_LOBO.csv').fillna('')
    role={(r.method,r.heldout_building,r.class_id):r for r in roles.itertuples()}
    pair_rows=[];normalized=[];seen_triples={};duplicate_triples=[]
    for r in combined.to_dict('records'):
        pid=r['pool_id'];method=r['method'];p=pools[pid];meta=p['meta'];b=meta['building']
        assert r['building']==b and r['heldout_building']==b
        for f in ['reference_id','reference_version']:
            if pd.notna(r.get(f)) and str(r[f]):assert str(r[f])==str(meta[f]),(r['event_id'],f)
        s,t=r['source_class'],r['target_class'];sr,tr=role[method,b,s],role[method,b,t]
        sk=(float(sr.primary_role_rank),s);tk=(float(tr.primary_role_rank),t)
        sign=1 if sk<tk else -1
        canonical_s,canonical_t=(s,t) if sign==1 else (t,s)
        a,bkey,c=r['A_team_key'],r['B_team_key'],r['C_team_key']
        assert pd.notna(a) and pd.notna(bkey) and pd.notna(c) and len({a,bkey,c})==3
        triple=(pid,method,int(r['n']),int(r['m']),s,t,*sorted([a,bkey]),c)
        if triple in seen_triples:
            duplicate_triples.append({'event_id':r['event_id'],'kept_event_id':seen_triples[triple],'reason':'same_physical_ABC_with_possible_XY_reverse'})
            continue
        seen_triples[triple]=r['event_id']
        row={k:r.get(k) for k in IDENTITY if k in combined}
        row.update(strict_source_family=r['strict_source_family'],scope=p['scope'],reference_id=meta['reference_id'],reference_version=meta['reference_version'],
            source_role_axis=sr.primary_role_axis,source_role_rank=float(sr.primary_role_rank),target_role_rank=float(tr.primary_role_rank),
            source_parent_class=sr.parent_class,target_parent_class=tr.parent_class,
            strict_role_direction=f'{int(sr.primary_role_rank)}/{int(sr.k)}->{int(tr.primary_role_rank)}/{int(tr.k)}',
            canonical_source_class=canonical_s,canonical_target_class=canonical_t,strict_to_canonical_sign=sign,
            same_class_B_control_class=s,same_class_B_control_role_rank=float(sr.primary_role_rank))
        if not pd.notna(row.get('block_id')) or not str(row.get('block_id')):row['block_id']=r['event_id']
        for metric in SCALAR_METRICS:
            ba,ca,cb=[pd.to_numeric(r.get(metric+'_'+leg),errors='coerce') for leg in ['BA','CA','CB']]
            triple_ok=all(pd.notna(v) and np.isfinite(v) for v in [ba,ca,cb])
            row[metric+'_BA']=ba;row[metric+'_strict_CA']=ca;row[metric+'_strict_CB']=cb
            row[metric+'_canonical_CA']=sign*ca;row[metric+'_canonical_CB']=sign*cb
            row[metric+'_abs_CA']=abs(ca) if pd.notna(ca) else np.nan
            row[metric+'_ABC_valid']=triple_ok
            row[metric+'_within_AB']=abs(ba) if triple_ok else np.nan
            row[metric+'_G_A']=abs(ca)-abs(ba) if triple_ok else np.nan
            row[metric+'_G_S']=(abs(ca)+abs(cb))/2-abs(ba) if triple_ok else np.nan
        for metric in PAIR_METRICS:
            ab,ac,bc=[pd.to_numeric(r.get(metric+'_'+leg),errors='coerce') for leg in ['AB','AC','BC']]
            triple_ok=all(pd.notna(v) and np.isfinite(v) for v in [ab,ac,bc])
            row[metric+'_AB']=ab;row[metric+'_AC']=ac;row[metric+'_BC']=bc;row[metric+'_ABC_valid']=triple_ok
            row[metric+'_G_A']=ac-ab if triple_ok else np.nan
            row[metric+'_G_S']=(ac+bc)/2-ab if triple_ok else np.nan
        row['record_time_strict_CA_pct_source_matched']=r.get('record_time_CA_pct_source_matched',np.nan)
        normalized.append(row)
        for leg,baseline in [('AC',a),('BC',bkey)]:
            physical=digest([pid,sorted([baseline,c])])[:24]
            pair_rows.append(dict(strict_event_id=r['event_id'],strict_source_family=r['strict_source_family'],pool_id=pid,method=method,
                n=int(r['n']),m=int(r['m']),source_class=s,target_class=t,strict_role_direction=row['strict_role_direction'],
                pair_leg=leg,baseline_team_key=baseline,target_team_key=c,physical_pair_id=physical,
                canonical_source_class=canonical_s,canonical_target_class=canonical_t,strict_to_canonical_sign=sign,
                same_class_B_control_class=s,reference_id=meta['reference_id'],reference_version=meta['reference_version']))
    d=pd.DataFrame(normalized);pairs=pd.DataFrame(pair_rows)
    save(d,'STRICT_NORMALIZED_EVENTS.csv.gz');save(pairs,'STRICT_EXACT_AC_BC_PAIR_INDEX.csv.gz')
    if duplicate_triples:save(pd.DataFrame(duplicate_triples),'STRICT_PHYSICAL_TRIPLE_DUPLICATES.csv')
    cellkeys=['strict_source_family','pool_id','image','building','scope','method','n','m','source_class','target_class',
        'canonical_source_class','canonical_target_class','strict_to_canonical_sign','strict_role_direction']
    result=[]
    for key,g in d.groupby(cellkeys,dropna=False,sort=True):
        base=dict(zip(cellkeys,key));base.update(registered_ABC_events=len(g),registered_blocks=g.block_id.nunique())
        for metric in SCALAR_METRICS+PAIR_METRICS:
            if metric in SCALAR_METRICS:
                fields={'strict_signed_CA':metric+'_strict_CA','canonical_signed_CA':metric+'_canonical_CA','absolute_CA':metric+'_abs_CA',
                        'within_AB':metric+'_within_AB','G_A':metric+'_G_A','G_S':metric+'_G_S'}
            else:fields={'absolute_CA':metric+'_AC','within_AB':metric+'_AB','G_A':metric+'_G_A','G_S':metric+'_G_S'}
            rr=dict(base,metric=metric)
            for label,col in fields.items():
                bg=g.groupby('block_id')[col].mean();values=g[col].dropna()
                rr[label+'_mean']=bg.mean();rr[label+'_valid_events']=len(values);rr[label+'_valid_blocks']=int(bg.notna().sum())
                rr[label+'_event_p10']=values.quantile(.1) if len(values) else np.nan
            rr['ABC_valid_events']=int(g[metric+'_ABC_valid'].sum());result.append(rr)
    save(pd.DataFrame(result),'STRICT_IMAGE_CONDITION_METRICS.csv.gz')
    pair_lookup=defaultdict(list)
    for r in pair_rows:pair_lookup[(r['method'],r['physical_pair_id'])].append(r)
    new_path=BASE/'stage01_registered/AC_EVENTS.csv.gz';matches=[];match_new=set();match_physical=set()
    if new_path.exists():
        with gzip.open(new_path,'rt',encoding='utf-8-sig',newline='') as f:
            for e in csv.DictReader(f):
                for old in pair_lookup.get((e['method'],e['physical_pair_id']),[]):
                    assert e['pool_id']==old['pool_id'] and int(float(e['n']))==old['n'] and int(float(e['m']))==old['m']
                    matches.append(dict(new_event_id=e['event_id'],new_design_family=e['design_family'],**old))
                    match_new.add(e['event_id']);match_physical.add(e['physical_pair_id'])
        if matches:save(pd.DataFrame(matches),'NEW_AC_EXACT_STRICT_PAIR_OVERLAPS.csv.gz')
    receipt={'status':'completed_existing_results_normalization_only','source_commit':COMMIT,
        **overlap_counts,
        'selected_prior_m7_m8_rows':len(raw_old),'selected_latest_m9_m10_rows':len(raw_new),
        'normalized_strict_events':len(d),'physical_ABC_duplicates_removed':len(duplicate_triples),
        'strict_AC_BC_index_rows':len(pairs),'strict_unique_physical_AC_BC_pairs':int(pairs.physical_pair_id.nunique()),
        'new_registered_method_events_matching_strict_pair':len(match_new),'new_registered_physical_pairs_matching_strict_pair':len(match_physical),
        'new_to_strict_link_rows':len(matches),'new_fusions':0,'new_scores':0,'new_labels':0,
        'new_AC_does_not_estimate_cross_minus_within':True,'current_inputs':[
          {'path':str(p.relative_to(WORK)),'sha256':sha(p)} for p in [old_path,new_path,CAP/'FROZEN_ROLE_PARENT_MAP_ALL_LOBO.csv']],
        'aggregation':'Average available backgrounds within each exact block, then equal-weight blocks within pool/method/direction/n/m; retain metric-specific valid denominators.'}
    (OUT/'STRICT_PREPARATION_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(receipt,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
