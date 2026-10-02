"""S3-A：固定45图、Manual主候选、1—8人；只描述粗难度与参考曲线。"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import warnings

import numpy as np

from .lee_tile_stage1_20261002 import ROOT, METHODS, write_json, write_csv
from .lee_tile_precision_20261003 import run, exact_ks, mc_bound
from .research_round_20260929 import prepare_record, reconstruct, validate_panel
from .research_panel_inventory_20261003 import bind_difficulty, HUMAN

INVENTORY = ROOT/'analysis_results/research_panel_inventory_20261003'
DEFAULT_OUT = ROOT/'analysis_results/lee_difficulty_20261003'
UNB = 'uNb9QFRL6hY'


def collect(out):
    """沿用当前完整包；逐对象对照S2资格/方法状态，不由曲线选择数据。"""
    from tools.thesis_main.data_prep.consolidate_research_input import load_current_bundle
    from tools.thesis_main.data_prep.project_public_research_20260929 import project_bundle
    inventory = json.loads((INVENTORY/'input.json').read_text(encoding='utf-8'))
    chosen = json.loads((INVENTORY/'next_panels.json').read_text(encoding='utf-8'))['a']['images']
    old_images = {i['image']:i for i in inventory['images']}
    old_records = {r['id']:r for r in inventory['records']+inventory['references']}
    bundle=load_current_bundle(); panel,mapping=project_bundle(bundle)
    source={mapping['records'][o['object_id']]:o for o in bundle['data']['objects']}
    current_images={i['image_code']:i for i in bundle['research']['images']}
    labels=bind_difficulty(json.loads((ROOT/HUMAN).read_text(encoding='utf-8-sig')),
                           [i['image_id'] for i in current_images.values()])
    images=[]; checks=[]; notices=[]
    for im in panel['images']:
        if im['code'] not in chosen:
            continue
        old=old_images[im['code']]; current=current_images[im['code']]
        if (current['image_id']!=old['image_id'] or labels[current['image_id']]!=old['difficulty']
                or im['building']!=old['building'] or im['room']!=old['room']):
            raise ValueError('image_or_label_drift:'+im['code'])
        im.update(difficulty=old['difficulty'],image_id=old['image_id'])
        for field in ('annotations','references'):
            updated=[]
            for r in im[field]:
                prepared=prepare_record(dict(r,source_pair_indices=source[r['id']]['ordered_source_pair_indices']))
                if prepared['points'] is not None:
                    expected_points=[source[r['id']]['preprocessed_points'][j] for j in prepared['source_point_indices']]
                    if not np.array_equal(np.asarray(prepared['points']),np.asarray(expected_points)):
                        raise ValueError('preprocessed_coordinate_binding_mismatch:'+r['id'])
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter('always',RuntimeWarning)
                    geometry=reconstruct(prepared)
                notices.extend(dict(id=r['id'],message=str(w.message)) for w in caught)
                state=geometry['representations']['declared_footprint']; previous=old_records[r['id']]
                if (state['status']=='ok') != previous['bev_ok'] or prepared['order_used']!=previous['order_used']:
                    raise ValueError('geometry_or_order_drift:'+r['id'])
                if field=='annotations':
                    for key,value in dict(worker=r['worker'],condition=r['condition'],independent=r['independent'],
                        consensus_gate=r['main_consensus_gate']['status'],quality_gate=r['main_quality_gate']['status']).items():
                        if previous[key]!=value:
                            raise ValueError('record_binding_drift:'+r['id']+':'+key)
                prepared['footprint']=geometry['floor'].tolist() if state['status']=='ok' else None
                prepared['footprint_state']=state
                updated.append(prepared); checks.append(dict(id=r['id'],image=im['code'],status='matched_S2_and_current_bundle',
                    coordinates='exact_source_index_match' if prepared['points'] is not None else 'unavailable_preserved'))
            im[field]=updated
        images.append(im)
    if sorted(chosen)!=sorted(i['code'] for i in images) or len(images)!=45:
        raise ValueError('fixed_45_image_panel_mismatch')
    validate_panel(dict(schema='layout_research_panel_v1',images=images))
    for im in images:
        got={r['id'] for r in im['annotations']+im['references']}
        expected={r['id'] for r in inventory['records']+inventory['references'] if r['image']==im['code']}
        if got!=expected:
            raise ValueError('record_population_drift:'+im['code'])
    write_json(out/'source_binding.json',dict(status='passed',objects=len(checks),records=checks,warnings=notices,
        source_manifest=panel['source_manifest'],selection='S2 next_panels.a; source coordinates from current validated bundle, not inventory statuses'))
    data=dict(schema='lee_tile_stage1_input_v1',images=images,plan=dict(stage='S3-A',max_k=8,
        condition='manual',gate='main_candidate',difficulty_counts=dict(Counter(i['difficulty'] for i in images)),
        source_manifest=panel['source_manifest'],selection_source='analysis_results/research_panel_inventory_20261003/next_panels.json'))
    write_json(out/'input.json',data)
    return data


def summarize(rows, meta):
    by_point={}
    for r in rows:
        key=(r['image'],r['method'],r['version'],r['k'])
        if key in by_point:
            raise ValueError('duplicate_curve_point')
        by_point[key]=r
    ks=set(range(1,max(r['k'] for r in rows)+1))
    for image in meta:
        for method in METHODS:
            if {r['k'] for r in rows if (r['image'],r['method'],r['version'])==(image,method,'original')} != ks:
                raise ValueError('nonconstant_image_panel')
    versions={v:{r['image'] for r in rows if r['version']==v} for v in {r['version'] for r in rows}}
    enriched=[]
    for r in rows:
        base=by_point[r['image'],r['method'],r['version'],1]
        reference_area=r['expected_omission_h2']+r['expected_intersection_h2']
        if reference_area<=0 or base['mc_error_bound']!=0:
            raise ValueError('invalid_reference_or_inexact_singleton')
        enriched.append(dict(r,**meta[r['image']],gain_from_one=r['iou_mean']-base['iou_mean'],
            gain_mc_error_bound=r['mc_error_bound'],reference_area_h2=reference_area,
            omission_fraction=r['expected_omission_h2']/reference_area,
            extension_fraction=r['expected_extension_h2']/reference_area))
    cohorts={'全部':set(meta),'非困难':{i for i,m in meta.items() if m['difficulty']!='困难'}}
    for difficulty in ('简单','中等','困难'):
        cohorts[difficulty]={i for i,m in meta.items() if m['difficulty']==difficulty}
        cohorts['uNb内_'+difficulty]={i for i,m in meta.items() if m['difficulty']==difficulty and m['building']==UNB}
    cohorts['双参考配对']=versions.get('manual_revision',set())
    result=[]
    for cohort,images in cohorts.items():
        if not images:continue
        for version in ('original','manual_revision') if cohort=='双参考配对' else ('original',):
            for method in METHODS:
                for k in sorted(ks):
                    group=[r for r in enriched if r['image'] in images and r['method']==method and r['version']==version and r['k']==k]
                    if len(group)!=len(images) or {r['image'] for r in group}!=images:
                        raise ValueError('nonconstant_image_panel')
                    values={name:float(np.mean([r[name] for r in group])) for name in
                            ('iou_mean','gain_from_one','mc_error_bound','gain_mc_error_bound','omission_fraction','extension_fraction')}
                    result.append(dict(cohort=cohort,method=method,version=version,k=k,image_n=len(images),
                        building_n=len({meta[i]['building'] for i in images}),images='|'.join(sorted(images)),**values))
    return enriched,result


def figures(rows, grouped, out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    font_manager.fontManager.addfont('C:/Windows/Fonts/msyh.ttc')
    plt.rcParams.update({'font.family':'Microsoft YaHei','axes.unicode_minus':False,'font.size':10})
    families=[('简单','中等','困难'),('全部','非困难','困难'),('uNb内_简单','uNb内_中等','uNb内_困难')]
    for method in METHODS:
        fig,axes=plt.subplots(2,3,figsize=(15,8),squeeze=False)
        for j,family in enumerate(families):
            for name,color in zip(family,['tab:blue','tab:orange','tab:green']):
                rs=sorted([r for r in grouped if r['cohort']==name and r['method']==method and r['version']=='original'],key=lambda r:r['k'])
                for i,field in enumerate(['iou_mean','gain_from_one']):
                    ax=axes[i,j];x=[r['k'] for r in rs];y=np.array([r[field] for r in rs]);e=np.array([r['mc_error_bound'] for r in rs])
                    ax.plot(x,y,'o-',color=color,label=f"{name}（{rs[0]['image_n']}图）",markersize=3)
                    ax.fill_between(x,np.maximum(0,y-e) if i==0 else y-e,np.minimum(1,y+e) if i==0 else y+e,color=color,alpha=.12)
                    ax.set(xlabel='人数',ylabel='平均参考IoU' if i==0 else '相对单人均值的改善',xticks=range(1,9))
                    ax.grid(alpha=.2);ax.legend(fontsize=8)
        axes[0,0].set_title('人工粗难度');axes[0,1].set_title('单列困难图');axes[0,2].set_title('同一uNb建筑内部（仍有人员差异）')
        for ax in axes[0]:ax.set_ylim(0,1)
        for ax in axes[1]:ax.axhline(0,color='gray',linewidth=.7)
        fig.suptitle(f'{method}：固定图片、原始参考、图片等权；中等13图均来自同一建筑')
        fig.text(.5,.01,'阴影仅为同时MC均值计算误差界；不是总体置信区间。不同图人员池不同；不推断独立难度效应。',ha='center',fontsize=10)
        fig.tight_layout(rect=(0,.035,1,.95));fig.savefig(out/f'groups_{method}.png',dpi=160);plt.close(fig)
    fig,axes=plt.subplots(2,2,figsize=(12,8))
    for i,method in enumerate(METHODS):
        for name in ('简单','中等','困难'):
            rs=[r for r in grouped if r['cohort']==name and r['method']==method]
            for j,field in enumerate(['omission_fraction','extension_fraction']):
                axes[i,j].plot([r['k'] for r in rs],[r[field] for r in rs],'o-',label=name)
                axes[i,j].set(title=method,xlabel='人数',ylabel=('遗漏' if j==0 else '外扩')+'面积 / 参考面积',xticks=range(1,9))
                axes[i,j].grid(alpha=.2);axes[i,j].legend()
    fig.suptitle('解析面积期望：先逐图除以参考面积，再图片等权；不是平均IoU')
    fig.tight_layout(rect=(0,0,1,.95));fig.savefig(out/'area_diagnostics.png',dpi=160);plt.close(fig)
    images=list(dict.fromkeys(r['image'] for r in rows))
    for start in range(0,len(images),9):
        fig,axes=plt.subplots(3,3,figsize=(15,10))
        for ax,image in zip(axes.flat,images[start:start+9]):
            selected=[r for r in rows if r['image']==image]
            for method,color in zip(METHODS,['tab:blue','tab:orange']):
                for version,style in [('original','-'),('manual_revision','--')]:
                    rs=[r for r in selected if r['method']==method and r['version']==version]
                    if not rs:continue
                    x=[r['k'] for r in rs];y=np.array([r['iou_mean'] for r in rs]);e=np.array([r['mc_error_bound'] for r in rs])
                    ax.plot(x,y,style,color=color,label=method+(' 原始' if version=='original' else ' 修订'))
                    ax.fill_between(x,np.maximum(0,y-e),np.minimum(1,y+e),color=color,alpha=.1)
                ax.set(title=f"{image} | {selected[0]['difficulty']} | N={selected[0]['n']}",xlabel='人数',ylabel='参考IoU',ylim=(0,1),xticks=range(1,9))
                ax.grid(alpha=.2);ax.legend(fontsize=7)
        for ax in list(axes.flat)[len(images[start:start+9]):]:ax.set_visible(False)
        fig.suptitle('逐图固定池参考均值；阴影仅MC计算误差，不表示人群不确定性')
        fig.tight_layout(rect=(0,0,1,.96));fig.savefig(out/f'per_image_{start//9+1}.png',dpi=150);plt.close(fig)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,help='直接复算已固定的输入；省略则绑定当前bundle与S2')
    parser.add_argument('--out',type=Path,default=DEFAULT_OUT)
    args=parser.parse_args();out=args.out;out.mkdir(parents=True,exist_ok=True)
    data=json.loads(args.input.read_text(encoding='utf-8')) if args.input else collect(out)
    if args.input:write_json(out/'input.json',data)
    validate_panel(dict(schema='layout_research_panel_v1',images=data['images']))
    meta={i['code']:{k:i[k] for k in ('difficulty','building','room')} for i in data['images']}
    expected_images=json.loads((INVENTORY/'next_panels.json').read_text(encoding='utf-8'))['a']['images']
    if set(meta)!=set(expected_images):
        raise ValueError('fixed_45_image_identity_mismatch')
    if len(meta)!=45 or Counter(m['difficulty'] for m in meta.values())!={'简单':22,'中等':13,'困难':10}:
        raise ValueError('fixed_difficulty_panel_mismatch')
    candidate_counts={im['code']:sum(r['independent'] and r['consensus_eligible'] and r['condition']=='manual'
        and r['main_consensus_gate']['status']=='main_candidate' for r in im['annotations']) for im in data['images']}
    comparisons=sum(2*sum(k not in exact_ks(candidate_counts[im['code']]) for k in range(1,9))
                    *sum(r['footprint'] is not None for r in im['references']) for im in data['images'])
    if min(candidate_counts.values())<8 or comparisons!=464 or mc_bound(16384,comparisons)>.02:
        raise ValueError('planned_precision_population_drift')
    write_json(out/'preflight.json',dict(status='passed',images=45,counts=candidate_counts,
        mc_comparisons=comparisons,draws=16384,simultaneous_mc_bound=mc_bound(16384,comparisons),
        scope='计算前固定名单与预算；没有按结果调整批次'))
    try:
        rows=run(out/'input.json',out,16384,max_k=8,stratum=('manual','main_candidate'),make_plot=False)
        enriched,grouped=summarize(rows,meta)
        write_csv(out/'image_curves.csv',enriched);write_csv(out/'group_curves.csv',grouped)
        design=json.loads((out/'design.json').read_text(encoding='utf-8'))
        if design['simultaneous_mc_comparisons']!=464 or not design['precision_target_met']:
            raise ValueError('planned_precision_population_drift')
        contract=json.loads((out/'field_contract.json').read_text(encoding='utf-8'))
        contract.update(difficulty_stage='S3-A',image_fields=list(enriched[0]),group_fields=list(grouped[0]),
            grouping='固定图片集合，图片等权；同uNb建筑与去困难对照均为描述，不是因果或总体检验。',
            gain='每图同规则同参考减去精确单人均值；MC误差界保持原界。组均值界为逐图界平均，不假设跨图独立。',
            areas='omission/extension_fraction为逐图解析面积期望除以对应参考面积，再图片等权；不是比值的IoU期望。',
            dual_reference='仅在有双参考的同一2图上配对汇总，不与45图均值直接比较。',
            coverage='输入保留45图所有条件及既有资格；仅Manual/main_candidate的独立票参与。其他条件不属于本轮，不称清洗剔除。')
        write_json(out/'field_contract.json',contract)
        figures(enriched,grouped,out)
    except Exception as exc:
        write_json(out/'failure.json',dict(status='failed',error=type(exc).__name__,message=str(exc),policy='不删人、不修复、不发布成功解释'))
        raise


if __name__=='__main__':
    main()
