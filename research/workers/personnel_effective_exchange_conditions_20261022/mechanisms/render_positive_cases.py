#!/usr/bin/env python3
"""Render actual photographs plus frozen raw annotations, votes and endpoints."""
import copy,importlib.util,json,sys
from pathlib import Path
import numpy as np
from PIL import Image
import export_positive_cases as e

def main():
    spec=importlib.util.spec_from_file_location('existing_case_renderer',e.OLD/'evidence/render_evidence.py');r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
    spec=importlib.util.spec_from_file_location('frozen_viewer',r.RENDERER);v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
    cases=[]
    for p in sorted((e.HERE/'cases').glob('*.json.gz')):
        c=copy.deepcopy(e.gs.read(p));cases.append(c)
        photos=e.V3/'evidence/originals' if 'wc2' in c['case_id'] else e.HERE.parent/'originals'
        photo=r.original_photo(c,photos)
        if 'zs16' in c['case_id']:
            c['zoom_erp']=[460,530,175,355];c['focus_title']='衣柜右侧墙体转折：人数门槛10→11'
            c['highlight_reference_edges']=[0,1]
            g=v.viewer_geometry(c['reference']['points_1024x512']);p0,p1=g['floor'][:2]
            c['zoom_bev']=[min(p0[0],p1[0])-.7,max(p0[0],p1[0])+.7,min(p0[1],p1[1])-.7,max(p0[1],p1[1])+.7]
        else:
            c['zoom_erp']=[525,565,195,330];c['focus_title']='同一角点的中位数定位，全部20票都保留'
        c['raw_overlay_title']=c['title']+'：三块实际成员原答'
        out=e.HERE/'figures'/c['case_id'];out.mkdir(parents=True,exist_ok=True)
        result=v.render_case(c,out,font_path=e.HERE/'assets/NotoSansCJKsc-MechanismSubset.ttf')
        result['raw_three_views']=r.raw_three_views(v,c,photo,out)
        e.gs.save(out/'RENDER_RECEIPT.json',dict(result,case_sha256=e.prior.sha(p),no_fusion=True,no_scoring=True,original_image_sha256=c['image_sha256']))
        print('rendered',c['case_id'],flush=True)
    zs=[c for c in cases if 'zs16' in c['case_id']];zs.sort(key=lambda c:c['n'])
    fig,axes=v.plt.subplots(2,4,figsize=(16,8),gridspec_kw={'height_ratios':[1.25,1]})
    photo=np.asarray(Image.open(e.HERE.parent/'originals'/f"{zs[0]['image_id']}.png").convert('RGB'))
    colors={'B':'#3e78a4','C':'#299678'}
    for col,(c,arm) in enumerate((c,a) for c in zs for a in ['B','C']):
        t=c['teams']['ABC'.index(arm)];ax=axes[0,col];v._erp_background(ax,photo,[460,530,175,355])
        v._erp_edges(ax,c['reference']['points_1024x512'],v.REF_ERP_COLOR,reference=True,linewidth=1.3)
        v._erp_edges(ax,t['geometry']['points'],colors[arm],linewidth=1.6,alpha=1,markers=True)
        ax.set_title(f"n={c['n']}，{arm}团队\nQ={t['B8L2']:.2f}；{t['nodes']}个节点",fontsize=12)
        ax=axes[1,col];votes=10 if arm=='B' else 11;threshold=t['minimum_support']
        ax.bar(['共同背景','替换块'],[5,votes-5],color=['#91a1b4',colors[arm]])
        ax.set_ylim(0,8);ax.set_ylabel('r1角点票数')
        ax.set_title(f"总票数{votes} / 门槛{threshold}："+('保留' if votes>=threshold else '失选'),fontsize=12)
        ax.text(.5,-.20,f"记录时间 {t['source_time_total_seconds']:.0f} 秒",transform=ax.transAxes,ha='center',fontsize=10)
        ax.spines[['top','right']].set_visible(False)
    fig.suptitle('同一类别块的作用取决于背景与门槛：zs-16 的 n20→n21 路径',fontsize=17,y=.99)
    fig.text(.035,.02,'只增加共同背景成员W125；三组X/Y/Z保持原人。W125未提供r1票，B仍10票却低于新门槛11，C的11票恰好保留。\n黄色为冻结参考；同类B和跨类C均由相同背景构成。这里解释具体路径，不用单案例代替总体均值。',fontsize=10)
    fig.subplots_adjust(left=.05,right=.985,top=.90,bottom=.16,hspace=.38,wspace=.32)
    dest=e.HERE/'figures/Zs16_THRESHOLD_AND_BACKGROUND.png';fig.savefig(dest,dpi=170,facecolor='white');v.plt.close(fig)
    print('saved',dest,flush=True)

if __name__=='__main__':main()
