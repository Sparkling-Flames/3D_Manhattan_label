import pathlib,json,csv,numpy as np,math,itertools
P=pathlib.Path('pro_round4_review_20261012/extracted/quality_top_structure_research_20261012');S=P/'structure_height_preference_20261012';geo=json.load(open(next(P.rglob('current_geometry_compact.json'))))['geometries'];read=lambda f:list(csv.DictReader(open(f,encoding='utf-8-sig')))
def direction(g):
 q=np.array(g['bottom3d'])[:,[0,2]];e=np.roll(q,-1,axis=0)-q;w=np.linalg.norm(e,axis=1);a=np.degrees(np.arctan2(e[:,1],e[:,0]))%90;cuts=np.unique(np.r_[0,(a+45)%90,90]);best=1e10
 for lo,hi in zip(cuts[:-1],cuts[1:]):
  mid=(lo+hi)/2;aa=mid+(a-mid+45)%90-45;phi=np.clip(np.dot(w,aa)/w.sum(),lo,hi);loss=np.dot(w,((a-phi+45)%90-45)**2)/w.sum();best=min(best,loss)
 return math.sqrt(best)
rows=read(S/'structure/results/real39_structural_metrics.csv')+read(S/'structure/results/development907_structural_metrics.csv');errs=[abs(direction(geo[x['object_id']])-float(x['dir'])) for x in rows]
r=json.load(open(S/'height/results/candidate_scores_39.json'));es=[]
for x in r:
 d=x['dir'];base=1+x['S_bottom_deg']**2/32+(x['Hmean']/.5)**2+(x['Hcenter']/.25)**2
 for cap,key in [(1,'Q_dbounded1_hsplit'),(2,'Q_dbounded2_hsplit')]:es.append(abs(100*x['iou_2d']/(base+cap*d*d/(d*d+25))-x[key]))
 for key in ['Q_dbounded1_hsplit_weakTop']:es.append(abs(100*x['iou_2d']/(base+d*d/(d*d+25)+x['S_top_deg']**2/512)-x[key]))
print('independent D 946 maxdiff',max(errs),'3 candidate x39 maxdiff',max(es))
print('keycases',[(x['case_id'],x['Q_dbounded1_hsplit'],x['Q_dbounded2_hsplit']) for x in r if x['case_id'] in ['T20','T09','T22','T13']])
result=dict(D_rows=len(rows),D_max_delta=max(errs),scalar_cells=len(es),scalar_max_delta=max(es),method='independent interval minimization and direct scalar equations; not independent human validation')
pathlib.Path('pro_round4_review_20261012/independent_checks.json').write_text(json.dumps(result,indent=2))
