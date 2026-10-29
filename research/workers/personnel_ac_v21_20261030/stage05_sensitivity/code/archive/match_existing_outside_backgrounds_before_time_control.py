"""Exact X/Z-controlled neutral-versus-outside-class background comparisons.

No new team is selected or fused. Main A/B equal neutral events are matched to
existing B unequal equal-size anchors by pool, method, n, m and canonical X/Z.
The strict F-only range is owned by stage05_funnel_bridge; overlap is explicit.
"""
from pathlib import Path
import argparse,csv,gzip,hashlib,json,math,sys,time
import numpy as np
import pandas as pd
from analyze_population_sensitivity import (METRICS,ARM_METRICS,META,COMMON,finite_array,
 meta,role_direction,digest,save,merge_shards,validate_final_tables,pipe)

KEY=['pool_id','method','n','m','X_workers','Z_workers']
GROUP=['scope','condition','layer','method','role_direction','n','m','background_change_type']
LINK=['event_id','pool_id','design_family','background_profile','parent_contrast_id','member_rep']

def match_pool(d,links):
    normal=links[links.design_family.isin(['A_equal_AC','B_equal_whole_class']) & links.background_profile.eq('neutral_members_0')]
    outside=links[links.design_family.eq('B_unequal_equal_size_anchor')]
    f_ids=set(links.loc[links.design_family.eq('F_strict_common_n_bridge'),'event_id'])
    if normal.empty or outside.empty:return pd.DataFrame()
    normal_meta={eid:'|'.join(sorted(set(g.design_family))) for eid,g in normal.groupby('event_id',sort=False)}
    outside_meta={eid:'|'.join(sorted(set(g.parent_contrast_id.dropna()))) for eid,g in outside.groupby('event_id',sort=False)}
    a=d[d.event_id.isin(normal_meta)].copy();b=d[d.event_id.isin(outside_meta)].copy()
    pair=a.merge(b,on=KEY,suffixes=('_neutral','_outside'),how='inner')
    pair=pair[pair.D_workers_neutral.fillna('').ne(pair.D_workers_outside.fillna('')) &
              pair.event_id_neutral.ne(pair.event_id_outside)]
    rows=[];seen=set()
    for row in pair.to_dict('records'):
        aid,bid=row['event_id_neutral'],row['event_id_outside']
        comparison=digest([row['pool_id'],row['method'],sorted([aid,bid])])[:24]
        if comparison in seen:continue
        seen.add(comparison)
        assert row['source_class_neutral']==row['source_class_outside'] and row['target_class_neutral']==row['target_class_outside']
        ad,bd=set(pipe(row['D_workers_neutral'])),set(pipe(row['D_workers_outside']))
        assert len(ad)==len(bd)==int(row['n']-row['m']) and ad!=bd
        ac,bc=row['D_class_counts_neutral'],row['D_class_counts_outside']
        bgtype='same_class_counts_different_background_members' if ac==bc else 'background_class_counts_and_members_changed'
        rr={k:row[k] if k in KEY else row[k+'_neutral'] for k in COMMON}
        rr.update(background_comparison_id=comparison,
            physical_background_comparison_id=digest([row['pool_id'],sorted([row['physical_pair_id_neutral'],row['physical_pair_id_outside']])])[:24],
            n=row['n'],m=row['m'],X_workers=row['X_workers'],Z_workers=row['Z_workers'],
            source_class=row['source_class_neutral'],target_class=row['target_class_neutral'],
            source_role_rank=row['source_role_rank_neutral'],target_role_rank=row['target_role_rank_neutral'],
            role_direction=role_direction({'source_class':row['source_class_neutral'],'target_class':row['target_class_neutral'],
                'source_role_rank':row['source_role_rank_neutral'],'target_role_rank':row['target_role_rank_neutral']}),
            neutral_event_id=aid,outside_event_id=bid,neutral_design_families=normal_meta[aid],
            neutral_event_also_in_F_strict_bridge=aid in f_ids,outside_parent_contrast_ids=outside_meta[bid],
            neutral_D_workers='|'.join(sorted(ad)),outside_D_workers='|'.join(sorted(bd)),
            neutral_D_class_counts=ac,outside_D_class_counts=bc,background_change_type=bgtype,
            shared_D_n=len(ad&bd),removed_D_workers='|'.join(sorted(ad-bd)),added_D_workers='|'.join(sorted(bd-ad)),
            minimum_support=math.ceil(row['n']/2),block_can_reach_MV50_by_size=row['m']>=math.ceil(row['n']/2))
        for arm in ['A','C']:
            rr['neutral_'+arm+'_team_key']=row[arm+'_team_key_neutral']
            rr['outside_'+arm+'_team_key']=row[arm+'_team_key_outside']
            for metric in ARM_METRICS:
                av=row.get(arm+'_'+metric+'_neutral',np.nan);bv=row.get(arm+'_'+metric+'_outside',np.nan)
                rr[arm+'_'+metric+'__background_change']=bv-av
        for metric in METRICS:
            av=row[metric+'_neutral'];bv=row[metric+'_outside']
            rr[metric+'__neutral_AC']=av;rr[metric+'__outside_AC']=bv;rr[metric+'__effect_difference']=bv-av
        rows.append(rr)
    return pd.DataFrame(rows)

