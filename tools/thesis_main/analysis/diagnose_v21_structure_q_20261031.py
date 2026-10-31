"""Saved-data audit of structural classes, differing selections, and difficulty profiles."""
import json
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
from tools.thesis_main.analysis.q_only_exchange_v21_20261031 import ROOT,OUT as STUDY,UP,members,rows,image_means
from tools.thesis_main.analysis.worker_difficulty_profiles_20261018 import add_relative,preferences

OUT=STUDY/'diagnostic_20261031'
def save(name,d):d.to_csv(OUT/(name+'.csv'),index=False,encoding='utf-8-sig')

def classes():
    h=pd.read_csv(STUDY/'HISTORY_LOBO.csv');h=h[h.known.eq(True)].copy()
    f=pd.read_csv(UP/'classification/HISTORY_ALL_LOBO.csv.gz')
    features=['m_all_turn_n','m_all_short_turn_edges','m_all_near_straight_nodes_5deg','m_all_unmatched_ref_9','m_hard_turn_n','m_hard_short_turn_edges','m_hard_unmatched_ref_9','m_hard_minus_easy_turn_n']
    h=h.merge(f[['worker_id','heldout_building']+features],on=['worker_id','heldout_building'],validate='one_to_one')
    c=h.groupby(['heldout_building','class_id']).agg(workers=('worker_id','size'),raw_q=('raw_q','mean'),raw_q_sd=('raw_q','std'),raw_q_min=('raw_q','min'),raw_q_max=('raw_q','max'),peer_q=('peer_q','mean'),**{k:(k,'mean') for k in features}).reset_index();save('CLASS_BY_FOLD',c)
    stats=[]
    for fold,g in h.groupby('heldout_building'):
        gm=g.groupby('class_id').raw_q.transform('mean');means=g.groupby('class_id').raw_q.mean()
        stats.append(dict(heldout_building=fold,workers=len(g),Q_between_class_fraction=float(((gm-g.raw_q.mean())**2).sum()/((g.raw_q-g.raw_q.mean())**2).sum()),Q_C3_auc=roc_auc_score(g.class_id.eq('C3'),g.raw_q),C3_minus_C2=means['C3']-means['C2'],C2_minus_C1=means['C2']-means['C1']))
    save('CLASS_Q_ASSOCIATION',pd.DataFrame(stats));save('CLASS_AVERAGE_OVER_FOLDS',c.groupby('class_id').mean(numeric_only=True).reset_index())

def changed_events(raw):
    links=pd.read_csv(STUDY/'DESIGN_LINKS.csv');sel=pd.read_csv(STUDY/'SELECTION_OVERLAP.csv');pairs=pd.read_csv(STUDY/'PAIRED_EVENTS.csv')
    lab=pd.read_csv(STUDY/'LABEL_SNAPSHOT.csv').set_index(['heldout_building','worker_id']);ep={r['team_key']:r for r in rows(STUDY/'ENDPOINTS.jsonl.gz')}
    records=raw.set_index(['pool_id','worker_id']);assert records.index.is_unique
    extra=['nodes','minimum_support','S_bottom_deg','dir','geometry_area_h2','centroid_x_h','centroid_z_h','height_mean_h','height_min_h','height_max_h']
    person_fields=['B8L2','turn_n','short_turn_edges','near_straight_nodes_5deg','unmatched_ref_9','matched_boundary_abs_deg','omission','extension']
    details=[]
    for r in sel[~sel.same_block].itertuples():
        l=links[links.event_id.eq(r.event_id)].set_index('policy');s=l.loc['STRUCTURE'];q=l.loc[r.policy]
        removed=sorted(members(s.incoming_members)-members(q.incoming_members));added=sorted(members(q.incoming_members)-members(s.incoming_members))
        a=ep[s.team_key];b=ep[q.team_key];rc=[lab.loc[(r.building,w),'class_id'] for w in removed];ac=[lab.loc[(r.building,w),'class_id'] for w in added]
        z=dict(event_id=r.event_id,comparator=r.policy,n=r.n,image=r.image,building=r.building,removed='|'.join(removed),added='|'.join(added),removed_classes='|'.join(rc),added_classes='|'.join(ac),class_composition_same=sorted(rc)==sorted(ac),changed_people=len(removed),structure_scored=a.get('B8L2') is not None,q_scored=b.get('B8L2') is not None,structure_connection=a.get('connection_available'),q_connection=b.get('connection_available'),structure_team=s.team_key,q_team=q.team_key)
        for k in extra:
            x,y=a.get(k),b.get(k);z[k+'_structure']=x;z[k+'_q']=y;z[k+'_delta']=x-y if x is not None and y is not None else np.nan
        z['centroid_distance_h']=float(np.hypot(z['centroid_x_h_delta'],z['centroid_z_h_delta']))
        for k in person_fields:
            z['removed_raw_'+k]=records.loc[[(s.pool_id,w) for w in removed],k].mean();z['added_raw_'+k]=records.loc[[(s.pool_id,w) for w in added],k].mean()
        details.append(z)
    detail=pd.DataFrame(details);d=pairs.merge(detail,on=['event_id','comparator','n','image','building'],validate='one_to_one');save('DIFFERENT_SELECTION_EVENTS',d)
    sums=[];ims=[]
    for (n,pol),g in d.groupby(['n','comparator']):
        z=dict(n=int(n),comparator=pol,events=len(g),images=g.image.nunique(),buildings=g.building.nunique(),same_class_composition=int(g.class_composition_same.sum()),different_class_composition=int((~g.class_composition_same).sum()),scored_events=g.B8L2_delta.notna().sum(),scored_images=g.loc[g.B8L2_delta.notna(),'image'].nunique(),same_turn_events=int(g.fusion_turn_n_delta.eq(0).sum()),Q_positive=int(g.B8L2_delta.gt(1e-8).sum()),Q_negative=int(g.B8L2_delta.lt(-1e-8).sum()),Q_tie=int(g.B8L2_delta.abs().le(1e-8).sum()),structure_only=int((g.structure_scored&~g.q_scored).sum()),q_only=int((~g.structure_scored&g.q_scored).sum()),both_unscored=int((~g.structure_scored&~g.q_scored).sum()))
        for k in ['B8L2_delta','IoU3D100_delta','fusion_turn_n_delta','boundary_loss_delta','direction_loss_delta','centroid_distance_h']:
            v=g.dropna(subset=[k]);im=image_means(v,[k]);z[k+'_image_mean']=im[k].mean();z[k+'_images']=len(im)
        sums.append(z)
        im=image_means(g.dropna(subset=['B8L2_delta']),['B8L2_delta','fusion_turn_n_delta','IoU3D100_delta']);im['comparator']=pol;ims.append(im)
    save('DIFFERENT_SELECTION_SUMMARY',pd.DataFrame(sums));save('DIFFERENT_SELECTION_IMAGES',pd.concat(ims,ignore_index=True))
    # Original seven-person ABC remains a different comparison from the one-person policy discrepancy.
    old=pd.read_csv(UP/'HALF_EVENT_LEGALITY.csv.gz',low_memory=False);old=old[old.updated_class_legal]
    save('HALF_ORIGINAL_SUMMARY',pd.read_csv(UP/'HALF_SUMMARY.csv'))
    assert set(sel[sel.policy.eq('Q_RAW')&~sel.same_block].event_id)==set(d[d.comparator.eq('Q_RAW')].event_id)
    assert d[d.comparator.eq('Q_RAW')].changed_people.eq(1).all()

