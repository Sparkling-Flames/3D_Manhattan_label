"""Reflow manuscript evidence at print size; saved geometry and scores remain inputs."""
from pathlib import Path
import copy, json, gzip, re
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from PIL import Image, ImageChops
import fitz
import render_paper_evidence_20261107 as e
import render_manuscript_3d as m
import render_semi_case_20261107 as semi
import render_localization_case_20261107 as loc
ROOT=e.ROOT; PAPER=e.PAPER; OUT=e.OUT
WORK=e.SUPPORT/'整体图表重排_20261108'
BACK=WORK/'source_panels'
AUDIT={}

def capture(module, function):
    result=[]; original=module.save
    module.save=lambda fig,name: result.append((fig,name))
    try: function()
    finally: module.save=original
    assert len(result)==1
    return result[0]

def save(fig,name):
    e.save(fig,name)

def trimmed(path):
    raw=Image.open(path).convert('RGBA');im=Image.alpha_composite(Image.new('RGBA',raw.size,'white'),raw).convert('RGB');mask=ImageChops.difference(im,Image.new('RGB',im.size,'white')).convert('L').point(lambda x:255 if x>25 else 0)
    box=mask.getbbox();assert box
    return im.crop(box)

def photo(fig,rect,path,title=None,trim=False):
    ax=fig.add_axes(rect);ax.imshow(trimmed(path) if trim else Image.open(path));ax.axis('off')
    if title:ax.set_title(title,loc='left',fontsize=8,pad=2)
    return ax

def compact_existing():
    fig,name=capture(e,e.geometry_consensus);fig.set_size_inches(3.45,2.35)
    replacements={'Independent\ncorner pairs':'Corner pairs','Five geometric\nmeasurements':'5 measurements','Person support\nand position':'Support + position'}
    for ax in fig.axes:
        for text in ax.texts:text.set_text(replacements.get(text.get_text(),text.get_text()))
    save(fig,name)
    fig,name=capture(e,e.mixture_effects);fig.set_size_inches(3.45,3.05)
    fig.subplots_adjust(top=.94,bottom=.16,hspace=.85,left=.29,right=.98)
    fig.axes[0].set_title('(a) Combination means',loc='left');fig.axes[1].set_title('(b) Mixture minus pure',loc='left')
    fig.texts[-1].remove();save(fig,name)
    fig,name=capture(e,e.member_distributions);fig.set_size_inches(3.45,2.85)
    fig.subplots_adjust(top=.93,bottom=.18,hspace=.8,left=.16,right=.98)
    for ax in fig.axes:ax.set_xlabel('C1 / C2 / C3 counts');ax.set_yticks([0,50,100]);ax.set_ylabel('Q')
    fig.texts[-1].remove();save(fig,name)
    fig,name=capture(e,e.image_changes);fig.set_size_inches(3.45,2.15);fig.axes[0].set_title('20 → 30 annotators',loc='left');fig.axes[0].set_ylabel('Image-mean ΔQ');save(fig,name)
    fig,name=capture(e,e.doorway_absolute_curves);fig.set_size_inches(3.45,3.05)
    for ax,title in zip(fig.axes,['(a) Screening: Q','(b) Screening: rate','(c) Targets: Q','(d) Targets: rate']):
        ax.set_title(title,fontsize=8,loc='left');ax.set_xlabel('Annotators');ax.set_ylabel('Q' if ax in [fig.axes[0],fig.axes[2]] else 'Rate (%)')
    for ax in fig.axes:
        if ax.get_legend():ax.get_legend().remove()
    fig.legend([Line2D([],[],c=c) for c in ['#b36d37','#26847b','#437b97','#b36d37','#26847b']],['Before','After','Space 1','Space 2','Whole'],ncol=3,loc='lower center',fontsize=7.3,frameon=False)
    fig.set_layout_engine(None);fig.subplots_adjust(left=.14,right=.97,top=.93,bottom=.25,hspace=.85,wspace=.55);save(fig,name)
    fig,name=capture(e,e.same_room);fig.set_size_inches(7.2,2.15)
    for a,title in zip(fig.axes,['(a) View A','Event: before / after','(b) View B','Same member blocks','(c) Pair-mean effects']):
        a.set_title(title,fontsize=8,loc='left',pad=2)
    for a in [fig.axes[1],fig.axes[3]]:a.set_xlabel('');a.set_ylabel('$z/h$')
    fig.texts[-1].remove();fig.texts[0].set_position((.81,.10));save(fig,name)
    fig,name=capture(m,m.group_size_figure);fig.set_size_inches(7.2,1.75)
    ax=fig.axes;fig.delaxes(ax[-1])
    titles=['(a) Mean Q','(b) P10 Q','(c) SD of Q','(d) Floor diversity','(e) Complete rate']
    labels=['Q','Q','SD','1 − IoU','%']
    for i,a in enumerate(ax[:5]):
        a.set_position([.055+i*.196,.28,.14,.52]);a.set_title(titles[i],fontsize=8,loc='left');a.set_ylabel(labels[i],labelpad=1);a.set_xlabel('Annotators',labelpad=1);a.set_xticks([3,6,20,30]);a.tick_params(labelsize=7.3,pad=1)
    fig.legend(*ax[0].get_legend_handles_labels(),loc='lower center',ncol=4,frameon=False,fontsize=8);save(fig,name)

