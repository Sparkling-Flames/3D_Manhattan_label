"""Index only files that actually exist; Library ids come only from successful receipts."""
from pathlib import Path
import csv, hashlib, json

ROOT=Path(__file__).resolve().parent
D=ROOT/'deliverables'
ids={}
for p in sorted(D.glob('UPLOAD_*_RESULT.json'),key=lambda p:p.stat().st_mtime):
    try:r=json.loads(p.read_text())
    except (ValueError,OSError):continue
    for x in r.get('results',[]):
        if x.get('status')=='succeeded':ids[x['local_path']]=x

chosen=[ROOT/'final/人员分类与构成不确定性_主报告_更新至20261025.md',
 ROOT/'final/20261025_新增分类与有效换类章节.md',ROOT/'final/有效换类条件_20261025.csv',
 ROOT/'analysis/FINAL_CONDITIONS_COMPACT.csv',ROOT/'analysis/METHOD_ADOPTION_DECISIONS.csv',
 ROOT/'final/LABELS_ALL.csv',ROOT/'final/LABELS_LOBO.csv.gz',ROOT/'final/ALL_EVENTS_EXACT.csv.gz',
 ROOT/'final/UNIQUE_ENDPOINT_INVENTORY.csv.gz',ROOT/'analysis/figures/CONFIRM_Q_SEPARATION.png',
 ROOT/'cases_size_threshold/SIZE_THRESHOLD_MECHANISM_ZH.png']
chosen+=sorted(D.glob('*.zip'))
rows=[]
for p in chosen:
    if not p.exists():continue
    receipt=ids.get(str(p),{})
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(2**20),b''):h.update(b)
    rows.append({'file':str(p.relative_to(ROOT)),'bytes':p.stat().st_size,'sha256':h.hexdigest(),
                 'library_file_id':receipt.get('library_file_id',''),
                 'saved_status':receipt.get('status','local_file_present'),
                 'library_version':receipt.get('current_version_number','')})
with (ROOT/'DOWNLOAD_INDEX.csv').open('w',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)

out=['# HOHONET 本轮最终下载索引','',
'实际读取最新 main：`e88d1d443f4000715a50475e085a773661be9c04`；计算版本：`972857b2b3f548316be215400e42d6ef6e639250`；底层数据真人v2。',
'','本表只登记实际存在的文件。最终主报告沿用仓库原主报告更新；没有向GitHub推送。各阶段标签、请求和结果保持原身份。',
'','## 推荐阅读顺序','',
'先看完整主报告或本轮新增章节，再看四个主要换类条件及71行完整条件表；人员名单与精确事件可以单独下载。后续需要图像、票账、几何或再聚合时，再取相应分包。',
'','## 可单独取得的文件与各阶段分包','',
'|文件|大小 MiB|下载|','|---|---:|---|']
for r in rows:
    p=ROOT/r['file'];lid=r['library_file_id']
    link=f'[下载](https://chatgpt.com/library?file_id={lid}&account_id=personal)' if lid else f'[本地文件]({r["file"]})'
    out.append(f'|{p.name}|{r["bytes"]/2**20:.2f}|{link}|')
out += ['',
'精确字节数、SHA256及保存身份见 [DOWNLOAD_INDEX.csv](DOWNLOAD_INDEX.csv)。同名阶段01已经修复并替换为同一下载项的新版本：原67项中66项精确恢复，唯一未取得原字节的是首轮注册脚本，使用早期阶段02版本且已记录；标签、请求和事件没有改变。',
'','## 分包职责与解压位置','',
'- **06A**：最终主报告、全部标签／历史中心、比较表、必要小输入与实际代码。直接解压到仓库根目录，研究文件进入 `research/workers/personnel_exchange_discrimination_20261025/`，主报告进入 `docs/thesis_main/`。更新主报告前可先审阅包内补丁。',
'- **06C**：97,552事件、事件—端点关联及283,211去重端点库存。也解压到仓库根目录，保留其规范研究目录前缀。',
'- **01—05及06B**：压缩包内部路径从研究目录开始，解压到上述 `personnel_exchange_discrimination_20261025/` 目录。为避免旧脚本覆盖最终版本，依次解压01—05、06B，最后解压06A和06C。',
'- **02A／04A1／04A2／05**含完整逐事件指标；**02B／04B／04C／05**含各批端点标量和几何。最终库存逐端点指向真实批次，重复团队只需保留一个端点。',
'- **02C**是前四例；**06B**是新增反推小类与人数门槛反转两例。没有打包原图全集，仅保留机制案例所需原图与几何。',
'',
'本轮97,552事件包括95,264严格ABC与2,288直接AC，覆盖170张普通Manual图、22栋楼。283,211去重端点中283,092新计算、119直接复用；记录为失败／不可评分的4,198端点仍在完整账中。',
'',
'完整字段和恢复步骤见 [DATA_DICTIONARY.md](DATA_DICTIONARY.md)、[REPRODUCTION.md](REPRODUCTION.md)。不需要重新融合才能重聚合已保存结果。',
'',
'## 保存状态','',
'本独立索引是最后一批文件的下载入口。压缩包内的索引快照可能早于该包自身的保存，因而不列其自身下载身份；此处不会用计划文件冒充已经保存的文件。',
]
(ROOT/'DOWNLOAD_INDEX.md').write_text('\n'.join(out)+'\n')
print(json.dumps({'files':len(rows),'saved':sum(bool(r['library_file_id']) for r in rows),'bytes':sum(r['bytes'] for r in rows)},ensure_ascii=False))
