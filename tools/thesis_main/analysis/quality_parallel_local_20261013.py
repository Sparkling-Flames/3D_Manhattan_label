"""冻结三候选本地接入；独立复算、资格曝光与条件人员描述，不选择参数。"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
from itertools import combinations
import json
import math
from pathlib import Path
from statistics import mean
import subprocess
import sys

from tools.thesis_main.data_prep.consolidate_research_input import load_current_bundle

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'research/quality_parallel_local_20261012'
PACKAGE = OUT / 'source_package/quality_parameter_calibration_20261012'
NAMES = ('P_tied_quad08', 'P_tied_mix08', 'B_main_relative2')
CONFIG_SHA = 'fb1b6f0d79249bd922e6cd5b11cce346c8cda1b51db0c9c929e6dad4b48272fb'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def independent_score(m, candidate):
    """独立标量表达式，仅实现已冻结的三个算子，不调用包内评分函数。"""
    values = [m[k] for k in ('iou_2d', 'dir', 'S_bottom_deg', 'Hmean', 'Hcenter')]
    if any(v is None or not math.isfinite(v) or v < 0 for v in values) or values[0] > 1+1e-9:
        raise ValueError('Missing or invalid metric; do not impute zero')
    i, d, sb, hm, hc = values
    if candidate not in NAMES:
        raise ValueError(candidate)
    direction = d*d/(25+d*d) if candidate == 'B_main_relative2' else 1.5*d*d/(37.5+d*d)
    if candidate == 'P_tied_mix08':
        global_loss = .2*(hm/.5)**2+.8*(hm/.5)**4
    else:
        global_loss = (hm/(.8 if candidate == 'P_tied_quad08' else .5))**2
    losses = dict(bottom_loss=sb*sb/32, direction_loss=direction,
                  global_loss=global_loss, local_loss=(hc/.25)**2)
    return dict(score=100*i/(1+sum(losses.values())), **losses)


def raw_residual(o):
    p, links = o['before_preprocessing_points'], o['links_zero_based']
    if not links or sorted(i for pair in links for i in pair) != list(range(len(p))):
        return dict(status='missing_established_pairing', X_rms_deg=None, X_max_deg=None)
    if any(p[t][1] >= p[b][1] for t, b in links):
        return dict(status='pair_roles_unresolved', X_rms_deg=None, X_max_deg=None)
    delta = [((p[b][0]-p[t][0]+512)%1024-512)*360/1024 for t,b in links]
    if any(abs(v) >= 180-1e-8 for v in delta):
        return dict(status='antipodal_ambiguous', X_rms_deg=None, X_max_deg=None)
    return dict(status='mechanical_only', X_rms_deg=math.sqrt(mean(v*v for v in delta)),
                X_max_deg=max(abs(v) for v in delta), semantic_pairing_certified=False)


def personnel_reasons(o, r, reference_barriers, hold_groups, source_same):
    reasons = list(reference_barriers)
    if o['worker_id'] == 'W019': reasons.append('W019_calibration_only')
    if o['cleaning_disposition'] != 'retained': reasons.append('cleaning:'+o['cleaning_disposition'])
    if o['worker_quality_gate'] != 'candidate_pending_geometry': reasons.append('formal_gate:'+o['worker_quality_gate'])
    if not o['independent_vote_eligible']: reasons.append('not_independent_vote')
    if r is None:
        reasons.append('outside_frozen_scoring_pool')
        return reasons
    if not source_same: reasons.append('current_input_or_reference_drift')
    if not r['applicability_confirmed']: reasons.append('scope_not_confirmed_in_frozen_layer')
    gate = r['gate']
    if not gate.get('new_descriptive_development_allowed', False): reasons.append('no_development_gate')
    if gate.get('explicit_exposure_barriers'): reasons.append('explicit_exposure_barrier')
    if r.get('room_group') in hold_groups: reasons.append('original_holdout_group')
    return sorted(set(reasons))


def worker_conditions(rows):
    """同图/参考/条件的人员均分去中心；不把全库均分解释为人员能力。"""
    cells = defaultdict(lambda: defaultdict(list))
    for r in rows:
        if r['conditional_personnel_eligible']:
            cells[(r['image_id'],r['reference_id'],r['condition'])][r['worker_id']].append(r)
    centered = []
    for key, workers in sorted(cells.items()):
        if len(workers) < 2: continue
        av = {w:{n:mean(r['scores'][n] for r in rr) for n in NAMES} for w,rr in workers.items()}
        center = {n:mean(a[n] for a in av.values()) for n in NAMES}
        for w,rr in workers.items():
            centered.append(dict(worker_id=w,image_id=key[0],reference_id=key[1],condition=key[2],
                building_id=rr[0]['building_id'],record_ids=[r['record_id'] for r in rr],peers=len(workers),
                score=av[w],within_cell_difference={n:av[w][n]-center[n] for n in NAMES},
                raw_X_rms_deg=mean(r['raw_input']['X_rms_deg'] for r in rr)))
    groups = defaultdict(list)
    for r in centered: groups[(r['worker_id'],r['condition'])].append(r)
    summary=[]
    for (w,c),rr in sorted(groups.items()):
        buildings=sorted({r['building_id'] for r in rr});sensitivity={}
        for n in NAMES:
            leave=[mean(r['within_cell_difference'][n] for r in rr if r['building_id'] != b) for b in buildings] if len(buildings)>1 else []
            sensitivity[n]=dict(mean_within_cell_difference=mean(r['within_cell_difference'][n] for r in rr),
                leave_one_building_range=[min(leave),max(leave)] if leave else None)
        summary.append(dict(worker_id=w,condition=c,shared_images=len(rr),buildings=buildings,
            records=sum(len(r['record_ids']) for r in rr),results=sensitivity,
            raw_X_rms_mean_deg=mean(r['raw_X_rms_deg'] for r in rr)))
    return dict(schema='quality_conditional_workers_v1',cells=centered,workers=summary,
        scope='Descriptive development only; varying panels and peers, no ability ranks or causal effects. Leave-building ranges are sensitivity, not confidence intervals.')


def run(package=PACKAGE, out=OUT):
    from shapely.geometry import Polygon
    assert sha(package/'config/frozen_selected_candidates.json') == CONFIG_SHA
    frozen=read(package/'config/frozen_selected_candidates.json')
    sys.path.insert(0,str(package/'scripts'))
    from scoring import scalar_terms
    from frozen_guard import verify_scoring_identity
    verify_scoring_identity(frozen,package)
    data=read(package/'inputs/calibration_records.json'); saved=read(package/'results/selected_scores.json')
    expected={r['id']:r for r in saved['rows']}; source=read(package/'inputs/current_formal_loader_data.json')
    old_objects={o['object_id']:o for o in source['objects']};bundle=load_current_bundle()
    objects={o['object_id']:o for o in bundle['data']['objects']}
    by_object={r['object_id']:r for r in data['rows']}
    assert len(by_object)==len(data['rows'])==len(expected)
    actual_sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    exclusions=read(ROOT/'research/quality_next_stage_handoff_20261010/reference_exclusion_registry_20261010.json')
    reference_blocks=defaultdict(list)
    for key in ('confirmed_reference_exclusions','preserved_user_analysis_holds','reference_evidence_conflicts_primary_research_quarantine'):
        for r in exclusions[key]:reference_blocks[r['image_id']].append(key+':'+r['classification'])
    scope_regions=defaultdict(list)
    scope_path=ROOT/'research/quality_scope_review_complete_20261010/data/reference_registry.json'
    for region in read(scope_path)['records']:
        scope_regions[region['image_id']].append({k:region[k] for k in ('region_id','reference_id','is_active','selected_gt_object_id','top_boundary_pending','reference_ready')})
    exposure=read(ROOT/'research/quality_holdout_exposure_correction_20261011/exposure_registry.json')
    hold_groups={**exposure['groups_touched_by_this_screen'],**exposure['groups_not_touched_by_this_screen']}
    with (package/'input_quality/results/current_input_922.csv').open(encoding='utf-8-sig',newline='') as f:
        expected_raw={r['id']:r for r in csv.DictReader(f)}
    rows=[];ledger=[];replay=[]
    source_fields=('before_preprocessing_points','preprocessed_points','points_1024x512','links_zero_based','ordered_source_point_indices')
    for oid,o in sorted(objects.items()):
        if o['object_kind']!='annotation':continue
        r=by_object.get(oid);changed=[]
        if r:
            for target in (oid,r['reference_object_id']):
                if target not in objects: changed.append(target+':missing_current_object');continue
                for field in source_fields:
                    if objects[target].get(field)!=old_objects[target].get(field):changed.append(target+':'+field)
            for field in ('image_id','worker_id','condition'):
                if o[field]!=old_objects[oid][field]:changed.append(oid+':'+field)
        same=bool(r) and not changed
        reasons=personnel_reasons(o,r,reference_blocks[o['image_id']],hold_groups,same)
        entry=dict(object_id=oid,record_id=r['id'] if r else None,image_id=o['image_id'],image_code=o['image_code'],
            room_id=o['room_id'],building_id=o['building_id'],worker_id=o['worker_id'],condition=o['condition'],
            source_geometry_status=o['geometry']['status'],scope_status='frozen_confirmed' if r and r['applicability_confirmed'] else 'not_confirmed',
            frozen_metrics_available=r is not None,current_snapshot_matches=same if r else None,source_differences=changed,
            scoring_geometry_status='frozen_computable' if r else 'not_assessed_by_this_run',
            declared_scope_regions=scope_regions[o['image_id']],
            frozen_reference_annotations=r['gate'].get('reference_annotations') if r else None,
            current_formal_gate=o['worker_quality_gate'],scene_oos_status=o['scene_oos_status'],scene_doorway_status=o['scene_doorway_status'],
            individual_review=o['final_review']['individually_reviewed'],independent_vote_eligible=o['independent_vote_eligible'],
            conditional_personnel_eligible=not reasons,use_barriers=reasons,reference_id=r['reference_object_id'] if r else None,
            original_room_group=r.get('room_group') if r else None,formal_eligibility_newly_granted=False)
        ledger.append(entry)
        if r is None:continue
        m=r['metrics'];scores={};components={};deltas={}
        for name in NAMES:
            v=scalar_terms(m,frozen['candidates'][name]['parameters'])
            independent=independent_score(m,name)
            deltas[name]=max(abs(v['score']-expected[r['id']]['scores'][name]),abs(v['score']-independent['score']))
            assert deltas[name]<1e-8,(r['id'],name,deltas[name])
            scores[name]=v['score'];components[name]=v
        a,g=(data['geometries'][r[k]] for k in ('object_id','reference_object_id'))
        pa,pg=(Polygon([(p[0],p[2]) for p in geo['bottom3d']]) for geo in (a,g))
        assert pa.is_valid and pg.is_valid
        inter=pa.intersection(pg).area
        ha,hg=(mean(t[1]-b[1] for b,t in zip(geo['bottom3d'],geo['top3d'])) for geo in (a,g))
        q3d=100*inter*min(ha,hg)/(pa.area*ha+pg.area*hg-inter*min(ha,hg))
        qfloor=100*inter/(pa.area+pg.area-inter)
        d,f=m['dir'],m['flat'];qold=100*m['iou_2d']*(1-.075*d*d/(d*d+25)-.075*f*f/(f*f+4))/(1+(m['S_top_deg']**2+m['S_bottom_deg']**2)/32+(r['legacy_metrics']['Hstar']/.5)**2)
        for name,value in [('Q_official_iou3d',q3d),('Q_floor_iou',qfloor),('Q_v11',qold)]:
            scores[name]=value;deltas[name]=abs(value-expected[r['id']]['scores'][name]);assert deltas[name]<1e-7,(r['id'],name,deltas[name])
        raw=raw_residual(old_objects[oid])
        raw_delta=max(abs(raw[k]-float(expected_raw[r['id']][k])) for k in ('X_rms_deg','X_max_deg'))
        assert raw_delta<1e-8
        bottom=a['bottom3d'];lengths=[math.dist(u,v) for u,v in zip(bottom,bottom[1:]+bottom[:1])]
        diagnostics=dict(minimum_wall_perimeter_fraction=min(lengths)/sum(lengths),
            annotation_corner_count=len(bottom),reference_corner_count=len(g['bottom3d']),
            corner_count_difference=len(bottom)-len(g['bottom3d']),
            bottom_horizon_margin_deg=min(math.degrees(math.atan2(1,math.hypot(p[0],p[2]))) for p in bottom),
            height_profile=r.get('profile'),semantic_missing_corner_or_short_wall_error_inferred=False)
        rows.append(dict(**entry,reference_version=r['gate'].get('reference_version','reviewed_extra_fixed_reference'),
            input_version='calibration_20261012:'+r['current_points_sha256'],source_sha=data['main_sha'],local_checkout_sha=actual_sha,
            coordinate_group=r['coordinate_hash'],metrics=m,scores=scores,components=components,raw_input=raw,diagnostics=diagnostics,
            pool=r['pool']))
        replay.append(dict(record_id=r['id'],absolute_deltas=deltas,raw_residual_delta=raw_delta,current_snapshot_matches=same))
    rows.sort(key=lambda r:r['record_id'])
    strata={}
    for label,rr in [('confirmed_compatible',[r for r in rows if r['conditional_personnel_eligible']]),('diagnostic_only',[r for r in rows if not r['conditional_personnel_eligible']])]:
        unique={(r['coordinate_group'],r['condition']):r for r in rr};cells=defaultdict(list)
        for r in unique.values():cells[(r['image_id'],r['reference_id'],r['condition'])].append(r)
        pairs=[(a,b) for cell in cells.values() for a,b in combinations(cell,2)]
        strata[label]=dict(records=len(rr),coordinate_groups=len(unique),images=len({r['image_id'] for r in rr}),
            buildings=len({r['building_id'] for r in rr}),same_cell_pairs=len(pairs),
            reversals={n:sum((a['scores'][n]-b['scores'][n])*(a['scores']['B_main_relative2']-b['scores']['B_main_relative2']) < -1e-12 for a,b in pairs) for n in NAMES[:2]},
            delta_from_baseline={n:dict(min=min(r['scores'][n]-r['scores']['B_main_relative2'] for r in rr),max=max(r['scores'][n]-r['scores']['B_main_relative2'] for r in rr),mean=mean(r['scores'][n]-r['scores']['B_main_relative2'] for r in rr)) for n in NAMES[:2]} if rr else {})
    reviewed=read(ROOT/'research/quality_review_constraints_20261012/evidence.json')
    reviewed_ids={r['id'] for table in ('real39','targeted8') for r in reviewed['tables'][table]}
    reviewed_ids.update(('R01609','R02297','R00464','R00481'))
    groups={}
    for field in ('record_id','image_id','original_room_group','building_id'):
        gg=defaultdict(list)
        for r in rows:gg[str(r[field])].append(r['record_id'])
        groups[field]=[dict(id=k,record_ids=v,exposure='development_used',
            known_review_material_record_ids=sorted(set(v)&reviewed_ids),
            other_record_human_view_status='unknown_not_imputed',candidate_unseen=False,
            independent_validation_certified=False) for k,v in sorted(gg.items())]
    save(out/'candidate_identity.json',dict(frozen_config_sha256=CONFIG_SHA,candidates=[c for c in read(package/'config/algorithm_identity.json')['candidates'] if c['name'] in NAMES],formal_score_replaced=False))
    save(out/'record_results.json',dict(schema='quality_parallel_records_v1',rows=rows,strata=strata))
    save(out/'eligibility_ledger.json',dict(schema='quality_parallel_eligibility_v1',records=ledger,summary=dict(current_annotations=len(ledger),frozen_records=len(rows),conditional_personnel_records=sum(r['conditional_personnel_eligible'] for r in rows),barriers=Counter(reason for r in ledger for reason in r['use_barriers'])),qualification_source=str(exclusions['schema'])))
    save(out/'exposure_ledger.json',dict(schema='quality_parallel_exposure_v1',levels=groups,original_holdout_groups=hold_groups,original_holdout_records=exposure['original_heldout_records'],certified_independent_human_validation=0,outside_package_exposure='unknown_not_claimed_unseen'))
    save(out/'worker_conditions.json',worker_conditions(rows))
    summary=dict(records=len(replay),maximum_absolute_delta={n:max(r['absolute_deltas'][n] for r in replay) for n in replay[0]['absolute_deltas']},maximum_raw_residual_delta=max(r['raw_residual_delta'] for r in replay),current_snapshot_mismatches=[r['record_id'] for r in replay if not r['current_snapshot_matches']])
    save(out/'independent_replay.json',dict(schema='quality_parallel_replay_v1',summary=summary,rows=replay,scope='Scalar and independent polygon/prism arithmetic replay; full key geometry replay in key_geometry_replay.json; no human validation.'))
    sources=[package/'config/frozen_selected_candidates.json',package/'inputs/calibration_records.json',package/'scripts/scoring.py',scope_path,ROOT/'research/quality_next_stage_handoff_20261010/reference_exclusion_registry_20261010.json',ROOT/'research/quality_holdout_exposure_correction_20261011/exposure_registry.json',ROOT/'analysis_results/research_input_20260929/manifest.json']
    save(out/'run_manifest.json',dict(package_source_sha=data['main_sha'],checkout_sha=actual_sha,expected_remote_main='36079bedb76610a14f891b643a0569c4a4ce76fa',sources=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p)) for p in sources],loader_validation=bundle['validation'],new_parameter_search=False,new_fusion_run=False))
    print(json.dumps(dict(replay=summary,strata=strata,workers=len(read(out/'worker_conditions.json')['workers'])),ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--package',type=Path,default=PACKAGE);p.add_argument('--out',type=Path,default=OUT)
    args=p.parse_args();run(args.package,args.out)
