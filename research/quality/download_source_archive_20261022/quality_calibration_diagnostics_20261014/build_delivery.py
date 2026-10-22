#!/usr/bin/env python3
"""Package actual logs and deterministic independent controls; never certify calibration."""
from pathlib import Path
import datetime, hashlib, json, os, shutil, subprocess, sys, tempfile, traceback, zipfile
root=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
logs=root/'logs';logs.mkdir(exist_ok=True)
# Retain exact first-submitted probe code before making a portable copy.
original=root/'startup_probe.py'
if original.exists() and not (root/'startup_probe_first_submitted.py').exists():
    shutil.copy2(original,root/'startup_probe_first_submitted.py')
if original.exists():
    txt=original.read_text()
    txt=txt.replace("SUPPORT=Path('/mnt/data/quality_execution_support_20261013(2).zip')", "SUPPORT=Path(sys.argv[1]) if len(sys.argv)>1 else (ROOT/'inputs/quality_execution_support_20261013.zip')\nRUNTIME=Path(os.environ.get('QUALITY_RUNTIME_ROOT',str(ROOT.parent)))")
    txt=txt.replace("Path('/mnt/data').iterdir()", "RUNTIME.iterdir()")
    txt=txt.replace("os.walk('/mnt/data')", "os.walk(RUNTIME)")
    txt=txt.replace("relative_to('/mnt/data')", "relative_to(RUNTIME)")
    original.write_text(txt)
