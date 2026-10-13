#!/usr/bin/env python3
"""Fixed-reference formula impact, routing/formula factorial attribution, and fusion replay.

This module consumes externally admitted reference routes. It never changes a
gate, assigns a human grade, fits parameters, or recomputes a fusion algorithm.
"""
from __future__ import annotations
import argparse, csv, hashlib, json, math, sys
from collections import Counter, defaultdict
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'calibration'))
sys.path.insert(0,str(ROOT/'experiments'))
from score import BASELINE, score_metrics
from structural_features import direction_descriptors, jointly_optimized_hinge

def load(p): return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,x):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def csvout(p,rows):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with p.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader()
        w.writerows({k:(json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v) for k,v in r.items()} for r in rows)
def summarize(a):
    a=[float(x) for x in a if x is not None and math.isfinite(float(x))]
    if not a:return {'n':0,'min':None,'median':None,'mean':None,'max':None}
    return dict(n=len(a),min=min(a),median=float(np.median(a)),mean=float(np.mean(a)),max=max(a))
def descriptor(geometry,configs):
    d=direction_descriptors(geometry['bottom3d'])
    out=dict(moment4=d['weighted_abs_moments_deg_power']['p4'],
             excess2={k:v['positive_part_m2_deg2'] for k,v in d['excess_by_threshold_deg'].items()},joint_hinge={})
    for c in configs.values():
        if c['family']=='joint_hinge':
            t=c['tail_threshold'];g=c['hinge_weight'];key=f't{t:g}_g{g:g}'
            out['joint_hinge'][key]=jointly_optimized_hinge(d,t,g)['value_deg2']
    return out
def candidate_metric(r):
    if not r or r.get('floor_status')!='available':return None
    return dict(I=r['I'],Sb=r['Sb_deg'],D=r['D_deg'],
                Hm=r.get('Hm') if r.get('full_status')=='available' else None,
                Hc=r.get('Hc') if r.get('full_status')=='available' else None)
def evaluate(m,c,d):
    if m is None:return dict(status='unavailable',score=None,floor_score=None,reason='missing_or_ineligible_geometry_metric')
    return score_metrics(m,c,d)
def difference(a,b):return a-b if a is not None and b is not None else None
def independent_baseline(m):
    return 100*min(1.,m['iou_2d'])/(1+m['S_bottom_deg']**2/32+1.5*m['dir']**2/(m['dir']**2+37.5)+(m['Hmean']/.8)**2+(m['Hcenter']/.25)**2)

