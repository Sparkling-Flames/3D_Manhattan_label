"""复用绿色 Panorama Studio 的109份独立点编辑复核；不写回正式数据。"""
from __future__ import annotations
import argparse,csv,hashlib,json,shutil,zipfile
from collections import Counter
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).parent
OUT=ROOT/'analysis_results/point_edit_review_20261009'
RECEIVED=ROOT/'research/point_review_109_received_20261009'
RESCREEN=RECEIVED/'109份复核重筛清单_20261010.csv'
QUEUE_RESOLUTION=RECEIVED/'queue_resolution_20261010.json'
MEMBER='quality_research_20261009/inputs/snapshot/image_manifest.json'
def digest(b):return hashlib.sha256(b).hexdigest()
def encode(x):return json.dumps(x,ensure_ascii=False,separators=(',',':'))
def hjson(x):return digest(encode(x).encode('utf-8'))
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def point(oid,i,xy):
 return dict(id=f'{oid}::original_export_points[{i}]',label=f'p{i+1}',x=xy[0],y=xy[1],origin='original',source_index=i)
def normalize(o,review,history,image):
 oid=o['canonical_object_id'];raw=o['original_export_points']
 rp=[point(oid,i,p) for i,p in enumerate(raw)]
 versions={'raw':dict(name='原始导出 · 稳定原p号',available=True,points=rp,pairs=[]),
           'historical':dict(name='历史生效删点 · 只读证据',available=False,points=[],pairs=[]),
           'current':dict(name='当前有效输入 · 缺失不回退',available=False,points=[],pairs=[])}
 if history:
  assert history['canonical_object_id']==oid and history['image_id']==o['image_id'] and history['source']==o['source']
  assert history['original_export_points']==raw
  ids=history['historical_effective_to_original_indices_zero_based']
  assert history['historical_effective_points_reconstructed']==[raw[i] for i in ids]
  versions['historical'].update(available=True,points=[rp[i] for i in ids])
 cp=o['preprocessed_points'];indices=o['original_export_indices']
 warnings=[]
 if cp:
  if len(cp)==len(indices) and all(isinstance(i,int) and 0<=i<len(raw) for i in indices):
   pts=[point(oid,i,p) for i,p in zip(indices,cp)]
   ps=[[pts[a]['id'],pts[b]['id']] for a,b in o['links_zero_based'] or []]
   versions['current'].update(available=True,points=pts,pairs=ps)
  else:warnings.append('当前有效点缺少可靠原始身份映射，不作为可编辑基准')
 else:warnings.append('冻结研究输入中的有效点 / 配对 / 确认环缺失；本次独立草稿另行显示，不自动写回或恢复资格。')
 if review['note_problem']:warnings.append(review['note_problem'])
 if review['raw_out_of_domain_points']!='[]':warnings.append('原始越界点：'+review['raw_out_of_domain_points']+'；显示原值，不取模或裁剪修正')
 if history:warnings.append('历史删除已生效于9/9计算视图；当前 missing_point_identity 断链。历史预览不补造配对或环。')
 if review['new_review_vs_historical_action']:warnings.append(review['new_review_vs_historical_action'])
 warnings.append('新审查CSV未声明坐标版本或点号约定，第三方建议均待审')
 return dict(record_id=o['id'],canonical_object_id=oid,image_id=o['image_id'],image_code=o['image_code'],worker=o['worker'],condition=o['condition'],
 source_identity={k:o['source'][k] for k in ['project','task','annotation']},source_hash=hjson(o),raw_hash=hjson(raw),current_hash=hjson(cp),
 photo_hash=image.get('sha256'),photo=image,versions=versions,reviewer=review,history=history,current=o,warnings=warnings)
