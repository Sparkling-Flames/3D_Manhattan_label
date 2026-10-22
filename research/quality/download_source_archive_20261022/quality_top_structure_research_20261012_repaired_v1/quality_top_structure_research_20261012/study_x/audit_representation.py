#!/usr/bin/env python3
"""Audit the four point layers without changing source arrays or guessing pairs.

Use --previous for an extracted prior deliverable or --archive for its ZIP.
New numerical residuals are withheld for the frozen holdout. All-record checks
are mechanical identity/projection checks only. No labels are inferred.
"""
from __future__ import annotations
import argparse,csv,hashlib,io,json,math,pathlib,zipfile
from collections import Counter
import numpy as np

W,H=1024.,512.
BASE='inputs_extracted/quality_cloud_compute_review_20261010'

class Reader:
    def __init__(self,previous=None,archive=None):
        self.previous=pathlib.Path(previous) if previous else None
        self.z=zipfile.ZipFile(archive) if archive else None
        self.prefix='quality_calibration_research_20261011/'
    def bytes(self,p):
        return (self.previous/p).read_bytes() if self.previous else self.z.read(self.prefix+p)
    def json(self,p): return json.loads(self.bytes(p))

def save_json(p,x):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')

def save_csv(p,rows):
    p.parent.mkdir(parents=True,exist_ok=True)
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with p.open('w',encoding='utf-8-sig',newline='') as f:
        wr=csv.DictWriter(f,fieldnames=keys);wr.writeheader()
        for r in rows:wr.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v for k,v in r.items()})

