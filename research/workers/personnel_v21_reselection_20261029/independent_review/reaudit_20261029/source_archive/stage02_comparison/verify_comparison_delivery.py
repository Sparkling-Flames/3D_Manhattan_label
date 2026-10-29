"""Read every delivered CSV/JSON/GZIP member and record content hashes."""
from pathlib import Path
import ast,csv,gzip,hashlib,io,json

ROOT=Path(__file__).resolve().parent
inventory=[]
for path in sorted(ROOT.rglob('*')):
    if not path.is_file() or '__pycache__' in path.parts or path.name in ['DELIVERY_READABILITY_INVENTORY.csv','DELIVERY_READABILITY_RECEIPT.json']:
        continue
    data=path.read_bytes();item={'path':str(path.relative_to(ROOT)),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'read_check':'binary_read'}
    if path.suffix=='.gz':
        decoded=gzip.decompress(data);item['uncompressed_bytes']=len(decoded)
        if path.name.endswith('.csv.gz'):
            reader=csv.reader(io.StringIO(decoded.decode('utf-8-sig')))
            header=next(reader,None);width=len(header or []);n=0
            for row in reader:
                if not row:continue
                assert len(row)==width,(path,n,len(row),width)
                n+=1
            item.update(read_check='gzip_crc_and_complete_csv',rows=n,columns=width)
        else:item['read_check']='complete_gzip_crc'
    elif path.suffix=='.csv':
        reader=csv.reader(io.StringIO(data.decode('utf-8-sig')))
        header=next(reader,None);width=len(header or []);n=0
        for row in reader:
            if not row:continue
            assert len(row)==width,(path,n,len(row),width)
            n+=1
        item.update(read_check='complete_csv',rows=n,columns=width)
    elif path.suffix=='.json':json.loads(data.decode('utf-8-sig'));item['read_check']='json_parse'
    elif path.suffix=='.py':ast.parse(data.decode('utf-8-sig'));item['read_check']='python_ast'
    inventory.append(item)
with (ROOT/'DELIVERY_READABILITY_INVENTORY.csv').open('w',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=['path','bytes','sha256','read_check','uncompressed_bytes','rows','columns']);writer.writeheader();writer.writerows(inventory)
receipt=dict(files=len(inventory),bytes=sum(x['bytes'] for x in inventory),all_readable=True,
    csv_files=sum('csv' in x['read_check'] for x in inventory),gzip_files=sum('gzip' in x['read_check'] for x in inventory),
    purpose='Complete member readability; the parent separately verifies final zip archives. Exact numerical crosschecks are in abc_integrated/INDEPENDENT_Q_IDENTITY_CROSSCHECK.json and conditional_results completion receipts.')
(ROOT/'DELIVERY_READABILITY_RECEIPT.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))
