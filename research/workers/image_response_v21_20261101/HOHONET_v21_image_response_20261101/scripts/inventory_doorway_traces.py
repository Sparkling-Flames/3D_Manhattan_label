#!/usr/bin/env python3
"""Map current doorway teams to already saved full-state traces, without replay."""
import argparse,json,zipfile
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT);a=p.parse_args();r=a.root.resolve()
    out=r/'stage00_doorway_sources';src=r/'stage02_normalized/doorway'
    z=zipfile.ZipFile(r/'source/cache/DOORWAY_04_PHYSICAL_GEOMETRY.zip')
    name='HOHONET_doorway_v21_20261031/stage04_computation/ENDPOINT_TARGET_SCORES.csv.gz'
    cols=['physical_team_key','image','k','target','B8L2','nodes','complete_evaluable','geometry_status',
          'full_state_pointer','full_state_retained','cached_source_file','cached_source_team_key',
          'selected_nodes_unavailable_from_compact_cache','endpoint_origin','endpoint_file']
    with z.open(name) as f:d=pd.read_csv(f,compression='gzip',usecols=cols,low_memory=False)
    sources=pd.read_csv(src/'ENDPOINT_SOURCES.csv.gz',usecols=['endpoint_source_key','team_key','member_object_ids','member_workers'])
    d=d.merge(sources,left_on='physical_team_key',right_on='endpoint_source_key',how='inner',validate='many_to_one')
    full=d[d.full_state_pointer.notna()].copy()
    full['trace_relative_path']=full.full_state_pointer.str.split('#',n=1).str[0]
    full['trace_line']=full.full_state_pointer.str.extract(r'#L(\d+)$',expand=False)
    full['candidate_repo_path']='research/workers/personnel_population_curves_v2_20261023/sampling_extension_20261026/'+full.trace_relative_path
    group=full.groupby('candidate_repo_path').agg(teams=('team_key','nunique'),images=('image',lambda x:'|'.join(sorted(set(x)))),ks=('k',lambda x:'|'.join(str(k) for k in sorted(set(x))))).reset_index()
    registry=r/'source/repo/research/workers/personnel_population_curves_v2_20261023/sampling_extension_20261026/LOCAL_SOURCE_FILES.csv'
    package_count=None
    if registry.exists():
        meta=pd.read_csv(registry)
        meta=meta[meta.archive_path.isin(group.candidate_repo_path)]
        group=group.merge(meta,left_on='candidate_repo_path',right_on='archive_path',how='left',validate='one_to_one')
        assert group.source_package.notna().all()
        full=full.merge(group[['candidate_repo_path','source_package','package_member','archive_path','bytes','disposition']],on='candidate_repo_path',how='left',validate='many_to_one')
        packages=group.groupby('source_package').agg(files=('archive_path','size'),trace_bytes=('bytes','sum')).reset_index()
        packages.to_csv(out/'CURRENT_DOORWAY_FULL_STATE_PACKAGE_SUMMARY.csv',index=False)
        package_count=len(packages)
    full.to_csv(out/'CURRENT_DOORWAY_FULL_STATE_CANDIDATES.csv',index=False)
    group.to_csv(out/'CURRENT_DOORWAY_FULL_STATE_FILES.csv',index=False)
    full.groupby(['image','k']).agg(teams=('team_key','nunique')).reset_index().to_csv(out/'CURRENT_DOORWAY_FULL_STATE_CAPACITY.csv',index=False)
    receipt={'current_legacy_target_rows':len(d),'current_full_state_target_rows':len(full),
             'current_full_state_teams':full.team_key.nunique(),'trace_files':len(group),
             'images':full.image.nunique(),'registered_source_packages':package_count,
             'candidate_paths_status':'relative source pointer expanded and registry mapped; first exact expanded GitHub full_state path probed 404; retrieve registered source ZIP before claiming state locally available',
             'native439_trace_limit':'native JSONL stores selected supports, geometry and score only; no unselected groups or connection alternatives',
             'new_fusion_runs':0}
    (out/'CURRENT_DOORWAY_FULL_STATE_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2));print(json.dumps(receipt,ensure_ascii=False));print(full[['image','k','cached_source_file','full_state_pointer','candidate_repo_path']].head(3).to_json(orient='records'))
if __name__=='__main__':main()
