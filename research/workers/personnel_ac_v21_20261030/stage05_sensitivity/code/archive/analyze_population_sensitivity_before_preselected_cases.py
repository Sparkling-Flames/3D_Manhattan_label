"""Saved-endpoint sensitivity; no fusion, scoring, class fitting or team selection.

Inputs are frozen links, pool metric shards and frozen role/member maps. Processing
is per pool. Signed scalar differences, symmetric geometry distances, percentages
and statuses have separate orientation rules; missing remains missing.
"""
from __future__ import annotations
import argparse, csv, gzip, hashlib, itertools, json, math, os, time
from collections import Counter, defaultdict
from pathlib import Path
for name in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS']:
    os.environ[name]='1'
import numpy as np
import pandas as pd

METRICS=['B8L2_CA','D10_CA','IoU3D100_CA','S_bottom_deg_CA','dir_CA','Hmean_CA',
 'omission_CA','extension_CA','fusion_turn_n_CA','fusion_short_turn_edges_CA','nodes_CA',
 'ref_node_recall_5_CA','ref_edge_recall_5_CA','geometry_area_h2_pct_CA','height_mean_h_pct_CA',
 'centroid_x_h_CA','centroid_z_h_CA','geometry_bev_distance_AC','geometry_centroid_distance_AC',
 'record_time_CA_pct_source_matched','record_time_CA_seconds_single_source',
 'record_time_per_member_CA_pct_single_source','Q_missing_risk_change_CA',
 'fusion_failure_observed_risk_change_CA','output_not_complete_risk_change_CA']
ARM_METRICS=['B8L2','D10','fusion_turn_n','nodes','Q_missing','fusion_failure_observed','output_not_complete']
META=['event_id','physical_pair_id','pool_id','method','scope','condition','layer','image','building',
 'source_class','target_class','source_role_rank','target_role_rank','role_axis','n','m','n_A','n_C',
 'm_X','m_Z','D_n','A_team_key','C_team_key','A_workers','C_workers','D_workers','X_workers','Z_workers',
 'A_class_counts','C_class_counts','D_class_counts','whole_source','whole_target',
 'source_class_available_n','target_class_available_n','mv50_threshold_A','mv50_threshold_C',
 'A_output_state','C_output_state','actual_A_minimum_support','actual_C_minimum_support']
LINK=['event_id','pool_id','method','design_family','input_orientation_sign','cell_id','n','m',
 'block_id','background_id','background_profile','member_rep','background_rep','sample_batch',
 'sampled_XZ_blocks','possible_XZ_blocks','XZ_enumerated','possible_D_per_XZ','nested_background_path_id',
 'anchor_A_path_id','max_m_on_path','parent_contrast_id','decomposition_leg','fixed_D_panel_id',
 'possible_XZ_given_D','A_alliance','C_alliance','coalition_comparison_type','unknown_background_included',
 'input_A_classes','input_C_classes','unknown_background','all_other_classes_in_D',
 'bridge_strict_to_canonical_sign']
COMMON=['pool_id','image','building','scope','condition','layer','method']

def finite(v):
    try:return math.isfinite(float(v))
    except (TypeError,ValueError):return False

def number(v):return float(v) if finite(v) else np.nan
def text(v):return '' if v is None or (not isinstance(v,(list,dict)) and pd.isna(v)) else str(v)
def pipe(v):return text(v).split('|') if text(v) else []
def enc(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=lambda x:x.item() if hasattr(x,'item') else str(x))
def digest(v):return hashlib.sha256(enc(v).encode()).hexdigest()

def save(df,path):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_name(path.name+'.partial')
    with gzip.open(tmp,'wt',encoding='utf-8-sig',newline='',compresslevel=5) as f:df.to_csv(f,index=False)
    tmp.replace(path)

def kind(metric):
    if metric.endswith('_AC'):return 'symmetric_distance'
    if 'pct' in metric:return 'percentage'
    if '_ratio_' in metric and '_log_ratio_' not in metric:return 'ratio'
    return 'additive_difference'

def oriented(v,sign,metric):
    if not finite(v):return np.nan
    v=float(v);sign=int(sign)
    if sign==1 or kind(metric)=='symmetric_distance':return v
    if kind(metric)=='percentage':return 100*(1/(1+v/100)-1) if 1+v/100>0 else np.nan
    if kind(metric)=='ratio':return 1/v if v>0 else np.nan
    return -v

