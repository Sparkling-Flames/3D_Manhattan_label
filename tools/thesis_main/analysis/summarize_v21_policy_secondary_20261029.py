"""当前策略的逐角色次要范围描述；按实际8/32条基础路径分开，不补造区间。"""
import json
import math
import numpy as np
import pandas as pd
from .rebuild_v21_20261028 import OUT,read
from .analyze_v21_current_policies_20261028 import native_module


def main():
    assert read(OUT/'current_policy_inputs/CHECKS.json')['all_non_k2_executed']
    native=native_module();F=native.F;ks_rows=[];phase_rows=[]
    for path in sorted((OUT/'current_policy_inputs').glob('*.csv.gz')):
        d=native.legalize(pd.read_csv(path,low_memory=False))
        for cohort,batch in [('original_old8','old8'),('added_reference32','added32')]:
            source=d[d.base_batch.eq(batch)]
            if source.empty:continue
            meta=source.iloc[0][F.META].to_dict();ks=np.arange(1,int(meta['pool_n'])+1)
            for policy in F.POLICIES:
                bases=sorted(set(source.loc[source.policy.eq(policy),'base_path_id'])&set(source.loc[source.policy.eq('natural_random'),'base_path_id']))
                if not bases:continue
                expected=min(8,math.factorial(int(meta['pool_n']))) if batch=='old8' else 32
                assert len(bases)==expected,(meta['pool_id'],batch,len(bases),expected)
                n=F.matrices(source[source.policy.eq('natural_random')],bases,ks);p=F.matrices(source[source.policy.eq(policy)],bases,ks)
                values=F.statistics({c:a[None] for c,a in n.items()},{c:a[None] for c,a in p.items()})[0]
                common=np.isfinite(n['B8L2'])&np.isfinite(p['B8L2'])
                for j,k in enumerate(ks):
                    if k==2:values[j]=np.nan
                    ks_rows.append(dict(**meta,cohort=cohort,policy=policy,k=int(k),base_paths=len(bases),both_Q_paths=int(common[:,j].sum()),execution_status='not_executed_policy_k2' if k==2 else 'executed',**dict(zip(F.METRICS,values[j]))))
                for phase,mask in zip(F.PHASES,F.phase_masks(ks,int(meta['pool_n']))):
                    for i,metric in enumerate(F.METRICS):
                        valid=mask&np.isfinite(values[:,i]);value=F.fixed_mean(values[:,i],valid,0)
                        phase_rows.append(dict(**meta,cohort=cohort,policy=policy,phase=phase,metric=metric,base_paths=len(bases),matched_k=int(valid.sum()),matched_k_list='|'.join(map(str,ks[valid])),estimate=value))
    target=OUT/'current_policy_results/secondary';target.mkdir(parents=True,exist_ok=True)
    pd.DataFrame(ks_rows).to_csv(target/'POLICY_IMAGE_K.csv.gz',index=False,encoding='utf-8-sig')
    phase=pd.DataFrame(phase_rows);phase.to_csv(target/'POLICY_IMAGE_PHASE.csv.gz',index=False,encoding='utf-8-sig')
    fields=['cohort','condition','layer','policy','phase','metric'];rows=[]
    for key,g in phase.groupby(fields,dropna=False):
        valid=g[g.estimate.notna()];by_building=valid.groupby('building').estimate.mean()
        rows.append(dict(zip(fields,key),attempted_images=g.pool_id.nunique(),valid_images=valid.pool_id.nunique(),valid_buildings=valid.building.nunique(),image_equal=valid.estimate.mean(),building_equal=by_building.mean(),uncertainty='descriptive_only_not_generated'))
    pd.DataFrame(rows).to_csv(target/'DESCRIPTIVE_SUMMARY.csv',index=False,encoding='utf-8-sig')
    receipt=dict(data_release='v2.1',pools=phase.pool_id.nunique(),per_k_rows=len(ks_rows),phase_rows=len(phase),cohorts=['original_old8','added_reference32'],common_support='natural/policy paired by exact pool and base path; each role retains its own eligible images',
        limitation='secondary descriptive scope, no bootstrap here; primary ordinary Manual all-four-role common32 has separate path/building inference',new_fusion=0)
    (target/'CHECKS.json').write_text(json.dumps(receipt,indent=2),encoding='utf8');print(json.dumps(receipt),flush=True)


if __name__=='__main__':main()
