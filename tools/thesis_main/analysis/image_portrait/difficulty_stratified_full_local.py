"""Preserve all six face identities in the local comparison; no new viewpoints."""
from tools.thesis_main.analysis.image_portrait.difficulty_stratified_prepare import *
def main():
 ids=pd.read_csv(O/'images/labels106.csv').image_id.tolist();extra=[]
 for model,layers in [('dinov3',[3,6,9,11,12]),('da3',[5,7,9,11])]:
  for layer in layers:
   key=f'{model}__block{layer}__faces_local96'if model=='dinov3'else f'{model}__layer{layer}__faces_local96';mat=[]
   for i in ids:
    with np.load(B/'models'/model/(i+'.features.npz'),allow_pickle=False)as z:
     names=[f'{face}_block{layer}_patch_local16'for face in FACES]if model=='dinov3'else[f'{face}_view0_out_layer_{layer}_local16'for face in FACES]
     a=np.concatenate([z[n].ravel()for n in names]);assert a.shape==(147456,)and np.isfinite(a).all();mat.append(a)
   np.save(O/'cache'/f'{key}.npy',np.asarray(mat,np.float32));extra.append(dict(feature=key,dimension=147456,n_images=106,model=model,pooling='ordered 6 faces x 16 local strips x full channel mean/std; not additional capture positions',candidate_kind='full_local_prespecified_layers_followup_pooling'))
   print('LOCAL',key,flush=True)
 inv=pd.read_csv(O/'models/feature_inventory.csv');inv=inv[~inv.feature.str.endswith('__faces_local96')];csv('models/feature_inventory.csv',pd.concat([inv,pd.DataFrame(extra)],ignore_index=True))
if __name__=='__main__':main()