def meta(row):return {k:row.get(k,'') for k in COMMON}

def role_direction(row):
    s,t=row.get('source_role_rank'),row.get('target_role_rank')
    return f'{int(float(s))}->{int(float(t))}' if finite(s) and finite(t) else text(row.get('source_class'))+'->'+text(row.get('target_class'))

def merged(d,links):
    d=d.drop(columns=['design_family'],errors='ignore')
    rename={c:'link_'+c for c in links if c!='event_id' and c in d}
    x=d.merge(links.rename(columns=rename),on='event_id',how='inner',validate='one_to_many')
    return x

def value(row,field,default=''):
    key='link_'+field if 'link_'+field in row else field
    result=row.get(key,default)
    return default if (not isinstance(result,(list,dict)) and pd.isna(result)) else result

def input_view(row,sign_override=None):
    sign=int(float(value(row,'input_orientation_sign',1))) if sign_override is None else int(sign_override)
    out={m:oriented(row.get(m),sign,m) for m in METRICS}
    out.update(input_sign=sign,input_A_team_key=row['A_team_key'] if sign==1 else row['C_team_key'],
       input_C_team_key=row['C_team_key'] if sign==1 else row['A_team_key'],
       input_n_A=row['n_A'] if sign==1 else row['n_C'],input_n_C=row['n_C'] if sign==1 else row['n_A'],
       input_A_class_counts=row.get('A_class_counts') if sign==1 else row.get('C_class_counts'),
       input_C_class_counts=row.get('C_class_counts') if sign==1 else row.get('A_class_counts'))
    rd=role_direction(row)
    out['input_role_direction']=rd if sign==1 else '->'.join(reversed(rd.split('->')))
    for arm,opposite in [('A','C'),('C','A')]:
        for m in ARM_METRICS:out['input_'+arm+'_'+m]=number(row.get((arm if sign==1 else opposite)+'_'+m))
    return out

def finite_array(series):
    x=pd.to_numeric(series,errors='coerce').to_numpy(dtype=float)
    return x[np.isfinite(x)]

def summarize_values(row,series,prefix):
    x=finite_array(series);n=len(x)
    row[prefix+'__valid']=n
    for name,val in [('mean',x.mean() if n else np.nan),('sd',x.std(ddof=1) if n>1 else np.nan),
      ('min',x.min() if n else np.nan),('max',x.max() if n else np.nan),
      ('span',x.max()-x.min() if n else np.nan),('mean_abs',np.abs(x).mean() if n else np.nan),
      ('positive_fraction',np.mean(x>1e-9) if n else np.nan),
      ('negative_fraction',np.mean(x< -1e-9) if n else np.nan),
      ('sign_flip',float(np.any(x>1e-9) and np.any(x< -1e-9)) if n>1 else np.nan)]:row[prefix+'__'+name]=float(val)

def member_panels(d,links):
    result=[]
    eq=links[links.design_family.isin(['A_equal_AC','B_equal_whole_class','S_equal_whole_class']) & links.background_profile.eq('neutral_members_0')]
    x=merged(d,eq).drop_duplicates('event_id')
    if len(x):
        x['composition_key']=x.A_class_counts.fillna('')+'|'+x.C_class_counts.fillna('')
    fixed=merged(d,links[links.design_family.eq('E_fixed_D_member_sensitivity')]).drop_duplicates('event_id')
    panels=[('class_count_preserving_members_D_not_fixed',x,['method','n','m','source_class','target_class','composition_key']),
            ('exact_fixed_D_member_panel',fixed,['fixed_D_panel_id'])]
    for family,frame,groups in panels:
        if frame.empty:continue
        for key,g in frame.groupby(groups,dropna=False,sort=False):
            base=g.iloc[0];r=meta(base);r.update(panel_kind=family,panel_id=digest([family,key])[:24],
                role_direction=role_direction(base),n=base.n,m=base.m,source_class=base.source_class,target_class=base.target_class,
                A_class_counts=base.get('A_class_counts',''),C_class_counts=base.get('C_class_counts',''),
                unique_pairs=g.event_id.nunique(),unique_A_teams=g.A_team_key.nunique(),unique_C_teams=g.C_team_key.nunique(),
                distinct_D=g.D_workers.nunique(),event_ids='|'.join(g.event_id.astype(str)),
                one_pair_only=g.event_id.nunique()==1)
            for m in METRICS:summarize_values(r,g[m],m)
            for arm in ['A','C']:
                for m in ARM_METRICS:summarize_values(r,g[arm+'_'+m],arm+'_'+m)
            result.append(r)
    return pd.DataFrame(result)

