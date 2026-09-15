"""Publish numerical deliverables as auditable ZIPs; no remote write.

The full ZIP includes all current statistical outputs plus exact pooled matrices.
The reader ZIP omits only large .npy predictor caches. Original photos, weights,
and raw model-output duplicates are never packaged.
"""
from __future__ import annotations
import argparse,csv,hashlib,io,json,os,shutil,subprocess,sys,tempfile,zipfile
from pathlib import Path
from tools.thesis_main.analysis.image_portrait.difficulty_stratified_prepare import ROOT,B,O

VERIFY = '''"""Verify every declared member of an extracted delivery."""
import hashlib,json,sys
from pathlib import Path
root=Path(sys.argv[1] if len(sys.argv)>1 else '.')
manifest=json.loads((root/'ARCHIVE_MANIFEST.json').read_text(encoding='utf-8'))
errors=[]
for r in manifest['files']:
 p=root/r['path']
 if not p.is_file(): errors.append((r['path'],'missing')); continue
 h=hashlib.sha256()
 with p.open('rb') as f:
  for x in iter(lambda:f.read(1024*1024),b''): h.update(x)
 if h.hexdigest()!=r['sha256'] or p.stat().st_size!=r['bytes']:errors.append((r['path'],'digest/size mismatch'))
print(json.dumps({'declared_files':len(manifest['files']),'errors':errors,'kind':manifest['kind']},ensure_ascii=False,indent=2))
raise SystemExit(bool(errors))
'''


def digest(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()


def files_to_include():
 files=[]
 allowed={'.py','.md','.txt','.json','.jsonl','.csv','.gz','.yaml','.yml','.toml','.ini','.js','.html','.css','.npz','.npy','.log','.png','.xml','.sh','.ps1'}
 for folder in ['tools','tests','lib','config','docs']:
  for p in (ROOT/folder).rglob('*'):
   if p.is_file() and p.suffix in allowed and '__pycache__' not in p.parts and p.suffix not in {'.png','.npz','.npy'}:files.append(p)
 for name in ['pytest.ini','requirements-mainspace.txt']:
  if (ROOT/name).is_file():files.append(ROOT/name)
 for p in B.rglob('*'):
  if not p.is_file() or '__pycache__' in p.parts or 'reproduction_backups' in p.parts or p.suffix not in allowed:continue
  rel=p.relative_to(B)
  if rel.parts[0]=='models' and p.suffix=='.npz':continue
  # Only numerical figures in the cloud reports are allowed as PNG.
  if p.suffix=='.png' and ('cloud' not in rel.parts or 'figures' not in rel.parts):continue
  files.append(p)
 return sorted(set(files))


def pending_list():
 targets=list(O.rglob('*'))+list((ROOT/'tools/thesis_main/analysis/image_portrait').glob('difficulty_*.py'))+[ROOT/'tests/test_difficulty_stratified_followup.py',ROOT/'docs/DIFFICULTY_MAINSPACE_EXPLORATION_INDEX.md',ROOT/'requirements-mainspace.txt']
 pending=O/'PENDING_GITHUB_RETURN.csv'
 with pending.open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=['repository_relative_path','bytes','sha256','remote_status','suggested_action']);w.writeheader()
  for p in sorted(set(targets)):
   if not p.is_file() or p==pending or '__pycache__' in p.parts or 'reproduction_backups' in p.parts:continue
   local='cache' in p.relative_to(ROOT).parts and p.suffix=='.npy'
   w.writerow(dict(repository_relative_path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=digest(p),remote_status='not_pushed_this_round',suggested_action='local_reproducibility_input_cache; do_not_blindly_commit_large_arrays' if local else 'new_research_code_or_output; review_then_commit_without_overwriting_prior_versions'))
 return pending


