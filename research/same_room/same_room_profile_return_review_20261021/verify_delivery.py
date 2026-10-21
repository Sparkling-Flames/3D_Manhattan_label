from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parent

def main():
 files=json.loads((ROOT/'DELIVERY_FILES.json').read_text(encoding='utf-8'))
 for r in files:
  assert hashlib.sha256((ROOT/r['path']).read_bytes()).hexdigest()==r['sha256'],r['path']
 print(f"PASS: {len(files)} curated delivery files; omitted intermediates are listed in DELIVERY_SELECTION.json")
if __name__=='__main__':main()
