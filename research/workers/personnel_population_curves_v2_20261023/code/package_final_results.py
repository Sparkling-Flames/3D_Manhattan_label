"""Build separately downloadable completed research packages, not new analyses."""
from pathlib import Path
import argparse, hashlib, json, os, zipfile

ROOT=Path('/workspace/scratch/fe955c3c772c')
REPO=ROOT/'HOHONET_population_latest'
OUT=REPO/'research/workers/personnel_population_curves_v2_20261023'
DEST=ROOT/'population_deliverables'
WORK=ROOT/'population_work'

def good(p):
    return p.is_file() and not any(x.startswith('.') or x=='__pycache__' for x in p.parts) and not p.name.endswith(('.pyc','.tmp','.log'))
def files(path):return sorted(p for p in path.rglob('*') if good(p))
def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()

def package(name, paths, base):
    dest=DEST/name; temp=dest.with_name(name+'.partial')
    with zipfile.ZipFile(temp,'w',allowZip64=True,compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in paths:
            compression=zipfile.ZIP_STORED if p.suffix in ('.gz','.zip','.jpg','.png','.pdf') else zipfile.ZIP_DEFLATED
            z.write(p,str(p.relative_to(base)),compress_type=compression)
    with temp.open('rb') as f:os.fsync(f.fileno())
    temp.replace(dest)
    # Verify archive indexing and declared entry sizes. Endpoint semantics were
    # verified before packaging, and are not recomputed here.
    with zipfile.ZipFile(dest) as z:
        assert len(z.infolist())==len(paths)
        assert all(i.file_size==p.stat().st_size for i,p in zip(z.infolist(),paths))
    receipt={'file':str(dest),'bytes':dest.stat().st_size,'sha256':sha(dest),'entries':len(paths),'members':[str(p.relative_to(base)) for p in paths]}
    (WORK/(name+'.json')).write_text(json.dumps(receipt,ensure_ascii=False,indent=2))
    print(json.dumps({k:v for k,v in receipt.items() if k!='members'},ensure_ascii=False),flush=True)
    return receipt

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--parts',nargs='+',default=['04A','04B','04C']);a=ap.parse_args()
    for part in a.parts:
        if part=='04A':
            package('HOHONET_v2人数过程_阶段04A_自然曲线与215568完整过程事件_20261023.zip',files(OUT/'natural')+[OUT/'events/NATURAL_ADJACENT_TRANSITIONS_LINKED.csv.gz',OUT/'events/NATURAL_PAIRED_PATH_INTERVALS_LINKED.csv.gz'],OUT)
        elif part=='04B':
            package('HOHONET_v2人数过程_阶段04B_四方向全部比较与分项分布_20261023.zip',files(OUT/'policies'),OUT)
        elif part=='04C':
            package('HOHONET_v2人数过程_阶段04C_341570完整策略比较事件_20261023.zip',[OUT/'events/POLICY_PAIRED_PREFIX_EVENTS_LINKED.csv.gz',OUT/'events/POLICY_DIRECT_PAIRED_PREFIX_EVENTS_LINKED.csv.gz'],OUT)
        elif part=='04D':
            pieces=[]
            for p in files(OUT):
                rel=p.relative_to(OUT)
                if rel.parts[0] in ('results','natural','policies'):continue
                if rel.parts[0]=='events' and p.name.endswith('_LINKED.csv.gz'):continue
                # exact orders also appear in 03C; small intentional input copy.
                pieces.append(p)
            pieces += [REPO/'docs/thesis_main/人员分类与构成不确定性_研究组织与比较清单_20261022.md',REPO/'docs/thesis_main/人员标法分类与换类研究_总体进度_20261020.md',REPO/'research/catalog/INDEX.md']
            package('HOHONET_v2人数过程_阶段04D_主报告代码输入标签与五案_仓库接入_20261023.zip',sorted(pieces),REPO)
        else:raise ValueError(part)

if __name__=='__main__':main()
