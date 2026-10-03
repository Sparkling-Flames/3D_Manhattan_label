"""Selected records transcribed from the pinned current results blob.
This is not a byte-identical copy or a reconstruction of the complete package.
"""
import json
from pathlib import Path
B=Path(__file__).resolve().parents[1]
triples={
'R03286':[[176.86227731261442,181.21322945665864,336.0166660166508],[487.76886232670256,177.89080456904932,332.1433035451666],[555.8547154096547,178.15879668575874,331.9717056027775],[979.4696135484799,119.41038397619782,391.7395348837209]],
'R03288':[[177.6,184.,332.8],[227.2,136.,451.2],[792.8,131.2,457.6],[977.5999999999999,120.,392.]],
'R03280':[[176.95114135742188,180.82254028320312,338.5046691894531],[487.0206604003906,176.02500915527344,333.1740417480469],[555.25,176.55807495117188,332.6409606933594],[977.4261474609375,119.52101135253906,391.8103942871094]],
'R03281':[[176.3827751196172,178.83253588516746,338.066985645933],[487.5023923444976,178.83253588516746,328.26794258373207],[553.6459330143541,176.3827751196172,328.26794258373207],[977.155039152357,120.47180870132992,394.87463042926254]],
'R03287':[[175.9707495429616,179.71480804387568,338.83729433272396],[486.72760511882996,177.84277879341863,331.34917733089577],[555.9926873857404,175.9707495429616,329.4771480804388],[977.199268738574,119.80987202925046,389.382084095064]],
'R03284':[[176.94412163541318,179.74450616897283,339.60518316574166],[487.5566762662962,176.01712137972882,331.88128145157845],[554.8813342973313,177.74894538052712,335.34492945317504],[983.0250441411115,119.05333823798811,376.61020363671577]],
'R03282':[[177.88528560347595,176.39011590481437,343.5102040816324],[489.14285714285717,177.6326530612245,335.6734693877551],[555.7551020408164,180.2448979591837,334.36734693877554],[976.9795918367347,120.16326530612245,395.75510204081627]],
'R03285':[[2.7675675675675766,119.92792792792793,372.6990990990991],[174.35675675675677,184.50450450450452,339.4882882882883],[218.63783783783782,180.81441441441441,350.55855855855856],[227.86306306306307,132.84324324324325,448.345945945946]],
'R03283':[[174.2863202545069,177.00106044538705,330.1124072110286],[490.2820784729587,178.08695652173913,334.45599151643694],[554.3499469777307,179.1728525980912,332.2841993637327],[976.7635206786852,119.44856839872746,389.8366914103924]],
'R02503':[[556.31,182.77,333.37],[930.43,130.05,387.15],[177.2,175.32,341.1],[250.22,166.8,349.89],[225.69,49.68,465.22],[486.97,181.13,335.08]],
}
workers=['P018','P019','P020','P021','P022','P024','P025','P026','P027']
indices={k:list(range(8)) for k in triples if k!='R02503'}
indices.update(R03280=[4,5,2,3,6,7,0,1],R03281=[6,7,0,3,1,2,5,4],R03285=[6,7,0,1,2,3,4,5],R03283=[0,1,2,4,3,5,6,7])
records=[]
for i,(k,t) in enumerate(triples.items()):
    ref=k=='R02503'
    r=dict(id=k,points=[[x,y] for x,top,bottom in t for y in (top,bottom)],
           coordinate_convention='continuous',order_status='original_gt_reference' if ref else 'human_confirmed',
           ring_confirmed=not ref,source_point_indices=list(range(12)) if ref else indices[k])
    if ref:r['version']='original'
    else:r.update(worker=workers[i],condition='manual',cleaning='retained',independent=True,
                  consensus_eligible=True,quality_candidate=False,
                  main_quality_gate={'status':'out_of_primary_scene','reasons':['doorway_difficult']},
                  main_consensus_gate={'status':'oos_doorway_exploratory','scope_policy':'retain_scope_variation'})
    records.append(r)
obj={'schema':'independent_quality_numeric_subset_v1','source':{
    'repository':'Sparkling-Flames/3D_Manhattan_label',
    'commit':'bba3dc7c9a79b8342ecb4ce2487affe41886eb56',
    'path':'research/pro_quality_handoff_20261002/analysis_results/layout_3d_quality_probe_20261002/results.json',
    'blob_sha':'3809553a325c49baebb1a15a04da30017d98177d',
    'transfer':'Selected numeric records transcribed from actual GitHub connector text. Not a byte-identical download.',
    'coordinate_policy':'Saved shared-x paired continuous coordinates and ring. No raw fallback, repeated preprocessing, fitting or data writeback.',
    'selection':'First complete image available in the connector text; availability sample, not representative sampling.'},
    'images':[{'code':'2t7WUuJeko7-07','building':'2t7WUuJeko7',
    'scene':{'oos_status':'not_recorded','doorway_status':'difficult'},
    'annotations':records[:-1],'references':[records[-1]]}]}
(B/'inputs/current_numeric_subset.json').write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
(B/'inputs/upstream_csv_selected.json').unlink(missing_ok=True)
print('Saved 9 current responses + one reference, with saved order and source indices.')
