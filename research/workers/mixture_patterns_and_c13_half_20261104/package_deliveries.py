"""Create repository-relative, numbered delivery overlays."""
from pathlib import Path
import hashlib,json,zipfile
BASE=Path(__file__).resolve().parent
REPO=BASE.parents[2]
DEST=REPO.parent/'deliverables';DEST.mkdir(exist_ok=True)
def allowed(p):return p.is_file() and '__pycache__' not in p.parts and p.suffix not in ['.log','.pyc','.writing','.tmp','.part'] and not p.name.startswith('.')
first=[p for sub in ['mixtures','curves'] for p in (BASE/sub).rglob('*') if allowed(p)]
second=[p for p in BASE.rglob('*') if allowed(p) and p.relative_to(BASE).parts[0] not in ['mixtures','curves']]
second += [REPO/p for p in json.loads((BASE/'audit/UPDATED_PROJECT_ENTRIES.json').read_text())]
check=json.loads((BASE/'DELIVERY_CHECKS.json').read_text());assert check['status']=='passed'
result=[]
for number,name,files in [
(11,'HOHONET_v21_batch11_mixture_patterns_and_convergence_20261104.zip',first),
(12,'HOHONET_v21_batch12_C13_half_and_integrated_workbench_20261104.zip',second)]:
 files=sorted(set(p.resolve() for p in files));manifest=[]
 for p in files:
  b=p.read_bytes();manifest.append({'path':str(p.relative_to(REPO)).replace('\\','/'),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()})
 note=f'''# HOHONET v2.1 第 {number} 批

日期：2026-11-04。按ZIP内部仓库相对路径解压至 D:/Work/HOHONET。第11批为既有混合规律与进入过程，第12批为新增C1↔C3 50%严格ABC、整合报告、离线研究台与入口更新。请先11后12安装，原自动实验与第08–10批图册保持。

第11批可先阅读 research/workers/mixture_patterns_and_c13_half_20261104/mixtures/REPORT_ZH.html 和 curves/REPORT_ZH.html。两批安装后打开 research/workers/mixture_patterns_and_c13_half_20261104/workbench/index.html 或 REPORT_ZH.html。无需网络或重新计算即可阅读。

新增团队只用于已授权的C1↔C3缺口。现有分类、有效预处理、原答、参考与原自动结果保留；旧人工顺序只精确复用，缺失Q不记0。K4小池两个实际辅助端点已经接续。

本包是已有v2.1仓库与前面批次的增量，不包含整个原仓库或406MB既有自然输入。源文件版本、恢复说明、统计口径和验收见专题SOURCE_AND_REPRODUCTION、README及各项来源清单。

本包 {len(files)} 个仓库文件，另附本说明和文件清单。覆盖的7个入口只在第12批；其余原始端点与实验文件未被覆盖。
'''
 target=DEST/name
 with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as z:
  for r,p in zip(manifest,files):z.write(p,r['path'])
  z.writestr(f'INSTALL_BATCH{number}.md',note)
  z.writestr(f'MANIFEST_BATCH{number}.json',json.dumps({'batch':number,'source_commit':'48a2fc6aedd51cd701b1bce06c02bd3ef92ec75b','files':manifest},ensure_ascii=False,indent=2))
 with zipfile.ZipFile(target) as z:
  bad=z.testzip();assert bad is None,bad
  assert len(z.namelist())==len(files)+2
 data=target.read_bytes();record={'batch':number,'path':str(target),'bytes':len(data),'MiB':round(len(data)/1048576,2),'repository_files':len(files),'archive_entries':len(files)+2,'sha256':hashlib.sha256(data).hexdigest(),'zip_integrity':'passed'}
 result.append(record);print(json.dumps(record),flush=True)
(DEST/'BATCH11_12_DELIVERY_RECEIPT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
