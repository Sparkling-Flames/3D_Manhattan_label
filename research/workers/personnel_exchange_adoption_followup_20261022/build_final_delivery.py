#!/usr/bin/env python3
"""Package completed results and map separately downloaded large files.

No scientific computation, network write or fusion. Existing historical
packages and full event/endpoint data remain separate, avoiding large duplicates.
"""
from pathlib import Path
import csv,hashlib,json,os,re,shutil,subprocess,zipfile

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[2]
OLD=ROOT.parent/'personnel_exchange_closure_20261022'
PACKAGE=ROOT/'packages/HOHONET_人员分类换类_本轮实质续研与采用_20261022.zip'

def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()

def build_download_map():
 rows=[]
 old=list(csv.DictReader((ROOT/'STAGE01_ACTUAL_FILES.csv').open(encoding='utf-8-sig')))
 for r in old:
  src=Path(r['source']);dst=Path(r['download_path'])
  rows.append(dict(download_filename=dst.name,repo_destination=str(src.relative_to(REPO)),
   bytes=dst.stat().st_size,sha256=sha(dst),stage='上一轮完整实存，本轮保存',role=r['role']))
 new=[('EVENTS_COMPLETE.csv.gz','HOHONET_新增背景梯度_完整事件1092.csv.gz','新背景完整ABC'),
      ('ENDPOINT_SCALARS.csv.gz','HOHONET_新增背景梯度_端点标量3276.csv.gz','新背景端点标量'),
      ('ENDPOINT_GEOMETRY.csv.gz','HOHONET_新增背景梯度_端点几何3276.csv.gz','新背景端点几何'),
      ('MATCHED_BACKGROUND_GRADIENT_PAIRS.csv.gz','HOHONET_新增背景梯度_精确配对1448.csv.gz','新背景六端点比较'),
      ('ANCHORS_EXACT.csv','HOHONET_新增背景梯度_精确XYZ78组.csv','冻结XYZ与剩余背景成员')]
 for source,name,role in new:
  src=ROOT/'structure_followup/background_gradient'/source;dst=ROOT/'deliverables'/name
  # Preserve any existing downloadable-file identity and update only its bytes.
  if not dst.exists():shutil.copyfile(src,dst)
  elif sha(src)!=sha(dst):shutil.copyfile(src,dst)
  rows.append(dict(download_filename=name,repo_destination=str(src.relative_to(REPO)),bytes=dst.stat().st_size,
                   sha256=sha(dst),stage='本轮新实验最终版',role=role))
 src=ROOT/'structure_followup/FIXED_A_PATHS_EXACT.csv.gz'
 dst=ROOT/'deliverables/HOHONET_固定A_替换规模路径.csv.gz'
 if not dst.exists() or sha(src)!=sha(dst):shutil.copyfile(src,dst)
 rows.append(dict(download_filename=dst.name,repo_destination=str(src.relative_to(REPO)),bytes=dst.stat().st_size,
                  sha256=sha(dst),stage='本轮共同分母分析',role='固定A全部规模路径'))
 with (ROOT/'DOWNLOAD_MAP.csv').open('w',newline='',encoding='utf-8-sig') as f:
  w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)

def render_report():
 report=ROOT/'人员分类与换类_采用结论与实质续研.md'
 html=report.with_suffix('.html')
 style=ROOT/'report_style.css'
 old_style=OLD/'delivery/report_style.css'
 if not style.exists():shutil.copyfile(old_style,style)
 subprocess.run(['pandoc',str(report),'-f','gfm','-t','html5','--standalone','--embed-resources',
  '--toc','--toc-depth=2','--metadata','lang=zh-CN','--metadata','title=HOHONET 人员分类与换类：采用结论与实质续研',
  '--css',str(style),'--resource-path',str(ROOT),'-o',str(html)],check=True)
 s=html.read_text()
 def links(m):
  u=m.group(1)
  if u.startswith(('#','http:','https:','data:','sandbox:')):return m.group(0)
  p=(ROOT/u).resolve()
  return 'href="sandbox:'+str(p)+'"' if p.exists() else m.group(0)
 html.write_text(re.sub(r'href="([^"]+)"',links,s))

