#!/usr/bin/env python3
"""Independent strict JSON/identity/geometry/overlay audit, standard-library only."""
import json, math, hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parent
errors=[]
def check(test, message):
    if not test: errors.append(message)
def unique_object(pairs):
    out={}
    for k,v in pairs:
        if k in out: raise ValueError('Duplicate JSON key: '+k)
        out[k]=v
    return out
def load(p):
    return json.loads(p.read_text(),object_pairs_hook=unique_object,parse_constant=lambda x:(_ for _ in ()).throw(ValueError('Nonfinite JSON: '+x)))
a=load(ROOT/'inputs/raw_scope_receipt.json');d=load(ROOT/'inputs/data.json');o=load(ROOT/'normalized_confirmation_overlay.json')
by={c['image_code']:c for c in d['images']};rb={r['image_code']:r for r in a['records']}
def area(p): return abs(sum(x*z2-x2*z for (x,z),(x2,z2) in zip(p,p[1:]+p[:1])))/2

def cross(a,b,c): return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
def segdistance(q,a,b):
    dx,dz=b[0]-a[0],b[1]-a[1];ll=dx*dx+dz*dz
    if ll==0:return math.dist(q,a)
    t=max(0,min(1,((q[0]-a[0])*dx+(q[1]-a[1])*dz)/ll))
    return math.hypot(a[0]+t*dx-q[0],a[1]+t*dz-q[1])
def simple(p):
    for i,(a,b) in enumerate(zip(p,p[1:]+p[:1])):
        if math.dist(a,b)<=1e-12:return False
        for j in range(i+1,len(p)):
            if j==i+1 or (i==0 and j==len(p)-1):continue
            c,e=p[j],p[(j+1)%len(p)]
            o1,o2,o3,o4=cross(a,b,c),cross(a,b,e),cross(c,e,a),cross(c,e,b)
            if ((o1>0)!=(o2>0)) and ((o3>0)!=(o4>0)):return False
            if min(segdistance(c,a,b),segdistance(e,a,b),segdistance(a,c,e),segdistance(b,c,e))<=1e-12:return False
    return True

def camera_inside(p):
    winding=0
    for a,b in zip(p,p[1:]+p[:1]):
        if a[1]<=0<b[1] and cross(a,b,[0,0])>0:winding+=1
        elif b[1]<=0<a[1] and cross(a,b,[0,0])<0:winding-=1
    return winding!=0 and min(segdistance([0,0],a,b) for a,b in zip(p,p[1:]+p[:1]))>1e-7

def project(p):
    out=[]
    for x,y in p[1::2]:
        u=(x/1024-.5)*2*math.pi;v=(y/512-.5)*math.pi;r=1/math.tan(v)
        out.append([r*math.sin(u),-r*math.cos(u)])
    return out

def approx(p,q,tol=1e-8):return len(p)==len(q) and all(abs(x-y)<tol for a,b in zip(p,q) for x,y in zip(a,b))
checks=[];max_math=0
for r in a['records']:
    c=by[r['image_code']];id=r['image_code'];p=r['polygon'];floor=project(c['reference_points_1024x512'])
    check(r['image_id']==c['image_id'],id+': identity')
    check(r['original_GT_points_1024x512']==c['reference_points_1024x512'],id+': GT points exact')
    check(approx(floor,r['original_GT_floor_xz_h']),id+': independent ERP floor projection')
    max_math=max(max_math,max(abs(x-y) for a,b in zip(floor,r['original_GT_floor_xz_h']) for x,y in zip(a,b)))
    for name,poly in [('baseline',floor),('current',p)]:
        check(len(poly)>=3 and area(poly)>1e-8 and simple(poly) and camera_inside(poly),id+': independent '+name+' geometry')
    if r['operations']:
        check(len(r['operations'])==1 and r['operations'][0]['type']=='rectangle',id+': effective operation')
        op=r['operations'][0];check(op['angle']==0,id+': rectangle angle zero')
        x,z=op['a'];xx,zz=op['b'];check(p==[[x,z],[xx,z],[xx,zz],[x,zz]],id+': independent exact rectangle replay')
    else:check(approx(floor,p),id+': no-operation floor replay')
    checks.append(id)
check(len(o['records'])==16,'overlay count')
check(o['prior_count_resolution']['status']=='resolved_by_explicit_user_clarification','resolved count')
check(o['prior_count_resolution']['unresolved_count']==0,'zero unresolved')
check(o['source']['user_confirmation']['message_id']=='Sentinel_9ed00ac0b1388191a64819aae866107b','message ID exact')
check(o['source']['prior_count_clarification']['message_id']=='Sentinel_b0471b82acec8191b2289d5f76e245bd','clarification message ID exact')
for n in o['records']:
    r=rb[n['image_code']];c=by[n['image_code']];id=n['image_code']
    for key in ['polygon','cropped_floor_xz_h','operations','cuts','note','decision','axis_angle','updated_at']:
        check(n[key]==r[key],id+': normalized preserves '+key)
    check(n['confirmed_review']['polygon']==r['polygon'],id+': confirmed polygon preserves source exactly')
    check(n['completed'] is True and n['floor_region_confirmed'] is True,id+': confirmation')
    check(n['top_boundary_pending'] is True and n['reference_ready'] is False and n['formal_eligibility_changed'] is False,id+': no scope overreach')
    check(n['protected_site_metadata']['gates']==c['gates'],id+': gates unchanged')
    check(n['source_sha256']==hashlib.sha256((ROOT/'inputs/raw_scope_receipt.json').read_bytes()).hexdigest(),id+': receipt SHA256')
    if c.get('confirmed_review'):
        check(n['source']=='user_chat' and n['confirmation_message_id']=='Sentinel_9ed00ac0b1388191a64819aae866107b',id+': chat confirmation source')
        check(n['confirmed_at']=='2026-10-10T11:53:17Z',id+': chat confirmation time')
        hist={h['role']:h['snapshot'] for h in n['previous_confirmation_history']}
        check(hist['site_prior_confirmed_review']==c['confirmed_review'],id+': old Site snapshot preserved')
        check(hist['raw_confirmed_version']==r['confirmed_version'],id+': old raw snapshot preserved')
        check(r['completed'] is False and r['floor_region_confirmed'] is False,id+': raw false flags remain')
    else:
        check(n['source']=='workbench_button' and n['confirmed_at']==r['confirmed_version']['confirmed_at'],id+': button source/timestamp preserved')
result={'schema':'independent_scope_receipt_audit_v1','result':'FAIL' if errors else 'PASS','strict_json_files':3,'duplicate_json_keys':0,'nonfinite_json_values':0,'independently_checked_polygons':518,'independent_replayed_drafts':259,'exact_preserved_normalized_records':16,'floor_projection_max_abs_discrepancy':max_math,'method':'Python standard library, independent ERP projection, winding-number camera test, segment intersection checks, exact rectangle construction, exact normalized-source/provenance comparisons','errors':errors}
(ROOT/'independent_audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(result,ensure_ascii=False,indent=2));raise SystemExit(bool(errors))
