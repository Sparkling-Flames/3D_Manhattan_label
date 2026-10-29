"""Index only existing deliverables; use successful persistence receipts when present."""
from pathlib import Path
import csv,hashlib,json

W=Path(__file__).resolve().parents[1]
D=W/'deliverables'

def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()

def topic(name):
    for token,text in [
      ('阶段01','旧形成/选型流程、合法空间与来源'),('阶段02','45法冻结标签、历史特征和形成代码'),
      ('阶段03A','31其它准入目标的完整有限配比及端点'),('阶段03B','Manual完整有限配比；核心/分方法分布'),
      ('阶段03C','Semi自身粗细分类的完整有限配比'),('阶段03D','先完成的七法合法小池进入策略'),
      ('阶段04','45法原答相似性、同点数控制、图/楼结果'),('阶段05A','69,485广筛精确事件与端点标量'),
      ('阶段05B','45法7,356条件及固定块人数路径'),('阶段06','六张原图、完整原答、投票与融合机制'),
      ('阶段07A','更新主报告、采用表、人员名单、当前代码及主方向反例'),
      ('阶段07B','重点扩展、真实父类/Q基线、成员敏感性完整事件'),
      ('阶段07C','固定A规模、背景及大队直接AC完整事件'),
      ('阶段07D','父构成固定细分、慢小类、完整配比例、新主角色进入策略'),
      ('广筛端点','广筛142,270团队的去重完整几何分批'),('补充端点','实际新增几何增量及全部请求来源映射')]:
        if token in name:return text
    return '阶段结果与可追溯输入'

receipts={}
for p in sorted(D.glob('UPLOAD*_RESULT.json'),key=lambda x:x.stat().st_mtime):
    try:x=json.loads(p.read_text())
    except (ValueError,OSError):continue
    for r in x.get('results',[]):
        if r.get('status')=='succeeded' and r.get('library_file_id'):
            receipts[str(Path(r['local_path']).resolve())]=r

standalone=[
 '人员分类与构成不确定性_研究组织与比较清单_20261022.md',
 'REPRODUCE_AND_DATA_DICTIONARY_ZH.md',
 'stage01/OLD_FORMATION_AND_SELECTION_ZH.md','stage01/TARGET_SCOPE_AND_DIFFICULTY_ZH.md',
 'stage07_adoption/PERSONNEL_ROLES_AND_MEMBERS_ZH.md','stage07_adoption/PERSONNEL_ALL_MEMBERS.csv',
 'stage07_adoption/PERSONNEL_LOBO_LABELS_AND_SUPPORT.csv.gz',
 'stage07_adoption/EFFECTIVE_EXCHANGE_CONDITIONS.csv','stage07_adoption/ALL32_EXTENDED_CONDITIONS_COMPLETE.csv',
 'stage07_adoption/ALL45_METHOD_ADOPTION_DECISIONS.csv','stage07_adoption/METHODS_ADOPTION_RATIONALE_ZH.md',
 'stage07_adoption/RECOMMENDED_CONDITIONS_ALL_IMAGES.csv','stage07_adoption/RECOMMENDED_CONDITIONS_COUNTEREXAMPLES.csv',
 'stage07_adoption/MAIN_DIRECTION_COUNTEREXAMPLE_MECHANISM.md','stage07_adoption/MAIN_CONDITION_COMPARISON.png',
 'stage07_adoption/DIFFICULTY_ROLE_EFFECTS.png','stage07_adoption/main_direction_counterexample/S9_09_SCOPE_AND_HALF_VOTE_PATH.png',
 'classification/MAIN45_LABELS_ALL_LOBO.csv.gz','classification/OLD_V2_TO_CURRENT_V21_WORKER_LABEL_TRANSITIONS.csv.gz',
 'stage05/ALL7356_CONDITIONS_KEY_RESULTS.csv','stage06_cases/CASE_MECHANISMS_ZH.md',
 'analysis/scale_background_summary/README.md','analysis/fine_increment/README.md',
 'composition/OPPJOINT_K4_complete_configuration_cases/CASE_TABLES.md',
 'composition/OPPJOINT_K4_complete_configuration_cases/ALL_CONFIGURATIONS_Q_READABLE.csv',
 'composition/OPPJOINT_K4_complete_configuration_cases/ALL_CONFIGURATION_Q_DISTRIBUTIONS.png',
 'integration/PERSONNEL_MAIN_REPORT_UPDATE.patch'
]
files=[('archive',p) for p in sorted(D.glob('HOHONET_v21_*.zip'))]
files += [('standalone',W/s) for s in standalone if (W/s).is_file()]
rows=[]
for kind,p in files:
    r=receipts.get(str(p.resolve()),{});lid=r.get('library_file_id','')
    rows.append(dict(kind=kind,path=p.relative_to(W).as_posix(),filename=p.name,bytes=p.stat().st_size,sha256=sha(p),
        topic=topic(p.name) if kind=='archive' else p.parent.name,
        library_file_id=lid,download_url=f'https://chatgpt.com/library?file_id={lid}&account_id=personal' if lid else '',
        file_exists=True,persistence='independently_saved' if lid else 'included_in_phase_archive_or_pending_final_save'))
with (W/'DOWNLOAD_INDEX.csv').open('w',newline='',encoding='utf-8-sig') as f:
    wr=csv.DictWriter(f,fieldnames=list(rows[0]));wr.writeheader();wr.writerows(rows)

