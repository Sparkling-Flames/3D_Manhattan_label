"""English scientific figures and complete per-image atlases from saved results."""
from pathlib import Path
import json,gzip,html,os
from contextlib import nullcontext
import numpy as np,pandas as pd
os.environ.setdefault('MPLCONFIGDIR',str(Path(__file__).resolve().parents[1]/'assets/mpl_cache'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'stage08_figures';OUT.mkdir(exist_ok=True)
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False,'axes.titlesize':12,'figure.dpi':130,'savefig.dpi':160,'pdf.fonttype':42,'svg.fonttype':'none','axes.labelcolor':'#233343','text.color':'#233343'})
COL={'Easy':'#2276a5','Medium':'#d19326','Hard':'#a64967','All':'#172d43'}
DC={'doorway_before':'#547a97','doorway_after':'#239278','doorway_whole':'#8164ac','doorway_space1':'#cf9133','doorway_space2':'#bd5b6a'}
DL={'doorway_before':'Before screening','doorway_after':'After screening','doorway_whole':'Whole-compatible','doorway_space1':'Space 1','doorway_space2':'Space 2'}

def save(fig,name,data=None):
 for ext in ['png','pdf','svg']:fig.savefig(OUT/f'{name}.{ext}',bbox_inches='tight',facecolor='white')
 if data is not None:data.to_csv(OUT/f'{name}_data.csv.gz',index=False,compression='gzip')
 plt.close(fig)

def read():
 idx=pd.read_csv(ROOT/'stage02_normalized/manual/POOL_INDEX.csv');idx=idx[idx.domain.eq('ordinary_manual_main')]
 c=pd.read_csv(ROOT/'stage03_response/manual/POOL_K_STATISTICS.csv.gz',low_memory=False);c=c[c.domain.eq('ordinary_manual_main')]
 o=pd.read_csv(ROOT/'stage03_response/manual/PLATEAU_SENSITIVITY.csv.gz');o=o[o.domain.eq('ordinary_manual_main')&o.primary_rule]
 geo=pd.read_csv(ROOT/'stage04_geometry/ordinary_cached/GEOMETRY_U_CURVES.csv.gz',low_memory=False)
 go=pd.read_csv(ROOT/'stage04_geometry/ordinary_cached/GEOMETRY_LOW_DISPERSION_SENSITIVITY.csv.gz');go=go[go.primary_rule]
 dc=pd.read_csv(ROOT/'stage03_response/doorway/POOL_K_STATISTICS.csv.gz');dg=pd.read_csv(ROOT/'stage04_geometry/doorway/GEOMETRY_PAIR_SUMMARY.csv.gz')
 du=pd.read_csv(ROOT/'stage04_geometry/doorway_exact_U/GEOMETRY_U_CURVES.csv.gz').rename(columns={'k':'k_from'})
 du['k_to']=du.k_from;du['kind']='same_k_U';dg=pd.concat([dg[~dg.kind.eq('same_k_matching')],du],ignore_index=True)
 return idx,c,o,geo,go,dc,dg

