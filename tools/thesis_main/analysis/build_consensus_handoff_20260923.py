"""导出可追溯数值输入、先行诊断和独立可运行Pro包；不修改原始证据。"""
import argparse
from collections import Counter, defaultdict
import csv
import gzip
import json
from pathlib import Path
import sys
import zipfile

import numpy as np

if __package__:
    from . import consensus_region_20260923 as region
else:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import consensus_region_20260923 as region

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'analysis_results/consensus_research_20260923'
METHODS = ['mv50', 'mv_strict', 'medoid', 'em_correct_probability', 'greedy_empirical', 'staple']
MISSING_METRICS = dict.fromkeys(['iou','erp_dx_px','dy_px','erp_distance_px','circular_dx_px','moment_distance'])


def clean(value):
    if isinstance(value, dict): return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, np.ndarray)): return [clean(x) for x in value]
    if isinstance(value, (np.integer,)): return int(value)
    if isinstance(value, (np.bool_,)): return bool(value)
    if isinstance(value, (float, np.floating)): return float(value) if np.isfinite(value) else None
    return value


def write_json(path, value, lines=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    text = ('\n'.join(json.dumps(clean(r), ensure_ascii=False, allow_nan=False) for r in value) if lines
            else json.dumps(clean(value), ensure_ascii=False, indent=2, allow_nan=False)) + '\n'
    if path.suffix == '.gz':
        with gzip.open(path, 'wt', encoding='utf8') as f: f.write(text)
    else: path.write_text(text, encoding='utf8')


def read_json(path, lines=False):
    opener = gzip.open if path.suffix == '.gz' else open
    with opener(path, 'rt', encoding='utf-8-sig') as f:
        return [json.loads(x) for x in f if x.strip()] if lines else json.load(f)


def write_csv(path, rows):
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(clean(v), ensure_ascii=False) if isinstance(v, (dict, list)) else clean(v)
                             for k, v in row.items()})


