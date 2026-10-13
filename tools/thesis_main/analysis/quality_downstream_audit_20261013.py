"""既有人群条件与融合终点核查；不拟合参数、不重跑融合、不生成能力排名。"""
import csv
import gzip
import importlib.util
import json
from collections import Counter, defaultdict
from itertools import combinations
from statistics import mean

from tools.thesis_main.analysis.quality_current_candidate_view_20261013 import ROOT, SOURCE, read, load_inputs

OUT = ROOT / 'research/quality_downstream_audit_20261013'
LOCAL = ROOT / 'research/quality_parallel_local_20261012'


def centered_cells(rows):
    groups = defaultdict(lambda: defaultdict(list))
    for row in rows:
        groups[(row['image_id'], row['reference_id'], row['condition'])][row['worker_id']].append(row)
    cells = []
    for (image, ref, condition), workers in groups.items():
        means = {w: {n: mean(r['scores'][n] for r in rr) for n in rr[0]['scores']} for w, rr in workers.items()}
        center = {n: mean(m[n] for m in means.values()) for n in next(iter(means.values()))}
        for worker, scores in means.items():
            cells.append(dict(image_id=image, reference_id=ref, condition=condition, worker_id=worker,
                record_ids=[r['record_id'] for r in workers[worker]], peers_including_self=len(workers),
                within_cell_difference={n: scores[n]-center[n] for n in scores}))
    return cells


def check_member(member, gate, image_id):
    if (member['record_id'], member['object_id'], member['quality_worker_id'], image_id) != (
            gate['record_id'], gate['object_id'], gate['worker_id'], gate['image_id']):
        raise ValueError('fusion member identity mismatch: ' + member['record_id'])


def csv_scores(row, names):
    return {n: float(row[n]) if row[n] else None for n in names}


def reference_gap_action(full_ids, admitted):
    if admitted:
        if len(admitted)==1 and admitted[0]['full'] and admitted[0]['reference_id'] in full_ids:
            return 'unique_existing_full_reference_conditional',admitted[0]['reference_id']
        if not any(c['full'] for c in admitted):
            return 'only_confirmed_floor_available',admitted[0]['reference_id'] if len(admitted)==1 else None
        return 'existing_reference_not_bound_to_fused_target',None
    if len(full_ids)==1:return 'unique_existing_full_reference_conditional',full_ids[0]
    if full_ids:return 'existing_reference_not_bound_to_fused_target',None
    return 'no_unrestricted_full_reference',None


