#!/usr/bin/env python3
"""Replay review-36 selection and geometry checks using only public artifacts.
Default checks are dependency-free. Add --metrics and the bundled vendor folder
for unchanged-definition numeric reproduction (numpy/scipy/shapely required).
"""
from pathlib import Path
import argparse,hashlib,json,math,sys
p=argparse.ArgumentParser(description=__doc__)
r=Path(__file__).resolve().parent
p.add_argument('--manifest',type=Path,default=r/'public_selection_manifest.json')
p.add_argument('--geometry',type=Path,default=r/'public_frozen_geometry.json')
p.add_argument('--ratings',type=Path,default=r/'public_ratings_initial.json')
p.add_argument('--metrics',action='store_true')
p.add_argument('--vendor',type=Path,default=r/'vendor')
a=p.parse_args();manifest=json.loads(a.manifest.read_text());geo=json.loads(a.geometry.read_text());ratings=json.loads(a.ratings.read_text())
count=0;maximum_3d=0.;maximum_erp=0.;seams=0;points=0

def check(value,msg):
 global count
 count+=1
 if not value:raise AssertionError(msg)
def jsha(v):return hashlib.sha256(json.dumps(v,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()).hexdigest()
def projection(v):
 x,y,z=v
 return [((math.atan2(x,-z)/(2*math.pi)+.5)%1)*1024,(.5-math.atan2(y,math.hypot(x,z))/math.pi)*512]
def blend(x,y,t):return [c+(d-c)*t for c,d in zip(x,y)]
def independent_vertices(q):
 top=[];bottom=[]
 for i in range(0,len(q),2):
  x,yt=q[i];xb,yb=q[i+1]
  check(abs((x-xb+512)%1024-512)<1e-8,'shared longitude')
  theta=2*math.pi*(xb/1024-.5);rho=1/math.tan(math.pi*(yb/512-.5))
  xx=rho*math.sin(theta);zz=-rho*math.cos(theta)
  bottom.append([xx,-1.,zz]);top.append([xx,rho*math.tan(math.pi*(.5-yt/512)),zz])
 return top,bottom
selected={s['id']:s for s in manifest['selectedRecords']}
check(len(selected)==36,'36 selected');check(len(manifest['candidatePool'])==135,'135 candidates');check(len(geo['images'])==6,'six images')
check(manifest['datasetFingerprintSha256']==geo['datasetFingerprintSha256']==ratings['datasetFingerprintSha256'],'shared dataset fingerprint')
check(len(ratings['ratings'])==36,'36 initial ratings')
for rating in ratings['ratings']:
 check(rating['overallRating'] is None and rating['comment']=='' and rating['reviewed'] is False,'empty rating template')
 check(rating['referenceVersionAtSave'] is None and rating['exposureHistory']==[],'empty save/exposure history')
record_count=0;metric_checks=0;metric_max=0.
for im in geo['images']:
 code=im['code'];pm=next(m for m in manifest['images'] if m['image']==code)
 check(len(im['annotations'])==6,'six per image')
 pool=pm['candidatePoolIds'];check(jsha(pool)==pm['candidatePoolIdsSha256'],'pool hash')
 remain=[rid for rid in pool if rid not in pm['targetedIds']]
 ordered=sorted(remain,key=lambda rid:(hashlib.sha256((manifest['seed']+'|'+code+'|'+rid).encode()).hexdigest(),rid))
 check(ordered==pm['randomSelectionOrderIds'],'random ordering');check(ordered[:2]==pm['randomSelectedIds'],'two random draws')
 shown=sorted(pm['targetedIds']+ordered[:2],key=lambda rid:(hashlib.sha256((manifest['seed']+'|display|'+code+'|'+rid).encode()).hexdigest(),rid))
 check([r['id'] for r in im['annotations']]==shown,'display ordering')
 refs={g['version']:g for g in im['groundtruths']}
 check(im['defaultReferenceVersion']=='original' and im['defaultReferenceId']==refs['original']['id'],'original reference default')
 for rec in im['annotations']+im['groundtruths']:
  record_count+=1;rid=rec['id'];q=rec['points'];top,bottom=independent_vertices(q);n=len(top)
  check(n==rec['pairCount'],'pair count')
  if 'reviewId' in rec:
   check(rec['reviewId']==selected[rid]['reviewId'],'Q/R mapping');check(jsha(q)==selected[rid]['pointsSha256'],'frozen points hash');check(rec['userRating'] is None,'rating empty')
  for xs,ys in [(top,rec['top3d']),(bottom,rec['bottom3d'])]:
   for x,y in zip(xs,ys):
    for u,v in zip(x,y):
     delta=abs(u-v);maximum_3d=max(maximum_3d,delta);check(delta<1e-11,'independent 3D')
  edges=[('top',i,top[i],top[(i+1)%n]) for i in range(n)]+[('bottom',i,bottom[i],bottom[(i+1)%n]) for i in range(n)]+[('vertical',i,top[i],bottom[i]) for i in range(n)]
  check(len(edges)==len(rec['erpPaths']),'edge count')
  for exp,actual in zip(edges,rec['erpPaths']):
   kind,ix,aa,bb=exp;check(actual['kind']==kind and actual['index']==ix,'edge identity')
   samples=[projection(blend(aa,bb,i/99.)) for i in range(100)];segments=[[]];edge_seams=0
   for i,xy in enumerate(samples):
    if i and abs(xy[0]-samples[i-1][0])>512:
     t=-aa[0]/(bb[0]-aa[0]);cross=blend(aa,bb,t);cy=projection(cross)[1]
     check(cross[2]>0 and (i-1)/99.-1e-12<=t<=i/99.+1e-12,'exact seam crossing')
     before=1024. if samples[i-1][0]>512 else 0.;segments[-1].append([before,cy]);segments.append([[1024.-before,cy]])
     seams+=1;edge_seams+=1
    segments[-1].append(xy)
   check(actual['seamSplit']==bool(edge_seams),'seam status');check(len(segments)==len(actual['segments']),'split count')
   for expected,got in zip(segments,actual['segments']):
    check(len(expected)==len(got),'sample count')
    for i,(e,g) in enumerate(zip(expected,got)):
     points+=1;check(0<=g[0]<=1024 and 0<=g[1]<=512,'ERP bounds')
     for u,v in zip(e,g):
      delta=abs(u-v);maximum_erp=max(maximum_erp,delta);check(delta<=.5001e-6,'independent ERP projection')
     if i:check(abs(g[0]-got[i-1][0])<=512,'no false seam chord')
 if a.metrics:
  sys.dont_write_bytecode=True;sys.path.insert(0,str(a.vendor));from components_reused import compare,intrinsic
  for rec in im['annotations']:
   ins=intrinsic(rec)
   for version,ref in refs.items():
    c=compare(rec,ref);m={'iou':c.get('iou'),'C':c.get('centroid_distance_normalized'),'U':c.get('top_mae_deg'),'B':c.get('bottom_mae_deg'),'T':c.get('top3d_symmetric_mean_h'),'dir':ins.get('direction_rms_deg'),'flat':ins.get('flat_top_angular_rms_deg'),'F':c.get('floor3d_symmetric_mean_h'),'omission':c.get('omission_ref'),'extension':c.get('extension_ref')}
    s=geo['scales'];m['LC']=1-m['iou']+.5*m['C'];m['LCT']=m['LC']+.3*s['L']*m['T']/s['T'];m['LCG']=m['LC']+.3*s['L']*.5*(m['dir']/s['dir']+m['flat']/s['flat'])
    stored=rec['metricsByReference'][version]['metrics']
    for key,value in m.items():
     target=stored[key];metric_checks+=1
     if value is None or target is None:check(value is None and target is None,'metric NA unchanged')
     else:
      delta=abs(value-target);metric_max=max(metric_max,delta);check(delta<1e-9,'metric reproduction '+rid+' '+key)
check(record_count==44 and seams==88,'44 geometries and 88 seam edges')
fingerprint=jsha({'images':[{'code':im['code'],'imageSha256':im['imageSha256'],'annotations':[{'reviewId':r['reviewId'],'id':r['id'],'points':r['points']} for r in im['annotations']],'groundtruths':[{'id':r['id'],'version':r['version'],'points':r['points']} for r in im['groundtruths']]} for im in geo['images']]})
check(fingerprint==geo['datasetFingerprintSha256'],'content fingerprint recomputed')
print(json.dumps({'passed':True,'checks':count,'geometryRecords':record_count,'erpSamplesChecked':points,'seamSplitEdges':seams,'maximum3dDifference':maximum_3d,'maximumErpDifferencePx':maximum_erp,'metricChecks':metric_checks,'maximumMetricDifference':metric_max,'datasetFingerprintSha256':fingerprint,'limits':'Public artifacts verify selected geometry and deterministic selection. Full-source population eligibility is pinned by provenance hashes and was checked during preparation; unselected source coordinates and original photographs are intentionally absent.'},indent=2))
