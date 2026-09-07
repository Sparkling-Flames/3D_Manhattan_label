"""Package the actual state, never upgrade unviewed renders to completed reviews."""
from pathlib import Path
import json,hashlib,zipfile,html,shutil,subprocess,sys
import pandas as pd
ROOT=Path(__file__).resolve().parents[1];O=ROOT/'review_results';P=ROOT/'analysis_results/uncertainty_cloud_inputs_20260906_v1';O.mkdir(parents=True,exist_ok=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def table(name,cols=None):
 p=O/name
 if not p.exists():return '**该阶段未产出结果。参见运行日志；不计完成。**'
 d=pd.read_csv(p)
 if cols:d=d[cols]
 return d.to_markdown(index=False,floatfmt='.5f')
q=json.loads((O/'ANALYSIS_QA.json').read_text()) if (O/'ANALYSIS_QA.json').exists() else {}
r=json.loads((O/'RENDER_STATUS.json').read_text()) if (O/'RENDER_STATUS.json').exists() else {}
status={'source_commit':'29f628fd5a9c4d3e2064ffffec32bbffb324776c','numerical_audit_finished':bool(q),'render_preparation_finished':bool(r),'actual_visual_reviews_completed':0,'visual_calibration_approved':False,'expansion_started':False,'new_results_pushed_to_main':False,'github_write_status':'create_file call blocked by tool; no successful replacement route claimed','not_a_final_thesis_direction':True}
(O/'DELIVERY_STATUS.json').write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding='utf-8')
for n in ['audit_run.log','render_run.log']:
 if (ROOT/n).exists():shutil.copy2(ROOT/n,O/n)
(O/'download_failures.csv').write_text('image_id,status,reason\n2t7WUuJeko7_3be66dc4f0fb46449d63b07d92c74f3f,not_verified,Direct image download attempt did not produce verified usable bytes; no other image is declared downloaded by inference\n')
# Source validator is safe, offline and independent of GPU or remote assets.
if (P/'cloud_inputs.py').exists():
 p=subprocess.run([sys.executable,'-I','-S',str(P/'cloud_inputs.py'),'validate','--package',str(P)],capture_output=True,text=True,timeout=60)
 (O/'offline_validation.log').write_text(p.stdout+'\nSTDERR:\n'+p.stderr);status['offline_validation_exit']=p.returncode
(O/'DELIVERY_STATUS.json').write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding='utf-8')
report='''# 接手分析与视觉校准准备：实际完成状态

本目录对应源提交 `29f628fd5a9c4d3e2064ffffec32bbffb324776c`。它不是完整视觉审查的完成报告。

**GitHub新结果写入未成功；实际完成视觉审查为0张。生成预览不计审查，渲染校准未批准，扩展审查未启动。**

## 1. 接手任务及口径

依据输入包的 README、FIELDS 和 CLOUD_HANDOFF：先核查测量，保留原始序列，再连接已有extended73簇；historical42与legacy213均不覆盖。保留26名历史人员；当前20人只作资源属性。Bi双头不自动等于两类工人、两种合法解或疲劳状态。没有修改论文方向、原始标注、参考或人工30张判断。

输入包离线验证日志：`offline_validation.log`。本轮代码读取的是已发布的可移植原始坐标及来源包，而不是声称又从仓库外原始导出文件逐个重建了全部历史记录。文件哈希在 `census/input_hashes.csv`。

## 2. 本轮程序实际完成的数量

'''
report+='```json\n'+json.dumps(q or {'status':'numerical_stage_not_completed'},ensure_ascii=False,indent=2)+'\n```\n'
report+='''
## 3. 测量定义、假设及不可计算情形

主对照是**原邻接关系地面轮廓1-IoU**：按全景射线与Y=-1平面求交，比较地面多边形。相机高度只是统一的相对尺度；不是米、3D IoU、围护范围正确性或Manhattan合法性。原序自交、相机外部、端点无法配对等情况明确不可计算，不按x排序修复。

辅助对照是单值环向边界域上的球面投影墙面带及其固体角加权版本。同一物理直墙的展开边界可以弯曲。凹形或非星形轮廓不一定能进入单值墙面带，因此其不可计算不是标注错误。每个距离单列分母。

线性对照使用同一原邻接关系、同一可计算集合的线性插值，明确命名 `linear_common`，不是冒称复现可能使用不同点序/归一化的所有旧距离表。合成共线点插入、起点改变和环向反转的检查在 `measurement/math_checks.json`。

上下端点只在**原有相邻点对**中按半球确定角色。该操作保存原点编号映射，不移动坐标，不改变点对成员或角点邻接。无法形成跨地平线点对时阻断。完整角色和失败日志见 `measurement/layout_audit.csv`。

## 4. 380图普查与连续关系

`census/images_380.csv`逐图保留来源、building、响应/人员/context数量、模型与参考可用性、两份簇版本，以及human30和AI50覆盖。候选图的人类分歧为缺失，不置零。房间实例ID缺失不由building或语义类别填补。

`analysis/associations.csv`保留全部指标、阶段和条件分层，以及剔除合成trap后的敏感性。建筑重采样区间条件于这批历史人员；不是新人总体置信区间。`analysis/worker_sensitivity.csv`另做逐一去工人敏感性，不冒称联合交叉bootstrap。

'''
f=O/'analysis/associations.csv'
if f.exists():
 d=pd.read_csv(f);d=d[(d.scope.isin(['extended73','without_synthetic']))&(d.stratum=='all')];report+=d[['scope','x','y','contexts','buildings','rho','ci_low','ci_high','building_mean_rho']].to_markdown(index=False,floatfmt='.5f')+'\n'