def worker_audit(admission):
    old = read(SOURCE / 'integration/results/worker_conditions_new.json')
    local = read(LOCAL / 'worker_conditions.json')
    frozen = {r['record_id']: r for r in read(ROOT / 'research/quality_current_candidate_view_20261013/CANDIDATE_VIEW.json')['rows']}
    input_rows, ledger = [], []
    for cell in old['cells']:
        for rid in cell['record_ids']:
            gate, f = admission[rid], frozen[rid]
            if (cell['image_id'], cell['reference_id'], cell['condition'], cell['worker_id']) != (
                    gate['image_id'], f['reference_object_id'], gate['condition'], gate['worker_id']):
                raise ValueError('worker cell identity/reference mismatch: '+rid)
            input_rows.append(dict(record_id=rid, image_id=cell['image_id'], reference_id=cell['reference_id'],
                condition=cell['condition'], worker_id=cell['worker_id'], scores={
                    ('baseline' if n=='baseline_quad08' else n): value['score'] for n,value in f['scores'].items()}))
            ledger.append(dict(record_id=rid, image_id=gate['image_id'], reference_id=cell['reference_id'],
                worker_id=gate['worker_id'], condition=gate['condition'], source_cohort=gate['source_cohort'],
                current_role=gate['role'], current_personnel_gate=gate['current_personnel_gate'],
                personnel_barriers=gate['personnel_barriers'], context_barriers=gate['context_barriers'],
                original_holdout=gate['original_holdout'],
                current_manual_condition_use=gate['role']=='manual_development_candidate'))
    if len({r['record_id'] for r in input_rows}) != len(input_rows):
        raise ValueError('duplicate worker record across cells')
    def key(c): return c['image_id'], c['reference_id'], c['condition'], c['worker_id']
    actual = {key(c): c for c in centered_cells(input_rows)}
    errors = [abs(actual[key(c)]['within_cell_difference'][n]-v) for c in old['cells'] for n,v in c['within_cell_difference'].items()]
    aggregate_errors=[]
    for worker in old['workers']:
        cc=[c for c in old['cells'] if (c['worker_id'],c['condition'])==(worker['worker_id'],worker['condition'])]
        if worker['shared_images']!=len(cc) or set(worker['buildings'])!={c['building_id'] for c in cc}:
            raise ValueError('worker panel summary mismatch')
        for name,result in worker['results'].items():
            aggregate_errors.append(abs(mean(actual[key(c)]['within_cell_difference'][name] for c in cc)-result['mean_within_cell_difference']))
            leave=[mean(actual[key(c)]['within_cell_difference'][name] for c in cc if c['building_id']!=b) for b in worker['buildings']] if len(worker['buildings'])>1 else []
            if leave:
                aggregate_errors.extend(abs(x-y) for x,y in zip((min(leave),max(leave)),result['leave_one_building_range']))
            elif result['leave_one_building_range'] is not None:
                raise ValueError('one-building result should not have leave-building interval')
    old_ids = {rid for c in local['cells'] for rid in c['record_ids']}
    if old_ids != {r['record_id'] for r in input_rows} or max(errors+aggregate_errors)>1e-9:
        raise ValueError('legacy worker coverage or independent centering differs')
    panels = defaultdict(lambda: defaultdict(set))
    for cell in old['cells']:
        panels[cell['condition']][cell['worker_id']].add((cell['image_id'],cell['reference_id']))
    coverage = {cond: dict(workers=len(workers), union_images=len(set.union(*workers.values())),
        common_to_all_workers=len(set.intersection(*workers.values())),
        per_worker_images={w:len(v) for w,v in sorted(workers.items())},
        pairwise_shared_images=[dict(A=a,B=b,n=len(workers[a]&workers[b])) for a,b in combinations(sorted(workers),2)])
        for cond,workers in panels.items()}
    summary = dict(records=len(ledger), worker_condition_rows=len(old['workers']),
        workers=len({r['worker_id'] for r in ledger}), by_condition=dict(Counter(r['condition'] for r in ledger)),
        by_source_cohort=dict(Counter(r['source_cohort'] for r in ledger)), by_current_role=dict(Counter(r['current_role'] for r in ledger)),
        original_holdout_records=sum(r['original_holdout'] for r in ledger),
        personnel_or_context_blocked=sum(bool(r['personnel_barriers'] or r['context_barriers']) for r in ledger),
        max_independent_centering_difference=max(errors), legacy_local_record_set_equal=True,
        max_worker_aggregate_or_leave_building_difference=max(aggregate_errors),
        no_worker_ability_ranking=True)
    expanded=read(ROOT/'research/quality_candidate_disagreement_20261013/RESULTS.json')['records']
    expanded=[r for r in expanded if r['score_kind']=='full']
    current_panels=defaultdict(set)
    for r in expanded:current_panels[r['worker_id']].add((r['image_id'],r['reference_object_id']))
    summary['current_expanded_manual_full_coverage']=dict(records=len(expanded),workers=len(current_panels),
        images=len({r['image_id'] for r in expanded}),reference_cells=len(set.union(*current_panels.values())),
        common_reference_cells_all_workers=len(set.intersection(*current_panels.values())),
        per_worker_reference_cells={w:len(v) for w,v in sorted(current_panels.items())},
        coverage_only_not_worker_ranking=True)
    return dict(summary=summary, records=ledger, shared_image_coverage=coverage,
        current_expanded_manual_panels={w:[dict(image_id=i,reference_id=r) for i,r in sorted(v)] for w,v in sorted(current_panels.items())},
        independently_recomputed_cells=list(actual.values()),
        policy='Historical semi cells retained as isolated diagnostics; they do not enter manual calibration or a pooled worker ranking.')


