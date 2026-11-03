"""Targeted manual-order sensitivity of frozen/updated-label alliance tables.

Label snapshot `version` is never confused with `connection_version`.
No fusion, member selection, label fitting or original output writes occur.
"""
from __future__ import annotations
import argparse
import gzip
import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'research/data/releases/v2.1/closeout_20261030/alliance_completion_20261031'
IMPACT = ROOT / 'research/fusion/manual_order_impact_20261104'
METRICS = ['B8L2','D10','IoU3D100','fusion_turn_n','fusion_short_turn_edges',
           'boundary_loss','direction_loss','height_loss','omission','extension',
           'source_time_total_seconds','recorded_time_total_seconds']
KEYS = ['version','pool_id','unknown_background_included']


def save(out, name, frame):
    out.mkdir(parents=True, exist_ok=True)
    frame.to_csv(out/name, index=False)


def derive(d):
    strata=[]
    for keys,g in d.groupby(['version','scope','condition','unknown_background_included','classes']):
        base=dict(zip(['version','scope','condition','unknown_background_included','classes'],keys))
        for metric in METRICS:
            im=g.groupby('image')[metric].mean().dropna()
            strata.append(dict(**base,metric=metric,registered_pools=len(g),
                               eligible_pools=int(g.n.ge(3).sum()),valid_images=len(im),mean=im.mean()))
    comparisons=[]
    for (version,pool,unknown),g in d.groupby(KEYS):
        full=g.loc[g.n.idxmax()];pure=g[g.classes.isin(['C1','C2','C3']) & g.n.ge(3)]
        if pd.isna(full.B8L2) or pure.B8L2.notna().sum()==0:
            continue
        best=pure.loc[pure.B8L2.idxmax()]
        comparisons.append(dict(version=version,pool_id=pool,unknown_background_included=unknown,
                                image=full.image,building=full.building,scope=full.scope,condition=full.condition,
                                full_Q=full.B8L2,best_pure_Q=best.B8L2,
                                full_minus_best_pure=full.B8L2-best.B8L2,
                                scoreable_pure_classes=int(pure.B8L2.notna().sum()),
                                full_team_key=full.team_key,best_pure_team_key=best.team_key))
    c=pd.DataFrame(comparisons)
    both=c.pivot(index=['pool_id','image','scope','condition','unknown_background_included'],
                 columns='version',values=['full_Q','best_pure_Q','full_minus_best_pure']).dropna()
    both.columns=['_'.join(x) for x in both.columns];both=both.reset_index()
    stats=[]
    for (scope,condition,unknown),g in both.groupby(['scope','condition','unknown_background_included']):
        images=g.groupby('image').mean(numeric_only=True)
        for version in ['frozen','updated']:
            x=images['full_minus_best_pure_'+version]
            stats.append(dict(scope=scope,condition=condition,unknown_background_included=unknown,
                              version=version,pools=len(g),images=len(images),
                              mean_full_minus_best_pure=x.mean(),pure_better_images=int((x< -1e-8).sum()),
                              full_better_images=int((x>1e-8).sum()),tied_images=int((x.abs()<=1e-8).sum())))
    return {'CLASS_METRIC_SUMMARY.csv':pd.DataFrame(strata),
            'FULL_VS_BEST_PURE.csv':c,'FULL_VS_BEST_PURE_COMMON.csv':both,
            'FULL_VS_BEST_PURE_SUMMARY.csv':pd.DataFrame(stats)}


def parity(old, saved, keys, fields):
    a=old.set_index(keys).sort_index();b=saved.set_index(keys).sort_index()
    assert a.index.equals(b.index),(keys,a.shape,b.shape)
    checks=[]
    for f in fields:
        x=pd.to_numeric(a[f],errors='coerce');y=pd.to_numeric(b[f],errors='coerce')
        assert x.isna().equals(y.isna()),f
        error=float((x-y).abs().max()) if x.notna().any() else 0.
        assert error<1e-8,(f,error)
        checks.append(dict(field=f,rows=len(a),max_absolute_error=error))
    return checks


