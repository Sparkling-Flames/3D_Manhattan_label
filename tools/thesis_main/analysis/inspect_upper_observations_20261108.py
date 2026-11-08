"""Inspect archived upper/lower observations; no reference-quality ranking."""
from pathlib import Path
import csv,gzip,json,copy
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image
from tools.thesis_main.analysis.consensus_delivery_20261008 import fuse
from tools.thesis_main.analysis.fusion_common_panel_20261024 import medoid
from tools.thesis_main.analysis.research_round_20260929 import reconstruct
from tools.thesis_main.analysis.lee_tile_stage1_20261002 import tile_consensus

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'docs/thesis_main/论文写作工作资料/顶面信息与基线比较_20261108'
BASE=ROOT/'research/fusion/structural_support_comparison_20261108'

def main():
    OUT.mkdir(exist_ok=True)
    with gzip.open(ROOT/'research/workers/personnel_population_curves_v2_20261023/inputs/INPUT_SNAPSHOT.json.gz','rt',encoding='utf-8') as f:
        pools={p['pool_id']:p for p in json.load(f)['images']}
    teams={r['team_key']:r for r in csv.DictReader((BASE/'TEAM_SUPPORT.csv').open(encoding='utf-8-sig')) if r['layer']=='ordinary_manual'}
    rows=[]
    for n in csv.DictReader((BASE/'NODE_SUPPORT.csv').open(encoding='utf-8-sig')):
        if n['team_key'] not in teams or n['in_medoid']!='True' or n['support_kind']!='strict_majority':continue
        t=teams[n['team_key']];lookup={r['object_id']:r for r in pools[n['pool_id']]['records']}
        pairs=json.loads(n['source_pairs']);mine=[(oid,i) for oid,i in pairs if oid==t['medoid_object']]
        other=[np.array(lookup[oid]['points'])[2*i:2*i+2] for oid,i in pairs if oid!=t['medoid_object']]
        assert len(mine)==1 and len(other)==int(n['support'])-1
        oid,i=mine[0];pair=np.array(lookup[oid]['points'])[2*i:2*i+2];a=np.array(other);v=np.median(a[:,:,1],axis=0)
        du=(pair[0,0]-a[:,0,0]+512)%1024-512
        rows.append(dict(team_key=n['team_key'],pool_id=n['pool_id'],image=n['image'],n=int(t['n']),feature_id=n['feature_id'],
                         support=int(n['support']),worker=t['medoid_worker'],object_id=oid,pair_index=i,
                         top_deg=float(abs(pair[0,1]-v[0])*180/512),bottom_deg=float(abs(pair[1,1]-v[1])*180/512),
                         horizontal_deg=float(abs(np.median(du))*360/1024),medoid_pair=pair.tolist(),others=a.tolist()))
    assert len(teams)==70 and len(rows)==356
    rows.sort(key=lambda r:r['top_deg'],reverse=True)
    (OUT/'逐角点观察.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
    summary=[]
    for threshold in [1,2,3,5]:
        s=[r for r in rows if r['top_deg']>=threshold and r['bottom_deg']<=1 and r['horizontal_deg']<=1]
        summary.append(dict(top_threshold_deg=threshold,nodes=len(s),teams=len({r['team_key'] for r in s}),images=len({r['image'] for r in s})))
    chosen=[r for r in rows if r['top_deg']>=3 and r['bottom_deg']<=1 and r['horizontal_deg']<=1]
    assert len(chosen)==2
    cases=[];fig,axes=plt.subplots(2,3,figsize=(12,7),layout='constrained')
    for line,r in enumerate(chosen):
        pool=pools[r['pool_id']];t=teams[r['team_key']]
        records=[x for x in pool['records'] if x['worker_id'] in t['member_workers'].split('|')]
        old,_,exclusions,distance=medoid(records);assert old['object_id']==r['object_id']
        f=fuse(records,gap=7.5)['automatic']['candidate'];index=f['feature_ids'].index(r['feature_id'])
        cp=np.array(f['points'])[2*index:2*index+2];mp=np.array(r['medoid_pair']);others=np.array(r['others'])
        reference=np.array(pool['reference']['points_1024x512']);ri=np.argmin(abs((reference[::2,0]-mp[0,0]+512)%1024-512))
        rp=reference[2*ri:2*ri+2]
        # Controlled perturbation checks the distance's information use, not natural error prevalence.
        changed=copy.deepcopy(records)
        for x in changed:
            if x['object_id']==r['object_id']:
                for p in x['points'][::2]:p[1]+=2
        new,_,exc2,dist2=medoid(changed)
        assert new['object_id']==old['object_id'] and exclusions==exc2 and distance==dist2
        def regions(items):
            return tile_consensus([dict(id=x['object_id'],worker=x['worker_id'],footprint=reconstruct(x)['floor']) for x in items])['regions']['mv50']
        assert regions(records).symmetric_difference(regions(changed)).area<1e-12
        photo=next(ROOT/'data/mp3d_layout'/split/'img'/f"{pool['meta']['image_id']}.png" for split in ['test','valid','train'] if (ROOT/'data/mp3d_layout'/split/'img'/f"{pool['meta']['image_id']}.png").exists())
        img=Image.open(photo)
        for k in [0,1]:
            a=axes[line,k];a.imshow(img,extent=(0,1024,512,0));a.scatter(*others[:,k,:].T,c='#777777',s=30,label='Other supporters')
            a.scatter(*mp[k],c='#b74736',marker='x',s=80,label='Medoid');a.scatter(*cp[k],c='#16799b',marker='D',s=36,label='Consensus')
            a.scatter(*rp[k],c='black',marker='+',s=80,label='Adopted reference')
            points=np.vstack([others[:,k,:],mp[k],cp[k],rp[k]])
            a.set(xlim=(points[:,0].min()-15,points[:,0].max()+15),ylim=(points[:,1].max()+12,points[:,1].min()-12),xlabel='Panorama u (px)',ylabel='v (px)')
            a.set_title(r['image']+f" | {r['n']} people | "+('Upper' if k==0 else 'Lower'))
        a=axes[line,2]
        for k,label in [(0,'Upper'),(1,'Lower')]:
            center=np.median(others[:,k,1]);a.scatter((others[:,k,1]-center)*180/512,np.full(len(others),k),c='#777777',s=28)
            a.scatter((mp[k,1]-center)*180/512,k,c='#b74736',marker='x',s=80)
            a.scatter((cp[k,1]-center)*180/512,k,c='#16799b',marker='D',s=36)
        a.axvline(0,c='gray',ls='--');a.set(yticks=[0,1],yticklabels=['Upper','Lower'],ylim=(-.5,1.5),xlabel='Vertical angle from other-supporter median (deg)')
        a.set_title('Matched observations, not Q scores')
        cases.append(dict(**r,consensus_pair=cp.tolist(),reference_pair=rp.tolist(),reference_version=pool['meta']['reference_version'],
                          member_workers=t['member_workers'],control=dict(top_shift_px=2,medoid_choice_unchanged=True,medoid_distance_unchanged=True,bev_unchanged=True)))
    handles,labels=axes[0,0].get_legend_handles_labels();fig.legend(handles,labels,loc='outside lower center',ncol=4)
    fig.savefig(OUT/'上下端点观察对照.png',dpi=170);plt.close(fig)
    (OUT/'案例与统计.json').write_text(json.dumps(dict(teams=70,matched_majority_occurrences=356,threshold_sensitivity=summary,cases=cases),ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False));print('two case perturbation checks passed')

if __name__=='__main__':main()
