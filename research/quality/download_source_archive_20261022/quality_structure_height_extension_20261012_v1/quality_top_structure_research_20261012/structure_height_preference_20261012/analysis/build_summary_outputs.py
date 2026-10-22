#!/usr/bin/env python3
"""Summarize already computed evidence; this script never fits or relabels.

All plots are scientific data plots. Synthetic points are explicitly identified;
the old ordinal answers and severe-screen answers remain separate data layers.
"""
from pathlib import Path
import csv
import json
import math
import hashlib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
STUDY = HERE.parent


def read_csv(path):
    return list(csv.DictReader(path.open(encoding='utf-8-sig', newline='')))


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)


def save_figure(fig, name):
    (HERE/'figures').mkdir(exist_ok=True)
    fig.savefig(HERE/'figures'/f'{name}.png', dpi=180, bbox_inches='tight', pad_inches=.15)
    fig.savefig(HERE/'figures'/f'{name}.svg', bbox_inches='tight', pad_inches=.15)
    plt.close(fig)


def main():
    out = HERE/'results'; out.mkdir(exist_ok=True)
    real_path = STUDY/'height/results/candidate_scores_39.json'
    real = json.loads(real_path.read_text())
    by_case = {(r.get('old_case_id') or r.get('new_case_id')): r for r in real}
    rank_path = STUDY/'evidence/new_candidate_comparison_log_addendum/old24_rank_summary.csv'
    ranks = {r['method']: r for r in read_csv(rank_path)}
    calibration = json.loads((STUDY/'evidence/new_candidate_comparison_log_addendum/same_budget_two_cutpoint_summary.json').read_text())
    calibration = {r['method']: r for r in calibration}
    methods = ['Q_v11','Q_floor_iou','Q_official_iou3d','Q_no_topS','Q_split_local025',
               'Q_hsplit_top1','Q_hsplit_top1_4','Q_hsplit_top1_16',
               'Q_dbounded1_hsplit','Q_dbounded1_hsplit_weakTop',
               'Q_dbounded2_hsplit','Q_dbounded1_d10_hsplit','Q_dunbounded_hsplit',
               'Q_dbounded1_local05','Q_dbounded1_Fguard','Q_dbounded1_hsplit_logMean']
    comparison = []
    for method in methods:
        r, c = ranks[method], calibration[method]
        comparison.append({'method': method, 'old24_cross_grade_pairs': int(r['pairs']),
            'old24_inversions': int(r['inversions']), 'same_image_pairs': int(r['same_image_code_pairs']),
            'same_image_inversions': int(r['same_image_code_inversions']),
            'same_building_pairs': int(r['same_building_id_pairs']),
            'same_building_inversions': int(r['same_building_id_inversions']),
            'building_LOBO_threshold_step_loss_min': c['total_held_absolute_step_loss_min'],
            'building_LOBO_threshold_step_loss_max': c['total_held_absolute_step_loss_max'],
            'T20': by_case['T20'][method], 'T09': by_case['T09'][method], 'T22': by_case['T22'][method],
            'independent_validation': False, 'error_range_is_confidence_interval': False})
    write_csv(out/'key_candidate_comparison.csv', comparison)
    cases = ['T01','T02','T03','T05','T07','T08','T09','T12','T13','T17','T19','T20','T21','T22','S001','S012','S034','S052','S066','S071','S107']
    columns = ['record_id','image_code','evidence_layer','iou_2d','iou_3d_corner_mean','dir','flat',
               'Hmean','Hlocal','Hstar','Hcenter','S_top_deg','S_bottom_deg']
    write_csv(out/'key_real_cases.csv', [{'case_id':cid, **{k:by_case[cid].get(k) for k in columns},
                  **{k:by_case[cid][k] for k in methods}} for cid in cases])

    controls_path = STUDY/'height/results/matched_control_scores.csv'
    controls = read_csv(controls_path)
    controls_by_id = {r['case_id']:r for r in controls}
    selected_control_ids = [f'matched_s{s}_e0.1_{mode}' for s in ['2','10']
        for mode in ['structure_shear','global_down','local_tilt','local_alternating']]
    keep_control = ['family','horizontal_scale','target_relative_rms_displacement',
        'exact_relative_rms_displacement','shear_corner_departure_deg','iou_2d','dir','flat',
        'Hmean','Hcenter','Q_v11','Q_no_topS','Q_dbounded1_hsplit','Q_dbounded1_d10_hsplit','Q_dbounded2_hsplit']
    write_csv(out/'matched_control_key_comparisons.csv', [
        {'case_id': cid, **{k:controls_by_id[cid].get(k) for k in keep_control}, 'synthetic_no_human_grade': True}
        for cid in selected_control_ids])

    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    fig, axs = plt.subplots(1, 2, figsize=(12,4.5), sharey=True)
    colors = {'structure_shear':'#B6465F','local_tilt':'#3679A8','global_down':'#39805B'}
    for ax, scale in zip(axs, ['2','10']):
        for mode, label in [('structure_shear','Structure shear'),('local_tilt','Local tilt'),('global_down','Level global lowering')]:
            xx, yy, oldyy = [], [], []
            for e in ['0.05','0.1','0.2']:
                r=controls_by_id[f'matched_s{scale}_e{e}_{mode}']
                xx.append(float(e)*100); yy.append(float(r['Q_dbounded1_hsplit'])); oldyy.append(float(r['Q_no_topS']))
            ax.plot(xx,yy,'o-',color=colors[mode],label=label)
            ax.plot(xx,oldyy,':',color=colors[mode],alpha=.7)
        ax.set_title(f'Horizontal scale = {scale} camera heights')
        ax.set_xlabel('Reference-top 3D RMS displacement / GT wall height (%)')
        ax.grid(alpha=.16); ax.set_ylim(0,102)
    axs[0].set_ylabel('Score (higher is better)'); axs[0].legend(loc='lower left',frameon=False)
    fig.suptitle('Synthetic controls: same displacement does not imply same angle\nSolid: bounded D (capacity 1, scale 5 deg); dotted: previous no-top-S',fontsize=12)
    fig.tight_layout(); save_figure(fig,'matched_structure_height_controls')

    # A scale comparison at constant relative level lowering. It is not a
    # sampling distribution or an estimate of an annotator's noise.
    fig, ax = plt.subplots(figsize=(8.5,4.6))
    scales=[.5,2.,10.]
    for method,label,col in [('Q_v11','Old formula','#B6465F'),('Q_hsplit_top1_16','Height split + top S / 16','#A17B2A'),
                             ('Q_dbounded1_hsplit','Bounded D + split height, no top S','#3679A8')]:
        vals=[float(controls_by_id[f'matched_s{s:g}_e0.2_global_down'][method]) for s in scales]
        ax.plot(scales,vals,'o-',label=label,color=col)
    ax.set_xscale('log'); ax.set_xticks(scales,labels=['0.5','2','10']); ax.set_ylim(0,102)
    ax.set_xlabel('Horizontal scale / camera height'); ax.set_ylabel('Score')
    ax.set_title('Synthetic level ceiling lowered by 20% of GT wall height')
    ax.grid(alpha=.15); ax.legend(frameon=False,loc='lower right'); fig.tight_layout()
    save_figure(fig,'global_height_horizontal_scale')

    t20=by_case['T20']
    old_den={'top_S': t20['S_top_deg']**2/32,
             'Hstar': (t20['Hstar']/.5)**2,
             'bottom_S': t20['S_bottom_deg']**2/32}
    no_c=100*t20['iou_2d']/(1+sum(old_den.values()))
    own_d=t20['dir']**2/(t20['dir']**2+25)*.075
    own_f=t20['flat']**2/(t20['flat']**2+4)*.075
    dump(out/'T20_denominator_audit.json', {'record_id':t20['record_id'],'components':old_den,
         'old_Q':t20['Q_v11'],'old_Q_without_DF':no_c,'DF_score_points':no_c-t20['Q_v11'],
         'old_D_fraction_of_preC_base':own_d,'old_F_fraction_of_preC_base':own_f,
         'new_score_is_not_user_assigned':True,'human_target_score_provided':False})
    dump(out/'scope_of_claims.json', {
       'engineering_recomputation':True,'synthetic_human_labels':0,'new_human_labels':0,
       'development_candidate_comparison':True,'independent_validation':False,
       'severe_screen_unchecked_are_negative':False,'fpr_estimable':False,
       'final_quality_cutpoints_frozen':False,'formal_algorithm_replaced':False,
       'repair_is_byte_preserving_separate_deliverable':True,
       'old_D_fraction_upper_bound_of_preC_base':.075*675/(675+25),
       'old_D_fraction_upper_bound_relative_same_F_counterfactual_loose_bound':.075*675/(675+25)/.925})
    source_paths=[real_path,rank_path,controls_path,Path(__file__)]
    dump(out/'summary_input_manifest.json', [{'path':str(p.relative_to(STUDY)),
            'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in source_paths])
    print(json.dumps({'case_rows':len(cases),'comparison_methods':len(methods),'figures':2,'source_labels_changed':False}))


if __name__=='__main__':
    main()
