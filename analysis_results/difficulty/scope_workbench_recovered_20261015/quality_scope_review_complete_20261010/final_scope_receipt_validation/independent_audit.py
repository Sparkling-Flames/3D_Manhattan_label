#!/usr/bin/env python3
"""Independent offline JSON, ERP projection, geometry and provenance audit; Python standard library only."""
import json,math,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parent
errors=[];checks=0;audited_polygons=0;replayed_operations=0;max_projection_error=0;max_replay_error=0

def check(yes,label):
    global checks
    checks+=1
    if not yes:errors.append(label)
def unique_object(pairs):
    out={}
    for k,v in pairs:
        if k in out:raise ValueError('Duplicate JSON key: '+k)
        out[k]=v
    return out
def load(p):return json.loads(p.read_text(),object_pairs_hook=unique_object,parse_constant=lambda x:(_ for _ in ()).throw(ValueError('Nonfinite JSON: '+x)))
A=load(ROOT/'inputs/raw_scope_receipt.json');D=load(ROOT/'inputs/data.json');O=load(ROOT/'normalized_confirmation_overlay.json');V=load(ROOT/'validation_report.json');OLD=load(ROOT/'inputs/prior_normalized_confirmation_overlay.json')
by={c['image_code']:c for c in D['images']};rb={r['image_code']:r for r in A['records']};ob={(r['image_code'],r['region_id']):r for r in O['records']}
def cross(a,b,c):return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
def area(p):return abs(sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(p,p[1:]+p[:1])))/2
def segdistance(q,a,b):
    dx,dy=b[0]-a[0],b[1]-a[1];ll=dx*dx+dy*dy
    if not ll:return math.dist(q,a)
    t=max(0,min(1,((q[0]-a[0])*dx+(q[1]-a[1])*dy)/ll))
    return math.hypot(a[0]+t*dx-q[0],a[1]+t*dy-q[1])
def simple(p):
    for i,(a,b) in enumerate(zip(p,p[1:]+p[:1])):
        if math.dist(a,b)<=1e-12:return False
        for j in range(i+1,len(p)):
            if j==i+1 or (i==0 and j==len(p)-1):continue
            c,d=p[j],p[(j+1)%len(p)]
            u,v,w,z=cross(a,b,c),cross(a,b,d),cross(c,d,a),cross(c,d,b)
            if ((u>0)!=(v>0)) and ((w>0)!=(z>0)):return False
            if min(segdistance(c,a,b),segdistance(d,a,b),segdistance(a,c,d),segdistance(b,c,d))<=1e-12:return False
    return True
def camera_inside(p):
    w=0
    for a,b in zip(p,p[1:]+p[:1]):
        if a[1]<=0<b[1] and cross(a,b,[0,0])>0:w+=1
        elif b[1]<=0<a[1] and cross(a,b,[0,0])<0:w-=1
    return w!=0 and min(segdistance([0,0],a,b) for a,b in zip(p,p[1:]+p[:1]))>1e-7
def valid(p):return len(p)>=3 and area(p)>1e-8 and simple(p)
def audit_polygon(p,label):
    global audited_polygons
    check(valid(p),label+': independent simple positive-area polygon')
    check(camera_inside(p),label+': independent winding camera containment')
    audited_polygons+=1
def project(points):
    out=[]
    for x,y in points[1::2]:
        u=(x/1024-.5)*2*math.pi;v=(y/512-.5)*math.pi;r=1/math.tan(v)
        out.append([r*math.sin(u),-r*math.cos(u)])
    return out
def approx(p,q,tol=1e-8):return len(p)==len(q) and all(abs(x-y)<tol for a,b in zip(p,q) for x,y in zip(a,b))
def line_intersection(a,b,c,d):
    u=[b[i]-a[i] for i in (0,1)];v=[d[i]-c[i] for i in (0,1)];den=u[0]*v[1]-u[1]*v[0]
    if abs(den)<1e-8:raise ValueError('parallel supporting lines')
    t=((c[0]-a[0])*v[1]-(c[1]-a[1])*v[0])/den
    return [a[i]+t*u[i] for i in (0,1)]
