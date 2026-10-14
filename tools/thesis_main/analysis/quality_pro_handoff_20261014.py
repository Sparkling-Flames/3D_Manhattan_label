"""只补证据、可视材料与离线交接；不搜索参数，不改资格。"""
from collections import Counter
from pathlib import Path
import json
import base64
import inspect
import io
import shutil
import zipfile
import numpy as np
from tools.thesis_main.analysis.quality_staged_calibration_20261014 import OUT as STAGE, PREP, ROOT, ARCHIVE, PACKAGE, read, engine
from tools.thesis_main.data_prep.consolidate_research_input import load_current_bundle
from tools.thesis_main.analysis.quality_decision_check_20261012 import render_reviews

OUT=ROOT/'research/quality_pro_handoff_20261014'
PACK=OUT/'package'


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def penalty_diagnostic(components):
    terms=('boundary_loss','direction_loss','global_height_loss','local_height_loss')
    return dict(largest_denominator_term=max(terms,key=components.get),
                height_score_drop=components['height_score_drop'],
                interpretation='仅比较分母四项，未含分子IoU；不是因果归因或人工严重度')


def prepare():
    e=engine();data=load_current_bundle()['data']
    objects={o['object_id']:o for o in data['objects']};images={o['image_id']:o for o in data['images']}
    baseline=read(PREP/'BASELINE.json')['rows'];door=read(STAGE/'DOORWAY.json');coarse=read(STAGE/'COARSE.json')
    admission={r['record_id']:r for r in read(ROOT/'research/quality_data_admission_audit_20261013/FULL_ADMISSION.json')['records']}
    ledger={r['record_id']:r for r in read(ROOT/'research/quality_scope_resolution_20261013/STAGE_LEDGER.json')['records']}
    history=[dict(record_id=r['id'],**{k:v for k,v in r.items() if k!='id'}) for r in read(ARCHIVE/'calibration/inputs/search_inputs.json')['rows'] if r['id'] in coarse['historical_scores']]
    records={r['record_id']:r for r in baseline+door['rows']+history}
    needed={r['object_id'] for r in records.values()}
    for r in records.values():
        ref=r.get('reference_object_id') or (r.get('reference') or {}).get('object_id')
        if ref:needed.add(ref)
    for r in door['rows']:
        needed.update(ref['object_id'] for ref in r['available_reference_versions'].values())
    fields=('object_id','object_kind','image_id','image_code','worker_id','condition','source','points_1024x512',
        'original_export_points','before_preprocessing_points','links_zero_based','ordered_source_point_indices',
        'ordered_source_pair_indices','pairing_basis','geometry','preprocessing','repair_evidence','final_review')
    selected=[];geometries={};unavailable={}
    for oid in sorted(needed):
        obj=objects[oid];row={k:obj[k] for k in fields if k in obj}
        ev=obj.get('review_evidence',{})
        row['review_evidence']={k:ev[k] for k in ('verdict','current_comment','current_decision_comment','image_comment',
            'gt_version_note','review_history','image_review_history','annotation_traits','image_traits','semantic_annotation_evidence','semantic_image_evidence') if k in ev}
        selected.append(row)
        try:
            if obj['geometry']['status']!='surface_valid' or not obj['links_zero_based']:raise ValueError('current_geometry_not_surface_valid')
            geometries[oid]=e['geometry'](obj['points_1024x512'])
        except ValueError as exc:unavailable[oid]=str(exc)
    write(PACK/'data/objects.json',dict(objects=selected,geometry_unavailable=unavailable,geometries=geometries,
        coordinate_frame=data['coordinate_frame'],preprocessing=data['preprocessing'],sources=data['sources']))
    scopes=[];pairs=[]
    for image in door['images']:
        rows=[r for r in door['rows'] if r['image_code']==image['image_code']];im=images[rows[0]['image_id']]
        valid=[r for r in rows if r['status']=='complete']
        comments=[dict(record_id=r['record_id'],object_id=r['object_id'],source='current_loader.review_evidence',
                       evidence=next(o['review_evidence'] for o in selected if o['object_id']==r['object_id'])) for r in rows]
        scoped=dict(image=im,counts=image['statuses'],records=[r['record_id'] for r in rows],annotation_reviews=comments,
            semantic_state='已有评论/场景依据；并非完整参考语义确认' if im['image_comment'] or im['comments'] else '条件数值；没有找到明确的全布局参考确认',
            floor_basis=im['expected_annotation_extent'],top_basis='现有GT坐标；未新增逐点顶界人工确认',
            photo='photos/'+im['image_id']+'.png',reference_versions=rows[0]['available_reference_versions'],
            held_followup='保留既有hold；参考版本备注未绑定，不从Q选参考',
            held_reasons=dict(Counter(x for r in rows for x in r['reason_codes'])))
        if valid:
            chosen=[min(valid,key=lambda r:r['candidate_components']['center']['score']),max(valid,key=lambda r:r['candidate_components']['center']['score'])]
            pid='D'+str(len(pairs)+1).zfill(2)
            scoped['visual_pair']=pid
            pairs.append(dict(id=pid,records=[dict(id=r['record_id'],image_id=r['image_id'],reference_object_id=r['reference']['object_id'],object_id=r['object_id']) for r in chosen],
                question='核查范围、底边和顶界：A/B与绿色参考分别表达了什么？分数极端仅为选例依据，不是人评标签。'))
        scopes.append(scoped)
    for pid,ids in [('N01',('R01501','R01191')),('N02',('R02888','R03123')),('N03',('R03274','R03272')),('N04',('R03346','R03347'))]:
        pairs.append(dict(id=pid,records=[dict(id=rid,**{k:records[rid][k] for k in ('image_id','reference_object_id','object_id')}) for rid in ids],question='普通图既有分歧与明显改分案例，保留已有意见，不预设哪份更好。'))
    ordinary=[r for r in baseline if r['use']=='ordinary_development']
    shifts=[dict(record_id=r['record_id'],image_id=r['image_id'],image_code=objects[r['object_id']]['image_code'],
        delta=coarse['records'][r['record_id']]['hill_global08']['score']-coarse['records'][r['record_id']]['current_tail']['score'],
        review_evidence=objects[r['object_id']]['review_evidence']['current_comment']) for r in ordinary]
    shifts.sort(key=lambda r:-r['delta'])
    valid=[r for r in door['rows'] if r['status']=='complete']
    diagnostics={r['record_id']:penalty_diagnostic(r['candidate_components']['center']) for r in valid}
    strata=Counter('explicit_ordinary' if ledger[r['record_id']]['ordinary_status_is_explicit'] else 'existing_conditional' for r in ordinary)
    assert dict(strata)=={'explicit_ordinary':207,'existing_conditional':367}
    write(PACK/'data/supplement.json',dict(schema='quality_pro_supplement_v1',doorway_images=scopes,ordinary_changes=shifts,
        doorway_diagnostics=diagnostics,summary=dict(ordinary=574,ordinary_strata=dict(strata),severe=9,doorway=217,complete=125,held=92,
        shifts_ge5=sum(r['delta']>=5 for r in shifts),shifts_ge10=sum(r['delta']>=10 for r in shifts),
        denominator_dominant=dict(Counter(r['largest_denominator_term'] for r in diagnostics.values())),
        median_height_drop=float(np.median([r['height_score_drop'] for r in diagnostics.values()]))),
        parameter_change=False,formal_eligibility_change=False))
    write(PACK/'data/cohorts.json',dict(ordinary=[dict(r,scene_layer=ledger[r['record_id']]) for r in ordinary],
        severe=[r for r in baseline if r['use']=='separate_severe_constraint'],doorway=door['rows'],historical_only=history,
        admissions=[admission[rid] for rid in records if rid in admission]))
    write(PACK/'data/review_pairs_private.json',dict(review_pairs=pairs))
    photos={p.stem:p for p in (ROOT/'data/mp3d_layout').glob('*/img/*.png')}
    image_ids={s['image']['image_id'] for s in scopes}|{p['records'][0]['image_id'] for p in pairs}
    for iid in image_ids:
        dest=PACK/'photos'/f'{iid}.png';dest.parent.mkdir(exist_ok=True);shutil.copy2(photos[iid],dest)
    write(PACK/'data/photo_sources.json',{iid:photos[iid].relative_to(ROOT).as_posix() for iid in sorted(image_ids)})
    for src,folder in [(STAGE,'stage'),(PREP,'preparation')]:
        for name in (['COARSE.json','DOORWAY.json','REGRESSION.json','WORKING_COARSE.json','WORKING_FINAL.json','DESIGN.json','README.md'] if folder=='stage' else ['EVIDENCE.json','BOTTOM_CONTROLS.json','RESPONSE_FINDINGS.json']):
            dest=PACK/folder/name;dest.parent.mkdir(exist_ok=True);shutil.copy2(src/name,dest)
    for rel,name in [('quality_height_calibration_ready_20261013/CONTROLS.json','HEIGHT_CONTROLS.json'),
                     ('quality_scope_resolution_20261013/USER_REVIEW_v2.json','height_user_receipt.json'),
                     ('quality_scope_resolution_20261013/REVIEW_INTERPRETATION.json','height_interpretation.json')]:
        shutil.copy2(ROOT/'research'/rel,PACK/'preparation'/name)
    for key in ('au','sp','valid','hm','center','trad','score'):
        dest=PACK/'engine'/Path(e[key].__file__).name;dest.parent.mkdir(exist_ok=True);shutil.copy2(e[key].__file__,dest)
    shutil.copy2(ARCHIVE/'routing/prepare_inputs.py',PACK/'engine/prepare_inputs.py')
    # 冻结传统IoU模块在调用时需要同目录vendor；不带不相关引擎脚本。
    vendor=Path(e['trad'].__file__).parent/'vendor'
    shutil.copytree(vendor,PACK/'engine/vendor',dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    write(PACK/'data/source_manifest.json',dict(schema='quality_pro_source_manifest_v1',status='awaiting_targeted_human_receipt',
        engine_sources={Path(e[k].__file__).name:Path(e[k].__file__).relative_to(ROOT).as_posix() for k in ('au','sp','valid','hm','center','trad','score')},
        source_loader='analysis_results/research_input_20260929/manifest.json',no_new_tuning=True,
        purpose='离线调参输入，非正式算法发布；新增人审回执尚未收到'))
    render_reviews(dict(geometries=geometries),dict(review_pairs=pairs),PACK)
    print(json.dumps(dict(images=len(image_ids),pairs=len(pairs),objects=len(selected),geometry_unavailable=len(unavailable)),ensure_ascii=False))


def package():
    with zipfile.ZipFile(OUT/'quality_pro_handoff_20261014_PENDING_REVIEW.zip','w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(PACK.rglob('*')):
            if p.is_file() and '__pycache__' not in p.parts:z.write(p,p.relative_to(PACK))


def pages():
    from PIL import Image
    objects_data=read(PACK/'data/objects.json');geos=objects_data['geometries'];objects={r['object_id']:r for r in objects_data['objects']}
    pairs=read(PACK/'data/review_pairs_private.json')['review_pairs']
    def question(qid,title,purpose,options):return dict(id=qid,title=title,purpose=purpose,options=options)
    quality=question('overall','结合照片、底面和三维，两份整体质量如何？','确认不同错误的取舍；不要求给分。',[
        ('A','A明显更好'),('A_slight','A略好'),('close','整体接近'),('B_slight','B略好'),('B','B明显更好'),
        ('both_bad','两份都不合理，不宜仅排先后'),('different_scope','范围不同，无法直接比较'),('uncertain','不确定／看不清')])
    primary=question('main_issue','影响判断的主要问题在哪里？','把范围、底面和高度区分，避免只调高度。',[
        ('scope','选择的范围或停止位置'),('floor','底点位置／底面形状或墙间夹角'),('height','整体高度或局部顶面'),
        ('mixed','多个问题共同影响'),('minor','都没有明显问题'),('reference','参考本身有明显问题'),('uncertain','无法判断')])
    scope=question('reference_scope','绿色静态参考／紫色交互参考包含右侧长廊，能否作为这张图的评价目标？','核实小房间与门外长廊的范围依据，不因分数高而选择。',[
        ('full_only','可以，完整范围应包含长廊'),('both_valid','完整范围可以，但只标小房间也合理'),('small_only','应只标小房间，参考范围不合适'),
        ('neither','两种范围都不合理'),('uncertain','无法判断')])
    top=question('reference_top','参考的顶部边界，是否有严重到不宜用作参考的问题？','沿用小瑕疵仍按正确参考的口径，仅确认实质性问题。',[
        ('usable','可用；即使有小偏差也不影响参考'),('serious','存在明显实质错误，请备注位置'),('uncertain','遮挡／看不清，无法判断')])
    selected={'D06':('Q01',[scope,top],'这一例只确认评价范围与参考顶界，不要求给A/B打分。'),
              'D09':('Q02',[quality,primary],'比较一份保留部分转折但歪斜、另一份省略转折的整体得失。'),
              'N01':('Q03',[quality,primary],'两份已有正面旧评论；这里仅补它们之间的整体比较，旧评价不撤销。')}
    cards=[]
    def record(oid,label):
        g=geos[oid];paths=[]
        rings=[np.asarray(g[k]) for k in ('bottom3d','top3d')]
        edges=[(a,b) for ring in rings for a,b in zip(ring,np.roll(ring,-1,axis=0))]+list(zip(*rings))
        for a,b in edges:
            p=np.linspace(a,b,80);xy=np.c_[(np.arctan2(p[:,0],-p[:,2])/(2*np.pi)+.5)*1024,(.5-np.arctan2(p[:,1],np.hypot(p[:,0],p[:,2]))/np.pi)*512]
            split=np.where(np.abs(np.diff(xy[:,0]))>512)[0]+1
            paths.append(dict(segments=[x.tolist() for x in np.split(xy,split) if len(x)>1]))
        return dict(**g,reviewId=label,points=objects[oid]['points_1024x512'],erpPaths=paths)
    for pair in pairs:
        a,b=pair['records'];assert a['reference_object_id']==b['reference_object_id']
        pid=pair['id'];cid,questions,purpose=selected.get(pid,(pid,[],'既有材料备查，不需要重复作答。'))
        photo='photos/'+a['image_id']+'.png'
        preview=io.BytesIO()
        with Image.open(PACK/photo) as image:image.convert('RGB').save(preview,format='JPEG',quality=92)
        cards.append(dict(id=cid,pair_id=pid,image_id=a['image_id'],image_code=objects[a['object_id']]['image_code'],
            photo=photo,photo_data='data:image/jpeg;base64,'+base64.b64encode(preview.getvalue()).decode(),
            A=record(a['object_id'],'A'),B=record(b['object_id'],'B'),G=record(a['reference_object_id'],'GT'),
            purpose=purpose,questions=questions,bindings=dict(A=a,B=b)))
    write(PACK/'data/human_review_manifest.json',dict(schema='quality_pro_review_20261014_v1',status='awaiting_receipt',
        cards=[{k:v for k,v in r.items() if k not in ('photo_data','A','B','G')} for r in cards],
        score_blinded=True,algorithm_blinded=True,previous_opinions_not_displayed_for_pairwise_answers=True))
    (PACK/'review_data.js').write_text('const REVIEW_DATA='+json.dumps(cards,ensure_ascii=False).replace('</','<\\/')+';\n',encoding='utf-8')
    for source,name in [('quality_pro_review_20261014.html','REVIEW.html'),('quality_pro_review_20261014.js','review_app.js')]:
        shutil.copy2(ROOT/'tools/thesis_main/analysis'/source,PACK/name)
    (PACK/'vendor').mkdir(exist_ok=True)
    for source,name in [('tools/label_studio/three.min.js','three.min.js'),('tools/label_studio/OrbitControls.js','OrbitControls.js'),
                        ('research/quality_review36_20261008/frontend/review36-view.js','review36-view.js')]:
        shutil.copy2(ROOT/source,PACK/'vendor'/name)
    # 所有新增逐边数据为解释性诊断，不进Q，也不建立错误点人工真值。
    e=engine();detail={}
    for pair in pairs:
        for r in pair['records']:
            geo=geos[r['object_id']];theta,w=e['au'].direction_data(geo);axis=e['au'].direction_axis(geo)
            residual=np.rad2deg((theta-axis+np.pi/4)%(np.pi/2)-np.pi/4)
            assert abs(np.sqrt(np.dot(w,residual**2)/w.sum())-e['au'].direction_residual(geo,axis))<1e-8
            detail[r['id']]=dict(common_axis_radians=axis,edge_residual_degrees=residual.tolist(),
                normalized_edge_length=(w/w.sum()).tolist(),weighted_squared_residual=(w/w.sum()*residual**2).tolist(),
                bottom_polar_elevation_degrees=(90-np.asarray(objects[r['object_id']]['points_1024x512'])[1::2,1]/512*180).tolist(),
                wall_heights=(np.asarray(geo['top3d'])[:,1]+1).tolist(),reference_object_id=r['reference_object_id'])
    write(PACK/'data/selected_geometry_diagnostics.json',detail)
    control_geometries=[]
    for r in read(PACK/'preparation/BOTTOM_CONTROLS.json')['rows']:
        control_geometries.append(dict(record_id='quality_calibration_preparation_20261013:'+r['case_id'],
            source='34份既有底点控制；本包由既有点坐标还原几何，未全量重算metrics',
            annotation_geometry=e['geometry'](r['points']),reference_geometry=e['geometry'](r['reference_points'])))
    old={r['case_id']:r for r in read(ARCHIVE/'calibration/results/physical_controls.json')['rows']}
    for r in read(PACK/'preparation/HEIGHT_CONTROLS.json')['records']:
        g=old[r['case_id']] if r['origin']=='reused_frozen_control' else r
        control_geometries.append(dict(record_id='quality_height_calibration_ready_20261013:'+r['case_id'],
            source='48份旧高度控制' if r['origin']=='reused_frozen_control' else '62份此前重建高度控制',
            annotation_geometry=g['annotation_geometry'],reference_geometry=g['reference_geometry']))
    for r in read(PACK/'stage/COARSE.json')['controls']:
        if r['source']!='new_complete_rhombus_RMS':continue
        theta=np.radians(r['angle']);u=np.array([1.,0]);v=np.array([np.cos(theta),np.sin(theta)])
        p=np.array([(-u-v)/2,(u-v)/2,(u+v)/2,(-u+v)/2]);ref=np.array([[-.5,-.5],[.5,-.5],[.5,.5],[-.5,.5]])
        def geo(x):return dict(bottom3d=np.c_[x[:,0],-np.ones(4),x[:,1]].tolist(),top3d=np.c_[x[:,0],np.full(4,1.6),x[:,1]].tolist())
        control_geometries.append(dict(record_id=r['record_id'],source='本轮七份完整RMS菱形控制',annotation_geometry=geo(p),reference_geometry=geo(ref)))
    assert len(control_geometries)==151
    write(PACK/'data/control_geometries.json',control_geometries)
    from tools.thesis_main.analysis.quality_manual_expansion_20261013 import evaluate_geometry
    (PACK/'engine/evaluate_geometry.py').write_text('import numpy as np\n\n'+inspect.getsource(evaluate_geometry),encoding='utf-8')
    shutil.copy2(ROOT/'tools/thesis_main/analysis/quality_pro_offline_20261014.py',PACK/'run.py')
    print('3例待审、16组查看器、逐边诊断已生成；参数不变')


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=('prepare','pages','package'))
    {'prepare':prepare,'pages':pages,'package':package}[parser.parse_args().stage]()
