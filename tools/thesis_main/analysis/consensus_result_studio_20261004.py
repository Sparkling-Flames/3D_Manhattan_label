"""把既有全员融合候选接入原全景／3D工作台，仅生成展示工件。"""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path

from tools.label_studio.panorama_studio.geometry import analyze
from .lee_tile_stage1_20261002 import ROOT, write_json

SOURCE = ROOT/'analysis_results/lee_consensus_demos_20261003/demos.json'
OUT = ROOT/'analysis_results/consensus_result_studio_20261004'
STUDIO = ROOT/'tools/label_studio/panorama_studio'
ADAPTER = ROOT/'tools/thesis_main/analysis/consensus_result_studio_20261004'


def variant_for_cluster(cluster, workers, point_cache):
    ids=cluster['members']
    if (len(set(ids))!=len(ids) or len(ids)!=cluster['support']
            or any(i not in workers for i in ids) or cluster['representative'] not in ids):
        raise ValueError('cluster_member_identity_mismatch')
    if [workers[i]['worker'] for i in ids]!=cluster['workers']:
        raise ValueError('cluster_worker_identity_mismatch')
    candidate=cluster['candidate']
    representative=workers[cluster['representative']]
    source=dict(role='consensus_candidate', method='point_pair_median_candidate',
        pointset_version='point_pattern_demo_20261003:full_pool:5deg',
        cluster=copy.deepcopy(cluster),candidate_erp=copy.deepcopy(point_cache.get(candidate['erp_key'])),
        representative={k:copy.deepcopy(representative[k]) for k in ('id','worker','erp')},
        members=[dict(id=i,worker=workers[i]['worker']) for i in ids],
        note='既有簇内完整上下候选；既定候选环尚未经人工确认；展示不增加GT质量验证。')
    variant=dict(name=f"{cluster['id']} · {cluster['support']}人 · 完整上下候选",source=source)
    if candidate['status']=='unavailable':
        variant['error']=candidate['reason']
        return variant
    points=candidate['points']
    if points is None or len(points)<6 or len(points)%2:
        raise ValueError('invalid_candidate_endpoint_count')
    payload=dict(width=1024,height=512,coordinate_mode='pixels',coordinate_convention='continuous',
        ordered_pairs=[dict(source_pair_id=f"candidate:{cluster['id']}:pair:{i//2+1}",
            top=dict(x=points[i][0],y=points[i][1]),bottom=dict(x=points[i+1][0],y=points[i+1][1]))
            for i in range(0,len(points),2)])
    geometry=analyze(payload,compute_fit=False,coordinate_convention='continuous')
    restored=[p for pair in geometry['pairs'] for p in (pair['top'],pair['bottom'])]
    if restored!=points:
        raise ValueError('candidate_points_changed_during_display_reconstruction')
    variant['geometry']=geometry
    return variant


def relative(path, out):
    return os.path.relpath(path,out).replace('\\','/')


