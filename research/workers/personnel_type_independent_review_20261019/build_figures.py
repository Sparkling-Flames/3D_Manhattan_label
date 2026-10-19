from pathlib import Path
import json,hashlib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
P=Path(__file__).resolve().parent
m=json.loads((P/'independent/independent_metrics.json').read_text());o=json.loads((P/'independent/independent_origin_contrast.json').read_text());d=json.loads((P/'independent/SCIENTIFIC_DIAGNOSTICS.json').read_text())
a=[x for x in m['brier'] if x['method']=='reverse_selected' and x['reference']=='old_QT']
rows=[next(x for x in a if x['stratum']==s) for s in ['all','common','Q_near']]+[o['origin_control_k16']]
labels=['vs old QT: all events (4,080)','vs old QT: common known (3,990)','vs old QT: Q-near common (1,290)','vs cohort-aware baseline (4,080)']
fig,ax=plt.subplots(figsize=(10,4.7));ys=list(range(4))[::-1]
for y,r in zip(ys,rows):
 v=r['building_mean'];lo,hi=r['ci'];ax.errorbar(v,y,xerr=[[v-lo],[hi-v]],fmt='o',color='#155f80',capsize=5)
ax.axvline(0,color='#9b4545',linestyle='--');ax.set_yticks(ys,labels);ax.set_xlabel('Reference Brier loss minus main-reverse Brier loss (positive favors reverse)');ax.set_title('Independent reaggregation: new-background k=16 predictive gain',loc='left');ax.grid(axis='x',alpha=.2);ax.set_ylim(-.6,3.6)
fig.text(.02,.015,'22 buildings; 2,000 fixed-output building bootstrap replicates. Different controls/support; not an interchangeability test.',fontsize=9);fig.tight_layout(rect=[0,.07,1,1]);fig.savefig(P/'figures/independent_brier_controls.png',dpi=180);fig.savefig(P/'figures/independent_brier_controls.svg');plt.close(fig)
cal=d['calibration_direction'];names=['old_QT','forward_selected','reverse_selected','reverse_selected_swap'];counts=[cal[x]['negative_cells'] for x in names]
fig,ax=plt.subplots(figsize=(8.3,4.5));bars=ax.bar(['Old QT','Forward','Geometry reverse','Replacement reverse'],counts,color=['#8c9ba4','#4794ad','#b75e42','#6d8f56']);ax.bar_label(bars,labels=[f'{n}/264' for n in counts],padding=3);ax.set_ylim(0,80);ax.set_ylabel('Calibration cells with within probability < between');ax.set_title('Better probability prediction need not mean safer within-class swaps',fontsize=12);fig.text(.02,.015,'22 overlapping folds × 4 k values × 3 difficulties. Descriptive cells, not 264 independent trials.',fontsize=9);fig.tight_layout(rect=[0,.06,1,1]);fig.savefig(P/'figures/independent_calibration_direction.png',dpi=180);fig.savefig(P/'figures/independent_calibration_direction.svg');plt.close(fig)
files=['independent/independent_metrics.json','independent/independent_origin_contrast.json','independent/SCIENTIFIC_DIAGNOSTICS.json']
(P/'figures/INDEPENDENT_FIGURE_PROVENANCE.json').write_text(json.dumps({'inputs':{s:hashlib.sha256((P/s).read_bytes()).hexdigest() for s in files},'builder':'build_figures.py','figures':['independent_brier_controls','independent_calibration_direction'],'note':'Generated from independently recomputed saved receipts; no newly fitted model.'},indent=2)+'\n')