def difficulty(raw):
    d=raw[raw.history_eligible].copy();assert d.official_difficulty.isin(['简单','中等','困难']).all()
    d['context_key']=d[['image_id','condition','reference_id','reference_version']].apply(lambda r:json.dumps(r.tolist()),axis=1)
    d=add_relative(d);cells=[];prefs=[]
    for scope in ['primary','all_admitted']:
        part=d if scope=='all_admitted' else d[d.scope.eq('primary')]
        for (condition,w,grade),g in part.groupby(['condition','worker_id','official_difficulty']):
            # Collapse targets within an image before reporting each person's image-equal result.
            im=g.groupby('image_id')[['B8L2','D10','B8L2_rank']].mean()
            cells.append(dict(scope=scope,condition=condition,worker_id=w,difficulty=grade,records=len(g),images=len(im),buildings=g.building.nunique(),Q_record_mean=g.B8L2.mean(),Q_image_mean=im.B8L2.mean(),D10_image_mean=im.D10.mean(),relative_rank=im.B8L2_rank.mean()))
        man=part[part.condition.eq('manual')].copy()
        # Reuse the historical preference rule on one row per person-image, avoiding multi-target duplication.
        im=man.groupby(['worker_id','building','image_id','official_difficulty'])[['B8L2','D10','B8L2_rank','D10_rank','peer_n']].mean().reset_index().rename(columns={'building':'building_id'})
        im['difficulty']=im.official_difficulty.map({'简单':'easy','中等':'medium','困难':'hard'})
        p=preferences(im);p['scope']=scope;prefs.append(p)
    cell=pd.DataFrame(cells);save('WORKER_DIFFICULTY_CURRENT',cell);save('DIFFICULTY_PREFERENCES_CURRENT',pd.concat(prefs,ignore_index=True))
    # The primary snapshot must reproduce the already-published v2.1 personnel cells.
    old=pd.read_csv(ROOT/'research/data/releases/v2.1/personnel_descriptive/profiles.csv');old=old[old.panel.eq('manual|ordinary_primary')&old.difficulty.ne('all')].copy();old['difficulty']=old.difficulty.map({'easy':'简单','medium':'中等','hard':'困难'})
    current=cell[cell.scope.eq('primary')&cell.condition.eq('manual')]
    bridge=old.merge(current,on=['worker_id','difficulty'],validate='one_to_one');assert len(bridge)==len(old)==len(current)
    assert np.allclose(bridge.B8L2_mean,bridge.Q_record_mean,atol=1e-9)
    assert (bridge.n==bridge.records).all();save('PRIMARY_DIFFICULTY_PARITY',bridge[['worker_id','difficulty','n','B8L2_mean','Q_record_mean']])
    wide=[]
    for (scope,w),g in cell[cell.condition.eq('manual')].groupby(['scope','worker_id']):
        r=dict(scope=scope,worker_id=w)
        for grade,pref in [('简单','easy'),('中等','medium'),('困难','hard')]:
            z=g[g.difficulty.eq(grade)]
            for field in ['Q_image_mean','images','relative_rank']:r[pref+'_'+field]=z.iloc[0][field] if len(z) else np.nan
        wide.append(r)
    save('MANUAL_WORKER_DIFFICULTY_WIDE',pd.DataFrame(wide))

def main():
    OUT.mkdir(exist_ok=True);raw=pd.read_csv(UP/'classification/RAW_TARGET_RESPONSE_RECORDS.csv.gz',low_memory=False)
    classes();changed_events(raw);difficulty(raw)
    print(pd.read_csv(OUT/'DIFFERENT_SELECTION_SUMMARY.csv').to_string(index=False))
if __name__=='__main__':main()