def edge_edit(poly,index,line):
    n=len(poly);p=[x[:] for x in poly]
    p[index]=line_intersection(poly[(index-1)%n],poly[index],*line)
    p[(index+1)%n]=line_intersection(poly[(index+1)%n],poly[(index+2)%n],*line)
    if valid(p) and all(math.dist(a,b)>1e-8 for a,b in zip(p,p[1:]+p[:1])):return p
    # Only merge coincident adjacent points touching an edited endpoint.
    entries=[{'point':q,'edited':i in [index,(index+1)%n],'junction':False} for i,q in enumerate(p)];collapsed=False
    i=len(entries)-1
    while i>=0:
        j=(i+1)%len(entries);a,b=entries[i],entries[j]
        if (a['edited'] or b['edited']) and math.dist(a['point'],b['point'])<=1e-8:
            a['junction']=True;a['edited']=a['edited'] or b['edited'];entries.pop(j);collapsed=True;i=min(i,len(entries)-1)
        i-=1
    if not collapsed:raise ValueError('invalid edge edit without eligible collapsed corner')
    i=len(entries)-1
    while i>=0 and len(entries)>3:
        e=entries[i]
        if e['junction']:
            a,b,c=entries[(i-1)%len(entries)]['point'],e['point'],entries[(i+1)%len(entries)]['point'];u=[b[k]-a[k] for k in (0,1)];v=[c[k]-b[k] for k in (0,1)];ln=math.hypot(*u)*math.hypot(*v)
            if ln>1e-8 and abs(u[0]*v[1]-u[1]*v[0])<=1e-10*ln and sum(x*y for x,y in zip(u,v))>0:entries.pop(i)
        i-=1
    return [e['point'] for e in entries]
def replay_one(p,op):
    typ=op['type']
    if typ=='rectangle':
        a,b=op['a'],op['b'];t=math.radians(op['angle']);co,si=math.cos(t),math.sin(t)
        loc=lambda q:[q[0]*co+q[1]*si,-q[0]*si+q[1]*co]
        glob=lambda q:[q[0]*co-q[1]*si,q[0]*si+q[1]*co]
        a,b=loc(a),loc(b);return [glob(q) for q in [[a[0],a[1]],[b[0],a[1]],[b[0],b[1]],[a[0],b[1]]]]
    if typ=='cut':
        q=[];a,b,side=op['a'],op['b'],op['side']
        for u,v in zip(p,p[1:]+p[:1]):
            fu,fv=side*cross(a,b,u),side*cross(a,b,v);iu,iv=fu>=-1e-8,fv>=-1e-8
            if iu:q.append(u[:])
            if iu!=iv:
                t=fu/(fu-fv);q.append([u[i]+t*(v[i]-u[i]) for i in (0,1)])
        cleaned=[]
        for v in q:
            if not cleaned or math.dist(v,cleaned[-1])>1e-8:cleaned.append(v)
        if len(cleaned)>1 and math.dist(cleaned[-1],cleaned[0])<=1e-8:cleaned.pop()
        return cleaned
    if typ=='edge_move':
        i=op['index'];a,b=p[i],p[(i+1)%len(p)];ln=math.dist(a,b);normal=[-(b[1]-a[1])/ln,(b[0]-a[0])/ln]
        return edge_edit(p,i,[[v[k]+op['offset']*normal[k] for k in (0,1)] for v in (a,b)])
    if typ=='gt_follow':return [line_intersection(*op['lines'][(i-1)%4],*op['lines'][i]) for i in range(4)]
    if typ=='edge_follow':
        q=[x[:] for x in p];i=op['index'];line=op['line'];ln=math.dist(*line);on=lambda p:abs(cross(*line,p))/ln<=1e-8
        while len(q)>3 and on(q[(i-1)%len(q)]) and on(q[i]):
            prev=(i-1)%len(q);q.pop(i);i=prev-1 if prev>i else prev
        while len(q)>3 and on(q[(i+1)%len(q)]) and on(q[(i+2)%len(q)]):
            nxt=(i+1)%len(q);q.pop(nxt)
            if nxt<i:i-=1
        return edge_edit(q,i,line)
    raise ValueError('unsupported operation '+typ)
def audit_snapshot(c,r,label):
    global replayed_operations,max_replay_error
    p=project(c['reference_points_1024x512'])
    for i,op in enumerate(r['operations']):
        p=replay_one(p,op);audit_polygon(p,label+'/operation/'+str(i));replayed_operations+=1
    check(approx(p,r['polygon']),label+': independent operation replay')
    if len(p)==len(r['polygon']):max_replay_error=max(max_replay_error,max(abs(x-y) for a,b in zip(p,r['polygon']) for x,y in zip(a,b)))
    audit_polygon(r['polygon'],label+'/polygon')