def summarize_pool(frame):
    if frame.empty:return pd.DataFrame()
    cols=[c for c in frame if c.endswith(('__neutral_AC','__outside_AC','__effect_difference','__background_change'))]
    # Weight each exact X/Z block equally inside a pool/condition, regardless
    # of whether one or two outside-D member variants were feasible/registered.
    block=frame.groupby(GROUP+['pool_id','image','building','X_workers','Z_workers'],dropna=False,sort=False)[cols].mean().reset_index()
    rowcounts=frame.groupby(GROUP+['pool_id'],dropna=False,sort=False).size()
    rows=[]
    for key,g in block.groupby(GROUP+['pool_id','image','building'],dropna=False,sort=False):
        r=dict(zip(GROUP+['pool_id','image','building'],key));r['matched_XZ_blocks']=len(g)
        r['matched_background_pairs']=int(rowcounts.loc[tuple(r[k] for k in GROUP+['pool_id'])])
        for col in cols:
            x=finite_array(g[col]);r[col+'__valid_blocks']=len(x)
            r[col+'__pool_mean']=float(x.mean()) if len(x) else np.nan
            r[col+'__pool_mean_abs']=float(np.abs(x).mean()) if len(x) else np.nan
            r[col+'__pool_min']=float(x.min()) if len(x) else np.nan
            r[col+'__pool_max']=float(x.max()) if len(x) else np.nan
        rows.append(r)
    return pd.DataFrame(rows)

