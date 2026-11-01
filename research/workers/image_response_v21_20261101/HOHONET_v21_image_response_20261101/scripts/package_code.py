"""Package portable analysis code, reproduction guidance and final validation."""
from pathlib import Path
import ast,csv,gzip,hashlib,io,json,zipfile

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'stage09_delivery'

def sha(b):return hashlib.sha256(b).hexdigest()

def main():
    selected={p.relative_to(ROOT).as_posix():p for p in sorted((ROOT/'scripts').glob('*.py'))}
    # Small read-only provenance: exact public source plans, adopted documents,
    # frozen upstream snippets. Large source caches and transfers stay outside.
    for dirname in ['stage00_manual_sources','stage00_doorway_sources']:
        for p in sorted((ROOT/dirname).rglob('*')):
            if p.is_file() and '__pycache__' not in p.parts and not p.name.endswith(('.tmp','.pyc','.log')):
                selected[p.relative_to(ROOT).as_posix()]=p
    for name in ['requirements.txt','assets/NotoSansSC-Regular.ttf','assets/NotoSansSC-Semibold.ttf','assets/OFL_NotoSansSC.txt']:
        selected[name]=ROOT/name
    for p in sorted(OUT.iterdir()):
        if p.name.endswith(('.csv','.json','.html','.md')) and not any(s in p.name for s in ['UPLOAD_','PACKAGING_PLAN','VALIDATION.json.tmp']):
            selected[p.relative_to(ROOT).as_posix()]=p
    # Exact bytes of the same portable indices supplied in the input packages.
    for name in ['manual','doorway','doorway_enriched']:
        rel=f'stage02_normalized/{name}/POOL_INDEX.csv'
        selected[rel]=ROOT/'reproduction_inputs'/rel
    for name in ['stage09_delivery/REPRODUCTION_GUIDE_ZH.html','stage09_delivery/DEPENDENCIES_PINNED.csv',
                 'stage09_delivery/NEW_COMPUTATIONS_LEDGER.csv','stage09_delivery/RESULTS_PACKAGE_VALIDATION.json',
                 'stage09_delivery/CROSS_PACKAGE_OVERLAP_CHECK.json']:
        assert name in selected and selected[name].is_file(),name
    # The historical intake record retains its original checkpoint status.
    selected['stage01_intake/INPUT_LOCK.json']=ROOT/'stage01_intake/INPUT_LOCK.json'
    target=ROOT/'delivery/06_Code_and_Reproduction.zip'
    assert not target.exists(),target
    rows=[]
    with zipfile.ZipFile(target.with_suffix('.zip.tmp'),'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for rel,p in sorted(selected.items()):
            assert p.is_file(),p
            b=p.read_bytes();member=ROOT.name+'/'+rel
            z.writestr(member,b)
            rows.append({'relative_path':rel,'archive_member':member,'source_bytes':len(b),'source_sha256':sha(b)})
    temp=target.with_suffix('.zip.tmp')
    with zipfile.ZipFile(temp) as z:
        assert z.testzip() is None
        for rec in rows:
            b=z.read(rec['archive_member']);assert sha(b)==rec['source_sha256']
            rec['source_equals_archive_member']=True
            rel=rec['relative_path']
            if rel.endswith('.py'):ast.parse(b.decode('utf-8'));rec['python_ast_parsed']=True
            if rel.endswith('.json'):json.loads(b.decode('utf-8-sig'));rec['json_parsed']=True
            if rel.endswith('.csv'):
                rd=csv.reader(io.StringIO(b.decode('utf-8-sig'),newline=''));h=next(rd,[]);n=0;blank=0
                for rr in rd:
                    if not rr:blank+=1;continue
                    assert len(rr)==len(h),(rel,n)
                    n+=1
                rec['csv_rows']=n;rec['csv_blank_lines']=blank
    temp.replace(target)
    with (OUT/'CODE_PACKAGE_MANIFEST.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=sorted({k for r in rows for k in r}));w.writeheader();w.writerows(rows)
    result={'status':'passed','package_name':target.name,'bytes':target.stat().st_size,'sha256':sha(target.read_bytes()),
            'files':len(rows),'python_files':sum(r.get('python_ast_parsed',False) for r in rows),
            'all_zip_crc_passed':True,'all_sources_equal_archive_members':True,'all_python_ast_valid':True,
            'vendor_binary_included':False,'portable_indices_identical_to_inputs':True,
            'fonts':'Noto Sans SC static Regular and Semibold; OFL license included'}
    (OUT/'CODE_PACKAGE_VALIDATION.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps(result))

if __name__=='__main__':main()
