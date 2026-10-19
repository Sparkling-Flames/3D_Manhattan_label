"""Numerically equivalent sidecar to frozen reverse/selection_common.py.

It pre-encodes image/building cells; model, weights and shrinkage stay unchanged.
Public wrappers accept the same DataFrames and relation series as the original.
"""
from __future__ import annotations
import hashlib
import numpy as np
import pandas as pd

PRIOR_BUILDINGS=2.0
_CACHE={}
_IDENTITY={}


def _codes(frame,columns):
    index=pd.MultiIndex.from_frame(frame[columns])
    code,unique=pd.factorize(index,sort=True)
    return np.asarray(code,dtype=int),list(unique)


def _mean(values,codes,size):
    count=np.bincount(codes,minlength=size)
    total=np.bincount(codes,weights=values,minlength=size)
    return np.divide(total,count,out=np.full(size,np.nan),where=count>0),count


class EncodedPanel:
    def __init__(self,frame,outcome="stable_main"):
        self.frame=frame
        self.outcome=outcome
        self.index=frame.index
        f=frame[["building","image_id","k","difficulty",outcome]].copy()
        f["building"]=f.building.astype(str);f["image_id"]=f.image_id.astype(str)
        f["k"]=f.k.astype(int);f["difficulty"]=f.difficulty.astype(str)
        self.y=pd.to_numeric(f[outcome],errors="coerce").to_numpy(float)
        if not np.isfinite(self.y).all():
            raise ValueError("Fast binary selection sidecar expects the complete registered stable_main denominator")
        self.imagecode,imagekeys=_codes(f,["building","image_id","k","difficulty"])
        self.images=pd.DataFrame(imagekeys,columns=["building","image_id","k","difficulty"])
        self.ng=len(self.images)
        self.bc,self.bkeys=_codes(self.images,["building","k","difficulty"]);self.nb=len(self.bkeys)
        self.bmeta=pd.DataFrame(self.bkeys,columns=["building","k","difficulty"])
        self.cc,self.ckeys=_codes(self.bmeta,["k","difficulty"]);self.nc=len(self.ckeys)
        self.bk,self.bkkeys=_codes(self.images,["building","k"])
        self.bkmeta=pd.DataFrame(self.bkkeys,columns=["building","k"])
        self.bk_k,self.kkeys=_codes(self.bkmeta,["k"])
        self.plain_image,self.plain_imagekeys=_codes(f,["building","image_id"])
        self.plain_images=pd.DataFrame(self.plain_imagekeys,columns=["building","image_id"])
        self.plain_b,self.buildings=_codes(self.plain_images,["building"])
        self.building_names=[str(x[0])for x in self.buildings]
        self.cell_for_event=pd.MultiIndex.from_frame(f[["k","difficulty"]])
        self.event_cell=pd.MultiIndex.from_tuples(self.ckeys).get_indexer(self.cell_for_event)
        image_mean,_=_mean(self.y,self.imagecode,self.ng)
        building_mean,_=_mean(image_mean,self.bc,self.nb)
        cell_mean,_=_mean(building_mean,self.cc,self.nc)
        self.cells={(int(k),str(d)):float(v)for (k,d),v in zip(self.ckeys,cell_mean)}
        bk_mean,_=_mean(image_mean,self.bk,len(self.bkkeys))
        k_mean,_=_mean(bk_mean,self.bk_k,len(self.kkeys))
        self.k_rates={int(k[0]):float(v)for k,v in zip(self.kkeys,k_mean)}
        plain_image_mean,_=_mean(self.y,self.plain_image,len(self.plain_images))
        plain_building_mean,_=_mean(plain_image_mean,self.plain_b,len(self.buildings))
        self.global_rate=float(np.mean(plain_building_mean))

    def relation_codes(self,relation):
        if isinstance(relation,pd.Series):r=relation.reindex(self.index).fillna("unknown").to_numpy()
        else:r=np.asarray(relation)
        if r.dtype.kind in ("i","u"):
            assert np.isin(r,[0,1,2]).all();return r.astype(int,copy=False)
        return np.where(r=="within",1,np.where(r=="between",2,0)).astype(int)

    def fit(self,relation):
        r=self.relation_codes(relation)
        image_mean,counts=_mean(self.y,self.imagecode+r*self.ng,3*self.ng)
        rates={};support={}
        for ri,name in [(1,"within"),(2,"between")]:
            vals=image_mean[ri*self.ng:(ri+1)*self.ng]
            ok=np.isfinite(vals)
            bvals,bcount=_mean(vals[ok],self.bc[ok],self.nb)
            valid=np.isfinite(bvals)
            sums=np.bincount(self.cc[valid],weights=bvals[valid],minlength=self.nc)
            nums=np.bincount(self.cc[valid],minlength=self.nc)
            for ci,(k,d) in enumerate(self.ckeys):
                if nums[ci]:
                    key=(int(k),str(d),name);prior=self.cells[(int(k),str(d))]
                    rates[key]=float((sums[ci]+PRIOR_BUILDINGS*prior)/(nums[ci]+PRIOR_BUILDINGS));support[key]=int(nums[ci])
        return {"global":self.global_rate,"k":self.k_rates,"cells":self.cells,"rates":rates,"support":support}

    def predict(self,calibrator,relation):
        r=self.relation_codes(relation)
        lookup=np.empty((self.nc,3))
        for i,(k,d) in enumerate(self.ckeys):
            base=calibrator["cells"].get((int(k),str(d)),calibrator["k"].get(int(k),calibrator["global"]))
            lookup[i,0]=base
            for ri,name in [(1,"within"),(2,"between")]:lookup[i,ri]=calibrator["rates"].get((int(k),str(d),name),base)
        return lookup[self.event_cell,r]

    def brier(self,predicted):
        err=(np.asarray(predicted)-self.y)**2
        im,_=_mean(err,self.plain_image,len(self.plain_images))
        b,_=_mean(im,self.plain_b,len(self.buildings))
        return pd.DataFrame({"building":self.building_names,"brier":b})


def panel(frame,outcome="stable_main"):
    # The sidecar is scoped to immutable registered event frames. Keep a bounded
    # cache, and include both row index and stable outcome/identity columns in key.
    identity=(id(frame),outcome)
    previous=_IDENTITY.get(identity)
    if previous is not None and previous.frame is frame:
        return previous
    h=pd.util.hash_pandas_object(frame[["building","image_id","k","difficulty",outcome]],index=True).to_numpy()
    key=(outcome,hashlib.sha256(h.tobytes()).hexdigest())
    if key not in _CACHE:
        if len(_CACHE)>=6:
            old=_CACHE.pop(next(iter(_CACHE)))
            stale=[i for i,v in _IDENTITY.items()if v is old]
            for i in stale:_IDENTITY.pop(i,None)
        _CACHE[key]=EncodedPanel(frame,outcome)
    _IDENTITY[identity]=_CACHE[key]
    return _CACHE[key]


def fit_calibrator(train,relation,outcome="stable_main"):
    return panel(train,outcome).fit(relation)


def predict_calibrator(calibrator,frame,relation):
    return panel(frame).predict(calibrator,relation)


def building_brier(frame,predicted,outcome="stable_main"):
    return panel(frame,outcome).brier(predicted)
