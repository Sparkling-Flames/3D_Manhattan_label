#!/usr/bin/env python3
"""Render only stored native cases and actual Release photo; no fusion/scoring."""
import copy,hashlib,importlib.util,json
from pathlib import Path
import export_cases as e

HERE=e.HERE
SPECS={
 'V3_7y13_positive_n12_m4':[
    dict(class_id='S1',workers=['W027'],label='净移出W027：4转折'),
    dict(class_id='S3',workers=['W109'],label='净移入W109：本图也是4转折'),
    dict(class_id='S1',workers=['W112'],label='B的底点中位数来自W112'),
    dict(class_id='S1',workers=['W033'],label='C的底点中位数来自W033')],
 'V3_7y13_counterexample_n12_m4':[
    dict(class_id='S1',workers=['W033','W105'],label='同构成移出：S1两人'),
    dict(class_id='S3',workers=['W109','W127'],label='同构成移出：S3两人'),
    dict(class_id='S1',workers=['W008','W124'],label='同构成移入：S1两人'),
    dict(class_id='S3',workers=['W017','W134'],label='同构成移入：S3两人')],
}

def main():
    spec=importlib.util.spec_from_file_location('existing_case_renderer',e.OLD/'evidence/render_evidence.py');r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
    spec=importlib.util.spec_from_file_location('existing_frozen_viewer',r.RENDERER);v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
    e.gs.save(HERE/'VIEW_SPECS.json',dict(selection='post-result explanation, full members retained separately',groups=SPECS,
        zoom_erp=[225,290,220,300],zoom_bev=[-6.25,-5.1,-.7,.6],display_text_substitutions={'恶化':'变差'}))
    for p in sorted((HERE/'cases').glob('*.json.gz')):
        c=copy.deepcopy(e.gs.read(p));c['raw_overlay_groups']=SPECS[c['case_id']]
        members={m['worker_id']:m for m in c['members']}
        assert all(members[w]['class_id']==g['class_id'] for g in c['raw_overlay_groups'] for w in g['workers'])
        c['title']=c['title'].replace('恶化','变差')
        c['member_overlay_title']=c['member_overlay_title'].replace('恶化','变差')
        c['raw_overlay_title']=c['title']+'：具体成员的原答'
        c['zoom_erp']=[225,290,220,300];c['zoom_bev']=[-6.25,-5.1,-.7,.6]
        c['focus_title']='远端角定位：节点仍是4个，位置中位数发生变化'
        c['highlight_reference_edges']=[2]
        photo=r.original_photo(c,e.V3/'evidence/originals_7y13')
        out=HERE/'figures'/c['case_id'];out.mkdir(parents=True,exist_ok=True)
        result=v.render_case(c,out,font_path=r.DEFAULT_FONT)
        result['raw_three_views']=r.raw_three_views(v,c,photo,out)
        e.gs.save(out/'EVIDENCE_RECEIPT.json',dict(result,case_input_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
            viewer_spec_sha256=hashlib.sha256((HERE/'VIEW_SPECS.json').read_bytes()).hexdigest(),no_fusion=True,no_scores=True))
        print('Rendered',c['case_id'],flush=True)

if __name__=='__main__':main()
