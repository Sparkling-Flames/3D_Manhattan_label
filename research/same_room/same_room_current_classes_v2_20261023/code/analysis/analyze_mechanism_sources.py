"""View differences on the frozen B8L2 scale and range-bias conditions.

No rescoring, altered weights, or causal attribution. For positive IoU,
Q=100/(1+G+H+L). Split the *change* in G=hypot(F,D) symmetrically between
floor fidelity F and intrinsic direction D; multiply by the exact common
reciprocal factor so four reported contributions sum to the observed delta Q.
"""
from pathlib import Path
import argparse,json
import numpy as np
import pandas as pd
from analyze_exact_changes import read_pool,finite,analysis_subsets

NAMES=['floor_fidelity','intrinsic_direction','global_height','local_height']


def arr(rows,key):return np.array([r.get(key) if finite(r.get(key)) else np.nan for r in rows],float)


def decompose(rows,i,j):
    I=arr(rows,'iou_2d');Sb=arr(rows,'S_bottom_deg');D=arr(rows,'dir');Hm=arr(rows,'Hmean');Hc=arr(rows,'Hcenter')
    with np.errstate(divide='ignore',invalid='ignore'):
        F=np.where(I>0,1/I-1+Sb**2/32,np.nan)
        di=1.5*(D/np.hypot(D,8))**2;hh=(Hm/.8)**2;ll=(Hc/.25)**2
        G=np.hypot(F,di);total=G+hh+ll
        fchange=.5*(np.hypot(F[j],di[i])-G[i]+G[j]-np.hypot(F[i],di[j]))
        dchange=.5*(np.hypot(F[i],di[j])-G[i]+G[j]-np.hypot(F[j],di[i]))
        factor=-100/((1+total[i])*(1+total[j]))
        terms=np.column_stack([fchange,dchange,hh[j]-hh[i],ll[j]-ll[i]])*factor[:,None]
    q=arr(rows,'B8L2');expected=q[j]-q[i]
    error=np.nanmax(np.abs(terms.sum(axis=1)-expected)) if np.isfinite(terms).any() else np.nan
    return terms,error


