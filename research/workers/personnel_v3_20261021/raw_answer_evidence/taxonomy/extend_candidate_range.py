#!/usr/bin/env python3
"""Complete missing K above the initial 2..8 grid to actual capacity limits."""
import pandas as pd
import discover_behavior_classes as b
import discover_joint_qt as j

def main():
    x=b.load();caps=pd.read_csv(b.HERE/'CLASS_CAPACITY_LIMITS.csv')
    for method,cls,prefix in [('V3_BEHAVIOR',b.Study,''),('V3_JOINT_QT',j.Joint,'JOINT_')]:
        s=cls(x);p=b.HERE/(prefix+'INNER_BUILDING_CANDIDATE_LOSSES.csv.gz');old=pd.read_csv(p);new=[]
        for r in caps[caps.method.eq(method)&caps.capacity_max_k.gt(8)].itertuples():
            for inner in [v for v in s.bb[r.condition] if v!=r.heldout_building]:
                exc=tuple(sorted(set([inner]+([] if r.heldout_building=='ALL' else [r.heldout_building]))))
                for k in range(9,r.capacity_max_k+1):
                    out=s.evaluate(r.condition,exc,inner,r.family,k)
                    if out is not None:new.append(dict(heldout_building=r.heldout_building,**out))
        combined=pd.concat([old,pd.DataFrame(new)],ignore_index=True)
        combined=combined.drop_duplicates(['condition','heldout_building','target_building','family','k'])
        b.save(combined,p.name)
        print(method,'new inner rows',len(new),'total',len(combined),flush=True)
    b.js('CAPACITY_RANGE_AMENDMENT.json',dict(reason='User sets no class-count limit; initial computational grid extended wherever actual Ward class sizes support more classes',
        mathematical_upper_bound=max(b.KS),max_supported_k=int(caps.capacity_max_k.max()),capacity_evaluations=len(caps),
        capacity_rule='minimum 3 members, monotone under Ward splitting',new_team_outcomes_seen=False))

if __name__=='__main__':main()
