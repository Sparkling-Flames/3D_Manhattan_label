"""Create a compact, explicit research package; omit reproducible caches."""
from pathlib import Path
import argparse,csv,hashlib,json,zipfile

HERE=Path(__file__).resolve().parents[1]
SKIP_PARTS={'__pycache__','runtime','nested_runtime'}
SKIP_NAMES={
 'STAGE1_CLASSIFICATION.html','STAGE_REPORT_ZH.md',
 'pair_observations.csv.gz','lobo_incremental_predictions.csv.gz',
 'REUSED_COMMON_ENDPOINT_LABELS.csv.gz','A2_REUSED_COMMON_LABELS.csv.gz',
 'A2_NEW_B_DESIGN_LABELS.csv.gz','HIERARCHY_PAIR_VALUES.csv.gz',
 'SELECTED_STATES.json.gz','JTC26_PREDECLARED.json.gz'}
ROOT_FILES={'README.md','REPORT_ZH.md','REPRODUCE.md','INPUT_MANIFEST.json','DELIVERY_NOTES.json'}

def selected(p):
    rel=p.relative_to(HERE)
    if any(x in SKIP_PARTS for x in rel.parts) or p.name in SKIP_NAMES:return False
    if p.name=='PACKAGE_MANIFEST.csv':return False
    if p.suffix=='.pyc':return False
    if len(rel.parts)==1:return p.name in ROOT_FILES
    first=rel.parts[0]
    if first=='route_a' and p.name.endswith('.csv.gz'):return False
    if first not in {'route_a','route_b','fusion','code','evidence','figures','labels'}:return False
    return p.suffix in {'.csv','.json','.gz','.png','.py','.md'}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);args=ap.parse_args()
    files=sorted(p for p in HERE.rglob('*') if p.is_file() and selected(p))
    manifest=HERE/'PACKAGE_MANIFEST.csv'
    with manifest.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['path','group','bytes','sha256']);w.writeheader()
        for p in files:
            b=p.read_bytes();rel=p.relative_to(HERE);w.writerow({'path':str(rel),'group':rel.parts[0] if len(rel.parts)>1 else 'report_and_contract','bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()})
    args.out.parent.mkdir(exist_ok=True,parents=True)
    with zipfile.ZipFile(args.out,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in files+[manifest]:z.write(p,str(Path(HERE.name)/p.relative_to(HERE)))
    with zipfile.ZipFile(args.out) as z:
        bad=z.testzip()
        if bad:raise ValueError('ZIP CRC failure: '+bad)
        names=z.namelist()
        if any('/runtime/' in n or '/nested_runtime/' in n or '__pycache__' in n for n in names):raise ValueError('unexpected cache')
    print(json.dumps({'package':str(args.out),'files':len(files)+1,'uncompressed_bytes':sum(p.stat().st_size for p in files+[manifest]),'zip_bytes':args.out.stat().st_size,'zip_crc':'ok','raw_image_archives_included':False},ensure_ascii=False))

if __name__=='__main__':main()