lines=['# v2.1人员分类与换类：统一交付索引','',
'实际读取 main `a476461d7ede8db95da43de4139e612c05e618bc`。底层v2.1；本索引只列当前实际存在的文件。正文已更新既有人员主报告，本轮没有推送GitHub或改动CURRENT。','',
'## 先取得这几个独立文件','',
'完整研究不要求先下载所有几何。先读主报告、采用条件、名单和全方法采用表；需要逐事件复算时再取相应数据包。','',
'|文件|用途|下载|','|---|---|---|']
meaning={
 standalone[0]:'既有主报告的本轮更新，含原过程、45法比较、主法、规模背景、配比与正反机制',
 'REPRODUCE_AND_DATA_DICTIONARY_ZH.md':'版本、键、分母、环境、实际代码与接回仓库方法',
 'stage07_adoption/EFFECTIVE_EXCHANGE_CONDITIONS.csv':'32个重点扩展格的平均量、支持、风险、时间和采用',
 'stage07_adoption/ALL45_METHOD_ADOPTION_DECISIONS.csv':'全部45法的发现和进入/未进入主文理由',
 'stage07_adoption/PERSONNEL_ALL_MEMBERS.csv':'62人ALL名单、三粗四细/结构类与历史机会',
 'stage07_adoption/PERSONNEL_LOBO_LABELS_AND_SUPPORT.csv.gz':'实际实验用22楼外折名单与支持',
 'stage07_adoption/RECOMMENDED_CONDITIONS_COUNTEREXAMPLES.csv':'新推荐条件的全部反向/无幅度优势/失败图',
 'stage07_adoption/MAIN_DIRECTION_COUNTEREXAMPLE_MECHANISM.md':'S9-09六个事件的既有范围裁定、7:5/6:6/5:7票数与连接'}
for r in rows:
    if r['path'] not in meaning:continue
    url=r['download_url'] or r['path']
    lines.append(f"|[{r['filename']}]({r['path']})|{meaning[r['path']]}|[独立文件]({url})|")
lines+=['','## 分主题完整研究包','','全部包以同一个研究根目录为基准，可叠加解压。原始几何只在广筛三批及新增delta包保存；配比包中的端点标量和本轮新ABC分别保留来源。','',
'|现存分包|MB|实际内容|下载|','|---|---:|---|---|']
for r in rows:
    if r['kind']!='archive':continue
    lines.append(f"|[{r['filename']}]({r['path']})|{r['bytes']/1e6:.2f}|{r['topic']}|[取得]({r['download_url'] or r['path']})|")
lines+=['','## 范围与重复使用怎样识别','','|研究部分|已完成范围|解释边界|','|---|---|---|',
'|候选|45法、64,170行ALL/LOBO标签；13新前向和4目标等权RFUSE实际形成|45不是全部算法穷举；旧3种XCOND没有冒充v2.1重拟|',
'|全局严格ABC|69,485事件、142,270去重队、7,356条件|小池全合法n/m；大池14个主要格，每格冻结抽样，不是全成员穷举|',
'|重点扩展|32条件、10,980事件、187图22楼|2组成员块和可达背景梯度；图/楼等权，不把重复端点当独立证据|',
'|整批换类执行|189,514不同团队、180,367新融合；89,660不同方法事件|90,436阶段登记含跨阶段复用；全部负向、失败保留|',
'|固定A规模|10,184关联、1,947路径；直接AC另1,966登记|共同四端点分解ΔC/ΔB/净；实际mmax与统一m分开|',
'|父内细分|13,544严格ABC，25子父关系|完整父类向量固定；主联合方向跨父类与真正细分不混|',
'|主目标有限配比|Manual231面板、213,444关联；Semi105面板、97,016端点|每面板12选6全部枚举；不等于每图全部35人子集|',
'|其它准入目标|31池231原答；8,940精确团队，6,481新融合|N≤10全n≥3；N11全11选5；更大池固定12选6；219,284理论队中210,344未覆盖|',
'|病例|阶段06六图，主方向另S9-09；原图/完整原答/票账/失败|只重放既有端点导出状态，不记为新的独立团队实验|',
'|策略|旧自然256与V3策略32保留；小目标新角色精确前缀另记|不把旧V3改名DSTRUCT/OPPJOINT；同最终池只看前中段|','',
'## 未完成或未纳入本轮主任务','','其它合法目标的正式人工难度最终采用仍单列；目标可计算结构条件及目标感知历史已经完成。旧3种XCOND没有本轮新版标签；Semi主要完成自身分类配比及小池补充，没有新增全面大块ABC。全35人池的所有成员/顺序没有穷尽。以上均不妨碍本轮有明确支持的主分类与替换条件收尾。','',
'## 原始来源和恢复','','逐文件精确大小、SHA256、已取得的独立下载地址在 [DOWNLOAD_INDEX.csv](DOWNLOAD_INDEX.csv)。每个大包另有实际源文件清单与事件—端点覆盖回执；索引不列临时文件、空占位或只在作者说明中出现的旧产物。','',
'包内索引是打包当时快照；外置DOWNLOAD_INDEX包含核心包自身的最终大小/SHA。代码与研究报告保留产生阶段，较旧阶段的“在进行”描述由本轮顶部完成表接续，不改写为它在当时就已完成。','']
(W/'DELIVERY_INDEX.md').write_text('\n'.join(lines))
print(json.dumps({'archives':sum(x['kind']=='archive' for x in rows),'standalone':sum(x['kind']=='standalone' for x in rows),'indexed_files':len(rows),'saved_independently':sum(bool(x['library_file_id']) for x in rows)},ensure_ascii=False))