def background_changes(d,links):
    lg=links[links.design_family.isin(['A_equal_AC','B_equal_whole_class','S_equal_whole_class'])]
    x=merged(d,lg)
    if x.empty:return pd.DataFrame()
    x=x.drop_duplicates(['method','block_id','n','m','background_profile','event_id'])
    rows=[]
    for key,g in x.groupby(['method','block_id','n','m'],dropna=False,sort=False):
        neutral=g[g.background_profile.eq('neutral_members_0')]
        if neutral.empty:continue
        assert neutral.event_id.nunique()==1
        before=neutral.iloc[0];iv0=input_view(before)
        for _,after in g[~g.background_profile.eq('neutral_members_0')].iterrows():
            assert before.X_workers==after.X_workers and before.Z_workers==after.Z_workers
            iv1=input_view(after);r=meta(after);r.update(role_direction=role_direction(after),n=after.n,m=after.m,
                block_id=after.block_id,baseline_event_id=before.event_id,changed_event_id=after.event_id,
                background_profile=after.background_profile,baseline_D=before.D_workers,changed_D=after.D_workers,
                baseline_D_class_counts=before.D_class_counts,changed_D_class_counts=after.D_class_counts,
                same_background_class_counts=before.D_class_counts==after.D_class_counts,
                comparison='same_composition_background_members' if before.D_class_counts==after.D_class_counts else 'background_composition_and_members',
                baseline_A_team_key=iv0['input_A_team_key'],changed_A_team_key=iv1['input_A_team_key'],
                baseline_C_team_key=iv0['input_C_team_key'],changed_C_team_key=iv1['input_C_team_key'])
            if after.background_profile=='neutral_members_1':assert r['same_background_class_counts']
            for metric in METRICS:
                r[metric+'__baseline']=iv0[metric];r[metric+'__changed']=iv1[metric]
                r[metric+'__effect_difference']=iv1[metric]-iv0[metric]
            for arm in ['A','C']:
                for metric in ARM_METRICS:r[arm+'_'+metric+'__background_difference']=iv1['input_'+arm+'_'+metric]-iv0['input_'+arm+'_'+metric]
            rows.append(r)
    return pd.DataFrame(rows)

def paths(d,links,fixed_A=False):
    families=['D_fixed_A_expand_replacement'] if fixed_A else ['A_equal_AC','B_equal_whole_class','F_strict_common_n_bridge']
    lg=links[links.design_family.isin(families)].copy()
    if not fixed_A:lg=lg[lg.background_profile.eq('neutral_members_0')]
    x=merged(d,lg);path='anchor_A_path_id' if fixed_A else 'nested_background_path_id'
    if x.empty or path not in x:return pd.DataFrame()
    x=x[x[path].notna() & x[path].astype(str).ne('')].drop_duplicates(['method',path,'event_id'])
    rows=[];level='m' if fixed_A else 'n'
    for key,g in x.groupby(['method',path],dropna=False,sort=False):
        g=g.sort_values(level);rs=g.to_dict('records')
        for before,after in zip(rs,rs[1:]):
            iv0=input_view(before);iv1=input_view(after)
            if fixed_A:assert iv0['input_A_team_key']==iv1['input_A_team_key']
            else:
                assert before['X_workers']==after['X_workers'] and before['Z_workers']==after['Z_workers']
                assert set(pipe(before['D_workers']))<=set(pipe(after['D_workers']))
            r=meta(after);r.update(path_kind='fixed_A_expand_m' if fixed_A else 'fixed_XZ_expand_background_n',
                path_id=after[path],role_direction=role_direction(after),event_from=before['event_id'],event_to=after['event_id'],
                n_from=before['n'],n_to=after['n'],m_from=before['m'],m_to=after['m'],
                D_from=before['D_workers'],D_to=after['D_workers'],A_from=iv0['input_A_team_key'],A_to=iv1['input_A_team_key'],
                C_from=iv0['input_C_team_key'],C_to=iv1['input_C_team_key'],
                minimum_support_from=before.get('actual_A_minimum_support'),minimum_support_to=after.get('actual_A_minimum_support'))
            for metric in METRICS:
                r[metric+'__from']=iv0[metric];r[metric+'__to']=iv1[metric]
                r[metric+'__step_difference']=iv1[metric]-iv0[metric]
            rows.append(r)
    return pd.DataFrame(rows)