def classes():
    fig=plt.figure(figsize=(7.2,2.65));picked=[]
    for row,(image,diff) in enumerate([(e.CLASS_EASY_IMAGE,'Easy'),('jtcxE69GiFV-26','Difficult')]):
        im=next(x for x in e.DATA['images'] if x['image_code']==image);ref=e.DATA['references'][im['reference_key']];y=.59 if row==0 else .12
        a=photo(fig,[.005,y,.22,.30],e.EX/im['path'],f'({chr(97+row)}) {diff}')
        for col in range(3):
            s=e.chosen(image,f'C{col+1}');o=e.DATA['objects'][s['object_id']];picked.append(s['object_id'])
            a=fig.add_axes([.29+col*.235,y,.17,.30]);e.clean(a)
            for obj,c,ls in [(ref,'#7f8b94','--'),(o,e.COLORS[col],'-')]:
                xy=np.asarray(obj['traits']['floor_xz_h']);ring=np.vstack([xy,xy[0]]);a.plot(*ring.T,c=c,ls=ls,lw=1)
            for edge in o['traits']['short_edge_start_nodes_1based']:a.plot(*ring[edge-1:edge+1].T,c='#c18b00',lw=2)
            a.scatter([0],[0],marker='+',c='#333333',s=12)
            x0,x1,z0,z1=im['floor_bounds'];a.set(xlim=(x0,x1),ylim=(z0,z1),aspect='equal',xlabel='$x/h$',ylabel='$z/h$');a.tick_params(labelsize=7,pad=1)
            a.set_title(f'C{col+1} · {e.IDS[s["worker_id"]]}',fontsize=8,pad=1)
            if row==0:a.set_xlabel('')
            fig.text(.375+col*.235,y-(.09 if row==0 else .14),f'{s["turn_n"]:.0f} turns · Q {s["B8L2"]:.1f} · {s["source_active_time_seconds"]:.0f} s',ha='center',fontsize=7.5)
    save(fig,'class_annotations');AUDIT['class_examples']=picked

