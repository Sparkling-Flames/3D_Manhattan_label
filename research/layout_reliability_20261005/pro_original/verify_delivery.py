from pathlib import Path
import hashlib,json
r=Path(__file__).resolve().parent
m=json.loads((r/"MANIFEST.json").read_text())
bad=[]
for f in m["files"]:
 p=r/f["path"]
 if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=f["sha256"]:bad.append(f["path"])
print({"checked":len(m["files"]),"mismatches":bad})
raise SystemExit(bool(bad))
