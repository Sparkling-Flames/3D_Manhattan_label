#!/usr/bin/env python3
"""Portable entry for selected actual replays and deterministic regeneration."""
from pathlib import Path
import argparse, hashlib, json, os, subprocess, sys
ROOT=Path(__file__).resolve().parent
S=ROOT/'interchangeability_20261020'
def main():
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('stage',choices=['hashes','cases','core','designs','forward','fetch-originals','render-cases','report'])
 ap.add_argument('--restored',type=Path);ap.add_argument('--work',type=Path,default=ROOT.parent/'personnel_replay_output');ap.add_argument('--jobs',type=int,default=3)
 a=ap.parse_args();work=a.work.resolve();work.mkdir(parents=True,exist_ok=True)
 env=os.environ.copy();env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1',MPLCONFIGDIR=str(work/'mplconfig'))
 def run(cmd):subprocess.run([sys.executable,*map(str,cmd)],cwd=ROOT,env=env,check=True)
 if a.stage=='hashes':
  rows=json.loads((ROOT/'FILES_SHA256.json').read_text())['files']
  for row in rows:
   p=ROOT/row['path'];assert p.is_file(),str(p)
   assert p.stat().st_size==row['bytes'] and hashlib.sha256(p.read_bytes()).hexdigest()==row['sha256'],str(p)
  print(json.dumps(dict(files_verified=len(rows),all_passed=True)));return
 if a.stage in ['cases','core','designs','forward']:
  if a.restored is None:ap.error('--restored is required; see README_ZH.md for pinned recovery')
  restored=a.restored.resolve()
  if a.stage=='cases':run([S/'code/replay_cases.py','--restored',restored,'--cases',S/'cases','--out',work/'cases'])
  elif a.stage=='core':run([S/'code/core_replay.py','run','--bundle',S/'core_replay','--restored',restored,'--native-out',work/'core_native','--report',work/'core','--jobs',a.jobs])
  elif a.stage=='designs':run([S/'reproduction/verify_designs.py','--package-root',ROOT,'--restored',restored,'--out',work/'designs'])
  else:run([S/'reproduction/rebuild_forward.py','--package-root',ROOT,'--restored',restored,'--out',work/'forward'])
 elif a.stage=='fetch-originals':
  sys.path.insert(0,str(ROOT/'analysis/visual_sources'));import range_zip
  manifest=json.loads((S/'ORIGINALS_MANIFEST.json').read_text());out=S/'originals/selected';out.mkdir(parents=True,exist_ok=True)
  range_zip.extract(json.loads((ROOT/'analysis/visual_sources/release_metadata.json').read_text()),ROOT/'analysis/visual_sources/zip_directories.json',ROOT/'analysis/visual_sources/release_IMAGE_INDEX.csv',[r['image_id'] for r in manifest['images']],out)
  for r in manifest['images']:assert hashlib.sha256((ROOT/r['local_path']).read_bytes()).hexdigest()==r['sha256']
 elif a.stage=='render-cases':run([S/'code/render_review_cases.py','--cases',S/'cases','--out',work/'case_figures','--font',ROOT/'analysis/fonts/NotoSansSC-Regular.ttf'])
 elif a.stage=='report':run([S/'code/build_report_pdf.py','--root',ROOT,'--out',work/'REPORT_ZH.pdf'])
if __name__=='__main__':main()
