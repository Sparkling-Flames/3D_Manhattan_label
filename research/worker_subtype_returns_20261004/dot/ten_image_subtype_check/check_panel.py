"""Independent finite ten-image panel check. Fixed original-Q LOBO median labels.

No source scripts executed; stored polygons and identities are read without repair.
The 2-image delivery is an equivalence anchor, not new blind validation.
"""
from pathlib import Path
import csv, json, hashlib, math, sys, argparse, statistics
import numpy as np
from shapely.geometry import Polygon
from shapely.ops import unary_union, polygonize

ROOT=Path(__file__).resolve().parent
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--out',required=True,help='New output directory; must not already exist')
args=parser.parse_args()
OUT=Path(args.out).resolve()
if OUT.exists():raise SystemExit('Output directory already exists; choose a new directory')
SOURCE=ROOT/'inputs/footprints_240.json'
SOURCE_BLOB='5a174746730bb70e405680a3748663caf56dd51f'

def readcsv(path):
    with path.open() as f: return list(csv.DictReader(f))
def writecsv(name,rows):
    with (OUT/name).open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def hg(N,c,k,j):
    if j<0 or j>c or k-j<0 or k-j>N-c: return 0.
    return math.comb(c,j)*math.comb(N-c,k-j)/math.comb(N,k)
def inclusion(c,k,rule):
    t=(k+1)//2 if rule=='mv50' else k//2+1
    return sum(hg(12,c,k,j) for j in range(t,k+1))
def disjoint_difference(c,k,rule):
    t=(k+1)//2 if rule=='mv50' else k//2+1
    return sum(hg(12,c,k,j)*hg(12-k,c-j,k,l)
               for j in range(k+1) for l in range(k+1) if (j>=t)!=(l>=t))

source_manifest=json.loads((ROOT/'SOURCE_MANIFEST.json').read_text())
for relative,expected in source_manifest['files'].items():
    content=(ROOT/relative).read_bytes()
    assert len(content)==expected['bytes'] and hashlib.sha256(content).hexdigest()==expected['sha256'],relative
data=json.loads(SOURCE.read_bytes());blob=data['upstream_source_git_blob'];assert blob==SOURCE_BLOB
matrix=readcsv(ROOT/'inputs/matrix_original_iou.csv')
matrix_bytes=(ROOT/'inputs/matrix_original_iou.csv').read_bytes()
assert hashlib.sha1(b'blob '+str(len(matrix_bytes)).encode()+b'\0'+matrix_bytes).hexdigest()==source_manifest['matrix_original_git_blob']
OUT.mkdir(parents=True)
workers=list(matrix[0])[2:];assert len(workers)==24
assign=readcsv(ROOT/'inputs/frozen_labels.csv')
assert len(data['images'])==len(matrix)==10
design={'purpose':'Finite ten-image check of raw within-subtype dispersion and same-k fused-output redraw difference',
 'source':'inputs/footprints_240.json','source_git_blob':blob,'class_rule':'original reference, LOBO median 12/12, frozen labels',
 'k':[4,6],'rules':['mv50','mv_strict'],'normalization':'fixed all-24-person polygon union area per image',
 'couplings':['independent draws may overlap','disjoint draws'],
 'no_geometry_repairs':True,'new_workers':0,'excluded_historical_records':20,
 'inference_scope':'descriptive same already-explored panel; not new buildings, new people, T/S/B, or visual quality',
 'prior_k4_status':'k4 is replication anchor of earlier ten-image analysis, not all new',
 'stopping_condition':'10 images x 2 subtypes x k4/6 x 2 rules; no six-person IoU enumeration'}
