"""9月新导出探索复算：保留全部实收审计，分配外可纳入，未决独立性做敏感性。"""
import collections
import copy
import itertools
import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

from tools.thesis_main.analysis.clustering_release import pipeline, local_points
from tools.thesis_main.analysis.paired_split_research import study
from tools.thesis_main.analysis.clustering_numeric_research.common import next_uncovered, clean
from tools.thesis_main.analysis.audit_collection_plan_20260921 import blocks

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'analysis_results/new_manual_analysis_20260921'
HIST=ROOT/'analysis_results/clustering_release_local_20260920/current/inputs'
SOURCES=['export_label/新增中文20图/project-93-at-2026-09-21-04-34-9e224397.json',
         'export_label/新增英文30+20图/project-94-at-2026-09-20-13-45-d09d9d53.json',
         'export_label/新增英文30+20图/project-95-at-2026-09-20-13-44-3fe72103.json']


def read(p):
    return pipeline.read(ROOT/p)


def dump(name,value):
    (OUT/name).write_text(json.dumps(clean(value),ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf8')


def intake(history,registry,sources=None):
    """历史首次作答保留；重复新作答未决不选优，父关联仅进条件敏感性池。"""
    images={i['image_id']:i for i in registry['images']}
    history_exposure={(r['image_id'],r['worker_id']) for r in history}
    for r in read('import_json/scene_stability_stage1_20260913_v2/historical_exposure.json'):
        history_exposure.add((r['image_id'],f"W{r['worker_id']:03d}"))
    required={(r['image_id'],f"W{r['worker_id']:03d}") for r in read('import_json/scene_stability_stage1_20260913_v2/required_assignments.json')}
    receipts=[];new=[];raw_annotations={}
    for source in SOURCES if sources is None else sources:
        for task in read(source):
            meta=task['data'];iid=meta['base_task_id']
            assert iid in images and meta['condition']=='manual' and meta['annotation_form_version']=='manual_scope_only_v1'
            from urllib.parse import unquote,urlparse
            assert Path(unquote(urlparse(meta['image']).path)).stem==iid
            for ann in task['annotations']:
                raw_annotations[ann['id']]=ann
                w=f"W{int(ann['completed_by']):03d}";p=pipeline.raw_points(ann)
                assert ann['task']==task['id'] and int(ann['project'])==int(task['project'])
                flags=[]
                if ann.get('was_cancelled') or ann.get('ground_truth'):flags.append('cancelled_or_gold')
                if not p:flags.append('empty_points')
                if p and not all(0<=x<=1024 and 0<=y<512 for x,y in p):flags.append('invalid_coordinates')
                if len(p)%2:flags.append('odd_unconfirmed')
                if (iid,w) in history_exposure:flags.append('prior_exposure_not_new_independent_vote')
                if ann.get('parent_annotation'):flags.append('parent_annotation_independence_pending')
                if w in {'W019','W026'}:flags.append('existing_worker_exclusion')
                cid=f"new_{task['project']}_{task['id']}_{ann['id']}_{w}"
                receipt=dict(id=cid,source=source,project=task['project'],task=task['id'],annotation=ann['id'],
                    worker=w,image_id=iid,code=f"{images[iid]['building']}-{images[iid]['number']:02d}",
                    point_count=len(p),parent_annotation=ann.get('parent_annotation'),flags=flags,
                    assignment='required' if (iid,w) in required else ('optional' if meta['project_key']=='en_optional' else 'outside_required'),
                    created_at=ann['created_at'],updated_at=ann['updated_at'])
                receipts.append(receipt)
                new.append(dict(canonical_annotation_id=cid,worker_id=w,image_id=iid,building_id=images[iid]['building'],
                    raw_condition='manual',assistance_exposure='none',stage='scene_stability_stage1',block_index=0,
                    raw_points_1024x512=p,effective_points_1024x512=p,raw_point_count=len(p),effective_point_count=len(p),
                    calculation_included=not flags,processing_status='latest_export_unmodified',imputed_point=False,
                    active_time_status='unfrozen',active_time_seconds=None,annotation_form_version='manual_scope_only_v1',
                    difficulty_status='not_collected',model_issue_status='not_collected',scope_original=[r for r in ann['result'] if r['type']=='choices'],
                    provenance=receipt))
    counts=collections.Counter((r['image_id'],r['worker']) for r in receipts if r['point_count'])
    for r,n in zip(receipts,new):
        if r['parent_annotation']:
            parent=raw_annotations.get(r['parent_annotation'])
            r['parent_present']=parent is not None
            r['points_identical_to_parent']=pipeline.raw_points(parent)==n['raw_points_1024x512'] if parent else None
        if counts[r['image_id'],r['worker']]>1:r['flags'].append('multiple_submissions_version_pending')
        n['calculation_included']=not r['flags']
        r['conditional_include']=not [x for x in r['flags'] if x!='parent_annotation_independence_pending']
        r['strict_include']=not r['flags']
    assert len(receipts)==len(new)==len({r['id'] for r in receipts})
    return new,receipts


def prepare(history,new,registry):
    rows=copy.deepcopy(history)+copy.deepcopy(new)
    # 用同一计算视图构建距离；独立性资格在分池时处理，绝不静默删记录。
    for row in rows[len(history):]:row['calculation_included']=row['provenance']['conditional_include']
    images={i['image_id']:i for i in registry['images']}
    audit=pd.DataFrame([dict(id=r['canonical_annotation_id'],code=f"{images[r['image_id']]['building']}-{images[r['image_id']]['number']:02d}") for r in rows]).set_index('id')
    accepted=study.accepted_map(HIST,rows)
    rec,elig=study.prepare(rows,audit,accepted,'min_horizontal')
    return rows,rec,elig


def statistics(d,ids,threshold,kind):
    labels,representatives=local_points.partition(d,ids,threshold,kind)
    counts=collections.Counter(labels);tri=np.triu_indices(len(ids),1)
    return dict(N=len(ids),groups=len(counts),singletons=sum(n==1 for n in counts.values()),largest_share=max(counts.values())/len(ids),
        near_but_split=int(((d[tri]<=threshold)&(labels[tri[0]]!=labels[tri[1]])).sum()),
        far_but_grouped=int(((d[tri]>threshold)&(labels[tri[0]]==labels[tri[1]])).sum())),labels,representatives


def main():
    OUT.mkdir(exist_ok=True)
    history=pipeline.rows_at(HIST/'responses.jsonl.gz')
    registry=read('analysis_results/scene_image_exploration_20260910_v1/same_room_selection_registry_v2_20260912.json')
    new,receipts=intake(history,registry);rows,rec,elig=prepare(history,new,registry)
    dump('intake.json',receipts);pipeline.write_rows(OUT/'responses.jsonl.gz',rows)
    elig.to_json(OUT/'eligibility.json',orient='records',force_ascii=False,indent=2)
    review_path=Path('C:/Users/ASUS/Downloads/八组采集采用_我的审核.json')
    review=pipeline.read(review_path)
    expected=read('analysis_results/collection_review_20260921/审核输入.json')
    assert review['binding']==expected['binding'] and set(review['decisions'])==set(g['id'] for g in expected['groups'])
    shutil.copyfile(review_path,OUT/'用户_八组采集采用_原始.json')
    grouped=collections.defaultdict(list)
    for cid,r in rec.items():
        if r['links'] is not None:grouped[r['row']['image_id'],r['row']['raw_condition']].append(cid)
    historical_ids={r['canonical_annotation_id'] for r in history}
    strict_ids={r['id'] for r in receipts if r['strict_include']}
    variants={'historical':historical_ids,'strict':historical_ids|strict_ids,'conditional':set(rec)}
    results=[];changes=[];membership=[];curves=[];cache={};pair_alerts=[]
    for (iid,condition),ids in sorted(grouped.items()):
        ids.sort();n=len(ids);d=np.full((n,n),1e6);s=d.copy();np.fill_diagonal(d,0);np.fill_diagonal(s,0)
        for i,j in itertools.combinations(range(n),2):
            a,b=rec[ids[i]],rec[ids[j]]
            if len(a['p'])!=len(b['p']):continue
            ep=local_points.endpoint_rows(a,b)
            d[i,j]=d[j,i]=max(e['image_px'] for e in ep);s[i,j]=s[j,i]=max(e['sphere_deg'] for e in ep)
            if (ids[i] not in historical_ids or ids[j] not in historical_ids) and d[i,j]>25.6:
                L,R=a['links'],b['links'];cost=np.maximum(local_points.pixel_distance(a['p'][L[:,0]],b['p'][R[:,0]]),local_points.pixel_distance(a['p'][L[:,1]],b['p'][R[:,1]]))
                free,mapping=study.bottleneck(cost)
                if free<=25.6:pair_alerts.append(dict(image_id=iid,a=ids[i],b=ids[j],fixed_px=d[i,j],free_px=free,mapping_b_1based=(mapping+1).tolist(),status='仅预警，不自动改对应'))
        for pool,eligible in variants.items():
            ix=[i for i,cid in enumerate(ids) if cid in eligible]
            if not ix:continue
            subids=[ids[i] for i in ix];dd=d[np.ix_(ix,ix)];ss=s[np.ix_(ix,ix)]
            base=dict(pool=pool,image_id=iid,condition=condition,code=rec[subids[0]]['audit']['code'],building=rec[subids[0]]['row']['building_id'])
            cache[pool,iid,condition]=dict(ids=subids,image=dd,sphere=ss,base=base)
            for metric,mat in [('image',dd),('sphere',ss)]:
                for cut in [6,9,12]:
                    t=cut*1024/360 if metric=='image' else cut
                    for kind in ['complete','representative']:
                        st,labels,reps=statistics(mat,subids,t,kind)
                        results.append(dict(**base,metric=metric,nominal_cut=cut,partition=kind,**st))
                        membership.extend(dict(**base,metric=metric,nominal_cut=cut,partition=kind,id=cid,group=int(label),representative=cid in reps) for cid,label in zip(subids,labels))
                        if pool!='historical':
                            oldix=[i for i,cid in enumerate(subids) if cid in historical_ids]
                            if oldix and len(oldix)<len(subids):
                                oldmat=mat[np.ix_(oldix,oldix)];oldids=[subids[i] for i in oldix]
                                oldstats,oldlabels,_=statistics(oldmat,oldids,t,kind)
                                tri=np.triu_indices(len(oldix),1);restricted=labels[oldix]
                                changes.append(dict(**base,metric=metric,nominal_cut=cut,partition=kind,old_N=len(oldix),new_N=len(subids)-len(oldix),old_groups=oldstats['groups'],after_groups=st['groups'],
                                    old_relations_changed=int(((oldlabels[:,None]==oldlabels)[tri]!=(restricted[:,None]==restricted)[tri]).sum()),old_pairs=len(tri[0]),
                                    new_without_old_neighbor=sum(bool(np.all(mat[i,oldix]>t)) for i in range(len(subids)) if i not in oldix)))
            if condition in ['manual','oos']:
                for metric,mat in [('image',dd),('sphere',ss)]:
                    for cut in [6,9,12]:
                        t=cut*1024/360 if metric=='image' else cut
                        for k in range(1,len(subids)):
                            curves.append(dict(**base,metric=metric,nominal_cut=cut,N=len(subids),k=k,next_uncovered=next_uncovered(mat,k,t),tail=len(subids)-k))
    print('距离与分簇完成',flush=True)
    dump('partitions.json',results);dump('memberships.json',membership);dump('old_new_changes.json',changes);dump('coverage_curves.json',curves);dump('correspondence_alerts.json',pair_alerts)
    # 保留全量距离，未来人工核验不依赖下载目录最新文件。
    dump('distances.json',[dict(**v['base'],ids=v['ids'],image=v['image'],sphere=v['sphere']) for v in cache.values()])
    prediction=transfer(curves,cache,registry,rec)
    dump('transfer.json',prediction)
    # 同一图、同一固定人员池的嵌套加入，逐次重算分组；不是全池标签倒推。
    replay=[];rng=np.random.default_rng(20260921)
    for (pool,iid,condition),v in cache.items():
        if pool!='strict' or condition not in ['manual','oos'] or len(v['ids'])<8:continue
        if not any(cid not in historical_ids for cid in v['ids']):continue
        orders=[rng.permutation(len(v['ids'])) for _ in range(100)]
        accum=collections.defaultdict(list)
        for order in orders:
            for k in range(2,len(order)+1):
                ix=order[:k];ids2=[v['ids'][i] for i in ix];mat=v['image'][np.ix_(ix,ix)]
                for kind in ['complete','representative']:
                    z,lab,_=statistics(mat,ids2,25.6,kind);accum[k,kind].append([z['groups'],z['largest_share']])
        for (k,kind),values in accum.items():replay.append(dict(image_id=iid,code=v['base']['code'],N=len(v['ids']),k=k,partition=kind,orders=100,groups_mean=np.mean(values,axis=0)[0],largest_share_mean=np.mean(values,axis=0)[1]))
    dump('nested_replay.json',replay)
    summary=dict(raw_history=len(history),raw_new=len(new),sources=SOURCES,
        flags=collections.Counter(f for r in receipts for f in r['flags']),
        strict_new=sum(r['strict_include'] for r in receipts),conditional_new=sum(r['conditional_include'] for r in receipts),
        assignments=collections.Counter(r['assignment'] for r in receipts),
        strict_assignment_counts=collections.Counter(r['assignment'] for r in receipts if r['strict_include']),
        binding_eligible={pool:sum(len(v['ids']) for (p,i,c),v in cache.items() if p==pool) for pool in variants},
        units={pool:sum(p==pool for p,i,c in cache) for pool in variants},
        new_pairing_alerts=len(pair_alerts),historical_point_payloads_preserved=True,
        parent_exact_point_copies=sum(r.get('points_identical_to_parent') is True for r in receipts),
        new_time_status='未冻结，不以lead_time替代',methods='原有min_horizontal点对＋按固定起点环序逐端点最大距离；6/9/12°及等值像素探针；完整链接与真实代表半径。不同有效点数硬分开。无IoU。',
        review_status='7组35图采用；G180四图条件暂缓；子图未填，无冲突。用途空白不补成无用途。',
        prediction_scope='探索性同图留出／有限人员池覆盖预测，不是前瞻冻结停止人数验证。借用点补全作答不进入transfer。',
        source_versions=[dict(path=p,size=(ROOT/p).stat().st_size,sha256=pipeline.sha(ROOT/p)) for p in SOURCES])
    dump('SUMMARY.json',summary);print(json.dumps(clean(summary),ensure_ascii=False,indent=2),flush=True)


def transfer(curves,cache,registry,rec):
    """无目标响应输入：源图有限池未覆盖概率预测目标；不挑成功的目标。"""
    candidates=[c for c in registry['candidates'] if c['physical_same_supported']]
    families=blocks(candidates);adj=collections.defaultdict(set)
    for c in candidates:
        for a,b in itertools.combinations(c['image_ids'],2):adj[a].add(b);adj[b].add(a)
    answer=[]
    for pool in ['strict','conditional']:
        for metric in ['image','sphere']:
            for cut in [6,9,12]:
                for k in [5,8]:
                    y={}
                    for (p,i,c),v in cache.items():
                        if p!=pool or c not in ['manual','oos']:continue
                        ix=[j for j,cid in enumerate(v['ids']) if not rec[cid]['row']['imputed_point']]
                        if len(ix)<k+5:continue
                        assert i not in y, '同图Manual/OOS双单元必须显式处理'
                        y[i]=next_uncovered(v[metric][np.ix_(ix,ix)],k,cut*1024/360 if metric=='image' else cut)
                    for target,truth in y.items():
                        same=[i for i in adj[target] if i in y]
                        if not same:continue
                        family=families[target];building=target.split('_')[0]
                        outbuilding=[i for i in y if i.split('_')[0]!=building]
                        otherroom=[i for i in y if i.split('_')[0]==building and families.get(i)!=family]
                        if not outbuilding:continue
                        answer.append(dict(pool=pool,metric=metric,cut=cut,k=k,target=target,building=building,family=family,
                            target_value=truth,same_room_prediction=float(np.mean([y[i] for i in same])),
                            external_baseline=float(np.mean([y[i] for i in outbuilding])),
                            same_building_other_room=float(np.mean([y[i] for i in otherroom])) if otherroom else None,
                            source_images=sorted(same),source_count=len(same),baseline_count=len(outbuilding),
                            new_target=any(rec[cid]['row']['stage']=='scene_stability_stage1' for (p,i,c),v in cache.items() if p==pool and i==target for cid in v['ids'])))
    return answer


if __name__=='__main__':main()