def export_inputs(out):
    from .audit_supervisor_gt_sensitivity_20260922 import load_annotation_inputs, is_substantive_revision, consecutive_pairs
    from .shared_x_reanalysis_20260922 import shared_x, verify_raw
    from .materialize_model_gt_threshold_screen import _read_test_gt
    from .geometry_consensus.representation import normalize_geometry

    rows, _, _, records, registry = load_annotation_inputs()
    accepted = {r['canonical_annotation_id'] for r in rows
                if r['calculation_included'] and r['worker_id'] not in {'W019', 'W026'}}
    verified = verify_raw(rows, accepted)
    write_json(out/'source_verification.json', verified)
    known_review = read_json(ROOT/'analysis_results/cluster_screen_reviewed_20260922/逐项接收.json')
    wrong = {cid for r in known_review if r['case'] == 14 for cid in r['ids']}
    exported = []
    for row in rows:
        cid = row['canonical_annotation_id']; rec = records.get(cid)
        item = {k: row.get(k) for k in ['canonical_annotation_id', 'image_id', 'building_id', 'worker_id',
            'raw_condition', 'stage', 'assistance_exposure', 'context_key', 'raw_points_1024x512',
            'effective_points_1024x512', 'processing_status', 'imputed_point', 'imputation_provenance',
            'pairing_review', 'raw_export_path', 'runtime_task_id', 'raw_annotation_id', 'provenance',
            'review_decision', 'exclusion_reason', 'evidence']}
        item.update(accepted_before_new_review=cid in accepted, known_wrong=cid in wrong,
                    known_wrong_source='analysis_results/cluster_screen_reviewed_20260922/逐项接收.json#case14' if cid in wrong else None,
                    pairs_shared_x=None, pairing_status='unavailable', links_zero_based=None)
        if rec is not None and rec['links'] is not None:
            links = np.asarray(rec['links'], int)
            points = shared_x(rec['p'], links)
            item.update(pairs_shared_x=points[links], links_zero_based=links, pairing_status='existing_accepted_pairing')
        exported.append(item)
    if len(accepted) != 3019: raise ValueError(f'accepted_snapshot_drift:{len(accepted)}')
    write_json(out/'inputs/annotations.jsonl.gz', exported, lines=True)
    image_ids = {r['image_id'] for r in exported if r['accepted_before_new_review']}
    manual = _read_test_gt(ROOT/'export_label/groudTruth.json')
    bi_root = Path('D:/Work/Manhattan_3D/Bi_layout/exports/mp3d_dual_predictions')
    bi = {}
    for split in ('test', 'val'):
        with (bi_root/split/'manifest.csv').open(encoding='utf-8-sig') as f:
            bi.update({r['pano_id']: r for r in csv.DictReader(f)})
    metadata = {r['image_id']: r for r in registry['images']}
    references = {}
    for iid in sorted(image_ids):
        values = []
        gt = next((ROOT/f'data/mp3d_layout/{s}/label_cor/{iid}.txt' for s in ('test', 'valid')
                   if (ROOT/f'data/mp3d_layout/{s}/label_cor/{iid}.txt').exists()), None)
        changed = bool(gt is not None and iid in manual and is_substantive_revision(np.loadtxt(gt), manual[iid]))
        def add(name, points, source, kind, revised=False):
            pairs = None; status = 'ok'; why = None
            try:
                if revised:
                    norm = normalize_geometry(points)
                    if not norm['valid']: raise ValueError(norm['reason'])
                    pairs = np.array([[[p['x']%1024,p['y_ceiling']],[p['x']%1024,p['y_floor']]] for p in norm['pairs']])
                else: pairs = consecutive_pairs(points, average_x=True)
            except ValueError as exc: status, why = 'pairing_unresolved', str(exc)
            values.append(dict(name=name, kind=kind, source=source, raw_points=points,
                               pairs_shared_x=pairs, pairing_status=status, reason=why,
                               pairing_basis='existing_GT_normalization' if revised else 'source_alternating_pairs'))
        if gt is not None:
            original = np.loadtxt(gt); source = gt.relative_to(ROOT).as_posix()
            add('gt_original', original, source, 'gt')
            add('gt_revised', manual[iid] if changed else original,
                'export_label/groudTruth.json' if changed else source, 'gt', revised=changed)
        else:
            values.extend(dict(name=n,kind='gt',source=None,pairs_shared_x=None,pairing_status='missing')
                          for n in ('gt_original','gt_revised'))
        hh = next((p for p in [ROOT/f'output/mp3d_layout/HOHO_layout_aug_efficienthc_Transen1_resnet34/{iid}.txt',
                    ROOT/f'analysis_results/c2b_validation_static_20260802_v16/validation_prediction_txt/{iid}.txt'] if p.exists()), None)
        if hh: add('hohonet',np.loadtxt(hh),hh.relative_to(ROOT).as_posix(),'model')
        else: values.append(dict(name='hohonet',kind='model',source=None,pairs_shared_x=None,pairing_status='missing'))
        for head in ('enclosed', 'extended'):
            b = bi.get(iid); rel = b.get(head+'_corners_px_path') if b else None
            path = bi_root/rel if rel else None
            if b and b['status']=='ok' and path and path.is_file():
                add('bilayout_'+head,np.loadtxt(path),str(path),'model')
            else: values.append(dict(name='bilayout_'+head,kind='model',source=str(path) if path else None,
                                pairs_shared_x=None,pairing_status=b['status'] if b else 'missing'))
        references[iid] = dict(image_id=iid,building_id=metadata[iid]['building'],
                              image_path=metadata[iid]['path'],code=f"{metadata[iid]['building']}-{metadata[iid]['number']:02d}",
                              manual_gt_changed=changed,references=values)
    write_json(out/'inputs/references.json.gz', references)
    write_json(out/'inputs/room_registry.json.gz', registry)
    snapshot = dict(schema='consensus_inputs_v1', raw_rows=len(rows), accepted=len(accepted),images=len(image_ids),
        conditions=Counter(r['raw_condition'] for r in exported if r['accepted_before_new_review']),
        manual_gt_changed_images=sum(r['manual_gt_changed'] for r in references.values()),
        paired=sum(r['accepted_before_new_review'] and r['pairs_shared_x'] is not None for r in exported),
        known_wrong_ids=sorted(wrong), raw_verified=len(verified),
        original_points='raw_points_1024x512', computed_points='pairs_shared_x',
        semantics='初始纳入标志不是新视觉裁决；known_wrong只承接明确case14；所有未决原件另附',
        dependencies=['numpy','scipy','pandas','shapely','scikit-learn'], optional=['SimpleITK for standard STAPLE'])
    write_json(out/'inputs/manifest.json',snapshot)
    return snapshot


