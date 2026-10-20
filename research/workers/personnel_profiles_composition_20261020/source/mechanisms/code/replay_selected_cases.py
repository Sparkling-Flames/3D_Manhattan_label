"""Recompute saved illustrative teams with HOHONET's unchanged native pipeline.

Uses repository inputs, not a new reference, preprocessing, score, or fusion
rule. Replays are diagnostics of existing teams and must not be counted as
additional independent teams or pictures in the study's effectiveness totals.
"""
from __future__ import annotations
import argparse,csv,gzip,json,math,os,sys
from pathlib import Path

FUSION_REL='research/workers/pro_personnel_v2_archive_20261019/work_v2_20261019/fusion'


def read(p):
 p=Path(p);return json.loads(gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_bytes())


def main():
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('--repo',required=True,type=Path)
 ap.add_argument('--case',type=Path,nargs='+',default=[])
 ap.add_argument('--paths',type=Path,help='Optional complete-path CSV with pool_id, member_workers and scores.')
 ap.add_argument('--out',required=True,type=Path)
 a=ap.parse_args();assert a.case or a.paths,'Provide --case and/or --paths.'
 repo=a.repo.resolve();sys.path.insert(0,str(repo));os.environ['PERSONNEL_V2_REPOSITORY']=str(repo)
 from tools.thesis_main.analysis.fusion_change_mechanisms_20261020 import engine,normalized_state
 fe=engine();pools={p['pool_id']:p for p in read(repo/FUSION_REL/'INPUT_SNAPSHOT.json.gz')['images']}
 requests={}
 for file in a.case:
  case=read(file);pool=pools[case['pool_id']];by_id={r['object_id']:r for r in pool['records']}
  # Case geometry is a retained snapshot of actual admitted input, not an edit.
  for r in case['records']:
   assert r['points_1024x512']==by_id[r['object_id']]['points'],r['object_id']
  assert case['reference']['points_1024x512']==pool['reference']['points_1024x512']
  for p in case['panels']:
   requests[p['team_key']]=dict(pool_id=case['pool_id'],workers=sorted(p['score']['member_workers']),expected_points=p['state']['candidate']['points'],B8L2=p['score']['B8L2'],D10=p['score']['D10'],source_case=str(file))
 if a.paths:
  for r in csv.DictReader(a.paths.open(encoding='utf-8-sig')):
   if r['team_key'] not in requests:requests[r['team_key']]=dict(pool_id=r['pool_id'],workers=r['member_workers'].split('|'),B8L2=float(r['B8L2']),D10=float(r['D10']),source_case=str(a.paths))
 rows=[]
 with fe.cached_matching(),fe.scoring_engine(fe.ENGINE/'measurement_engine.zip',fe.ENGINE/'working_models.py') as (scorer,models):
  for key,r in requests.items():
   pool=pools[r['pool_id']];by={x['worker_id']:x for x in pool['records']};state=normalized_state(fe.compact(fe.fuse([by[w] for w in sorted(r['workers'])],gap=fe.WORKING_GAP)['automatic']))
   geometry_equal=(state['candidate']['points']==r['expected_points']) if 'expected_points' in r else None
   if geometry_equal is False:raise AssertionError('Geometry changed: '+key)
   score=fe.compute_score(state,pool,scorer,models)
   for field in ('B8L2','D10'):
    actual,expected=score[field],r[field]
    assert actual is not None and expected is not None and math.isclose(actual,expected,rel_tol=1e-10,abs_tol=1e-7),(key,field,actual,expected)
   rows.append(dict(team_key=key,pool_id=r['pool_id'],member_workers=r['workers'],B8L2=score['B8L2'],D10=score['D10'],geometry_exact_match=geometry_equal,minimum_support=state['minimum_support'],node_count=len(state['candidate']['points'])//2,source_case=r['source_case'],identity_groups=state['identity_groups'],ring_diagnostics=state['ring_diagnostics']))
 a.out.parent.mkdir(parents=True,exist_ok=True)
 a.out.write_text(json.dumps(fe.clean(dict(purpose='replay saved teams; not new effectiveness observations',working_gap_degrees=fe.WORKING_GAP,replayed_unique_teams=len(rows),results=rows)),ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(dict(replayed_unique_teams=len(rows),out=str(a.out)),ensure_ascii=False))

if __name__=='__main__':main()
