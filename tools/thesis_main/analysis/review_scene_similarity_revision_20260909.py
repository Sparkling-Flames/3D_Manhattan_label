"""独立回读房间类别连接并重组已审计曲线；不推断房间实例或人数阈值。"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
import re
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
from statistics import mean, median

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'analysis_results/scene_similarity_revision_20260909_v1'
SOURCE = Path('D:/Work/Manhattan_3D/mp3d_layout_gt_sources/Matterport_official/tasks/region_classification/data')
OLD = ROOT / 'analysis_results/building_convergence_evidence_20260908_v1/review'
IMAGES = ROOT / 'analysis_results/uncertainty_visual_review_20260907_v1/reproduced_numerical/census/images_380.csv'


def rows(path):
    return list(iter_rows(path))


def iter_rows(path):
    opener = gzip.open if str(path).endswith('.gz') else open
    with opener(path, 'rt', encoding='utf-8-sig', newline='') as f:
        yield from csv.DictReader(f)


def write_csv(path, records):
    if not records:
        raise ValueError(f'empty records: {path}')
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(records[0])); w.writeheader(); w.writerows(records)


def source_identity(path: str, kind: str):
    parts = path.replace('\\', '/').split('/')
    match = re.fullmatch(r'([0-9a-f]{32})(?:_i[0-9]+_[0-9]+)?\.jpg', parts[-1])
    if not match:
        raise ValueError(f'unrecognized image: {path}')
    if kind == 'single':
        if len(parts) < 3 or parts[-2] != 'undistorted_color_images':
            raise ValueError(f'unrecognized single directory: {path}')
        building = parts[-3]
    elif kind == 'pano':
        if len(parts) < 2:
            raise ValueError(path)
        building = parts[-2]
    else:
        raise ValueError(kind)
    return building + '_' + match.group(1)


def load_classes(source=SOURCE):
    evidence = defaultdict(set)
    indexes, inventory = {}, []
    for split in ('train', 'test'):
        for kind in ('pano', 'single'):
            a = source / f'{split}_room_{kind}_image.txt'
            b = source / f'{split}_room_{kind}_label.txt'
            paths, labels = a.read_text().splitlines(), b.read_text().splitlines()
            if len(paths) != len(labels):
                raise ValueError(f'row alignment mismatch: {a}')
            values = defaultdict(set)
            for path, label in zip(paths, labels):
                identity = source_identity(path, kind)
                code = int(label)
                if not 1 <= code <= 12:
                    raise ValueError(f'unknown code {code}')
                values[identity].add(code); evidence[identity].add(code)
            indexes[split, kind] = dict(values)
            inventory.append(dict(split=split, kind=kind, rows=len(paths), unique_images=len(values), bytes=a.stat().st_size+b.stat().st_size))
    conflicts = {k: sorted(v) for k, v in evidence.items() if len(v) > 1}
    if conflicts:
        raise ValueError(f'conflicting labels: {conflicts}')
    return {k: next(iter(v)) for k, v in evidence.items()}, indexes, inventory


def pair_summary(records):
    """分别报告图对等权和楼/楼对等权；不把两者或重采样当独立实验。"""
    groups = defaultdict(list)
    for r in records:
        groups[r['building_relation'], r['class_relation']].append(r)
    result = []
    for (building_relation, class_relation), group in sorted(groups.items()):
        total_pairs=len(group)
        group=[r for r in group if r.get('status','comparable')=='comparable']
        if not group:
            continue
        blocks = defaultdict(list)
        for r in group:
            blocks[tuple(sorted((r['left_building'], r['right_building'])))].append(float(r['curve_distance']))
        distances = [float(r['curve_distance']) for r in group]
        shared = [int(r['shared_replicates']) for r in group]
        result.append(dict(building_relation=building_relation, class_relation=class_relation,
            total_pairs=total_pairs, image_pairs=len(group), images=len({r[k] for r in group for k in ('left_image','right_image')}),
            buildings=len({r[k] for r in group for k in ('left_building','right_building')}),
            building_blocks=len(blocks), pair_equal_mean=mean(distances), pair_median=median(distances),
            block_equal_mean=mean(mean(v) for v in blocks.values()), shared_replicates_min=min(shared),
            shared_replicates_max=max(shared), pair_replicate_records=sum(shared)))
    return result


def replay_pairs(inputs, classes):
    by_context=defaultdict(lambda:defaultdict(dict));metadata={}
    for r in inputs:
        context,rep,k=r['context_key'],int(r['replicate']),int(r['k'])
        if k in by_context[context][rep]:
            raise ValueError('duplicate context/replicate/k')
        by_context[context][rep][k]=float(r['value']);metadata[context]=r
    pairs=[]
    for left,right in combinations(sorted(by_context),2):
        a,b=by_context[left],by_context[right];shared=sorted(set(a)&set(b))
        x,y=metadata[left],metadata[right];lc,rc=classes.get(x['image_id']),classes.get(y['image_id'])
        value=''
        if shared:
            nodes=set(a[shared[0]])
            assert all(set(a[r])==set(b[r])==nodes for r in shared)
            value=mean(abs(mean(a[r][k] for r in shared)-mean(b[r][k] for r in shared)) for k in sorted(nodes))
        pairs.append(dict(left_context=left,right_context=right,left_image=x['image_id'],right_image=y['image_id'],
            left_building=x['building_id'],right_building=y['building_id'],left_class_code='' if lc is None else lc,
            right_class_code='' if rc is None else rc,class_relation='unknown' if lc is None or rc is None else 'same' if lc==rc else 'different',
            building_relation='same' if x['building_id']==y['building_id'] else 'different',shared_replicates=len(shared),
            shared_replicates_json=json.dumps(shared),status='comparable' if shared else 'no_shared_replicates',curve_distance=value))
    return pairs


def audit():
    images = rows(IMAGES)
    assert len(images) == len({r['image_id'] for r in images}) == 380
    classes, indexes, inventory = load_classes()
    mapped = []
    for r in images:
        image_id = r['image_id']
        for split in ('train', 'test'):
            assert indexes[split,'pano'].get(image_id) == indexes[split,'single'].get(image_id)
        mapped.append(dict(image_id=image_id, building_id=r['building_id'], population_role=r['population_role'],
            class_code=classes.get(image_id,''), class_name='', room_instance_id='',
            old_class_values_json=r['region_class_values_json'], old_room_instance_id=r['room_instance_id']))
        assert not r['room_instance_id']
    old_records = rows(ROOT/'analysis_results/annotation_research_decision_audit_20260905_v1/inventory/room_region_mapping_records.csv')
    old_ids = {r['image_id'] for r in old_records}
    assert len(old_ids) == len(old_records)
    for r in old_records:
        assert classes[r['image_id']] == int(r['region_class'])
    coverage = []
    for role in sorted({r['population_role'] for r in images}):
        group = [r for r in mapped if r['population_role'] == role]
        coverage.append(dict(population_role=role,total_images=len(group),old_mapped=sum(r['image_id'] in old_ids for r in group),
            mapped=sum(r['class_code']!='' for r in group),missing=sum(r['class_code']=='' for r in group),instance_mapped=0))
    counts=[]
    for code in list(range(1,13))+['']:
        group=[r for r in mapped if r['class_code']==code]
        counts.append(dict(class_code=code if code!='' else 'unknown',historical_images=sum(r['population_role']=='historical_annotated' for r in group),
            candidate_images=sum(r['population_role']=='candidate_without_historical_annotation' for r in group),
            buildings=len({r['building_id'] for r in group})))
    core=OUT/'core'
    incoming=rows(core/'images_380.csv')
    assert {r['image_id'] for r in incoming}=={r['image_id'] for r in mapped}
    for r in incoming:
        assert r['class_code']==str(classes.get(r['image_id'],''))
        assert not any(r[k] for k in ['class_name','room_instance_id','position_x','position_y','position_z'])
    masks={}
    for r in iter_rows(OLD.parent/'core/fixed_window_membership.csv.gz'):
        if (r['stage'],r['block_index'],r['raw_condition'],r['scheme'],r['config'],r['max_k'],r['path'],r['measure']) == ('P1','0','manual','two_thirds','ospa30_t6','15','full_history_fixed','distribution_tv'):
            masks[r['context_key']]=set(json.loads(r['valid_split_ids_json']))
    original_values={}
    for r in iter_rows(ROOT/'analysis_results/order_free_cluster_holdout_20260908_v1/fixed_taxonomy_prefixes.csv.gz'):
        if r['context_key'] in masks and r['split_id'] in masks[r['context_key']] and r['config']=='ospa30_t6' and r['k'] in {'3','5','8','10','12','15'}:
            key=r['context_key'],int(r['replicate']),int(r['k'])
            assert key not in original_values
            original_values[key]=float(r['distribution_tv'])
    inputs=rows(core/'pair_curve_inputs.csv.gz');incoming_values={(r['context_key'],int(r['replicate']),int(r['k'])):float(r['value']) for r in inputs}
    assert len(incoming_values)==len(inputs) and set(incoming_values)==set(original_values)
    input_error=max(abs(incoming_values[k]-original_values[k]) for k in incoming_values)
    assert input_error<1e-10
    pairs=replay_pairs(inputs,classes)
    check={(r['left_context'],r['right_context']):r for r in rows(core/'class_pair_curves.csv')}
    assert len(check)==len(pairs)
    pair_error=0.
    for r in pairs:
        got=check[r['left_context'],r['right_context']]
        for k in ['left_image','right_image','left_building','right_building','status']:assert got[k]==r[k]
        assert int(got['shared_replicates'])==r['shared_replicates']
        assert json.loads(got['shared_replicates_json'])==json.loads(r['shared_replicates_json'])
        assert got['class_relation']=={'same':'same_numeric_class','different':'different_numeric_class','unknown':'unknown'}[r['class_relation']]
        assert got['building_relation']==r['building_relation']+'_building'
        if r['status']=='comparable':pair_error=max(pair_error,abs(float(got['curve_distance'])-r['curve_distance']))
        else:assert got['curve_distance']==''
    assert pair_error<1e-10
    summaries=pair_summary(pairs)
    summary_error=0.
    for r in summaries:
        match=next(x for x in rows(core/'class_pair_summary.csv') if x['class_relation']=={'same':'same_numeric_class','different':'different_numeric_class','unknown':'unknown'}[r['class_relation']] and x['building_relation']==r['building_relation']+'_building')
        for a,b in [('total_pairs','total_pairs'),('image_pairs','valid_pairs'),('images','images'),('buildings','buildings'),('building_blocks','building_units'),('shared_replicates_min','minimum_shared_replicates'),('shared_replicates_max','maximum_shared_replicates'),('pair_replicate_records','total_pair_replicate_occurrences')]:assert r[a]==int(match[b])
        for a,b in [('pair_equal_mean','pair_equal_mean'),('block_equal_mean','building_unit_equal_mean')]:summary_error=max(summary_error,abs(r[a]-float(match[b])))
    assert summary_error<1e-10
    curve=[]
    for r in rows(OLD/'context_curves.csv.gz'):
        if (r['stage'],r['raw_condition'],r['scheme'],r['config'],r['max_k'],r['path'],r['measure']) == ('P1','manual','two_thirds','ospa30_t6','15','full_history_fixed','distribution_tv'):
            curve.append({**r,'class_code':classes.get(r['image_id'],'unknown')})
    review=OUT/'review'; review.mkdir(parents=True,exist_ok=True)
    for name,data in [('independent_images_380.csv',mapped),('mapping_coverage.csv',coverage),('class_counts.csv',counts),
        ('independent_class_pairs.csv',pairs),('class_pair_summary.csv',summaries),('p1_class_curves.csv',curve)]:
        write_csv(review/name,data)
    result=dict(status='passed',images=380,old_mapped=len(old_ids),mapped=sum(r['class_code']!='' for r in mapped),
        buildings=len({r['building_id'] for r in mapped}),new_instance_mappings=0,pano_single_conflicts=0,
        sources=inventory,pair_rows=len(pairs),valid_pairs=sum(r['status']=='comparable' for r in pairs),curve_rows=len(curve),curve_images=len({r['image_id'] for r in curve}),
        source_input_rows=len(inputs),source_input_max_error=input_error,pair_max_error=pair_error,summary_max_error=summary_error,
        primary_filter='P1/manual/block0/two_thirds/ospa30_t6/full_history_fixed/distribution_tv/max_k15',
        source_geometry_recomputed=False,source_curve_values_changed=False,room_class_is_instance=False,
        pair_weighting='image-pair equal and building/building-pair block equal reported separately; not matched effects',
        formal_protocol_changed=False)
    (review/'INDEPENDENT_AUDIT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return result


def figures():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.sans-serif':['Microsoft YaHei','SimHei','DejaVu Sans'],'axes.unicode_minus':False,'font.size':10})
    dest=OUT/'figures';dest.mkdir(exist_ok=True)
    records=rows(OUT/'review/class_counts.csv')
    fig,ax=plt.subplots(figsize=(9,5.5)); xs=list(range(len(records)))
    ax.bar([x-.18 for x in xs],[int(r['historical_images']) for r in records],width=.36,color='black',label='历史图')
    ax.bar([x+.18 for x in xs],[int(r['candidate_images']) for r in records],width=.36,color='.65',label='候选图')
    ax.set_xticks(xs,[r['class_code'] if r['class_code']!='unknown' else '未知' for r in records]);ax.set_xlabel('官方分类任务数值类别（名称对应尚未核实）');ax.set_ylabel('图像数');ax.legend(frameon=False)
    ax.set_title('类别连接覆盖：178/214历史图，119/166候选图');fig.tight_layout();fig.savefig(dest/'class_coverage.png',dpi=180);plt.close(fig)
    records=rows(OUT/'review/class_pair_summary.csv')
    labels=[('同楼' if r['building_relation']=='same' else '异楼')+'／'+{'same':'同类别','different':'不同类别','unknown':'类别未知'}[r['class_relation']]+f"（{r['image_pairs']}图对）" for r in records]
    fig,ax=plt.subplots(figsize=(9,5));ys=list(range(len(records)))
    ax.scatter([float(r['pair_equal_mean']) for r in records],ys,color='black',marker='o',label='图对等权')
    ax.scatter([float(r['block_equal_mean']) for r in records],ys,color='black',marker='x',label='楼／楼对等权')
    ax.set_yticks(ys,labels);ax.invert_yaxis();ax.set_xlim(left=0);ax.set_xlabel('TV曲线距离均值（水平与形状共同变化）');ax.set_title('P1 Manual：3—15人，30°截断／6°分簇，2/3历史组');ax.legend(frameon=False)
    fig.tight_layout();fig.savefig(dest/'class_pair_comparison.png',dpi=180);plt.close(fig)
    records=rows(OUT/'review/p1_class_curves.csv');codes=sorted({r['class_code'] for r in records},key=lambda x:99 if x=='unknown' else int(x))
    fig,axes=plt.subplots(math.ceil(len(codes)/2),2,figsize=(11,3.4*math.ceil(len(codes)/2)),squeeze=False)
    for ax,code in zip(axes.flat,codes):
        group=[r for r in records if r['class_code']==code];by_image=defaultdict(list);by_k=defaultdict(list)
        for r in group:by_image[r['image_id']].append(r);by_k[int(r['k'])].append(float(r['mean']))
        for g in by_image.values():
            g=sorted(g,key=lambda r:int(r['k']));ax.plot([int(r['k']) for r in g],[float(r['mean']) for r in g],color='.7',linewidth=.8)
        ax.plot(sorted(by_k),[mean(by_k[k]) for k in sorted(by_k)],color='black',linewidth=2)
        ax.set_title(f"类别{code}：{len(by_image)}图");ax.set_ylim(0,1);ax.set_xlabel('历史人数 k');ax.set_ylabel('验证TV');ax.set_xticks([3,5,8,10,12,15])
    for ax in list(axes.flat)[len(codes):]:ax.axis('off')
    fig.suptitle('固定历史分类下的逐图曲线；灰线为图，黑线为类别内图等权均值',y=1.002);fig.tight_layout();fig.savefig(dest/'p1_class_curves.png',dpi=180,bbox_inches='tight');plt.close(fig)


if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('--figures',action='store_true');args=p.parse_args()
    result=audit()
    if args.figures:figures()
    print(json.dumps(result,ensure_ascii=False,indent=2))