def build(source=SOURCE, out=OUT):
    source,out=Path(source).resolve(),Path(out).resolve()
    if out.exists():
        raise ValueError('use_new_output_directory')
    demos=json.loads(source.read_text(encoding='utf-8'))
    cases=[]; images={}; audit=[]
    for index,demo in enumerate(demos):
        end=demo['steps'][-1]
        if end['k']!=demo['n'] or len(end['members'])!=demo['n']:
            raise ValueError('last_step_not_full_pool')
        matches=[v for v in end['pattern_views'] if v['threshold_deg']==5.]
        if len(matches)!=1: raise ValueError('explicit_5_degree_view_required')
        view=matches[0]
        if sorted(i for c in view['clusters'] for i in c['members'])!=sorted(end['members']):
            raise ValueError('clusters_do_not_partition_current_members')
        workers={w['id']:w for w in demo['workers']}
        if len(workers)!=demo['n']: raise ValueError('worker_record_count_mismatch')
        variants=[variant_for_cluster(c,workers,demo['point_projection_cache']) for c in view['clusters']]
        photo=(source.parent/demo['photo']).resolve()
        if not photo.is_file(): raise ValueError('local_panorama_missing:'+str(photo))
        photo_url=relative(photo,out)
        images[index]=dict(original=photo_url,texture=photo_url)
        kept={key:copy.deepcopy(demo[key]) for key in
              ('image','n','difficulty','building','scene','workers','references','erp_references',
               'single_mean','single_best','full_gain')}
        kept['photo']=photo_url
        kept['step']={key:copy.deepcopy(value) for key,value in end.items() if key!='tiles'}
        needed={end['all_erp_region_key'],*[c['erp_region_key'] for c in view['clusters']]}
        kept['erp_region_cache']={key:copy.deepcopy(demo['erp_region_cache'][key]) for key in sorted(needed)}
        case=dict(image_id=photo.stem,title=demo['image'],category='融合结果 · 逐标法簇',
                  image_source=photo_url,variants=variants,demo=kept)
        cases.append(case)
        audit.append(dict(image=demo['image'],image_id=photo.stem,n=demo['n'],variants=[
            dict(name=v['name'],cluster_id=v['source']['cluster']['id'],
                members=v['source']['members'],candidate_points=v['source']['cluster']['candidate']['points'],
                geometry=v.get('geometry'),error=v.get('error')) for v in variants]))
    counts=dict(cases=len(cases),variants=sum(len(c['variants']) for c in cases))
    counts.update(fit_not_requested=sum('geometry' in v for c in cases for v in c['variants']),
                  input_failed=sum('geometry' not in v for c in cases for v in c['variants']))
    payload=dict(schema_version='consensus_result_studio_v1',cases=cases,counts=counts,
        annotation_writeback=False,source=relative(source,out),
        selection='既有四个目的性demo的全员最后一步；全部24个簇候选保留，不按GT择优。')
    out.mkdir(parents=True)
    encoded=json.dumps(payload,ensure_ascii=False,allow_nan=False,separators=(',',':')).replace('</','<\\/')
    (out/'data.js').write_text('window.STUDIO_IMAGES='+json.dumps(images,separators=(',',':'))+';\nwindow.STUDIO_DATA='+encoded+';\n',encoding='utf-8',newline='\n')
    html=(STUDIO/'index.html').read_text(encoding='utf-8')
    for name in ('studio.css','studio.js'):
        html=html.replace('"'+name+'"','"'+relative(STUDIO/name,out)+'"')
    for name in ('three.min.js','OrbitControls.js'):
        html=html.replace('"'+name+'"','"'+relative(STUDIO.parent/name,out)+'"')
    html=html.replace('</head>',f'  <link rel="stylesheet" href="{relative(ADAPTER.with_suffix(".css"),out)}">\n'
        f'  <script defer src="{relative(ADAPTER.with_suffix(".js"),out)}"></script>\n</head>')
    html=html.replace('<title>空间标本 · 全景布局审查</title>','<title>融合结果工作台 · 全景与3D</title>')
    (out/'index.html').write_text(html,encoding='utf-8',newline='\n')
    write_json(out/'geometry_audit.json',dict(schema='consensus_result_studio_geometry_v1',counts=counts,
        source=relative(source,out),compute_fit=False,coordinate_convention='continuous',
        point_identity_check='all candidate endpoint arrays equal stored points exactly',cases=audit))
    write_json(out/'field_contract.json',dict(schema='consensus_result_studio_v1',
        input='Existing demos.json final full-pool step only; no new clustering, fusion, votes or GT scoring.',
        cases='image_id,title,category,variants,demo; demo keeps workers, references, last step, selected ERP cache.',
        variants='name,source,geometry or explicit error; each full-pool whole-annotation cluster is retained.',
        source='role,method,pointset_version,cluster,candidate_erp,representative{id,worker,erp},members[{id,worker}],note.',
        geometry='panorama_studio_v1 from analyze(...compute_fit=False,continuous); source candidate points/order unchanged.',
        image_urls='Repository-relative local PNG URLs for original and texture; no image copying or resampling.',
        identity='candidate:<cluster_id>:pair:<index> is a new candidate point identity, never an original worker point ID; provenance in source.cluster.candidate.source_pair_maps.',
        scope='Full-pool result display only. Pattern IDs local to each image/full-pool input. No natural-mode claim or quality improvement validation.',
        representations='Point candidates have complete sparse top/bottom pairs. ERP is dense top/bottom in applicable domain. Lee-BEV only has ground boundary.',
        readonly='No annotation writeback, no Manhattan fitting, no GT-assisted selection; raw Studio reconstruction uses paired-floor depth proxy for top.'))
    text=f'''# 融合结果工作台：全景与3D

推荐在仓库根目录启动本地HTTP服务，再打开[融合结果工作台](http://127.0.0.1:8879/analysis_results/consensus_result_studio_20261004/index.html)。本页以融合后上下角点和全景轮廓为主视图，复用已有空间标本工作台的3D墙体、纹理和线框。

- 当前只接入既有四例的全员结果，共{counts['variants']}个标法簇候选；所有簇保留，不按GT或簇大小筛成唯一结果。
- 完整点候选沿用已有上下坐标与环序。3D只做`analyze(..., compute_fit=False, coordinate_convention='continuous')`显示重建，没有重新分簇、融合、评分或Manhattan拟合。
- 3D相机高度为相对单位1。上点深度沿用对应底点水平距离；墙顶封口是显示假设，不能解释成真实天花板深度或质量验证。
- ERP多数轮廓和Lee-BEV底边保留为方法对照；前者是稠密上下轮廓，后者只有底边，不冒充完整稀疏角点输出。
- 图片和共享渲染器沿仓库相对路径加载，没有复制或改写原图。保留完整仓库路径并通过本地HTTP服务访问；`file://`加载纹理可能受到浏览器跨域限制，单独复制此文件夹不足以携带依赖。
- 原始输入、既有指标与旧demo不改写。[旧详情](../lee_consensus_demos_20261003/index.html)保留人数和分组追溯。

字段见[field_contract.json](field_contract.json)，24份候选坐标／几何核对见[geometry_audit.json](geometry_audit.json)。所有成功重建的点数组与既有候选逐值完全相同，拟合状态为`not_requested`；不可用输入保留错误。

本地服务：在仓库根目录运行`python -m http.server 8879 --bind 127.0.0.1`。

复现：`python -B -m tools.thesis_main.analysis.consensus_result_studio_20261004 --out analysis_results/<新的目录>`。已有目录拒绝覆盖。前端适配器位于`tools/thesis_main/analysis/consensus_result_studio_20261004.js`及同名CSS；共享工作台文件保持原样。
'''
    (out/'README.md').write_text(text,encoding='utf-8',newline='\n')
    return payload


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,default=SOURCE)
    parser.add_argument('--out',type=Path,default=OUT)
    args=parser.parse_args()
    print(json.dumps(build(args.input,args.out)['counts']),flush=True)