def make_overviews(idx,c,o,geo,go,dc,dg):
 fig,axs=plt.subplots(2,2,figsize=(12,8),layout='constrained');records=[]
 for ax,(metric,title,limit) in zip(axs.ravel(),[('B8L2_mean','Mean B8L2: remaining range <= 2 points',2),('B8L2_p10','P10 B8L2: remaining range <= 2 points',2),('B8L2_sd','B8L2 SD: remaining range <= 1 point',1),('V_floor','Floor diversity: all later mean 1-IoU <= 0.10',.1)]):
  src=go[go.metric.eq(metric)] if metric=='V_floor' else o[o.metric.eq(metric)]
  for dl in ['Easy','Medium','Hard']:
   g=src[src.difficulty_en.eq(dl)];on=g.onset_k.to_numpy();ks=np.arange(3,36);vals=np.array([(on<=k).sum()/len(g) for k in ks]);ax.step(ks,vals*100,where='post',color=COL[dl],label=f'{dl} ({len(g)} images)',lw=2)
   for k,v in zip(ks,vals):records.append(dict(metric=metric,difficulty=dl,k=k,all_images=len(g),onsets_at_or_before_k=int((on<=k).sum()),proportion=v))
  ax.set(title=title,xlabel='Annotators at onset (k)',ylabel='Share of all images (%)',ylim=(0,101),xlim=(3,35));ax.grid(alpha=.16);ax.legend(fontsize=8,loc='upper left' if metric=='B8L2_sd' else 'lower right')
 fig.suptitle('Small-change onset varies across images and metrics',fontsize=16)
 fig.supxlabel('All later observed counts must qualify; at least max(5, ceil(0.15 N)) further people are observed.',fontsize=9)
 save(fig,'01_Onset_by_Difficulty',pd.DataFrame(records))
 keep=idx[idx.N.ge(30)];g=c[c.pool_id.isin(keep.pool_id)&c.k.between(3,30)];gg=geo[geo.pool_id.isin(keep.pool_id)&geo.k.between(3,30)&geo.metric.eq('V_floor')];records=[]
 fig,axs=plt.subplots(2,2,figsize=(12,8),layout='constrained')
 for ax,metric,title,yl in zip(axs.ravel(),['B8L2_mean','B8L2_p10','B8L2_sd','V_floor'],['Mean quality','Lower tail of team quality','Member-combination variability','Floor-layout diversity'],['B8L2 (0-100)','P10 B8L2 (0-100)','B8L2 SD (points)','Mean pairwise 1-IoU']):
  for dl in ['All','Easy','Medium','Hard']:
   z=gg if metric=='V_floor' else g
   if dl!='All':z=z[z.difficulty_en.eq(dl)]
   col='mean' if metric=='V_floor' else metric
   agg=z.groupby('k')[col].agg(['mean','count']);ax.plot(agg.index,agg['mean'],label=f'{dl}',color=COL[dl],lw=2.4 if dl=='All' else 1.5)
   for k,r in agg.iterrows():records.append(dict(panel_min_N=30,metric=metric,difficulty=dl,k=k,valid_images=int(r['count']),mean=r['mean']))
  ax.set(title=title,xlabel='Annotators (k)',ylabel=yl);ax.grid(alpha=.16);ax.legend(fontsize=8)
 fig.suptitle(f'Same {len(keep)} images, capacity at least 30: average quality and tail response',fontsize=15)
 fig.supxlabel('Image-equal conditional quality and geometry; output states and valid image counts are retained in the data.',fontsize=9)
 save(fig,'02_Fixed171_Count_Response',pd.DataFrame(records))
 fig,axs=plt.subplots(1,3,figsize=(13,4),layout='constrained');records=[]
 for ax,met,title in zip(axs,['B8L2_mean','B8L2_p10','B8L2_sd'],['Mean quality change','P10 quality change','Quality SD change']):
  p=g.pivot(index='pool_id',columns='k',values=met);v=p[30]-p[20];v=v.dropna()
  ax.hist(v,bins=25,color='#4f8eaf',edgecolor='white',lw=.4);ax.axvline(0,color='#27394a',lw=1);ax.axvline(v.mean(),color='#b85e39',ls='--',lw=1.8)
  ax.set(title=f'{title}\nmean {v.mean():+.2f}; {len(v)} images',xlabel='Change from k=20 to k=30',ylabel='Images');ax.grid(axis='y',alpha=.15)
  for pool,value in v.items():records.append(dict(pool_id=pool,metric=met,k_from=20,k_to=30,delta=value))
 fig.suptitle('A small overall gain does not describe the lower tail or the distribution of image changes',fontsize=14)
 save(fig,'03_Image_Changes_20_to_30',pd.DataFrame(records))
 fig,axs=plt.subplots(2,2,figsize=(12,8),layout='constrained');records=[]
 for ax,metric,title,yl in zip(axs.ravel(),['B8L2_mean','B8L2_p10','B8L2_sd','complete_evaluable_rate'],['Mean quality','Lower tail','Member-combination variability','Complete and evaluable output'],['B8L2 (0-100)','P10 B8L2 (0-100)','B8L2 SD (points)','Fraction of all paths']):
  for dom in ['doorway_before','doorway_after']:
   z=dc[dc.domain.eq(dom)&dc.k.between(3,14)];ag=z.groupby('k')[metric].agg(['mean','count'])
   ax.plot(ag.index,ag['mean'],color=DC[dom],lw=2.3,label=DL[dom])
   for k,r in ag.iterrows():records.append(dict(domain=dom,k=k,metric=metric,images=int(r['count']),mean=r['mean']))
  ax.set(title=title,xlabel='Annotators (k)',ylabel=yl);ax.grid(alpha=.16);ax.legend(fontsize=9)
  if metric.endswith('_rate'):ax.set_ylim(0,1.02)
 fig.suptitle('Doorway screening: the same 17 images and common counts 3-14',fontsize=15)
 fig.supxlabel('584 eligible originals before screening; 439 after. Whole-target comparison; side-target pools are separate.',fontsize=9)
 save(fig,'04_Doorway_Common14_Screening',pd.DataFrame(records))
 fig,ax=plt.subplots(figsize=(8.5,5.5),layout='constrained');full=c[c.k.eq(c.N)][['pool_id','B8L2_mean']].rename(columns={'B8L2_mean':'full_B8L2'});q=o[o.metric.eq('B8L2_mean')].merge(full,on='pool_id');q=q[q.onset_k.notna()]
 for dl in ['Easy','Medium','Hard']:
  a=q[q.difficulty_en.eq(dl)];ax.scatter(a.onset_k_fraction,a.full_B8L2,label=f'{dl} ({len(a)})',c=COL[dl],alpha=.7,s=32,edgecolor='white',lw=.35)
 pa=q[q.image.eq('pa4otMbVnkk-11')]
 if len(pa):r=pa.iloc[0];ax.annotate('pa4-11: stable reference mismatch',xy=(r.onset_k_fraction,r.full_B8L2),xytext=(.23,13),arrowprops=dict(arrowstyle='-',color='#687c8b'),fontsize=9)
 ax.set(xlabel='Mean-Q onset as fraction of the available pool (k/N)',ylabel='B8L2 of the actual full team',title='A stable quality curve can still end at low quality',ylim=(0,100),xlim=(0,.86));ax.grid(alpha=.16);ax.legend(title='Frozen difficulty',fontsize=9)
 save(fig,'05_Stability_Is_Not_Accuracy',q)
 fig,axs=plt.subplots(1,2,figsize=(12,4.5),layout='constrained');records=[]
 for ax,kind,metric,title,yl in [(axs[0],'same_k_U','floor_distance','Different teams at the same count','Mean pairwise 1-IoU'),(axs[1],'adjacent_1','floor_distance','Adding one person on the same path','Mean within-path floor 1-IoU')]:
  for dom in ['doorway_before','doorway_after']:
   z=dg[dg.domain.eq(dom)&dg.kind.eq(kind)&dg.metric.eq(metric)&dg.k_from.between(3,13 if kind=='adjacent_1' else 14)];ag=z.groupby('k_from')['mean'].agg(['mean','count']);ax.plot(ag.index,ag['mean'],lw=2,color=DC[dom],label=DL[dom])
   for k,r in ag.iterrows():records.append(dict(domain=dom,kind=kind,metric=metric,k=k,images=int(r['count']),mean=r['mean']))
  ax.set(title=title,xlabel='Annotators before addition (k)' if kind=='adjacent_1' else 'Annotators (k)',ylabel=yl);ax.grid(alpha=.16);ax.legend(fontsize=9)
 fig.suptitle('Doorway geometry changes remain distinct from quality changes',fontsize=15)
 fig.supxlabel('Same-k diversity uses the full path-frequency U statistic; one-step change uses every saved path.',fontsize=9)
 save(fig,'06_Doorway_Geometry_Response',pd.DataFrame(records))