def fixed_record_impact(root,source,configs,out):
    data=load(source/'inputs/calibration_records.json');local=load(root/'sources/main/research/quality_parallel_local_20261012/record_results.json')
    gates={r['record_id']:r for r in local['rows']};raw={r['object_id']:r for r in load(source/'input_quality/results/source_layers_922.json')}
    rows=[];maxbaseline=0.;maxinput=0.
    for r in data['rows']:
        gate=gates[r['id']];assert gate['object_id']==r['object_id'] and gate['image_id']==r['image_id']
        assert gate['current_snapshot_matches'];assert gate['input_version']=='calibration_20261012:'+r['current_points_sha256']
        d=descriptor(data['geometries'][r['object_id']],configs)
        scores={name:score_metrics(r['metrics'],c,d) for name,c in configs.items()}
        old=score_metrics(r['metrics'],BASELINE,d)
        maxbaseline=max(maxbaseline,abs(old['score']-independent_baseline(r['metrics'])),abs(old['score']-gate['scores']['P_tied_quad08']))
        rs=raw[r['object_id']];p=np.asarray(rs['before_preprocessing_points']);links=np.asarray(rs['links_zero_based']);delta=(p[links[:,0],0]-p[links[:,1],0]+512)%1024-512
        xrms=float(np.sqrt(np.mean(delta**2))*360/1024);maxinput=max(maxinput,abs(xrms-gate['raw_input']['X_rms_deg']))
        rows.append(dict(record_id=r['id'],object_id=r['object_id'],image_id=r['image_id'],image_code=r['image_code'],building_id=r['building_id'],worker_id=r['worker_id'],condition=gate['condition'],reference_object_id=r['reference_object_id'],reference_version=gate['reference_version'],dataset_sha256=sha(source/'inputs/calibration_records.json'),current_points_sha256=r['current_points_sha256'],reference_points_sha256=r['reference_points_sha256'],legacy_input_version=gate['input_version'],conditional_personnel_eligible=gate['conditional_personnel_eligible'],use_barriers=gate['use_barriers'],current_formal_gate=gate['current_formal_gate'],pair_delta_rms_deg=xrms,endpoint_adjustment_rms_deg=xrms/2,raw_points=rs['before_preprocessing_points'],raw_links=rs['links_zero_based'],mean_x_ordered_points=rs['points_1024x512'],metrics=r['metrics'],baseline=old,candidates=scores,official_iou3d_x100=gate['scores']['Q_official_iou3d'],no_new_grade=None))
    dump(out/'fixed_reference_922.json',dict(schema='new_formula_fixed_reference_v1',rows=rows,independent_baseline_max_abs_difference=maxbaseline,independent_raw_X_max_abs_difference_deg=maxinput,reference_protocol='unchanged exact frozen reference; all old gates retained'))
    wide=[]
    for r in rows:
        w={k:r[k] for k in ['record_id','object_id','image_code','worker_id','condition','reference_object_id','conditional_personnel_eligible','pair_delta_rms_deg','endpoint_adjustment_rms_deg']}
        w['baseline_Q']=r['baseline']['score'];w['official_iou3d_x100']=r['official_iou3d_x100']
        for name,v in r['candidates'].items():w[name]=v['score'];w[name+'_minus_baseline']=difference(v['score'],w['baseline_Q'])
        wide.append(w)
    csvout(out/'fixed_reference_922.csv',wide)
    eligible=[r for r in rows if r['conditional_personnel_eligible']];assert len(eligible)==143;assert all(r['worker_id']!='W019' for r in eligible)
    groups=defaultdict(list)
    for r in eligible:groups[(r['image_id'],r['reference_object_id'],r['condition'])].append(r)
    pairrows=[]
    for key,rr in groups.items():
        for i,a in enumerate(rr):
            for b in rr[i+1:]:
                old=a['baseline']['score']-b['baseline']['score']
                pairrows.append(dict(image_id=key[0],reference_object_id=key[1],condition=key[2],A=a['record_id'],B=b['record_id'],baseline_gap=old,new_gaps={n:a['candidates'][n]['score']-b['candidates'][n]['score'] for n in configs},strict_reversal={n:old*(a['candidates'][n]['score']-b['candidates'][n]['score'])<-1e-10 for n in configs}))
    byrid={r['record_id']:r for r in rows};coordinate_groups={r['id']:r['coordinate_hash'] for r in load(root/'calibration/inputs/search_inputs.json')['rows']}
    for p in pairrows:
        p['same_coordinate_hash']=coordinate_groups[p['A']]==coordinate_groups[p['B']]
        p['both_cross_worker']=byrid[p['A']]['worker_id']!=byrid[p['B']]['worker_id']
        p['strict_comparable']={n:not p['same_coordinate_hash'] and abs(p['baseline_gap'])>=1e-10 and abs(p['new_gaps'][n])>=1e-10 for n in configs}
    dump(out/'same_condition_pairs.json',dict(rows=pairrows,independent_human_labels=False))
    # Replicate the previous equal-image, within-image/ref/condition centering.
    cells=[];worker_cells=defaultdict(list)
    for key,rr in groups.items():
        wr=defaultdict(list)
        for r in rr:wr[r['worker_id']].append(r)
        means={w:{n:float(np.mean([r['baseline']['score'] if n=='baseline' else r['candidates'][n]['score'] for r in rs])) for n in ['baseline',*configs]} for w,rs in wr.items()}
        cellmean={n:float(np.mean([v[n] for v in means.values()])) for n in ['baseline',*configs]}
        for w,v in means.items():
            row=dict(image_id=key[0],reference_id=key[1],condition=key[2],building_id=rr[0]['building_id'],worker_id=w,record_ids=[r['record_id'] for r in wr[w]],within_cell_difference={n:v[n]-cellmean[n] for n in v})
            cells.append(row);worker_cells[(w,key[2])].append(row)
    workers=[]
    oldworkers={(w['worker_id'],w['condition']):w for w in load(root/'sources/main/research/quality_parallel_local_20261012/worker_conditions.json')['workers']}
    maxcentering=0.
    for (w,cond),cc in sorted(worker_cells.items()):
        buildings=sorted({r['building_id'] for r in cc});results={}
        for n in ['baseline',*configs]:
            value=float(np.mean([r['within_cell_difference'][n] for r in cc]));leave=[float(np.mean([r['within_cell_difference'][n] for r in cc if r['building_id']!=b])) for b in buildings] if len(buildings)>1 else []
            results[n]=dict(mean_within_cell_difference=value,leave_one_building_range=[min(leave),max(leave)] if leave else None)
        maxcentering=max(maxcentering,abs(results['baseline']['mean_within_cell_difference']-oldworkers[(w,cond)]['results']['P_tied_quad08']['mean_within_cell_difference']))
        workers.append(dict(worker_id=w,condition=cond,shared_images=len(cc),buildings=buildings,results=results,not_a_worker_ability_ranking=True))
    dump(out/'worker_conditions_new.json',dict(cells=cells,workers=workers,baseline_independent_centering_max_abs_difference=maxcentering,confidence_interval=False,scope='same 143 eligible records only; unchanged reference, gate and observed image panel'))
    return dict(fixed_rows=len(rows),eligible_rows=len(eligible),eligible_images=len({r['image_id'] for r in eligible}),worker_condition_rows=len(workers),same_condition_pairs=len(pairrows),same_coordinate_hash_pairs=sum(r['same_coordinate_hash'] for r in pairrows),strict_geometry_distinct_pairs={n:sum(r['strict_comparable'][n] for r in pairrows) for n in configs},baseline_scalar_max_abs_difference=maxbaseline,raw_X_max_abs_difference_deg=maxinput,centering_max_abs_difference=maxcentering,all922_changes={n:summarize(r['candidates'][n]['score']-r['baseline']['score'] for r in rows) for n in configs},eligible143_changes={n:summarize(r['candidates'][n]['score']-r['baseline']['score'] for r in eligible) for n in configs},eligible143_strict_reversals={n:sum(r['strict_reversal'][n] for r in pairrows) for n in configs})

