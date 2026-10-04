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
GLOBAL_RESULTS = ROOT/'analysis_results/global_pair_consensus_20261004/primary_results.json'
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


def attach_global_results(out, results_path):
    """接入新全员点输出，保留原簇候选为诊断；不重算旧投票或更改点序。"""
    from .lee_consensus_demos_20261003 import project_display_record
    text=(out/'data.js').read_text(encoding='utf-8')
    image_prefix,encoded=text.split('window.STUDIO_DATA=',1)
    payload=json.loads(encoded.rstrip(';\n'))
    study=json.loads(results_path.read_text(encoding='utf-8'))
    lookup={r['image']:r for r in study['images']}
    audit=[]
    for case in payload['cases']:
        case['variants']=[v for v in case['variants'] if v['source']['role']=='consensus_candidate']
        case['pattern_count']=len(case['variants'])
        case['global_point_indices']={}
        result=lookup[case['demo']['image']]
        if result['n']!=case['demo']['n']:
            raise ValueError('global_and_demo_roster_size_mismatch')
        for method,value in result['methods'].items():
            ids=sorted(a['id'] for a in value['assignments'])
            if ids!=sorted(r['id'] for r in case['demo']['workers']):
                raise ValueError('global_and_demo_roster_identity_mismatch')
            candidate=value['candidate'];geometry=None;projection=None;error=None
            if candidate['status']!='unavailable':
                points=candidate['points']
                geometry=analyze(dict(width=1024,height=512,coordinate_mode='pixels',
                    ordered_pairs=[dict(source_pair_id=identity,
                        top=dict(zip(('x','y'),points[2*i])),bottom=dict(zip(('x','y'),points[2*i+1])))
                        for i,identity in enumerate(candidate['feature_ids'])]),
                    compute_fit=False,coordinate_convention='continuous')
                if [p for pair in geometry['pairs'] for p in (pair['top'],pair['bottom'])]!=points:
                    raise ValueError('global_candidate_points_changed')
                projection=project_display_record(candidate)
            else:
                error=candidate['reason']
            source=dict(role='global_point_consensus',method=method,n=value['n'],
                threshold_deg=value['threshold_deg'],minimum_support=value['minimum_support'],
                record_ids=ids,candidate=candidate,candidate_erp=projection,
                ring_diagnostics=value['ring_diagnostics'],method_details=value['method_details'],
                reference_metrics=value['reference_metrics'])
            case['global_point_indices'][method]=len(case['variants'])
            variant=dict(name='全员点对共识 · '+method,source=source)
            if geometry is not None:variant['geometry']=geometry
            else:variant['error']=error
            case['variants'].append(variant)
            audit.append(dict(image=result['image'],method=method,n=value['n'],
                candidate_status=candidate['status'],reason=candidate['reason'],
                displayed=geometry is not None,ring_confirmed=False,
                pair_count=len(candidate['points'])//2 if candidate.get('points') else 0))
    payload['counts']['variants']=sum(len(c['variants']) for c in payload['cases'])
    payload['counts']['global_candidates']=len(audit)
    payload['counts']['fit_not_requested']=sum('geometry' in v for c in payload['cases'] for v in c['variants'])
    payload['counts']['input_failed']=sum('geometry' not in v for c in payload['cases'] for v in c['variants'])
    payload['global_result_source']=relative(results_path,out)
    (out/'data.js').write_text(image_prefix+'window.STUDIO_DATA='+
        json.dumps(payload,ensure_ascii=False,allow_nan=False,separators=(',',':')).replace('</','<\\/')+';\n',
        encoding='utf-8',newline='\n')
    write_json(out/'global_display_audit.json',dict(schema='global_point_display_v1',results=audit,
        full_pool_roster_verified=True,source_coordinates_and_ring_unchanged=True,
        reference='GT neither used for selection nor for ring construction.'))
    contract=json.loads((out/'field_contract.json').read_text(encoding='utf-8'))
    contract.update(
        input='Existing demos.json final full-pool step plus global_pair_consensus_20261004/primary_results.json. The renderer does not recompute fusion or GT scores.',
        cases='image_id,title,category,variants,demo,pattern_count,global_point_indices; demo retains the original full-pool source records and method caches.',
        variants='Auxiliary whole-annotation cluster variants followed by two all-person point variants. global_point_indices maps mv50/mv_strict; unavailable results have explicit error and no geometry.',
        source='Auxiliary sources retain cluster, representative and members. Global sources retain method,n,threshold_deg,minimum_support,record_ids,candidate,candidate_erp,ring_diagnostics,method_details,reference_metrics.',
        identity='Global candidate.feature_ids and source_pair_maps refer to the current point-identity partition, not original person corner IDs. Auxiliary candidate identities remain local to each whole-annotation cluster.',
        counts='variants includes auxiliary and global outputs; global_candidates counts both rules including failures. fit_not_requested counts displayed geometries; legacy input_failed counts variants without display geometry, not excluded people.')
    contract['global_point_extension']='case.pattern_count separates auxiliary patterns from appended full-pool point variants. global_point_indices maps voting rule to one all-person result. Global candidate status, denominator, endpoint votes and ring evidence retained. No unique-true-layout claim.'
    write_json(out/'field_contract.json',contract)
    return payload


def relative(path, out):
    return os.path.relpath(path,out).replace('\\','/')


def build(source=SOURCE, out=OUT, global_results=GLOBAL_RESULTS):
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
    text='''# 全员融合结果工作台：全景与3D

打开[融合结果工作台](http://127.0.0.1:8879/analysis_results/consensus_result_studio_20261004/index.html)。默认展示同一张图全部当前人员形成的一份上下点共识；下方用同一组点和环显示3D。原有整份标法簇改为辅助页签。

- 四个固定案例分别使用22、15、15、8人的全员池，接入两种投票规则的8个输出。默认5°为未校准探索阈值，允许不同点数共同参与；失败显示为不可用，不改用最大簇。
- 保留24个原簇内候选供解释不同标法，与全员点身份分区严格区分。全员ERP上下轮廓、Lee底边并列对照；ERP尚无稀疏角点，Lee尚无top_y。
- Lee页可切换“显示底边表示节点”：使用已有全精度顶点，排除闭环重复点；节点未认证为物理墙角，也没有补造上点。用途与回投验收见[说明](../lee_boundary_usability_20261005/REPORT.md)。
- GT默认关闭，构造与选择结果均不读GT。主图标明人数、点支持、连接不足和完整结构支持，后者不是坐标完全相同，也不要求输出复制某个人。
- 3D复用Panorama Studio，以`continuous`坐标且`compute_fit=False`显示，不拟合成Manhattan、不改候选点或环。相机高度为相对单位1，顶部深度沿用配对底点的水平距离；墙顶是代理重建。可绘制及`ok`都不等于物理真值或环序人工确认。
- 来源坐标、资格、人工确认环和旧Lee结果不改写。图片与共享渲染器沿仓库相对路径引用，没有复制原图；单独复制该目录不足以携带依赖。

整体证据见[137图基础报告](../global_pair_consensus_20261004/REPORT.md)及[Pro独立审查](../../research/full_layout_pro_review_20261004/REVIEW.md)。[字段合同](field_contract.json)、[全员8输出展示绑定](global_display_audit.json)、[历史24簇候选绑定](geometry_audit.json)、[浏览器检查](ui_check.json)分别记录范围，不能把簇候选数当作全图共识数。

在仓库根目录运行`python -m http.server 8879 --bind 127.0.0.1`。复现工作台用`python -B -m tools.thesis_main.analysis.consensus_result_studio_20261004 --out analysis_results/<新的目录>`；默认读取已完成的137图点结果，也可显式传`--global-results`。已有输出目录拒绝覆盖。

前端在`tools/thesis_main/analysis/consensus_result_studio_20261004.js`及同名CSS。共享工作台不属于本轮修改。截图仅内联目视检查，无截图文件留存。
'''
    (out/'README.md').write_text(text,encoding='utf-8',newline='\n')
    return attach_global_results(out,Path(global_results))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,default=SOURCE)
    parser.add_argument('--out',type=Path,default=OUT)
    parser.add_argument('--global-results',type=Path,default=GLOBAL_RESULTS)
    args=parser.parse_args()
    print(json.dumps(build(args.input,args.out,args.global_results)['counts']),flush=True)