def unequal_decomposition(d,links):
    families=['B_unequal_whole_classes','B_unequal_equal_size_anchor','B_unequal_additional_same_target_members']
    x=merged(d,links[links.design_family.isin(families)])
    if x.empty:return pd.DataFrame()
    rows=[]
    for parent,g in x.groupby('parent_contrast_id',dropna=False,sort=False):
        total=g[g.design_family.eq('B_unequal_whole_classes')]
        if len(total)!=1:raise AssertionError(('bad_parent_total',parent,len(total)))
        total=total.iloc[0];tv=input_view(total)
        eq=g[g.design_family.eq('B_unequal_equal_size_anchor')]
        add=g[g.design_family.eq('B_unequal_additional_same_target_members')]
        for _,er in eq.iterrows():
            ar=add[add.member_rep.eq(er.member_rep)]
            assert len(ar)==1,(parent,er.member_rep,len(ar));ar=ar.iloc[0]
            ev,av=input_view(er),input_view(ar)
            assert tv['input_A_team_key']==ev['input_A_team_key']
            assert ev['input_C_team_key']==av['input_A_team_key']
            assert av['input_C_team_key']==tv['input_C_team_key']
            r=meta(total);r.update(parent_contrast_id=parent,member_rep=er.member_rep,
                role_direction=tv['input_role_direction'],parent_D_workers=total.D_workers,
                addition_actual_common_members=ar.D_workers,
                background_profile=value(total,'background_profile'),total_event_id=total.event_id,
                equal_event_id=er.event_id,addition_event_id=ar.event_id,
                small_team=tv['input_A_team_key'],middle_team=ev['input_C_team_key'],large_team=tv['input_C_team_key'],
                n_small=tv['input_n_A'],n_middle=ev['input_n_C'],n_large=tv['input_n_C'])
            assert r['n_small']==r['n_middle'] and r['n_large']>r['n_small']
            for metric in METRICS:
                a,b,c=tv[metric],ev[metric],av[metric]
                r[metric+'__total']=a;r[metric+'__equal']=b;r[metric+'__addition']=c
                closed=kind(metric)=='additive_difference' and all(map(finite,[a,b,c]))
                error=a-b-c if closed else np.nan
                if closed:assert abs(error)<=1e-6,(parent,metric,a,b,c,error)
                r[metric+'__closure_error']=error
                r[metric+'__parts_opposite_sign']=float(b*c< -1e-18) if finite(b) and finite(c) else np.nan
            rows.append(r)
    return pd.DataFrame(rows)

def signature(counts,method,building,roles):
    raw=json.loads(text(counts) or '{}');parts=[]
    for cl,n in raw.items():
        if int(n)<=0:continue
        rank=roles.get((method,building,cl))
        parts.append('unknown' if cl=='unknown' else f'role{int(rank)}' if rank is not None else cl)
    return '+'.join(sorted(parts))

