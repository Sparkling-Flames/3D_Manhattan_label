"""Recompute the new large-block analyses from the saved exact endpoints.

No fusion, class fitting, team selection or original-image download occurs.
Run from the study root, or provide --root. Population bootstrap is a separate
study with its own inputs and run instructions.
"""
import argparse,subprocess,sys
from pathlib import Path

def main(root):
    r=Path(root).resolve();s=r/'analysis'
    calls=[
      ['build_events.py','--design',r/'design/STRICT_ABC_EVENTS.csv.gz','--native',r/'native_endpoints/ENDPOINT_SCALARS.csv.gz','--out',r/'results'],
      ['summarize_conditions.py','--events',r/'results/EVENT_Q_STRUCTURE_EFFECTS.csv.gz','--out',r/'results'],
      ['member_sensitivity.py','--events',r/'results/EVENT_Q_STRUCTURE_EFFECTS.csv.gz','--out',r/'sensitivity'],
      ['summarize_geometry.py','--events',r/'results/EVENT_Q_STRUCTURE_EFFECTS.csv.gz','--geometry',r/'geometry/EVENT_GEOMETRY_RESULTS.csv.gz','--out',r/'geometry_summary'],
      ['history_q_common_support.py','--events',r/'results/EVENT_Q_STRUCTURE_EFFECTS.csv.gz','--geometry',r/'geometry_summary/EVENT_GEOMETRY_COMMON_SUPPORT.csv.gz','--out',r/'history_q'],
      ['analyze_anchor_paths.py','--design-dir',r/'design','--native',r/'native_endpoints/ENDPOINT_SCALARS.csv.gz','--out',r/'anchor_paths'],
      ['report_anchor_paths.py','--root',r],
      ['build_reader_tables.py','--root',r],
      ['render_direction_tables.py','--design-dir',r/'design','--direction-results',r/'results/DIRECTION_RESULTS.csv','--out',r/'direction_tables'],
      ['make_figures.py','--root',r],
      ['build_final_report.py','--root',r],
    ]
    for call in calls:
        cmd=[sys.executable,str(s/call[0]),*[str(x) for x in call[1:]]]
        print('Running',call[0],flush=True);subprocess.run(cmd,check=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',default='.')
    a=p.parse_args();main(a.root)
