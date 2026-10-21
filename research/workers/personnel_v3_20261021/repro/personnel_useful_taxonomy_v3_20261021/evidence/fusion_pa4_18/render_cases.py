#!/usr/bin/env python3
"""Render exact stored Manual endpoints and raw answers over the Release image."""
import copy, hashlib, importlib.util
import export_cases as e

HERE = e.HERE
SPECS = {
 'V3_pa4_18_positive_n12_m4': [
    dict(class_id='M2.1',workers=['W100','W127'],label='B→C移出：M2两人'),
    dict(class_id='M3.1',workers=['W112','W122'],label='B→C移入：M3两人'),
    dict(class_id='M2.1',workers=['W101'],label='两队共有W101：也是六点'),
    dict(class_id='M3.1',workers=['W109','W130'],label='两队共有：左后短转折')],
 'V3_pa4_18_counterexample_n20_m5': [
    dict(class_id='M3',workers=['W122'],label='A移出的M3：完整六点'),
    dict(class_id='M3',workers=['W112'],label='B移入的M3：完整六点'),
    dict(class_id='M2',workers=['W101'],label='C以W101替W112：不同六点'),
    dict(class_id='M2',workers=['W100','W131','W134'],label='B/C中的M2：共同补左后角')]}

def main():
    mod = importlib.util.spec_from_file_location('existing_case_renderer',e.OLD/'evidence/render_evidence.py')
    r = importlib.util.module_from_spec(mod);mod.loader.exec_module(r)
    mod = importlib.util.spec_from_file_location('existing_frozen_viewer',r.RENDERER)
    v = importlib.util.module_from_spec(mod);mod.loader.exec_module(v)
    e.gs.save(HERE/'VIEW_SPECS.json',dict(selection='post-result explanatory groups; complete members retained in case JSON',
        groups=SPECS,zoom_erp=[380,465,170,328],zoom_bev=[-2.5,-.65,-4.65,-1.85],
        highlight_reference_edges=[3,4],no_point_or_reference_changes=True))
    for p in sorted((HERE/'cases').glob('*.json.gz')):
        c = copy.deepcopy(e.gs.read(p));c['raw_overlay_groups']=SPECS[c['case_id']]
        byworker = {m['worker_id']:m for m in c['members']}
        assert all(byworker[w]['class_id']==g['class_id'] for g in c['raw_overlay_groups'] for w in g['workers'])
        c['raw_overlay_title']=c['title']+'：同点数也可能表达不同位置'
        c['zoom_erp']=[380,465,170,328];c['zoom_bev']=[-2.5,-.65,-4.65,-1.85]
        c['focus_title']='左后墙短转折：局部票数、对应与定位共同传递到融合'
        c['highlight_reference_edges']=[3,4]
        photo = r.original_photo(c,e.V3/'evidence/originals')
        out = HERE/'figures'/c['case_id'];out.mkdir(parents=True,exist_ok=True)
        result = v.render_case(c,out,font_path=r.DEFAULT_FONT)
        result['raw_three_views']=r.raw_three_views(v,c,photo,out)
        e.gs.save(out/'EVIDENCE_RECEIPT.json',dict(result,case_input_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
            viewer_spec_sha256=hashlib.sha256((HERE/'VIEW_SPECS.json').read_bytes()).hexdigest(),no_fusion=True,no_scores=True))
        print('Rendered',c['case_id'],flush=True)

if __name__=='__main__':main()