def fireplace():
    base=e.SUPPORT/'Dot交付审查_20261106/Paper_Figures_4_5_6_10_CURRENT_ONLY_20261106/02_Figure6_latest'
    d=json.loads((base/'inputs/fig6_geometry_inputs.json').read_text(encoding='utf-8'));floors=[e.geometry(c['points'])[0,:,:2] for c in d['cases']];xy=np.concatenate(floors);lo=xy.min(0)-.15;hi=xy.max(0)+.15
    renders=[];boxes=[]
    for case in d['cases'][1:]:
        raw=Image.open(base/f'output/renders/Fig6_{case["label"]}_complete_walls.png').convert('RGBA')
        im=Image.alpha_composite(Image.new('RGBA',raw.size,'white'),raw).convert('RGB');renders.append(im)
        boxes.append(ImageChops.difference(im,Image.new('RGB',im.size,'white')).convert('L').point(lambda x:255 if x>25 else 0).getbbox())
    assert renders[0].size==renders[1].size
    shared=(min(b[0] for b in boxes),min(b[1] for b in boxes),max(b[2] for b in boxes),max(b[3] for b in boxes))
    AUDIT['fireplace_common_render_crop']=shared
    fig=plt.figure(figsize=(3.45,2.65))
    photo(fig,[.01,.69,.36,.24],base/'inputs'/d['image'],'(a) Panorama')
    photo(fig,[.01,.16,.36,.32],base/'output/verified_gt_views/GT_main.png','(b) Context',True)
    for k,(x,c,title) in enumerate([(.48,'#168c87','A29: 4 corners'),(.79,'#df732f','A59: 8 corners')],1):
        a=fig.add_axes([x,.61,.19,.30]);e.clean(a)
        for f,col,ls in [(floors[0],'#68737c','--'),(floors[k],c,'-')]:a.plot(*np.vstack([f,f[0]]).T,c=col,ls=ls,lw=1)
        a.set(xlim=(lo[0],hi[0]),ylim=(lo[1],hi[1]),aspect='equal',xlabel='$x/h$',ylabel='$z/h$' if k==1 else '')
        a.set_title(title,fontsize=7.5,pad=1);a.tick_params(labelsize=7,pad=1)
        a=fig.add_axes([x-.055,.10,.27,.37]);a.imshow(renders[k-1].crop(shared));a.axis('off')
    fig.legend(handles=[Line2D([],[],c='#68737c',ls='--',label='Reference'),Line2D([],[],c='#168c87',label='A29'),Line2D([],[],c='#df732f',label='A59')],loc='lower center',ncol=3,frameon=False,fontsize=7.5)
    save(fig,'individual_fireplace')

def semi_case():
    initial,finals,counts=semi.load_case();fig,axs=plt.subplots(2,2,figsize=(3.45,2.25));fig.subplots_adjust(left=.16,right=.99,bottom=.20,top=.87,hspace=.18,wspace=.18)
    im=Image.open(semi.PHOTO)
    for col,points in enumerate([initial,finals[semi.EDITED]['points']]):
        for row,yr in enumerate(semi.CROP_Y):
            a=axs[row,col];crop=im.crop((640,2*yr[1],840,2*yr[0]));a.imshow(crop,extent=[*semi.CROP_X,*yr],interpolation='none');ps=points[row::2]
            a.scatter(*ps.T,s=16,c=[semi.EXTRA if np.isclose(p[0],initial[4,0]) else semi.BASE for p in ps],edgecolors='white',lw=.5)
            a.set(xlim=semi.CROP_X,ylim=yr,xticks=[330,370,410]);a.tick_params(labelsize=7,pad=1,length=2)
            if row==0:a.set_xticklabels([]);a.set_title('Initial = A3 · 5 pairs' if col==0 else 'A2 edited · 4 pairs',fontsize=7.7)
            else:a.set_xlabel('$u$ (px)',labelpad=1)
            if col==0:a.set_ylabel(('Top' if row==0 else 'Floor')+' $v$ (px)',labelpad=1)
            else:a.set_yticklabels([])
    save(fig,'semi_editing');AUDIT['semi_counts']=counts