def coalitions(d,links,roles):
    lg=links[links.design_family.isin(['C_complete_class_alliances','S_complete_class_coalition'])]
    x=merged(d,lg);rows=[]
    for _,base in x.iterrows():
        iv=input_view(base);sign=iv['input_sign'];r=meta(base)
        sa=signature(iv['input_A_class_counts'],base.method,base.building,roles)
        sc=signature(iv['input_C_class_counts'],base.method,base.building,roles)
        registered_sign=sign
        if sa>sc:
            sign=-sign;iv=input_view(base,sign_override=sign);sa,sc=sc,sa
        unknown=value(base,'unknown_background_included',None)
        if unknown is None:unknown=bool(pipe(value(base,'unknown_background','')))
        else:unknown=text(unknown).lower() in ['true','1','1.0']
        r.update(event_id=base.event_id,physical_pair_id=base.physical_pair_id,
            registered_input_orientation_sign=registered_sign,analysis_orientation_sign=sign,
            input_A_team_key=iv['input_A_team_key'],input_C_team_key=iv['input_C_team_key'],
            n_A=iv['input_n_A'],n_C=iv['input_n_C'],delta_n=iv['input_n_C']-iv['input_n_A'],
            A_class_counts=iv['input_A_class_counts'],C_class_counts=iv['input_C_class_counts'],
            coalition_A_roles=sa,coalition_C_roles=sc,role_direction=sa+' -> '+sc,
            raw_input_A_alliance=value(base,'A_alliance',value(base,'input_A_classes')),
            raw_input_C_alliance=value(base,'C_alliance',value(base,'input_C_classes')),
            coalition_comparison_type=value(base,'coalition_comparison_type','Semi_complete_class_union'),
            unknown_background_included=unknown,
            D_workers=base.D_workers,D_n=base.D_n,
            A_output_state=base.A_output_state if sign==1 else base.C_output_state,
            C_output_state=base.C_output_state if sign==1 else base.A_output_state)
        r['number_condition']='equal_n' if r['delta_n']==0 else 'more_people' if r['delta_n']>0 else 'fewer_people'
        for metric in METRICS:r[metric]=iv[metric]
        for arm in ['A','C']:
            for metric in ARM_METRICS:r[arm+'_'+metric]=iv['input_'+arm+'_'+metric]
        rows.append(r)
    return pd.DataFrame(rows)

def batches(d,links):
    lg=links[links.design_family.isin(['A_equal_AC','B_equal_whole_class']) & links.background_profile.eq('neutral_members_0')]
    x=merged(d,lg).drop_duplicates(['cell_id','event_id']);rows=[]
    for cell,g in x.groupby('cell_id',dropna=False,sort=False):
        if not {'batch_0','batch_1'}<=set(g.sample_batch):continue
        a,b=g[g.sample_batch.eq('batch_0')],g[g.sample_batch.eq('batch_1')];base=g.iloc[0]
        r=meta(base);r.update(cell_id=cell,role_direction=role_direction(base),n=base.n,m=base.m,
            batch0_pairs=a.event_id.nunique(),batch1_pairs=b.event_id.nunique(),
            batch0_event_ids='|'.join(a.event_id),batch1_event_ids='|'.join(b.event_id))
        for metric in METRICS:
            aa,bb=finite_array(a[metric]),finite_array(b[metric]);ma=aa.mean() if len(aa) else np.nan;mb=bb.mean() if len(bb) else np.nan
            r[metric+'__batch0_mean']=ma;r[metric+'__batch1_mean']=mb;r[metric+'__mean_difference']=mb-ma
            r[metric+'__batch0_valid']=len(aa);r[metric+'__batch1_valid']=len(bb)
            sa=0 if finite(ma) and abs(ma)<=1e-9 else np.sign(ma)
            sb=0 if finite(mb) and abs(mb)<=1e-9 else np.sign(mb)
            r[metric+'__direction_agreement']=float(sa==sb) if finite(ma) and finite(mb) else np.nan
        rows.append(r)
    return pd.DataFrame(rows)

def member_usage(d,members):
    rows=[]
    for method,g in d.groupby('method',sort=False):
        teams={}
        for a in ['A','C']:
            teams.update(dict(zip(g[a+'_team_key'],g[a+'_workers'])))
        used=Counter(w for ws in teams.values() for w in pipe(ws));events={b:Counter(w for ws in g[b+'_workers'] for w in pipe(ws)) for b in ['X','Z','D']}
        base=g.iloc[0];mp=members.get((base.pool_id,method),{});cl_count=Counter(mp.values())
        for w,n in sorted(used.items()):
            cl=mp.get(w,'unknown');r=meta(base);r.update(worker_id=w,frozen_class=cl,
                available_class_n=cl_count.get(cl,0),unique_used_endpoints=n,total_method_unique_endpoints=len(teams),
                endpoint_presence_fraction=n/len(teams),X_event_exposures=events['X'][w],Z_event_exposures=events['Z'][w],
                D_event_exposures=events['D'][w],exposure_denominator_method_events=len(g))
            rows.append(r)
    return pd.DataFrame(rows)