def atlas(idx,c,o,geo,dc,dg):
 imgdir=OUT/'per_image';imgdir.mkdir(exist_ok=True)
 index=[] if len(idx) else pd.read_csv(OUT/'IMAGE_ATLAS_INDEX.csv').query('domain == "ordinary_manual_main"').to_dict('records')
 with (PdfPages(OUT/'Manual_206_Image_Atlas.pdf') if len(idx) else nullcontext(None)) as pdf:
  for _,r in idx.sort_values(['difficulty_en','image']).iterrows():
   s=c[c.pool_id.eq(r.pool_id)&c.k.ge(3)];g=geo[geo.pool_id.eq(r.pool_id)&geo.k.ge(3)];op=o[o.pool_id.eq(r.pool_id)].set_index('metric')
   fig,axs=plt.subplots(2,2,figsize=(11.7,7.8),layout='constrained')
   ax=axs[0,0];ax.fill_between(s.k,s.B8L2_p10,s.B8L2_p90,color='#80afd0',alpha=.2,label='P10-P90');ax.plot(s.k,s.B8L2_mean,c='#256e9f',label='B8L2 mean',lw=2);ax.plot(s.k,s.B8L2_p10,c='#bd7d28',label='B8L2 P10',lw=1.5);ax.plot(s.k,s.D10_mean,c='#687889',label='D10 mean',lw=1,ls=':');ax.set(title='Conditional quality',ylabel='Score (0-100)',ylim=(0,100));ax.legend(fontsize=8,ncol=2)
   axs[0,1].plot(s.k,s.B8L2_sd,color='#bd7d28',lw=2);axs[0,1].set(title='Different members, same k',ylabel='B8L2 SD (points)',ylim=(0,None))
   for metric,col,label in [('V_floor','#256e9f','Floor 1-IoU'),('V_centroid_h','#8b5c99','Centroid distance / camera height')]:
    a=g[g.metric.eq(metric)];axs[1,0].plot(a.k,a['mean'],color=col,label=label,lw=1.8)
   axs[1,0].set(title='Layout diversity across teams',ylabel='Pairwise geometric difference',ylim=(0,None));axs[1,0].legend(fontsize=8)
   axs[1,1].plot(s.k,s.complete_evaluable_rate,c='#21896e',lw=2);axs[1,1].set(title='Complete and evaluable output',ylabel='Fraction of all paths',ylim=(-.02,1.04))
   for ax in axs.ravel():ax.set_xlabel('Annotators (k)');ax.grid(alpha=.15);ax.axvspan(.8*r.N,r.N,color='#8d9aa4',alpha=.07);ax.set_xlim(3,max(4,r.N))
   for ax,met in [(axs[0,0],'B8L2_mean'),(axs[0,1],'B8L2_sd'),(axs[1,1],'complete_evaluable_rate')]:
    if met in op.index and np.isfinite(op.loc[met,'onset_k']):ax.axvline(op.loc[met,'onset_k'],color='#5d6972',ls='--',lw=.9)
   full=s[s.k.eq(r.N)];fulltxt='Full Q unavailable' if full.empty or not np.isfinite(full.B8L2_mean.iloc[0]) else f'Full B8L2={full.B8L2_mean.iloc[0]:.2f}'
   onset=op.loc['B8L2_mean','onset_k'];ost='not identified' if not np.isfinite(onset) else str(int(onset))
   fig.suptitle(f'{r.image} | {r.difficulty_en} | N={r.N} | {fulltxt}',fontsize=15)
   fig.supxlabel(f'Mean-Q small-change onset: {ost}. Dashed lines mark metric-specific retrospective onsets.\n256 nested paths; repeated teams retain frequency. Shaded k/N >= 0.8; full-pool dispersion is mechanically zero when evaluable.',fontsize=8.6)
   name=f'Manual_{r.image}.png';fig.savefig(imgdir/name,dpi=120,facecolor='white');pdf.savefig(fig);plt.close(fig);index.append(dict(image=r.image,domain='ordinary_manual_main',N=r.N,difficulty=r.difficulty_en,file='per_image/'+name))
 with PdfPages(OUT/'Doorway_17_Image_Atlas.pdf') as pdf:
  for image,g in dc.groupby('image'):
   fig,axs=plt.subplots(2,2,figsize=(11.7,7.8),layout='constrained')
   for dom in DC:
    s=g[g.domain.eq(dom)&g.k.ge(3)];n=int(g[g.domain.eq(dom)].N.iloc[0]) if len(g[g.domain.eq(dom)]) else 0
    if s.empty:continue
    label=f'{DL[dom]} (N={n})'
    for ax,col in [(axs[0,0],'B8L2_mean'),(axs[0,1],'B8L2_sd'),(axs[1,1],'complete_evaluable_rate')]:ax.plot(s.k,s[col],lw=1.8,c=DC[dom],label=label)
    z=dg[dg.image.eq(image)&dg.domain.eq(dom)&dg.kind.eq('same_k_U')&dg.metric.eq('floor_distance')];axs[1,0].plot(z.k_from,z['mean'],lw=1.8,c=DC[dom],label=label)
   for ax,title,ylabel in [(axs[0,0],'Conditional mean quality','Mean B8L2'),(axs[0,1],'Member-combination variability','B8L2 SD'),(axs[1,0],'Layout diversity across teams','Mean pairwise 1-IoU'),(axs[1,1],'Complete and evaluable output','Fraction of all paths')]:
    ax.set(title=title,xlabel='Annotators (k)',ylabel=ylabel);ax.grid(alpha=.15);ax.axvline(14,c='#8a979d',ls=':',lw=1)
   axs[0,0].set_ylim(0,100);axs[1,1].set_ylim(-.02,1.04);axs[0,0].legend(fontsize=7.5,loc='best');fig.suptitle(f'{image} | Doorway: frozen 584 / 439 release',fontsize=15)
   fig.supxlabel('Each target has its own compatible members and reference. Lines end at actual capacity.\nVertical dotted line: k=14 is the before/after common limit across all 17 images; side pools have much lower support.',fontsize=8.6)
   name=f'Doorway_{image}.png';fig.savefig(imgdir/name,dpi=120,facecolor='white');pdf.savefig(fig);plt.close(fig);index.append(dict(image=image,domain='doorway',N=int(g.N.max()),difficulty='Doorway',file='per_image/'+name))
 pd.DataFrame(index).to_csv(OUT/'IMAGE_ATLAS_INDEX.csv',index=False)
 cards=''.join(f'<article data-search="{html.escape(x["image"]+" "+x["difficulty"]+" "+x["domain"])}"><h2>{html.escape(x["image"])} · {html.escape(x["difficulty"])} · N={x["N"]}</h2><img loading="lazy" src="{x["file"]}" alt="Image-specific response curves"></article>' for x in index)
 text='''<!doctype html><html lang="zh"><meta charset="utf-8"><title>HOHONET 逐图人数响应图册</title><style>body{font-family:system-ui,sans-serif;max-width:1200px;margin:30px auto;padding:0 20px;color:#233343;background:#f6f8fa}h1{font-size:30px}p{line-height:1.7}input{padding:12px;width:95%;font-size:18px;position:sticky;top:0;background:white;border:1px solid #acbac6;border-radius:5px}article{background:white;margin:24px 0;padding:15px;box-shadow:0 1px 6px #0001}img{width:100%}h2{font-size:20px}</style><h1>HOHONET v2.1 逐图人数响应图册</h1><p>普通 Manual 206 图与门洞 17 图独立展示。输入图名、Easy、Medium、Hard 或 doorway 筛选。灰色后段为 k/N ≥ 0.8；满员只有一支队，波动归零不表示准确。Q 缺失保留空白，不填零。起点虚线按该指标的全剩余区间规则定义。</p><input id="search" placeholder="输入图片名或条件，例如 VFua、pa4、Hard、doorway">'''+cards+'''<script>document.querySelector('#search').oninput=e=>{let q=e.target.value.toLowerCase();document.querySelectorAll('article').forEach(a=>a.hidden=!a.dataset.search.toLowerCase().includes(q))}</script></html>'''
 (OUT/'IMAGE_ATLAS_ZH.html').write_text(text,encoding='utf8')

if __name__=='__main__':
 args=read();make_overviews(*args);atlas(args[0],args[1],args[2],args[3],args[5],args[6]);print('Figures and 223 image pages complete.')