def profiles():
    p=ROOT/'research/workers/current_class_interpretation_20261104/dstruct/ORDINARY_RECORDS_WITH_COMPONENTS.csv.gz'
    d=pd.read_csv(p)
    for metric in ['B8L2','log_time']:
        keys=['pool_id']+(['origin','time_source'] if metric=='log_time' else [])
        expected=d[metric]-d.groupby(keys,dropna=False)[metric].transform('median')
        assert np.allclose(expected,d[metric+'_peer'],equal_nan=True,atol=1e-10)
    d=d[(d.layer=='ordinary_manual')&(d.scope=='primary')].copy()
    assert len(d)==6512 and d.worker_id.nunique()==60 and not d.object_id.duplicated().any()
    # Paired support for quality and time; within-source peer centering avoids mixing clock baselines.
    d=d.dropna(subset=['B8L2_peer','log_time_peer']);rows=d.groupby(['worker_id','building','image'])[['B8L2_peer','log_time_peer']].mean().groupby(['worker_id','building']).mean().groupby('worker_id').mean()
    a=pd.read_csv(p.parent/'SAME_PERSON_SAME_BUILDING_DIFFICULTY.csv.gz');a=a[(a.method==e.METHOD)&(a.condition=='manual')&(a.scope=='primary')&(a.source_stratum=='all_sources')&(a.metric=='turn_n')]
    h=a.groupby('worker_id').hard_minus_easy.mean();joined=rows.join(h.rename('turn_response'),how='inner');assert len(joined)>20
    fig,axs=plt.subplots(1,2,figsize=(3.45,1.85));fig.subplots_adjust(left=.15,right=.98,bottom=.27,top=.86,wspace=.60)
    for ax,x,xlabel,title in [(axs[0],joined.log_time_peer,'Relative log time','(a) Quality and labor'),(axs[1],joined.turn_response,'Turns: difficult − easy','(b) Structural response')]:
        ax.scatter(x,joined.B8L2_peer,c='#367b91',s=12,alpha=.75);ax.axhline(0,c='#777777',lw=.5);e.clean(ax);ax.set(xlabel=xlabel,ylabel='Relative Q' if ax==axs[0] else '');ax.set_title(title,loc='left',fontsize=8)
    save(fig,'continuous_profiles');joined.to_csv(WORK/'continuous_profiles.csv');AUDIT['continuous_profiles']={'people':len(joined),'record_support':int(d.worker_id.isin(joined.index).sum()),'source':str(p.relative_to(ROOT)),'aggregation':'image, building, worker means; paired Q/time observations; hard-easy within-person building contrasts'}

def study():
    im=next(x for x in e.DATA['images'] if x['image_code']==e.CLASS_EASY_IMAGE);s=e.chosen(im['image_code'],'C3');o=e.DATA['objects'][s['object_id']]
    fig=plt.figure(figsize=(7.2,1.85));a=fig.add_axes([.005,.40,.25,.48]);e.panorama(a,Image.open(e.EX/im['path']),o['points_1024x512']);a.set_title('(a) Upper/lower corner pairs',loc='left',fontsize=8)
    a=fig.add_axes([.25,.32,.18,.60],projection='3d');g=e.geometry(o['points_1024x512']);m.frame(a,[g],1);m.wire(a,g,'#267788');a.set_axis_off();a.set_title('(b) 3D preview',fontsize=8,pad=0)
    a=fig.add_axes([.46,.12,.54,.82]);a.axis('off')
    lines=['Independent submissions','RQ1  Individual expression','RQ2  Group size: nested teams','RQ3  Composition: controlled replacements','RQ4  Views, targets and recorded labor']
    for i,t in enumerate(lines):a.text(.01,.95-i*.18,t,fontsize=8,va='top',weight='bold' if i==0 else 'normal')
    fig.text(.02,.12,'Manual: draw from scratch\nSemi: edit an initial layout',fontsize=8)
    fig.text(.48,.02,'Team outputs → structural consensus + geometric quality',fontsize=8)
    save(fig,'study_design')

