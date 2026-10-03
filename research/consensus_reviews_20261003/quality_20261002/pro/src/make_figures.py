"""Each plot is separate; default matplotlib colors; no chart style override."""
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
BASE=Path(__file__).resolve().parents[1]
def main():
    out=BASE/'figures';out.mkdir(exist_ok=True)
    names=[]
    def save(fig,name):
        fig.tight_layout();fig.savefig(out/(name+'.png'),dpi=170,bbox_inches='tight');fig.savefig(out/(name+'.svg'),bbox_inches='tight')
        plt.close(fig);names.append(name+'.png')
    d=pd.read_csv(BASE/'results/collinear_density.csv')
    fig,ax=plt.subplots(figsize=(8.8,4.9))
    ax.plot(d.inserted_points,d.current_model_volume_iou,'o-',label='CURRENT: perimeter-mean height proxy')
    ax.plot(d.inserted_points,d.vertex_ls_volume_iou,'s--',label='EXPLORATORY: equally weighted vertex angular fit')
    ax.set(xlabel='Extra collinear point pairs on the same physical edge',ylabel='Volume-proxy IoU between identical wall surfaces',ylim=(.65,1.025),
           title='The current implementation preserves collinear-subdivision equivalence\nThe alternative vertex-fitting rule does not')
    ax.legend(loc='lower left');save(fig,'01_subdivision_current_vs_alternative')
    fig,ax=plt.subplots(figsize=(8.8,4.8));x=np.linspace(-2,2,201)
    ax.plot(x,3+.5*x,label='Ceiling A: H=3+0.5X');ax.plot(x,3-.5*x,label='Ceiling B: H=3-0.5X')
    ax.set(xlabel='X / common camera height',ylabel='Height above floor / common camera height',
           title='Equal mean height and RMS do not locate the height difference\nCurrent flat-top proxy IoU = 1; exact synthetic volume IoU = 0.7143')
    ax.legend();save(fig,'02_opposite_roofs')
    d=pd.read_csv(BASE/'results/real_selected_metrics.csv');d=d[d.column_status=='ok'].sort_values('bev_iou')
    xx=np.arange(len(d));fig,ax=plt.subplots(figsize=(9,5))
    ax.plot(xx,d.bev_iou,'o-',label='BEV IoU')
    ax.plot(xx,d.current_model_volume_iou,'s-',label='Current perimeter-height volume proxy')
    ax.plot(xx,d.column_iou,'^-',label='Declared column-band IoU')
    ax.set_xticks(xx,d.annotation);ax.set(ylabel='Agreement with R02503',xlabel='Annotation IDs, ordered only by BEV IoU',
        title='One image: changing the metric can change the order\nThese are response comparisons, NOT worker-quality rankings')
    ax.legend();save(fig,'03_real_metric_order')
    return names
if __name__=='__main__':print(main())