def matrix_for(old,new,configs,d):
    oldbase=evaluate(old,BASELINE,d);newbase=evaluate(new,BASELINE,d);matrix={}
    for n,c in configs.items():
        oldnew=evaluate(old,c,d);newnew=evaluate(new,c,d);mm={}
        for kind,field in [('full','score'),('floor','floor_score')]:
            q00=oldbase[field];q10=newbase[field];q01=oldnew[field];q11=newnew[field];complete=all(x is not None for x in [q00,q10,q01,q11])
            mm[kind]=dict(old_reference_old_formula=q00,new_route_old_formula=q10,old_reference_new_formula=q01,new_route_new_formula=q11,common_computable=complete,reference_effect_old_formula=difference(q10,q00),formula_effect_old_reference=difference(q01,q00),formula_effect_new_reference=difference(q11,q10),interaction=(q11-q10-q01+q00) if complete else None)
        matrix[n]=mm
    return matrix

def four_way(root,configs,out):
    data=load(root/'routing/inputs/prepared_input.json');geoms={r['record_id']:r['geometry'] for r in data['records']};routes=load(root/'routing/results/routes.json')['rows'];allm=load(root/'routing/results/all_candidate_metrics.json')['rows'];by={(r['record_id'],r['candidate_id']):r for r in allm};rows=[]
    for r in routes:
        rid=r['record_id'];oldid=r.get('previous_fixed_candidate_id');newid=r.get('selected_candidate_id');originalid=r.get('historical_original_candidate_id');old=by.get((rid,oldid));new=by.get((rid,newid));d=descriptor(geoms[rid],configs) if geoms.get(rid) else None
        status=r['status'];om=candidate_metric(old) if status=='available' else None;nm=candidate_metric(new) if status=='available' else None
        oldbase=evaluate(om,BASELINE,d);newbase=evaluate(nm,BASELINE,d);matrix={}
        for n,c in configs.items():
            oldnew=evaluate(om,c,d);newnew=evaluate(nm,c,d);mm={}
            for kind,field in [('full','score'),('floor','floor_score')]:
                q00=oldbase[field];q10=newbase[field];q01=oldnew[field];q11=newnew[field]
                complete=all(x is not None for x in [q00,q10,q01,q11])
                mm[kind]=dict(old_reference_old_formula=q00,new_route_old_formula=q10,old_reference_new_formula=q01,new_route_new_formula=q11,common_computable=complete,reference_effect_old_formula=difference(q10,q00),formula_effect_old_reference=difference(q01,q00),formula_effect_new_reference=difference(q11,q10),interaction=(q11-q10-q01+q00) if complete else None)
            matrix[n]=mm
        admitted=bool(old and old.get('admitted_for_routing') and new and new.get('admitted_for_routing'))
        rows.append(dict(record_id=rid,object_id=r['object_id'],image_code=r['image_code'],image_id=r['image_id'],worker_id=r['worker_id'],old_fixed_candidate_id=oldid,new_candidate_id=newid,historical_original_candidate_id=originalid,reference_changed=oldid!=newid,both_references_admitted=admitted,route_status=status,route_reason=r.get('route_reason'),uncertainty=r.get('uncertainty'),current_formal_gate=r['current_formal_gate'],original_use_barriers=r['original_use_barriers'],original_conditional_personnel_eligible=r['original_conditional_personnel_eligible'],old_full_reference_available=bool(old and old.get('full_reference_available')),new_full_reference_available=bool(new and new.get('full_reference_available')),matrix=matrix,raw_input_diagnostics=r.get('raw_input_diagnostics'),official_IoU3D_same_old_reference=old.get('IoU3D_corner_mean') if old and admitted else None,official_IoU3D_same_new_reference=new.get('IoU3D_corner_mean') if new and admitted else None))
        original=by.get((rid,originalid));hm=candidate_metric(original) if status=='available' else None
        rows[-1]['historical_original_matrix']=matrix_for(hm,nm,configs,d)
        rows[-1]['historical_original_both_admitted']=bool(original and original.get('admitted_for_routing') and new and new.get('admitted_for_routing'))
        rows[-1]['historical_original_reference_changed']=originalid!=newid
        image=next(x for x in data['candidate_images'] if x['image_id']==r['image_id'])
        rows[-1]['image_has_two_distinct_legal_full_references']=sum(c['admitted_for_routing'] and c['full_reference_available'] for c in image['candidates'])>=2
    dump(out/'reference_formula_four_way.json',dict(schema='reference_formula_factorial_v1',old_reference_definition='previous fixed selected reference in the current loader/source, with historical original GT retained separately',rows=rows,no_height_imputation=True,no_human_reference_accuracy_claim=True))
    wide=[]
    for r in rows:
        for n,m in r['matrix'].items():
            for kind,q in m.items():wide.append({k:r[k] for k in ['record_id','image_code','old_fixed_candidate_id','new_candidate_id','reference_changed','both_references_admitted','route_status']}|dict(candidate=n,score_kind=kind,**q))
    csvout(out/'reference_formula_four_way.csv',wide)
    csvout(out/'historical_original_four_way.csv',[dict(record_id=r['record_id'],image_code=r['image_code'],original_candidate_id=r['historical_original_candidate_id'],new_candidate_id=r['new_candidate_id'],both_references_admitted=r['historical_original_both_admitted'],candidate=n,score_kind=kind,**q) for r in rows for n,m in r['historical_original_matrix'].items() for kind,q in m.items()])
    result={}
    for n in configs:
        result[n]={}
        for kind in ['full','floor']:
            cc=[r for r in rows if r['both_references_admitted'] and r['matrix'][n][kind]['common_computable']];changed=[r for r in cc if r['reference_changed']]
            result[n][kind]=dict(n_common=len(cc),images=len({r['image_id'] for r in cc}),reference_changed_count=len(changed),reference_changed_images=sorted({r['image_code'] for r in changed}),reference_effect=summarize(r['matrix'][n][kind]['reference_effect_old_formula'] for r in cc),formula_effect_at_new_reference=summarize(r['matrix'][n][kind]['formula_effect_new_reference'] for r in cc),interaction=summarize(r['matrix'][n][kind]['interaction'] for r in cc))
            fullcap=[r for r in cc if r['image_has_two_distinct_legal_full_references']]
            result[n][kind]['subset_two_distinct_legal_full_references']=dict(n=len(fullcap),record_ids=[r['record_id'] for r in fullcap],changed=sum(r['reference_changed'] for r in fullcap))
            hh=[r for r in rows if r['historical_original_both_admitted'] and r['historical_original_matrix'][n][kind]['common_computable']]
            result[n][kind]['historical_original_protocol']=dict(n_common=len(hh),changed=sum(r['historical_original_reference_changed'] for r in hh),reference_effect=summarize(r['historical_original_matrix'][n][kind]['reference_effect_old_formula'] for r in hh))
    return result