report+='''
这些是探索性关联，不是已确认的场景歧义标签、因果机制或已验证的新图预测。不同度量和不同可计算集合的差异应同时解读，不挑一个最好看的数字。

## 5. 旧簇与Bi输出

原始115份分区的成员数与映射核对在 `analysis/membership_checks.csv`。raw-version-only成员仍保留原版本，未以canonical6052顶替旧6053。主工作关联只使用extended73。

`analysis/clusters_to_bi.csv`中的代表响应是**在原簇现有可计算成员中重新选取的显示medoid**，不是上游保存的旧代表；ID、支持数、缺失和原簇状态全部列出。没有重新聚类。距离亲近不等于enclosed/extended语义。探索半径0.05/0.1/0.2不是质量线，允许两头都近或两头都远。

'''+table('analysis/template_coverage.csv')+'''

## 6. 模拟可行性：现在保留什么，不推断什么

可以利用实际簇成员和实际双头坐标做条件亲近度与覆盖分析。若进一步以两头为模拟模板，至少需要核实：在留出图像上是否覆盖人类主要模式、同一规则下是否成立、不能覆盖的残差是什么，以及人员混合权重是否具有独立依据。

当前模板亲近度不自动提供“真人选择某头的概率”；样本重组不等于新增真人。所有疲劳转移概率、同人状态变化和学习速率仍缺乏必要的时序/重复识别证据，本轮未填入假定值冒充经验参数。

## 7. 视觉部分只完成准备，不声称已经审图

'''
report+='```json\n'+json.dumps(r or {'status':'render_preparation_not_completed'},ensure_ascii=False,indent=2)+'\n```\n'
report+='''
图像直接下载未获得可核验字节。校准准备仅可使用已固定的panorama_studio_v2内嵌原图，不称其为本轮新下载；来源及SHA在 `census/available_image_assets.csv`。可得性限制改变了探索样本支持，不能用于总体比例推断；不能声称166候选图已获视觉覆盖。

选择发生在380图统计之后，理由、building及既往审查重合在 `selection.csv`。原始全景优先排在页面顶部；编号叠图、四方向80度局部透视、俯视和斜视只是待检查证据。未完成实际盲读，所有观察字段留空，不根据统计异常编造图像原因。没有扩展到其余图片。

### 渲染假设

1024×512连续像素坐标，不另加半像素。Y向上，相机原点，地面Y=-1。上端点使用其自身射线及所配地面端点的水平距离，这是代理，不是观测深度；非共面墙显示为两三角形代理。原邻接无自交才填充网格；无效输入保留来源和失败，不自动规整。没有Manhattan拟合、环向反转、起点调整、邻接重排或原坐标覆盖。

纹理来自同一全景的回投影，并非额外视角的独立验证；房间家具遮挡也会被投到代理表面。3D视图仅用于诊断，不用于判定真实墙面材质或物理尺度。每个版本自动取景，不宜直接用显示大小推断面积变化。

数值投影往返误差和端点角色映射在 `point_order_and_render_log.csv`。它不能代替尚未进行的接缝、朝向、纹理和图像语义的实际视觉校准。渲染失败和未查看都不计完成。

## 8. 交付与复现

包内 `review_code/` 是可运行源文件，`review_results/` 是实际生成结果，`analysis_results/uncertainty_cloud_inputs_20260906_v1/` 是固定输入副本。原型内嵌图在 `available_images/`；不含字体文件或模型权重。

安装requirements后，在解压目录执行：

```bash
python review_code/audit.py
python review_code/prepare_calibration.py
```

渲染器需要固定原型图像来源；本包同时保留其来源引用及已解码字节。包内同时保存固定原型的data.js及image_*.js，校准准备脚本可以重新解码并重现；不会把缺失素材伪装为成功。

**尚未完成：main上传、实际3—5图视觉校准、逐图观察、扩展视觉检查。** 本交付物不替代这些未完成环节。
'''
(O/'REPORT_ZH.md').write_text(report,encoding='utf-8')
# Render-only gallery, no fabricated annotations or review approval.
css='body{font-family:system-ui,sans-serif;margin:32px;max-width:1280px;color:#222}img{max-width:100%;height:auto}details{margin:20px 0;border:1px solid #aaa;padding:12px}code{overflow-wrap:anywhere}.warning{background:#fff2db;padding:16px}'
body='<h1>全景校准证据：生成但未完成视觉审查</h1><p class="warning">实际完成视觉审查：0张。先查看原图，再展开模型/参考；不得将生成文件数计为审查数。</p>'
for case in sorted((O/'cases').glob('*')) if (O/'cases').exists() else []:
 if not case.is_dir():continue
 body+='<h2>'+html.escape(case.name)+'</h2>'
 for n in ['01_original_blind.jpg','02_perspectives.jpg']:
  if (case/n).exists():body+=f'<h3>{n}</h3><img loading="lazy" src="cases/{case.name}/{n}">'
 for f in sorted(case.glob('*_evidence.jpg')):
  body+=f'<details><summary>{html.escape(f.stem)} — 待查看</summary><img loading="lazy" src="cases/{case.name}/{f.name}"></details>'
 body+='<p>边界可见性、遮挡、门洞/范围、局部角点、规则执行、参考疑点：未进行本轮实际视觉判断，均留空。</p>'
