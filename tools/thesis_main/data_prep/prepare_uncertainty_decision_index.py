"""连接现有不确定性输入与已归档初始化追溯，不改变源记录或资格。"""
import argparse
import json
from pathlib import Path

import pandas as pd


def join_index(annotations, links, times, traces):
    key = 'canonical_annotation_id'
    for frame in (annotations, links, times, traces):
        if not frame[key].is_unique or frame[key].eq('').any():
            raise ValueError('canonical identity is blank or duplicated')
    ids = set(annotations[key])
    if set(links[key]) != ids or set(times[key]) != ids:
        raise ValueError('links/time coverage differs from canonical universe')
    if set(traces[key]) != set(annotations.loc[annotations.raw_condition == 'semi', key]):
        raise ValueError('initialization trace coverage differs from Semi responses')
    link_fields = [key, 'partition_ids_json', 'model_layout_ids_json', 'reference_ids_json', 'actual_proposal_ids_json']
    time_fields = [key, 'active_time_seconds', 'active_time_formal_available', 'timing_status', 'active_time_source']
    trace_fields = [key, 'legacy_initialization_source_kind', 'initial_import_match_status',
                    'initial_model_checkpoint_status', 'initialization_reconstructed_source', 'initial_trace_interpretation']
    result = annotations.merge(links[link_fields], on=key, validate='one_to_one')
    result = result.merge(times[time_fields], on=key, validate='one_to_one')
    return result.merge(traces[trace_fields], on=key, how='left', validate='one_to_one').fillna('')


def main(root, out):
    base = root / 'analysis_results/uncertainty_cloud_inputs_20260906_v1'
    def read(path):
        return pd.read_csv(path, dtype=str, keep_default_na=False)
    a = read(base / 'annotations.csv.gz')
    fields = ['canonical_annotation_id', 'annotation_identity', 'raw_annotation_id', 'worker_id',
              'context_key', 'image_id', 'building_id', 'stage', 'block_index', 'raw_condition',
              'current20_member', 'canonical_selection_status', 'legacy_exclusion_reason', 'raw_export_path']
    trace_path = root / 'analysis_results/annotation_research_prework_20260905_v2/evidence/initialization_trace.csv'
    responses = join_index(a[fields], read(base / 'response_links.csv.gz'),
                           read(base / 'facts/active_time_context.csv.gz'), read(trace_path))
    if responses.duplicated(['context_key', 'worker_id']).any():
        raise ValueError('Repeated worker within a context')
    out.mkdir(parents=True, exist_ok=True)
    responses.to_csv(out / 'response_index.csv.gz', index=False)
    contexts = []
    for context, group in responses.groupby('context_key'):
        row = {'context_key': context}
        for field in ['image_id', 'building_id', 'stage', 'block_index', 'raw_condition']:
            if group[field].nunique() != 1:
                raise ValueError('Context metadata conflict: ' + field)
            row[field] = group[field].iloc[0]
        row.update(response_count=len(group), worker_count=group.worker_id.nunique(),
                   current20_worker_count=group.loc[group.current20_member.str.lower() == 'true', 'worker_id'].nunique(),
                   observed_active_time_count=int(group.active_time_seconds.ne('').sum()),
                   initialization_trace_count=int(group.initialization_reconstructed_source.ne('').sum()),
                   initialization_source_set_json=json.dumps(sorted(set(group.initialization_reconstructed_source) - {''})))
        contexts.append(row)
    pd.DataFrame(contexts).to_csv(out / 'context_index.csv', index=False)
    summaries = []
    for (stage, condition), group in responses.groupby(['stage', 'raw_condition']):
        summaries.append(dict(stage=stage, condition=condition, responses=len(group),
                              images=group.image_id.nunique(), contexts=group.context_key.nunique(),
                              workers=group.worker_id.nunique(), buildings=group.building_id.nunique()))
    pd.DataFrame(summaries).to_csv(out / 'coverage_by_condition.csv', index=False)
    qa = dict(canonical_responses=len(responses), historical_images=responses.image_id.nunique(),
              workers=responses.worker_id.nunique(), contexts=len(contexts),
              actual_initialization_traces=int(responses.initialization_reconstructed_source.ne('').sum()),
              source_trace=str(trace_path.relative_to(root)).replace('\\', '/'),
              response_index_fields=list(responses.columns), context_index_fields=list(contexts[0]),
              rules='缺失时间不补零；旧排除保留属性；初始化追溯不等于实际观看事件；不改旧来源标签。')
    (out / 'INDEX_QA.json').write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in qa.items() if not k.endswith('_fields')}, ensure_ascii=False))


def check_prepared(root, out):
    """仅使用仓库内文件核对交付连接；不访问外部模型目录或图片服务。"""
    def read(name):
        return pd.read_csv(out / name, dtype=str, keep_default_na=False)
    def jsonl(name):
        return [json.loads(line) for line in (out / name).read_text(encoding='utf-8').splitlines() if line.strip()]
    index = read('response_index.csv.gz')
    geometry = read('geometry/human_bi_comparisons.csv.gz')
    contexts = read('context_index.csv')
    ids = set(index.canonical_annotation_id)
    assert index.canonical_annotation_id.is_unique
    assert set(geometry.canonical_annotation_id) == ids
    assert geometry.groupby('canonical_annotation_id').size().eq(6).all()
    assert not geometry.duplicated(['canonical_annotation_id', 'reading', 'representation']).any()
    assert set(contexts.context_key) == set(index.context_key)
    cases = jsonl('semantics/case_evidence.jsonl')
    links = jsonl('semantics/response_semantic_links.jsonl')
    assert len(cases) == len({r['case_id'] for r in cases}) == 50
    human_links = [r for r in links if r.get('canonical_annotation_id')]
    assert all(r['canonical_annotation_id'] in ids for r in human_links)
    assert all(r['scope_of_claim'] == 'displayed_object_only' for r in links)
    assert all(r['semantic_label_is_final_human_adjudication'] is False for r in links)
    base = root / 'analysis_results/uncertainty_cloud_inputs_20260906_v1'
    members = pd.read_csv(base / 'clusters/memberships.csv.gz', dtype=str, keep_default_na=False)
    versions = {r['raw_annotation_version_id'] for r in
                (json.loads(line) for line in (base / 'raw_annotation_versions.jsonl').read_text(encoding='utf-8').splitlines())}
    assert set(members.loc[members.mapping_status == 'matched', 'canonical_annotation_id']) <= ids
    assert set(members.loc[members.mapping_status == 'raw_version_only', 'raw_annotation_version_id']) <= versions
    qa = dict(canonical_responses=len(index), contexts=len(contexts), human_bi_rows=len(geometry),
              case_records=len(cases), response_semantic_links=len(human_links),
              legacy_member_status=members.mapping_status.value_counts().to_dict(),
              raw_version_count=len(versions), external_model_or_image_access=False,
              field_contract='见README_ZH.md及各子目录说明；数据可连接不代表语义、几何或工人类型已获确认。')
    (out / 'DELIVERY_QA.json').write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(qa, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--check-prepared', action='store_true')
    args = parser.parse_args()
    (check_prepared if args.check_prepared else main)(args.root.resolve(), args.out)