for i,r in enumerate(A['records']):
    c=by[r['image_code']];id=r['image_code'];gt=project(c['reference_points_1024x512']);audit_polygon(gt,id+'/baseline')
    check(r['image_id']==c['image_id'],id+': identity');check(r['editing_reference_points_1024x512']==c['reference_points_1024x512'],id+': source ERP GT exact')
    check(approx(gt,r['original_GT_floor_xz_h']),id+': independent ERP projection')
    max_projection_error=max(max_projection_error,max(abs(x-y) for a,b in zip(gt,r['original_GT_floor_xz_h']) for x,y in zip(a,b)))
    for region in r['space_regions']['regions']:
        rid=region['region_id'];lab=id+'/'+rid;audit_snapshot(c,region,lab)
        expected={'source_commit':A['source_commit'],'image_code':id,'image_id':r['image_id'],'editing_reference_object_id':c['reference_object_id'],'editing_reference_version':c['reference_version'],'editing_reference_points_1024x512':c['reference_points_1024x512']}
        check(region['source_binding']==expected,lab+': source binding exact')
        conf=region['confirmed_version']
        if conf:
            audit_snapshot(c,conf,lab+'/confirmation')
            if region['floor_region_confirmed']:
                check(conf['polygon']==region['polygon'] and conf['operations']==region['operations'] and conf['decision']==region['decision'],lab+': confirmation matches draft')
                check((id,rid) in ob,lab+': approved region included')
                row=ob[(id,rid)]
                check(row['polygon']==region['polygon'] and row['operations']==region['operations'] and row['confirmed_review']==conf,lab+': normalized original coordinates and snapshot preserved')
                check(row['source']==conf['source'] and row['confirmed_at']==conf['confirmed_at'],lab+': original confirmation provenance preserved')
                check(row['reference_ready'] is False and row['formal_eligibility_changed'] is False and row['top_boundary_pending'] is True,lab+': protected gates unchanged')
        else:check((id,rid) not in ob,lab+': unapproved region excluded')
    if r['received_confirmed_version']:audit_snapshot(c,r['received_confirmed_version'],id+'/received')
    for j,h in enumerate(r['received_confirmed_history']):audit_snapshot(c,h.get('snapshot',h),id+'/history/'+str(j))
check(len(O['records'])==35 and len(ob)==35,'35 unique approved region records')
check(sum(r['in_current_corpus'] for r in O['records'])==33,'33 confirmed current-corpus images')
check(sum(r['recovered_reference_view'] for r in O['records'])==2,'two recovered external image views')
check(all(rb[r['image_code']]['confirmed_version']==r['confirmed_review'] for r in OLD['records']),'all previous 16 confirmation snapshots exact')
check(not A['room_review_batch_policy']['applied_image_codes'],'no no-operation policy approvals inferred')
check(all(rb[code]['floor_region_confirmed'] for code in D['missing_room_scope_queue']['priority_image_codes']),'all 19 priority images confirmed')
check(all(rb[code]['floor_region_confirmed'] for code in A['room_review_batch_policy']['assigned_image_codes']),'all 23 assigned images confirmed')
check(O['source']['receipt_sha256']==hashlib.sha256((ROOT/'inputs/raw_scope_receipt.json').read_bytes()).hexdigest(),'immutable raw receipt hash')
for name,info in V['inputs'].items():check(hashlib.sha256((ROOT/'inputs'/name).read_bytes()).hexdigest()==info['sha256'],'immutable input hash '+name)
result={'result':'PASS' if not errors else 'FAIL','implementation':'independent Python standard-library JSON/ERP/line-intersection/clipping/winding audit; no JS execution','checks':checks,'audited_polygons_including_intermediate_and_historical':audited_polygons,'independently_replayed_operation_instances':replayed_operations,'max_projection_abs_error':max_projection_error,'max_replay_abs_error':max_replay_error,'errors':errors,'limits':'Geometry/source consistency is verified; this is not a new semantic image review or top-boundary/3D approval.'}
(ROOT/'independent_audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False,indent=2));raise SystemExit(bool(errors))