(O/'index.html').write_text('<!doctype html><html lang="zh"><meta charset="utf-8"><title>校准准备</title><style>'+css+'</style>'+body,encoding='utf-8')
(ROOT/'requirements.txt').write_text('numpy\npandas\nscipy\nshapely>=2\nPillow>=10.1\ntabulate\n')
# Transparent ledger includes only files actually present. No private keys, font files or code caches.
files=[]
for folder in [ROOT/'review_code',O,P,ROOT/'available_images']:
 if folder.exists():
  for f in sorted(folder.rglob('*')):
   if f.is_file() and '__pycache__' not in f.parts and f.suffix not in ['.ttf','.otf','.woff','.woff2'] and f.name!='DELIVERY_MANIFEST.json':files.append(f)
studio = ROOT/'analysis_results/panorama_studio_20260906_v2'
if studio.exists():
 for f in [studio/'data.js', *sorted(studio.glob('image_*.js'))]:
  if f.is_file(): files.append(f)
files.append(ROOT/'requirements.txt')
manifest={'status':status,'files':[{'path':str(f.relative_to(ROOT)),'bytes':f.stat().st_size,'sha256':sha(f)} for f in files]}
mp=O/'DELIVERY_MANIFEST.json';mp.write_text(json.dumps(manifest,ensure_ascii=False,indent=2));files.append(mp)
archive=Path('/mnt/data/uncertainty_handoff_calibration_workpackage_20260906.zip')
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for f in files:z.write(f,str(f.relative_to(ROOT)))
with zipfile.ZipFile(archive) as z:
 assert z.testzip() is None
 for r in manifest['files']:assert hashlib.sha256(z.read(r['path'])).hexdigest()==r['sha256']
shutil.copy2(O/'REPORT_ZH.md','/mnt/data/uncertainty_handoff_status_20260906.md')
Path(str(archive)+'.sha256').write_text(sha(archive)+'  '+archive.name+'\n')
print(json.dumps({'archive':str(archive),'bytes':archive.stat().st_size,'sha256':sha(archive),'status':status},ensure_ascii=False,indent=2))
