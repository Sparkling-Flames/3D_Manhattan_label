#!/usr/bin/env python3
"""Evaluate the mathematical class-capacity boundary instead of imposing K."""
import pandas as pd
import discover_behavior_classes as b
import discover_joint_qt as j

def main():
    x=b.load();rows=[]
    for method,cls,families in [('V3_BEHAVIOR',b.Study,b.FAMILIES),('V3_JOINT_QT',j.Joint,j.FAMILIES)]:
        study=cls(x)
        for condition in ['manual','semi']:
            for heldout in ['ALL']+study.buildings:
                for family in families:
                    fits=study.fitted(condition,() if heldout=='ALL' else (heldout,),family)
                    valid=[k for k,v in fits.items() if v['eligible']]
                    rows.append(dict(method=method,condition=condition,heldout_building=heldout,family=family,
                        capacity_max_k=max(valid,default=0),k8_allowed=8 in valid,
                        n_workers=len(next(iter(fits.values()))['workers']) if fits else 0))
    b.save(pd.DataFrame(rows),'CLASS_CAPACITY_LIMITS.csv')
    print(pd.DataFrame(rows).groupby(['method','condition','family']).capacity_max_k.agg(['min','max']).to_string())

if __name__=='__main__':main()