def aggregate(out):
    raw=sorted((out/'pool_shards').glob('*.csv.gz'));sums=sorted((out/'pool_summaries').glob('*.csv.gz'))
    if not raw:raise RuntimeError('No exact background match found')
    merged_receipt=merge_shards(raw,out/'EXACT_NEUTRAL_OUTSIDE_BACKGROUND_PAIRS.csv.gz')
    pooled=pd.concat([pd.read_csv(p,low_memory=False) for p in sums],ignore_index=True)
    save(pooled,out/'EXACT_NEUTRAL_OUTSIDE_POOL_SUMMARY.csv.gz')
    cols=[c for c in pooled if c.endswith('__pool_mean')];rows=[]
    for key,g in pooled.groupby(GROUP,dropna=False,sort=False):
        base=dict(zip(GROUP,key))
        for col in cols:
            image=g.groupby(['image','building'],dropna=False)[col].mean().dropna()
            buildings=image.groupby(level='building').mean();x=image.to_numpy();n=len(x)
            r=dict(base,metric=col[:-11],registered_pools=g.pool_id.nunique(),valid_pools=int(g[col].notna().sum()),
                registered_images=g.image.nunique(),valid_images=n,valid_buildings=len(buildings),
                image_mean=float(x.mean()) if n else np.nan,image_mean_abs=float(np.abs(x).mean()) if n else np.nan,
                image_median=float(np.median(x)) if n else np.nan,image_p10=float(np.quantile(x,.1)) if n else np.nan,
                image_min=float(x.min()) if n else np.nan,image_max=float(x.max()) if n else np.nan,
                positive_images=int(np.sum(x>1e-9)),negative_images=int(np.sum(x< -1e-9)),
                positive_image_fraction=float(np.mean(x>1e-9)) if n else np.nan,
                building_balanced_mean=float(buildings.mean()) if len(buildings) else np.nan,
                matched_XZ_blocks=int(g.matched_XZ_blocks.sum()),matched_background_pairs=int(g.matched_background_pairs.sum()))
            rows.append(r)
    save(pd.DataFrame(rows),out/'EXACT_NEUTRAL_OUTSIDE_IMAGE_BALANCED_SUMMARY.csv.gz')
    return merged_receipt,len(rows)

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--metrics',required=True);ap.add_argument('--links',required=True);ap.add_argument('--out',required=True)
    args=ap.parse_args();out=Path(args.out);out.mkdir(parents=True,exist_ok=True);started=time.monotonic()
    contract={'code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'common_module_sha256':hashlib.sha256((Path(__file__).parent/'analyze_population_sensitivity.py').read_bytes()).hexdigest(),
        'links_sha256':hashlib.sha256(Path(args.links).read_bytes()).hexdigest(),
        'metrics':str(Path(args.metrics).resolve()),'selection':'exact identity matching only, no effect filtering',
        'baseline_scope':'A_equal_AC or B_equal_whole_class neutral_members_0; F-only scope belongs to stage05_funnel_bridge',
        'new_fusions':0,'new_scores':0,'new_teams':0}
    cp=out/'EXACT_BACKGROUND_INPUT_CONTRACT.json'
    if cp.exists():assert json.loads(cp.read_text())==contract
    else:cp.write_text(json.dumps(contract,ensure_ascii=False,indent=2)+'\n')
    links=pd.read_csv(args.links,usecols=lambda c:c in LINK,low_memory=False)
    for c in LINK:
        if c not in links:links[c]=np.nan
    grouped={p:g for p,g in links.groupby('pool_id',sort=False)}
    wanted=set(META+METRICS+[a+'_'+m for a in ['A','C'] for m in ARM_METRICS]);done=[]
    for path in sorted((Path(args.metrics)/'metric_shards').glob('*.csv.gz')):
        pid=path.name[:-7]
        if pid not in grouped:continue
        lg=grouped[pid]
        if not lg.design_family.eq('B_unequal_equal_size_anchor').any():continue
        dest=out/'pool_shards'/path.name;summary=out/'pool_summaries'/path.name
        if dest.exists() and summary.exists():done.append(pid);continue
        d=pd.read_csv(path,usecols=lambda c:c in wanted,low_memory=False)
        for c in wanted:
            if c not in d:d[c]=np.nan
        for c in METRICS+[a+'_'+m for a in ['A','C'] for m in ARM_METRICS]:
            d[c]=d[c].astype(float) if d[c].dtype==bool else pd.to_numeric(d[c],errors='coerce')
        frame=match_pool(d,lg)
        if frame.empty:continue
        save(frame,dest);save(summarize_pool(frame),summary);done.append(pid)
        print(json.dumps({'pool':pid,'exact_background_pairs':len(frame)}),flush=True)
    merged_receipt,summary_rows=aggregate(out)
    validation=validate_final_tables(out)
    (out/'FINAL_TABLE_READABILITY.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2)+'\n')
    receipt={'matched_pools':len(done),'table':merged_receipt,'summary_rows':summary_rows,'exact_XZ_matching':True,
        'D_difference_required':True,'same_n_m_different_XZ_excluded':True,
        'overlap_with_strict_F_marked_on_baseline_event':True,'physical_comparison_id_available':True,
        'new_fusions':0,'new_scores':0,'new_teams':0,'seconds':time.monotonic()-started}
    (out/'EXACT_BACKGROUND_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(receipt,ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__':main()
