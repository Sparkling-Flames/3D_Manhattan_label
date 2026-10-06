"""接收8图补标，保留旧结果，只重汇总既有人数结果。"""
from collections import Counter
import json

from .difficulty_consensus_20261006 import OUT, REVIEW, scene_group, summarize
from .research_artifact_io import ROOT, INVENTORY, read_csv, write_csv, write_json


def apply_review(meta, payload, identities):
    if payload['schema'] != 'difficulty_review_20261006_v1':
        raise ValueError('不是本次难度补标文件')
    decisions = payload['decisions']
    if len(decisions) != len(REVIEW) or {r['image_code'] for r in decisions} != set(REVIEW):
        raise ValueError('补标图片名单不匹配')
    result = {i: dict(r) for i, r in meta.items()}
    for r in decisions:
        code = r['image_code']
        if r['image_id'] != identities[code]:
            raise ValueError('图片身份不匹配：'+code)
        if r['difficulty'] not in ('简单', '中等', '困难', '暂不能判断'):
            raise ValueError('难度未填写或不支持：'+code)
        item = result[code]
        item.update(previous_difficulty=item['difficulty'], difficulty=r['difficulty'],
                    review_note=r['note'], review_updated_at=r['updated_at'])
        for field, source, mapping in (
            ('oos_status', 'oos', {'是':'confirmed', '否':'not_oos', '不确定':'pending'}),
            ('doorway_status', 'doorway', {'是':'difficult', '否':'none', '不确定':'pending'})):
            if r[source]:
                item[field] = mapping[r[source]]
        item['scene'] = scene_group(item)
    return result


def run():
    dest = OUT/'updated'
    dest.mkdir(exist_ok=True)
    review_path = OUT/'user_review.json'
    payload = json.loads(review_path.read_text(encoding='utf-8-sig'))
    inventory = json.loads(INVENTORY.read_text(encoding='utf-8'))
    meta = {r['image']: dict(r, previous_difficulty=r['difficulty'], review_note='',
                            review_updated_at='') for r in read_csv(OUT/'difficulty_roster.csv')}
    meta = apply_review(meta, payload, {r['image']:r['image_id'] for r in inventory['images']})
    high = ROOT/'analysis_results/worker_count_composition_20261006'
    raw = [r for r in read_csv(high/'per_image.csv') if r['condition']=='manual'
           and r['scenario']=='uniform' and r['policy']=='none' and r['version']=='original']
    new = [dict(image=r['image'], n=int(r['n']), k=int(r['k']), method=r['method'],
                distance=float(r['ref_symdiff_ref'])) for r in raw]
    old = [dict(image=r['image'], n=int(r['n']), k=int(r['k']), method=r['method'],
                distance=float(r['omission_fraction'])+float(r['extension_fraction']))
           for r in read_csv(ROOT/'analysis_results/lee_expanded_20261003/image_curves.csv')
           if r['image'] in meta and r['condition']=='manual' and r['version']=='original']
    common = json.loads((high/'panels.json').read_text(encoding='utf-8'))['common10']['images']
    groups = json.loads((high/'input.json').read_text(encoding='utf-8'))['groups']
    pools = [sorted(r['worker'] for r in g['records']) for g in groups
             if g['image'] in common and g['condition']=='manual']
    assert len(pools)==10 and len(pools[0])==24 and all(p==pools[0] for p in pools)
    summary = summarize(old, meta, 8)+summarize(new, meta, 16)+summarize(new, meta, 20)
    summary += [r for r in summarize([r for r in new if r['image'] in common], meta, 24)
                if r['scope']=='all']
    individual = [dict(image=r['image'], difficulty=meta[r['image']]['difficulty'],
                       note=meta[r['image']]['review_note'], method=r['method'], k=int(r['k']),
                       **{f:float(r[f]) for f in ('ref_symdiff_ref','omission_ref','extension_ref',
                                                  'member_symdiff_union')})
                  for r in raw if r['image'] in common]
    write_csv(dest/'summary.csv', summary)
    write_csv(dest/'difficulty_roster.csv', list(meta.values()))
    write_csv(dest/'common10_per_image.csv', individual)
    contract = json.loads((OUT/'field_contract.json').read_text(encoding='utf-8'))
    contract.update(schema='difficulty_consensus_user_update_v1',
        sources=contract['sources']+[str(review_path.relative_to(ROOT))],
        common10_images=common, common24_workers=pools[0],
        common10_difficulty_counts=dict(Counter(meta[i]['difficulty'] for i in common)),
        roster='原67图名单，8份用户补标覆盖有效难度／场景字段；previous_difficulty保留之前难度，review_note原样保留。',
        individual='共同十图原GT、随机抽组、单一Lee融合；保留遗漏／外扩以及换组波动。后者按全员并集归一化，不与GT误差直接比数值。')
    # 原字段是全259图统计，补标只更新其中8张，其他历史判断保留。
    updated_all = apply_review({r['image']:r for r in inventory['images']}, payload,
                               {r['image']:r['image_id'] for r in inventory['images']})
    contract['label_counts'] = dict(Counter(r['difficulty'] for r in updated_all.values()))
    contract['scene_counts'] = dict(Counter(scene_group(r) for r in updated_all.values()))
    write_json(dest/'field_contract.json', contract)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.sans-serif':['Microsoft YaHei'], 'axes.unicode_minus':False})
    fig, axes = plt.subplots(5, 2, figsize=(12, 15), sharex=True, sharey=True)
    for ax, code in zip(axes.flat, common):
        for method, style, label in [('mv50','-','至少半数'),('mv_strict','--','严格多数')]:
            rows = sorted((r for r in individual if r['image']==code and r['method']==method),key=lambda r:r['k'])
            ax.plot([r['k'] for r in rows],[r['ref_symdiff_ref'] for r in rows],style,label=label)
        ax.set_title(f"{code} · {meta[code]['difficulty']}")
        ax.set_ylim(0,.9);ax.set_xticks([1,4,8,12,16,20,24]);ax.grid(alpha=.2)
    axes[0,0].legend()
    fig.suptitle('同一批24人 · 十图单一融合的范围参考误差',fontsize=17)
    fig.supxlabel('参与人数 k（每组人只产生一个融合区域）')
    fig.supylabel('期望遗漏＋外扩 / GT面积；越小越近')
    fig.tight_layout(rect=(.02,.02,1,.97))
    fig.savefig(dest/'common10_count_error.png',dpi=150);plt.close(fig)
    print(json.dumps(contract['common10_difficulty_counts'],ensure_ascii=False))


if __name__ == '__main__':
    run()
