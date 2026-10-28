"""Archive user adoption, preserving exclusions and historical reference identities."""
import copy
import gzip
import json
import zipfile
import numpy as np
import pandas as pd
from tools.thesis_main.local_inputs import source_zip
from .orthogonal_scope_references_20261028 import ROOT,OUT as SOURCE,axis,geometry,floor
from .difficulty_user_revision_20261015 import convert_original

OUT=SOURCE.parent/'adopted_references_20261028'
WC2='wc2JMjhGNzB_40ea4145b9e946aab5d56de3ce179c8e'


def write(name,value):
    (OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')


def main():
    OUT.mkdir(exist_ok=True)
    refs=json.loads((SOURCE/'REFERENCES.json').read_text(encoding='utf-8'))
    base=json.loads((ROOT/'research/quality/quality_workers_v2_20261019/reference_catalog.json').read_text(encoding='utf-8'))
    catalog={r['target_id']:copy.deepcopy(r) for r in base}
    receipt=dict(version='user_orthogonal_adoption_20261028',user_statement='大部分修正都没问题，只不过最后一个wc2JMjhGNzB-23 — historical_not_current有点问题，不如直接用回原来的mp3d的gt',
        interpretation='adopt reviewed non-OOS corrections, except wc2-23 use original MP3D; preserve all existing holds, exclusions and historical identity',
        source_package=str(SOURCE.relative_to(ROOT)),reference_only_not_eligibility_admission=True)
    write('USER_ADOPTION_RECEIPT.json',receipt)
    rows=[];adopted=[]
    for r in refs:
        item=copy.deepcopy(r);tid=r['target_id'];original_tid=tid
        if r['image_id']==WC2:
            member='label_data/'+WC2+'_label.json'
            with zipfile.ZipFile(source_zip()) as archive:raw=json.loads(archive.read(member))
            points=convert_original(raw);tid='mp3d_original_20261028:'+WC2
            item.update(target_id=tid,points_1024x512=points,floor_xz_h=floor(points).tolist(),geometry=geometry(points),adoption_method='original_MP3D_ERP_conversion_no_orthogonalization',replaces_candidate_target_id=original_tid,
                original_source=dict(archive='data/external/label_data.zip',member=member,source_json_geometry=raw))
        else:item['adoption_method']='user_confirmed_orthogonal_candidate'
        item.update(adopted=True,status='user_adopted_reference',reference_version='user_adopted_reference_20261028')
        p=np.asarray(item['points_1024x512']);g=geometry(p);top=np.asarray(g['top3d']);bottom=np.asarray(g['bottom3d'])
        vertical=float(np.abs(top[:,[0,2]]-bottom[:,[0,2]]).max());height_range=float(np.ptp(top[:,1]));residual=axis(floor(p))[1]
        np.testing.assert_allclose(top[:,[0,2]],bottom[:,[0,2]],atol=1e-10)
        if r['image_id']!=WC2:assert residual<1e-8
        old=catalog.get(original_tid)
        if old:
            entry=copy.deepcopy(old)
        else:
            entry=dict(target_id=tid,image_id=r['image_id'],image_code=r['image'],current_target=False,is_admitted_space_candidate=False,image_analysis_blocked=False,image_analysis_hold_reasons=[],role='historical_reference_not_in_frozen_catalog')
        entry.update(target_id=tid,reference_version=item['reference_version'],points_1024x512=item['points_1024x512'],floor_xz_h=item['floor_xz_h'],geometry=g,full_reference_available=True,status='user_adopted_reference',minimal_gap='',adoption_receipt=str((OUT/'USER_ADOPTION_RECEIPT.json').relative_to(ROOT)))
        catalog[tid]=entry
        rows.append(dict(image=r['image'],target_id=tid,previous_candidate_target_id=original_tid,current_target=entry['current_target'],hold_reasons='|'.join(entry['image_analysis_hold_reasons']),axis_residual_deg=residual,vertical_xz_error_h=vertical,ceiling_height_range_h=height_range,floor_rectilinear=residual<1e-8,flat_ceiling=height_range<1e-8,full_3D_Manhattan=residual<1e-8 and height_range<1e-8,method=item['adoption_method']))
        adopted.append(item)
    assert len(adopted)==71
    write('ADOPTED_REFERENCES.json',adopted);write('REFERENCE_CATALOG.json',list(catalog.values()))
    pd.DataFrame(rows).to_csv(OUT/'GEOMETRY_ACCEPTANCE.csv',index=False,encoding='utf-8')
    from .scope_local_routing_20261017 import route_missing_space
    bindings=json.loads((ROOT/'research/quality/quality_workers_v2_20261019/reference_bindings.json').read_text(encoding='utf-8'))
    with gzip.open(ROOT/'research/data/releases/v2/analysis_input/data.json.gz','rt',encoding='utf-8') as f:data=json.load(f)
    objects={o['object_id']:o for o in data['objects']};routed={};routing=[];prepared={}
    for b in bindings:
        if b['image_code']!='e9zR4mvMWw7-09':continue
        assert not b['manual_source'] and not b['manual_family_source'],'manual priority needs explicit preservation'
        chosen,evidence=route_missing_space(objects[b['object_id']]['points_1024x512'],list(catalog.values()),b['allowed_target_ids'],prepared)
        routed[b['object_id']]=chosen
        routing.append(dict(object_id=b['object_id'],old_target=b['chosen_target_id'],new_target=chosen,changed=chosen!=b['chosen_target_id'],evidence=evidence))
    write('E9Z_BINDING_RECHECK.json',routing)
    # Reuse paired measured outputs only for the exact frozen binding; no reference optimization.
    cached={}
    for line in (SOURCE/'PAIRED_MEASUREMENTS.jsonl').read_text(encoding='utf-8').splitlines():
        r=json.loads(line);cached[(r['object_id'],r['target_id'])]=r['results']['after']
    inventory=json.loads((ROOT/'research/quality/quality_workers_v2_20261019/quality_inventory.json').read_text(encoding='utf-8'))
    repaired={r['target_id'] for r in adopted};linked=[]
    for old in inventory:
        tid=routed.get(old['object_id'],old['chosen_target_id'])
        if tid not in repaired:continue
        result=cached.get((old['object_id'],tid));complete=bool(result and result['score_status']=='complete')
        blockers=list(old['quality_exclusion_reasons'])
        if complete:blockers=[x for x in blockers if x not in ('full_reference_unavailable','reference_not_full','score_unavailable')]
        changed_floor=old['image_code']=='e9zR4mvMWw7-09'
        if changed_floor and not routed.get(old['object_id']):blockers.append('latest_floor_binding_recheck_pending')
        usable=complete and not blockers
        linked.append(dict(object_id=old['object_id'],image=old['image_code'],condition=old['condition'],target_id=tid,old_quality_usable=old['quality_usable'],old_exclusions=old['quality_exclusion_reasons'],new_exclusions=blockers,measurement_reused=complete,quality_eligible_after_reference_repair=usable,B8L2=result['B8L2'] if usable else None,D10=result['D10'] if usable else None,diagnostic_B8L2=result.get('B8L2') if result else None))
    write('BOUND_SCORE_REUSE.json',linked)
    assert all(not r['quality_eligible_after_reference_repair'] for r in linked if r['image']=='wc2JMjhGNzB-14')
    checks=dict(adopted_reference_versions=len(adopted),orthogonal_candidates_adopted=70,MP3D_exceptions=1,old_catalog_unchanged=True,new_fusion=0,new_scores=0,cached_measurements_reused=sum(r['measurement_reused'] for r in linked),post_repair_eligible=sum(r['quality_eligible_after_reference_repair'] for r in linked),e9z_binding_rechecked=len(routing),e9z_binding_changed=sum(r['changed'] for r in routing),e9z_binding_pending=sum(not r['new_target'] for r in routing))
    write('CHECKS.json',checks);print(checks)
    (OUT.parent/'CURRENT_REFERENCES.json').write_text(json.dumps(dict(version='user_adopted_reference_20261028',catalog=str((OUT/'REFERENCE_CATALOG.json').relative_to(ROOT)),receipt=str((OUT/'USER_ADOPTION_RECEIPT.json').relative_to(ROOT)),qualification='preserve prior holds; use BOUND_SCORE_REUSE only for repaired-reference eligibility; frozen v2 unchanged'),ensure_ascii=False,indent=2),encoding='utf-8')
    print(pd.DataFrame(rows).groupby(['floor_rectilinear','flat_ceiling','full_3D_Manhattan']).size().to_string())
    print(pd.DataFrame(rows).query("image=='wc2JMjhGNzB-23'").to_string(index=False))


if __name__=='__main__':main()
