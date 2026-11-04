"""Package the completed study into ordered repository-relative ZIP overlays.

Run only after validate_delivery.py passes. ZIPs and the outer checksum index are
written to an explicitly provided directory. No source data are changed.
"""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import shutil
import zipfile

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[2]
STUDY=ROOT.relative_to(REPO)
NAMES={13:'HOHONET_v21_batch13_current_DSTRUCT_AC_audit_and_gap_20261104.zip',
       14:'HOHONET_v21_batch14_current_DSTRUCT_AC_statistics_20261104.zip',
       15:'HOHONET_v21_batch15_current_DSTRUCT_AC_mechanisms_and_closeout_20261104.zip'}


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()


def eligible(p):
    rel=p.relative_to(ROOT)
    if any(x in rel.parts for x in ('__pycache__','raw_target_metrics')):return False
    if p.suffix in ('.pyc','.log','.tmp','.writing'):return False
    if p.name.startswith('PRELIM_'):return False
    if rel.parts[0]=='delivery' and (p.name.startswith('BATCH_') or p.name.startswith('ZIP_')):return False
    return p.is_file()


def batch(p):
    first=p.relative_to(ROOT).parts[0]
    if first=='analysis':return 14
    if first in ('registry','inputs','supplement','audit'):return 13
    return 15


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output-dir',required=True)
    parser.add_argument('--batches',nargs='+',type=int,default=[13,14,15],choices=[13,14,15]);args=parser.parse_args()
    check=json.loads((ROOT/'DELIVERY_CHECKS.json').read_text(encoding='utf-8'))
    assert check['status']=='passed','Final delivery validation must pass before packaging.'
    dest=Path(args.output_dir).expanduser().resolve();dest.mkdir(parents=True,exist_ok=True)
    by={n:[] for n in NAMES}
    for p in sorted(ROOT.rglob('*')):
        if eligible(p):by[batch(p)].append(p)
    with (ROOT/'delivery/INTEGRATED_PROJECT_FILES.csv').open(encoding='utf-8-sig') as f:
        by[15].extend(REPO/r['path'] for r in csv.DictReader(f))
    results=[]
    for n in args.batches:
        install=ROOT/f'delivery/BATCH_{n}_INSTALL.md'
        install.write_text(f'''# HOHONET v2.1 第{n}批安装

文件：{NAMES[n]}

本次交付为第13、14、15批三个仓库增量包。请保留目录结构，按13→14→15顺序解压到已有 `D:/Work/HOHONET`。底座为固定main `48a2fc6aedd51cd701b1bce06c02bd3ef92ec75b` 与此前第08–12批。

13：合法性/容量/登记/有限补充完整端点。14：全部当前合法AC底表与统计、分项/劳动/状态。15：中文报告、原图机制与背景成员、研究台、最终验收和项目入口更新。

全部解压后打开 `research/workers/current_dstruct_ac_final_20261104/workbench/index.html`。正常阅读无需联网或重新运行融合。

本包对应的 `BATCH_{n}_FILES.csv` 列出每个实际文件的仓库路径、字节数及SHA256；清单不递归包含自身。ZIP自身SHA256在单独随交付提供的 `HOHONET_v21_batches13_15_DOWNLOAD_INDEX.csv` 中。三个ZIP的完整下载目录见第15批的 `delivery/README.html`。
''',encoding='utf-8')
        paths=sorted(set(by[n]+[install]),key=lambda p:str(p.relative_to(REPO)))
        rows=[dict(path=str(p.relative_to(REPO)).replace('\\','/'),bytes=p.stat().st_size,sha256=digest(p)) for p in paths]
        manifest=ROOT/f'delivery/BATCH_{n}_FILES.csv'
        with manifest.open('w',newline='',encoding='utf-8-sig') as f:
            w=csv.DictWriter(f,fieldnames=['path','bytes','sha256']);w.writeheader();w.writerows(rows)
        paths.append(manifest)
        zip_path=dest/NAMES[n]
        with zipfile.ZipFile(zip_path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as z:
            for p in paths:
                name=str(p.relative_to(REPO)).replace('\\','/')
                info=zipfile.ZipInfo(name,date_time=(2026,11,4,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
                info.external_attr=0o100644<<16
                with p.open('rb') as f,z.open(info,'w',force_zip64=True) as out:shutil.copyfileobj(f,out,8*1024*1024)
        # Full archive read validates CRC; additionally compare every manifest digest.
        with zipfile.ZipFile(zip_path) as z:
            assert len(z.namelist())==len(set(z.namelist()))==len(paths)
            assert z.testzip() is None
            for r in rows:
                with z.open(r['path']) as f:
                    h=hashlib.sha256();size=0
                    for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b);size+=len(b)
                assert h.hexdigest()==r['sha256'] and size==r['bytes'],r['path']
        result=dict(batch=n,filename=zip_path.name,bytes=zip_path.stat().st_size,
                    sha256=digest(zip_path),archive_members=len(paths),
                    uncompressed_bytes=sum(p.stat().st_size for p in paths),
                    CRC_and_member_SHA256='passed',installation_order='13 -> 14 -> 15',
                    entrypoint=str(STUDY/'workbench/index.html'))
        results.append(result);print(json.dumps(result,ensure_ascii=False),flush=True)
    index=dest/'HOHONET_v21_batches13_15_DOWNLOAD_INDEX.csv'
    if len(args.batches)<3 and index.exists():
        with index.open(encoding='utf-8-sig') as f:old=list(csv.DictReader(f))
        results.extend(x for x in old if int(x['batch']) not in args.batches)
    results.sort(key=lambda x:int(x['batch']))
    with index.open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=list(results[0]));w.writeheader();w.writerows(results)
    (dest/'HOHONET_v21_batches13_15_ZIP_ACCEPTANCE.json').write_text(json.dumps(
        dict(status='passed',packages=results,files_index=index.name,zip_crc_and_all_manifest_hashes_verified=True),
        ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'status':'passed','index':str(index),'batches':[r['batch'] for r in results]},ensure_ascii=False))


if __name__=='__main__':main()