(OUT/'DESIGN.json').write_text(json.dumps(design,indent=2,ensure_ascii=False)+'\n')
rows=[];disp=[];rosters=[];audits=[];anchor=[]
excluded_meta=readcsv(ROOT/'inputs/exclusion_manifest.csv')
assert all(r['independent']=='False' and r['consensus_eligible']=='False' and r['quality_candidate']=='False' for r in excluded_meta)
excluded=[{k:r[k] for k in ['image','worker','record_id']} for r in excluded_meta]
for image in data['images']:
    code=image['code'];building=image['building']
    records=[r for r in image['annotations'] if r['worker'] in workers]
    assert len(records)==24 and set(r['worker'] for r in records)==set(workers)
    records=sorted(records,key=lambda r:workers.index(r['worker']))
    for r in records:
        assert r['condition']=='manual' and r['independent'] and r['consensus_eligible'] and r['quality_candidate']
        assert r['footprint_state']['status']=='ok'
    assert len(image['annotations'])==24
    assert image['upstream_annotations_n']==26 and image['excluded_non_candidate_n']==2
    assert len([r for r in excluded if r['image']==code])==2
    train=np.array([[float(m[w]) for w in workers] for m in matrix if m['building']!=building])
    x=(train-train.mean(axis=1,keepdims=True)).mean(axis=0)
    med=np.median(x);assert not np.any(x==med)
    labels=(x>med).astype(int);assert sum(labels)==12
    delivery_labels={r['worker']:int(r['subtype']) for r in assign if r['policy']=='original' and r['method']=='median2' and r['target']==building}
    assert all(delivery_labels[w]==int(z) for w,z in zip(workers,labels))
    for r,z in zip(records,labels):rosters.append({'image':code,'building':building,'worker':r['worker'],'record_id':r['id'],'subtype':int(z),'calibration_buildings':'|'.join(sorted({m['building'] for m in matrix if m['building']!=building}))})
    polygons=[Polygon(r['footprint']) for r in records]
    assert all(p.is_valid and not p.is_empty and p.area>0 for p in polygons)
    U=unary_union(polygons).area
    tiles=[];votes=[]
    for tile in polygonize(unary_union([p.boundary for p in polygons])):
        point=tile.representative_point();v=np.array([p.covers(point) for p in polygons],dtype=bool)
        if v.any():tiles.append(tile);votes.append(v)
    areas=np.array([t.area for t in tiles]);votes=np.array(votes)
    residual=abs(areas.sum()-U)
    assert residual<max(1e-10,U*1e-10)
    audits.append({'image':code,'candidate_n':24,'excluded_n':image['excluded_non_candidate_n'],'tiles_n':len(tiles),'union_area':U,'tile_area_residual':residual,'labels_match_delivery':True})
    for g in [0,1]:
        ids=np.flatnonzero(labels==g)
        raw=np.mean([1-polygons[i].intersection(polygons[j]).area/polygons[i].union(polygons[j]).area for n,i in enumerate(ids) for j in ids[n+1:]])
        disp.append({'image':code,'building':building,'subtype':g,'n':12,'pair_n':66,'mean_pair_1_minus_iou':raw})
        support=votes[:,ids].sum(axis=1)
        for k in [4,6]:
            for rule in ['mv50','mv_strict']:
                q=np.array([inclusion(int(c),k,rule) for c in support])
                indep=float(areas@(2*q*(1-q))/U)
                dj=np.array([disjoint_difference(int(c),k,rule) for c in support])
                disjoint=float(areas@dj/U)
                rows.append({'image':code,'building':building,'subtype':g,'n':12,'k':k,'rule':rule,'same_k_independent_symdiff_union':indep,'same_k_disjoint_symdiff_union':disjoint,'raw_pair_1_minus_iou':raw,'union_area':U})
    if code in ['7y3sRwLe3Va-04','rPc6DW4iMge-06']:
        old_area=[r for r in readcsv(ROOT/'inputs/two_image_shape_anchors.csv') if r['image']==code]
        old_raw=[r for r in readcsv(ROOT/'inputs/two_image_raw_anchors.csv') if r['image']==code]
        for r in rows:
            if r['image']!=code:continue
            composition=f"{r['k']}|0" if r['subtype']==0 else f"0|{r['k']}"
            match=[q for q in old_area if q['policy']=='original' and q['method']=='median2' and q['composition']==composition and q['rule']==r['rule']]
            assert len(match)==1
            for metric in ['same_k_independent_symdiff_union','same_k_disjoint_symdiff_union']:
                diff=abs(r[metric]-float(match[0][metric]));assert diff<1e-10
                anchor.append({'image':code,'subtype':r['subtype'],'k':r['k'],'rule':r['rule'],'metric':metric,'absolute_difference':diff})
        for r in disp:
            if r['image']!=code:continue
            match=[q for q in old_raw if q['policy']=='original' and q['method']=='median2' and int(q['subtype'])==r['subtype']]
            assert len(match)==1
            diff=abs(r['mean_pair_1_minus_iou']-float(match[0]['mean_raw_pair_1_minus_iou']));assert diff<1e-10
            anchor.append({'image':code,'subtype':r['subtype'],'k':'','rule':'','metric':'mean_pair_1_minus_iou','absolute_difference':diff})
    print(code,'tiles',len(tiles),'done',flush=True)
assert len(rows)==80 and len(disp)==20 and len(excluded)==20
for name,rr in [('same_k_shape.csv',rows),('raw_dispersion.csv',disp),('roster.csv',rosters),('input_audit.csv',audits),('excluded_records.csv',excluded),('two_image_equivalence.csv',anchor)]:writecsv(name,rr)
print('Completed 80 shape rows; 20 raw-dispersion rows; 36 equivalence checks',flush=True)

comparison=[]
for image in sorted({r['image'] for r in disp}):
    pair={r['subtype']:r['mean_pair_1_minus_iou'] for r in disp if r['image']==image}
    row={'image':image,'raw_low':pair[0],'raw_high':pair[1],'raw_high_minus_low':pair[1]-pair[0]}
    for rule,k in [('mv50',4),('mv50',6),('mv_strict',4),('mv_strict',6)]:
        v={r['subtype']:r['same_k_independent_symdiff_union'] for r in rows if r['image']==image and r['rule']==rule and r['k']==k}
        row[f'{rule}_k{k}_low']=v[0];row[f'{rule}_k{k}_high']=v[1];row[f'{rule}_k{k}_high_minus_low']=v[1]-v[0]
    comparison.append(row)
writecsv('comparison_by_image.csv',comparison)
summary=[]
for metric in ['raw_high_minus_low']+[f'{rule}_k{k}_high_minus_low' for rule in ['mv50','mv_strict'] for k in [4,6]]:
    values=[float(r[metric]) for r in comparison]
    summary.append({'metric':metric,'high_more_variable_images':sum(v>0 for v in values),'high_less_variable_images':sum(v<0 for v in values),'equal_images':sum(v==0 for v in values),'mean_high_minus_low':statistics.mean(values),'median_high_minus_low':statistics.median(values)})
(OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
