"""Finalize canonical reproducibility metadata after all result files are saved."""
from pathlib import Path
import csv,hashlib,json,shutil

ROOT=Path('/workspace/scratch/fe955c3c772c')
WORK=ROOT/'population_work'
OUT=ROOT/'HOHONET_population_latest/research/workers/personnel_population_curves_v2_20261023'
def valid(p):
    return p.is_file() and not any(x.startswith('.') or x=='__pycache__' for x in p.parts) and not p.name.endswith(('.tmp','.pyc','.log'))
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()
def manifest(folder,name='FILE_MANIFEST.csv'):
    p=folder/name
    rows=[{'path':str(f.relative_to(folder)),'bytes':f.stat().st_size,'sha256':sha(f)} for f in sorted(folder.rglob('*')) if valid(f) and f!=p]
    with p.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['path','bytes','sha256']);w.writeheader();w.writerows(rows)
    return rows

for p in (WORK/'code').glob('*.py'):shutil.copy2(p,OUT/'code'/p.name)
shutil.copy2(WORK/'code/RECIPE.md',OUT/'code/RESTORE_EVENT_WIDE_RECIPE.md')
shutil.copy2(WORK/'code/RESTORE_EVENT_WIDE_SMOKE_RECEIPT.json',OUT/'code/RESTORE_EVENT_WIDE_SMOKE_RECEIPT.json')
shutil.copy2(WORK/'report_link_check.json',OUT/'REPORT_LINK_CHECK.json')

p=OUT/'REPRODUCE.md';s=p.read_text()
anchor='## 由完整关系式事件恢复分析宽表\n'
addition='''
已经提供可直接运行的标准库恢复工具，无需复制下面的示例。详细命令见[恢复说明](code/RESTORE_EVENT_WIDE_RECIPE.md)，四种表前48行的列序、缺失与数值核对见[小样本恢复回执](code/RESTORE_EVENT_WIDE_SMOKE_RECEIPT.json)。它只恢复原列，不重算事件差值。

```bash
python code/restore_event_wide.py --root . --dataset policy_paired --out restored/POLICY_PAIRED_PREFIX_EVENTS.csv.gz
```

'''
if '已经提供可直接运行的标准库恢复工具' not in s:s=s.replace(anchor,anchor+addition)
p.write_text(s)
p=OUT/'events/README.md';s=p.read_text()
start=s.index('在完整本轮目录下运行：')
s=s[:start]+'''原整理脚本保留历史执行路径与源表身份。当前交付不再重复存放原宽表，直接接续请使用本目录完整关系表；需要宽表时运行：

```bash
python code/restore_event_wide.py --root . --dataset policy_paired --out restored/POLICY_PAIRED_PREFIX_EVENTS.csv.gz
```

上例当前目录为研究目录根部，完整说明见[恢复入口](../code/RESTORE_EVENT_WIDE_RECIPE.md)。四种关系表都支持恢复。原始列、行顺序、数值和缺失状态保留，事件差值不重新计算；额外的六个关联字段继续保留在LINKED表。
'''
p.write_text(s)

manifest(OUT/'events');manifest(OUT/'cases')
rows=manifest(OUT)
(WORK/'FINAL_FILE_COUNTS.json').write_text(json.dumps({'files':len(rows),'bytes':sum(x['bytes'] for x in rows),'manifest':str(OUT/'FILE_MANIFEST.csv')},indent=2))
print(json.dumps({'files':len(rows),'bytes':sum(x['bytes'] for x in rows)}))
