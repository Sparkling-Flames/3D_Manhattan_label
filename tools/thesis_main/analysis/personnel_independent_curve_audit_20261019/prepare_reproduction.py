"""Prepare a new reproduction directory without changing frozen inputs."""
import argparse, pathlib, shutil, ast
p=argparse.ArgumentParser();p.add_argument("input_root",type=pathlib.Path);p.add_argument("--evidence",required=True,type=pathlib.Path);a=p.parse_args();root=a.input_root.resolve();e=a.evidence.resolve()
assert (root/"extracted/work_v2_20261019").is_dir(), "Extract all four archives into input_root/extracted first"
assert not (root/"independent").exists(), "Use a new reproduction root to avoid overwriting outputs"
scripts=pathlib.Path(__file__).parent/"scripts"
for src in scripts.rglob("*.py"):
 dst=root/"independent"/src.relative_to(scripts);dst.parent.mkdir(parents=True,exist_ok=True)
 text=src.read_text().replace("/workspace/shared/personnel_v2_audit_20261018",str(root));ast.parse(text);dst.write_text(text)
for src in (e/"source").glob("official_*.json"):shutil.copy2(src,root/"independent"/src.name)
for name in ["DESIGN.json","REGISTRATION.json","DESIGN_RECEIPT.json"]:shutil.copy2(e/"curves"/name,root/"independent/curves"/name)
print("Prepared scripts and frozen curve design under",root/"independent")
