"""Validate final delivery files without recalculating any research result.

Examples:
  python code/validate_delivery_files.py --stages stage00_intake stage01_classification --prefix CORE
  python code/validate_delivery_files.py --stages stage04_cases stage05_synthesis stage06_reproduction --prefix REMAINING

Every selected file receives a SHA256. CSV/TSV are read to EOF with width
checks, JSON/JSONL are parsed, gzip CRC is exercised through EOF, ZIP/Office
archives are read member by member (including nested containers), PDF pages
are loaded with PyMuPDF, and raster images are verified and fully decoded.
No source file or pre-existing manifest is modified.
"""
from __future__ import annotations
import argparse,csv,gzip,hashlib,io,json,os,shutil,sys,tarfile,tempfile,time,zipfile
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
import xml.etree.ElementTree as ET

CHUNK=1024*1024
TEXT_SUFFIXES={'.md','.txt','.py','.js','.mjs','.cjs','.ts','.tsx','.jsx','.css','.scss','.html','.htm',
               '.sql','.yaml','.yml','.toml','.ini','.cfg','.conf','.log','.tex','.bib','.sh','.bash','.zsh',
               '.ps1','.bat','.c','.cpp','.cc','.h','.hpp','.r','.R','.rst','.env','.lock'}
ZIP_SUFFIXES={'.zip','.docx','.xlsx','.pptx','.odt','.ods','.odp','.npz'}
IMAGE_SUFFIXES={'.png','.jpg','.jpeg','.webp','.gif','.tif','.tiff','.bmp','.ico'}
TEMP_SUFFIXES=('.writing','.tmp','.temp','.partial','.incomplete','~','.pyc','.pyo')
FIELDS=['path','stage','bytes','sha256','status','checks','seconds','csv_files','csv_rows','csv_blank_rows',
        'csv_min_columns','csv_max_columns','csv_width_violations','json_documents','jsonl_files','jsonl_records',
        'jsonl_blank_lines','json_nonfinite_constants','gzip_streams','gzip_uncompressed_bytes','zip_archives',
        'zip_members','tar_archives','tar_members','pdf_files','pdf_pages','image_files','image_frames',
        'text_files','text_lines','xml_files','binary_files','errors_json']
COUNTERS=[x for x in FIELDS if x not in ['path','stage','bytes','sha256','status','checks','seconds',
                                     'csv_min_columns','csv_max_columns','errors_json']]

class Audit:
    def __init__(self):
        self.counts=Counter();self.checks=set();self.errors=[];self.csv_widths=[]
    def error(self,name,message):
        if len(self.errors)<50:self.errors.append({'member':name,'error':str(message)})
        self.counts['error_count']+=1
    def nonfinite(self,value):
        # Frozen historical JSON uses Python's NaN/Infinity-compatible reader.
        # Count these tokens transparently; they are not replaced in the source.
        self.counts['json_nonfinite_constants']+=1
        return float(value)

def drain(stream):
    while stream.read(CHUNK):pass

def text_reader(stream):
    return io.TextIOWrapper(stream,encoding='utf-8-sig',errors='strict',newline='')

def parse_csv(stream,name,audit,delimiter=','):
    audit.counts['csv_files']+=1;audit.checks.add('csv_utf8_EOF_and_consistent_width')
    wrapper=text_reader(stream)
    try:
        reader=csv.reader(wrapper,delimiter=delimiter);width=None;rowno=0
        for row in reader:
            if not row:audit.counts['csv_blank_rows']+=1;continue
            if width is None:width=len(row);audit.csv_widths.append(width);continue
            rowno+=1;audit.counts['csv_rows']+=1
            if len(row)!=width:
                audit.counts['csv_width_violations']+=1
                audit.error(name,f'CSV record {rowno}: {len(row)} fields, header has {width}; physical line {reader.line_num}')
        if width is None:audit.csv_widths.append(0)
    finally:wrapper.detach()

def parse_jsonl(stream,name,audit):
    audit.counts['jsonl_files']+=1;audit.checks.add('jsonl_utf8_parse_each_record_to_EOF')
    wrapper=text_reader(stream)
    try:
        for no,line in enumerate(wrapper,1):
            if not line.strip():audit.counts['jsonl_blank_lines']+=1;continue
            audit.counts['jsonl_records']+=1
            try:json.loads(line,parse_constant=audit.nonfinite)
            except Exception as exc:audit.error(name,f'JSONL line {no}: {type(exc).__name__}: {exc}')
    finally:wrapper.detach()

def parse_text(stream,audit):
    audit.counts['text_files']+=1;audit.checks.add('text_utf8_decode_to_EOF')
    wrapper=text_reader(stream)
    try:
        for _ in wrapper:audit.counts['text_lines']+=1
    finally:wrapper.detach()

