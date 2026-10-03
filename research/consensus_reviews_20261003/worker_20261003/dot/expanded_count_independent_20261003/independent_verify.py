"""Read-only independent A-line audit. No source algorithm imports or source changes.
Primary new computational question fixed before numerical run: original-GT 8 -> 20
contrast in the frozen N>=20 panel, both rules, 16,384 NEW independent draws/image.
Also regenerate original seed orders for source checks. Family: two rules, alpha=.05.
"""
import argparse,csv,json,math,time,warnings,zlib,hashlib
from collections import Counter,defaultdict
from itertools import combinations
from pathlib import Path
import numpy as np
from shapely.geometry import Polygon
from shapely.ops import unary_union,polygonize
from shapely import contains_xy
ROOT=Path(__file__).resolve().parent; D=ROOT/'analysis_results/lee_expanded_20261003'; O=ROOT/'independent_results';O.mkdir(exist_ok=True)
DRAW=16384; NEWSEED=30412027; METHODS=('mv50','mv_strict')
PC=np.array([i.bit_count() for i in range(65536)],dtype=np.uint8)
def readj(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def readc(p):return list(csv.DictReader(p.open(encoding='utf-8-sig')))
def writej(name,x):(O/name).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def writec(name,x):
 with (O/name).open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=x[0].keys());w.writeheader();w.writerows(x)
def eligible(r):return r['independent'] and r['consensus_eligible'] and r['condition']=='manual' and r['main_consensus_gate']['status']=='main_candidate'
def exactks(n):return set(range(1,n+1)) if n<=9 else {1,2,n-2,n-1,n}
def masks_exact(n,k):return np.fromiter((sum(1<<j for j in s) for s in combinations(range(n),k)),np.uint32)
def make_basis(polys,refs):
 tiles=list(polygonize(unary_union([p.boundary for p in polys])))
 xy=np.array([(p.representative_point().x,p.representative_point().y) for p in tiles])
 v=np.array([contains_xy(p,xy[:,0],xy[:,1]) for p in polys])
 keep=v.any(axis=0);v=v[:,keep];tiles=[p for p,b in zip(tiles,keep) if b]
 area=np.array([p.area for p in tiles]); assert np.max(abs(v@area-np.array([p.area for p in polys])))<1e-8
 patterns=(v.T.astype(np.uint32)@ (1<<np.arange(len(polys),dtype=np.uint32)))
 p,ix=np.unique(patterns,return_inverse=True)
 a=np.bincount(ix,weights=area)
 overlap={key:np.bincount(ix,weights=[t.intersection(g).area for t in tiles],minlength=len(a)) for key,g in refs.items()}
 return p,a,overlap,len(tiles)
