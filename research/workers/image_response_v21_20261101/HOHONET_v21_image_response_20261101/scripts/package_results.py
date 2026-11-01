"""Archive final downstream results and geometry events; fully read all members.

The main path-change event tables already have dedicated 03 packages. This
script never changes a research source or result. It omits temporary files and
does not include Library transfer receipts, credentials, or large upstream ZIPs.
"""
from pathlib import Path
import csv, gzip, hashlib, io, json, time, zipfile
from concurrent.futures import ThreadPoolExecutor
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'stage09_delivery'

def digest(b): return hashlib.sha256(b).hexdigest()

def eligible(p):
    return p.is_file() and '__pycache__' not in p.parts and not any(
        x.endswith(('.tmp','.pyc','.part')) or x.startswith('.tmp') for x in p.parts
    ) and not p.name.endswith('.log')

def select():
    results=[]; geometry=[]
    for dirname in ['stage03_response','stage04_components','stage04_geometry',
                    'stage07_summary','stage08_figures','stage09_report']:
        for p in sorted((ROOT/dirname).rglob('*')):
            if not eligible(p): continue
            if p.name=='PATH_CHANGE_EVENTS.csv.gz': continue
            if p.name=='GEOMETRY_PAIR_EVENTS.csv.gz': geometry.append(p)
            else: results.append(p)
    for name in [
        'stage01_intake/INPUT_LOCK.json',
        'stage00_doorway_sources/CURRENT439_CAPACITY_PANELS.csv',
        'stage00_doorway_sources/CURRENT439_MEMBERSHIP_AUDIT.json',
        'stage00_doorway_sources/CURRENT439_POOL_CAPACITY.csv',
        'stage00_doorway_sources/SOURCE_AUDIT_ZH.txt',
        'stage09_delivery/FINAL_SCOPE.json',
        'stage09_delivery/REPORT_PRESENTATION_QA.json',
        'stage09_delivery/MINIMUM_INPUT_REPRO_CHECK.json',
        'stage09_delivery/PATH_EVENT_PACKAGE_MANIFEST.csv',
        'stage09_delivery/PATH_EVENT_PACKAGE_VALIDATION.json',
        'stage09_delivery/REPRODUCTION_INPUT_PACKAGE_MANIFEST.csv',
        'stage09_delivery/REPRODUCTION_INPUT_PACKAGE_VALIDATION.json',
    ]:
        p=ROOT/name
        assert p.is_file(),name
        results.append(p)
    assert len(results)==len(set(results))
    assert len(geometry)==len(set(geometry))
    return {'02_Results_Report_and_Figures.zip':results,
            '07_Geometry_Pair_Events.zip':geometry}

def package(item):
    name, paths=item; start=time.monotonic()
    dest=ROOT/'delivery'/name; temp=dest.with_suffix('.zip.tmp')
    if dest.exists(): raise FileExistsError(dest)
    manifests=[]
    with zipfile.ZipFile(temp,'w',allowZip64=True) as z:
        for p in paths:
            rel=p.relative_to(ROOT).as_posix();member=ROOT.name+'/'+rel
            b=p.read_bytes()
            info=zipfile.ZipInfo(member,date_time=(2026,11,1,0,0,0))
            info.compress_type=(zipfile.ZIP_STORED if p.suffix in {'.gz','.png','.pdf','.zip'}
                                else zipfile.ZIP_DEFLATED)
            info.external_attr=0o100644<<16
            z.writestr(info,b)
            manifests.append({'package_name':name,'relative_path':rel,'archive_member':member,
                              'source_bytes':len(b),'source_sha256':digest(b)})
    gzip_n=csv_n=pdf_n=rows_n=0
    with zipfile.ZipFile(temp) as z:
        assert z.testzip() is None
        assert len(z.namelist())==len(set(z.namelist()))==len(paths)
        for rec in manifests:
            b=z.read(rec['archive_member'])
            assert digest(b)==rec['source_sha256'],rec['relative_path']
            rec['archive_member_sha256']=digest(b)
            rec['source_equals_archive']=True
            content=b
            if rec['relative_path'].endswith('.gz'):
                content=gzip.decompress(b) # validates every member through EOF
                gzip_n+=1;rec['gzip_eof_passed']=True
                rec['uncompressed_sha256']=digest(content)
                rec['uncompressed_bytes']=len(content)
            if rec['relative_path'].endswith(('.csv','.csv.gz')):
                rd=csv.reader(io.StringIO(content.decode('utf-8-sig'),newline=''))
                header=next(rd,None);n=0
                for row in rd:
                    assert header is not None and len(row)==len(header),(rec['relative_path'],n+2)
                    n+=1
                rec['csv_data_rows']=n;rec['csv_columns']=len(header or [])
                csv_n+=1;rows_n+=n
            if rec['relative_path'].endswith('.json'):
                json.loads(content.decode('utf-8-sig'));rec['json_parsed']=True
            if rec['relative_path'].endswith('.pdf'):
                reader=PdfReader(io.BytesIO(b));rec['pdf_pages']=len(reader.pages);pdf_n+=1
                for pg in reader.pages:
                    assert float(pg.mediabox.width)>0
    temp.replace(dest)
    report={'status':'passed','package_name':name,'bytes':dest.stat().st_size,
            'sha256':digest(dest.read_bytes()),'files':len(paths),'gzip_files':gzip_n,
            'csv_files':csv_n,'csv_data_rows':rows_n,'pdf_files':pdf_n,
            'all_zip_crc_passed':True,'all_inner_gzip_eof_passed':True,
            'all_source_member_hashes_match':True,'all_csv_column_counts_valid':True,
            'elapsed_seconds':round(time.monotonic()-start,3)}
    stem='RESULTS' if name.startswith('02') else 'GEOMETRY_EVENT'
    keys=sorted({k for r in manifests for k in r})
    with (OUT/(stem+'_PACKAGE_MANIFEST.csv')).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(manifests)
    (OUT/(stem+'_PACKAGE_VALIDATION.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2))
    return report

if __name__=='__main__':
    selection=select()
    plan={n:{'files':len(ps),'bytes':sum(p.stat().st_size for p in ps)} for n,ps in selection.items()}
    (OUT/'RESULTS_PACKAGING_PLAN.json').write_text(json.dumps(plan,indent=2))
    print(json.dumps(plan),flush=True)
    with ThreadPoolExecutor(max_workers=2) as ex:
        for result in ex.map(package,selection.items()):print(json.dumps(result),flush=True)
