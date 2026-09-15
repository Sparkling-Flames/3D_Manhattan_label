"""Assignment-aware image prediction with genuinely cross-fitted worker history.

For *every* training/test image, historical worker effects exclude that image's
building, all outer test buildings, and all inner validation buildings. Only the
identities/count of actual assigned people, not their target outcomes, are used.
Unknown axes remain missing and never become a personnel type.
"""
import json
import numpy as np
import pandas as pd
from tools.thesis_main.analysis.image_portrait.pro_core import BUNDLE,OUT,load,write_json
from tools.thesis_main.analysis.image_portrait.pro_workers import ProfileCache,ALL_AXES

class AssignmentFeatures:
    def __init__(self,image_ids,condition,base,mode):
        self.ids=list(image_ids);self.base=base;self.mode=mode
        raw=pd.read_csv(OUT/'human/response_metrics.csv.gz');raw=raw[raw.main_worker_included & (raw.raw_condition==condition)]
        self.rosters=raw.groupby('image_id').worker_id.apply(list).to_dict();self.stages=raw.groupby('image_id').stage.apply(list).to_dict()
        old=pd.DataFrame(load(BUNDLE/'history/worker_axes_historical.jsonl.gz'));old=old[old.main_worker_included].copy();old['value']=old.value.astype(float);self.cache=ProfileCache(old);self.memo={}
    def __call__(self,excluded):
        key=tuple(sorted(excluded))
        if key in self.memo:return self.memo[key]
        rows=[]
        for image in self.ids:
            workers=self.rosters[image];n=len(workers);v=[np.log1p(n)]
            if self.mode=='composition':
                profile,_=self.cache.fit(set(excluded)|{image.split('_')[0]})
                for axis in ALL_AXES:
                    vals=[profile.loc[w,axis]for w in workers if axis in profile and w in profile.index and pd.notna(profile.loc[w,axis])]
                    v += [float(np.mean(vals)) if vals else np.nan,float(np.std(vals)) if vals else np.nan,len(vals)/n]
            if self.mode=='context':
                stages=self.stages[image];v += [stages.count(s)/len(stages) for s in ['P1','C1','C2-B','C2-A-RP']]
            rows.append(v)
        result=np.column_stack([self.base,np.asarray(rows)])
        self.memo[key]=result
        # The descriptors, rather than any target values, are the only retained
        # fold-specific features. Cache growth is bounded by exclusion pairs.
        return result

def register():
    root=OUT/'features';registry=json.loads((root/'registry.json').read_text());base=registry['ABC_traits_feedback_shared']
    for name,mode in [('ABCN_actual_people_count','count'),('ABCP_crossfit_worker_composition','composition'),('ABCC_historical_context','context')]:
        registry[name]={**base,'dimensions':base['dimensions']+{'count':1,'composition':19,'context':5}[mode],'family':'increment_personnel','dynamic_assignment':mode,'prespecified':False,'exact_duplicate_of':None,'columns':[]}
    write_json(root/'registry.json',registry)

if __name__=='__main__':register()
