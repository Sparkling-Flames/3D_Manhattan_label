"""Intercept-only controls matched to the exact stratified Ridge pipeline."""
from tools.thesis_main.analysis.image_portrait.difficulty_stratified_cv import *
from tools.thesis_main.analysis.image_portrait.difficulty_stratified_results import measure,paired

def main():
 np.save(O/'cache/control__zero.npy',np.zeros((106,1),np.float32));pieces=[]
 for flag,design in [(False,'pooled'),(True,'within_coarse'),('main','within_main')]:
  run_feature('control__zero',flag);q=pd.read_csv(O/'cv'/design/'control__zero.csv.gz');pieces.append(q[q.algorithm=='ridge'])
 z=csv('controls/matched_intercept_predictions.csv',pd.concat(pieces,ignore_index=True));csv('controls/matched_intercept_scores.csv',[dict(design=k[0],baseline=k[1],**measure(g))for k,g in z.groupby(['design','baseline'])])
 p=pd.read_csv(O/'results/all_oof_predictions.csv.gz');out=[]
 for (design,mode),b in z.groupby(['design','baseline']):
  for name in ['selected__existing','selected__feedback','selected__dinov3','selected__existing_plus_dino','selected__all_models']:
   a=p[(p.design==design)&(p.baseline==mode)&(p.algorithm=='ridge')&(p.feature==name)];out.append(paired(a,b,design+' '+name+'['+mode+'] vs matched intercept'))
 csv('controls/matched_intercept_paired.csv',out);savej('controls/method.json',dict(control='same hierarchy, training subset, class-residualization and clipping, but all covariates zero',interpretation='matches the unsmoothed training-stratum intercept implicit in linear Ridge; not a learned visual representation',primary_control_algorithm='Ridge only',knn_note='zero-feature kNN has arbitrary tied neighbors and is not used as a no-information comparator',group_strength_for_initial_frequency_baselines=3))
 print('CONTROLS DONE',flush=True)
if __name__=='__main__':main()