def fusion_audit(scorer, configs, admission):
    old = read(LOCAL / 'fusion_rescore.json')
    inv = read(LOCAL / 'fusion_inventory.json')
    geom = read(SOURCE / 'integration/results/fusion_geometries_60.json')
    geometry = {(r['image_code'],r['version']):r for r in geom['rows']}
    with (SOURCE / 'integration/results/fusion_220_ledger_and_scores.csv').open(encoding='utf-8-sig',newline='') as f:
        scores = {(r['image_code'],r['version']):r for r in csv.DictReader(f)}
    if set(scores) != {(r['image_code'],r['version']) for r in old['rows']}:
        raise ValueError('fusion endpoint coverage differs')
    spec = importlib.util.spec_from_file_location('frozen_structural_features',SOURCE/'experiments/structural_features.py')
    features=importlib.util.module_from_spec(spec);spec.loader.exec_module(features)
    candidate_configs={n:c for n,c in configs.items() if n!='baseline_quad08'}
    current_references={v['object_id']:v['restrictions'] for r in admission.values() for v in r['available_reference_versions'].values()}
    disagreement={r['record_id'] for r in read(ROOT/'research/quality_candidate_disagreement_20261013/RESULTS.json')['records']}
    rows=[]; differences=[]
    for r in old['rows']:
        key=(r['image_code'],r['version']); source_path=ROOT/r['source']
        issues=[]; source = read(source_path) if source_path.exists() else None
        endpoint=source[r['version']] if source else None
        if source is None: issues.append('missing_current_source_file')
        else:
            if source['image_id']!=r['image_id'] or source['gap']!=r['fusion_gap']: issues.append('source_identity_or_gap_drift')
            if endpoint['n']!=r['n']: issues.append('source_member_count_drift')
            if {(a['id'],a['worker']) for a in endpoint['assignments']} != {(m['record_id'],m['fusion_worker_alias']) for m in r['members']}:
                issues.append('source_membership_drift')
            if endpoint['candidate']['feature_ids']!=r['feature_ids']: issues.append('source_ring_order_drift')
            if any(endpoint['candidate'].get(k)!=r[k] for k in ('ring_confirmed','order_status')):
                issues.append('source_order_confirmation_drift')
            if r['version']=='assisted' and source['applied_reviews']!=r['applied_reviews']:
                issues.append('source_assistance_receipt_drift')
        members=[]
        for m in r['members']:
            gate=admission[m['record_id']];check_member(m,gate,r['image_id'])
            members.append(dict(**m, current_role=gate['role'], current_condition=gate['condition'],
                current_source_cohort=gate['source_cohort'], current_personnel_barriers=gate['personnel_barriers'],
                current_context_barriers=gate['context_barriers'], original_holdout=gate['original_holdout'],
                in_current_disagreement_view=m['record_id'] in disagreement))
        pro=scores[key]; expected=csv_scores(pro,candidate_configs)
        if pro['formal_comparison_eligible']!='False' or r['formal_comparison_eligible']:
            raise ValueError('unexpected formal fusion qualification: '+str(key))
        if pro['status']!=r['status'] or (pro['unavailable_reason'] or None)!=r['unavailable_reason']:
            raise ValueError('fusion status/reason differs: '+str(key))
        result=None
        if key in geometry:
            g=geometry[key]
            if g['reference_id']!=r['reference_id'] or g['image_id']!=r['image_id']:
                raise ValueError('fusion geometry/reference binding mismatch: '+str(key))
            if endpoint and endpoint['candidate']['points']!=g['source_points']: issues.append('source_endpoint_points_drift')
            d=features.direction_descriptors(g['geometry']['bottom3d']); descriptor={'joint_hinge':{}}
            for c in candidate_configs.values():
                if c['family']=='joint_hinge':
                    t,w=c['tail_threshold'],c['hinge_weight']
                    descriptor['joint_hinge'][f't{t:g}_g{w:g}']=features.jointly_optimized_hinge(d,t,w)['value_deg2']
            result={n:scorer.score_metrics(r['metrics'],c,descriptor) for n,c in candidate_configs.items()}
            if any(v['score'] is None or expected[n] is None for n,v in result.items()):
                raise ValueError('available fusion missing candidate score')
            differences += [abs(v['score']-expected[n]) for n,v in result.items()]
            differences.append(abs(scorer.score_metrics(r['metrics'],configs['baseline_quad08'])['score']-float(pro['baseline'])))
        elif any(v is not None for v in expected.values()):
            raise ValueError('unbound scored fusion endpoint: '+str(key))
        rows.append(dict(image_id=r['image_id'],image_code=r['image_code'],version=r['version'],
            source=r['source'],source_issues=issues,n=r['n'],fusion_gap=r['fusion_gap'],members=members,
            feature_ids=r['feature_ids'],order_status=r['order_status'],ring_confirmed=r['ring_confirmed'],
            assisted=r['version']=='assisted',applied_reviews=r['applied_reviews'],reference_id=r['reference_id'],
            reference_status=r['reference_status'],reference_barriers=r['reference_barriers'],
            current_reference_registered=r['reference_id'] in current_references,
            current_reference_barriers=current_references.get(r['reference_id']),
            original_holdout_groups=r['original_holdout_groups'],existing_use_barriers=r['use_barriers'],
            current_member_barriers=[m['record_id'] for m in members if m['current_personnel_barriers'] or m['current_context_barriers']],
            status=r['status'],unavailable_reason=r['unavailable_reason'],scores=result,
            formal_comparison_eligible=False,sequence_id=None,no_fusion_recomputed=True,
            numerical_scope='frozen_metrics_and_existing_fused_floor_direction_only_no_reference_reselection'))
    if max(differences)>1e-8: raise ValueError('fusion frozen score parity failed')
    sequences=[]
    for seq in inv['historical_sequences']:
        p=ROOT/seq['path'];entry=dict(seq,exists_now=p.exists())
        if p.exists() and (p.name.endswith('.csv') or p.name.endswith('.csv.gz')):
            opener=gzip.open if p.name.endswith('.gz') else open
            with opener(p,'rt',encoding='utf-8-sig',newline='') as f: entry['actual_fields']=next(csv.reader(f))
        sequences.append(entry)
    summary=dict(endpoints=len(rows),images=len({r['image_id'] for r in rows}),
        scope='legacy_220_endpoint_inventory_and_60_scores; additional coverage is in REFERENCE_GAP_AUDIT.json',
        by_version={v:dict(endpoints=sum(r['version']==v for r in rows),scored=sum(r['version']==v and r['scores'] is not None for r in rows),
            unavailable_reasons=dict(Counter(r['unavailable_reason'] for r in rows if r['version']==v and r['scores'] is None))) for v in ('automatic','assisted')},
        scored_images=len({r['image_id'] for r in rows if r['scores'] is not None}),
        current_source_issues=dict(Counter(issue for r in rows for issue in r['source_issues'])),
        endpoints_with_current_member_barriers=sum(bool(r['current_member_barriers']) for r in rows),
        scored_endpoints_with_current_member_barriers=sum(bool(r['current_member_barriers']) for r in rows if r['scores'] is not None),
        scored_endpoints_with_current_reference_barriers=sum(bool(r['current_reference_barriers']) for r in rows if r['scores'] is not None),
        scored_endpoints_missing_current_reference_registry=sum(not r['current_reference_registered'] for r in rows if r['scores'] is not None),
        scored_member_occurrences=sum(len(r['members']) for r in rows if r['scores'] is not None),
        scored_member_roles=dict(Counter(m['current_role'] for r in rows if r['scores'] is not None for m in r['members'])),
        max_frozen_score_difference=max(differences),current_k_sequence_available=False,
        sequence_claim_basis='Inspected endpoint sources provide full-pool assignments and rings, not entry order or per-k candidates; listed historical artifacts are different methods.',
        formal_comparison_eligible_endpoints=0)
    return dict(summary=summary,rows=rows,historical_sequences=sequences,whole_pool_failures=old['whole_pool_failures'])


