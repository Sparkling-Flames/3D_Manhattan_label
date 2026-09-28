"""复用Panorama Studio与已有审核导入导出，逐项列新数据异常，原点不修改。"""
import collections
import json
import re
import shutil
import numpy as np

from .analyze_new_manual_20260921 import ROOT,OUT,read,HIST,prepare
from .clustering_release.pipeline import rows_at
from .clustering_numeric_research.common import clean
from .paired_split_research.release_review import FOUNDATION,SCHEMA,digest
from tools.label_studio.panorama_studio.geometry import analyze


def build():
    dest=OUT/'审核';dest.mkdir(exist_ok=True)
    rows=rows_at(OUT/'responses.jsonl.gz');by={r['canonical_annotation_id']:r for r in rows}
    receipts=read(OUT.relative_to(ROOT)/'intake.json');ann={r['annotation']:r for r in receipts}
    registry=read('analysis_results/scene_image_exploration_20260910_v1/same_room_selection_registry_v2_20260912.json')
    _,records,elig=prepare(rows[:2501],rows[2501:],registry)
    meta={i['image_id']:i for i in registry['images']}
    distances={v['image_id']:v for v in read(OUT.relative_to(ROOT)/'distances.json') if v['pool']=='strict' and v['condition']=='manual'}
    membership=read(OUT.relative_to(ROOT)/'memberships.json')
    jobs=[]
    alerts=read(OUT.relative_to(ROOT)/'correspondence_alerts.json')
    for a in alerts:
        a['candidate_mapping_original_point_ids_top_bottom']=[dict(left=(records[a['a']]['links'][j]+1).tolist(),right=(records[a['b']]['links'][m-1]+1).tolist()) for j,m in enumerate(a['mapping_b_1based'])]
    iid=alerts[0]['image_id'];assert all(a['image_id']==iid for a in alerts)
    jobs.append(dict(iid=iid,kind='点位对应',pairs=[(a['a'],a['b']) for a in alerts],options=['确认候选对应且可视为相近','确认对应但仍保留差异','候选对应不成立','暂不能判断'],
        question='先核对W002与W033/W028的接缝处上下角点。换起点仅是候选，不自动合簇；请分别写两对作答的原点号对应及是否相近。',evidence=alerts))
    for r in receipts:
        if 'odd_unconfirmed' in r['flags']:
            jobs.append(dict(iid=r['image_id'],kind='奇数点',pairs=[(r['id'],r['id'])],options=['多标需删点（见文字）','漏标需补点（见文字）','原样保留观察','暂不能判断'],
                question=f"{r['worker']}／annotation {r['annotation']}共{r['point_count']}点。请明确多标/漏标及原点号；补点需给位置，不因奇数自动删。",evidence=r))
    dup=[r for r in receipts if 'multiple_submissions_version_pending' in r['flags']]
    assert len(dup)==2 and len({r['image_id'] for r in dup})==1
    jobs.append(dict(iid=dup[0]['image_id'],kind='同人重复版本',pairs=[tuple(r['id'] for r in dup)],options=['采用7271作为当前版本','采用7272作为当前版本','两份均暂不采用','暂不能判断'],
        question='W034／7271和7272是同人同图，不能算两人。请结合来源决定当前版本，不按哪个更像其他人来选。',evidence=dup))
    for r in elig.to_dict('records'):
        if r['id'].startswith('new_') and by[r['id']]['provenance']['strict_include'] and not r['bound_available']:
            jobs.append(dict(iid=r['image_id'],kind='上下绑定',pairs=[(r['id'],r['id'])],options=['确认上下对应（见文字）','点集需要修复（见文字）','原样保留观察','暂不能判断'],
                question=f"{r['worker']}上下角色/配对未唯一确定。请按p原点号写top-bottom对应，尤其检查地平线附近；局部确认不补成完整映射。",evidence=r))
    parents=collections.defaultdict(list)
    for r in receipts:
        if r['parent_annotation']:parents[r['image_id']].append(r)
    for iid,rr in sorted(parents.items(),key=lambda x:(meta[x[0]]['building'],meta[x[0]]['number'])):
        jobs.append(dict(iid=iid,kind='父记录来源',pairs=[(r['id'],ann[r['parent_annotation']]['id']) for r in rr],
            options=['已核实均独立作答（见依据）','存在复用或编辑父记录（见文字）','逐份情况不同（见文字）','来源仍不确定'],
            question='父记录关联是来源问题，不能单凭图像判断独立性。逐对切换核对人员/annotation，写明是否复制或编辑已有答案、代录或系统操作；点相同不能证明动机。',evidence=rr))
    cases=[];photos=[];geometry_cache={}
    for index,job in enumerate(jobs):
        iid=job['iid'];code=f"{meta[iid]['building']}-{meta[iid]['number']:02d}"
        ids=sorted(cid for cid,r in by.items() if r['image_id']==iid and r['raw_condition']=='manual')
        vv=[]
        for cid in ids:
            row=by[cid];points=row['effective_points_1024x512'] or row['raw_points_1024x512'] or []
            if cid not in geometry_cache:
                rec=records.get(cid);geom=None;error='尚无唯一计算点对，仅审二维原点；不能强行生成3D'
                if rec and rec['links'] is not None:
                    links=rec['links'];ordered=[dict(source_pair_id=f'raw:{a+1}/{b+1}',top=dict(zip(['x','y'],points[a])),bottom=dict(zip(['x','y'],points[b]))) for a,b in links]
                    try:geom=analyze(dict(width=1024,height=512,coordinate_mode='pixels',ordered_pairs=ordered))
                    except ValueError as e:error=str(e)
                geometry_cache[cid]=(geom,error)
            geom,error=geometry_cache[cid]
            aid=row.get('provenance',{}).get('annotation',row.get('raw_annotation_id'))
            vv.append(dict(name=f"{row['worker_id']} · Manual · annotation {aid} · {len(points)}点",geometry=geom,error=error,
                source=dict(canonical_annotation_id=cid,worker_id=row['worker_id'][1:],mode='Manual',annotation_id=aid,
                    display_points=points,effective_points=row['effective_points_1024x512'],points_display_kind=f'当前计算点／annotation {aid}',current_row=row)))
        labels={};pair_details={}
        for kind in ['representative','complete']:
            mm={r['id']:r['group'] for r in membership if r['pool']=='strict' and r['image_id']==iid and r['condition']=='manual' and r['metric']=='image' and r['nominal_cut']==9 and r['partition']==kind}
            labels[kind]=[mm.get(cid,'unavailable') for cid in ids]
            v=distances.get(iid);pairs=[]
            for a,b in job['pairs']:
                distance=None
                if a!=b and v and a in v['ids'] and b in v['ids']:
                    distance=v['image'][v['ids'].index(a)][v['ids'].index(b)]
                    if distance>=1e6:distance=None
                pairs.append(dict(ids=list(dict.fromkeys([a,b])),workers=[f"{by[c]['worker_id']}／{by[c].get('provenance',{}).get('annotation',by[c].get('raw_annotation_id'))}" for c in dict.fromkeys([a,b])],
                    distance=distance,unit='像素',kind=job['kind'],reason='来源或点集资格待确认；未用距离作裁决'))
            pair_details[kind]=pairs
        followup=dict(key=f'{iid}|{job["kind"]}|{index}',code=code,condition='Manual',reasons=job['question'],ids=ids,labels=labels,
            pairs_by_method=pair_details,decision_options=job['options'],coverage='本轮数值预警；具体AI目视意见未补造',
            point_numbering='p为当前计算数组原点号；本轮新记录与导出顺序一致。图上点击可放大；原点/来源随导出保存。',
            ai=[],user_original=[],research_notes=job['evidence'],user_decision=None)
        cases.append(dict(image_id=iid,title=f'{code} · {job["kind"]}',category='新增数据审核 · 按优先级',variants=vv,followup=followup))
        path='../../../'+meta[iid]['path'];photos.append(f'window.STUDIO_IMAGES[{index}]={{original:{json.dumps(path)},texture:{json.dumps(path)}}};')
    cases=clean(cases)
    binding=dict(input=digest(read(OUT.relative_to(ROOT)/'SUMMARY.json')),points=digest({c:r['effective_points_1024x512'] for c,r in by.items()}),review_content=digest([c['followup'] for c in cases]));binding['id']=digest(binding)
    payload=dict(schema=SCHEMA,binding=binding,cases=cases,counts=dict(cases=len(cases),variants=sum(len(c['variants']) for c in cases)),
        review_title='新增数据审核 · 8项点位/版本优先，31图父记录来源随后',export_filename='新增数据_我的审核.json',
        review_instructions='先审前8项，再核对父记录来源。保留每簇全选/取消、原点号、点击局部放大及有条件的3D。未进入计算的记录不属于同一簇。原始点不改，裁决默认留空。',
        decision_instructions='本项结论对应上方具体问题。多对作答请在文字中分别写人员、annotation和原点号；来源未知可暂缓。确认不会自动改点、传播映射或合簇。',
        method_options=[dict(value='representative',label='图上25.6px／真实代表半径'),dict(value='complete',label='图上25.6px／完整链接')])
    for name in ['studio.js','studio.css','history.css','three.min.js','OrbitControls.js']:shutil.copyfile(FOUNDATION/name,dest/name)
    panel=(ROOT/'tools/thesis_main/analysis/paired_split_research/release_review_panel.js').read_text(encoding='utf8')
    (dest/'followup.js').write_text(panel.replace('原图／历史3D','原图／条件3D'),encoding='utf8')
    html=(FOUNDATION/'index.html').read_text(encoding='utf8')
    html=re.sub(r'<script[^>]*src="(?:image_\d+|history_data|history)\.js"[^>]*></script>','',html)
    html=html.replace('</body>','<script defer src="followup.js"></script></body>').replace('<title>空间标本 · 全景布局审查</title>','<title>新增数据审核</title>')
    (dest/'index.html').write_text(html,encoding='utf8')
    (dest/'data.js').write_text('window.STUDIO_DATA='+json.dumps(payload,ensure_ascii=False,allow_nan=False)+';\nwindow.STUDIO_IMAGES={};\n'+'\n'.join(photos),encoding='utf8')
    (dest/'REVIEW_MANIFEST.json').write_text(json.dumps(dict(binding=binding,cases=[c['followup'] for c in cases]),ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8')
    print(payload['counts'])


if __name__=='__main__':build()
