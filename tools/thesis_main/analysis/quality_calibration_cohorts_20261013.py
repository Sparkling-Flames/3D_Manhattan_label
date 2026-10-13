"""质量校准来源分层；不改旧数据、参数、人员资格或人工标签。"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

from tools.thesis_main.data_prep.consolidate_research_input import load_current_bundle

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'research/quality_joint_calibration_feedback_20261013/CALIBRATION_COHORTS.json'


def source_cohort(record):
    """仅看来源证据；改过坐标不等于改对，未知不作为已核实非trap。"""
    condition = record['condition']
    if condition == 'manual':
        return 'manual_priority'
    if condition != 'semi':
        return 'other_condition_separate'
    if record['trap_status'] == 'confirmed_trap':
        return 'semi_trap_separate'
    if record['model_edit_status'] == 'unchanged_coordinates':
        return 'semi_unchanged_separate'
    if record['explicit_model_influence'] or 'model_unchanged' in record['annotation_traits'].get('tags', []):
        return 'semi_model_issue_separate'
    if record['trap_status'] == 'confirmed_nontrap' and record['model_edit_status'] == 'changed_coordinates':
        return 'semi_nontrap_changed_candidate'
    return 'semi_unverified_separate'


def select_evidence(grades, constraints, record_ids):
    """比较中任一成员不在选定池，该整项约束均不进入此池的校准。"""
    return dict(grades=[g for g in grades if g['id'] in record_ids],
                constraints=[c for c in constraints if c['record_ids'] and set(c['record_ids']) <= record_ids])


def build(search, bundle):
    research = {r['object_id']: r for r in bundle['research']['annotations']}
    records = []
    for row in search['rows']:
        source = research[row['object_id']]
        for key in ('condition', 'image_id', 'worker_id'):
            if source[key] != row[key]:
                raise ValueError(f"source_binding_mismatch:{row['id']}:{key}")
        records.append(dict(record_id=row['id'], object_id=row['object_id'], image_code=row['image_code'],
            worker_id=row['worker_id'], condition=source['condition'], cohort=source_cohort(source),
            trap_status=source['trap_status'], model_edit_status=source['model_edit_status'],
            explicit_model_influence=source['explicit_model_influence'],
            annotation_traits_review_recorded=bool(source['annotation_traits']),
            current_worker_quality_gate=source['worker_quality_gate'],
            prior_conditional_personnel_eligible=row['conditional_personnel_eligible'],
            prior_use_barriers=row['use_barriers']))
    cohorts = {name: [r['record_id'] for r in records if r['cohort'] == name]
               for name in sorted({r['cohort'] for r in records})}
    eligible = {name: [r['record_id'] for r in records
                       if r['cohort'] == name and r['prior_conditional_personnel_eligible']]
                for name in cohorts}
    evidence = {name: select_evidence(search['grades'], search['constraints'], set(ids))
                for name, ids in cohorts.items()}
    j02 = research['d0df2148541db2cf']['trap_evidence']
    result = dict(schema='quality_calibration_source_cohorts_20261013_v1',
        purpose='manual优先；已确认semi trap、未改坐标、模型问题及来源未核实作答分开。仅新增来源筛选，不授予校准或人员资格。',
        sources=dict(bundle='analysis_results/research_input_20260929/manifest.json',
                     frozen_search_input_schema=search['schema']),
        records=records, cohort_ids=cohorts, prior_eligibility_intersection_ids=eligible,
        evidence_by_source_cohort=evidence,
        summary=dict(records=len(records), source_counts=dict(Counter(r['cohort'] for r in records)),
            prior_eligibility_intersection_counts={k:len(v) for k,v in eligible.items()},
            evidence_counts={k:{'grades':len(v['grades']), 'constraints':len(v['constraints'])} for k,v in evidence.items()}),
        j02_a_verified_evidence=j02,
        limits=['source cohort membership does not confer reference, exposure or personnel eligibility',
                'source-only evidence subsets are not automatically fitting-ready',
                'all existing human evidence remains development evidence',
                'no score threshold is used to select records',
                'unchanged coordinates do not prove absence of inspection; changed coordinates do not prove successful correction',
                'historical search results remain unchanged and are not claimed to satisfy this new cohort policy'])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--search-inputs', type=Path, required=True)
    parser.add_argument('--out', type=Path, default=OUT)
    args = parser.parse_args()
    search = json.loads(args.search_inputs.read_text(encoding='utf-8-sig'))
    result = build(search, load_current_bundle())
    result['sources']['search_inputs'] = str(args.search_inputs.resolve())
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    print(json.dumps(result['summary'], ensure_ascii=False))


if __name__ == '__main__':
    main()
