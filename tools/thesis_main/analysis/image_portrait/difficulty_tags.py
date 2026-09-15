"""Materialize user-confirmed difficulty tags; no human outcomes or model fitting."""
from collections import Counter
import gzip
import json

from .common import BUNDLE, read_images, save_json

OUT = BUNDLE / 'difficulty_tags_20260915_v1'
ORDINAL = {'简单': 0, '中等': 1, '困难': 2}


def materialize(images, spatial):
    byid = {r['image_id']: r for r in spatial}
    if (len(byid) != len(spatial) or len({r['image_id'] for r in images}) != len(images)
            or set(byid) != {r['image_id'] for r in images}):
        raise ValueError('Image identity mismatch or duplicates')
    rows = []
    for im in images:
        r = byid[im['image_id']]
        if r['building'] != im['building']:
            raise ValueError('Building identity mismatch')
        d = r['latest_selection_record']
        if d is not None and (d['image_id'] != im['image_id'] or d['difficulty'] not in {*ORDINAL, '未定'}):
            raise ValueError('Selection identity or difficulty vocabulary mismatch')
        tag = d['difficulty'] if d is not None else None
        scene = r['spatial_classification']['coarse_type'] or r['spatial_prior_user']['user_type']
        if not isinstance(scene, str) or not scene:
            raise ValueError('Missing human scene category')
        rows.append(dict(image_id=im['image_id'], building=im['building'], source_split=im['source_split'],
                         scene_category=scene,
                         scene_source=r['spatial_field_sources']['coarse_type'],
                         selection_display_group=d['group'] if d is not None else None,
                         difficulty_tag=tag, difficulty_ordinal=ORDINAL.get(tag),
                         difficulty_status='not_recorded' if d is None else 'labelled' if tag in ORDINAL else 'undetermined'))
    return rows


def counts_by(rows, field):
    result = []
    for value in sorted({r[field] for r in rows if r[field] is not None}):
        group = [r for r in rows if r[field] == value]
        tags = Counter(r['difficulty_tag'] for r in group)
        result.append({field: value, 'all_images': len(group),
                       'labelled': sum(tags[t] for t in ORDINAL),
                       **{t: tags[t] for t in ORDINAL},
                       'undetermined': tags['未定'], 'not_recorded': tags[None]})
    return result


def main():
    with gzip.open(BUNDLE / 'metadata/spatial_history.jsonl.gz', 'rt', encoding='utf8') as f:
        spatial = [json.loads(line) for line in f]
    rows = materialize(read_images(), spatial)
    tags = Counter(r['difficulty_tag'] for r in rows)
    assert len(rows) == 648 and tags == Counter({'简单': 49, '中等': 41, '困难': 16, '未定': 6, None: 536})
    labelled = [r for r in rows if r['difficulty_status'] == 'labelled']
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'image_tags.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf8')
    summary = dict(schema='image_difficulty_tag_inventory_v1', user_confirmed='2026-09-15: use located tags',
                   source='metadata/spatial_history.jsonl.gz#/latest_selection_record',
                   original_source='analysis_results/candidate_selection_review_20260913_v2/用户审查原始记录.json#/decisions',
                   total_images=len(rows), labelled_images=len(labelled),
                   labels={t: tags[t] for t in ORDINAL}, undetermined=tags['未定'], not_recorded=tags[None],
                   labelled_buildings=len({r['building'] for r in labelled}),
                   labelled_display_groups=len({r['selection_display_group'] for r in labelled}),
                   scene_counts=counts_by(rows, 'scene_category'),
                   building_counts=counts_by(rows, 'building'),
                   display_group_counts=counts_by(rows, 'selection_display_group'),
                   limitations=['Counts only; no significance or model fitting.',
                                'Scene: spatial_classification.coarse_type when nonempty; else existing spatial_prior_user.user_type, as in Pro v2 evidence_layers.',
                                'Display groups are not independent physical-room identities.',
                                'User difficulty judgments are not verified human convergence outcomes.',
                                'Ordinal 0/1/2 records order, not equal distances.',
                                'Unlabelled images are retained, never relabelled as easy.'])
    save_json(OUT / 'coverage.json', summary)
    # Make a compact, checkable descriptive table; inference remains the Pro task.
    lines = ['# 已确认难易标签：覆盖与场景分布', '',
             '仅为计数核对，未拟合模型或检验显著性。用户已确认使用这批标签。', '',
             '648图中简单49、中等41、困难16，共106张有标签；6张未定、536张无该版记录。',
             '有标签图来自13个building、21个展示组；展示组不是物理房间普查。', '',
             '|场景原分类|648池图数|有标签|简单|中等|困难|', '|---|---:|---:|---:|---:|---:|']
    for r in summary['scene_counts']:
        name = r['scene_category'].replace('|', '\\|').replace('\n', ' ')
        lines.append(f"|{name}|{r['all_images']}|{r['labelled']}|{r['简单']}|{r['中等']}|{r['困难']}|")
    lines += ['', '各类被选中填写难易tag的比例不同，不能把这些标签频数解释为648图总体难度分布。',
              '分类字符串保留来源原文；同类别、同房/楼重复及选择因素需要在后续分析中区分。']
    (OUT / '覆盖与场景分布.md').write_text('\n'.join(lines) + '\n', encoding='utf8')
    print('648 identities; 106 confirmed tags; counts materialized; no model fitting.')


if __name__ == '__main__':
    main()