def coordinate_candidate(out):
    """Separate user-specified coordinate sensitivity; never promote it."""
    candidate=json.load(gzip.open(IMPACT/'coordinate_candidate/CANDIDATE_FULL_STATE.json.gz','rt'))[1]
    score=candidate['score'];before=pd.read_csv(IMPACT/'alliances/ALLIANCE_RESULTS_ASSISTED.csv.gz')
    after=before.copy();hit=before.team_key.eq(score['team_key'])
    assert hit.sum()==2 and before.loc[hit,'B8L2'].isna().all()
    for _,r in before[hit].iterrows():
        assert (r.reference_id,r.reference_version)==(score['reference_id'],score['reference_version'])
    for c in METRICS:
        if 'time' not in c:after.loc[hit,c]=score[c]
    after.loc[hit,'complete_evaluable']=score['complete_evaluable'];after.loc[hit,'status']=score['score_status']
    mutable=[c for c in METRICS if 'time' not in c]+['complete_evaluable','status']
    pd.testing.assert_frame_equal(before.drop(columns=mutable),after.drop(columns=mutable))
    pd.testing.assert_frame_equal(before[~hit],after[~hit])
    old=derive(before);new=derive(after);destination=out/'coordinate_candidate'
    affected=[];summaries=[]
    for version,d,derived in [('manual_assisted_fixed_coordinates',before,old),('coordinate_candidate_not_adopted',after,new)]:
        part=d[hit].copy();part['connection_version']=version;affected.append(part)
        for name,frame in derived.items():save(destination,version.upper()+'_'+name,frame)
        s=derived['FULL_VS_BEST_PURE_SUMMARY.csv'].copy();s['connection_version']=version;summaries.append(s)
    save(destination,'AFFECTED_ALLIANCE_ROWS.csv',pd.concat(affected,ignore_index=True))
    save(destination,'SUMMARY_COMPARISON.csv',pd.concat(summaries,ignore_index=True))
    a=old['FULL_VS_BEST_PURE.csv'];b=new['FULL_VS_BEST_PURE.csv']
    pools=a.merge(b,on=KEYS,suffixes=('_fixed','_candidate'),validate='one_to_one',how='outer',indicator=True)
    pools['new_pure_candidate']=pools.scoreable_pure_classes_candidate>pools.scoreable_pure_classes_fixed
    pools['best_pure_changed']=pools.best_pure_team_key_fixed.ne(pools.best_pure_team_key_candidate)&pools['_merge'].eq('both')
    changed=pools[pools.new_pure_candidate|pools.best_pure_changed|pools['_merge'].ne('both')]
    save(destination,'AFFECTED_POOL_COMPARISONS.csv',changed)
    resolution=pd.read_csv(IMPACT/'alliances/ALLIANCE_414_RESOLUTION_ASSISTED.csv')
    resolution_hit=resolution['assisted_team_key'].eq(score['team_key'])
    assert resolution_hit.sum()==0,'Unexpected additional candidate resolution consumer'
    record=dict(source_commit='ac395e703d1fef573d1ef3e105df0286d62a0468',candidate_adopted=False,
        comparison='fixed-coordinate assisted version versus separate coordinate candidate',affected_team=score['team_key'],
        affected_rows=2,newly_scorable_rows=2,Q=score['B8L2'],D10=score['D10'],
        original_and_fixed_coordinate_Q=None,source_annotation_time_changed=False,human_coordinate_labor_known=False,
        fixed_coordinate_branch_overwritten=False,labels_or_members_changed=False,reference_changed=False,
        camera_in_visibility_kernel=candidate['geometry_audit']['camera_in_visible_kernel'],
        current_414_resolution_hits=int(resolution_hit.sum()),
        new_comparison_pool_contexts=int(pools['_merge'].eq('right_only').sum()),
        existing_best_pure_changed=int(pools.best_pure_changed.sum()),new_fusions=0,new_scores=0)
    (destination/'CHECKS.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(record,ensure_ascii=False,indent=2))


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,default=IMPACT/'alliances')
    ap.add_argument('--candidate-only',action='store_true');args=ap.parse_args()
    if args.candidate_only:
        coordinate_candidate(args.out);return
    out=args.out;out.mkdir(parents=True,exist_ok=True)
    old=pd.read_csv(BASE/'ALLIANCE_RESULTS.csv');new=old.copy()
    end=pd.read_csv(IMPACT/'endpoints/ENDPOINT_SCORES.csv').set_index(['team_key','reference_id','reference_version'])
    assert end.index.is_unique
    affected=[]
    for i,r in old.iterrows():
        key=(r.team_key,r.reference_id,r.reference_version)
        if key not in end.index:
            continue
        e=end.loc[key]
        assert pd.isna(r.B8L2) and pd.isna(r.D10)
        for f in METRICS:
            if 'time' not in f:
                new.loc[i,f]=e[f]
        new.loc[i,'complete_evaluable']=e.complete_evaluable;new.loc[i,'status']=e.score_status
        affected.append(dict(source_row=i,team_key=r.team_key,version=r.version,pool_id=r.pool_id,image=r.image,
                             building=r.building,classes=r.classes,unknown_background_included=r.unknown_background_included,
                             old_status=r.status,new_status=e.score_status,old_Q=r.B8L2,new_Q=e.B8L2))
    affected=pd.DataFrame(affected)
    assert len(affected)==19 and affected.team_key.nunique()==12
    fixed=[c for c in old if c not in METRICS[:-2]+['complete_evaluable','status']]
    pd.testing.assert_frame_equal(old[fixed],new[fixed])
    assert old.loc[old.B8L2.notna(),METRICS].equals(new.loc[old.B8L2.notna(),METRICS])
    derived_old=derive(old);derived_new=derive(new)
    checks=[]
    for name,keys,fields in [
        ('CLASS_METRIC_SUMMARY.csv',['version','scope','condition','unknown_background_included','classes','metric'],
         ['registered_pools','eligible_pools','valid_images','mean']),
        ('FULL_VS_BEST_PURE.csv',KEYS,['full_Q','best_pure_Q','full_minus_best_pure','scoreable_pure_classes']),
        ('FULL_VS_BEST_PURE_SUMMARY.csv',['scope','condition','unknown_background_included','version'],
         ['pools','images','mean_full_minus_best_pure','pure_better_images','full_better_images','tied_images'])]:
        for c in parity(derived_old[name],pd.read_csv(BASE/name),keys,fields):
            checks.append(dict(source=name,**c))
    save(out,'BASELINE_REPRODUCTION.csv',pd.DataFrame(checks));save(out,'AFFECTED_ALLIANCE_ROWS.csv',affected)
    new['connection_version']='manual_assisted';save(out,'ALLIANCE_RESULTS_ASSISTED.csv.gz',new)
    summaries=[]
    for v,ds in [('automatic',derived_old),('manual_assisted',derived_new)]:
        for name,frame in ds.items():
            save(out, v.upper()+'_'+name,frame)
        x=ds['FULL_VS_BEST_PURE_SUMMARY.csv'].copy();x['connection_version']=v;summaries.append(x)
    summary=pd.concat(summaries,ignore_index=True);save(out,'FULL_VS_BEST_PURE_CONNECTION_COMPARISON.csv',summary)
    a=derived_old['FULL_VS_BEST_PURE.csv'];b=derived_new['FULL_VS_BEST_PURE.csv']
    comparison=a.merge(b,on=KEYS,suffixes=('_automatic','_assisted'),how='outer',validate='one_to_one',indicator=True)
    comparison['support_class']=comparison['_merge'].map({'left_only':'lost','right_only':'new_comparison_support','both':'same_pool_support'}).astype(str)
    comparison['new_pure_candidate_in_same_pool']=(comparison.scoreable_pure_classes_assisted>comparison.scoreable_pure_classes_automatic)
    comparison['aggregate_difference_on_same_pool']=comparison.full_minus_best_pure_assisted-comparison.full_minus_best_pure_automatic
    comparison['fixed_original_endpoint_support_difference']=np.where(comparison['_merge'].eq('both'),0.,np.nan)
    comparison['best_pure_selection_changed']=comparison.best_pure_team_key_assisted.ne(comparison.best_pure_team_key_automatic) & comparison['_merge'].eq('both')
    save(out,'POOL_SUPPORT_AND_SELECTION_CHANGES.csv',comparison.drop(columns='_merge'))
    changed=comparison[comparison.support_class.ne('same_pool_support')|comparison.new_pure_candidate_in_same_pool|comparison.best_pure_selection_changed]
    save(out,'AFFECTED_POOL_COMPARISONS.csv',changed)
    image_rows=[];building_rows=[]
    for v,ds in [('automatic',derived_old),('manual_assisted',derived_new)]:
        c=ds['FULL_VS_BEST_PURE.csv']
        group=['version','scope','condition','unknown_background_included','building','image']
        im=c.groupby(group,dropna=False).agg(full_minus_best_pure=('full_minus_best_pure','mean'),
            pools=('pool_id','nunique'),pure_classes=('scoreable_pure_classes','mean')).reset_index()
        im['connection_version']=v;image_rows.append(im)
        bu=im.groupby(group[:-1],dropna=False).agg(full_minus_best_pure=('full_minus_best_pure','mean'),images=('image','nunique')).reset_index()
        bu['connection_version']=v;building_rows.append(bu)
    save(out,'IMAGE_EFFECTS.csv',pd.concat(image_rows,ignore_index=True));save(out,'BUILDING_EFFECTS.csv',pd.concat(building_rows,ignore_index=True))
    resolution=pd.read_csv(BASE/'ALLIANCE_414_RESOLUTION.csv')
    current=new[new.version.eq('updated') & ~new.unknown_background_included]
    replacement=current[['pool_id','classes','team_key','status','B8L2']].rename(columns={'team_key':'assisted_team_key','status':'assisted_status','B8L2':'assisted_B8L2'})
    resolution=resolution.merge(replacement,on=['pool_id','classes'],how='left',validate='one_to_one')
    assert len(resolution)==414 and resolution.assisted_status.eq('capacity_only').sum()==11
    # `new_team_key` is the pre-completion archive lookup and can be missing;
    # `team_key` is the resolved endpoint identity in this completion table.
    assert resolution.team_key.fillna('').equals(resolution.assisted_team_key.fillna(''))
    known=resolution.new_team_key.notna()
    assert resolution.loc[known,'new_team_key'].equals(resolution.loc[known,'assisted_team_key'])
    save(out,'ALLIANCE_414_RESOLUTION_ASSISTED.csv',resolution)
    count=[]
    for v,d in [('automatic',old),('manual_assisted',new)]:
        for keys,g in d.groupby(['version','scope','condition','unknown_background_included']):
            count.append(dict(connection_version=v,**dict(zip(['label_version','scope','condition','unknown_background_included'],keys)),
                              rows=len(g),teams=g.team_key.nunique(),capacity_only=int(g.n.lt(3).sum()),
                              eligible=int(g.n.ge(3).sum()),scorable=int(g.B8L2.notna().sum()),
                              eligible_unscored=int((g.n.ge(3)&g.B8L2.isna()).sum())))
    save(out,'SUPPORT_COUNTS.csv',pd.DataFrame(count))
    record=dict(source_commit='ac395e703d1fef573d1ef3e105df0286d62a0468',source=str(BASE.relative_to(ROOT)),
                baseline_parity_max_error=max(x['max_absolute_error'] for x in checks),
                affected_teams=12,affected_rows=19,newly_scored_rows=int(affected.new_Q.notna().sum()),
                original_scored_endpoint_values_changed=0,labels_changed=False,members_changed=False,
                current_changed_alliances_executable=403,capacity_only=11,
                new_pools=int(comparison.support_class.eq('new_comparison_support').sum()),
                best_pure_changes_in_original_comparable_pools=int(comparison.best_pure_selection_changed.sum()),
                interpretation='New scored endpoint support; same already-scored endpoints unchanged. Frozen/updated are label snapshots.',
                source_annotation_time_changed=False,human_order_time_available=False,new_fusions=0)
    (out/'CHECKS.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(record,ensure_ascii=False,indent=2));print(summary.to_string(index=False))
    coordinate_candidate(out)


if __name__=='__main__':
    main()