def reference_gap_audit(scorer, configs, admission):
    from tools.thesis_main.data_prep.consolidate_research_input import load_current_bundle
    from tools.thesis_main.analysis.quality_manual_expansion_20261013 import engine, evaluate_geometry, module
    from tools.thesis_main.analysis.quality_frozen_fusion_rescore_20261013 import project
    data=load_current_bundle()['data'];images={r['image_id']:r for r in data['images']};objects={o['object_id']:o for o in data['objects']}
    restrictions={v['object_id']:v['restrictions'] for r in admission.values() for v in r['available_reference_versions'].values()}
    pro={r['image_id']:r for r in read(SOURCE/'routing/inputs/prepared_input.json')['candidate_images']}
    routes=defaultdict(list)
    for r in read(SOURCE/'routing/results/routes.json')['rows']:routes[r['image_id']].append(r)
    expanded=defaultdict(set)
    for r in read(ROOT/'research/quality_manual_expansion_20261013/RESULTS.json')['records']:
        expanded[r['image_id']].add(r['reference_object_id'])
    old=read(LOCAL/'fusion_rescore.json')['rows'];rows=[]
    for r in old:
        if r['unavailable_reason']!='missing_reference':continue
        im=images[r['image_id']];pc=pro.get(r['image_id'],{}).get('candidates',[])
        current=[dict(reference_id=oid,version=version,restrictions=restrictions.get(oid,[]),
            geometry_status=objects[oid]['geometry']['status'],in_manual_899=oid in expanded[r['image_id']]) for version,oid in im['references'].items()]
        full=sorted({c['reference_id'] for c in current if not c['restrictions'] and c['geometry_status']=='surface_valid'})
        admitted=[dict(reference_id=c['reference_object_id'],candidate_id=c['candidate_id'],full=c['full_reference_available'],
            floor_available=True,top_status=c['top_status'],restriction=c['restriction']) for c in pc if c['admitted_for_routing']]
        action,selected=reference_gap_action(full,admitted)
        rows.append(dict(image_id=r['image_id'],image_code=r['image_code'],version=r['version'],source=r['source'],
            old_reference_id=r['reference_id'],old_reference_versions=r['reference_versions'],old_unavailable_reason=r['unavailable_reason'],
            current_references=current,pro_admitted_candidates=admitted,existing_manual_expansion_reference_ids=sorted(expanded[r['image_id']]),
            individual_routes_not_reused=[dict(record_id=q['record_id'],selected_candidate_id=q['selected_candidate_id'],status=q['status']) for q in routes[r['image_id']]],
            classification=action,conditional_reference_id=selected,
            true_reference_absence=not current and not admitted,
            current_member_ids=[m['record_id'] for m in r['members']],
            current_member_barriers=[m['record_id'] for m in r['members'] if admission[m['record_id']]['personnel_barriers'] or admission[m['record_id']]['context_barriers']],
            original_holdout_member_ids=[m['record_id'] for m in r['members'] if admission[m['record_id']]['original_holdout']],
            scores=None,metrics=None,new_formal_qualification=False,new_reference_selected_by_quality=False,
            fusion_scope_not_adjudicated=True,new_individual_route_applied_to_fusion=False))
    e=engine();features=module(SOURCE/'experiments/structural_features.py','gap_fusion_direction')
    candidate_configs=configs
    # 同一引擎先核对一个已有融合端点，避免把投影约定变化当成新结果。
    check=next(r for r in old if r['status']=='available_diagnostic_only')
    a,state=project(read(ROOT/check['source'])[check['version']]['candidate']['points'])
    g=e['geometry'](objects[check['reference_id']]['points_1024x512']);parity=evaluate_geometry(a,g,e)
    error=max(abs(parity['metrics'][k]-check['metrics'][k]) for k in ('iou_2d','S_bottom_deg','dir','Hmean','Hcenter'))
    if error>1e-8:raise ValueError('reference gap fused geometry parity failed')
    for i,row in enumerate(rows):
        ref=row['conditional_reference_id']
        if ref is None:continue
        a,state=project(read(ROOT/row['source'])[row['version']]['candidate']['points'])
        row['projection']=state
        if a is None:row['calculation_status']='projection_unavailable';continue
        d=features.direction_descriptors(a['bottom3d']);desc={'joint_hinge':{}}
        for c in candidate_configs.values():
            if c['family']=='joint_hinge':
                t,w=c['tail_threshold'],c['hinge_weight'];desc['joint_hinge'][f't{t:g}_g{w:g}']=features.jointly_optimized_hinge(d,t,w)['value_deg2']
        if row['classification']=='unique_existing_full_reference_conditional':
            g=e['geometry'](objects[ref]['points_1024x512']);result=evaluate_geometry(a,g,e)
            row['calculation_status']=result['status'];row['reason_codes']=result['reason_codes'];row['metrics']=result['metrics']
        else:
            c=next(c for c in pro[row['image_id']]['candidates'] if c['reference_object_id']==ref)
            g={'bottom3d':[[x,-1,z] for x,z in c['floor_xz_h']]}
            try:
                areas=e['au'].area_metrics(a,g)
                row['metrics']=dict(iou_2d=areas['iou'],S_bottom_deg=float(e['sp'].spherical_sym_distance(a['bottom3d'],g['bottom3d'],2048)),
                    dir=float(e['au'].direction_residual(a,e['au'].direction_axis(a))),Hmean=None,Hcenter=None)
                row['calculation_status']='floor_only'
            except (ValueError,ArithmeticError) as exc:
                row['calculation_status']='floor_geometry_unavailable';row['reason_codes']=[str(exc)]
        if row['metrics'] is not None:row['scores']={n:scorer.score_metrics(row['metrics'],c,desc) for n,c in candidate_configs.items()}
        if (i+1)%10==0:print(f'fusion reference gap checked {i+1}/{len(rows)}',flush=True)
    summary=dict(legacy_missing_reference_endpoints=len(rows),images=len({r['image_id'] for r in rows}),
        true_reference_absence=sum(r['true_reference_absence'] for r in rows),
        classifications=dict(Counter(r['classification'] for r in rows)),
        calculation_status=dict(Counter(r.get('calculation_status','binding_unresolved_or_reference_restricted') for r in rows)),
        new_complete_scores=sum(r.get('calculation_status')=='complete' for r in rows),
        new_floor_only_scores=sum(r.get('calculation_status')=='floor_only' for r in rows),
        new_complete_with_member_barriers=sum(bool(r['current_member_barriers']) for r in rows if r.get('calculation_status')=='complete'),
        new_complete_with_original_holdout_members=sum(bool(r['original_holdout_member_ids']) for r in rows if r.get('calculation_status')=='complete'),
        merged_current_coverage=dict(full=60+sum(r.get('calculation_status')=='complete' for r in rows),
            floor_only=sum(r.get('calculation_status')=='floor_only' for r in rows),
            unavailable=220-60-sum(r.get('calculation_status') in ('complete','floor_only') for r in rows),formal_qualified=0),
        existing_fusion_metric_parity_max_difference=error,
        no_individual_route_inherited=True,no_scope_qualification_granted=True)
    return dict(summary=summary,records=rows,policy='Unique existing reference means conditional diagnostic binding only. Alternatives stay unselected; references are never ranked by score. Existing 60 scores remain untouched.')


