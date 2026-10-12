import json, math, hashlib, argparse
from pathlib import Path
ap=argparse.ArgumentParser();ap.add_argument('--study-root',type=Path,required=True);ap.add_argument('--output',type=Path,default=Path(__file__).parent/'dist');args=ap.parse_args();B=args.study_root;O=args.output;O.mkdir(parents=True,exist_ok=True)
raw=(B/'structure/review_pairs/inputs/selected_pairs_full.json').read_bytes()
r=json.loads(raw)['records']; research=json.load(open(B/'structure/review_pairs/selection_research.json'))
def area(p):return sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(p,p[1:]+p[:1]))/2

def clip(subject,ref):
    out=list(subject);sgn=1 if area(ref)>0 else -1
    assert all(sgn*((ref[(i+1)%len(ref)][0]-ref[i][0])*(ref[(i+2)%len(ref)][1]-ref[(i+1)%len(ref)][1])-(ref[(i+1)%len(ref)][1]-ref[i][1])*(ref[(i+2)%len(ref)][0]-ref[(i+1)%len(ref)][0]))>0 for i in range(len(ref))), 'clip reference must be convex'
    for a,b in zip(ref,ref[1:]+ref[:1]):
        def d(p):return sgn*((b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0]))
        old=out;out=[]
        if not old:break
        for u,v in zip(old[-1:]+old[:-1],old):
            du,dv=d(u),d(v)
            if (du>=0)!=(dv>=0):
                t=du/(du-dv);out.append([u[k]+t*(v[k]-u[k]) for k in range(2)])
            if dv>=0:out.append(v)
    return out

def geom(g,ref=None):
    bottom=g['bottom3d'];top=g['top3d'];p=[[v[0],v[2]] for v in bottom];n=len(p)
    v=[[p[(i+1)%n][k]-p[i][k] for k in range(2)] for i in range(n)];L=[math.hypot(*a) for a in v];S=sum(L)
    theta=[math.degrees(math.atan2(a[1],a[0])) for a in v]
    wrap=lambda a:(a+45)%90-45
    cuts=sorted(set([0,90]+[(a+45)%90 for a in theta]));best=None
    for lo,hi in zip(cuts,cuts[1:]):
        mid=(lo+hi)/2;unwrapped=[mid+wrap(a-mid) for a in theta]
        opt=max(lo,min(hi,sum(l*a for l,a in zip(L,unwrapped))/S))
        mse=sum(l*wrap(a-opt)**2 for l,a in zip(L,theta))/S
        if best is None or mse<best[0]:best=(mse,opt)
    sign=1 if area(p)>0 else -1
    angles=[]
    for i in range(n):
        u=v[i-1];w=v[i];turn=math.degrees(math.atan2(u[0]*w[1]-u[1]*w[0],u[0]*w[0]+u[1]*w[1]));angles.append(180-sign*turn)
    h=[t[1]-b[1] for t,b in zip(top,bottom)]
    mean=sum(L[i]*(h[i]+h[(i+1)%n])/2 for i in range(n))/S
    variance=sum(L[i]*((h[i]-mean)**2+(h[i]-mean)*(h[(i+1)%n]-mean)+(h[(i+1)%n]-mean)**2)/3 for i in range(n))/S
    result={'bottom':bottom,'top':top,'points':g['points'],'area':abs(area(p)),'D':math.sqrt(best[0]),'axis_deg':best[1], 'mean_height':mean,'height_range':max(h)-min(h),'height_std':math.sqrt(max(0,variance)), 'corners':[{'index':i+1,'interior_angle':angles[i],'height':h[i],'bottom':bottom[i],'top':top[i],'outgoing_length':L[i],'outgoing_direction':theta[i]%180,'axis_deviation':abs(wrap(theta[i]-best[1]))} for i in range(n)]}
    if ref:
        rp=[[a[0],a[2]] for a in ref['bottom3d']];ra=abs(area(rp));it=abs(area(clip(p,rp)))
        rh=geom(ref)['mean_height']
        result.update({'reference_area':ra,'area_ratio':result['area']/ra,'missing_reference_fraction':max(0,(ra-it)/ra),'extra_reference_fraction':max(0,(result['area']-it)/ra),'floor_iou':it/(result['area']+ra-it),'height_bias_relative':mean/rh-1,'height_std_relative':result['height_std']/rh,'height_range_relative':result['height_range']/rh})
    return result
out={'schema':'quality_geometry_supplement_v1','parent_dataset_id':'470c4c19769159139d77f8db0e2f75d91647571e7d7832de51276046d47e26ec','source_sha256':hashlib.sha256(raw).hexdigest(),'review_type':'numeric_assisted_development_rereview','groups':[]}
checks=[]
for pid in ['C02','C01']:
    rows=[x for x in r if x['pair_id']==pid]; rr=next(x for x in research['selected_pairs'] if x['pair_id']==pid)
    assert rows[0]['fixed_reference_geometry']==rows[1]['fixed_reference_geometry']
    group={'id':pid,'reference':geom(rows[0]['fixed_reference_geometry']),'cases':[],'original':'assets/'+pid+'_original.png','details':'assets/'+pid+'_details.jpg','processed':'assets/'+pid+'_input_processed.jpg'}
    for row,source in zip(rows,rr['source_scores_and_components']):
        x=geom(row['frozen_annotation_geometry'],row['fixed_reference_geometry']);x['label']=row['within_pair_label']
        assert abs(x['D']-source['dir'])<1e-9
        assert abs(x['floor_iou']-source['iou_2d'])<1e-9
        assert abs(abs(x['height_bias_relative'])-source['Hmean'])<1e-9
        checks.append({'case':pid+x['label'],'D_abs_error':abs(x['D']-source['dir']),'floor_iou_abs_error':abs(x['floor_iou']-source['iou_2d']),'Hmean_abs_error':abs(abs(x['height_bias_relative'])-source['Hmean'])})
        # No fitted Q, worker identity, or expected ranking enters the user-facing data.
        group['cases'].append(x)
    out['groups'].append(group)
out['dataset_id']=hashlib.sha256(json.dumps(out,sort_keys=True).encode()).hexdigest()
(O/'geometry-data.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
(O.parent/'geometry_verification.json').write_text(json.dumps(checks,indent=2))
for g in out['groups']:
 print(g['id'],[(x['label'],x['D'],[round(c['interior_angle'],3) for c in x['corners']],x['floor_iou'],x['height_bias_relative']) for x in g['cases']])
