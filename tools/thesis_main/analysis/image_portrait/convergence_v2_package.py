"""Package existing research, without models, images, weights or source edits.

The full archive includes every restored repository file except Python/pytest
caches. The readable archive omits NPZ caches only. Both disclose missing prior
intermediates and carry a per-file SHA-256 manifest.
"""
from __future__ import annotations
import argparse,csv,hashlib,io,json,zipfile
from pathlib import Path
from tools.thesis_main.analysis.image_portrait.convergence_v2_common import ROOT,OUT

def sha256(p:Path)->str:
 h=hashlib.sha256()
 with p.open('rb')as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()

def allowed(p:Path)->bool:
 return p.is_file() and not any(s in {'__pycache__','.pytest_cache','.git'} for s in p.parts) and p.suffix not in {'.pyc','.pyo'}

def write_csv(p:Path,rows:list[dict])->None:
 with p.open('w',encoding='utf-8-sig',newline='')as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0])if rows else['status']);w.writeheader();w.writerows(rows)

def record(p:Path)->dict:
 return dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=sha256(p))

def package(dest:Path)->dict:
 dest.mkdir(parents=True,exist_ok=True)
 if dest.resolve().is_relative_to(ROOT.resolve()):raise ValueError('ZIP destination must be outside repository')
 result_rows=[record(p) for p in sorted(OUT.rglob('*'))if allowed(p)and p.name not in {'RESULT_FILE_MANIFEST.csv','PENDING_GITHUB_RETURN.csv'}]
 write_csv(OUT/'RESULT_FILE_MANIFEST.csv',result_rows)
 sources=list((ROOT/'tools/thesis_main/analysis/image_portrait').glob('convergence_v2_*.py'))+[ROOT/'tests/test_image_portrait_convergence_v2.py',OUT.parent/'README.md',ROOT/'docs/UNCERTAINTY_CONVERGENCE_EXPLORATION_INDEX.md']
 pending=sorted(set([p for p in OUT.rglob('*')if allowed(p)and p.name!='PENDING_GITHUB_RETURN.csv']+sources))
 write_csv(OUT/'PENDING_GITHUB_RETURN.csv',[dict(**record(p),remote_submitted=False,disposition='new_followup_or_additive_index; original and v1 unchanged')for p in pending])
 files=[p for p in sorted(ROOT.rglob('*'))if allowed(p)]
 for p in files:
  if p.suffix.lower()in{'.jpg','.jpeg','.png','.webp','.bmp','.tif','.tiff'}and p.parent!=OUT/'figures':raise ValueError('Unapproved image: '+str(p))
  if p.suffix.lower()in{'.pth','.pt','.safetensors','.ckpt','.otf','.ttf','.woff','.woff2'}:raise ValueError('Weight/font file: '+str(p))
 rel='repo/'+OUT.relative_to(ROOT).as_posix()
 links=[('REPORT_ZH.html','中文综合报告（7张内嵌数值图）'),('REINTERPRETATION_ZH.md','上一轮发现的重新解释与纠正'),('review/LOCAL_REVIEW.html','离线本地审图页（不含原图、不上传图像）'),('review/local_review_final.csv','112项问题 / 62个image_id：审图清单'),('REPRODUCE.md','复算命令、环境及方法边界'),('process/image_uncertainty_structure.csv','逐图不确定性结构'),('subgroups/fixed_disjoint_split_target_processes.csv','固定名单跨楼宇目标结果'),('combinations/class_pool_process_transitions.csv','真实类群合并与增长过程'),('PENDING_GITHUB_RETURN.csv','尚未回传GitHub的文件清单')]
 start='''<!doctype html><html lang="zh"><meta charset="utf-8"><title>研究交付入口</title><style>body{font:17px/1.8 system-ui,sans-serif;max-width:1000px;margin:50px auto;padding:0 20px}h1{font-size:30px}a{display:block;margin:14px 0}code{overflow-wrap:anywhere}</style><h1>标注不确定性与收敛：数值研究交付</h1><p>先将ZIP完整解压，再双击此文件。主线是不确定性的结构、随真实人数的变化及跨图片和人员构成的复现。本轮是已查看旧结果后的探索，不是新的独立确认研究。</p>'''
 start+=''.join(f'<a href="{rel}/{p}">{label}</a>'for p,label in links)
 start+='''<p>完整包包含全部本轮代码、表、图和计算缓存；轻量包只省略NPZ，两者均保留全部代码和可读结果。上一轮可恢复的31个结果和原分析模块保持原样；222项未留存的旧中间文件有缺件记录，不冒称恢复。本轮没有向GitHub提交。</p><p>输入提交：<code>e086b2b94d60b8a858a71f0326f12930538fe4fe</code>。ARCHIVE_CONTENTS.csv为逐文件SHA-256清单；verify_archive.py可在本地核验完整性。</p></html>'''
 readme='''# 研究交付\n\n完整解压后打开 START_HERE.html。完整包用于复算；轻量包仅省略NPZ缓存。两个包都有全部代码、表、报告和图。\n\n未提交GitHub；待回传清单在新报告目录。旧报告不覆盖；旧缺件逐项披露。本次复算使用随包foundation及特征缓存；清空缓存后才需从冻结提交恢复原模型数值导出，不得重新运行视觉模型。\n\n原图和权重不在包内。审图页只读取您主动选择的本地文件，不上传。\n\n解压后验证：python verify_archive.py .\n'''
 verifier='''"""Validate archived research bytes. No network access."""\nimport csv,hashlib,sys\nfrom pathlib import Path\nroot=Path(sys.argv[1]if len(sys.argv)>1 else'.');failed=[];count=0\nwith (root/'ARCHIVE_CONTENTS.csv').open(encoding='utf-8-sig',newline='')as f:\n for r in csv.DictReader(f):\n  p=root/r['path'];count+=1\n  if not p.is_file():failed.append((r['path'],'missing'));continue\n  h=hashlib.sha256()\n  with p.open('rb')as s:\n   for b in iter(lambda:s.read(1048576),b''):h.update(b)\n  if p.stat().st_size!=int(r['bytes'])or h.hexdigest()!=r['sha256']:failed.append((r['path'],'mismatch'))\nprint('Files:',count,'Failures:',failed)\nsys.exit(bool(failed))\n'''
 root_files={'START_HERE.html':start.encode(),'README_ZH.md':readme.encode(),'verify_archive.py':verifier.encode()}
 summary=dict(input_commit='e086b2b94d60b8a858a71f0326f12930538fe4fe',github_submitted=False,prior_available_results=31,prior_missing_intermediates=222,original_images_included=False,model_weights_included=False,archives=[])
 hashes={p:record(p)for p in files}
 for kind,name in [('full','uncertainty_convergence_full.zip'),('readable','uncertainty_convergence_readable.zip')]:
  selected=[p for p in files if kind=='full'or p.suffix.lower()!='.npz']
  rows=[{'path':'repo/'+hashes[p]['path'],'bytes':hashes[p]['bytes'],'sha256':hashes[p]['sha256']}for p in selected]
  rows += [dict(path=n,bytes=len(b),sha256=hashlib.sha256(b).hexdigest())for n,b in root_files.items()]
  s=io.StringIO();w=csv.DictWriter(s,fieldnames=['path','bytes','sha256']);w.writeheader();w.writerows(rows)
  path=dest/name
  with zipfile.ZipFile(path,'w',allowZip64=True)as z:
   for p in selected:z.write(p,'repo/'+p.relative_to(ROOT).as_posix(),compress_type=zipfile.ZIP_STORED if p.suffix.lower()in{'.npz','.gz','.png'}else zipfile.ZIP_DEFLATED,compresslevel=6)
   for n,b in root_files.items():z.writestr(n,b,compress_type=zipfile.ZIP_DEFLATED)
   z.writestr('ARCHIVE_CONTENTS.csv','\ufeff'+s.getvalue(),compress_type=zipfile.ZIP_DEFLATED)
  with zipfile.ZipFile(path)as z:
   bad=z.testzip();names=z.namelist()
   if bad:raise RuntimeError('CRC mismatch: '+bad)
   if len(names)!=len(set(names)):raise RuntimeError('Duplicate paths')
  summary['archives'].append(dict(file=name,bytes=path.stat().st_size,sha256=sha256(path),members=len(names),crc_test='passed',manifested_files=len(rows),excludes_npz=kind=='readable'));print(json.dumps(summary['archives'][-1]),flush=True)
 (dest/'DELIVERY_MANIFEST.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');return summary

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--output-dir',type=Path,default=ROOT.parent/'delivery');args=ap.parse_args();package(args.output_dir)