def physical_overlap(d):
    rows=[];meta_row=d.iloc[0]
    method_pairs={m:set(g.physical_pair_id) for m,g in d.groupby('method',sort=False)}
    method_teams={m:set(g.A_team_key)|set(g.C_team_key) for m,g in d.groupby('method',sort=False)}
    for a,b in itertools.combinations(sorted(method_pairs),2):
        n=len(method_pairs[a]&method_pairs[b]);nt=len(method_teams[a]&method_teams[b])
        r={k:meta_row.get(k,'') for k in COMMON if k!='method'}
        r.update(method_A=a,method_B=b,A_physical_pairs=len(method_pairs[a]),B_physical_pairs=len(method_pairs[b]),
            shared_physical_pairs=n,A_unique_teams=len(method_teams[a]),B_unique_teams=len(method_teams[b]),shared_teams=nt)
        rows.append(r)
    return pd.DataFrame(rows)

TABLES=['MEMBER_PANELS','BACKGROUND_CHANGES','FIXED_BLOCK_BACKGROUND_STEPS','FIXED_A_REPLACEMENT_STEPS',
 'UNEQUAL_DECOMPOSITION','COMPLETE_COALITIONS','SAMPLING_BATCHES','MEMBER_USAGE','PHYSICAL_METHOD_OVERLAP']

def summary_spec(name,frame):
    base=['scope','condition','layer','method']
    if name=='MEMBER_PANELS':return base+['panel_kind','role_direction','n','m'],[c for c in frame if c.endswith(('__span','__sd','__mean','__sign_flip'))]
    if name=='BACKGROUND_CHANGES':return base+['comparison','background_profile','role_direction','n','m'],[c for c in frame if c.endswith('__effect_difference')]
    if name=='FIXED_BLOCK_BACKGROUND_STEPS':return base+['role_direction','n_from','n_to','m_from','m_to'],[c for c in frame if c.endswith('__step_difference')]
    if name=='FIXED_A_REPLACEMENT_STEPS':return base+['role_direction','n_from','m_from','m_to'],[c for c in frame if c.endswith('__step_difference')]
    if name=='UNEQUAL_DECOMPOSITION':return base+['role_direction','background_profile'],[c for c in frame if c.endswith(('__total','__equal','__addition','__parts_opposite_sign'))]
    if name=='COMPLETE_COALITIONS':return base+['role_direction','number_condition','unknown_background_included'],METRICS+['n_A','n_C','delta_n','D_n']
    if name=='SAMPLING_BATCHES':return base+['role_direction','n','m'],[c for c in frame if c.endswith(('__mean_difference','__direction_agreement'))]
    return [],[]

def pool_summary(name,frame):
    keys,cols=summary_spec(name,frame)
    if not keys or frame.empty:return pd.DataFrame()
    if name=='MEMBER_PANELS':
        # A single feasible physical pair supplies coverage, not an estimate of
        # member variability. Its full row remains in MEMBER_PANELS.
        frame=frame[frame.unique_pairs.gt(1)]
        if frame.empty:return pd.DataFrame()
    # Unequal parents share a total across multiple middle subsets. Average
    # middle subsets within parent before assigning parents equal weight.
    if name=='UNEQUAL_DECOMPOSITION':
        frame=frame.groupby(keys+['pool_id','image','building','parent_contrast_id'],dropna=False,sort=False)[cols].mean().reset_index()
    rows=[]
    for key,g in frame.groupby(keys+['pool_id','image','building'],dropna=False,sort=False):
        r=dict(zip(keys+['pool_id','image','building'],key));r['analysis_table']=name;r['panel_rows']=len(g)
        for col in cols:
            x=finite_array(g[col]);r[col+'__valid']=len(x)
            r[col+'__pool_mean']=float(x.mean()) if len(x) else np.nan
            r[col+'__pool_mean_abs']=float(np.abs(x).mean()) if len(x) else np.nan
            r[col+'__pool_min']=float(x.min()) if len(x) else np.nan
            r[col+'__pool_max']=float(x.max()) if len(x) else np.nan
        rows.append(r)
    return pd.DataFrame(rows)

