"""Rebuild only the 18 omitted derived tables; do not fuse or change inputs."""
from pathlib import Path
import importlib.util
import json
import warnings
from types import SimpleNamespace
import pandas as pd

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'unpacked/05'


def main():
    warnings.filterwarnings('ignore', category=pd.errors.PerformanceWarning)
    manifest = pd.read_csv(ROOT/'MANIFEST_PRESENCE_CHECK.csv')
    missing = manifest.loc[~manifest.present, 'resolved'].tolist()
    assert len(missing) == 18
    rows = []
    for stage, filename in [('size_paths','analyze_fixed_block_paths.py'), ('large_team_ac_tail','analyze_ac_tail.py')]:
        path = SOURCE/'analysis'/stage/'code'/filename
        spec = importlib.util.spec_from_file_location('rebuild_'+stage, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        helper = module if stage == 'size_paths' else module.hp
        expected = {Path(name).name for name in missing if name.startswith('analysis/'+stage+'/')}
        save = helper.save_csv
        def keep_missing(frame, target):
            if Path(target).name in expected:
                save(frame, target)
        helper.save_csv = keep_missing
        helper.sha = lambda path: 'not_recomputed_in_local_recovery'
        out = ROOT/'recovered_derived'/stage
        module.ROOT = ROOT
        args = SimpleNamespace(design=SOURCE/'design'/stage,metrics=SOURCE/'results'/stage/'EVENT_METRICS.csv.gz',
                               output=out,prepare=False,allow_partial=False,no_plots=True)
        if not all((out/name).is_file() for name in expected):
            module.main(args)
        for name in sorted(expected):
            p = out/name
            d = pd.read_csv(p,low_memory=False)
            assert len(d)>0 and d.shape[1]>0
            rows.append({'logical_path':'analysis/'+stage+'/'+name,'recovered_path':p.relative_to(ROOT).as_posix(),
                         'rows':len(d),'columns':len(d.columns),'bytes':p.stat().st_size})
    assert len(rows)==18
    (ROOT/'DERIVED_RECOVERY.json').write_text(json.dumps({'no_fusion':True,'source':'saved stage05 event metrics and delivered analysis code',
      'identity':'locally regenerated derived tables; not recovered original bytes','files':rows},ensure_ascii=False,indent=2),encoding='utf-8')


if __name__ == '__main__':
    main()
