"""Build separately versioned authorized references and inventory frozen bindings."""
import json
import numpy as np
import pandas as pd
from shapely.geometry import Polygon
from tools.label_studio.panorama_studio.geometry import project_pixel
from .audit_scope_vertical_cut_20261028 import ROOT, OUT as AUDIT
from .scope_reference_reconstruction_20261016 import geometry, floor

OUT=AUDIT/'extension_v1'
PENDING_COLLINEAR={'uNb9QFRL6hY-59','uNb9QFRL6hY-66','wc2JMjhGNzB-03','wc2JMjhGNzB-61'}


def main():
    OUT.mkdir(exist_ok=True)
    receipt=json.loads((AUDIT/'LATEST_E9Z_SCOPE_RECEIPT.json').read_text(encoding='utf-8'))
    assert receipt['exported_at']=='2026-10-28T05:59:52.604Z'
    assert receipt['record']['image_code']=='e9zR4mvMWw7-09'
    refs=json.loads((AUDIT/'CANDIDATE_REFERENCES.json').read_text(encoding='utf-8'))
    catalog=json.loads((ROOT/'research/quality/quality_workers_v2_20261019/reference_catalog.json').read_text(encoding='utf-8'))
    sources={r['target_id']:r for r in catalog}
    changes=[]
    for ref in refs:
        old=np.asarray(ref['floor_xz_h'])
        bottom=np.asarray(receipt['record']['cropped_floor_xz_h'] if ref['image']=='e9zR4mvMWw7-09' else old)
        assert Polygon(bottom).is_valid and Polygon(bottom).area>0
        a,b,c=ref['source_plane']['plane'];heights=a*bottom[:,0]+b*bottom[:,1]+c
        assert np.isfinite(heights).all() and (heights>0).all()
        points=[]
        for (x,z),h in zip(bottom,heights):
            points.extend([project_pixel([x,h,z],1024,512),project_pixel([x,-1,z],1024,512)])
        np.testing.assert_allclose(floor(points),bottom,atol=1e-8)
        geom=geometry(points)
        np.testing.assert_allclose(np.asarray(geom['top3d'])[:,1],heights,atol=1e-8)
        ref.update(status='authorized_reference_pending_binding_and_scoring',reference_version='scope_height_extension_v1_20261028',floor_xz_h=bottom.tolist(),points_1024x512=points,geometry=geom,
                   height_authority='2026-10-28 user confirmed inherit original height for all 29',
                   floor_authority=receipt['exported_at'] if ref['image']=='e9zR4mvMWw7-09' else 'previous accepted scope retained')
        ref['outside_source_percent']=100*Polygon(bottom).difference(Polygon(sources[ref['source_reference_id']]['floor_xz_h'])).area/Polygon(bottom).area
        changes.append(dict(image=ref['image'],target_id=ref['target_id'],source_reference_id=ref['source_reference_id'],old_vertices=len(old),new_vertices=len(bottom),old_area=Polygon(old).area,new_area=Polygon(bottom).area,floor_changed=not Polygon(old).equals(Polygon(bottom))))
    assert len(refs)==29 and sum(r['floor_changed'] for r in changes)==1
    (OUT/'REFERENCES.json').write_text(json.dumps(refs,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    views=json.loads((ROOT/'research/data/scope_redundant_vertices_20261016/scope_views.json').read_text(encoding='utf-8'))
    bytarget={r['target_id']:r for r in refs};derived=[]
    for view in views:
        if not view['current_target'] or not view['precision_removed']:continue
        base=bytarget.get(view['target_id'])
        if base:
            np.testing.assert_allclose(view['original_floor'],base['floor_xz_h'],atol=1e-12)
            v=view['precision_floor_view'];bottom=np.asarray(v['floor']);a,b,c=base['source_plane']['plane']
            heights=a*bottom[:,0]+b*bottom[:,1]+c;points=[]
            for (x,z),h in zip(bottom,heights):points.extend([project_pixel([x,h,z],1024,512),project_pixel([x,-1,z],1024,512)])
            mapping=v
        elif view['paired_view']:
            points=view['paired_view']['points_1024x512'];mapping=view['paired_view']['mapping']
            bottom=np.asarray(mapping['pair_floor']);heights=np.asarray(mapping['pair_heights'])-1
        else:continue
        np.testing.assert_allclose(floor(points),bottom,atol=1e-8)
        np.testing.assert_allclose(np.asarray(geometry(points)['top3d'])[:,1],heights,atol=1e-8)
        derived.append(dict(image=view['image_code'],target_id=view['target_id'],reference_version='confirmed_structure_view_with_height_20261028',
            original_floor=view['original_floor'],floor_xz_h=bottom.tolist(),points_1024x512=points,geometry=geometry(points),source_mapping=mapping,
            raw_vertices=view['raw_vertices'],exact_turns=view['exact_turns'],precision_turns=view['precision_turns'],
            precision_approximation=view['precision_turns']!=view['exact_turns'],
            note='Reuse user-confirmed 20261016 derived view; no new deletion, no global Manhattan snapping; not identical to original geometry when precision_approximation is true'))
    (OUT/'CONFIRMED_DERIVED_REFERENCES.json').write_text(json.dumps(derived,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    pd.DataFrame(changes).to_csv(OUT/'REFERENCE_CHANGES.csv',index=False,encoding='utf-8')
    q=pd.read_json(ROOT/'research/quality/quality_workers_v2_20261019/quality_inventory.json')
    scope=pd.read_csv(ROOT/'research/statistics/external_review_response_20261028/MULTISPACE_41_COVERAGE.csv')
    scope['previous_coarse_class']=scope.coarse_class
    assert scope.image.eq('pa4otMbVnkk-11').sum()==1
    scope.loc[scope.image.eq('pa4otMbVnkk-11'),'coarse_class']='中等'
    scope['difficulty_authority']=np.where(scope.image.eq('pa4otMbVnkk-11'),'user_revision_20261028','existing_accepted_label')
    scope['collinear_review_pending']=scope.image.isin(PENDING_COLLINEAR)
    scope.to_csv(OUT/'IMAGE_SCOPE_REGISTER.csv',index=False,encoding='utf-8')
    q=q[q.image_id.isin(scope.image_id)].copy()
    q=q.merge(scope[['image_id','target_id','coarse_class','previous_coarse_class','difficulty_authority','collinear_review_pending']],on='image_id',validate='many_to_one')
    q['frozen_current_class']=q.current_class
    q.loc[q.image_code.eq('pa4otMbVnkk-11'),'current_class']='中等'
    q['binding_matches_current']=q.chosen_target_id.eq(q.target_id)
    q['reference_repaired']=q.chosen_target_id.isin([r['target_id'] for r in refs])
    q.to_json(OUT/'FROZEN_BINDING_INVENTORY.json',orient='records',force_ascii=False,indent=2)
    pools=q.groupby(['image_code','condition','target_id','chosen_target_id','binding_status'],dropna=False).agg(records=('object_id','size'),people=('worker_id','nunique'),old_pool_eligible=('pool_analysis_eligible','sum'),old_quality_usable=('quality_usable','sum')).reset_index()
    pools.to_csv(OUT/'FROZEN_POOL_COVERAGE.csv',index=False,encoding='utf-8')
    checks=dict(references=29,changed_floors=1,roundtrip_passed=True,manual_records=int(q.condition.eq('manual').sum()),manual_repair_reference_records=int((q.condition.eq('manual')&q.reference_repaired).sum()),status='reference_construction_complete_binding_and_endpoint_audit_pending',new_scores=0,new_fusion=0)
    (OUT/'CHECKS.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(checks,ensure_ascii=False))


if __name__=='__main__':main()
