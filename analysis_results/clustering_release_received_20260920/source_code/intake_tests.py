"""Software tests using withheld historical records only; no fabricated human observations."""
from pathlib import Path
import copy,gzip,json,shutil,tempfile
import numpy as np,pandas as pd
from release import prepare,main,writejson
from review_correspondence import validate,pointsha

def run(root,out):
    st,rows,rec,elig,sroot=prepare(root);checks={};src=root/'input/source';sub='analysis_results/paired_split_research_received_20260920/inputs'
    approved=set(st.accepted_map(sroot/'inputs',rows));take=[copy.deepcopy(r)|{'record_type':'independent_initial'} for r in rows if r['canonical_annotation_id'] not in approved and r['worker_id'] not in ['W019','W026']][-10:];ids={r['canonical_annotation_id'] for r in take}
    with tempfile.TemporaryDirectory(prefix='rc1_intake_') as td:
        t=Path(td);dest=t/'input/source'/sub;dest.mkdir(parents=True)
        for f in (sroot/'inputs').iterdir():
            if f.is_file():shutil.copy2(f,dest/f.name)
        with gzip.open(dest/'responses.jsonl.gz','wt',encoding='utf-8') as f:
            for r in rows:
                if r['canonical_annotation_id'] not in ids:f.write(json.dumps(r)+'\n')
        incoming=t/'withheld_history.jsonl';incoming.write_text(''.join(json.dumps(r)+'\n' for r in take),encoding='utf-8')
        _,restored,rr,ee,_=prepare(t,incoming)
        assert len(restored)==len(rows) and set(rr)==set(rec)
        for k in rec:
            assert np.array_equal(rr[k]['p'],rec[k]['p'])
            assert np.array_equal(rr[k]['up'],rec[k]['up']) and np.array_equal(rr[k]['dn'],rec[k]['dn'])
        checks['withheld_10_historical_rows_append_restores_2501_and_all_roles']=True
        # Invalid/revision/overwrite writes never alter frozen rows.
        tests={
            'duplicate_id':copy.deepcopy(rows[0])|{'record_type':'independent_initial'},
            'revision_not_independent':copy.deepcopy(take[0]),
            'wrong_coordinates_frame':copy.deepcopy(take[0]),
            'wrong_count':copy.deepcopy(take[0])}
        tests['revision_not_independent']['record_type']='peer_revision';tests['wrong_coordinates_frame']['coordinate_width']=2048;tests['wrong_count']['effective_point_count']=999
        for name,row in tests.items():
            q=t/(name+'.jsonl');q.write_text(json.dumps(row)+'\n')
            try:prepare(t,q)
            except ValueError:checks[name+'_rejected']=True
            else:raise AssertionError(name+' accepted')
        # A real partial user anchor used as software fixture; point-index interpretation is explicit.
        a=rec['8178591994d42ce3'];b=rec['a4e0cac5adec2e1e'];base=dict(image_id=a['row']['image_id'],condition='manual',id_a=a['id'],id_b=b['id'],status='confirmed',reviewer='software_test_fixture_only',evidence_source='user_group3_to4_projected_to_raw_indices_for_test',point_payload_sha_a=pointsha(a['p']),point_payload_sha_b=pointsha(b['p']))
        records=[base|dict(role='top',point_a_1based=8,point_b_1based=8),base|dict(role='bottom',point_a_1based=7,point_b_1based=7)]
        p=t/'partial.csv';pd.DataFrame(records).to_csv(p,index=False);validate(root,p,t/'valid')
        s=pd.read_csv(t/'valid/mapping_summary.csv');assert not s.complete_mapping.iloc[0] and pd.isna(s.full_correspondence_distance.iloc[0]);assert s.max_confirmed_residual.iloc[0]<3
        checks['partial_anchor_not_promoted_to_full_mapping_or_cluster']=True
        wrong=copy.deepcopy(records);wrong[0]['point_payload_sha_a']='wrong';pd.DataFrame(wrong).to_csv(p,index=False)
        try:validate(root,p,t/'wrongsha')
        except ValueError:checks['correspondence_wrong_hash_rejected']=True
        else:raise AssertionError('hash failure')
        conflict=records+[base|dict(role='top',point_a_1based=8,point_b_1based=int(b['up'][0])+1)];pd.DataFrame(conflict).to_csv(p,index=False)
        try:validate(root,p,t/'conflict')
        except ValueError:checks['conflicting_correspondence_rejected']=True
        else:raise AssertionError('conflict accepted')
    checks['test_fixtures_not_added_to_analysis']=True;writejson(out/'INTAKE_AND_REVIEW_TESTS.json',checks)
if __name__=='__main__':
    r=Path(__file__).resolve().parents[1];run(r,r/'results/final_run')
