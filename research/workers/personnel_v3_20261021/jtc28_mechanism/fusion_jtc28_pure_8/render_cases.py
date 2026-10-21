#!/usr/bin/env python3
"""Two compact scientific figures from stored endpoints and the Release photo."""
import hashlib,json
from pathlib import Path
import numpy as np,pandas as pd
from PIL import Image
import export_cases as e
from analyze_mechanism import load_viewer
HERE=e.HERE
PHOTO=e.V3/'evidence/originals/jtcxE69GiFV_dce110162b244b2ab76a0804fc830a9e.png'

def main():
    v=load_viewer();v._configure_font(HERE/'assets/NotoSansCJKsc-CaseSubset.ttf')
    v.plt.rcParams['font.family']=[v.plt.rcParams['font.family'][0],'DejaVu Sans']
    photo=np.asarray(Image.open(PHOTO).convert('RGB'))
    cases=sorted([e.gs.read(p) for p in (HERE/'cases').glob('*.json.gz')],key=lambda c:c['n']);out=HERE/'figures';out.mkdir(exist_ok=True)
    cols={'A':'#f58c44','B':'#31a6dd','C':'#3bbe87'}
    fig=v.plt.figure(figsize=(20,16.5));grid=fig.add_gridspec(4,3,height_ratios=[1,1.22,1,1.22],hspace=.42,wspace=.18)
    for ci,c in enumerate(cases):
        ref=np.asarray(c['reference']['points_1024x512']);refg=v.viewer_geometry(ref)
        for j,t in enumerate(c['teams']):
            ax=fig.add_subplot(grid[ci*2,j]);v._erp_background(ax,photo)
            v._erp_edges(ax,ref,'#ffe476',1.5,reference=True,markers=False)
            if t['geometry']['points'] is not None:v._erp_edges(ax,t['geometry']['points'],cols[t['label']],1.65,markers=True)
            else:
                for g in t['full_state']['identity_groups']:
                    if g['selected']:
                        p=np.asarray(g['center']);ax.plot(p[:,0],p[:,1],color=cols[t['label']],lw=1.6);ax.scatter(p[:,0],p[:,1],color=cols[t['label']],s=8)
                ax.text(.5,.03,'仅画已入选的节点；原生结果无可用连接',transform=ax.transAxes,ha='center',fontsize=10,color='white',bbox=dict(facecolor='#942f36',alpha=.88,edgecolor='none'))
            for ri in [1,2,4,5,6]:
                x,y=ref[2*ri+1];ax.text(x,y+15,f'r{ri}',color='#ffe476',fontsize=9,ha='center',bbox=dict(facecolor='#222a32',alpha=.65,edgecolor='none',pad=.3))
            q='失败：no_connection' if t['B8L2'] is None else f'B8L2 {t["B8L2"]:.2f} / D10 {t["D10"]:.2f}'
            name={'A':'原类别块 X','B':'同类换人 Y','C':'改类换人 Z'}[t['label']]
            counts=' / '.join(f'{cl}={num}' for cl,num in t['counts'].items() if num)
            ax.set_title(f'{t["label"]} · {name}  |  n={t["k"]}, m=8\n{q}  ·  {counts}',fontsize=12,loc='left',pad=10)
            bx=fig.add_subplot(grid[ci*2+1,j]);v._bev_ring(bx,refg['floor'],'#333a45',1.8,reference=True)
            for ri in [1,2,4,5,6]:
                x,z=refg['floor'][ri];bx.annotate(f'r{ri}',(x,z),xytext=(3,5),textcoords='offset points',fontsize=9,color='#383f49')
            if t['geometry']['points'] is not None:
                floor=np.asarray(t['geometry']['footprint']);v._bev_ring(bx,floor,cols[t['label']],2)
                bx.scatter(floor[:,0],floor[:,1],color=cols[t['label']],s=20,zorder=6)
                extra=f'节点 {t["nodes"]}；门槛 {t["minimum_support"]}  |  IoU {t["iou_2d"]:.4f}；方向误差 {t["dir"]:.2f}°'
                if ci==1 and t['label']=='C':
                    bx.annotate('r5未入选\nr6→r4斜连',(-1.00,1.60),xytext=(-.12,1.10),fontsize=10,color='#ac3640',arrowprops=dict(arrowstyle='->',color='#ac3640'),bbox=dict(facecolor='white',alpha=.9,edgecolor='#e4d2d4'))
            else:
                pp=np.array([g['center'][1] for g in t['full_state']['identity_groups'] if g['selected']]);rr=v._ray(pp);ff=(-rr/rr[:,1,None])[:,[0,2]]
                bx.scatter(ff[:,0],ff[:,1],color=cols[t['label']],s=45,zorder=6)
                bx.text(.04,.09,'6个节点达到5票\n10份原答中没有完整投影环\n因此没有底面与质量分数',transform=bx.transAxes,fontsize=11,color='#a23540',bbox=dict(facecolor='white',alpha=.92,edgecolor='#e5c5c8'))
                extra='原生连接失败；散点仅表示节点位置，不连接成新轮廓'
            v._style_bev(bx,[-1.65,1.65,-1.90,2.12]);bx.set_title(extra,fontsize=10,loc='left',pad=7)
        if ci==0: fig.text(.03,.967,'正例：共同背景 W125、W134；常规类 M3 的8席转为转折表达类 M4',fontsize=13,weight='bold')
        else: fig.text(.03,.502,'反例：共同背景增为另一组7人；同一 Z 八人块仍补结构，但缺一个返角形成斜墙',fontsize=13,weight='bold')
    fig.suptitle('jtc-28 · 真正八席类别转移：结构补充有用，局部门槛与对应决定能否完整传递',fontsize=19,x=.03,ha='left',y=.995)
    fig.text(.03,.015,'黄色ERP线、黑色BEV虚线为冻结参考；彩色为原生融合。类别为 V3_BEHAVIOR 楼外几何四类（E+R+G，无QT）。两行的 n、背景与原块不同，不能当作受控人数曲线。\n这些几何沿用未人工确认源环的冻结条件评分资格；失败队保留为失败，未填0分、未按x排序制造连接。案例为事后机制选择，不估计成功率。',fontsize=10,color='#475565')
    fig.subplots_adjust(left=.035,right=.985,top=.928,bottom=.065)
    fig.savefig(out/'PURE_EIGHT_SEAT_ERP_BEV.png',dpi=150,facecolor='white');v.plt.close(fig)
    fg=pd.read_csv(HERE/'FOCUS_GROUPS.csv');fig,axes=v.plt.subplots(2,2,figsize=(18,12));clcolors={'M2':'#8d6baf','M3':'#2276a0','M4':'#3c9265'}
    for ci,c in enumerate(cases):
        ax=axes[0,ci];df=fg[fg.case_id==c['case_id']]
        roles=['left_outer_r4','left_return_r5'] if ci==0 else ['left_outer_r4','left_return_r5_primary','left_return_r5_secondary']
        z=pd.DataFrame([df[(df.arm==a)&(df.role==r)].iloc[0] for r in roles for a in 'ABC'])
        x=np.arange(len(z));bt=np.zeros(len(z))
        for cl,col in clcolors.items():ax.bar(x,z[cl+'_votes'],bottom=bt,color=col,width=.7,label=cl);bt+=z[cl+'_votes'].to_numpy()
        ax.axhline(c['teams'][0]['minimum_support'],ls='--',color='#bc4147',lw=1.5,label='实际门槛')
        for j,r in enumerate(z.itertuples()):ax.text(j,r.support+.2,str(r.support)+(' ✓' if r.selected else ''),ha='center',fontsize=11)
        ax.set_xticks(x,[a for r in roles for a in 'ABC']);ax.set_ylim(0,11);ax.grid(axis='y',alpha=.17);ax.set_axisbelow(True)
        for pos,title in zip([1,4,7],['左外角 r4','左返角 r5' if ci==0 else '返角 r5：主组','返角 r5：另一组'][:len(roles)]):
            ax.text(pos,-1.25,title,ha='center',fontsize=10)
        ax.set_title(f'{"正例" if ci==0 else "反例"} n={c["n"]}：同一可见左侧短转折机会',loc='left',fontsize=14);ax.set_ylabel('实际人员票数')
    c=cases[0];t=c['teams'][1];selected=[g for g in t['full_state']['identity_groups'] if g['selected']]
    selected.sort(key=lambda g:g['center'][0][0]);assign=t['full_state']['assignments'];z=np.array([[g['feature_id'] in a['feature_ids'] for g in selected] for a in assign],dtype=float)
    ax=axes[1,0];ax.imshow(z,cmap='Blues',vmin=0,vmax=1,aspect='auto');ax.set_yticks(range(len(assign)),[a['worker'] for a in assign]);ax.set_xticks(range(len(selected)),[f'x≈{g["center"][0][0]:.0f}\n{g["support"]}票' for g in selected]);
    for i in range(z.shape[0]):
        for j in range(z.shape[1]):ax.text(j,i,'●' if z[i,j] else '—',ha='center',va='center',fontsize=11,color='white' if z[i,j] else '#627287')
    ax.set_title('n10 同构成 B：x≈873 与 x≈889 两组各5票，却无一人同时提供',fontsize=12,loc='left',pad=12)
    ax.set_xlabel('每列为一个入选节点；没有一行覆盖全部6列，原生环选择因此失败',fontsize=10,labelpad=10)
    ax=axes[1,1];ax.axis('off'); incoming=c['event']['Z_workers'].split('|') if 'Z_workers' in c['event'] else ['W102','W104','W109','W115','W122','W123','W126','W130']
    byworker={m['worker_id']:m for m in c['members']};ca=c['teams'][2];cb=cases[1]['teams'][2]
    def group_at(t,w,lo=80,hi=95):
        for g in t['full_state']['identity_groups']:
            if lo<g['center'][0][0]<hi and w in {m['worker'] for m in g['members']}:
                return f'{g["support"]}票组'+('（保留）' if g['selected'] else '（未保留）')
        return '未提供该角'
    rows=[[w,len(byworker[w]['points'])//2,group_at(ca,w),group_at(cb,w)] for w in sorted(incoming)]
    tbl=ax.table(cellText=rows,colLabels=['同一Z块人员','原答点对数','n10的左返角归组','n15的左返角归组'],loc='center',cellLoc='center',colWidths=[.17,.19,.32,.32]);tbl.auto_set_font_size(False);tbl.set_fontsize(11);tbl.scale(1,1.85)
    for (r,col),cell in tbl.get_celld().items():
        cell.set_edgecolor('#d6dee5');cell.set_facecolor('#e8f2ed' if r==0 else ('#fff3d9' if r==5 else '#f9fbfd'))
    ax.set_title('M4是历史倾向；W104、W115在本图仍只画4对点',fontsize=12,loc='left',pad=12)
    ax.text(.02,.025,'W122原答未变：n10进入5票主组；n15与W117构成2票组。\n背景也有W103、W117、W129的返角观察，但分成6与2，不能直接相加改写冻结对应。',transform=ax.transAxes,fontsize=10,color='#475565')
    fig.suptitle('从类别块到局部票账：有效支持取决于结构位置、对应归组与实际门槛',x=.05,ha='left',fontsize=18)
    handles,labels=axes[0,0].get_legend_handles_labels();fig.legend(handles,labels,loc='upper center',bbox_to_anchor=(.52,.94),ncol=4,frameon=False)
    fig.text(.05,.018,'节点编号只在队内有效；跨队对应通过同一record id与pair index识别。✓表示达到本队门槛。票账图不做合并对应的反事实评分。',fontsize=10,color='#475565')
    fig.subplots_adjust(left=.065,right=.98,top=.88,bottom=.10,hspace=.5,wspace=.22)
    fig.savefig(out/'PURE_EIGHT_SEAT_VOTES.png',dpi=160,facecolor='white');v.plt.close(fig)
    e.gs.save(HERE/'FIGURE_RECEIPT.json',dict(photo_path=str(PHOTO.relative_to(e.ROOT)),photo_sha256=hashlib.sha256(PHOTO.read_bytes()).hexdigest(),
        figures=[dict(path=str(p.relative_to(HERE)),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bytes=p.stat().st_size) for p in sorted(out.glob('*.png'))],
        fused_geometry='unchanged native geometry; no_connection arm shown as isolated nodes only',fusion_calls=0,score_calls=0))
    print('Saved two exact endpoint/vote figures.',flush=True)
if __name__=='__main__':main()
