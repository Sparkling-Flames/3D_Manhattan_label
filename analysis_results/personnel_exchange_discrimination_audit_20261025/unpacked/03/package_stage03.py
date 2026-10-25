"""Save finished classifications and exact registrations while fusion runs."""
import hashlib,json,zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'deliverables'
OUT.mkdir(exist_ok=True)
selected=set()
for name in ['reverse','design/confirm','design/reverse_screen','design/reverse_confirm','design/target_omissions','design/size_paths','figures','stage00']:
    for p in (ROOT/name).rglob('*'):
        if p.is_file() and '__pycache__' not in p.parts and '.mpl' not in p.parts and p.name!='NotoSansCJKsc-Regular.otf': selected.add(p)
for name in ['STAGE03_README.md','run_native.py','measure_events.py','register_exchange.py','package_stage03.py','design/BATCH02_REGISTRATION.json','design/SELECTED_GRID_BEFORE_NEW_RESULTS.json','design/SELECTION_RATIONALE.json','analysis/SCREEN_SELECTION_MEMO.md','analysis/analyze_target_omissions.py','design_advice/register_target_omissions.py']:
    p=ROOT/name
    if p.exists():selected.add(p)
for p in (ROOT/'classifications').glob('*'):
    if p.is_file() and any(s in p.name for s in ['COMPLETE','README','LATEST_STAGE','ORDINARY_DIFFICULT_RAW_FOCUS','FILE_MANIFEST']): selected.add(p)
for p in (ROOT/'classifications/code').rglob('*.py'):selected.add(p)
manifest=[{'path':str(p.relative_to(ROOT)),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(selected)]
archive=OUT/'HOHONET_换类区分度_阶段03_反推分类与精确扩展登记_20261025.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=5) as z:
    for p in sorted(selected):z.write(p,p.relative_to(ROOT))
    z.writestr('STAGE03_PACKAGE_MANIFEST.json',json.dumps(manifest,ensure_ascii=False,indent=2))
receipt={'archive':str(archive),'files':len(manifest),'bytes':archive.stat().st_size,'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'status':'registrations_and_classifications_complete_effects_running'}
(OUT/'STAGE03_PACKAGE_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2))
(OUT/'UPLOAD_STAGE03.json').write_text(json.dumps({'uploads':[{'local_path':str(archive),'purpose':'create_library_file','library_artifact_type':'other'},{'local_path':str(ROOT/'STAGE03_README.md'),'purpose':'create_library_file','library_artifact_type':'report'}]},ensure_ascii=False))
print(json.dumps(receipt,ensure_ascii=False))
