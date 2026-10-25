#!/usr/bin/env python3
"""Outcome-aware mechanism selection, with its complete finite selection frame saved."""
from pathlib import Path
import hashlib,json
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1];OUT=Path(__file__).resolve().parent
CHOSEN='f261cd4329817662818a5684'

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    path=ROOT/'results/reverse_confirm/EVENT_METRICS.csv.gz'
    d=pd.read_csv(path,low_memory=False)
    q=d.loc[d.method.eq('RFUSE_GEOM_K2')&d.n.eq(12)&d.m.eq(4)].copy()
    cols=['event_id','pool_id','method','image','building','difficulty','phase','n','m','source_class','target_class','source_capacity','target_capacity','block_id','background_id','D','X','Y','Z','A_team_key','B_team_key','C_team_key','A_B8L2','B_B8L2','C_B8L2','B8L2_within','B8L2_cross','B8L2_gap','B8L2_CA','B8L2_CB','A_nodes','B_nodes','C_nodes','geometry_bev_distance_within','geometry_bev_distance_cross','geometry_bev_distance_gap']
    q['whole_target_class']=q.target_capacity.eq(q.m)
    q['ABC_Q_available']=q[['A_B8L2','B_B8L2','C_B8L2']].notna().all(axis=1)
    q[cols+['whole_target_class','ABC_Q_available']].to_csv(OUT/'SELECTION_FRAME_EVENTS.csv.gz',index=False,compression='gzip')
    rows=[]
    for key,z in q.groupby(['image','building','difficulty','phase','source_class','target_class','target_capacity']):
        v=z.loc[z.ABC_Q_available];bg=v.groupby('background_id').B8L2_gap.mean();bl=v.groupby('block_id').B8L2_gap.mean()
        r=dict(zip(['image','building','difficulty','phase','source_class','target_class','target_capacity'],key))
        r.update(attempted_events=len(z),valid_events=len(v),blocks=len(bl),backgrounds=len(bg),positive_events=int(v.B8L2_gap.gt(0).sum()),positive_blocks=int(bl.gt(0).sum()),positive_backgrounds=int(bg.gt(0).sum()),within_Q_mean=v.B8L2_within.mean(),cross_Q_mean=v.B8L2_cross.mean(),Q_gap_median=v.B8L2_gap.median(),Q_CA_median=v.B8L2_CA.median(),Q_CB_median=v.B8L2_CB.median(),shape_gap_mean=v.geometry_bev_distance_gap.mean(),C_more_nodes_events=int((v.C_nodes>v.B_nodes).sum()))
        r['eligible_opportunity_case']=r['target_capacity']==4 and r['difficulty'] in ['中等','困难'] and r['valid_events']>=2 and r['blocks']>=2 and r['backgrounds']>=2 and r['positive_blocks']==r['blocks'] and r['positive_backgrounds']==r['backgrounds']
        r['chosen_image']=r['image']=='B6ByNegPMKs-47'
        rows.append(r)
    s=pd.DataFrame(rows);s.to_csv(OUT/'SELECTION_IMAGE_SUPPORT.csv',index=False)
    selected=q.loc[q.event_id.eq(CHOSEN)].iloc[0];image=q.loc[q.image.eq(selected.image)].copy()
    median=image.B8L2_gap.median();image['distance_from_image_gap_median']=(image.B8L2_gap-median).abs();image['chosen_for_mechanism']=image.event_id.eq(CHOSEN)
    image.to_csv(OUT/'SELECTED_IMAGE_ALL_EVENTS.csv.gz',index=False,compression='gzip')
    assert selected.target_capacity==4
    assert np.isclose(image.loc[image.event_id.eq(CHOSEN),'distance_from_image_gap_median'].iloc[0],image.distance_from_image_gap_median.min())
    assert selected.B8L2_gap==image.B8L2_gap.min()
    exact=pd.read_csv(ROOT/'design/reverse_confirm/EVENTS_EXACT.csv.gz')
    exact.loc[exact.event_id.eq(CHOSEN)].to_csv(OUT/'SELECTED_EVENT_EXACT.csv',index=False)
    q.loc[q.event_id.eq(CHOSEN)].to_csv(OUT/'SELECTED_EVENT_METRICS.csv',index=False)
    labels=pd.read_csv(ROOT/'reverse/REVERSE_LABELS_ALL_LOBO.csv.gz')
    labels=labels.loc[labels.method.eq(selected.method)&labels.heldout_building.eq(selected.building)]
    labels.to_csv(OUT/'SELECTED_FOLD_PERSON_LABELS.csv',index=False)
    centers=pd.read_csv(ROOT/'reverse/REVERSE_CLASS_CENTERS_ALL_LOBO.csv.gz');centers=centers.loc[centers.method.eq(selected.method)&centers.heldout_building.eq(selected.building)];centers.to_csv(OUT/'SELECTED_FOLD_RESPONSE_CENTERS.csv',index=False)
    target=set(labels.loc[labels.class_id.eq(selected.target_class)&labels.known,'worker_id'])
    assert target==set(selected.Z.split('|')) and len(target)==4
    frame=q.loc[q.whole_target_class & q.difficulty.isin(['中等','困难'])]
    receipt={'selection_type':'post-comparison explanatory case; not a new independent effectiveness test','input':str(path.relative_to(ROOT)),'input_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'all_reverse_confirmation_events':len(d),'method_n_m_frame_events':len(q),'method_n_m_frame_images':q.image.nunique(),'method_n_m_frame_buildings':q.building.nunique(),'whole_four_person_medium_hard_events':len(frame),'whole_four_person_medium_hard_images':frame.image.nunique(),'whole_four_person_medium_hard_q_valid_events':int(frame.ABC_Q_available.sum()),'positive_in_each_of_multiple_blocks_backgrounds_images':int(s.eligible_opportunity_case.sum()),'chosen_image':selected.image,'chosen_event':CHOSEN,'reason':'Two different source XY blocks and backgrounds both positive Q gap; A/B have small Q differences; C changes nodes. Chose lower-gap event, equidistant from the two-event image median, not maximum effect. Alternative background has negative shape gap and remains in selected-image context. Cached originals had no qualifying medium/hard image; download only this one.','image_gap_median':median,'chosen_gap':float(selected.B8L2_gap),'chosen_gap_distance_from_median':float(abs(selected.B8L2_gap-median)),'both_backgrounds_shape_gap_positive':False,'lobo_target_members':sorted(target),'all_labels_used_for_event':False}
    (OUT/'SELECTION_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2))
    print(json.dumps(receipt,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
