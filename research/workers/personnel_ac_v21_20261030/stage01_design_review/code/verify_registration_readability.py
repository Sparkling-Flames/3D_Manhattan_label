"""Full gzip EOF, CSV-width, count and frozen-hash gate for a registration."""
from pathlib import Path
import argparse, csv, gzip, hashlib, json

def verify(directory):
    directory=Path(directory)
    receipt=json.loads((directory/'DESIGN_REGISTRATION_RECEIPT.json').read_text())
    manifest=json.loads((directory/'FROZEN_DESIGN_FILES.json').read_text())['requested_outputs']
    expected={
        'AC_EVENTS.csv.gz':receipt['method_events'],
        'TEAM_REQUESTS.csv.gz':receipt['unique_teams'],
        'DESIGN_LINKS.csv.gz':receipt['design_links'],
        'REGISTERED_AC_CELLS.csv.gz':receipt['registered_A_B_cells'],
        'PHYSICAL_PAIR_METHOD_OVERLAP.csv.gz':receipt['physical_pairs'],
    }
    records=[]
    for path in sorted(directory.glob('*.csv.gz')):
        n=0
        with gzip.open(path,'rt',encoding='utf-8-sig',newline='') as stream:
            rows=csv.reader(stream);header=next(rows)
            assert len(header)==len(set(header)),(path,'duplicate_columns')
            for row in rows:
                assert len(row)==len(header),(path,n,'row_width',len(row),len(header))
                n+=1
        sha=hashlib.sha256(path.read_bytes()).hexdigest()
        assert sha==manifest[path.name]['sha256'],(path,'manifest_hash_mismatch')
        assert path.stat().st_size==manifest[path.name]['bytes'],(path,'manifest_size_mismatch')
        if path.name in expected:assert n==expected[path.name],(path,n,expected[path.name])
        records.append(dict(file=path.name,rows=n,columns=len(header),compressed_bytes=path.stat().st_size,
                            sha256=sha,full_gzip_eof=True,all_csv_row_widths_valid=True))
    result=dict(status='complete',checked_all_csv_gzip_to_eof=True,frozen_manifest_hashes_match=True,
                receipt_counts_match=True,files=records)
    (directory/'REGISTRY_FILE_READABILITY_VALIDATION.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)
    return result

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('directory');verify(ap.parse_args().directory)
