"""Seal actual results and source evidence; no model output is an adjudication."""
from pathlib import Path
import json,hashlib,html,zipfile,shutil,sys,platform
import numpy as np
import pandas as pd
import scipy,shapely,cv2,PIL
import measure as m
PIN='29f628fd5a9c4d3e2064ffffec32bbffb324776c'
S=Path(__file__).resolve().parent

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def esc(x):return html.escape(str(x))
def mdtable(df):
 cols=list(df.columns);lines=['| '+' | '.join(cols)+' |','| '+' | '.join(['---']*len(cols))+' |']
 for row in df.itertuples(index=False,name=None):lines.append('| '+' | '.join('' if pd.isna(x) else str(round(x,5)) if isinstance(x,float) else str(x).replace('|','/') for x in row)+' |')
 return '\n'.join(lines)
def run():
 O=m.O;P=m.P;R=m.ROOT
 records=m.js(O/'review/verified_records.json');assert len(records)==12
 logs=pd.concat([pd.read_csv(O/f'rendering/{p}_preview_log.csv') for p in ['calibration','expansion']],ignore_index=True)
 assert len(logs)==70 and logs.filled_surface.all() and logs.reason.fillna('').eq('').all()
 manifest_download=m.js(O/'originals/download_manifest.json');dl={r['case_id']:r for r in manifest_download}
 evidence=[]
 for r in records:
  cid=r['case_id'];original=O/f'originals/{cid}_original.jpg';assert original.is_file() and sha(original)==dl[cid]['sha256']
  for p in [original,*[O/f'cases/{cid}/{name}.jpg' for name in ['perspective_contact','overlays_contact','mesh_contact']]]:
   assert p.is_file() and p.stat().st_size>0
   evidence.append(dict(case_id=cid,image_id=r['image_id'],path=p.relative_to(O).as_posix(),sha256=sha(p),role='source_and_reproducible_preview_evidence',visual_record='auxiliary_observation_record_not_CI_generated_judgement'))
  assert all(r[x] is None for x in ['final_scope_decision','final_ambiguity_decision','reference_correctness_decision'])
 m.save('review/evidence_manifest.csv',evidence)
 orders=[]
 for r in logs.to_dict('records'):
  cid=r['case_id'];v=r['variant'];base=O/f'cases/{cid}/{v}';g=m.js(base/'preview_geometry.json');raw=m.js(base/'raw_points.json')
  assert not g['coordinates_changed'] and not g['corner_adjacency_changed'] and not g['cycle_reversed'] and not g['cyclic_origin_changed']
  entry=dict(case_id=cid,variant=v,layout_key=g['layout_key'],source_point_numbering='original serialized rows, 1-based labels',role_map_zero_based=g['role_map'],role_swaps=g['endpoint_role_swaps'],coordinates_changed=False,adjacency_changed=False,cyclic_shift=False,reversal=False,reason='Interpret endpoint hemisphere inside each pre-existing pair; never re-pair or reorder the ring.',raw=f'cases/{cid}/{v}/raw_points.jpg',after=f'cases/{cid}/{v}/projected_overlay.jpg')
  if g['endpoint_role_swaps']:
   entry['before_after']=f'cases/{cid}/{v}/before_after_role_interpretation.jpg';assert (O/entry['before_after']).is_file()
  orders.append(entry)
 m.dump('rendering/point_order_interpretation_log.json',orders);m.save('rendering/selected_variant_checks.csv',logs)
 rawq=m.js(O/'ANALYSIS_QA.json');fq=m.js(O/'measurement/footprint_QA.json');cal=m.js(O/'rendering/numerical_calibration.json');cq=m.js(O/'EXTRA_QA.json')
 census=pd.read_csv(O/'census/images_380_final.csv',keep_default_na=False);selected=pd.read_csv(O/'census/selection_12.csv',keep_default_na=False)
 census['auxiliary_visual_review_completed']=census.image_id.isin(selected.image_id);m.save('census/images_380_review_status.csv',census)
 pop=census.groupby('population_role').agg(images=('image_id','size'),buildings=('building_id','nunique'),canonical_rows=('historical_rows','sum'),human30=('human30_id',lambda x:(x!='').sum()),AI50=('ai50_id',lambda x:(x!='').sum())).reset_index()
 eq=census.groupby(['population_role','head_equality_status']).size().reset_index(name='images');m.save('census/population_summary.csv',pop);m.save('census/head_equality_summary.csv',eq)
 assoc=pd.read_csv(O/'analysis/associations.csv');fa=pd.read_csv(O/'analysis/footprint_associations.csv');same=pd.read_csv(O/'analysis/exact_same_pairs_summary.csv');cov=pd.read_csv(O/'analysis/coverage_association.csv');nest=pd.read_csv(O/'analysis/head_nesting_diagnostic.csv')
 headline=assoc[(assoc.stratum=='all')&(assoc.y=='d_projected')&(assoc.scope.isin(['extended73','without_synthetic']))][['scope','contexts','buildings','spearman','ci_low','ci_high']]
 flo=fa[(fa.stratum=='all')&(fa.target=='d_human_floor')&(fa.scope.isin(['extended73','without_synthetic']))][['scope','n_contexts','n_buildings','spearman','ci_low','ci_high']]
 report=f'''# 不确定性接手分析与全景辅助视觉检查

输入版本：{PIN}。本轮为回顾性分析和辅助视觉检查，不确定论文方向，不替代人工裁决。

## 完成范围

已读取最新云端交接、字段说明与原有独立审查；离线验证380图输入包。主工作分区extended73，historical42及legacy213保留为有版本区别的对照；未重新聚类、未覆盖原始坐标、既有簇、人工30或AI50。原42中的raw-version-only成员保留原6053身份，不拿当前6052坐标替换。

实际视觉样本为12张、12个building：4张阅读/渲染校准，随后8张；7张历史、5张无历史响应候选。与人工30重合0张，与AI50重合4张。生成70个来源版本的原始点编号、投影叠图、局部透视、3D俯视与斜视。选中样本全部取得原图并完成辅助阅读；380是普查数，不是视觉已审数。

草稿串图描述已作废，详见review/DRAFT_CORRECTION_ZH.md。历史模型材料已经暴露，因此只声称本轮按原图优先的阅读顺序，不声称严格盲法。全部最终scope、歧义及参考正确性字段为空。

## 1. 先普查，后固定选样

{mdtable(pop)}

总building数：{census.building_id.nunique()}。实体房间ID已知数：{cq['room_instance_known']}。building和语义类别均未替代实体房间ID。

{mdtable(eq)}

原始双头坐标相同、允许环起点/环向后的相同、退化不可比较分别保留。双头相同不是无歧义真值。候选没有真人响应，真人分歧留空。

固定选样理由、既往重合和来源在census/selection_12.csv。样本覆盖同头/异头、真人分歧高/低及候选图，是探索性选择，不能估计总体歧义比例。

## 2. 测量检查

2501条canonical中，原邻接单值环向投影带可比较{rawq['raw_projectable']}条；原邻接有效地面轮廓可比较{fq['raw_usable']}条。两者适用条件不同，不可计算不等于标注错误或图像不适用；未将不可计算补零。

球面坐标采用u=2π(x/1024−1/2)，仰角=π(1/2−y/512)，Y向上，前方−Z。直的3D墙边在等距柱状全景中可以是曲线。单值投影带使用原点相邻关系和直边的球面投影；另保留同支持的线性代理和球面面积权重敏感性。地面轮廓用相机高度1的共同相对尺度，不称为米或3D IoU。

共线插点、仅改变环起点、仅反转环向的数学检查见measurement/math_checks.json。语义Manhattan合规与几何可解析分开。

## 3. Bi差异与真人分歧：条件性联系，不是因果或歧义分类

投影带：

{mdtable(headline)}

原邻接地面轮廓：

{mdtable(flo)}

区间为500次building重采样，条件于历史人员；没有把跨图重复人员当成新人样本。逐阶段、条件、合成初始化敏感性及删一工人诊断均保存。不同指标的可计算支持不同，不能直接把两张表的差异全归于度量。

完全相同context及双人身份的比较：

{mdtable(same)}

可计算覆盖与模型差异的关系：

{mdtable(cov)}

这提示可计算性可能不是随机缺失，相关关系只能限于明确分母。已提供每图最少2/5/10响应和至少0/50%/80%覆盖的敏感性，不选择最有利指标作最终结论。

## 4. 已有簇与两头的关系

保留115份分区及2498条成员身份。用于展示的medoid只在已有簇的可计算成员内重新选择，另标为new display medoid，不能冒充归档已保存代表。报告原支持、可计算支持、实际响应ID、原簇状态和并列信息；没有新语义标签。

几何距离可出现一头较近、两头都近、两头都远或不可计算；0.025/0.05/0.1/0.2只是半径敏感性。模型头名称不保证两个几何形状嵌套；head_nesting_diagnostic.csv逐图保存包含关系，不能将它变成enclosed/extended语义裁决。旧簇本身已按几何相似构造，组内比组间更近不是独立的新发现。

## 5. 阅读、渲染与点序校准

全随机射线往返最大误差{cal['pixel_ray_roundtrip_max']:.3g}像素；纹理采样往返最大通道差{cal['texture_sample_roundtrip_max']}。8个方向的纹理网格用于检查朝向与接缝。每张实际图有4个90°局部透视，使用源图而非生成图像。

70个来源版本均保留原始坐标、编号和相邻点对；4个版本含上下角色交换解释。它只改变既有点对内的上/下语义读取，不改变点位、配对、角点邻接、环起点或环向。全部解释映射及调整前后图在rendering/point_order_interpretation_log.json。没有Manhattan拟合，也没有按美观修复。

3D顶点是原射线代理：地面Y=−1，上端点沿自身射线使用相配地面点水平距离。上端深度不是独立观测；非共面墙采用明确的固定三角化代理。天花板未强行拟合成平面。纹理来自同一张全景，不能当独立3D证据；各版本自动取景也不能用于屏幕面积比较。

本批70个来源版本均生成有效代理表面；0个下载失败、0个选中版本渲染失败。成功渲染不代表Manhattan、范围或参考正确。全数据的不可计算原因另列，未将它们谎称为已完成视觉检查。

## 6. 逐图观察

详见cases/CASE_CARDS.md或离线index.html。每项包含具体位置、证据截图、其他解释和待人工确认问题。重点包括V03近门框与卧室延伸、V07同头但浴缸/柜体遮挡、V04同头且镜面解释仍需判断、V10开放厨房起居区的非简单嵌套变化，以及V05相机处于床/洗浴过渡的范围与局部几何问题。

这些观察不能建立“真人簇=Bi两头”的一一对应。候选没有真人模式证据。范围违规、局部错点、规则执行差异与同规则下合理替代解释均待人工区分。

## 7. 接手工作的结论与边界

现有数据可以继续研究模型差异与真人分布的条件联系，但度量适用性、原邻接和人员/建筑依赖必须进入解释。不存在本轮已经验证的两类自然工人、疲劳参数或统一收敛人数。两倾向输出模拟与疲劳状态模拟保持分开；本轮不默认转向POMDP或新正式实验。

另更正前轮轨迹保存范围：400次最终模拟摘要存在，但完整迭代轨迹只保存2次示例、9行，不能写成全部400次完整轨迹。

## 8. 完整交付

普通CSV/JSON、全部来源坐标预览、点序日志、失败记录、代码、中文报告及ZIP一起提交。ZIP包含本次输出、所依赖的便携输入包和渲染几何源码，不含字体或模型权重。DELIVERY_MANIFEST.json记录逐文件SHA；ZIP CRC及成员SHA检查必须通过。Actions artifact仅作备份，不替代main上的普通文件。
'''
 (O/'REPORT_ZH.md').write_text(report,encoding='utf-8')
 style='<style>body{font:17px/1.65 sans-serif;max-width:1180px;margin:32px auto;padding:0 20px;color:#222}img{width:100%;height:auto}article{border-top:2px solid #aaa;margin:40px 0;padding-top:16px}summary{cursor:pointer;font-weight:bold}table{border-collapse:collapse}td,th{border:1px solid #bbb;padding:8px}code{overflow-wrap:anywhere}.note{background:#f2f2f2;padding:16px}</style>'
 page=['<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>全景辅助复查</title>'+style,'<h1>12张全景辅助视觉检查</h1><p class="note">先看原图，再展开来源与多视图。不是最终人工裁决；380张为普查，只有这12张完成辅助阅读。完整代码和逐项证据在ZIP及main普通文件中。</p><p><a href="REPORT_ZH.md">中文报告</a> · <a href="census/images_380_review_status.csv">380图清单</a> · <a href="rendering/point_order_interpretation_log.json">点序解释日志</a></p>']
 cards=['# 实际辅助视觉案例\n\n12张；探索性选样，不估计总体歧义比例。最终人工裁定均为空。\n']
 for r in records:
  cid=r['case_id'];card=[f'# {cid} · {r["image_id"]}',r['scene_observed'],f'历史响应：{r["historical_rows"]}。既往重合：{r["prior_review_overlap"]}。',f'![原图](../../originals/{cid}_original.jpg)']
  page.extend([f'<article id="{cid}"><h2>{cid}</h2><img src="originals/{cid}_original.jpg" alt="{cid} 无模型标签的原始全景"><details><summary>展开来源、局部透视与3D辅助观察</summary><p>{esc(r["image_id"])} · {esc(r["scene_observed"])}</p><p>历史响应 {r["historical_rows"]}；既往审核重合 {esc(r["prior_review_overlap"])}；最终裁定：待人工。</p>'])
  for fn,title in [('perspective_contact','源图局部透视'),('overlays_contact','带原点编号的来源叠图'),('mesh_contact','原始射线代理：俯视及斜视')]:
   page.append(f'<h3>{title}</h3><img loading="lazy" src="cases/{cid}/{fn}.jpg" alt="{cid} {title}">');card.append(f'## {title}\n![{title}]({fn}.jpg)')
  for o in r['observations']:
   page.append(f'<h3>{esc(o["dimension"])} · {esc(o["location"])}</h3><p>{esc(o["observation"])}</p><p>其他解释：{esc(o["alternatives"])}</p><p>待确认：{esc(o["manual_question"])}</p>');card.append(f'## {o["dimension"]} · {o["location"]}\n{o["observation"]}\n\n其他解释：{o["alternatives"]}\n\n待人工确认：{o["manual_question"]}')
  sources=m.js(O/f'cases/{cid}/source_layouts.json');page.append('<h3>实际来源与单版本预览</h3><ul>')
  for j,z in enumerate(sources,1):
   tag=f'L{j:02}';page.append(f'<li>{tag} {esc(z["name"])} · {esc(z["key"])} · <a href="cases/{cid}/{tag}/raw_points.json">原始坐标</a> · <a href="cases/{cid}/{tag}/top.jpg">俯视</a> · <a href="cases/{cid}/{tag}/oblique.jpg">斜视</a> · <a href="cases/{cid}/{tag}/preview_geometry.json">代理假设及映射</a></li>')
  page.append('</ul></details></article>');(O/f'cases/{cid}/CARD_ZH.md').write_text('\n\n'.join(card),encoding='utf-8');cards.append(f'- [{cid}：{r["scene_observed"]}]({cid}/CARD_ZH.md)')
 page.append('</html>');(O/'index.html').write_text('\n'.join(page),encoding='utf-8');(O/'cases/CASE_CARDS.md').write_text('\n'.join(cards),encoding='utf-8')
 (O/'README_ZH.md').write_text('# 交付入口\n\n[中文报告](REPORT_ZH.md) · [案例索引](cases/CASE_CARDS.md) · [离线页面](index.html)\n\n解压完整ZIP后打开analysis_results/visual_takeover_20260906_v1/index.html。GitHub可直接阅读Markdown、CSV、JSON。\n\n复现顺序：review_data.py；measure.py；footprint.py；extra_checks.py；render.py --phase calibration；render.py --phase expansion；deliver.py。原图按保存的image_id/URL取得并验证下载SHA。输入包的cloud_inputs.py validate只做离线数据验证，不等同视觉检查。\n',encoding='utf-8')
 (O/'code').mkdir(exist_ok=True)
 for p in S.glob('*.py'):shutil.copyfile(p,O/'code'/p.name)
 env=dict(python=sys.version,numpy=np.__version__,pandas=pd.__version__,scipy=scipy.__version__,shapely=shapely.__version__,opencv=cv2.__version__,Pillow=PIL.__version__,platform=platform.platform(),font_file_distributed=False)
 m.dump('SOFTWARE_ENVIRONMENT.json',env)
 qa=dict(input_commit=PIN,census_images=len(census),buildings=census.building_id.nunique(),selected_images=12,actual_auxiliary_visual_images=12,calibration_images=4,expansion_images=8,selected_source_variants=len(logs),selected_download_failures=0,selected_render_failures=0,layouts_with_role_interpretation=int((logs.endpoint_role_swaps>0).sum()),coordinates_changed=False,adjacency_changed=False,new_cluster_version=False,final_human_decisions_written=False,originals_sha_verified=True)
 m.dump('DELIVERY_QA.json',qa)
 files=[]
 for p in sorted(O.rglob('*')):
  if p.is_file() and '__pycache__' not in p.parts and p.name not in ['DELIVERY_MANIFEST.json','visual_takeover_20260906_v1.zip','visual_takeover_20260906_v1.zip.sha256']:files.append(dict(path=p.relative_to(O).as_posix(),bytes=p.stat().st_size,sha256=sha(p)))
 m.dump('DELIVERY_MANIFEST.json',dict(file_count=len(files),files=files,input_commit=PIN))
 zpath=O/'visual_takeover_20260906_v1.zip'
 with zipfile.ZipFile(zpath,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  include=[O/f['path'] for f in files]+[O/'DELIVERY_MANIFEST.json']+[p for p in P.rglob('*') if p.is_file() and '__pycache__' not in p.parts]+list(S.glob('*.py'))+[R/'tools/label_studio/panorama_studio/geometry.py']
  for p in include:z.write(p,p.relative_to(R).as_posix())
 with zipfile.ZipFile(zpath) as z:
  assert z.testzip() is None
  for f in files:assert hashlib.sha256(z.read((O/str(f['path'])).relative_to(R).as_posix())).hexdigest()==f['sha256']
 (O/'visual_takeover_20260906_v1.zip.sha256').write_text(sha(zpath)+'  '+zpath.name+'\n',encoding='utf-8');print(json.dumps(qa));print('FILES',len(files),'ZIP',zpath.stat().st_size,sha(zpath))
if __name__=='__main__':run()