def collect():
 files=set()
 for directory,manifest in [('manual_qt_followup','FILE_INDEX.csv'),('semi_followup','FILE_INDEX.csv'),('structure_followup','DELIVERY_FILES.csv')]:
  p=ROOT/directory
  for r in csv.DictReader((p/manifest).open(encoding='utf-8-sig')):
   q=p/r['file']
   if not q.is_file():raise FileNotFoundError(q)
   files.add(q)
  files.add(p/manifest)
 for d in ('integration','figures','main_snapshot'):
  files.update(p for p in (ROOT/d).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
 root_names=['人员分类与换类_采用结论与实质续研.md','人员分类与换类_采用结论与实质续研.html','运行与文件索引.md',
  '阶段01_实际可读成果与接续依据.md','STAGE01_ACTUAL_FILES.csv','HISTORICAL_AVAILABLE_FILES.csv','MAIN_SOURCE.json','PR23_STATUS.json',
  'DOWNLOAD_MAP.csv','restore_downloaded_files.py','build_adoption_tables.py','build_new_results.py','build_final_delivery.py',
  'plot_structural_decisions.py','report_style.css']
 files.update(ROOT/x for x in root_names)
 return sorted(files)

def check_links(files):
 missing=[];checked=0
 for p in files:
  if p.suffix!='.md' or p.parent.name=='main_snapshot':continue
  # Snapshot documents retain their historical relative links and are citations.
  if (ROOT/'main_snapshot') in p.parents:continue
  for u in re.findall(r'\]\(([^\n\)]+)\)',p.read_text()):
   if u.startswith(('#','http:','https:','data:','sandbox:','mailto:')):continue
   u=u.split('#')[0]
   if not u:continue
   q=(p.parent/u).resolve();checked+=1
   if q==PACKAGE:continue
   if not q.exists():missing.append({'document':str(p.relative_to(ROOT)),'target':u})
 result=dict(local_links_checked=checked,missing=missing)
 (ROOT/'LINK_CHECK.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
 if missing:raise FileNotFoundError(str(missing))

def main():
 build_download_map();render_report();files=collect()
 # Generate the actual file manifest before checking the index's link to it.
 contents=[dict(path=str(p.relative_to(REPO)),bytes=p.stat().st_size,sha256=sha(p),stage='personnel_exchange_adoption_followup_20261022') for p in files]
 with (ROOT/'PACKAGE_CONTENTS.csv').open('w',newline='',encoding='utf-8-sig') as f:
  w=csv.DictWriter(f,fieldnames=contents[0]);w.writeheader();w.writerows(contents)
 files.append(ROOT/'PACKAGE_CONTENTS.csv');check_links(files)
 files.append(ROOT/'LINK_CHECK.json')
 PACKAGE.parent.mkdir(exist_ok=True)
 tmp=PACKAGE.with_suffix('.zip.writing')
 with zipfile.ZipFile(tmp,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for p in files:z.write(p,str(p.relative_to(REPO)))
  z.writestr('HOHONET_FOLLOWUP_README.txt','本包解压到固定main仓库根目录；先读 research/workers/personnel_exchange_adoption_followup_20261022/运行与文件索引.md。大事件与旧端点按DOWNLOAD_MAP.csv单独取得，不在本包重复保存。真人v2，v3仅研究轮次。\n')
 os.replace(tmp,PACKAGE)
 result=dict(status='complete',package=str(PACKAGE),bytes=PACKAGE.stat().st_size,sha256=sha(PACKAGE),
  contained_files=len(files)+1,large_historical_caches_included=False,new_native_endpoints=3040,
  new_unique_ABC=1014,new_finite_background_ABC=1092,read_main='cf053a6e31d17393c0e8216ce15660fa37b8b7bb',data='real_v2')
 (ROOT/'DELIVERY_COMPLETION.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
 print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':main()