def localization():
    d=loc.load_and_check();before=copy.deepcopy(d);arms=d['arms'];ref=np.asarray(d['reference']['floor_xz_h']);feet={s:np.asarray(v['geometry']['footprint']) for s,v in arms.items()}
    fig=plt.figure(figsize=(3.45,2.75));a=fig.add_axes([.14,.73,.83,.18]);loc.axes_style(a)
    for foot,c,ls in [(ref,loc.COLORS['R'],'--')]+[(feet[s],loc.COLORS[s],'-') for s in ['A','C']]:loc.draw_ring(a,foot,c,ls)
    a.set(xlim=(-6,1.75),ylim=(-.85,.8),aspect='equal',xlabel='$x/h$',ylabel='$z/h$');a.set_title('(a) Complete footprints',loc='left',fontsize=8,pad=2)
    a.scatter([0],[0],marker='^',c='#333333',s=14)
    a=fig.add_axes([.15,.20,.38,.33]);loc.axes_style(a);common=set(d['event']['D_workers'].split('|'));raw={}
    for s,v in arms.items():raw[s]={o['worker']:np.asarray(o['points'])[1] for o in next(g for g in v['full_state']['identity_groups'] if g['feature_id']=='node_003')['members']}
    for s,pts,marker in [('D',[raw['A'][w] for w in common],'o'),('A',[v for w,v in raw['A'].items() if w not in common],'s'),('C',[v for w,v in raw['C'].items() if w not in common],'^')]:a.scatter(*np.asarray(pts).T,s=10,c=loc.COLORS[s],marker=marker)
    for s in ['A','C']:a.scatter(*np.asarray(arms[s]['geometry']['points'])[7],s=25,c=loc.COLORS[s],edgecolors='black',lw=.5)
    a.invert_yaxis();a.set(xlabel='$u$ (px)',ylabel='$v$ (px)');a.set_title('(b) Corner 4',fontsize=8,loc='left',pad=2)
    a=fig.add_axes([.70,.20,.20,.33]);loc.axes_style(a)
    for foot,c,ls in [(ref,loc.COLORS['R'],'--')]+[(feet[s],loc.COLORS[s],'-') for s in ['A','C']]:loc.draw_ring(a,foot,c,ls)
    a.set(xlim=(-5.88,-5.30),ylim=(-.66,.52),aspect='equal',xlabel='$x/h$',xticks=[-5.8,-5.4]);a.tick_params(labelsize=7);a.set_title('(c) Detail',fontsize=8,pad=2)
    fig.legend(handles=[Line2D([],[],c=loc.COLORS[s],label=l,ls='--' if s=='R' else '-') for s,l in [('A','Before'),('C','After'),('R','Reference')]],loc='lower center',ncol=3,frameon=False,fontsize=7.5)
    assert d==before;save(fig,'localization_mechanism');AUDIT['localization_geometry_unchanged']=True

def scenes():
    base=ROOT/'analysis_results/dot_refinement_review_20261107/Dot_Scene_Refinement_01-05_FINAL_20261107'
    cases=[('Oblique wall','02_oblique','test/x8F5xyUWy9e_a51a0e2811f342a599ae4cdb9b84ff23'),('Sloped ceiling','03_sloped_ceiling','valid/S9hNv5qa7GM_53d54b73e58940019b731673e65c1902'),('Split ceiling','04_split_ceiling','test/q9vSo1VnCiC_69591068e5614642b710a8fb7733bdeb'),('Split floor','05_split_floor','test/uNb9QFRL6hY_ce88ee8b7ee84fca92c13ab16599d90e')]
    fig=plt.figure(figsize=(7.2,1.95))
    for i,(title,folder,source) in enumerate(cases):
        split,n=source.split('/');x=i*.25
        photo(fig,[x+.005,.60,.24,.30],ROOT/f'data/mp3d_layout/{split}/img/{n}.png',f'({chr(97+i)}) {title}')
        model=base/folder/'main.png' if i<3 else e.SUPPORT/'图5_下沉楼梯校准_20261107/main.png'
        photo(fig,[x+.005,.01,.24,.57],model,trim=True)
    save(fig,'oos_geometry_3d')
    fig=plt.figure(figsize=(7.2,1.65))
    photo(fig,[.00,.06,.30,.87],base/'01_doorway/main.png','(a) Threshold: 2t7-07',True)
    photo(fig,[.32,.20,.30,.68],ROOT/'data/mp3d_layout/valid/img/2t7WUuJeko7_53937db036374126830e0f1203b04ead.png','(b) Original panorama')
    photo(fig,[.65,.20,.35,.68],BACK/'doorway_scope_7y18.png','(c) Targets: 7y3s-18')
    save(fig,'doorway_boundary_3d')