def scores(basis,refs,masks,k):
 p,a,overlap,_=basis;out={(m,v):[] for m in METHODS for v in refs}
 for j in range(0,len(masks),512):
  x=masks[j:j+512,None]&p;votes=PC[x&65535]+PC[x>>16]
  for m in METHODS:
   sel=votes>=((k+1)//2 if m=='mv50' else k//2+1)
   area=np.einsum('ij,j->i',sel,a)
   for v,g in refs.items():
    inter=np.einsum('ij,j->i',sel,overlap[v]);out[m,v].append(inter/(g.area+area-inter))
 return {x:np.clip(np.concatenate(z),0,1) for x,z in out.items()}
def prefixes(seed,n):
 rng=np.random.default_rng(seed);orders=np.array([rng.permutation(n) for _ in range(DRAW)],dtype=np.uint8)
 return np.bitwise_or.accumulate(1<<orders.astype(np.uint32),axis=1)
def audit_metadata(data,src,inventory,stored):
 manifest=[]
 for f in readj(ROOT/'remote_manifest.json'):
  p=D/f['name']
  if p.exists():
   b=p.read_bytes();sha=hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest();manifest.append(dict(file=f['name'],size=len(b),expected_git_blob=f['sha'],actual_git_blob=sha,equal=sha==f['sha']))
 # Independently reconstruct full-pool selection from inventory, rather than trusting saved ledger.
 ims={r['image']:r for r in inventory['images']};groups=defaultdict(list)
 for r in inventory['records']:groups[r['image'],r['condition'],r['consensus_gate']].append(r)
 selected=[];failed=[]
 for (im,condition,gate),rr in groups.items():
  cc=[r for r in rr if r['consensus_candidate']]
  if condition=='manual' and gate=='main_candidate' and len(cc)>=2 and all(r['quality_candidate'] for r in cc):
   (selected if all(r['bev_ok'] for r in cc) and ims[im]['original_bev_ok'] else failed).append(im)
 assert set(selected)=={i['code'] for i in data['images']}
 assert set(selected+failed)=={i['code'] for i in src['images']}
 assert all(i==next(x for x in src['images'] if x['code']==i['code']) for i in data['images'])
 rrs={i['code']:sorted([r for r in i['annotations'] if eligible(r)],key=lambda r:r['id']) for i in data['images']}
 assert all(len({r['worker'] for r in rs})==len(rs) and all(r['quality_candidate'] and r['footprint'] is not None for r in rs) for rs in rrs.values())
 for i,rs in rrs.items():assert {r['id'] for r in rs}=={r['id'] for r in inventory['records'] if r['image']==i and r['condition']=='manual' and r['consensus_gate']=='main_candidate' and r['consensus_candidate']}
 badrows=[r for i in src['images'] if i['code'] in failed for r in i['annotations'] if eligible(r) and r['footprint'] is None]
 panels=[]
 for k in (2,4,8,12,16,20,24):
  pp=[i for i in data['images'] if len(rrs[i['code']])>=k];panels.append(dict(k=k,images=len(pp),buildings=len({i['building'] for i in pp}),difficulty=dict(Counter(i['difficulty'] for i in pp)),medium_buildings=dict(Counter(i['building'] for i in pp if i['difficulty']=='中等'))))
 exact=sum(r['estimator']=='exact' for r in stored);mc=len(stored)-exact;bound=math.sqrt(math.log(2*mc/.05)/(2*DRAW))
 for r in stored:
  n,k=int(r['n']),int(r['k']);assert (r['estimator']=='exact')==(k in exactks(n));assert float(r['mc_error_bound'])==(0 if k in exactks(n) else bound)
  assert int(r['evaluated_draws'])==(math.comb(n,k) if k in exactks(n) else DRAW)
 summary=dict(computable_images=len(rrs),buildings=len({i['building'] for i in data['images']}),votes=sum(map(len,rrs.values())),workers=len({r['worker'] for rs in rrs.values() for r in rs}),analysis_records=sum(len(i['annotations']) for i in data['images']),source_images=len(src['images']),source_records=sum(len(i['annotations']) for i in src['images']),source_references=sum(len(i['references']) for i in src['images']),failed_images=failed,failed_records=[dict(id=r['id'],footprint_state=r['footprint_state']) for r in badrows],stored_exact=exact,stored_mc=mc,simultaneous_hoeffding_bound=bound,panels=panels)
 writej('metadata_checks.json',summary);writej('download_git_blob_checks.json',manifest)
 # Verify every saved fixed panel row independently from per-image means, including explicit image lists.
 idx={(r['image'],r['method'],r['version'],int(r['k'])):r for r in stored};errors=[]
 for r in readc(D/'fixed_panel_curves.csv'):
  names=r['images'].split('|');assert len(names)==int(r['image_n']);assert len(names)==len(set(names));k=int(r['k']);assert all(len(rrs[i])>=int(r['panel_max_k']) for i in names)
  vals=[idx[i,r['method'],r['version'],k] for i in names]
  got=np.mean([float(x['iou_mean']) for x in vals]);bound2=np.mean([float(x['mc_error_bound']) for x in vals]);base=np.mean([float(idx[i,r['method'],r['version'],1]['iou_mean']) for i in names])
  errors.append(max(abs(got-float(r['iou_mean'])),abs(bound2-float(r['mc_error_bound'])),abs(got-base-float(r['gain_from_one']))))
 writej('fixed_summary_checks.json',dict(rows=len(errors),max_abs_difference=max(errors)))
 return rrs

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--all-k',action='store_true');args=ap.parse_args()
 data=readj(D/'input.json');src=readj(D/'source_input.json');inv=readj(D/'inventory_input.json');stored=readc(D/'curves.csv');rrs=audit_metadata(data,src,inv,stored)
 si={(r['image'],r['method'],r['version'],int(r['k'])):r for r in stored};rosters={r['image']:r for r in readj(D/'rosters.json')}
 results=[];endpoint=[];paired=[];drawsums={s:{m:np.zeros(DRAW) for m in METHODS} for s in ('source','new')};ranges=[];notices=[];start=time.time()
 for num,im in enumerate(data['images']):
  name=im['code'];rs=rrs[name];n=len(rs);refs={r['version']:Polygon(r['footprint']) for r in im['references'] if r['footprint'] is not None};polys=[Polygon(r['footprint']) for r in rs]
  assert all(p.is_valid and p.area>0 for p in polys)
  with warnings.catch_warnings(record=True) as caught:
   warnings.simplefilter('always');basis=make_basis(polys,refs)
   assert [r['id'] for r in rs]==rosters[name]['record_ids']
   full=scores(basis,refs,np.array([(1<<n)-1],np.uint32),n)
   for m in METHODS:
    for v,g in refs.items():
     singleton=np.mean([p.intersection(g).area/p.union(g).area for p in polys]);whole=float(full[m,v][0]);endpoint.append(dict(image=name,n=n,method=m,version=v,singleton=singleton,full=whole,gain=whole-singleton,singleton_error=singleton-float(si[name,m,v,1]['iou_mean']),full_error=whole-float(si[name,m,v,n]['iou_mean'])))
   ks=set(range(1,n+1)) if args.all_k else {1,n}
   if n>=20:ks|={8,20}
   order=prefixes(rosters[name]['seed'],n) if any(k not in exactks(n) for k in ks) else None
   cache={}
   for k in sorted(ks):
    masks=masks_exact(n,k) if k in exactks(n) else order[:,k-1];cache[k]=scores(basis,refs,masks,k)
    for (m,v),s in cache[k].items():
     assert int(si[name,m,v,k]['unique_subsets'])==len(np.unique(masks))
     results.append(dict(image=name,n=n,k=k,method=m,version=v,recomputed_mean=float(s.mean()),stored_mean=float(si[name,m,v,k]['iou_mean']),error=float(s.mean())-float(si[name,m,v,k]['iou_mean']),draws=len(s)))
   if n>=20:
    ranges.append(1 if 20 in exactks(n) else 2)
    for seedkind,pref in [('source',order),('new',prefixes(NEWSEED+zlib.crc32(name.encode()),n))]:
     s8=cache[8] if seedkind=='source' else scores(basis,refs,pref[:,7],8)
     s20=cache[20] if 20 in exactks(n) or seedkind=='source' else scores(basis,refs,pref[:,19],20)
     for m in METHODS:
      x20=float(s20[m,'original'].mean()) if 20 in exactks(n) else s20[m,'original'];z=x20-s8[m,'original'];drawsums[seedkind][m]+=z
      paired.append(dict(image=name,n=n,method=m,seed=seedkind,k20_exact=20 in exactks(n),mean_gain=float(z.mean()),sd_draw=float(z.std(ddof=1)),mc_se=float(z.std(ddof=1)/math.sqrt(DRAW))))
  notices.extend(dict(image=name,category=w.category.__name__,message=str(w.message)) for w in caught)
  print(num+1,name,n,len(basis[0]),round(time.time()-start,2),flush=True)
  if (num+1)%10==0:writec('endpoint_checks.partial.csv',endpoint)
 writec('endpoint_checks.csv',endpoint);writec('recomputed_means.csv',results);writec('paired_contrast_per_image.csv',paired);writej('geometry_warnings.json',notices)
 summary=[];mcount=len(ranges);log=math.log(4/.05)
 for seedkind in drawsums:
  for m,x in drawsums[seedkind].items():
   z=x/mcount;se=z.std(ddof=1)/math.sqrt(DRAW)
   hoeffding=math.sqrt(log*sum(r*r for r in ranges)/(2*DRAW*mcount*mcount))
   # Maurer-Pontil (2009), Thm 4: bounded IID empirical Bernstein, Bonferroni two rules.
   eblog=math.log(8/.05)  # two-sided bound for each of two rules
   eb=math.sqrt(2*z.var(ddof=1)*eblog/DRAW)+7*(sum(ranges)/mcount)*eblog/(3*(DRAW-1))
   summary.append(dict(seed=seedkind,method=m,images=mcount,draws_per_image=DRAW,mean_gain=float(z.mean()),mc_se=float(se),normal_approx_95_half_width=float(1.96*se),paired_two_rule_family_hoeffding=hoeffding,paired_two_rule_family_empirical_bernstein=float(eb),eb_lower=float(z.mean()-eb),eb_upper=float(z.mean()+eb),hoeffding_lower=float(z.mean()-hoeffding),hoeffding_upper=float(z.mean()+hoeffding),range_width=sum(ranges)/mcount,range1_images=ranges.count(1),range2_images=ranges.count(2)))
 writej('paired_contrast_summary.json',summary);writej('run_summary.json',dict(all_k=args.all_k,elapsed_seconds=time.time()-start,recomputed_means=len(results),max_mean_error=max(abs(r['error']) for r in results),endpoint_means=len(endpoint)*2,max_endpoint_error=max(max(abs(r['singleton_error']),abs(r['full_error'])) for r in endpoint),python=__import__('sys').version,numpy=np.__version__,shapely=__import__('shapely').__version__,new_seed=NEWSEED,draws=DRAW))
 np.savez_compressed(O/'paired_mean_draws.npz',**{s+'_'+m:x/mcount for s,mm in drawsums.items() for m,x in mm.items()})
 print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
