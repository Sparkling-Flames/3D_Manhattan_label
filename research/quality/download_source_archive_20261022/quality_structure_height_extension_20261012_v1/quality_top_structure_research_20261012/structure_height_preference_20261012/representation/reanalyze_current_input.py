#!/usr/bin/env python3
"""Current-version input diagnostics, explicitly separate from result score.

Uses recorded pairing only. No source arrays, labels, references or fusion
outputs are changed. Mathematical score probes are not formal replacements.
"""
from pathlib import Path
import argparse,csv,hashlib,itertools,json,sys
import numpy as np

def dump(p,x):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def csvout(p,rows):
    p.parent.mkdir(parents=True,exist_ok=True)
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with p.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def readcsv(p):return list(csv.DictReader(p.open(encoding='utf-8-sig')))
def wrap(x):return (np.asarray(x)+512)%1024-512
def pair_values(p,links):
    p=np.asarray(p,float);li=np.asarray(links,int)
    assert len(p)==2*len(li) and sorted(li.reshape(-1).tolist())==list(range(len(p)))
    d=wrap(p[li[:,1],0]-p[li[:,0],0])*360/1024
    if np.any(abs(d)>=180-1e-8):raise ValueError('ambiguous_antipodal_pair')
    return d
def probes(base,xr,xm):
    return {'processed_score':float(base),'input_probe_Xrms8':float(base)/(1+(xr/8)**2),
            'input_probe_Xmax8':float(base)/(1+(xm/8)**2)}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[2]);ap.add_argument('--out',type=Path);a=ap.parse_args();root=a.root.resolve()
    out=a.out or root/'structure_height_preference_20261012/representation/results';out.mkdir(parents=True,exist_ok=True)
    b=root/'previous_research/quality_calibration_research_20261011/inputs_extracted/quality_cloud_compute_review_20261010'
    p=root/'top_structure_20261012';new=root/'structure_height_preference_20261012';ev=new/'evidence/results'
    sys.path[:0]=[str(root/'study_x'),str(p/'mechanisms'),str(b/'frozen/scope_engine/core'),str(new/'height')]
    from audit_representation import audit_object
    from quality_v11 import score_geometry
    from centered_height import centered_height_components
    from candidate_functions import score
    objects={o['object_id']:o for o in json.loads((b/'inputs/current_formal_loader_data.json').read_text())['objects']}
    comp={r['record_id']:r for r in json.loads((b/'results/current_components.json').read_text())}
    sig={r['record_id']:r for r in readcsv(p/'representation/results/representation_signals_all3152.csv')}
    hset={r['record_id'] for r in readcsv(b/'results/room_holdout_manifest.csv') if r['held_out_of_sample_and_future_calibration']=='True'}
    registry=json.loads((new/'inputs/main_snapshot/research/quality_holdout_exposure_correction_20261011/exposure_registry.json').read_text())
    exposed={r['record_id'] for r in registry['screen_records_in_original_holdout']};exgroups=set(registry['groups_touched_by_this_screen'])
    rr=json.loads((ev/'numerical_evidence_39.json').read_text());ee={r['record_id']:r for r in rr}
    dd=json.loads((ev/'development_907_filter.json').read_text());dev={r['record_id']:r for r in dd if r['descriptive_development_allowed']}
    selected=sorted(set(dev)|set(ee));assert len(selected)==922 and not set(selected)&(hset|exposed)
    metrics={r['record_id']:r for r in json.loads((p/'analysis/results/candidate_scores_39.json').read_text())}
    raw={r['record_id']:r for r in readcsv(p/'representation/results/raw_boundary_cases.csv')}
    rows=[];parity=[]
    for rid in selected:
        meta=dev.get(rid,ee.get(rid));assert meta['room_group'] not in exgroups
        c=comp[rid];o=objects[c['object_id']];audit=audit_object(o)
        assert audit['pair_mechanically_valid'] and audit['source_midpoint_verified'] and audit['source_ring_view_verified']
        d=pair_values(o['before_preprocessing_points'],o['links_zero_based']);xr=float(np.sqrt(np.mean(d*d)));xm=float(max(abs(d)))
        parity.extend([abs(xr-float(sig[rid]['X_pair_rms_deg'])),abs(xm-float(sig[rid]['X_pair_max_deg']))])
        row={'record_id':rid,'image_code':c['image_code'],'object_id':c['object_id'],'worker_id':c['worker_id'],
             'room_group':meta['room_group'],'in_dev907':rid in dev,'in_quality39':rid in ee,
             'pairing_basis':o.get('pairing_basis'),'ring_confirmed':o.get('ring_confirmed'),
             'n_pairs':len(d),'export_equals_current_before':o['original_export_points']==o['before_preprocessing_points'],
             'current_before_equals_shared':o['before_preprocessing_points']==o['preprocessed_points'],
             'X_rms_deg':xr,'X_max_deg':xm,'normalization_endpoint_azimuth_rms_deg':xr/2,
             'normalization_endpoint_azimuth_max_deg':xm/2,'pair_units_are_azimuth_not_full_ray_angle':True,
             'S_top_raw_deg':float(raw[rid]['S_top_raw_deg']),'S_bottom_raw_deg':float(raw[rid]['S_bottom_raw_deg']),
             'raw_to_shared_boundary_rms_deg':float(raw[rid]['raw_to_shared_boundary_rms_deg']),
             'raw_minus_shared_boundary_rms_deg':float(raw[rid]['raw_minus_shared_rms_deg'])}
        if rid in metrics:
            m=metrics[rid];ss=score(m);row.update(case_id=m['old_case_id'] or m['new_case_id'])
            for mode in ['Q_no_topS','Q_dbounded1_hsplit']:
                row.update({mode+'__'+k:v for k,v in probes(ss[mode],xr,xm).items()})
        rows.append(row)
    csvout(out/'current_input_diagnostics_922.csv',rows)
    controls=json.loads((p/'representation/results/controlled_x_design.json').read_text())['cases']
    details={r['case_id']:r for r in json.loads((p/'representation/results/controlled_x_details.json').read_text())}
    cr=[];controlparity=[]
    for c in controls:
        q=np.asarray(c['raw_points']);links=[[i,i+1] for i in range(0,len(q),2)]
        row={'case_id':c['case_id'],'synthetic_not_person_error_distribution':True,'pairs':len(links)}
        try:d=pair_values(q,links)
        except ValueError as e:
            row.update(status='unavailable',reason=str(e));cr.append(row);continue
        xr=float(np.sqrt(np.mean(d*d)));xm=float(max(abs(d)));row.update(X_rms_deg=xr,X_max_deg=xm)
        if c['case_id'] not in details:raise AssertionError('No invented geometry')
        z=details[c['case_id']];sc=score_geometry(z['shared_geometry'],c['reference']);assert sc['status']=='available'
        controlparity.append(abs(sc['quality_score']-z['score']['quality_score']))
        m=sc['metrics'].copy();m.update(centered_height_components(z['shared_geometry'],c['reference']));m.update(X_rms_deg=xr,X_max_deg=xm)
        s=score(m);row.update(status='available',I3=s['Q_official_iou3d'],S_top=m['S_top_deg'],S_bottom=m['S_bottom_deg'],Hmean=m['Hmean'],Hcenter=m['Hcenter'],D=m['dir'],F=m['flat'])
        for mode in ['Q_no_topS','Q_dbounded1_hsplit']:
            row.update({mode+'__'+k:v for k,v in probes(s[mode],xr,xm).items()})
        cr.append(row)
    csvout(out/'controlled_input_vs_result.csv',cr)
    old=json.loads((root/'study_borderline/results/old24_evidence.json').read_text());by={r['record_id']:r for r in rows}
    ranking=[];changed=[]
    for mode in ['Q_no_topS','Q_dbounded1_hsplit']:
        for tail in ['processed_score','input_probe_Xrms8','input_probe_Xmax8']:
            key=mode+'__'+tail;bad=0;den=0;same=0;samebad=0
            for u,v in itertools.combinations(old,2):
                if u['quality_ordinal_original']==v['quality_ordinal_original']:continue
                if u['quality_ordinal_original']>v['quality_ordinal_original']:u,v=v,u
                x,y=by[u['record_id']],by[v['record_id']];err=x[key]<y[key];bad+=err;den+=1
                si=u['image_code']==v['image_code'];same+=si;samebad+=si and err
                base=mode+'__processed_score';before=x[base]<y[base]
                if err!=before:changed.append({'method':key,'better_case_received':u['case_id'],'worse_case_received':v['case_id'],'same_image':si,'change':'fixed_received_order' if before else 'broke_received_order'})
            ranking.append({'method':key,'records':24,'cross_grade_pairs':den,'inversions':int(bad),'same_image_pairs':same,'same_image_inversions':int(samebad),'developer_data_no_validation_claim':True})
    csvout(out/'old24_input_score_probes.csv',ranking);csvout(out/'old24_changed_pairs.csv',changed)
    w19=[r for r in json.loads((ev/'qualification_ledger_115.json').read_text()) if r['worker_id']=='W019']
    dump(out/'W019_status_preserved.json',w19)
    summary={'selected_records':len(rows),'dev907':len(dev),'numerical_evidence39':len(ee),'distinct_images':len({r['image_code'] for r in rows}),
       'source_versions_rechecked':True,'residual_parity_max_deg':max(parity),'controlled_frozen_oldQ_parity_max':max(controlparity),
       'raw_diagnostics_available':len(rows),'original_holdout_or_exposure_used':0,'new_human_labels_created':0,
       'dev907_current_nonzero':sum(r['in_dev907'] and r['X_max_deg']>1e-8 for r in rows),
       'dev907_export_current_different':sum(r['in_dev907'] and not r['export_equals_current_before'] for r in rows),
       'quality39_export_current_different':sum(r['in_quality39'] and not r['export_equals_current_before'] for r in rows),
       'quality39_current_nonzero':sum(r['in_quality39'] and r['X_max_deg']>1e-8 for r in rows),
       'old24_score_probes':ranking,'new_parameters_fitted':False,'input_grade_not_inferred_from_processed_review':True,
       'conclusion':'平均x丢失真实当前输入差异；诊断可保留，入分权重和其与共享x结果的共同用途尚无已审原始输入证据。等点权RMS会被冗余正确点稀释，MAX忽略范围。两种总分均为候选语义探针。'}
    dump(out/'summary.json',summary)
    dump(out/'input_manifest.json',{'files':{str(f.relative_to(root)):sha(f) for f in [b/'inputs/current_formal_loader_data.json',b/'results/current_components.json',b/'results/room_holdout_manifest.csv',ev/'numerical_evidence_39.json',ev/'development_907_filter.json',new/'inputs/main_snapshot/research/quality_holdout_exposure_correction_20261011/exposure_registry.json']}})
    print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