def numeric(out, methods=METHODS):
    annotations = read_json(out/'inputs/annotations.jsonl.gz',lines=True)
    references = read_json(out/'inputs/references.json.gz')
    groups = defaultdict(list)
    for r in annotations:
        if r['accepted_before_new_review']: groups[r['image_id'],r['raw_condition']].append(r)
    quality, audit, endpoint, failures, model_difficulty = [], [], [], [], []
    for number, ((iid, condition), rows) in enumerate(sorted(groups.items())):
        rows.sort(key=lambda r:r['canonical_annotation_id'])
        for mode in ('curve','linear'):
            rm, ref_errors = {}, {}
            for ref in references[iid]['references']:
                try:
                    if ref['pairs_shared_x'] is None: raise ValueError(ref['pairing_status'])
                    rm[ref['name']]=region.wall_mask(ref['pairs_shared_x'],mode=mode)
                except ValueError as exc:
                    ref_errors[ref['name']] = str(exc)
                    failures.append(dict(image_id=iid,condition=condition,mode=mode,object=ref['name'],reason=str(exc)))
            masks, mask_errors = {}, {}
            for row in rows:
                cid=row['canonical_annotation_id']
                try:
                    if row['pairs_shared_x'] is None: raise ValueError('pairing_unavailable')
                    masks[cid]=region.wall_mask(row['pairs_shared_x'],mode=mode)
                except ValueError as exc:
                    mask_errors[cid] = str(exc)
                    failures.append(dict(image_id=iid,condition=condition,mode=mode,object=cid,reason=str(exc)))
                    audit.append(dict(canonical_annotation_id=cid,image_id=iid,condition=condition,mode=mode,
                                      status='not_evaluable',reason=str(exc),worker_id=row['worker_id']))
            independent = {r['canonical_annotation_id'] for r in rows if not r['imputed_point'] and not r['known_wrong']}
            for row in rows:
                cid=row['canonical_annotation_id']
                for version in ('gt_original','gt_revised'):
                    reasons = []
                    if cid not in masks: reasons.append(mask_errors[cid])
                    if version not in rm: reasons.append('GT_unavailable:'+ref_errors.get(version,'missing'))
                    metrics = region.compare_masks(masks[cid],rm[version]) if not reasons else MISSING_METRICS
                    quality.append(dict(canonical_annotation_id=cid,image_id=iid,building_id=row['building_id'],
                        worker_id=row['worker_id'],condition=condition,mode=mode,gt_version=version,
                        status='not_evaluable' if reasons else 'ok',reason=';'.join(reasons) or None,
                        manual_gt_changed=references[iid]['manual_gt_changed'],known_wrong=row['known_wrong'],
                        imputed_point=row['imputed_point'],
                        circular_R=region.centroid(masks[cid])['circular_R'] if cid in masks else None,
                        gt_circular_R=region.centroid(rm[version])['circular_R'] if version in rm else None,
                        **metrics))
                if cid not in masks:continue
                mask=masks[cid];cent=region.centroid(mask)
                ref_scores={name:region.compare_masks(mask,m)['iou'] for name,m in rm.items()}
                peers = [r for r in rows if r['canonical_annotation_id'] in independent and
                         r['canonical_annotation_id'] in masks and r['worker_id'] != row['worker_id']]
                peer_scores=[(r['canonical_annotation_id'],region.compare_masks(mask,masks[r['canonical_annotation_id']])['iou']) for r in peers]
                closest_peer=max(peer_scores,key=lambda x:x[1]) if peer_scores else (None,None)
                closest_ref=max(ref_scores,key=ref_scores.get) if ref_scores else None
                ref_loss=1-ref_scores[closest_ref] if closest_ref else None
                peer_loss=1-closest_peer[1] if closest_peer[0] else None
                audit.append(dict(canonical_annotation_id=cid,image_id=iid,code=references[iid]['code'],condition=condition,
                    worker_id=row['worker_id'],mode=mode,status='pending_visual_review',known_wrong=row['known_wrong'],
                    imputed_point=row['imputed_point'],reference_count=len(rm),expected_reference_count=5,
                    reference_coverage_complete=len(rm)==5,peer_count=len(peers),closest_reference=closest_ref,
                    closest_reference_iou=ref_scores.get(closest_ref),closest_peer_id=closest_peer[0],closest_peer_iou=closest_peer[1],
                    joint_distance_rank=min(ref_loss,peer_loss) if ref_loss is not None and peer_loss is not None else None,
                    reference_ious=ref_scores,peer_ious=dict(peer_scores),**cent))
            ids=[r['canonical_annotation_id'] for r in rows if r['canonical_annotation_id'] in independent and r['canonical_annotation_id'] in masks]
            workers=[r['worker_id'] for r in rows]
            duplicate_worker = len(workers)!=len(set(workers))
            if duplicate_worker:
                failures.append(dict(image_id=iid,condition=condition,mode=mode,object='aggregate',reason='repeated_worker_requires_resolution'))
            if mode=='curve':
                for method in methods:
                    if duplicate_worker or not ids:
                        result=dict(status='not_evaluable',mask=None,
                                    reason='repeated_worker_requires_resolution' if duplicate_worker else 'no_eligible_members')
                    else:
                        result=region.aggregate(np.array([masks[cid] for cid in ids]),method)
                    used_ids=[] if duplicate_worker else ids
                    base=dict(image_id=iid,condition=condition,mode=mode,method=method,
                              k=len(set(workers)),member_ids=[r['canonical_annotation_id'] for r in rows],
                              used_k=len(used_ids),used_member_ids=used_ids,
                              algorithm_status=result['status'],raw_accepted_n=len(rows))
                    for version in ('gt_original','gt_revised'):
                        metrics=region.compare_masks(result['mask'],rm[version]) if result.get('mask') is not None and version in rm else MISSING_METRICS
                        reasons=[result['reason']] if result.get('reason') else []
                        if version not in rm: reasons.append('GT_unavailable:'+ref_errors.get(version,'missing'))
                        status=result['status'] if version in rm else 'not_evaluable'
                        endpoint.append(dict(**base,gt_version=version,gt_available=version in rm,
                                             status=status,reason=';'.join(reasons) or None,**metrics))
                if 'bilayout_enclosed' in rm and 'bilayout_extended' in rm:
                    model_difficulty.append(dict(image_id=iid,condition=condition,bi_disagreement=1-region.compare_masks(rm['bilayout_enclosed'],rm['bilayout_extended'])['iou']))
        if number%25==0:print(f'numeric groups {number+1}/{len(groups)}',flush=True)
    audit.sort(key=lambda r: (r.get('joint_distance_rank') is None,-(r.get('joint_distance_rank') or 0)))
    write_csv(out/'review_queue.csv',audit);write_csv(out/'individual_quality.csv',quality)
    write_csv(out/'endpoint_pilot.csv',endpoint);write_csv(out/'model_difficulty.csv',model_difficulty)
    write_json(out/'representation_failures.json',failures)
    report=dict(schema='consensus_numeric_pilot_v2',groups=len(groups),audit_rows=len(audit),quality_rows=len(quality),
                quality_status=Counter(r['status'] for r in quality),
                endpoint_rows=len(endpoint),endpoint_status=Counter(r['status'] for r in endpoint),
                representation_failures=Counter(r['reason'] for r in failures),
                scope='全量两种边界个体诊断及曲线全成员端点；不是完整前缀、分类或同房预测实验',
                new_visual_exclusions=0)
    write_json(out/'numeric_summary.json',report)
    return report