def pdf_panel(name,clip):
    doc=fitz.open(BACK/(name+'.pdf'));pix=doc[0].get_pixmap(matrix=fitz.Matrix(4,4),clip=fitz.Rect(*clip),alpha=False)
    return Image.frombytes('RGB',[pix.width,pix.height],pix.samples)

def observed():
    fig=plt.figure(figsize=(3.45,2.65))
    a=fig.add_axes([.02,.53,.60,.43]);a.imshow(pdf_panel('observed_corner_geometry',(13,17,250,136)));a.axis('off');a.set_title('(a) Panorama',fontsize=8,pad=2,loc='left')
    a=fig.add_axes([.66,.53,.32,.43]);a.imshow(pdf_panel('observed_corner_geometry',(16,153,130,208)));a.axis('off');a.set_title('(b) Floor corner',fontsize=8,pad=2,loc='left')
    # Full original/reference coordinates; no recentering or regularization.
    d=json.loads((ROOT/'research/quality/quality_pro_return_review_20261014/evidence/J04_interventions.json').read_text(encoding='utf-8'))
    a=fig.add_axes([.17,.17,.28,.27]);e.clean(a)
    for pts,c,ls in [(d['original_points'],'#2587bd','-'),(d['reference_points'],'#68737c','--')]:
        xy=e.geometry(pts)[0,:,:2];a.plot(*np.vstack([xy,xy[0]]).T,c=c,ls=ls,lw=1)
    a.set(aspect='equal',xlabel='$x/h$',ylabel='$z/h$');a.set_title('(c) Full BEV',fontsize=8,pad=2)
    a=fig.add_axes([.53,.12,.46,.36]);a.imshow(pdf_panel('observed_corner_geometry',(278,26,516,210)));a.axis('off');a.set_title('(d) 3D overlay',fontsize=8,pad=0)
    fig.legend(handles=[Line2D([],[],c='#2587bd',label='Original'),Line2D([],[],c='#68737c',ls='--',label='Reference')],loc='lower center',ncol=2,frameon=False,fontsize=8)
    save(fig,'observed_corner_geometry')

