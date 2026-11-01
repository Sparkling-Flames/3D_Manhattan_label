#!/usr/bin/env python3
"""Read every case artifact completely, render every PDF page, syntax-check viewers."""
from pathlib import Path
import csv,gzip,hashlib,json,subprocess,tempfile,xml.etree.ElementTree as ET
from io import StringIO
from PIL import Image
import fitz

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'stage05_cases/manual'
records=[];renderdir=ROOT/'tmp/manual_case_pdf_readback';renderdir.mkdir(parents=True,exist_ok=True)
for p in sorted(OUT.rglob('*')):
    if not p.is_file() or p.name in ['VALIDATION_MANIFEST.csv','VALIDATION_RECEIPT.json']:continue
    if '.writing' in p.name:raise RuntimeError('Unexpected unfinished artifact: '+str(p))
    data=p.read_bytes();kind=p.suffix.lower();n=None;check='full byte read'
    if kind=='.gz':
        decoded=gzip.decompress(data).decode('utf-8-sig')
        if p.name.endswith('.csv.gz'):n=sum(1 for _ in csv.reader(StringIO(decoded)))-1;check='gzip CRC and all CSV rows'
        elif p.name.endswith('.json.gz'):obj=json.loads(decoded);check='gzip CRC and complete JSON';n=len(obj)
        else:check='gzip CRC and complete decoded text'
    elif kind=='.csv':n=sum(1 for _ in csv.reader(StringIO(data.decode('utf-8-sig'))))-1;check='all CSV rows'
    elif kind=='.json':obj=json.loads(data);n=len(obj) if isinstance(obj,(list,dict)) else 1;check='complete JSON'
    elif kind=='.png':
        with Image.open(p) as im:im.load();n=im.width*im.height
        check='complete pixel decode'
    elif kind=='.pdf':
        doc=fitz.open(p);n=len(doc)
        for page in doc:
            pix=page.get_pixmap(matrix=fitz.Matrix(1,1),alpha=False)
            f=renderdir/(str(p.relative_to(OUT)).replace('/','__')+f'.page{page.number+1}.png');pix.save(f)
            with Image.open(f) as im:im.load()
        doc.close();check='all PDF pages rendered and decoded'
    elif kind=='.svg':ET.fromstring(data);check='complete XML parse'
    elif kind=='.html':
        text=data.decode('utf8');script=text.split('<script>',1)[1].split('</script>',1)[0]
        with tempfile.NamedTemporaryFile(suffix='.js',mode='w') as js:
            js.write(script);js.flush();subprocess.run(['node','--check',js.name],check=True,capture_output=True)
        check='complete UTF8 and JavaScript syntax'
    else:data.decode('utf-8-sig');check='complete UTF8 text'
    records.append(dict(path=str(p.relative_to(ROOT)),bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),
        check=check,rows_or_pages_or_pixels=n,valid=True))
with (OUT/'VALIDATION_MANIFEST.csv').open('w',newline='',encoding='utf8') as f:
    w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(records)
summary=dict(files=len(records),bytes=sum(r['bytes'] for r in records),invalid_files=0,
    gz_files=sum(r['path'].endswith('.gz') for r in records),pdf_files=sum(r['path'].endswith('.pdf') for r in records),
    png_files=sum(r['path'].endswith('.png') for r in records),html_files=sum(r['path'].endswith('.html') for r in records),
    manifest='VALIDATION_MANIFEST.csv',new_scientific_teams=0,new_natural_paths=0,new_formal_quality_scores=0,
    diagnostic_existing_team_replays=1 if (OUT/'VFuaQ6m2Qom-04/FULL35_DIAGNOSTIC_RECEIPT.json').exists() else 0)
(OUT/'VALIDATION_RECEIPT.json').write_text(json.dumps(summary,indent=2),encoding='utf8')
print(json.dumps(summary,indent=2))