def build(package,base):
 package=package.resolve()
 assert package.is_dir(),'109资料目录不可读'
 manifest=read(package/'MANIFEST_SHA256.json')
 for name,value in manifest.items():
  expected=value['sha256'] if isinstance(value,dict) else value
  assert digest((package/name).read_bytes())==expected,'包内hash不匹配:'+name
 objects=read(package/'source_extracts/current_109_records.json')['objects']
 reviews=read(package/'review_109_identity_and_actionability.json')
 history={r['record_id']:r for r in read(package/'history/historical_four_deletions_preview.json')['cases']}
 assert len(objects)==len(reviews)==109
 om={o['id']:o for o in objects};assert len(om)==109 and len({o['canonical_object_id'] for o in objects})==109
 assert len({o['image_id'] for o in objects})==71
 with zipfile.ZipFile(base) as z:images={i['image_id']:i for i in json.loads(z.read(MEMBER))}
 rm={r['record_id']:r for r in reviews}
 with (package/'delete_point_bindings_14.csv').open(encoding='utf-8-sig') as f:bindings=list(csv.DictReader(f))
 local={o['object_id']:o for o in read(ROOT/'analysis_results/research_input_20260929/preprocessed_source.json')['objects']}
 photos={}
 for image_id in {o['image_id'] for o in objects}:
  item=images[image_id];path=(ROOT/item['source_path']).resolve();available=path.is_file()
  photo=dict(source_path=item['source_path'],available=available,expected_width=item['original_width'],expected_height=item['original_height'])
  if available:
   with Image.open(path) as im:im.load();photo.update(width=im.width,height=im.height)
   photo['sha256']=digest(path.read_bytes())
   photo['dimension_conflict']=(photo['width'],photo['height'])!=(item['original_width'],item['original_height'])
  photos[image_id]=photo
 cases=[]
 for record_id in [r['record_id'] for r in reviews]:
  o=om[record_id];review=rm[record_id]
  assert (review['canonical_object_id'],review['image_id'],review['worker'],review['raw_point_count'])==(o['canonical_object_id'],o['image_id'],o['worker'],len(o['original_export_points']))
  assert all(review['source_'+k]==o['source'][k] for k in ['project','task','annotation'])
  c=normalize(o,review,history.get(record_id),photos[o['image_id']])
  lo=local.get(o['canonical_object_id'])
  c['proposed_deletions']=[b for b in bindings if b['record_id']==record_id]
  for b in c['proposed_deletions']:
   i=int(b['raw_index_zero_based']);assert b['canonical_object_id']==o['canonical_object_id'] and o['original_export_points'][i]==[float(b['x_1024']),float(b['y_512'])]
  c['local_coordinate_parity']=bool(lo and all(lo.get(k)==o.get(k) for k in ['image_id','original_export_points','before_preprocessing_points','preprocessed_points','links_zero_based','points_1024x512']))
  if not c['local_coordinate_parity']:c['warnings'].append('包内快照与本机当前坐标存在版本差异，请明确审查包内冻结版本')
  if not c['photo']['available']:c['warnings'].append('原图缺失：'+c['photo']['source_path'])
  if c['photo'].get('dimension_conflict'):c['warnings'].append('原图尺寸与图像清单冲突；确认已停止')
  cases.append(c)
 counts=dict(Counter(r['reviewer_conclusion'] for r in reviews))
 assert counts=={'需补点':39,'需删点':37,'建议恢复候选':18,'需改点':6,'坐标需修复':4,'维持原裁决':3,'其他':2}
 with RESCREEN.open(encoding='utf-8-sig',newline='') as f:screen=list(csv.DictReader(f))
 assert len(screen)==109 and {r['record_id'] for r in screen}==set(om)
 for r in screen:
  o=om[r['record_id']]
  assert (r['image_code'],r['worker'],r['canonical_object_id'],r['image_id'])==(o['image_code'],o['worker'],o['canonical_object_id'],o['image_id'])
  assert all(r['source_'+k]==str(o['source'][k]) for k in ['project','task','annotation'])
  assert r['保留在本次待核验清单'] in {'是（见待审类别）','否'}
 source_selected=[r for r in screen if r['保留在本次待核验清单'].startswith('是')]
 assert len(source_selected)==25
 resolution=read(QUEUE_RESOLUTION)
 assert resolution['schema']=='point_review_queue_resolution_20261010_v1'
 excluded_workers=Counter((r['worker'],local[r['canonical_object_id']]['worker_id']) for r in screen if r['保留在本次待核验清单']=='否')
 assert excluded_workers=={('P013','W019'):57,('P016','W026'):27}
 for record_id,item in resolution['records'].items():
  assert record_id in {r['record_id'] for r in source_selected} and item['action']=='remove_from_pending' and item['formal_decision_changed'] is False
  review=rm[record_id]
  if item['outcome']=='existing_invalid':
   assert review['current_review_verdict']=='invalid' and review['current_cleaning_disposition']=='excluded_by_review'
  elif item['outcome']=='retained_oos_uncalculable':
   assert review['current_review_verdict']=='usable' and review['current_cleaning_disposition']=='retained' and review['current_pairing_basis']=='user_explicit_oos_uncalculable'
  elif item['outcome']=='oos_no_effective_points':
   assert review['current_pairing_basis']=='no_effective_points' and review['current_na_reason']=='annotation_points_unavailable'
  else:raise AssertionError('未知队列处理结果:'+item['outcome'])
  if item['outcome']!='existing_invalid':assert next(r for r in screen if r['record_id']==record_id)['图片OOS判定']=='是'
 selected=[r for r in source_selected if r['record_id'] not in resolution['records']]
 review_queue=dict(source_file=str(RESCREEN.relative_to(ROOT)).replace('\\','/'),source_selected_records=len(source_selected),selected_records=len(selected),selected_images=len({r['image_id'] for r in selected}),excluded_records=len(screen)-len(source_selected),
                   resolved_removed_records=list(resolution['records']),resolved_items=resolution['records'],resolution_file=str(QUEUE_RESOLUTION.relative_to(ROOT)).replace('\\','/'),
                   items=[dict(record_id=r['record_id'],category=r['本轮处理类别'],reason=r['筛选原因'],advice=r['给本地线程的处理建议']) for r in selected])
 data=dict(schema='point_edit_review_20261009_v1',source_hash=hjson(manifest),queue_hash=hjson([c['source_hash'] for c in cases]),cases=cases,
           categories=counts,scope='review_patch_only',expected_records=109,image_count=71,review_queue=review_queue)
 OUT.mkdir(parents=True,exist_ok=True)
 if package!=RECEIVED:shutil.copytree(package,RECEIVED,dirs_exist_ok=True)
 (OUT/'data.js').write_text('window.POINT_REVIEW_DATA='+encode(data)+';\nwindow.STUDIO_IMAGES={};\nwindow.STUDIO_DATA='+encode(dict(cases=[
  dict(image_id=c['image_id'],title=f"{c['record_id']} · {c['image_code']} · {c['worker']}",category='109份独立复核 · '+c['reviewer']['reviewer_conclusion'],
       image_script='images/'+str(i)+'.js',variants=[
        dict(name=v['name'],source=dict(role='annotation',record_id=c['record_id'],version=k),geometry=None,error='本版本没有完整上下配对及确认环，不能生成房间表面')
        for k,v in c['versions'].items()]+[dict(name='新审核草稿 · 独立补丁',source=dict(role='annotation',record_id=c['record_id'],version='draft'),geometry=None,error='草稿尚未提供确认环，不生成房间表面')])
  for i,c in enumerate(cases)],counts=dict(cases=109,variants=436)))+';',encoding='utf-8')
 (OUT/'images').mkdir(exist_ok=True)
 for i,c in enumerate(cases):
  url='/image/'+c['image_id']
  (OUT/'images'/f'{i}.js').write_text(f'window.STUDIO_IMAGES[{i}]='+encode(dict(original=url,texture=url))+';',encoding='utf-8')
 # 保持绿色工作台的HTML、CSS和Three.js渲染器，增补独立点编辑层。
 original=ROOT/'analysis_results/order_studio_20260926'
 for name in ['studio.css','studio.js','three.min.js','OrbitControls.js']:
  shutil.copy2(original/name,OUT/name)
 shutil.copy2(HERE/'order_studio_20260926.css',OUT/'order_studio.css')
 html=(original/'index.html').read_text(encoding='utf-8')
 html=html.replace('<title>点对拖拽排序</title>','<title>点位复核（109份底库）</title>')
 html=html.replace('PANORAMA / SPATIAL STUDY','POINT REVIEW').replace('空间标本<span>全景布局审查</span>','点位复核<span>独立审核草稿</span>')
 html=html.replace('<script defer src="order_studio.js"></script>','<script defer src="point_edit_core.js"></script><script defer src="point_edit_sort.js"></script><script defer src="point_edit.js"></script>')
 html=html.replace('</head>','<link rel="stylesheet" href="point_edit.css"></head>')
 html=html.replace('<span class="read-only"><i></i>本地 · 只读</span>','<span class="read-only"><i></i>本地 · 独立审核草稿</span>')
 html=html.replace('<div class="toolbar">',(HERE/'point_edit_review_20261009_controls.html').read_text(encoding='utf-8')+'<div class="toolbar">',1)
 html=html.replace('<div class="viewport" id="viewport-raw">','<div class="viewport" id="viewport-raw"><div id="point-geometry-empty" class="empty-state">无完整上下配对及确认环；保留点，未生成3D房间。</div>')
 html=html.replace('原始重建','配对 / 环 / 3D状态').replace('曼哈顿约束','历史查看')
 (OUT/'index.html').write_text(html,encoding='utf-8')
 for src,dst in [('point_edit_review_20261009_core.js','point_edit_core.js'),('point_edit_review_20261009_sort.js','point_edit_sort.js'),('point_edit_review_20261009.js','point_edit.js'),('point_edit_review_20261009.css','point_edit.css')]:
  shutil.copy2(HERE/src,OUT/dst)
 (OUT/'image_sources.json').write_text(encode({k:v['source_path'] for k,v in photos.items()}),encoding='utf-8')
 validation=dict(bound_proposed_deletions=sum(len(c['proposed_deletions']) for c in cases),records=len(cases),unique_record_canonical_image_bindings=len({(c['record_id'],c['canonical_object_id'],c['image_id']) for c in cases}),
 images=len(photos),readable_original_images=sum(p['available'] for p in photos.values()),dimension_conflicts=sum(p.get('dimension_conflict',False) for p in photos.values()),
 local_coordinate_parity=sum(c['local_coordinate_parity'] for c in cases),history_deletions={k:v['removed_original_labels'] for k,v in history.items()},categories=counts,
 source_hash=data['source_hash'],queue_hash=data['queue_hash'],initial_user_confirmations=0,manifest_files_verified=len(manifest),
 rescreen_selected_records=review_queue['selected_records'],rescreen_selected_images=review_queue['selected_images'],rescreen_excluded_records=review_queue['excluded_records'],rescreen_resolved_removed_records=len(resolution['records']))
 (OUT/'validation.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2),encoding='utf-8')
 (OUT/'field_contract.json').write_text(json.dumps(dict(schema=data['schema'],identity='record_id + canonical_object_id + 完整image_id + project/task/annotation',
 original_point_id='canonical_object_id::original_export_points[原始零基索引]；显示原p标签，删除不重编号',new_point_id='new:uuid，不属于原作答；保存来源及是否插补',
 versions='raw / historical / current / draft；基准必须手工选择，缺失current不回退',hashes='source_hash=包内manifest规范JSON SHA256；记录source_hash=冻结对象；raw_hash/current_hash=相应数组规范JSON；photo_hash=本机实际原图字节',
 operations='pair_x按周期x生成候选上下点对并记录为一项可撤销操作；order拖动完整上下点对，仅改变有序pairs及相邻连接，坐标与稳定点ID不变；每项带操作ID/时间/稳定点ID/前后坐标/前后配对；移动解除关联配对；undo仅撤销本草稿操作，不恢复历史删除',statuses=['draft','completed','confirmed','deferred','kept'],
 confirmation='completed仅表示用户完成本条复核，备注可空、不要求勾选；外部意见仍只读；confirmed为兼容旧记录的补丁确认；ring_confirmed=false；不恢复人员/作答或投票资格；不足完整点对可保留未解决状态',
 persistence='既有草稿缓存键不变；编辑自动保存；刷新恢复最近记录；导入原子校验，冲突不覆盖；保存失败保留内存改动并暂停切换',
 review_queue='默认导航按20261010重筛清单及队列裁决补充文件遍历待核对象；人员已排除84份、既有单条invalid五份、明确OOS不可计算五份及OOS无有效点一份不重复审核；后两类保留原状态并记为无法计算，不以奇数点强行修改；原109份保留供查看与继续旧草稿；浏览器草稿绑定source_hash/原queue_hash不变，切换范围不改变审核返回',
 scope='不写原始标注、正式点数据、GT、算法、分数；不自动批准第三方建议'),ensure_ascii=False,indent=2),encoding='utf-8')
 return validation
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--package',type=Path,required=True);p.add_argument('--base',type=Path,required=True);a=p.parse_args();print(json.dumps(build(a.package,a.base),ensure_ascii=False,indent=2))