def main():
    scorer,configs,_,admission=load_inputs()
    workers=worker_audit(admission);fusion=fusion_audit(scorer,configs,admission)
    reference_gaps=reference_gap_audit(scorer,configs,admission)
    OUT.mkdir(parents=True,exist_ok=True)
    for name,data in [('WORKER_AUDIT.json',workers),('FUSION_AUDIT.json',fusion),('REFERENCE_GAP_AUDIT.json',reference_gaps),('SUMMARY.json',dict(workers=workers['summary'],fusion=fusion['summary'],reference_gaps=reference_gaps['summary']))]:
        (OUT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    w,f,gap=workers['summary'],fusion['summary'],reference_gaps['summary']
    text=f'''# 既有人员条件与融合终点核查

本轮只核对已有证据和冻结三候选。未重跑融合、未调参、未增加人员等级或正式资格。

## 人员条件

Pro旧人员结果共{w['records']}份、{w['workers']}人、{w['worker_condition_rows']}个人员×条件行：{w['by_condition']}。与仓库旧人员结果记录集合一致，同图、同参考、同条件内先按人员均值再等权中心化，独立复算最大差{w['max_independent_centering_difference']:.3g}。

当前来源分层为{w['by_source_cohort']}。71份manual保留条件描述；72份semi均属来源待核实隔离层，保留历史诊断，不能混入manual主校准，也不能据它们推出纯人工能力。历史结果未删除。

逐份原留出计数{w['original_holdout_records']}，人员或上下文阻碍{w['personnel_or_context_blocked']}；来源限制与人员资格是两层，前者不能因后者兼容而消失。旧Pro面板manual合计13图，但24人全部共同仅1图；semi三图全员共同但来源待核实。共同面板在WORKER_AUDIT.json逐人、逐人员对列明，不能凭总体均分新排名。人员等图均值和留一楼范围亦逐项复核，最大差{w['max_worker_aggregate_or_leave_building_difference']:.3g}；留一楼范围不是置信区间。

当前扩展面板另有962份完整manual条件分、24人、115图/116个图片×参考单元，24人共同4单元，各人覆盖11–54单元。覆盖清单已并列写入WORKER_AUDIT；旧71份的1个共同图不代表扩展后覆盖仍只有1图。本轮不依据扩展覆盖直接新增人员排名。

## 融合终点

220个既有版本=177自动+43人工辅助；旧922包接口只算出自动54、辅助6，共60版本/54图片，辅助与自动不是独立样本。旧160项限制按历史原值保留：自动103被旧接口记missing_reference、17两人排序暂缓、3无完整来源环；辅助36记missing_reference、1投影跨地平线。missing_reference不是当前确无GT，见下一节更正。另保留rPc6DW4iMge-22整池24人的输入失败，不从178原池分母抹去。

逐条核对交付文件中的image、gap、成员R与P别名、记录到object再到W的身份桥接，以及feature环序。60份已有端点坐标与当前交付坐标对照；复算只用冻结metrics和已有融合底面方向描述，不重新融合、不重新选GT。四公式（baseline及三J）与Pro旧CSV最大差{f['max_frozen_score_difference']:.3g}。

当前来源文件差异：{f['current_source_issues']}。220版本中{f['endpoints_with_current_member_barriers']}个含当前成员用途阻碍；60可算版本中为{f['scored_endpoints_with_current_member_barriers']}个。60版本的{f['scored_member_occurrences']}次成员出现对应当前角色{f['scored_member_roles']}。60份当前参考注册缺失{f['scored_endpoints_missing_current_reference_registry']}、明确参考限制{f['scored_endpoints_with_current_reference_barriers']}。成员资格、参考身份、融合范围、人工辅助是不同事项；60份仍全部formal_comparison_eligible=false，不能以数值可算越过fusion_scope_not_adjudicated。

## 旧missing_reference截断更正及补算

逐条比对当前完整loader、899份新增参考组合、Pro多空间候选/个人路由以及旧reference_id/version：139个旧missing_reference（106图）当前真正没有任何参考的数量为 **0**。旧接口只从922包收集参考ID，不能把这个截断写成资料不存在。

- 84终点只有唯一既有、未受限完整参考且无其他准入空间候选，已补算baseline及三J完整分；这是条件诊断绑定，旧reference_id=null仍原样保留，不冒称旧融合已获目标空间验收。
- 1终点q9vSo1VnCiC-16只有确认底面，已计算floor，完整分及高度分量仍为null，绝不借原GT顶面。
- 51终点有多个可用版本/空间，完整或底面候选及899覆盖逐条列明，但尚未绑定融合目标；没有继承任一人员的路由，没有按Q挑参考。
- 3终点现有完整GT明确受限，保留原因和参考身份，不能当作不存在资料。

独立核对一个旧融合端点的冻结几何指标，最大误差{gap['existing_fusion_metric_parity_max_difference']:.3g}后继续补算。新增84中{gap['new_complete_with_member_barriers']}个有当前成员/上下文限制，其中{gap['new_complete_with_original_holdout_members']}个含原留出成员；分数保留为诊断，不流回主校准。汇总220终点当前为 **{gap['merged_current_coverage']['full']}完整、{gap['merged_current_coverage']['floor_only']}仅底面、{gap['merged_current_coverage']['unavailable']}仍不可单独定分**，正式资格全部为false。旧60与新增结果分开保存，避免追改旧证据。

## 序列与缺口

当前交付是全员终点，没有当前方法的人员进入顺序、sequence_id或逐k几何。既有历史clustering前缀、Lee人数期望、统计permutation逐项核对路径和可读字段，保存在FUSION_AUDIT.json；这些不是当前gap7.5融合轨迹。没有插值、没有复制终点冒充人数曲线。

当前剩余75项由51多参考未绑定、3完整参考受限、21排序/来源环/投影限制组成。已有底面结果不移植成完整顶部，也没有新增人工验收。补算只是对冻结融合端点投影和评分，原融合成员、点坐标及环序均未重做。

## 复现与字段

运行 `python -B -m tools.thesis_main.analysis.quality_downstream_audit_20261013`；最小测试 `python -B -m pytest tests/test_quality_downstream_audit_20261013.py -q`。

WORKER_AUDIT保存record身份、当前来源/用途及独立中心化单元格，shared_image_coverage保存各条件面板；FUSION_AUDIT按image_id+version保留旧220账本和60分数，REFERENCE_GAP_AUDIT保存139条截断复核、84完整补分及1底面补分。scores为null代表未算/不可算，必须连同classification和calculation_status解释，不补零；没有新增sequence_id。四项测试覆盖人员等权/参考条件隔离、P/W身份不能按编号类比、缺值与零分不同、唯一完整参考不能压过其他准入底面候选。
'''
    (OUT/'README.md').write_text(text,encoding='utf-8')
    print(json.dumps(dict(workers=w,fusion=f,reference_gaps=gap),ensure_ascii=False,indent=2))


if __name__=='__main__':main()