def root_documents():
 r='repo/'+O.relative_to(ROOT).as_posix()
 page=f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>主空间与历史收敛分层：研究交付入口</title><style>body{{font-family:system-ui,"Microsoft YaHei",sans-serif;max-width:960px;margin:40px auto;padding:0 24px;line-height:1.85}}h1{{font-size:27px}}li{{margin:.6em 0}}code{{overflow-wrap:anywhere}}a{{color:#164f86}}</style><body>
<h1>主空间分层、五模型表征与历史收敛粗分类</h1>
<p>本轮为已查看历史结果后的后续探索。人工难度判断与历史收敛过程标签分开；不宣称“困难图永不收敛”。完整解压后使用本页面。</p>
<h2><a href="{r}/REPORT_ZH.html">打开中文综合报告（内嵌六张数值图）</a></h2>
<p><a href="{r}/REPRODUCE.md">复算命令</a>　<a href="{r}/PENDING_GITHUB_RETURN.csv">尚未回传GitHub的清单</a>　<a href="ARCHIVE_MANIFEST.json">本包文件哈希清单</a></p>
<ul>
<li><a href="{r}/images/labels106.csv">106张原始主观标签、人工类别及AI主空间来源</a></li>
<li><a href="{r}/results/all_candidate_scores.csv">全部候选、分层、方法与覆盖</a>；<a href="{r}/results/paired_increments.csv">相同覆盖配对增量</a></li>
<li><a href="{r}/results/stratified_scores.csv">大类、主空间、楼宇内结果</a>；<a href="{r}/controls/matched_intercept_paired.csv">匹配无模型对照</a></li>
<li><a href="{r}/rooms/same_room_tag_scores.csv">同房标签迁移</a>（不等于收敛迁移）</li>
<li><a href="{r}/historical_bridge/confirmation_sensitivity_counts.csv">历史早期k&lt;8、后缀与尾段敏感性</a></li>
<li><a href="{r}/review/local_image_review_queue.csv">本地审图队列：61项问题，含配对共50个image_id</a></li>
<li><a href="{r}/tests/test_run.log">23项针对性测试记录</a>；<a href="{r}/tests/bundle_check.log">工作包输入核验</a></li>
</ul>
<h2>版本、范围与旧结果</h2><p>分支读取头9d19e4e7，数值数据a36e307。实际取得106张标签图的五模型输出（含新DINO）；648图运行状态另行保存。没有读取原图、下载权重或进行视觉推理。本轮未提交GitHub。</p>
<p>阅读包包含全部统计结果和本轮代码；完整包另外包含准确的高维预测输入缓存。从缓存重新拟合无需原图。两个包都包含已恢复的旧报告和结果，但不冒称旧缺失中间文件已经恢复。</p>
<p><a href="repo/analysis_results/image_portrait_20260914_v1/cloud/pro_exploration/v2_convergence_e086b2b9/REPORT_ZH.html">上一轮收敛报告</a>；<a href="repo/analysis_results/image_portrait_20260914_v1/cloud/pro_exploration/v1_e086b2b9/REPORT_ZH.md">首轮报告</a>。新解释优先阅读本轮报告；旧结果保留原版本。</p>
<p>根目录运行 <code>python verify_archive.py .</code> 可核验本包文件。</p></body></html>'''
 return {'START_HERE.html':page.encode(),'verify_archive.py':VERIFY.encode(),'README_ZH.md':('完整解压后打开 START_HERE.html。阅读包含全部本轮统计结果/代码，完整包另含高维缓存。原图和权重不在包内；没有远端提交。详见新报告和 REPRODUCE.md。\n').encode()}


def write_zip(path,kind,files,documents):
 records=[]
 with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as z:
  for name,data in documents.items():
   z.writestr(name,data);records.append(dict(path=name,bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
  for p in files:
   if kind=='readable' and O/'cache' in p.parents and p.suffix=='.npy':continue
   name='repo/'+p.relative_to(ROOT).as_posix()
   ct=zipfile.ZIP_STORED if p.suffix in {'.npz','.gz','.png'} else zipfile.ZIP_DEFLATED
   z.write(p,name,compress_type=ct);records.append(dict(path=name,bytes=p.stat().st_size,sha256=digest(p)))
  manifest=dict(kind=kind,input_branch_head='9d19e4e7de5d49025f8844d1a02889a90e21b4b3',input_data_commit='a36e307724a127b7c110b4e5039f2d62a121091b',new_DINO_array_images=106,status_registry_DINO_images=648,original_images=False,weights=False,visual_inference=False,remote_results_pushed=False,omissions='high-dimensional cache/*.npy only'if kind=='readable'else'raw numerical model NPZ not duplicated; exact pooled matrices included',files=records)
  z.writestr('ARCHIVE_MANIFEST.json',json.dumps(manifest,ensure_ascii=False,indent=2).encode())
 print('CREATED',path.name,path.stat().st_size,len(records),flush=True)
 return manifest


def verify_zip(path):
 errors=[]
 with zipfile.ZipFile(path) as z:
  man=json.loads(z.read('ARCHIVE_MANIFEST.json'));assert len(z.namelist())==len(man['files'])+1
  for r in man['files']:
   h=hashlib.sha256();size=0
   with z.open(r['path']) as f:
    for block in iter(lambda:f.read(1024*1024),b''):h.update(block);size+=len(block)
   if size!=r['bytes'] or h.hexdigest()!=r['sha256']:errors.append(r['path'])
 assert not errors,errors
 return dict(file=path.name,bytes=path.stat().st_size,sha256=digest(path),verified_members=len(man['files']),all_member_sha256_match=True,zip_crc_read_success=True)


def main():
 p=argparse.ArgumentParser();p.add_argument('--destination',type=Path,required=True);args=p.parse_args();dest=args.destination;dest.mkdir(parents=True,exist_ok=True)
 pending_list();allfiles=files_to_include();docs=root_documents();checks=[]
 for kind in ['readable','full']:
  path=dest/f'mainspace_history_{kind}.zip';write_zip(path,kind,allfiles,docs);checks.append(verify_zip(path));print('VERIFIED',kind,flush=True)
 with tempfile.TemporaryDirectory(prefix='mainspace_delivery_test_') as tmp:
  with zipfile.ZipFile(dest/'mainspace_history_readable.zip') as z:z.extractall(tmp)
  root=Path(tmp);env=os.environ.copy();env['PYTHONPATH']=str(root/'repo');env['OPENBLAS_NUM_THREADS']='1';env['OMP_NUM_THREADS']='1'
  result=subprocess.run([sys.executable,'-m','tools.thesis_main.analysis.image_portrait.difficulty_stratified_reproduce','--tests-only'],cwd=root/'repo',env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
  (dest/'extracted_package_tests.log').write_text(result.stdout,encoding='utf-8')
  assert result.returncode==0,result.stdout
  print(result.stdout,flush=True)
  v=subprocess.run([sys.executable,'verify_archive.py','.'],cwd=root,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
  assert v.returncode==0,v.stdout
  (dest/'extracted_file_verification.log').write_text(v.stdout,encoding='utf-8')
 checks=dict(packages=checks,independent_extraction_tests=dict(package='readable',command='difficulty_stratified_reproduce --tests-only',returncode=result.returncode,log='extracted_package_tests.log',scope='23 targeted tests plus build_bundle --check, not a repeated full nested model experiment'),extracted_manifest_passed=True,remote_results_pushed=False)
 (dest/'DELIVERY_VERIFICATION.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 shutil.copy2(O/'REPORT_ZH.html',dest/'mainspace_history_report.html');shutil.copy2(O/'REPORT_ZH.md',dest/'mainspace_history_report.md');shutil.copy2(O/'REPRODUCE.md',dest/'REPRODUCE.md')
 for path,name in [(O/'results/all_candidate_scores.csv','all_candidate_scores.csv'),(O/'historical_bridge/confirmation_sensitivity_counts.csv','historical_confirmation_counts.csv'),(O/'review/local_image_review_queue.csv','local_image_review_queue.csv')]:shutil.copy2(path,dest/name)
 print('DELIVERY COMPLETE',dest,flush=True)

if __name__=='__main__':main()