def arr_hash(a):return hashlib.sha256(json.dumps(a,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def wrap(dx):return (np.asarray(dx)+W/2)%W-W/2
def count_quantiles(xs):
    a=np.asarray([x for x in xs if x is not None],float)
    return dict(n=len(a),minimum=float(np.min(a)) if len(a) else None,
                median=float(np.median(a)) if len(a) else None,p90=float(np.quantile(a,.9)) if len(a) else None,
                p95=float(np.quantile(a,.95)) if len(a) else None,maximum=float(np.max(a)) if len(a) else None)

def audit_object(o):
    before=o.get('before_preprocessing_points');raw=o.get('original_export_points')
    pre=o.get('preprocessed_points');final=o.get('points_1024x512');links=o.get('links_zero_based')
    row=dict(object_id=o['object_id'],object_kind=o['object_kind'],image_code=o['image_code'],
             raw_point_count=len(raw or []),before_point_count=len(before or []),
             raw_before_equal=raw==before,preprocessing_status=o.get('preprocessing_status'),
             pairing_basis=o.get('pairing_basis'),order_status=o.get('order_status'),
             ring_confirmed=o.get('ring_confirmed'),original_export_hash=arr_hash(raw),
             before_hash=arr_hash(before),preprocessed_hash=arr_hash(pre),final_hash=arr_hash(final),
             links_hash=arr_hash(links),pair_status='unavailable',pair_n=0,
             pair_mechanically_valid=False,source_midpoint_verified=False,source_ring_view_verified=False,
             raw_mapping_complete=False,raw_mapping_unchanged_coordinates=False,raw_mapping_status='not_checked',
             current_before_changed_from_export=raw!=before,
             has_borrowed_points=bool(o.get('borrowed_point_provenance')),
             point_edits_source=o.get('quality_review_provenance'),
             original_export_indices=o.get('original_export_indices'),
             deleted_previous_point_indices=o.get('deleted_previous_point_indices'),
             initialization_notes=o.get('initialization_notes'),errors=[])
    p=np.asarray(before,float) if before else np.empty((0,2))
    pairs=None
    if p.ndim!=2 or p.shape[1]!=2 or not np.isfinite(p).all():row['pair_status']='invalid_points'
    elif not len(p):row['pair_status']='empty_points'
    elif not links:row['pair_status']='no_established_pairing'
    elif any(len(t)!=2 or any(type(i)is not int for i in t) for t in links):row['pair_status']='invalid_pair_indices'
    elif sorted(i for t in links for i in t)!=list(range(len(p))):row['pair_status']='incomplete_or_duplicate_pairing'
    else:
        pairs=np.asarray(links,int);delta=wrap(p[pairs[:,1],0]-p[pairs[:,0],0])
        row['pair_n']=len(pairs)
        if np.any(abs(delta)>=W/2-1e-8):row['pair_status']='ambiguous_antipodal_midpoint'
        elif np.any(p[pairs[:,0],1]>=p[pairs[:,1],1]):row['pair_status']='top_bottom_role_inverted_or_equal'
        elif np.any((p[:,0]<0)|(p[:,0]>W)|(p[:,1]<0)|(p[:,1]>H)):row['pair_status']='coordinate_out_of_bounds'
        else:
            row['pair_status']='established_complete_pairing';row['pair_mechanically_valid']=True
            row['x_width_endpoint_count']=int(np.sum(p[:,0]==W))
            mids=(p[pairs[:,0],0]+delta/2)%W
            expected=p.copy();expected[pairs[:,0],0]=expected[pairs[:,1],0]=mids
            row['source_midpoint_verified']=pre is not None and np.shape(pre)==np.shape(expected) and bool(np.allclose(pre,expected,rtol=0,atol=1e-8))
            if not row['source_midpoint_verified']:row['errors'].append('preprocessed_not_exact_shortest_arc_midpoint')
            order=o.get('ordered_source_pair_indices');idx=o.get('ordered_source_point_indices')
            if order is not None and idx is not None and sorted(order)==list(range(len(pairs))):
                expected_idx=[i for j in order for i in links[j]]
                row['source_ring_view_verified']=(idx==expected_idx and final==[pre[i] for i in idx] and
                   o.get('matterport_links_zero_based')==[[i,i+1] for i in range(0,len(p),2)])
            if not row['source_ring_view_verified']:row['errors'].append('ring_view_identity_failure')
            row['shared_x_erases_nonzero_gap']=bool(np.any(abs(delta)>1e-8))
            row['cross_seam_pair_count']=int(np.sum(abs(p[pairs[:,1],0]-p[pairs[:,0],0])>W/2))
            row['same_horizon_side_pair_count']=int(np.sum((p[pairs[:,0],1]-H/2)*(p[pairs[:,1],1]-H/2)>=0))
            row['X_pair_rms_px']=float(np.sqrt(np.mean(delta**2)))
            row['X_pair_rms_deg']=row['X_pair_rms_px']*360/W
            row['X_pair_max_px']=float(np.max(abs(delta)))
            row['X_pair_max_deg']=row['X_pair_max_px']*360/W
            row['endpoint_projection_rms_px']=row['X_pair_rms_px']/2
            row['endpoint_projection_rms_deg']=row['X_pair_rms_deg']/2
            row['X_pair_mean_signed_deg']=float(np.mean(delta))*360/W
            row['pair_source_tier']=('explicit_review' if o.get('pairing_basis') in {
                'complete_pairing_review_20260929','user_completed_point_review_20261010',
                'previous_explicit_pairs_plus_x_completion'} else 'existing_recorded_pair_identity')
            inds=o.get('original_export_indices')
            if inds is None and before==raw:inds=list(range(len(p)))
            if inds is not None and len(inds)==len(p) and raw:
                valid=[isinstance(i,int) and not isinstance(i,bool) and 0<=i<len(raw) for i in inds]
                row['raw_mapping_complete']=all(valid) and len(set(inds))==len(inds)
                if row['raw_mapping_complete']:
                    rp=np.asarray(raw,float)[inds];rd=wrap(rp[pairs[:,1],0]-rp[pairs[:,0],0])
                    row['raw_mapping_unchanged_coordinates']=bool(np.array_equal(rp,p))
                    row['raw_mapping_status']='current_pairs_mapped_to_export_indices'
                    row['raw_mapped_pair_rms_deg']=float(np.sqrt(np.mean(rd**2)))*360/W
                    row['raw_mapped_pair_max_deg']=float(np.max(abs(rd)))*360/W
                    row['raw_mapped_not_original_pair_label']=True
                else:row['raw_mapping_status']='added_or_unmapped_points_no_raw_residual'
            else:row['raw_mapping_status']='no_complete_source_identity_map'
    return row

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--previous');ap.add_argument('--archive')
    ap.add_argument('--new-main',default='new_main_snapshot');ap.add_argument('--out',default='study_x/results')
    ap.add_argument('--severe-ledger',default='study_severe/results/ledger_115.json')
    args=ap.parse_args();reader=Reader(args.previous,args.archive);out=pathlib.Path(args.out);new=pathlib.Path(args.new_main)
    data=reader.json(BASE+'/inputs/current_formal_loader_data.json')
    comp=reader.json(BASE+'/results/current_components.json');cb={r['object_id']:r for r in comp}
    tar={r['record_id']:r for r in reader.json(BASE+'/results/target_alignment_ledger.json')}
    hold={r['record_id']:r['held_out_of_sample_and_future_calibration']=='True' for r in csv.DictReader(io.StringIO(reader.bytes(BASE+'/results/room_holdout_manifest.csv').decode('utf-8-sig')))}
    feedback=json.loads((new/'research/quality_severe_feedback_20261011/feedback_overlay.json').read_text())
    fr={r['record_id']:r for r in feedback['records']}
    private=json.loads((new/'research/quality_severe_screen_20261011/selection_private.json').read_text());pr={r['record_id']:r for r in private['cases']}
    displayed=json.loads((new/'research/quality_severe_screen_20261011/review_data.json').read_text());dr={r['id']:r for r in displayed['cases']}
    assert feedback['dataset_id']==private['dataset_id']==displayed['dataset_id']
    severe_ledger_path=pathlib.Path(args.severe_ledger)
    severe_ledger={r['record_id']:r for r in json.loads(severe_ledger_path.read_text())}
    assert set(severe_ledger)==set(fr)
    old=reader.json('work_blind/analysis_input.json');oldq={r['record_id']:r for r in old['quality']}
    objs={o['object_id']:o for o in data['objects']}
    objrows=[audit_object(o) for o in data['objects']]
    rows=[];pairrows=[]
    metric_fields=['X_pair_rms_px','X_pair_rms_deg','X_pair_max_px','X_pair_max_deg','endpoint_projection_rms_px','endpoint_projection_rms_deg','X_pair_mean_signed_deg','raw_mapped_pair_rms_deg','raw_mapped_pair_max_deg']
    for a in objrows:
        if a['object_kind']!='annotation':continue
        o=objs[a['object_id']];c=cb[a['object_id']];rid=c['record_id'];r=dict(a,record_id=rid,worker_id=c['worker_id'],
            image_id=c['image_id'],building_id=c['building_id'],room_id=c['room_id'],held_out=hold[rid],
            formal_primary_included=c['primary_included'],worker_quality_gate=c['worker_quality_gate'],
            target_dev_907=bool(tar[rid]['target_unconfounded_conservative'] and not hold[rid]),
            scope_oos=o.get('scene_oos_status'),scope_doorway=o.get('scene_doorway_status'),
            old_quality_case=oldq.get(rid,{}).get('selection',{}).get('case_id'),
            old_quality_grade=oldq.get(rid,{}).get('answer',{}).get('absolute_quality'),
            new_severe_case=fr.get(rid,{}).get('case_id'),new_review_status=fr.get(rid,{}).get('effective_review_status'),
            new_scope_hold=fr.get(rid,{}).get('calibration_scope_hold_reasons'),
            display_geometry_mode=fr.get(rid,{}).get('geometry_mode'),Q_v11=c.get('Q'),D_deg=c.get('dir'),F_deg=c.get('flat'),
            S_deg=c.get('boundary_rms_deg'),S_top_deg=c.get('S_top_deg'),S_bottom_deg=c.get('S_bottom_deg'),
            I_floor=c.get('iou_2d'),I_official3d=c.get('iou_3d_corner_mean'))
        if rid in fr:
            eligible=severe_ledger[rid]
            r['calibration_barrier_free']=eligible['applicability_known_barrier_free']
            r['calibration_barriers']=eligible['applicability_barriers']
            r['full_quality_geometry_ready']=eligible['full_Q_calibration_ready']
            visible=dr[fr[rid]['case_id']]['raw']
            r['display_raw_matches_current_final']=visible==o.get('points_1024x512')
            r['display_raw_matches_current_before']=visible==o.get('before_preprocessing_points')
            r['display_raw_matches_original_export']=visible==o.get('original_export_points')
            r['original_export_matches_selection_hash']=hashlib.sha256(json.dumps(o.get('original_export_points')).encode()).hexdigest()==pr[rid]['raw_annotation_sha256']
        if hold[rid]:
            for k in metric_fields:r[k]=None
            r['new_metric_policy']='withheld_frozen_holdout'
        else:r['new_metric_policy']='development_diagnostic_only'
        rows.append(r)
        if not hold[rid] and a['pair_mechanically_valid']:
            p=np.asarray(o['before_preprocessing_points'],float)
            for j,(t,b) in enumerate(o['links_zero_based']):
                dx=float(wrap(p[b,0]-p[t,0]));pairrows.append(dict(record_id=rid,object_id=o['object_id'],image_code=o['image_code'],
                    source_pair_index=j,source_top_index=t,source_bottom_index=b,top_label=o['point_labels'][t],bottom_label=o['point_labels'][b],
                    top_x_px=p[t,0],bottom_x_px=p[b,0],top_y_px=p[t,1],bottom_y_px=p[b,1],delta_bottom_minus_top_px=dx,
                    delta_bottom_minus_top_deg=dx*360/W,shared_x_px=float((p[t,0]+dx/2)%W),
                    target_dev_907=r['target_dev_907'],new_severe_case=r['new_severe_case'],old_quality_case=r['old_quality_case']))
    def group_summary(rr):
        ready=[r for r in rr if r['pair_mechanically_valid']]
        return dict(n=len(rr),pair_ready=len(ready),pair_unready=len(rr)-len(ready),
                    images=len({r['image_code'] for r in rr}),pair_status=dict(Counter(r['pair_status'] for r in rr)),
                    changed_from_export=sum(r['current_before_changed_from_export'] for r in rr),
                    nonzero_removed=sum(bool(r.get('shared_x_erases_nonzero_gap')) for r in rr),
                    X_rms_deg=count_quantiles([r.get('X_pair_rms_deg') for r in ready]),
                    X_max_deg=count_quantiles([r.get('X_pair_max_deg') for r in ready]),
                    diagnostic_cut_counts={str(k):sum(r.get('X_pair_max_deg') is not None and r['X_pair_max_deg']>=k for r in ready) for k in [1,2,5,10]},
                    note='cut counts are descriptive angles, not calibrated penalties or grade thresholds')
    dev=[r for r in rows if not r['held_out']];screen_all=[r for r in rows if r['new_severe_case']];screen=[r for r in dev if r['new_severe_case']]
    summary=dict(schema='four_layer_x_representation_audit_v1',main_sha='38e259c043fed0817307dbc3d21c6dba06bd6662',
      object_counts=dict(Counter(r['object_kind'] for r in objrows)),
      all_annotation_mechanical=dict(n=len(rows),held_out=sum(r['held_out'] for r in rows),
          pair_status=dict(Counter(r['pair_status'] for r in rows)),midpoint_failures=sum(bool(r['pair_mechanically_valid'] and not r['source_midpoint_verified']) for r in rows),
          ring_view_failures=sum(bool(r['pair_mechanically_valid'] and not r['source_ring_view_verified']) for r in rows),
          nonzero_gap_erased=sum(bool(r.get('shared_x_erases_nonzero_gap')) for r in rows),
          raw_before_different=sum(r['current_before_changed_from_export'] for r in rows),
          cross_seam_pairs=sum(r.get('cross_seam_pair_count',0) for r in rows)),
      development_all=group_summary(dev),target_dev_907=group_summary([r for r in dev if r['target_dev_907']]),
      quality24=group_summary([r for r in dev if r['old_quality_case']]),screen_nonholdout101=group_summary(screen),
      screen_all115_mechanical=dict(n=len(screen_all),held_out=sum(r['held_out'] for r in screen_all),known_barrier_free=sum(r['calibration_barrier_free'] for r in screen_all)),
      screen_by_status={s:group_summary([r for r in screen if r['new_review_status']==s and r['calibration_barrier_free']]) for s in sorted({r['new_review_status'] for r in screen})},
      screen_selection_holdout_conflict=[{k:r[k] for k in ['record_id','new_severe_case','image_code','new_review_status','new_scope_hold']} for r in screen_all if r['held_out']],
      display_versions=dict(frozen_n=sum(r['display_geometry_mode']=='frozen_geometry' for r in screen_all),
           frozen_final_match=sum(r['display_geometry_mode']=='frozen_geometry' and r['display_raw_matches_current_final'] for r in screen_all),
           frozen_original_match=sum(r['display_geometry_mode']=='frozen_geometry' and r['display_raw_matches_original_export'] for r in screen_all),
           nonfrozen_original_match=sum(r['display_geometry_mode']!='frozen_geometry' and r['display_raw_matches_original_export'] for r in screen_all)),
      formula=dict(delta='((x_bottom-x_top+512)%1024)-512',X_rms='sqrt(mean(delta_px**2))*360/1024',X_max='max(abs(delta_px))*360/1024',
           pair_weight='equal weight per established source pair; not invariant to redundant new pairs',
           endpoint_projection='each endpoint moves delta/2; endpoint RMS = pair RMS/2',
           source='current edited before_preprocessing_points; original_export residual separately mapped by indices only'),
      heldout_policy='Heldout source arrays are accessed for mechanical identity/projection, availability, and zero-versus-nonzero information-loss checks. New residual magnitudes are withheld from the exported heldout rows and excluded from magnitude summaries, example selection, raw-boundary experiments and calibration. Global mechanical counts include heldout; this does not claim the heldout source arrays were never read.')
    save_csv(out/'representation_signals_all3152.csv',rows);save_csv(out/'representation_signals_development.csv',dev)
    save_csv(out/'representation_signals_screen115.csv',screen_all);save_csv(out/'representation_signals_screen_development101.csv',screen);save_csv(out/'representation_signals_quality24.csv',[r for r in dev if r['old_quality_case']])
    save_csv(out/'current_pair_residuals_development.csv',pairrows)
    save_csv(out/'changed_current_input_records.csv',[r for r in rows if r['current_before_changed_from_export']])
    save_json(out/'summary.json',summary)
    input_hashes={p:hashlib.sha256(reader.bytes(p)).hexdigest() for p in [BASE+'/inputs/current_formal_loader_data.json',BASE+'/results/current_components.json',BASE+'/results/target_alignment_ledger.json',BASE+'/results/room_holdout_manifest.csv']}
    input_hashes['new_severe_eligibility_ledger']=hashlib.sha256(severe_ledger_path.read_bytes()).hexdigest()
    save_json(out/'input_hashes.json',input_hashes)
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
