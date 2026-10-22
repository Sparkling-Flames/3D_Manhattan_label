#!/usr/bin/env python3
"""Close, fsync, fully verify and freshly extract a deterministic research ZIP.

This only packages the new extension, under a path disjoint from the repaired
prior study's files. A completed archive is the sole upload input; no background
compression or partial-file upload is permitted by this workflow.
"""
from pathlib import Path
import argparse,csv,hashlib,json,os,zipfile


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--study',type=Path,default=Path(__file__).resolve().parents[1]);ap.add_argument('--zip',type=Path,required=True);ap.add_argument('--fresh-extract',type=Path,required=True);ap.add_argument('--proof-prefix',type=Path,required=True);a=ap.parse_args()
    study=a.study.resolve();archive=a.zip.resolve();dest=a.fresh_extract.resolve();proof=a.proof_prefix.resolve()
    assert study.name=='structure_height_preference_20261012'
    assert not archive.exists(), 'Never silently replace a previously finalized archive.'
    assert not dest.exists(), 'Fresh extraction must really be fresh.'
    rep=json.loads((study/'verification/fresh_reproduction_report.json').read_text());assert rep['status']=='pass'
    manifest_path=study/'FILE_MANIFEST_SHA256.json'
    paths=sorted(p for p in study.rglob('*') if p.is_file() and p!=manifest_path and '__pycache__' not in p.parts and p.suffix!='.pyc')
    assert all(not p.is_symlink() for p in paths)
    manifest={'schema':'independent_extension_delivery_v1','study':'structure_height_preference_20261012',
       'actual_main_sha':'a7ff459e992769c944541800dbe3be6e4b83ae4b',
       'requires_prior_archive':'quality_top_structure_research_20261012_repaired_v1.zip',
       'requires_prior_archive_sha256':'08b752a63cb8fb557fd32bce5c633539629f9eb847858d29bef1f027786e0bdd',
       'file_count_excluding_this_manifest':len(paths),'manifest_self_excluded':True,
       'files':[{'path':str(p.relative_to(study)),'bytes':p.stat().st_size,'sha256':sha(p)} for p in paths]}
    write(manifest_path,manifest)
    paths=sorted(paths+[manifest_path])
    prefix=Path('quality_top_structure_research_20261012')/study.name
    archive.parent.mkdir(parents=True,exist_ok=True)
    # The archive's central directory is written by exiting ZipFile, before fsync.
    with archive.open('xb') as stream:
        with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as z:
            for p in paths:
                name=str(prefix/p.relative_to(study))
                info=zipfile.ZipInfo(name,date_time=(2026,10,12,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
                info.create_system=3;info.external_attr=(0o100644<<16)
                z.writestr(info,p.read_bytes(),compress_type=zipfile.ZIP_DEFLATED,compresslevel=6)
        stream.flush();os.fsync(stream.fileno())
    members=[]
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        assert len(z.namelist())==len(set(z.namelist()))==len(paths)
        expected_names={str(prefix/p.relative_to(study)):p for p in paths}
        assert set(z.namelist())==set(expected_names)
        for item in z.infolist():
            p=expected_names[item.filename];data=z.read(item.filename)
            assert len(data)==p.stat().st_size and hashlib.sha256(data).hexdigest()==sha(p)
            members.append({'path':item.filename,'bytes':item.file_size,'compressed_bytes':item.compress_size,
                            'crc32':f'{item.CRC:08x}','sha256':hashlib.sha256(data).hexdigest()})
        z.extractall(dest)
    for r in members:
        p=dest/r['path'];assert p.is_file() and p.stat().st_size==r['bytes'] and sha(p)==r['sha256']
    with proof.with_name(proof.name+'_members.tsv').open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(members[0]),delimiter='\t');w.writeheader();w.writerows(members)
    result={'archive':archive.name,'bytes':archive.stat().st_size,'sha256':sha(archive),'members':len(members),
       'uncompressed_bytes':sum(r['bytes'] for r in members),'full_crc':'pass','member_sha256':'pass',
       'fresh_extraction_member_sha256':'pass','compressor_closed_before_upload':True,'fsync_before_upload':True,
       'zip_path_prefix':str(prefix),'old_study_files_in_extension':0,'fresh_extract':str(dest),
       'scientific_reproduction':{'commands':rep['commands'],'result_files':rep['numerical_result_files_checked'],'status':rep['status']},
       'actual_delivered_copy_validation':'pending; upload this closed archive, retrieve it, then run verify_delivered_archive.py'}
    write(proof.with_name(proof.name+'_integrity_local.json'),result)
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
