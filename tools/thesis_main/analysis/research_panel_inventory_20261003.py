"""S2：只盘点当前资格、粗难度及共同图片；不评分、分类、拟合或改写裁决。"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from itertools import combinations
import json
from math import isfinite
from pathlib import Path
import warnings

from .lee_tile_stage1_20261002 import GATES, write_csv, write_json
from .research_round_20260929 import prepare_record, reconstruct

ROOT = Path(__file__).resolve().parents[3]
HUMAN = 'analysis_results/candidate_selection_review_20260913_v2/用户审查原始记录.json'
FEATURE = 'analysis_results/c2b_validation_static_20260802_v16/static/c2b_static_model_risk.csv'
BILAYOUT = 'analysis_results/independent_direction_worker_review_20260908_v1/recomputed/bilayout_recomputed_per_image.csv'
DIFFICULTIES = ('简单', '中等', '困难', '未定', '未记录')


def bind_difficulty(source, image_ids):
    if source['schema'] != 'candidate_review_user_decisions_v5':
        raise ValueError('unexpected_difficulty_schema')
    labels = {}
    for r in source['decisions']:
        if r['image_id'] in labels:
            raise ValueError('duplicate_difficulty_image')
        if r['difficulty'] not in DIFFICULTIES[:4]:
            raise ValueError('unknown_human_difficulty')
        labels[r['image_id']] = r['difficulty']
    return {i: labels.get(i, '未记录') for i in image_ids}


def summarize_groups(records, images):
    groups = defaultdict(list); seen = set()
    for r in records:
        key = (r['image'], r['condition'], r['worker'])
        if r['independent']:
            if key in seen:
                raise ValueError('duplicate_person_in_condition')
            seen.add(key)
        groups[r['image'], r['condition'], r['consensus_gate']].append(r)
    rows = []
    for (image, condition, gate), members in sorted(groups.items()):
        im = images[image]
        candidates = [r for r in members if r['consensus_candidate']]
        failed = sum(not r['bev_ok'] for r in candidates)
        quality = [r for r in members if r['quality_candidate']]
        ready = bool(candidates) and failed == 0
        quality_compatible = gate == 'main_candidate' and bool(candidates) and all(r['quality_candidate'] for r in candidates)
        rows.append(dict(image=image, condition=condition, consensus_gate=gate,
            building=im['building'], room=im['room'], difficulty=im['difficulty'],
            raw_n=len(members), independent_n=sum(r['independent'] for r in members),
            candidate_n=len(candidates), candidate_bev_failed_n=failed,
            quality_candidate_n=len(quality),
            quality_bev_independent_n=sum(r['bev_ok'] and r['independent'] for r in quality),
            curve_ready=ready, original_bev_ok=im['original_bev_ok'],
            reference_quality_compatible=quality_compatible,
            workers='|'.join(sorted(r['worker'] for r in candidates))))
    return rows


def worker_overlap(records, images):
    coverage = defaultdict(set)
    for r in records:
        key = (r['condition'], r['worker']); coverage[key]
        if r['quality_candidate'] and r['independent'] and r['bev_ok'] and images[r['image']]['original_bev_ok']:
            coverage[key].add(r['image'])
    rows = []
    for condition in sorted({c for c, _ in coverage}):
        for a, b in combinations(sorted(w for c, w in coverage if c == condition), 2):
            common = coverage[condition, a] & coverage[condition, b]
            rows.append(dict(condition=condition, worker_a=a, worker_b=b,
                a_images=len(coverage[condition, a]), b_images=len(coverage[condition, b]),
                common_n=len(common), common_buildings=len({images[i]['building'] for i in common}),
                common_rooms=len({images[i]['room'] for i in common}), common_images='|'.join(sorted(common))))
    return rows


def indexed_csv(relative):
    rows = list(csv.DictReader((ROOT/relative).open(encoding='utf-8-sig', newline='')))
    index = {}
    for r in rows:
        if r['image_id'] in index:
            raise ValueError('duplicate_model_image:' + relative)
        index[r['image_id']] = r
    return index


def finite_field(row, key):
    if row is None:
        return None
    value = float(row[key])
    if not isfinite(value):
        raise ValueError('nonfinite_model_field:' + key)
    return value


def collect():
    from tools.thesis_main.data_prep.consolidate_research_input import load_current_bundle
    from tools.thesis_main.data_prep.project_public_research_20260929 import project_bundle
    bundle = load_current_bundle(); panel, mapping = project_bundle(bundle)
    current = {i['image_code']: i for i in bundle['research']['images']}
    human = json.loads((ROOT/HUMAN).read_text(encoding='utf-8-sig'))
    labels = bind_difficulty(human, [i['image_id'] for i in current.values()])
    features, bilayout = indexed_csv(FEATURE), indexed_csv(BILAYOUT)
    sources = {mapping['records'][o['object_id']]: o for o in bundle['data']['objects']}
    images, records, references, notices = {}, [], [], []
    for im in panel['images']:
        if not im['annotations']:
            continue  # 两张reference-only图只记来源覆盖，不加入259研究图。
        meta = current[im['code']]; image_id = meta['image_id']
        item = dict(image=im['code'], image_id=image_id, building=im['building'], room=im['room'],
            difficulty=labels[image_id], oos_status=im['scene']['oos_status'],
            doorway_status=im['scene']['doorway_status'], review_coverage=im['scene']['coverage'],
            coarse_space=meta['room_spatial_classification']['coarse_type'], **im['review'],
            original_bev_ok=False, manual_revision_bev_ok=False, raw_n=len(im['annotations']),
            d_model_feat_static=finite_field(features.get(image_id), 'd_model_feat_static'),
            bilayout_legacy_band=finite_field(bilayout.get(image_id), 'band') if image_id in bilayout and bilayout[image_id]['band_status']=='computable' else None,
            bilayout_source_present=image_id in bilayout)
        images[im['code']] = item
        for r in im['annotations'] + im['references']:
            r = dict(r, source_pair_indices=sources[r['id']]['ordered_source_pair_indices'])
            prepared = prepare_record(r)
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter('always', RuntimeWarning)
                geometry = reconstruct(prepared)
            notices.extend(dict(id=r['id'], message=str(w.message)) for w in caught)
            footprint = geometry['representations']['declared_footprint']
            row = dict(image=im['code'], id=r['id'], order_used=prepared['order_used'],
                source_order_changed=prepared['source_pair_indices'] != r['source_pair_indices'],
                bev_ok=footprint['status']=='ok', bev_reason=footprint['reason'],
                wall_band_status=geometry['representations']['declared_column_wall_band']['status'])
            if 'worker' not in r:
                row['version'] = r['version']; references.append(row)
                item[r['version']+'_bev_ok'] = row['bev_ok']
                continue
            gate = r['main_consensus_gate']['status']
            if r['consensus_eligible'] != (gate in GATES):
                raise ValueError('inconsistent_consensus_gate')
            row.update(worker=r['worker'], condition=r['condition'], independent=r['independent'],
                consensus_gate=gate, consensus_candidate=r['independent'] and r['consensus_eligible'],
                quality_gate=r['main_quality_gate']['status'], quality_candidate=r['quality_candidate'],
                quality_reasons='|'.join(r['main_quality_gate']['reasons']))
            records.append(row)
    return dict(schema='research_panel_inventory_input_v1', contract_version=bundle['data']['contract_version'],
        source_manifest=panel['source_manifest']['source_entry'], sources=dict(human=HUMAN, feature=FEATURE, bilayout=BILAYOUT),
        source_validation=bundle['validation']['status'], source_summary=bundle['data']['summary'],
        human_labels=[dict(image_id=d['image_id'], difficulty=d['difficulty']) for d in human['decisions']],
        images=list(images.values()), records=records, references=references, warnings=notices)


def build(snapshot, out):
    if snapshot['schema'] != 'research_panel_inventory_input_v1':
        raise ValueError('unsupported_inventory_input')
    out.mkdir(parents=True, exist_ok=True)
    images = {i['image']: i for i in snapshot['images']}; records = snapshot['records']
    groups = summarize_groups(records, images); pairs = worker_overlap(records, images)
    coverage = []
    for key in sorted({(g['condition'], g['consensus_gate'], g['reference_quality_compatible']) for g in groups}):
        pool = [g for g in groups if (g['condition'], g['consensus_gate'], g['reference_quality_compatible'])==key]
        if not any(g['candidate_n'] for g in pool):
            continue
        for k in range(1, max(g['candidate_n'] for g in pool)+1):
            for difficulty in DIFFICULTIES:
                all_rows = [g for g in pool if g['candidate_n']>=k and g['difficulty']==difficulty]
                ready = [g for g in all_rows if g['curve_ready'] and g['original_bev_ok']]
                coverage.append(dict(condition=key[0], consensus_gate=key[1], reference_quality_compatible=key[2],
                    difficulty=difficulty, k=k, candidate_images=len(all_rows), ready_images=len(ready),
                    ready_buildings=len({g['building'] for g in ready}), images='|'.join(g['image'] for g in ready)))
    blocks = defaultdict(list)
    for g in groups:
        if g['curve_ready'] and g['original_bev_ok']:
            blocks[g['condition'], g['consensus_gate'], g['reference_quality_compatible'], g['workers']].append(g)
    blocks = [dict(condition=c, consensus_gate=s, reference_quality_compatible=q, workers=w,
        n=len(w.split('|')), image_n=len(gs), building_n=len({g['building'] for g in gs}),
        difficulty_counts=dict(Counter(g['difficulty'] for g in gs)), images=[g['image'] for g in gs])
        for (c,s,q,w),gs in blocks.items()]
    blocks.sort(key=lambda r: (-r['image_n'], -r['n'], r['condition'], r['workers']))
    worker_rows = []
    for condition, worker in sorted({(r['condition'], r['worker']) for r in records}):
        raw = [r for r in records if (r['condition'], r['worker']) == (condition, worker)]
        usable = [r for r in raw if r['quality_candidate'] and r['independent'] and r['bev_ok'] and images[r['image']]['original_bev_ok']]
        worker_rows.append(dict(condition=condition, worker=worker, raw_n=len(raw),
            quality_candidate_n=sum(r['quality_candidate'] for r in raw), quality_bev_independent_n=len(usable),
            image_n=len({r['image'] for r in usable}), building_n=len({images[r['image']]['building'] for r in usable}),
            images='|'.join(sorted(r['image'] for r in usable))))
    # 仅按标签/覆盖预选；还没有计算这些图的IoU曲线或人员分数。
    a_panel = [g for g in groups if g['condition']=='manual' and g['reference_quality_compatible']
               and g['curve_ready'] and g['original_bev_ok'] and g['difficulty'] in DIFFICULTIES[:3]
               and g['candidate_n']>=8]
    b_panels = [b for b in blocks if b['condition']=='manual' and b['reference_quality_compatible'] and b['n']==24]
    next_panels = dict(
        status='S3预选；不是新增正式资格。按覆盖选择，未读曲线或分数。',
        a=dict(k=list(range(1,9)), selection='manual、既有主质量兼容、完整候选BEV可用、明确人工难度、N≥8；固定这些图片贯穿1—8人。8是首轮观察范围，不是足够人数。',
               images=[g['image'] for g in a_panel], difficulty_counts=dict(Counter(g['difficulty'] for g in a_panel)),
               building_counts={d:dict(Counter(g['building'] for g in a_panel if g['difficulty']==d)) for d in DIFFICULTIES[:3]},
               common_workers=sorted(set.intersection(*(set(g['workers'].split('|')) for g in a_panel))) if a_panel else []),
        b=dict(selection='manual、既有主质量兼容、相同24人完整作答的图片块；先连续分项画像，不由目标图倒推人员分类。', blocks=b_panels))
    current_ids = {i['image_id'] for i in images.values()}
    summary = dict(images=len(images), annotations=len(records), workers=len({r['worker'] for r in records}),
        difficulty=dict(Counter(i['difficulty'] for i in images.values())),
        human_source=dict(Counter(i['difficulty'] for i in snapshot['human_labels'])),
        human_outside_current=[i for i in snapshot['human_labels'] if i['image_id'] not in current_ids],
        conditions=dict(Counter(r['condition'] for r in records)),
        consensus_gates=dict(Counter(r['consensus_gate'] for r in records)),
        quality_gates=dict(Counter(r['quality_gate'] for r in records)),
        candidate_n=sum(r['consensus_candidate'] for r in records),
        candidate_geometry_failures=[r['id'] for r in records if r['consensus_candidate'] and not r['bev_ok']],
        quality_candidate_n=sum(r['quality_candidate'] for r in records),
        quality_geometry_failures=[r['id'] for r in records if r['quality_candidate'] and not r['bev_ok']],
        original_reference_failures=[i['image'] for i in images.values() if not i['original_bev_ok']],
        feature_available=sum(i['d_model_feat_static'] is not None for i in images.values()),
        bilayout_available=sum(i['bilayout_legacy_band'] is not None for i in images.values()),
        warnings=len(snapshot['warnings']))
    for name, rows in [('images',list(images.values())), ('annotations',records),
                       ('references',snapshot['references']), ('groups',groups),
                       ('worker_overlap',pairs), ('worker_coverage',worker_rows), ('a_coverage_by_k',coverage)]:
        write_csv(out/(name+'.csv'), rows)
    write_json(out/'input.json', snapshot)
    write_json(out/'summary.json', summary)
    write_json(out/'same_roster_blocks.json', blocks)
    write_json(out/'next_panels.json', next_panels)
    write_json(out/'field_contract.json', dict(schema='research_panel_inventory_v1',
        contract_version=snapshot['contract_version'],
        unit='image × condition × existing consensus gate; votes are distinct real people',
        difficulty='Exact image_id join to retained human tags. 未定 differs from 未记录. No legacy per-answer difficulty; no propagation within rooms.',
        curve_ready='At least one upstream independent candidate and every candidate has computable declared BEV. A failure keeps original N and blocks this full-roster curve; no silent deletion.',
        reference_quality_compatible='main_candidate and every consensus candidate already has upstream candidate_pending_geometry quality status; descriptive screening, not new formal eligibility or visual GT validation.',
        worker_overlap='Per condition: shared images with independent, upstream quality-candidate, BEV-computable responses and computable original GT. Zero-overlap pairs retained; pairwise overlap is not a common multi-person panel.',
        common_k='a_coverage_by_k images change with k. Freeze a single image list before comparing the shape over k; blocks contain identical rosters for stricter comparisons.',
        model_fields='Availability of historical model-only signals, not validated current-pipeline difficulty. d_model_feat_static is kept separate from local/hypot risk; BiLayout band is an archived metric awaiting model input and representation alignment.',
        missing='Null model value means unavailable, never zero. False review marks mean no recorded mark, not verified absence.',
        source='input.json freezes this inventory with geometry statuses, not coordinates. --input replays inventory; omitting it regenerates from validated local current bundle and existing geometry code. No visual review or model inference is claimed.'))
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, help='重放已落盘的盘点输入；省略则读取当前完整包')
    parser.add_argument('--out', type=Path, default=ROOT/'analysis_results/research_panel_inventory_20261003')
    args = parser.parse_args()
    snapshot = json.loads(args.input.read_text(encoding='utf-8')) if args.input else collect()
    summary = build(snapshot, args.out)
    print(json.dumps({k: summary[k] for k in ('images','annotations','workers','difficulty','feature_available','bilayout_available','warnings')}, ensure_ascii=True))


if __name__ == '__main__':
    main()
