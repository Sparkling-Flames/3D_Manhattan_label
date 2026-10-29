"""Read every completed audit CSV/gzip/JSON before packaging."""
from pathlib import Path
import ast, gzip, hashlib, json
import pandas as pd

ROOT=Path(__file__).resolve().parent

def main():
    checked=[]
    def digest(path):
        h=hashlib.sha256()
        with path.open('rb') as f:
            while data:=f.read(1024*1024):h.update(data)
        return h.hexdigest()
    for dirname in ['results','extended_capacity','new_registration_audit','completed_supplement']:
        for p in sorted((ROOT/dirname).rglob('*')):
            if not p.is_file():continue
            row=dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,sha256=digest(p))
            if p.suffix=='.gz':
                with gzip.open(p,'rb') as f:
                    while f.read(1024*1024):pass
            if p.name.endswith('.csv') or p.name.endswith('.csv.gz'):
                d=pd.read_csv(p,low_memory=False)
                row.update(rows=len(d),columns=len(d.columns),all_bytes_read=True)
            elif p.suffix=='.json':
                json.loads(p.read_text());row.update(json_valid=True,all_bytes_read=True)
            else:continue
            checked.append(row)
    scripts=list(sorted(ROOT.glob('*.py')))
    documents=list(sorted(ROOT.glob('*.md')))
    for p in scripts+documents:
        content=p.read_text(encoding='utf-8')
        if p.suffix=='.py':ast.parse(content)
        checked.append(dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,sha256=digest(p),
                            all_bytes_read=True,python_AST_valid=p.suffix=='.py'))
    pd.DataFrame(checked).to_csv(ROOT/'FINAL_READABILITY_INVENTORY.csv',index=False,encoding='utf-8-sig')
    receipt=dict(checked_files=len(checked),all_succeeded=True,checked_gzip_crc=True,csv_parsed_to_end=True,
                 source_scripts_AST_parsed=len(scripts),utf8_documents_read=len(documents),all_files_SHA256_recorded=True)
    (ROOT/'FINAL_READABILITY_CHECK.json').write_text(json.dumps(receipt,indent=2))
    print(json.dumps(receipt))

if __name__=='__main__':main()