def project_erp(points):
    p=np.asarray(points,float);assert len(p)%2==0 and np.isfinite(p).all()
    top=p[::2];bottom=p[1::2];assert np.max(abs((top[:,0]-bottom[:,0]+512)%1024-512))<1e-9
    u=(bottom[:,0]/1024-.5)*2*np.pi;v=(bottom[:,1]/512-.5)*np.pi;assert np.all((v>0)&(v<np.pi/2))
    radius=1/np.tan(v);xz=np.column_stack([radius*np.sin(u),-radius*np.cos(u)]);bt=np.column_stack([xz[:,0],-np.ones(len(xz)),xz[:,1]]);tp=bt.copy();tp[:,1]=-radius*np.tan((top[:,1]/512-.5)*np.pi)
    return dict(bottom3d=bt.tolist(),top3d=tp.tolist())

def fusion_impact(root,source,configs,out):
    data=load(root/'sources/main/research/quality_parallel_local_20261012/fusion_rescore.json');frozen=load(source/'inputs/calibration_records.json');settings=load(source/'config/frozen_selected_candidates.json')['candidates']['P_tied_quad08']['parameters'];sys.path.insert(0,str(source/'scripts'));from score_frozen_geometry import evaluate as old_evaluate
    rows=[];checks=[];geometries=[]
    for r in data['rows']:
        row={k:r.get(k) for k in ['image_id','image_code','version','source','input_version','reference_id','reference_versions','formal_comparison_eligible','use_barriers','status','unavailable_reason','members']}
        if not r.get('metrics'):
            row.update(baseline=None,candidates=None);rows.append(row);continue
        original=load(root/'sources/fusion'/r['source']);candidate=original[r['version']]['candidate'];assert original['image_id']==r['image_id'];assert candidate['feature_ids']==r['feature_ids'];g=project_erp(candidate['points']);ref=frozen['geometries'][r['reference_id']]
        old=old_evaluate(g,ref,settings,samples=2048,height_samples=4096);assert old['status']=='available'
        fields=['iou_2d','S_bottom_deg','dir','Hmean','Hcenter'];error=max(abs(old['metrics'][k]-r['metrics'][k]) for k in fields);assert error<1e-8,(r['image_code'],error)
        score_error=abs(old['quality_score']-r['scores']['P_tied_quad08']);assert score_error<1e-8
        d=descriptor(g,configs);scores={n:score_metrics(old['metrics'],c,d) for n,c in configs.items()}
        row.update(baseline=r['scores']['P_tied_quad08'],metrics=old['metrics'],candidates=scores,official_iou3d_x100=r['scores']['Q_official_iou3d'],source_points_sha256=hashlib.sha256(json.dumps(candidate['points'],separators=(',',':')).encode()).hexdigest(),source_file_sha256=sha(root/'sources/fusion'/r['source']),scope_not_adjudicated=True)
        rows.append(row);checks.append(dict(image_code=r['image_code'],version=r['version'],metric_max_abs_difference=error,baseline_score_abs_difference=score_error))
        geometries.append(dict(image_id=r['image_id'],image_code=r['image_code'],version=r['version'],geometry=g,reference_id=r['reference_id'],source_points=candidate['points'],source_points_sha256=row['source_points_sha256']))
    dump(out/'fusion_220_ledger_and_scores.json',dict(rows=rows,checks=checks,source_sha256=sha(root/'sources/main/research/quality_parallel_local_20261012/fusion_rescore.json'),reference_protocol='same exact old reference for every formula and official IoU; no new fusion-scope approval'))
    dump(out/'fusion_geometries_60.json',dict(rows=geometries,projection='independent continuous ERP reconstruction checked against frozen metrics, 2048 spherical/4096 height',whole_pool_failures=data['whole_pool_failures']))
    csvout(out/'fusion_220_ledger_and_scores.csv',[{k:r.get(k) for k in ['image_code','version','status','unavailable_reason','formal_comparison_eligible','baseline','official_iou3d_x100']}|{n:(r['candidates'][n]['score'] if r.get('candidates') else None) for n in configs} for r in rows])
    available=[r for r in rows if r.get('candidates')];assert len(available)==60
    return dict(total_versions=len(rows),scored_versions=len(available),scored_images=len({r['image_id'] for r in available}),all_diagnostic_only=all(r['formal_comparison_eligible'] is False for r in rows),metric_reconstruction_max_abs_difference=max(c['metric_max_abs_difference'] for c in checks),baseline_reconstruction_max_abs_difference=max(c['baseline_score_abs_difference'] for c in checks),by_version={v:dict(n=sum(r['version']==v for r in available),changes={n:summarize(r['candidates'][n]['score']-r['baseline'] for r in available if r['version']==v) for n in configs}) for v in ['automatic','assisted']})

def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,default=ROOT/'baseline');p.add_argument('--config',type=Path,default=ROOT/'calibration/recommended_parameters.json');p.add_argument('--out',type=Path,default=ROOT/'integration/results');a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True);config=load(a.config);configs=config['candidates']
    result=dict(schema='joint_impact_summary_v1',recommended=config['recommended'],config_sha256=sha(a.config),fixed_reference=fixed_record_impact(ROOT,a.source,configs,a.out),four_way=four_way(ROOT,configs,a.out),fusion=fusion_impact(ROOT,a.source,configs,a.out),not_independent_human_validation=True,formal_eligibility_unchanged=True)
    dump(a.out/'summary.json',result);print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
