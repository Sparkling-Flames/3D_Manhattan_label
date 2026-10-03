from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from shapely.geometry import shape,Polygon
ROOT=Path(__file__).resolve().parents[1]
def main():
 out=ROOT/'figures';out.mkdir(exist_ok=True);paths=[]
 f=pd.read_csv(ROOT/'results/exact_vs_16.csv'); s=f[f.method=='mv_strict']
 fig,ax=plt.subplots(figsize=(8.5,4.8))
 ax.plot(s.k,s.sample16_mean,'o--',label='Published design: 16 permutations, distinct subsets')
 ax.plot(s.k,s.exact_mean,'s-',label='All 255 nonempty subsets (uniform at each k)')
 ax.set(xlabel='Distinct people k (fixed pool N = 8)',ylabel='Mean BEV IoU with original reference',title='Exact enumeration changes the small-k curve\n2t7WUuJeko7-07: strict majority; exploratory doorway group',xticks=range(1,9),ylim=(.40,.68));ax.legend(loc='lower right');fig.tight_layout()
 path=out/'01_sampling_exact.png';fig.savefig(path,dpi=170);plt.close(fig);paths.append(path)
 s=pd.read_csv(ROOT/'results/support_field_finite_population.csv');d=json.loads((ROOT/'results/support_field.json').read_text())
 fig,ax=plt.subplots(figsize=(8.5,4.8))
 ax.plot(s.k,s.expected_soft_loss,'o-',label='Expected squared difference: support field vs reference')
 ax.plot(s.k,s.expected_within_prefix_disagreement,'s-',label='Expected disagreement inside the sampled prefix')
 ax.axhline(d['mean_individual_symmetric_difference'],linestyle='--',label='Mean individual symmetric-difference loss (constant)')
 ax.set(xlabel='Distinct people k',ylabel='Area normalized by the fixed reference area',title='Fusion stability is not agreement between original annotations\nExact finite-pool averages; no claim of visual truth',xticks=range(1,9),ylim=(0,.65));ax.legend(loc='center right');fig.tight_layout()
 path=out/'02_support_decomposition.png';fig.savefig(path,dpi=170);plt.close(fig);paths.append(path)
 data=json.loads((ROOT/'inputs/subset.json').read_text());g=data['groups'][0]
 geoms=json.loads((ROOT/'results/full_geometry.geojson').read_text())
 fig,ax=plt.subplots(figsize=(7,6))
 poly=Polygon(g['references']['original']);xy=np.array(poly.exterior.coords);ax.plot(xy[:,0],xy[:,1],linewidth=2,label='Original reference (ring not human-confirmed)')
 for feature in geoms['features']:
  p=shape(feature['geometry']);arr=np.array(p.exterior.coords)
  ax.plot(arr[:,0],arr[:,1],linestyle='--' if feature['properties']['method']=='mv_strict' else '-',label='All eight: '+feature['properties']['method'])
 ax.scatter([0],[0],marker='x',s=60,label='Camera');ax.set_aspect('equal');ax.set(xlabel='X / camera height',ylabel='Z / camera height',title='Same inputs, two explicit tie rules\nDeclared regions; not a visual correctness judgement');ax.legend(loc='lower left');fig.tight_layout()
 path=out/'03_full_geometry.png';fig.savefig(path,dpi=170);plt.close(fig);paths.append(path)
 return paths
if __name__=='__main__':main()
