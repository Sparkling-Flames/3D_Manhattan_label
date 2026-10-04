"""Manual主质量兼容池扩图；逐图1—N，汇总固定图片的多个共同人数窗口。"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

import numpy as np

from .lee_difficulty_20261003 import collect, INVENTORY, UNB
from .lee_tile_precision_20261003 import run, exact_ks, mc_bound
from .lee_tile_stage1_20261002 import ROOT, METHODS, write_json, write_csv
from .research_panel_inventory_20261003 import summarize_groups, DIFFICULTIES

OUT = ROOT/'analysis_results/lee_expanded_20261003'
THRESHOLDS = (2, 4, 8, 12, 16, 20, 24)


def select_groups(groups):
    ledger = []
    for g in groups:
        if g['condition']!='manual' or not g['reference_quality_compatible']:
            status = 'outside_manual_quality_panel'
        elif g['candidate_n']<2:
            status = 'single_person_only'
        elif not g['curve_ready'] or not g['original_bev_ok']:
            status = 'whole_pool_unavailable'
        else:
            status = 'selected'
        ledger.append(dict(g, expansion_status=status))
    return ledger


def summarize(rows, meta, thresholds=THRESHOLDS):
    points = {}
    for r in rows:
        key = (r['image'], r['method'], r['version'], r['k'])
        if key in points:
            raise ValueError('duplicate_curve_point')
        points[key] = r
    if {r['image'] for r in rows} != set(meta):
        raise ValueError('image_population_mismatch')
    for image, m in meta.items():
        versions = {r['version'] for r in rows if r['image']==image} | {'original'}
        for version in versions:
            for method in METHODS:
                series = [r for r in rows if (r['image'],r['method'],r['version'])==(image,method,version)]
                if {r['k'] for r in series}!=set(range(1,m['n']+1)) or any(r['n']!=m['n'] for r in series):
                    raise ValueError('incomplete_image_curve:'+image)
    enriched = []
    for r in rows:
        base = points[r['image'], r['method'], r['version'], 1]
        area = r['expected_omission_h2'] + r['expected_intersection_h2']
        if base['mc_error_bound']!=0 or area<=0:
            raise ValueError('invalid_baseline_or_reference')
        enriched.append(dict(r, **{k:v for k,v in meta[r['image']].items() if k!='n'},
            gain_from_one=r['iou_mean']-base['iou_mean'], gain_mc_error_bound=r['mc_error_bound'],
            omission_fraction=r['expected_omission_h2']/area,
            extension_fraction=r['expected_extension_h2']/area))
    indexed = {(r['image'],r['method'],r['version'],r['k']):r for r in enriched}
    paired = {r['image'] for r in rows if r['version']=='manual_revision'}
    grouped = []
    for limit in thresholds:
        pool = {i for i,m in meta.items() if m['n']>=limit}
        cohorts = {'全部': pool, '已标三档': {i for i in pool if meta[i]['difficulty'] in DIFFICULTIES[:3]},
            '非困难（已标）': {i for i in pool if meta[i]['difficulty'] in DIFFICULTIES[:2]},
            '双参考配对': pool & paired}
        cohorts.update({d:{i for i in pool if meta[i]['difficulty']==d} for d in DIFFICULTIES})
        cohorts.update({'uNb内_'+d:{i for i in pool if meta[i]['difficulty']==d and meta[i]['building']==UNB}
                        for d in DIFFICULTIES[:3]})
        for cohort, images in cohorts.items():
            if not images:
                continue
            for version in ('original','manual_revision') if cohort=='双参考配对' else ('original',):
                for method in METHODS:
                    for k in range(1,limit+1):
                        selected = [indexed[i,method,version,k] for i in sorted(images)]
                        averages = {f:float(np.mean([r[f] for r in selected])) for f in
                            ('iou_mean','gain_from_one','mc_error_bound','gain_mc_error_bound','omission_fraction','extension_fraction')}
                        grouped.append(dict(panel_max_k=limit,cohort=cohort,version=version,method=method,k=k,
                            image_n=len(images),building_n=len({meta[i]['building'] for i in images}),
                            images='|'.join(sorted(images)),**averages))
    return enriched, grouped


def figures(rows, grouped, out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    font_manager.fontManager.addfont('C:/Windows/Fonts/msyh.ttc')
    plt.rcParams.update({'font.family':'Microsoft YaHei','axes.unicode_minus':False,'font.size':9})
    for kind in ('reference','gain','difficulty'):
        fig, axes = plt.subplots(2,3,figsize=(16,9))
        for ax, limit in zip(axes.flat,THRESHOLDS[1:]):
            selections = [(d,'mv50') for d in DIFFICULTIES[:3]] if kind=='difficulty' else [('全部',m) for m in METHODS]
            for cohort, method in selections:
                rs = [r for r in grouped if (r['panel_max_k'],r['cohort'],r['method'],r['version'])==(limit,cohort,method,'original')]
                if not rs:continue
                y = np.array([r['gain_from_one' if kind=='gain' else 'iou_mean'] for r in rs])
                e = np.array([r['mc_error_bound'] for r in rs]); x = [r['k'] for r in rs]
                line, = ax.plot(x,y,'.-',label=f'{cohort} {method}（{rs[0]["image_n"]}图）')
                ax.fill_between(x,y-e,y+e,color=line.get_color(),alpha=.12)
            ticks=list(range(1,limit+1)) if limit<=8 else sorted({1,limit,*range(4,limit+1,4)})
            ax.set(title=f'固定N≥{limit}图片；1—{limit}人',xlabel='人数',ylabel='相对单人增益' if kind=='gain' else '平均BEV IoU',xticks=ticks,xlim=(1,limit))
            if kind!='gain':ax.set_ylim(0,1)
            else:ax.axhline(0,color='gray',linewidth=.5)
            ax.grid(alpha=.2);ax.legend(fontsize=8)
        fig.suptitle('Manual主质量兼容：各子图内部图片固定；不同子图不是同一图片群体')
        fig.text(.5,.01,'阴影仅同时MC计算误差，非人群置信区间。未记录／未定难度不归入非困难。',ha='center')
        fig.tight_layout(rect=(0,.04,1,.96));fig.savefig(out/f'fixed_panels_{kind}.png',dpi=150);plt.close(fig)
    images = list(dict.fromkeys(r['image'] for r in rows))
    for start in range(0,len(images),12):
        fig, axes = plt.subplots(4,3,figsize=(15,12))
        for ax, image in zip(axes.flat,images[start:start+12]):
            chosen = [r for r in rows if r['image']==image]
            for method,color in zip(METHODS,['tab:blue','tab:orange']):
                for version,style in [('original','-'),('manual_revision','--')]:
                    rs = [r for r in chosen if r['method']==method and r['version']==version]
                    if not rs:continue
                    x=[r['k'] for r in rs]; y=np.array([r['iou_mean'] for r in rs]); e=np.array([r['mc_error_bound'] for r in rs])
                    ax.plot(x,y,style,color=color,label=method+(' 原始' if version=='original' else ' 修订'))
                    ax.fill_between(x,np.maximum(0,y-e),np.minimum(1,y+e),color=color,alpha=.10)
            n=chosen[0]['n']; ticks=list(range(1,n+1)) if n<=8 else sorted({1,n,*range(4,n+1,4)})
            ax.set(title=f'{image} | {chosen[0]["difficulty"]} | N={n}',xlabel='人数',ylabel='BEV IoU',ylim=(0,1),xticks=ticks,xlim=(1,n))
            ax.grid(alpha=.2);ax.legend(fontsize=6)
        for ax in list(axes.flat)[len(images[start:start+12]):]:ax.set_visible(False)
        fig.suptitle('逐图1—N：固定GT参考一致性；全员点不证明人数已足够')
        fig.tight_layout(rect=(0,0,1,.97));fig.savefig(out/f'per_image_{start//12+1:02d}.png',dpi=130);plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,default=OUT)
    parser.add_argument('--input',type=Path,help='复算本轮source_input.json，包含失败整池')
    parser.add_argument('--inventory',type=Path,default=INVENTORY,help='新运行使用的盘点目录；--input仍重放相邻冻结盘点')
    args=parser.parse_args(); out=args.out
    if (out/'design.json').exists():
        raise ValueError('use_new_output_directory')
    out.mkdir(parents=True,exist_ok=True)
    inventory_path=args.input.parent/'inventory_input.json' if args.input else args.inventory/'input.json'
    inventory=json.loads(inventory_path.read_text(encoding='utf-8'))
    ledger=select_groups(summarize_groups(inventory['records'],{i['image']:i for i in inventory['images']}))
    write_csv(out/'selection_ledger.csv',ledger)
    wanted=[g['image'] for g in ledger if g['expansion_status'] in ('selected','whole_pool_unavailable')]
    ready={g['image']:g for g in ledger if g['expansion_status']=='selected'}
    source=json.loads(args.input.read_text(encoding='utf-8')) if args.input else collect(out,chosen=wanted,stage='S3-A-expanded',max_k=None,inventory_dir=args.inventory)
    if sorted(i['code'] for i in source['images'])!=sorted(wanted):
        raise ValueError('source_population_mismatch')
    write_json(out/'source_input.json',source)
    write_json(out/'inventory_input.json',inventory)
    data=dict(source,images=[i for i in source['images'] if i['code'] in ready])
    for im in data['images']:
        candidates=[r for r in im['annotations'] if r['independent'] and r['consensus_eligible'] and
                    r['condition']=='manual' and r['main_consensus_gate']['status']=='main_candidate']
        if (len(candidates)!=ready[im['code']]['candidate_n'] or any(r['footprint'] is None or not r['quality_candidate'] for r in candidates)
                or '|'.join(sorted(r['worker'] for r in candidates))!=ready[im['code']]['workers']):
            raise ValueError('roster_or_geometry_drift:'+im['code'])
    write_json(out/'input.json',data)
    comparisons=sum(2*sum(k not in exact_ks(ready[im['code']]['candidate_n']) for k in range(1,ready[im['code']]['candidate_n']+1))
                    *sum(r['footprint'] is not None for r in im['references']) for im in data['images'])
    if mc_bound(16384,comparisons)>.02:raise ValueError('insufficient_preplanned_precision')
    write_json(out/'preflight.json',dict(status='passed',selection='S2 Manual main-quality-compatible full pools, N>=2; no difficulty filter',
        attempted_images=len(wanted),ready_images=len(ready),blocked=[g for g in ledger if g['expansion_status']=='whole_pool_unavailable'],
        fixed_panel_max_k=THRESHOLDS,draws=16384,mc_comparisons=comparisons,mc_error_bound=mc_bound(16384,comparisons)))
    rows=run(out/'input.json',out,16384,stratum=('manual','main_candidate'),make_plot=False)
    meta={im['code']:dict(n=ready[im['code']]['candidate_n'],**{k:im[k] for k in ('difficulty','building','room')}) for im in data['images']}
    enriched, grouped=summarize(rows,meta)
    write_csv(out/'image_curves.csv',enriched);write_csv(out/'fixed_panel_curves.csv',grouped)
    cohorts=[dict(panel_max_k=k,image_n=sum(m['n']>=k for m in meta.values()),
        difficulty_counts=dict(Counter(m['difficulty'] for m in meta.values() if m['n']>=k)),
        images=sorted(i for i,m in meta.items() if m['n']>=k)) for k in THRESHOLDS]
    write_json(out/'fixed_panels.json',cohorts)
    contract=json.loads((out/'field_contract.json').read_text(encoding='utf-8'))
    contract.update(stage='S3-A-expanded',group_fields=list(grouped[0]),image_fields=list(enriched[0]),
        fixed_panels='每个panel_max_k内固定N>=上限的图片，图片等权；不同panel之间不得连成一条人数曲线。',
        unknown='未记录、未定独立保留；非困难（已标）仅简单及中等。',
        failure='selection_ledger包含所有S2池；source_input保留尝试范围的失败整池；input仅成功整池，不删除失败人员缩小N。',
        gain='同图同规则同参考减精确k=1；组MC界平均。不同k之差取两端界之和。',
        reference='全部及难度组采用original；manual_revision仅在相同图片双参考配对组比较。')
    write_json(out/'field_contract.json',contract)
    write_json(out/'summary.json',dict(images=len(meta),candidates=sum(m['n'] for m in meta.values()),
        buildings=len({m['building'] for m in meta.values()}),raw_records=sum(len(i['annotations']) for i in data['images']),
        workers=len({r['worker'] for im in data['images'] for r in im['annotations'] if r['independent'] and r['consensus_eligible'] and r['condition']=='manual' and r['main_consensus_gate']['status']=='main_candidate'}),
        curves=len(rows),estimators=dict(Counter(r['estimator'] for r in rows)),fixed_panels=cohorts,
        difficulty=dict(Counter(m['difficulty'] for m in meta.values())),warnings=len(json.loads((out/'warnings.json').read_text(encoding='utf-8')))))
    figures(enriched,grouped,out)


if __name__=='__main__':
    main()
