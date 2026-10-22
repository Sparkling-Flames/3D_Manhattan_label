#!/usr/bin/env python3
"""Descriptive impact only; unknown review status is never a quality label."""
from __future__ import annotations
import argparse,itertools,json,csv
from pathlib import Path
import numpy as np
from scipy.stats import spearmanr
from candidate_functions import score,PRIMARY_METHODS
from run_candidates import readcsv,csvwrite,dump

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=Path.cwd());a=ap.parse_args();r=a.root.resolve();p=r/'top_structure_20261012';o=p/'analysis/representation_and_pool';o.mkdir(parents=True,exist_ok=True)
    b=r/'previous_research/quality_calibration_research_20261011/inputs_extracted/quality_cloud_compute_review_20261010'
    filters=json.loads((p/'evidence/results/development_907_filter.json').read_text());cs={x['record_id']:x for x in json.loads((b/'results/current_components.json').read_text())};xs={x['record_id']:x for x in readcsv(p/'representation/results/representation_signals_all3152.csv')};raw={x['record_id']:x for x in readcsv(p/'representation/results/raw_boundary_cases.csv')}
    rows=[]
    for f in filters:
        if not f['descriptive_development_allowed']:continue
        c=cs[f['record_id']];x=xs[f['record_id']];assert x['held_out']=='False' and x['pair_mechanically_valid']=='True' and x['source_midpoint_verified']=='True' and x['source_ring_view_verified']=='True';z={**c,'X_rms_deg':float(x['X_pair_rms_deg']),'X_max_deg':float(x['X_pair_max_deg'])}
        z['S_top_raw_deg']=float(raw[f['record_id']]['S_top_raw_deg']);z['S_bottom_raw_deg']=float(raw[f['record_id']]['S_bottom_raw_deg'])
        scores=score(z);row={k:f[k] for k in ['record_id','image_code','image_id','worker_id','building_id','room_id','room_group','applicability_confirmed']};row.update({k:c[k] for k in ['iou_2d','S_top_deg','S_bottom_deg','Hstar','Hmean','Hlocal','dir','flat']})
        row.update(X_rms_deg=z['X_rms_deg'],X_max_deg=z['X_max_deg'],**scores);rows.append(row)
    csvwrite(o/'development_scores_907.csv',rows)
    delta_summary=[];sameimage=[]
    for m in PRIMARY_METHODS+['Q_no_top_Xrms8','Q_no_top_Xmax8']:
        for baseline in ['Q_v11','Q_no_topS']:
            ds=np.array([x[m]-x[baseline] for x in rows]);delta_summary.append({'method':m,'baseline':baseline,'records':len(rows),'median_delta_Q':float(np.median(ds)),'min_delta_Q':float(ds.min()),'max_delta_Q':float(ds.max()),'changed_more_than_5_score_points':int((abs(ds)>5).sum()),'changed_more_than_20_score_points':int((abs(ds)>20).sum()),'count_thresholds_are_descriptive_not_quality_levels':True})
        for image in sorted({x['image_code'] for x in rows}):
            rr=[x for x in rows if x['image_code']==image];pairs=0;flips=0;ties=0
            for u,v in itertools.combinations(rr,2):
                sa=np.sign(u['Q_v11']-v['Q_v11']);sb=np.sign(u[m]-v[m]);pairs+=1
                flips+=sa*sb<0;ties+=sa==0 or sb==0
            sameimage.append({'method':m,'image_code':image,'records':len(rr),'pairs':pairs,'rank_reversals_vs_v11':int(flips),'ties_either':int(ties),'no_human_accuracy_claim':True})
    csvwrite(o/'development_delta_summaries.csv',delta_summary);csvwrite(o/'development_same_image_order_changes.csv',sameimage)
    # Inspect why adding a raw-input term helps/hurts the selected old labels.
    real=json.loads((p/'analysis/results/candidate_scores_39.json').read_text());rb={x['record_id']:x for x in real};old=json.loads((r/'study_borderline/results/old24_evidence.json').read_text());changes=[]
    for aa,bb in itertools.combinations(old,2):
        if aa['quality_ordinal_original']==bb['quality_ordinal_original']:continue
        a1,b1=(aa,bb) if aa['quality_ordinal_original']<bb['quality_ordinal_original'] else (bb,aa);u,v=rb[a1['record_id']],rb[b1['record_id']]
        for m in ['Q_no_top_Xrms8','Q_no_top_Xmax8']:
            oldbad=u['Q_no_topS']<v['Q_no_topS'];newbad=u[m]<v[m]
            if oldbad!=newbad:changes.append({'method':m,'better_case':a1['case_id'],'worse_case':b1['case_id'],'same_image':a1['image_code']==b1['image_code'],'change':'fixed_original_order' if oldbad else 'broke_original_order','before_margin':u['Q_no_topS']-v['Q_no_topS'],'after_margin':u[m]-v[m]})
    csvwrite(o/'x_old24_changed_orders.csv',changes)
    controls=[]
    for x in readcsv(p/'analysis/results/candidate_scores_x_controls.csv'):
        if x['status']!='available':continue
        z={k:float(x[k]) for k in ['X_rms_deg','X_max_deg','Q_rawS_same_parameters','Q_no_topS','Q_no_top_Xrms8','Q_no_top_Xmax8']}
        controls.append({'case_id':x['case_id'],**z,'Q_rawS_then_Xrms8_diagnostic':z['Q_rawS_same_parameters']/(1+(z['X_rms_deg']/8)**2),'Q_rawS_then_Xmax8_diagnostic':z['Q_rawS_same_parameters']/(1+(z['X_max_deg']/8)**2),'double_response_not_automatically_double_counting':True})
    csvwrite(o/'raw_boundary_plus_x_control_diagnostic.csv',controls)
    # Correlations are descriptive; controlled opposed shifts establish the
    # exact information-loss counterexample, not a low correlation claim.
    corr=[]
    for k in ['dir','flat','Hstar','S_top_deg','S_bottom_deg']:
        for xk in ['X_rms_deg','X_max_deg']:
            corr.append({'a':xk,'b':k,'n':len(rows),'spearman':float(spearmanr([x[xk] for x in rows],[x[k] for x in rows]).statistic),'descriptive_not_independence_proof':True})
    csvwrite(o/'component_correlations_907.csv',corr)
    summary={'unlabeled_development_records':len(rows),'images':len({x['image_id'] for x in rows}),'workers':len({x['worker_id'] for x in rows}),'applicability_explicit':sum(x['applicability_confirmed'] for x in rows),'unknown_is_not_approved':True,'no_severe_prevalence_or_FPR_calculated':True,'current_paired_gap_nonzero':sum(x['X_max_deg']>1e-8 for x in rows),'original_raw_errors_not_repenalized':True,'heldout_used':0,'x_scores_compare_current_input_quality_only':'A standardized fused endpoint without a pre-average source layer has X=None, not an invented zero of human error.'}
    dump(o/'summary.json',summary);print(json.dumps(summary,ensure_ascii=False))
if __name__=='__main__':main()