inputs=root/'inputs';inputs.mkdir(exist_ok=True)
support=Path('/mnt/data/quality_execution_support_20261013(2).zip')
if support.exists():shutil.copy2(support,inputs/'quality_execution_support_20261013.zip')
validation={'status':'independent_diagnostic_only','run_time_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'main_pool_calibration_completed':False}
cmd=[sys.executable,str(root/'direction_mechanisms.py'),'--test','--output',str(root/'recomputed_synthetic_results')]
try:
    p=subprocess.run(cmd,capture_output=True,text=True,timeout=45)
    (logs/'independent_reproduction.log').write_text(p.stdout+'\nSTDERR:\n'+p.stderr)
    validation['independent_reproduction']={'argv':cmd,'returncode':p.returncode,'log':'logs/independent_reproduction.log','passed':p.returncode==0}
except Exception:
    (logs/'independent_reproduction.log').write_text(traceback.format_exc())
    validation['independent_reproduction']={'argv':cmd,'passed':False,'log':'logs/independent_reproduction.log'}
comparisons=[]
old=root/'synthetic_results';new=root/'recomputed_synthetic_results'
if old.exists() and new.exists():
    for p in sorted(new.glob('*')):
        q=old/p.name
        comparisons.append({'file':p.name,'first_exists':q.exists(),'first_sha256':sha(q) if q.exists() else None,'second_sha256':sha(p),'equal':q.exists() and sha(q)==sha(p)})
validation['independent_two_run_comparison']=comparisons
validation['independent_two_runs_byte_identical']=bool(comparisons) and all(r['equal'] for r in comparisons)
(root/'VALIDATION.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2))
startup={}
try:startup=json.loads((root/'startup_results.json').read_text())
except Exception:startup={'report_read_error':traceback.format_exc()}
ss={}
summary_path=new/'synthetic_summary.json'
if summary_path.exists() and validation['independent_reproduction']['passed']:
    ss=json.loads(summary_path.read_text())
(root/'NORMAL_STAGE_STATUS.json').write_text(json.dumps({'status':'NOT_FROZEN_NOT_CALIBRATED','expected_ordinary_manual':574,'expected_strata':[207,367],'expected_severe_manual':9,'validated_actual_counts':None,'working_version':None,'parameters':None,'reason':'No human/assistant-readable verified source execution chain, current loader/identity/reference verification, real-case score reproduction, or current 3D-IoU comparison was completed.'},ensure_ascii=False,indent=2))
(root/'DOORWAY_STAGE_STATUS.json').write_text(json.dumps({'status':'NOT_STARTED_NORMAL_STAGE_NOT_FROZEN','admitted_records':None,'rejected_records':None,'interpretation':'null means unreviewed, not no eligible data','parameters_changed':None,'normal_regression':None,'oos_used_for_tuning':False},ensure_ascii=False,indent=2))
(root/'synthetic_experiment_config.json').write_text(json.dumps({'scope':'synthetic_mechanism_diagnostics_only','deployable_working_parameters':False,'baseline_toy_score':'100 * floor_iou / (1 + (D_degrees / tau_degrees)^2)','toy_tau_degrees':8.0,'rhombus_theta_degrees':list(range(1,91)),'synthetic_bottom_camera_height':1.6,'synthetic_panorama_height_pixels':512,'normal_main_pool_used':False,'height_controls_110_used':False,'real_R03274_used':False,'current_repository_full_Q_used':False,'fourth_order_tail_reproduced':False},ensure_ascii=False,indent=2))
lines=['# 启动诊断与方向机制实验：未完成主池校准','',
'## 结论与交付边界','',
'本包不是574份普通manual与9份严重manual的校准完成包，不能据此推荐主Q工作参数。正常阶段未冻结，门洞阶段未启动，正式算法、GT、人员资格与融合算法均没有被本包修改。',
'本轮助手侧的工具调用没有提供可审阅的文本或图像返回。以下启动检查结果由实际执行的程序写入文件；它们与助手已经阅读、理解并核验源码不是同一件事。没有把回传问题解释为数据不存在，也没有以旧922份输入代替当前主池或3152份资料。','',
'## 1. 启动程序记录','',
'完整记录见 `startup_results.json`；每条外部命令的参数、目录、退出状态、日志路径均在其中。若进程被超时中断，状态可能停留在最后一次已保存步骤，不能把此状态视为启动全通过。','',
'```json',json.dumps({'support_zip':startup.get('support_zip'),'snapshot':startup.get('snapshot'),'remote_main_sha':startup.get('remote_main_sha'),'step_statuses':{k:v.get('status') for k,v in startup.get('steps',{}).items()},'probe_status':startup.get('status')},ensure_ascii=False,indent=2),'```','',
'`source_texts/` 只在仓库快照实际读取成功时包含相应材料。目录或文件未出现在本次快照，不等于其在远端或Library中不存在。模块导入与测试的结果保留在日志中；结构清单和测试通过均不自动证明574/9的身份、参考或当前loader语义正确。','',
'## 2. 独立方向实验的定义','',
'所有下述实验均由 `direction_mechanisms.py` 生成，与准备包底点控制、R03274真人作答和正式主Q区分。其参考是居中单位正方形；待测菱形由单位向量 (1,0)、(cosθ,sinθ) 构成，四条边恒为1。',
'对0<θ≤90°，面积交并比的闭式解为：',
'`I(θ) = sinθ × (1 − cosθ/4) / (1 + sinθ cosθ/4)`。',
'固定或自由共同轴且允许每条边自由归入两个正交方向族时，最小平均方向残差均为 `D = 0.5 min(θ,90°−θ)`。因四条边等长，长度加权与不加权相同。故这个反转不依赖边长变化，也不必依赖共同轴重新优化。',
'这里的打分消融仅为 `q_toy = 100 I / [1 + (D/8)²]`。没有读取并复现正式四次尾项的精确实现，也没有将此简式称为完整主Q。','']
if ss:
    a,b=ss['rhombus_45'],ss['rhombus_30']
    lines += ['## 3. 本包程序复算的数值','',
        f'θ=45°：I={a["floor_iou"]:.10f}，D={a["D_common_weighted"]:.10f}°，简式消融分数={a["toy_q_free_D_tau8"]:.10f}。',
        f'θ=30°：I={b["floor_iou"]:.10f}，D={b["D_common_weighted"]:.10f}°，简式消融分数={b["toy_q_free_D_tau8"]:.10f}。',
        f'两次独立运行的结果文件逐字节一致：{validation["independent_two_runs_byte_identical"]}。测试与第二次运行退出码：{validation["independent_reproduction"].get("returncode")}。',
        f'共运行{ss["counts"]["rhombus"]}个等边菱形控制、{ss["counts"]["independent_bottom"]}个另外构造的底点控制；其中可计算{ss["counts"]["independent_bottom_computed"]}个，不可评价{ss["counts"]["independent_bottom_not_evaluable"]}个。后者记录具体原因，未赋0分冒充有效结果。',
        '这些底点控制不是准备包控制，不能声称复现了用户给出的8→16像素、Q约9.39→16.86链条；逐例及逐边记录是独立机制探索。','',
        '## 4. 修正候选与负结果','',
        '候选一是仅放松方向项强度。网格结果见 `toy_direction_strength_sweep.csv`。这能消除某些简式控制反转，但只是减少错误测量的影响，并未修复“方向族塌缩”本身；真实方向错误会同时被宽容。因此该网格不用于选择主Q参数。',
        '候选二是在已知且可信的跨参考边对应下固定方向族。对本控制，残差变为 `(90°−θ)/2`，随变扁增加。代码对未确认的对应直接报错；缺点、多点或不同非冗余点数不会猜配对。其副作用是绝对参考方向也会处罚整体刚性旋转，而自由共同轴残差不会，可能与IoU重复计罚。',
        '候选三是参考条件下的有符号转角差，在本控制中试验 `max(D, mean_turn_error/2)`，避免简单相加重复处罚。这能针对本控制补充墙间结构，但并非可直接部署的通用结构项：真实停止点、对应歧义、不同分段及合法非正交边界仍需资格门控。',
        '反例检验显示：若合法非正交参考与作答完全相同，自身Manhattan方向D仍可能大于0，而参考转角差为0。因此直接对所有样本套用 `max(D,结构差)` 仍可错误处罚合法结构；本包不推荐该组合为工作版本。凹角采用有符号转角，禁止把270°凹角当成偏离90°的错误。共线冗余点会先规范化；长度加权方向对分段不变，不加权方向则不具备这一一般保证。','',
        '## 5. 单底点投影诊断的有限结果','',
        '独立控制固定原始方位角，只改一个底点的纵坐标，再由同一相机高度重建半径。设下视角v=π(y/H−1/2)，半径ρ=h/tan(v)，则 `dρ/dy = −hπ/(H sin²v)`。接近地平线时同一像素误差能造成更大的空间偏移；这是可直接推导的投影机制，不是已经核实的R03274归因。',
        '代码旁列逐方位角的底边像素差，包括平均值、95%分位数和采样最大值。连续射线与环形角度避免逐顶点数量相等的要求，并能检验接缝与共线冗余点；但只支持单一可见底边函数。遇到多重射线交点会限制评价，不会默默选取一个空间。最大值属于有限采样诊断，不宣称精确Hausdorff距离，也未加入主Q。',
        '本包没有R03274原图或其经过核实的几何，不能把合成控制解释为该题的视觉或几何核查；没有为R03274设置目标分数。','']
else:
    lines += ['## 3. 独立实验执行状态','', '复现程序未产生可确认成功的新结果。具体异常见 `logs/independent_reproduction.log`；本报告不引用可能存在的旧结果作为新实验。','']
lines += ['## 6. 未完成的明确项目','',
'574+9当前身份及参考核查、207/367分层、准备包底点控制的输入→几何→分项→总分复算、至少一份真人作答复算、3152当前loader、原图视觉核查、110份历史高度控制、T20/P04/L01/J02最新原话回接、正常样本方向反转频率、同资格现用3D IoU对照、按图及建筑集中度、原留出回归、门洞纳入名单及细调，均未由本包完成。',
'本包中的等高棱柱3D IoU只是在共同高度区间下与底面IoU相等的合成对照，不是执行了仓库现用3D IoU。来源受限历史案例没有混入manual主池；OOS没有参与调参。','',
'## 7. 是否推荐工作版本','',
'不能推荐经本轮校准的工作版本，具体原因是当前主池执行与参考链尚未获得可审阅核验，非“参数不唯一”或泛称证据不足。正式版本应保持未修改状态；这不等于确认其当前参数合适。',
'本轮可支持的机制判断限于：方向族自由归属可造成结构塌缩时D反而降低；应先修复或限定方向/结构测量，再研究惩罚强度。不能据此声称该问题在真人主池普遍、已改善R03274、已满足高度意见，或某候选全面优于3D IoU。',
'下一步的最小阻塞是恢复工具的可审阅源码、运行结果与图像返回；随后利用现存574+9准备材料执行正常阶段，不需要先新增人工复审。','',
'## 8. 复现','',
'仅复现独立机制实验（仅需Python标准库）：','',
'```bash','python direction_mechanisms.py --test --output reproduced_synthetic','```','',
'重做启动诊断（需要git、网络及仓库读取权限；相关依赖需要numpy、scipy、shapely、pytest）：','',
'```bash','python startup_probe.py inputs/quality_execution_support_20261013.zip','```','',
'注意：启动程序的git回退使用公开HTTPS；若仓库需要认证而本地未配置凭据，它会保存实际git错误并退到support-only检查，不会将该检查称为当前仓库全量核验。`startup_probe_first_submitted.py` 保存本轮最初提交执行的原始脚本；便携版只调整输入与运行目录获取，不把便携版当成另一份已运行证据。','',
'完整文件清单为MANIFEST.json。ZIP的逐项解压及哈希复验回执在压缩包旁的 `.verification.json`。文件完整性通过与算法校准完成是两种不同结论。','']
(root/'REPORT_ZH.md').write_text('\n'.join(lines),encoding='utf-8')
(root/'README.md').write_text('# 启动诊断与方向机制实验\n\n**未完成574+9主池校准，不包含可部署工作参数。**\n\n先读 REPORT_ZH.md，再读 startup_results.json、VALIDATION.json、NORMAL_STAGE_STATUS.json、DOORWAY_STAGE_STATUS.json。\n\n复现独立实验：`python direction_mechanisms.py --test --output reproduced_synthetic`。\n\n所有合成结果均不能替代准备包、真实manual、110份高度控制或现用3D IoU。\n',encoding='utf-8')
(root/'PROVENANCE.md').write_text('''# 来源与证据层级

1. 用户提供的补充ZIP：原样保留在inputs/，大小与SHA256记录在startup_results.json；验证失败时不会恢复其内容。
2. 远端仓库：仅以git命令实际观察到的提交与退出状态记录。无法获取时不推断文件不存在。
3. 当前研究入口：source_texts/中若有文件，它们是本次程序读取成功的快照，不代表助手完成了语义审核。
4. 合成控制：direction_mechanisms.py独立生成；没有使用任何人工分数标签、OOS或历史922输入来冒充当前主池。
5. 数学公式为本包明示定义与推导。外部搜索结果未获得可核查返回，因此没有伪造论文、作者、页码或引用链接。
6. 旧报告的数值只作为用户任务说明，不计入本包新运行证据；正式四次尾项和完整Q未复算。
7. 工具反馈受阻使助手不能逐项审阅机器日志。本包机器验证结果必须与研究者已复核的结论区分。
''',encoding='utf-8')
# Ensure all code ships, but do not ship a whole unreviewed clone or installed support tree.
excluded={'repository_snapshot','support_only_root','__pycache__','.git','.pytest_cache'}
payload=[]
for base,dirs,files in os.walk(root):
    dirs[:]=sorted(d for d in dirs if d not in excluded)
    for fn in sorted(files):
        p=Path(base)/fn;rel=p.relative_to(root)
        if fn in ['MANIFEST.json','delivery_console.log'] or fn.endswith('.pyc'):continue
        payload.append({'path':str(rel),'bytes':p.stat().st_size,'sha256':sha(p)})
(root/'MANIFEST.json').write_text(json.dumps({'scope':'payload_files_excluding_manifest_and_external_zip_receipt','files':payload},ensure_ascii=False,indent=2))
archive=root.parent/'quality_calibration_diagnostics_20261014.zip'
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for entry in payload:z.write(root/entry['path'],arcname=entry['path'])
    z.write(root/'MANIFEST.json',arcname='MANIFEST.json')
with zipfile.ZipFile(archive) as z:
    bad=z.testzip()
    assert bad is None, f'ZIP CRC failure: {bad}'
    with tempfile.TemporaryDirectory(prefix='quality_delivery_verify_') as tmp:
        z.extractall(tmp)
        for entry in payload:
            p=Path(tmp)/entry['path'];assert p.is_file(),entry['path'];assert p.stat().st_size==entry['bytes'],entry['path'];assert sha(p)==entry['sha256'],entry['path']
receipt={'archive':archive.name,'bytes':archive.stat().st_size,'sha256':sha(archive),'files_in_zip':len(payload)+1,'crc_passed':True,'full_extract_and_payload_hash_check_passed':True,'research_calibration_completed':False,'independent_reproduction_passed':validation['independent_reproduction']['passed']}
receipt_path=archive.with_suffix('.verification.json');receipt_path.write_text(json.dumps(receipt,ensure_ascii=False,indent=2))
assert archive.exists() and receipt_path.exists() and (root/'REPORT_ZH.md').exists()
print(json.dumps(receipt,ensure_ascii=False,indent=2))
print(str(root/'REPORT_ZH.md'))
