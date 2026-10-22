from pathlib import Path
import argparse,json
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager


def main(work,out,font):
    out.mkdir(parents=True,exist_ok=True)
    font_manager.fontManager.addfont(str(font))
    plt.rcParams.update({'font.family':font_manager.FontProperties(fname=str(font)).get_name(),
        'font.size':11,'axes.spines.top':False,'axes.spines.right':False,'savefig.dpi':170})
    s=pd.read_csv(work/'exact_changes/SUMMARY_BUILDING_EQUAL.csv')
    z=s.query("subset=='ordinary_mid' and kind in ['pure_class_block','same_composition']").copy()
    cols=['kind','m','pairs','images','groups','buildings','panels','attempted_contrasts','finite_q_contrasts','four_complete_rate']
    for metric in ['B8L2','D10','fusion_turn_n','nodes','S_bottom_deg','dir','Hmean','Hcenter']:
        cols += [metric+'__'+x for x in ['both_small','both_nonzero_same','opposite','one_small','view_gap_mean','mean_abs_a','mean_abs_b']]
    cols += ['B8L2__copy_source_mae','B8L2__symmetric_zero_effect_mae','B8L2__symmetric_source_trigger_same','B8L2__both_nonsmall_same']
    z[cols].to_csv(out/'EXACT_REPLACEMENT_MAIN.csv',index=False)
    rows=pd.concat([z.query("kind=='same_composition' and m<=3"),z.query("kind=='pure_class_block' and m<=3")]).reset_index(drop=True)
    fig,ax=plt.subplots(figsize=(11.8,5.5));left=np.zeros(len(rows))
    parts=[('both_small','两边幅度均≤2分','#d5dde5'),('one_small','仅一边幅度>2分','#efc46a'),('both_nonzero_same','两边同向且幅度均>2分','#429c89'),('opposite','两边反向且幅度均>2分','#d16b79')]
    for key,label,color in parts:
        values=100*rows['B8L2__'+key].to_numpy();ax.barh(np.arange(len(rows)),values,left=left,color=color,label=label,height=.62)
        for i,(v,l) in enumerate(zip(values,left)):
            if v>=5:ax.text(l+v/2,i,f'{v:.1f}%',ha='center',va='center',fontsize=10)
        left+=values
    labels=[('同配比换成员' if r.kind=='same_composition' else '纯类别块替换')+f'  m={r.m}' for r in rows.itertuples()]
    ax.set_yticks(range(len(rows)),labels);ax.invert_yaxis();ax.set_xlim(0,100);ax.set_xlabel('图对→原声明组→建筑等权比例（%）')
    ax.set_title('同一实际调整跨视角重复：小变化、单端变化与真正同向分开',loc='left',pad=20,fontweight='bold')
    ax.legend(loc='upper center',bbox_to_anchor=(.5,-.14),ncol=2,frameon=False)
    fig.text(.02,.015,'普通 Manual；主预算约 N/2；比例以四端 Q 均可用为条件，失败/不完整另报。',fontsize=9,color='#4e5d6c')
    fig.tight_layout(rect=[0,.08,1,1]);fig.savefig(out/'EXACT_REPLACEMENT_STATES.png');plt.close(fig)

    t=pd.read_csv(work/'time_transfer/BLOCK_TIME_SUMMARY.csv')
    t=t.query("subset=='ordinary_mid' and time_source_kind=='user_processed_reported_not_raw_log_replayed' and m==1").copy()
    t=t[t.kind.isin(['pure_class_block','same_composition'])]
    t.to_csv(out/'TIME_Q_SAME_SUPPORT.csv',index=False)
    fig,ax=plt.subplots(figsize=(9.8,4.8));xx=np.arange(len(t));w=.3
    time=100*t.time_same_support_same_sign_unthresholded.to_numpy();q=100*t.q_same_sign_unthresholded.to_numpy()
    ax.bar(xx-w/2,time,w,color='#378d89',label='记录劳动增减方向');ax.bar(xx+w/2,q,w,color='#9e748f',label='融合 B8L2 增减方向')
    for xs,vals in [(xx-w/2,time),(xx+w/2,q)]:
        for x,v in zip(xs,vals):ax.text(x,v+2,f'{v:.1f}%',ha='center')
    ax.set_xticks(xx,['纯类别一人替换' if x=='pure_class_block' else '同配比一人替换' for x in t.kind]);ax.set_ylim(0,100);ax.set_ylabel('跨视角同号比例（%）')
    ax.set_title('同一组可计时、可评分的替换：时间方向比质量方向更重复',loc='left',fontweight='bold',pad=16);ax.legend(frameon=False,loc='lower right')
    fig.text(.04,.02,'按完全相同的事件支持比较；未设效果阈值。仅同一种处理后作答耗时，非交付等待时间。',fontsize=9,color='#4e5d6c')
    fig.tight_layout(rect=[0,.07,1,1]);fig.savefig(out/'TIME_Q_REPEATABILITY.png');plt.close(fig)

    p=pd.read_csv(work/'design/PANELS.csv')
    st=pd.read_csv(work/'exact_changes/CONTRAST_STRATA.csv.gz')
    st=st.merge(p,on='panel_id');st['mid_n']=[max(3,k,min(N-k,N//2)) for k,N in zip(st.k_selected,st.known_common_n)]
    st=st[st.ordinary_comparable&(st.n==st.mid_n)&(st.replicate==0)]
    sr=[]
    for group,g in st.assign(group_id=st.groups.str.split('|')).explode('group_id').groupby('group_id'):
        for (kind,m),gg in g[g.kind.isin(['pure_class_block','same_composition'])].groupby(['kind','m']):
            rr={'group_id':group,'building':gg.building.iloc[0],'kind':kind,'m':m,'pairs':gg.pair_key.nunique(),'images':len(set(gg.image_a)|set(gg.image_b)),
                'panels':gg.panel_id.nunique(),'finite_q_contrasts':int(gg['B8L2__n'].sum()),'attempted_contrasts':int(gg.contrasts.sum()),
                'n_min':int(gg.n.min()),'n_max':int(gg.n.max()),'image_members':'|'.join(sorted(set(gg.image_a)|set(gg.image_b)))}
            vv=['B8L2__both_small','B8L2__both_nonzero_same','B8L2__opposite','B8L2__one_small','B8L2__view_gap_mean','B8L2__both_positive','B8L2__both_negative','D10__view_gap_mean','four_complete_rate','fusion_turn_n__both_small']
            pp=gg.groupby('pair_key')[vv].mean();rr.update(pp.mean().to_dict());sr.append(rr)
    pd.DataFrame(sr).to_csv(out/'GROUP_REPLACEMENT_READABLE.csv',index=False)


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--work',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--font',type=Path,required=True)
    a=ap.parse_args();main(a.work,a.out,a.font)