def parse_zip(stream,name,audit,depth):
    audit.counts['zip_archives']+=1;audit.checks.add('zip_every_member_read_to_EOF_and_CRC')
    # Spooling first also verifies the containing ZipExtFile/gzip through EOF.
    with tempfile.SpooledTemporaryFile(max_size=16*CHUNK,mode='w+b') as spool:
        shutil.copyfileobj(stream,spool,CHUNK);spool.seek(0)
        with zipfile.ZipFile(spool) as archive:
            for info in archive.infolist():
                if info.is_dir():continue
                audit.counts['zip_members']+=1;child=name+'!/'+info.filename
                try:
                    with archive.open(info,'r') as member:validate_stream(member,child,audit,depth+1)
                except Exception as exc:audit.error(child,f'{type(exc).__name__}: {exc}')

def parse_pdf(stream,name,audit):
    import fitz
    audit.counts['pdf_files']+=1;audit.checks.add('pdf_open_and_load_every_page')
    data=stream.read()
    with fitz.open(stream=data,filetype='pdf') as doc:
        if doc.needs_pass:raise ValueError('PDF needs a password and cannot be inspected')
        for number in range(doc.page_count):
            page=doc.load_page(number);page.get_text('text');audit.counts['pdf_pages']+=1

def parse_image(stream,name,audit):
    from PIL import Image
    audit.counts['image_files']+=1;audit.checks.add('PIL_verify_and_decode_all_frames')
    data=stream.read()
    with Image.open(io.BytesIO(data)) as img:img.verify()
    with Image.open(io.BytesIO(data)) as img:
        for frame in range(getattr(img,'n_frames',1)):
            img.seek(frame);img.load();audit.counts['image_frames']+=1

def validate_stream(stream,name,audit,depth=0):
    """Always drain the stream, even if a format parser fails part way."""
    try:
        if depth>24:raise ValueError('Nested container depth exceeds 24')
        lname=name.lower();suffix=Path(lname).suffix
        if suffix=='.gz':
            audit.counts['gzip_streams']+=1;audit.checks.add('gzip_decompress_to_EOF_and_CRC')
            with gzip.GzipFile(fileobj=stream,mode='rb') as decoded:
                validate_stream(decoded,name[:-3],audit,depth+1)
                audit.counts['gzip_uncompressed_bytes']+=decoded.tell()
        elif suffix in ZIP_SUFFIXES:parse_zip(stream,name,audit,depth)
        elif suffix=='.tar':
            audit.counts['tar_archives']+=1;audit.checks.add('tar_headers_and_members_read_to_EOF')
            with tarfile.open(fileobj=stream,mode='r|') as archive:
                for info in archive:
                    if not info.isfile():continue
                    audit.counts['tar_members']+=1
                    member=archive.extractfile(info)
                    if member is not None:
                        with member:validate_stream(member,name+'!/'+info.name,audit,depth+1)
        elif suffix in ['.csv','.tsv']:parse_csv(stream,name,audit,'\t' if suffix=='.tsv' else ',')
        elif suffix in ['.jsonl','.ndjson']:parse_jsonl(stream,name,audit)
        elif suffix in ['.json','.ipynb']:
            audit.counts['json_documents']+=1;audit.checks.add('json_utf8_parse_complete_document')
            json.loads(stream.read().decode('utf-8-sig'),parse_constant=audit.nonfinite)
        elif suffix=='.pdf':parse_pdf(stream,name,audit)
        elif suffix in IMAGE_SUFFIXES:parse_image(stream,name,audit)
        elif suffix in ['.xml','.rels','.svg']:
            audit.counts['xml_files']+=1;audit.checks.add('XML_parse_complete_document')
            ET.fromstring(stream.read())
        elif suffix in TEXT_SUFFIXES or (not suffix and Path(name).name.upper() in ['README','LICENSE','LICENCE','NOTICE','COPYING','MAKEFILE','DOCKERFILE']):
            parse_text(stream,audit)
        else:
            audit.counts['binary_files']+=1;audit.checks.add('binary_read_to_EOF');drain(stream)
    except Exception as exc:audit.error(name,f'{type(exc).__name__}: {exc}')
    finally:
        try:drain(stream)
        except Exception as exc:audit.error(name,f'EOF/CRC: {type(exc).__name__}: {exc}')

def ignored(parts):
    return any(part.startswith('.') or part=='__pycache__' for part in parts) or parts[-1].endswith(TEMP_SUFFIXES)