def bathroom():
    path=ROOT/'research/workers/personnel_v21_reselection_20261029/stage06_cases/traces_semantic/ae9bc0bdaf9a5f2119cea910.json.gz'
    with gzip.open(path,'rt',encoding='utf-8') as f:t=json.load(f)
    state=t['arms']['B']['full_state'];records={r['id']:r for r in t['pool']['records']};selected=[a for a in state['assignments'] if a['worker'] in ['W006','W108']]
    assert len(selected)==2
    pts=np.concatenate([e.geometry(records[a['id']]['points'])[0,:,:2] for a in state['assignments']]);lo=pts.min(0)-.1;hi=pts.max(0)+.1
    fig=plt.figure(figsize=(7.2,1.8));cols=['#00b6d0','#d8a000']
    for i,a in enumerate(selected):
        ax=fig.add_axes([.055+i*.19,.22,.13,.58]);xy=e.geometry(records[a['id']]['points'])[0,:,:2];ax.plot(*np.vstack([xy,xy[0]]).T,c='#6e8792',lw=1)
        for v,feature in zip(xy,a['feature_ids']):
            if feature in ['node_004','node_005']:ax.scatter(*v,c=cols[['node_004','node_005'].index(feature)],s=18)
        ax.set(xlim=(lo[0],hi[0]),ylim=(lo[1],hi[1]),aspect='equal',xlabel='$x/h$',ylabel='$z/h$' if i==0 else '');e.clean(ax);ax.set_title(f'({chr(97+i)}) Original {e.IDS[a["worker"]]}',loc='left',fontsize=8)
    ax=fig.add_axes([.42,.22,.12,.58]);arr=np.array([[f in a['feature_ids'] for f in ['node_004','node_005']] for a in state['assignments']]);assert arr.sum(0).tolist()==[4,2]
    for i in range(10):
        for j in range(2):ax.scatter(j,i,s=15,facecolor=cols[j] if arr[i,j] else 'white',edgecolor=cols[j],lw=.6)
    ax.set(xticks=[0,1],xticklabels=['4 votes','2 votes'],yticks=[],ylim=(9.6,-.6),xlim=(-.6,1.6));ax.spines[:].set_visible(False);ax.tick_params(length=0,labelsize=7.5);ax.set_title('(c) Ten voters',fontsize=8)
    for i,(clip,title,desc) in enumerate([((182,24,345,157),'(d) Team 1','4/2 votes: 4 corners'),((352,24,515,157),'(e) Team 2','8/8 votes: 6 corners')]):
        a=fig.add_axes([.59+i*.21,.17,.20,.65]);a.imshow(pdf_panel('bathroom_turn_votes',clip));a.axis('off');a.set_title(title,fontsize=8,pad=1);fig.text(.69+i*.21,.11,desc,ha='center',fontsize=7.5)
    fig.text(.30,.015,'Matched turns: cyan / amber. Filled symbols = support. Threshold: 5 people.',ha='center',fontsize=7.5)
    save(fig,'bathroom_turn_votes')

def supplement():
    doc=fitz.open();manifest=json.loads((WORK/'manifest.json').read_text(encoding='utf-8'))
    for i,row in enumerate(manifest,1):
        page=doc.new_page(width=595,height=842);page.insert_text((35,35),f'Supplement B{i}: detailed evidence panels',fontsize=12)
        names=row['assets'];height=600/len(names)
        for j,n in enumerate(names):
            dest=fitz.Rect(35,55+j*height,560,55+(j+1)*height-8)
            if n.endswith('.pdf'):
                src=fitz.open(BACK/n);page.show_pdf_page(dest,src,0)
            else:page.insert_image(dest,filename=str(BACK/n),keep_proportion=True)
        caption=re.search(r'\\caption\{(.*?)\}\s*\\label',row['latex'],re.S)
        if caption:
            txt=caption[1].replace('\\%','%').replace('~',' ').replace('$','').replace('\\','')
            remaining=page.insert_textbox(fitz.Rect(35,670,560,810),txt,fontsize=8.5)
            assert remaining >= 0, (i, remaining)
        else:
            raise ValueError(f'Missing caption for supplement panel {i}')
    doc.save(PAPER/'supplement_evidence.pdf');doc.close()

if __name__=='__main__':
    plt.rcParams.update({'font.size':8,'axes.labelsize':8,'axes.titlesize':8,'xtick.labelsize':7.5,'ytick.labelsize':7.5,'pdf.fonttype':42})
    for f in [compact_existing,classes,fireplace,semi_case,profiles,study,localization,scenes,observed,bathroom,supplement]:
        f();print(f.__name__+' OK',flush=True)
    AUDIT.update(e.AUDIT);(WORK/'RELAYOUT_CHECKS.json').write_text(json.dumps(AUDIT,ensure_ascii=False,indent=2),encoding='utf-8')