def merge_shards(files,dest):
    if not files:return None
    fields=[];count=0
    for f in files:
        with gzip.open(f,'rt',encoding='utf-8-sig',newline='') as stream:
            header=next(csv.reader(stream));fields.extend(x for x in header if x not in fields)
    tmp=dest.with_name(dest.name+'.partial')
    with gzip.open(tmp,'wt',encoding='utf-8-sig',newline='',compresslevel=5) as stream:
        wr=csv.DictWriter(stream,fieldnames=fields);wr.writeheader()
        for f in files:
            with gzip.open(f,'rt',encoding='utf-8-sig',newline='') as src:
                for r in csv.DictReader(src):wr.writerow(r);count+=1
    tmp.replace(dest)
    return {'file':dest.name,'rows':count,'columns':len(fields),'sha256':hashlib.sha256(dest.read_bytes()).hexdigest()}

def aggregate(out):
    receipts=[];summary_rows=[]
    for name in TABLES:
        files=sorted((out/'pool_shards').glob('*/'+name+'.csv.gz'))
        if files:receipts.append(merge_shards(files,out/(name+'.csv.gz')))
        sums=sorted((out/'pool_summaries').glob('*/'+name+'.csv.gz'))
        if not sums:continue
        frame=pd.concat([pd.read_csv(f,low_memory=False) for f in sums],ignore_index=True)
        save(frame,out/(name+'_POOL_SUMMARY.csv.gz'))
        keys,_=summary_spec(name,frame)
        cols=[c for c in frame if c.endswith('__pool_mean')]
        for key,g in frame.groupby(keys,dropna=False,sort=False):
            base=dict(zip(keys,key));base['analysis_table']=name
            for col in cols:
                metric=col[:-11]
                v=g.groupby(['image','building'],dropna=False)[col].mean().dropna()
                bv=v.groupby(level='building').mean()
                x=v.to_numpy();n=len(x)
                r=dict(base,metric=metric,registered_pools=g.pool_id.nunique(),valid_pools=int(g[col].notna().sum()),
                    registered_images=g.image.nunique(),valid_images=n,valid_buildings=len(bv),
                    image_mean=float(x.mean()) if n else np.nan,image_mean_abs=float(np.abs(x).mean()) if n else np.nan,
                    image_median=float(np.median(x)) if n else np.nan,image_p10=float(np.quantile(x,.1)) if n else np.nan,
                    image_min=float(x.min()) if n else np.nan,image_max=float(x.max()) if n else np.nan,
                    positive_images=int(np.sum(x>1e-9)),negative_images=int(np.sum(x< -1e-9)),
                    zero_images=int(np.sum(np.abs(x)<=1e-9)),
                    positive_image_fraction=float(np.mean(x>1e-9)) if n else np.nan,
                    building_balanced_mean=float(bv.mean()) if len(bv) else np.nan)
                summary_rows.append(r)
    if summary_rows:save(pd.DataFrame(summary_rows),out/'SENSITIVITY_IMAGE_BALANCED_SUMMARY.csv.gz')
    return receipts,len(summary_rows)