def main(args):
    started=time.monotonic();root=Path(args.root).resolve()
    output=Path(args.out_dir).resolve() if args.out_dir else root/'stage07_delivery_validation'
    output.mkdir(parents=True,exist_ok=True)
    prefix=args.prefix
    if not prefix or any(c not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-' for c in prefix):raise ValueError('Use a plain filename prefix')
    csv_path=output/(prefix+'_FILES_READABILITY.csv');receipt_path=output/(prefix+'_FILES_READABILITY_RECEIPT.json')
    if csv_path.exists() or receipt_path.exists():raise FileExistsError('Validation output already exists; choose another prefix to preserve old manifests')
    stage_paths=[(stage,(root/stage).resolve()) for stage in args.stages]
    for stage,path in stage_paths:
        if not path.exists():raise FileNotFoundError(stage)
        if not path.is_relative_to(root):raise ValueError('Stages must remain inside the delivery root')
    files={};ignored_files=0
    for stage,base in stage_paths:
        candidates=[base] if base.is_file() else sorted(base.rglob('*'))
        for path in candidates:
            if not path.is_file():continue
            parts=path.relative_to(root).parts
            if ignored(parts):ignored_files+=1;continue
            files.setdefault(path,stage)
    # Large saved JSON/CSV cells are permitted, while row widths remain checked.
    limit=sys.maxsize
    while True:
        try:csv.field_size_limit(limit);break
        except OverflowError:limit//=10
    totals=Counter();check_types=Counter();stage_summary={};failures=[];rows=[];last_progress=started
    print(json.dumps({'phase':'start','stages':args.stages,'files':len(files),'bytes':sum(p.stat().st_size for p in files)},ensure_ascii=False),flush=True)
    with csv_path.open('x',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=FIELDS);writer.writeheader()
        for index,(path,stage) in enumerate(sorted(files.items(),key=lambda kv:str(kv[0])),1):
            t=time.monotonic();rel=str(path.relative_to(root));a=Audit();sha=hashlib.sha256();nbytes=0
            st0=path.stat()
            try:
                with path.open('rb') as raw:
                    for chunk in iter(lambda:raw.read(CHUNK),b''):sha.update(chunk);nbytes+=len(chunk)
                with path.open('rb') as raw:validate_stream(raw,rel,a)
            except Exception as exc:a.error(rel,f'{type(exc).__name__}: {exc}')
            st1=path.stat()
            if (st0.st_size,st0.st_mtime_ns)!=(st1.st_size,st1.st_mtime_ns):a.error(rel,'File changed while being validated')
            row={'path':rel,'stage':stage,'bytes':nbytes,'sha256':sha.hexdigest(),'status':'FAIL' if a.errors else 'PASS',
                 'checks':'|'.join(sorted(a.checks)),'seconds':round(time.monotonic()-t,6),
                 'csv_min_columns':min(a.csv_widths) if a.csv_widths else '',
                 'csv_max_columns':max(a.csv_widths) if a.csv_widths else '',
                 'errors_json':json.dumps(a.errors,ensure_ascii=False,separators=(',',':'))}
            row.update({k:a.counts[k] for k in COUNTERS});writer.writerow(row);f.flush();rows.append(row)
            totals.update(a.counts);totals['files']+=1;totals['bytes']+=nbytes;check_types.update(a.checks)
            summary=stage_summary.setdefault(stage,Counter());summary['files']+=1;summary['bytes']+=nbytes;summary.update(a.counts)
            if a.errors:failures.append({'path':rel,'errors':a.errors});summary['failed_files']+=1
            if index%25==0 or time.monotonic()-last_progress>=25:
                print(json.dumps({'phase':'progress','files_done':index,'files_total':len(files),'failed_files':len(failures),
                                  'csv_rows':totals['csv_rows'],'jsonl_records':totals['jsonl_records'],'seconds':round(time.monotonic()-started,2)},ensure_ascii=False),flush=True)
                last_progress=time.monotonic()
    # A final read ensures that the newly written inventory itself is readable.
    with csv_path.open(encoding='utf-8-sig',newline='') as f:
        back=list(csv.DictReader(f))
    assert len(back)==len(rows) and all(set(r)==set(FIELDS) for r in back)
    receipt={'completed_utc':datetime.now(timezone.utc).isoformat(),'root':str(root),'stages':args.stages,'prefix':prefix,
             'all_readable':not failures,'files':len(rows),'failed_files':len(failures),'bytes':totals['bytes'],
             'elapsed_seconds':round(time.monotonic()-started,6),'totals':dict(totals),'stage_summary':{k:dict(v) for k,v in stage_summary.items()},
             'check_types':dict(check_types),'ignored_temporary_or_dot_files':ignored_files,'failures':failures,
             'inventory_file':str(csv_path.relative_to(root)) if csv_path.is_relative_to(root) else str(csv_path),
             'inventory_sha256':hashlib.sha256(csv_path.read_bytes()).hexdigest(),
             'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
             'counting_notes':['CSV row counts exclude headers and physically blank CSV records; every nonblank row is width-checked.',
                               'JSONL records exclude blank lines. Container members contribute to content counters and are not extra top-level files.',
                               'Python-compatible NaN/Infinity JSON constants, if present in frozen sources, are counted separately without modifying the source.',
                               'ZIP/Office members are read to EOF for CRC, recursively; no archive members are extracted into the delivery.',
                               'Source files and all pre-existing manifests are unchanged; no research calculations, packaging, or upload.']}
    with receipt_path.open('x',encoding='utf-8') as f:json.dump(receipt,f,ensure_ascii=False,indent=2);f.write('\n')
    print(json.dumps({k:receipt[k] for k in ['all_readable','files','failed_files','bytes','elapsed_seconds','totals']},ensure_ascii=False),flush=True)
    return 0 if not failures else 1

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root',default=str(Path(__file__).resolve().parents[1]))
    ap.add_argument('--stages',nargs='+',required=True)
    ap.add_argument('--prefix',required=True)
    ap.add_argument('--out-dir')
    sys.exit(main(ap.parse_args()))