def bundle(out):
    sources=read_json(out/'review_sources.json')
    files={p:'inputs/'+p.name for p in (out/'inputs').iterdir() if p.is_file()}
    files.update({out/name:name for name in ['README.md','review_sources.json','source_verification.json','numeric_summary.json','review_queue.csv','individual_quality.csv','endpoint_pilot.csv','representation_failures.json','model_difficulty.csv','centroid_summary.csv','centroid_findings.md','centroid_diagnostics.png','gt_sensitivity_summary.csv']})
    for item in sources['sources']:
        files[ROOT/item['path']]='source/'+item['path']
    for i,item in enumerate(sources.get('external_context_sources',[])):
        files[Path(item['external_path'])]=f'context/{i+1}_{Path(item["external_path"]).name}'
    for path in ['docs/thesis_main/PAPER_A_METHOD_CONTRACT_CURRENT.json','docs/thesis_main/PAPER_A_METHOD_CONTRACT_CURRENT.md',
                 'analysis_results/cluster_screen_reviewed_20260922/逐项接收.json',
                 'docs/thesis_main/STATISTICAL_ANALYSIS_PLAN_v1.md','docs/thesis_main/ROUND_BASED_ASSIGNMENT_SOP_v1.md',
                 'docs/thesis_main/相似场景标注稳定性分析SOP.md','docs/thesis_main/图片分类与同房间收敛预测研究SOP.md',
                 'docs/thesis_main/PRO_CONSENSUS_RESEARCH_TASK_20260923.md']:
        files[ROOT/path]='source/'+path
    files[Path(__file__) ]='code/run_numeric.py'
    files[Path(region.__file__) ]='code/consensus_region_20260923.py'
    files[Path(__file__).with_name('summarize_consensus_pilot_20260923.py')]='code/summarize_consensus_pilot.py'
    for path in ['lib/__init__.py','lib/misc/__init__.py','lib/misc/panostretch.py']:
        files[ROOT/path]=path
    manifest=dict(schema='consensus_pro_handoff_v1',contract_version='consensus_research_20260923_v1',
        command='python code/run_numeric.py --out . --numeric-only',
        required_packages=['numpy','scipy'],optional_packages=['SimpleITK for STAPLE','pandas and matplotlib for summary plots'],
        excludes='原图、active日志、账号和无关原始导出不入包；已有数值输入逐份回查来源',
        files=[dict(path=name,bytes=p.stat().st_size) for p,name in files.items()])
    with zipfile.ZipFile(out/'pro_handoff.zip','w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p,name in files.items():z.write(p,name)
        z.writestr('MANIFEST.json',json.dumps(manifest,ensure_ascii=False,indent=2))
    write_json(out/'handoff_manifest.json',manifest)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,default=OUT)
    parser.add_argument('--numeric-only',action='store_true');parser.add_argument('--export-only',action='store_true')
    parser.add_argument('--bundle-only',action='store_true');parser.add_argument('--methods',nargs='+',default=METHODS)
    args=parser.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    if args.bundle_only:bundle(args.out)
    else:
        if not args.numeric_only: print(json.dumps(clean(export_inputs(args.out)),ensure_ascii=False),flush=True)
        if not args.export_only: print(json.dumps(clean(numeric(args.out,args.methods)),ensure_ascii=False),flush=True)
