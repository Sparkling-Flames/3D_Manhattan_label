"""Four saved endpoints: hold X/Z fixed while a common background changes.

Local feature IDs are never equated across endpoints. Correspondence diagnostics
use exact original object_id/source_pair_index observations. Added background
members and a changed MV50 count threshold are reported jointly.
"""
from __future__ import annotations
import argparse,collections,gzip,itertools,json
from pathlib import Path
import numpy as np
import pandas as pd
from PIL import Image
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from geometry_draw import erp,bev,number,save_figure
from render_ac_cases import extent,setup_bev,get_group_points,present_points

def read(p):
    with gzip.open(p,'rt') as f:return json.load(f)
def members(e,field):return set(e.get(field,'').split('|'))-{''}
def obsmap(row):
    observations={};groups={}
    for g in (row.get('full_state') or {}).get('identity_groups',[]):
        groups[g['feature_id']]=g
        for m in g['members']:
            key=(str(m['id']),int(m['source_pair_index']));assert key not in observations
            observations[key]=g['feature_id']
    return observations,groups
def finite(x):return isinstance(x,(int,float)) and np.isfinite(x)

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--first','--smaller',dest='first',required=True);ap.add_argument('--second','--larger',dest='second',required=True)
    ap.add_argument('--first-label',default='背景条件1');ap.add_argument('--second-label',default='背景条件2')
    ap.add_argument('--original',required=True);ap.add_argument('--out',required=True);a=ap.parse_args()
    first,second=read(a.first),read(a.second);es,el=first['event'],second['event'];out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    for field in ['pool_id','method','reference_id','reference_version']:assert es[field]==el[field],field
    for field in ['X_workers','Z_workers']:assert members(es,field)==members(el,field),field
    ds,dl=members(es,'D_workers'),members(el,'D_workers');assert ds!=dl,'Background identities must differ.'
    common_d=ds&dl;removed=ds-dl;added=dl-ds;
    change_kind='same_n_different_background_members' if len(ds)==len(dl) else 'nested_background_expansion' if ds<dl else 'background_count_and_members_change'
    x=members(es,'X_workers');z=members(es,'Z_workers');assert len(x)==len(z)
    assert int(es['n_A'])==int(es['n_C']) and int(el['n_A'])==int(el['n_C'])
    groups_rows=[];obs_rows=[];coassign=[];endpoints=[]
    for arm in ['A','C']:
        sr,lr=first['arms'][arm],second['arms'][arm];sm,sg=obsmap(sr);lm,lg=obsmap(lr);common=set(sm)&set(lm)
        all_first=set(sm);missing=all_first-set(lm)
        both_states=sr.get('full_state') is not None and lr.get('full_state') is not None
        if both_states:
            shared_workers=set(sr['member_workers'])&set(lr['member_workers'])
            expected={(str(r['id']),i) for r in first['pool']['records'] if r['worker_id'] in shared_workers for i in range(len(r['points'])//2)}
            assert common==expected
        links=collections.Counter((sm[o],lm[o]) for o in common)
        for (g1,g2),count in sorted(links.items()):
            p,q=sg[g1],lg[g2]
            groups_rows.append({'arm':arm,'first_event_id':es['event_id'],'second_event_id':el['event_id'],
              'first_group':g1,'second_group':g2,'shared_original_observations':count,
              'first_support':p['support'],'second_support':q['support'],'first_threshold':sr['minimum_support'],'second_threshold':lr['minimum_support'],
              'first_selected':p['selected'],'second_selected':q['selected'],
              'first_center_json':json.dumps(p['center']),'second_center_json':json.dumps(q['center']),
              'second_added_background_support':sum(m['worker'] in added for m in q['members']),
              'first_removed_background_support':sum(m['worker'] in removed for m in p['members'])})
        for obj,index in sorted(common):
            obs_rows.append({'arm':arm,'object_id':obj,'source_pair_index':index,'first_group':sm[(obj,index)],'second_group':lm[(obj,index)],
                             'first_selected':sg[sm[(obj,index)]]['selected'],'second_selected':lg[lm[(obj,index)]]['selected']})
        n=changed=0
        for u,v in itertools.combinations(sorted(common),2):n+=1;changed+=(sm[u]==sm[v])!=(lm[u]==lm[v])
        coassign.append({'arm':arm,'shared_original_observations':len(common),'coassignment_pairs':n,'changed_pairs':changed,
                         'changed_fraction':changed/n if n else None,'both_full_states_available':both_states})
    fields=['B8L2','D10','nodes','fusion_turn_n','fusion_short_turn_edges','ref_node_recall_9','ref_edge_recall_9',
            'boundary_loss','direction_loss','height_loss','geometry_area_h2','centroid_x_h','centroid_z_h','height_mean_h','minimum_support','score_status']
    components=[]
    for field in fields:
        vals={n+'_'+arm:c['arms'][arm].get(field) for n,c in [('first',first),('second',second)] for arm in ['A','C']}
        dsig=vals['first_C']-vals['first_A'] if finite(vals['first_A']) and finite(vals['first_C']) else None
        dlig=vals['second_C']-vals['second_A'] if finite(vals['second_A']) and finite(vals['second_C']) else None
        components.append({'metric':field,**vals,'C_minus_A_first':dsig,'C_minus_A_second':dlig,
                           'second_contrast_minus_first_contrast':dlig-dsig if finite(dsig) and finite(dlig) else None})
    for filename,rows in [('GROUP_OBSERVATION_LINKS.csv',groups_rows),('SHARED_OBSERVATION_ASSIGNMENTS.csv',obs_rows),
                          ('COASSIGNMENT.csv',coassign),('FOUR_ENDPOINT_COMPONENTS.csv',components)]:
        pd.DataFrame(rows).to_csv(out/filename,index=False,encoding='utf-8-sig')
    ref=first['reference']['points_1024x512'];canvas=np.array(Image.open(a.original).convert('RGB').resize((1024,512),Image.Resampling.LANCZOS))
    ordered=[('first','A',first),('first','C',first),('second','A',second),('second','C',second)]
    limits=extent([ref]+[present_points(c['arms'][arm]) for _,arm,c in ordered]);palette={'D':'#87929c','removed':'#9566af','added':'#53a15d','X':'#2471a3','Z':'#d95f28'}
    fig,axes=plt.subplots(3,4,figsize=(20,12.5),gridspec_kw={'height_ratios':[1,1.1,1]})
    for col,(stage,arm,case) in enumerate(ordered):
        row=case['arms'][arm];p=present_points(row);color=palette['X' if arm=='A' else 'Z'];ax=axes[0,col]
        ax.imshow(canvas,extent=[0,1024,512,0]);ax.set_xlim(0,1024);ax.set_ylim(512,0);erp(ax,ref,'#111',1.3,.95,'--');erp(ax,p,color,2.,1.)
        ax.set_title(f"{a.first_label if stage=='first' else a.second_label} {arm}：n={row['k']}，m={len(x)}，门槛={row['minimum_support']}\nB8L2={number(row.get('B8L2'))}；{row['score_status']}",fontsize=10)
        ax.set_xlabel('ERP水平像素');ax.set_ylabel('ERP竖直像素');ax=axes[1,col]
        bev(ax,ref,'#111',1.4,.95,'--',True);bev(ax,p,color,2.0,1.,dots=True);setup_bev(ax,limits)
        items=(row.get('full_state') or {}).get('identity_groups',[]);items=sorted(items,key=lambda g:(get_group_points(g) or [[0,0],[np.inf,0]])[1][0]);ax=axes[2,col]
        for j,g in enumerate(items):
            counts={'D':0,'removed':0,'added':0,'X' if arm=='A' else 'Z':0}
            for member in g['members']:
                who=member['worker'];category='D' if who in common_d else 'removed' if who in removed else 'added' if who in added else 'X' if arm=='A' else 'Z';counts[category]+=1
            bottom=0
            for category,count in counts.items():ax.bar(j,count,bottom=bottom,color=palette[category],alpha=.95 if g['selected'] else .25);bottom+=count
            assert bottom==g['support'];ax.text(j,bottom+.2,str(bottom),ha='center',fontsize=7)
        ax.set_xticks(range(len(items)),[g['feature_id'].replace('node_','g') for g in items],rotation=40,fontsize=7)
        ax.axhline(row['minimum_support'],color='#b22f39',ls='--',lw=1.2);ax.set_ylim(0,max([row['minimum_support']]+[g['support'] for g in items])+2)
        ax.set_title('全部对应组（浅色未选）');ax.set_ylabel('独立人员支持票');ax.grid(axis='y',alpha=.15)
    explanation='同一n和替换比例，仅背景人员身份改变' if change_kind=='same_n_different_background_members' else '背景人数与门槛同时改变，逐组检查实际支持而不只看块人数'
    fig.suptitle(es['image']+f"：固定X/Z各{len(x)}人，背景{len(ds)}→{len(dl)}人\n"+explanation+'；移出D：'+('、'.join(sorted(removed)) or '无')+'；加入D：'+('、'.join(sorted(added)) or '无'),fontsize=13,y=.995)
    fig.legend(handles=[Line2D([0],[0],color=palette[c],lw=7,label=l) for c,l in [('D','两条件共有D'),('removed','仅条件1的D'),('added','仅条件2的D'),('X','固定X'),('Z','固定Z')]],loc='lower center',ncol=5,frameon=False)
    fig.tight_layout(rect=[0,.05,1,.94],h_pad=2.6)
    for suffix in ['png','pdf']:save_figure(fig,out/('FOUR_ENDPOINTS_FIXED_XZ.'+suffix),dpi=160)
    plt.close(fig)
    receipt={'pool_id':es['pool_id'],'first_event':es['event_id'],'second_event':el['event_id'],
       'X_workers':sorted(x),'Z_workers':sorted(z),'common_D_workers':sorted(common_d),'first_only_D_workers':sorted(removed),'second_only_D_workers':sorted(added),'background_change_kind':change_kind,
       'first_n':int(es['n_A']),'second_n':int(el['n_A']),'m':len(x),
       'first_block_can_reach_MV50':len(x)>=first['arms']['A']['minimum_support'],
       'second_block_can_reach_MV50':len(x)>=second['arms']['A']['minimum_support'],
       'actual_node_supports_saved':True,'no_local_group_id_equation_across_teams':True,
       'new_teams':0,'new_fusions':0,'new_scoring':0,'interpretation':explanation+'。Mechanism requires exact group observations and output state, not block size alone.'}
    (out/'FIXED_BLOCK_TRANSITION_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(receipt),flush=True)

if __name__=='__main__':main()