def validate_final_tables(out):
    rows=[]
    for path in sorted(out.glob('*.csv.gz')):
        n=0
        with gzip.open(path,'rt',encoding='utf-8-sig',newline='') as stream:
            reader=csv.reader(stream);header=next(reader)
            assert len(header)==len(set(header)),(path,'duplicate_columns')
            for row in reader:
                assert len(row)==len(header),(path,n,'inconsistent_row_width')
                n+=1
        h=hashlib.sha256()
        with open(path,'rb') as f:
            while chunk:=f.read(2**20):h.update(chunk)
        rows.append({'file':path.name,'rows':n,'columns':len(header),'bytes':path.stat().st_size,
                     'sha256':h.hexdigest(),'full_gzip_eof':True,'csv_widths_valid':True})
    return rows

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--metrics',required=True);ap.add_argument('--links',required=True);ap.add_argument('--capacity',required=True)
    ap.add_argument('--semi-capacity');ap.add_argument('--out',required=True);ap.add_argument('--max-pools',type=int)
    args=ap.parse_args();out=Path(args.out);out.mkdir(parents=True,exist_ok=True);started=time.monotonic()
    files=sorted((Path(args.metrics)/'metric_shards').glob('*.csv.gz'))
    if args.max_pools:files=files[:args.max_pools]
    contract={'code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'links_sha256':hashlib.sha256(Path(args.links).read_bytes()).hexdigest(),
              'metrics_source':str(Path(args.metrics).resolve()),'max_pools':args.max_pools,
              'new_fusions':0,'new_scores':0,'new_classifications':0}
    cp=out/'SENSITIVITY_INPUT_CONTRACT.json'
    if cp.exists():assert json.loads(cp.read_text())==contract,'Resume contract changed; use a fresh output directory.'
    else:cp.write_text(json.dumps(contract,ensure_ascii=False,indent=2)+'\n')
    links=pd.read_csv(args.links,usecols=lambda c:c in LINK,low_memory=False)
    for c in LINK:
        if c not in links:links[c]=np.nan
    linkp={p:g for p,g in links.groupby('pool_id',sort=False)}
    cap=Path(args.capacity);roles={};members={}
    rd=pd.read_csv(cap/'FROZEN_ROLE_PARENT_MAP_ALL_LOBO.csv')
    for row in rd.to_dict('records'):
        if finite(row['primary_role_rank']):roles[row['method'],row['heldout_building'],row['class_id']]=float(row['primary_role_rank'])
    member_sources=[cap/'POOL_METHOD_CAPACITY.csv.gz']
    if args.semi_capacity:member_sources.append(Path(args.semi_capacity))
    for src in member_sources:
        for row in pd.read_csv(src,usecols=lambda c:c in ['pool_id','method','class_members_json','unknown_workers']).to_dict('records'):
            mm={w:c for c,ws in json.loads(row['class_members_json']).items() for w in ws}
            mm.update({w:'unknown' for w in pipe(row.get('unknown_workers',''))})
            members[row['pool_id'],row['method']]=mm
    completed=[]
    wanted=set(META+METRICS+[a+'_'+m for a in ['A','C'] for m in ARM_METRICS])
    for i,path in enumerate(files):
        pid=path.name[:-7]
        if pid not in linkp:continue
        target=out/'pool_shards'/pid;marker=target/'COMPLETE.json'
        if marker.exists():completed.append(pid);continue
        d=pd.read_csv(path,usecols=lambda c:c in wanted,low_memory=False)
        for c in wanted:
            if c not in d:d[c]=np.nan
        for c in METRICS+[a+'_'+m for a in ['A','C'] for m in ARM_METRICS]:
            if d[c].dtype==bool:d[c]=d[c].astype(float)
            else:d[c]=pd.to_numeric(d[c],errors='coerce')
        lg=linkp[pid]
        functions=[member_panels,background_changes,lambda d,l:paths(d,l,False),lambda d,l:paths(d,l,True),
                   unequal_decomposition,lambda d,l:coalitions(d,l,roles),batches,
                   lambda d,l:member_usage(d,members),lambda d,l:physical_overlap(d)]
        counts={}
        for name,func in zip(TABLES,functions):
            frame=func(d,lg)
            counts[name]=len(frame)
            if frame.empty:continue
            save(frame,target/(name+'.csv.gz'))
            summary=pool_summary(name,frame)
            if len(summary):save(summary,out/'pool_summaries'/pid/(name+'.csv.gz'))
        target.mkdir(parents=True,exist_ok=True)
        marker.write_text(json.dumps({'pool_id':pid,'measured_events':len(d),'rows':counts},ensure_ascii=False,indent=2)+'\n')
        completed.append(pid)
        print(json.dumps({'pool':pid,'rows':counts,'seconds':round(time.monotonic()-started,1)}),flush=True)
    receipts,summary_n=aggregate(out)
    validation=validate_final_tables(out)
    (out/'FINAL_TABLE_READABILITY.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2)+'\n')
    measured_receipt=Path(args.metrics)/'MEASUREMENT_RECEIPT.json'
    measured_complete=json.loads(measured_receipt.read_text()).get('complete',False) if measured_receipt.exists() else False
    receipt={'metric_pools_available':len(files),'completed_pools':len(completed),'table_rows':receipts,
             'measurement_complete_at_sensitivity_finish':measured_complete,
             'all_available_metric_pools_processed':len(completed)==len(files),
             'image_balanced_summary_rows':summary_n,'missing_Q_imputed':False,'new_fusions':0,'new_scores':0,
             'scalar_decomposition_identity_checked':True,'fixed_A_identity_checked':True,'fixed_XZ_identity_checked':True,
             'neutral_background_quota_checked':True,'seconds':time.monotonic()-started}
    (out/'SENSITIVITY_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(receipt,ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__':main()
