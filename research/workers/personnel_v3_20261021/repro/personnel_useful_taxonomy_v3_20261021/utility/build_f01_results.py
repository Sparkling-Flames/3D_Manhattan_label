"""Compact, independently addressable completed F01 result package."""
from pathlib import Path
import json,zipfile
import pandas as pd
from prepare_training import HERE,atomic_csv,atomic_json,sha

def main():
    files=[p for p in HERE.glob('F01_*') if p.is_file() and not p.name.startswith('F01_RESULTS_PACKAGE_')]
    files+=list(HERE.glob('FIGURE_F01_*.png'))+list(HERE.glob('FIGURE_F01_*.svg'))
    files+=list((HERE/'f01_finite_LOBO/manual/F01_fixed_history').rglob('*'))
    files=[p for p in files if p.is_file() and not p.name.endswith('.partial')]
    names=['run_f01_finite_utility.py','summarize_f01_configurations.py','summarize_f01_policies.py',
        'plot_f01_configurations.py','build_f01_results.py','policy_study.py','prepare_training.py',
        'summarize_policy.py','REPRODUCE_UTILITY_ZH.md']
    files+= [HERE/n for n in names]
    files=sorted(set(files));assert all(p.exists() for p in files)
    manifest=HERE/'F01_RESULTS_PACKAGE_MANIFEST.csv'
    atomic_csv(pd.DataFrame([dict(path=str(p.relative_to(HERE)),bytes=p.stat().st_size,sha256=sha(p)) for p in files]),manifest)
    files.append(manifest)
    out=HERE/'HOHONET_v3_F01_完整配比与实际选择用途_20261021.zip'
    temp=out.with_name(out.name+'.partial')
    with zipfile.ZipFile(temp,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in files:z.write(p,arcname=str(Path('utility')/p.relative_to(HERE)))
    with zipfile.ZipFile(temp) as z:assert z.testzip() is None
    temp.replace(out)
    receipt=dict(status='complete',path=str(out),bytes=out.stat().st_size,sha256=sha(out),files=len(files),
        report_path=str(HERE/'F01_FINDINGS_ZH.md'),report_sha256=sha(HERE/'F01_FINDINGS_ZH.md'),
        native_endpoints_reference='../composition/batches/f01_001/',
        immutable_input_identity='frozen F01 historical10 labels; registered full n12 member domain',
        native_teams=1874,complete_configuration_cells=37,selection_panels=12,selection_policies=19)
    atomic_json(receipt,HERE/'F01_RESULTS_PACKAGE_RECEIPT.json')
    print(json.dumps(receipt,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