def main(design,native,out):
    out.mkdir(parents=True,exist_ok=True)
    panels=pd.read_csv(design/'PANELS.csv');links=pd.read_csv(design/'PANEL_TEAM_LINKS.csv.gz')
    bypanel={k:g.sort_values('selected_mask').reset_index(drop=True) for k,g in links.groupby('panel_id')}
    rows=[];maxerr=0;ready=0
    for pair,pp in panels.groupby('pair_key',sort=False):
        pools=[read_pool(native,pp.iloc[0].pool_id_a),read_pool(native,pp.iloc[0].pool_id_b)]
        for p in pp.itertuples():
            g=bypanel[p.panel_id];keys=[g.team_key_a.tolist(),g.team_key_b.tolist()]
            if not all(all(k in pools[s] for k in keys[s]) for s in (0,1)):continue
            ready+=1;recs=[[pools[s][k] for k in keys[s]] for s in (0,1)]
            masks=g.selected_mask.to_numpy(int);h=g.hi_selected.to_numpy(int);ii,jj=np.triu_indices(len(g),1)
            rev=h[jj]<h[ii];i=np.where(rev,jj,ii);j=np.where(rev,ii,jj)
            m=np.array([(int(x)^int(y)).bit_count()//2 for x,y in zip(masks[i],masks[j])]);r=h[j]-h[i]
            terms=[];qs=[];bias=[];shift=[];turns=[];bottom=[];direction=[]
            for rr in recs:
                tt,err=decompose(rr,i,j);terms.append(tt)
                if np.isfinite(err):maxerr=max(maxerr,err)
                q=arr(rr,'B8L2');qs.append(q[j]-q[i]);tr=arr(rr,'fusion_turn_n');turns.append(tr[j]-tr[i])
                b=arr(rr,'extension')-arr(rr,'omission');bias.append(b[i]);shift.append(b[j]-b[i])
                sb=arr(rr,'S_bottom_deg');bottom.append(sb[j]-sb[i]);dr=arr(rr,'dir');direction.append(dr[j]-dr[i])
            qa,qb=qs;ta,tb=turns;finiteq=np.isfinite(qa)&np.isfinite(qb)
            qopp=finiteq&(qa*qb<0)&(np.abs(qa)>2)&(np.abs(qb)>2)
            finite_terms=np.isfinite(terms[0]).all(axis=1)&np.isfinite(terms[1]).all(axis=1)
            components_difference=terms[0]-terms[1]
            dominant=np.argmax(np.where(np.isfinite(components_difference),np.abs(components_difference),-1),axis=1)
            for mm,rr in sorted(set(zip(m,r))):
                sel=(m==mm)&(r==rr);good=sel&finite_terms
                row={'panel_id':p.panel_id,'m':int(mm),'r':int(rr),'kind':'same_composition' if rr==0 else ('pure_class_block' if rr==mm else 'mixed_class_block'),
                     'attempted':int(sel.sum()),'finite_decomposition':int(good.sum()),'q_opposite_n':int((good&qopp).sum())}
                if good.any():
                    for k,name in enumerate(NAMES):
                        row[name+'__contribution_a']=float(terms[0][good,k].mean());row[name+'__contribution_b']=float(terms[1][good,k].mean())
                        row[name+'__view_gap_abs']=float(np.abs(components_difference[good,k]).mean())
                        row[name+'__largest_view_difference']=float(np.mean(dominant[good]==k))
                        if np.any(good&qopp):row[name+'__largest_among_q_opposite']=float(np.mean(dominant[good&qopp]==k))
                    row['q_opposite_both_turn_stable']=float(np.mean(((ta==0)&(tb==0))[good&qopp])) if np.any(good&qopp) else np.nan
                # This is a descriptive reference-known mechanism condition.
                # It is not a deployable target-GT-free selection rule.
                stable=sel&finiteq&(ta==0)&(tb==0)
                same_shift=stable&(shift[0]*shift[1]>0)&(np.abs(shift[0])>.01)&(np.abs(shift[1])>.01)
                opposite_bias=same_shift&(bias[0]*bias[1]<0)&(np.abs(bias[0])>.02)&(np.abs(bias[1])>.02)
                row['both_turn_stable_n']=int(stable.sum());row['same_area_shift_n']=int(same_shift.sum());row['same_shift_opposite_initial_bias_n']=int(opposite_bias.sum())
                for label,cond in [('stable',stable),('same_shift',same_shift),('same_shift_opposite_bias',opposite_bias)]:
                    if not cond.any():continue
                    row[label+'__q_opposite_rate']=float(qopp[cond].mean())
                    row[label+'__q_effect_view_gap']=float(np.abs(qa[cond]-qb[cond]).mean())
                    row[label+'__bottom_opposite_rate']=float(np.mean((bottom[0][cond]*bottom[1][cond])<0))
                if opposite_bias.any():
                    expected_a=-np.sign(shift[0][opposite_bias]*bias[0][opposite_bias])
                    expected_b=-np.sign(shift[1][opposite_bias]*bias[1][opposite_bias])
                    row['bias_correcting_direction__q_sign_agreement']=float(np.mean(np.r_[np.sign(qa[opposite_bias])==expected_a,np.sign(qb[opposite_bias])==expected_b]))
                    row['bias_correcting_direction__bottom_sign_agreement']=float(np.mean(np.r_[-np.sign(bottom[0][opposite_bias])==expected_a,-np.sign(bottom[1][opposite_bias])==expected_b]))
                rows.append(row)
        print('mechanism pair done',pair,'panels',ready,flush=True)
    df=pd.DataFrame(rows);df.to_csv(out/'MECHANISM_STRATA.csv.gz',index=False)
    if not len(df):return
    d=df.merge(panels,on='panel_id');d['mid_n']=[max(3,k,min(N-k,N//2)) for k,N in zip(d.k_selected,d.known_common_n)]
    keys=['m','r','kind'];nums=[c for c in df.select_dtypes('number').columns if c not in ['m','r']]
    sums=[];allgroups=[];allbuildings=[]
    for subset,z in analysis_subsets(d):
        if not len(z):continue
        pair=z.groupby(keys+['building','pair_key','groups'])[nums].mean().reset_index()
        gr=pair.assign(group_id=pair.groups.str.split('|')).explode('group_id').groupby(keys+['building','group_id'])[nums].mean().reset_index();gr['subset']=subset;allgroups.append(gr)
        bb=gr.groupby(keys+['building'])[nums].mean().reset_index();bb['subset']=subset;allbuildings.append(bb)
        for key,b in bb.groupby(keys):
            s=z[(z.m==key[0])&(z.r==key[1])&(z.kind==key[2])]
            row=dict(zip(keys,key));row.update(subset=subset,pairs=s.pair_key.nunique(),images=len(set(s.image_a)|set(s.image_b)),buildings=s.building.nunique(),groups=len(set('|'.join(s.groups).split('|'))),
                total_contrasts=int(s.attempted.sum()),q_opposite_contrasts=int(s.q_opposite_n.sum()),bias_opportunities=int(s.same_shift_opposite_initial_bias_n.sum()))
            row.update({c:b[c].mean() for c in nums});sums.append(row)
    pd.DataFrame(sums).to_csv(out/'MECHANISM_SUMMARY.csv',index=False);pd.concat(allgroups).to_csv(out/'MECHANISM_GROUPS.csv',index=False);pd.concat(allbuildings).to_csv(out/'MECHANISM_BUILDINGS.csv',index=False)
    (out/'MECHANISM_RECEIPT.json').write_text(json.dumps({'ready_panels':ready,'total_panels':len(panels),'maximum_reconstruction_error_B8L2_points':maxerr,
        'allocation':'exact symmetric two-factor split of change in frozen L2 geometric loss, followed by exact reciprocal factor; four contributions sum to deltaQ',
        'not_causal':True,'no_score_changes':True,'range_bias_condition':'both turn counts unchanged; normalized area shifts same sign and >1%GT; initial signed area biases opposite and >2%GT',
        'condition_uses_reference':'descriptive mechanism only, not target-GT-free policy'},ensure_ascii=False,indent=2))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--design',type=Path,required=True);ap.add_argument('--native',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();main(a.design,a.native,a.out)
