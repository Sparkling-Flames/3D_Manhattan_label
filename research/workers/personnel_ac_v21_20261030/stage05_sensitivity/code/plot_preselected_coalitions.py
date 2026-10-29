"""Complete 7-team / 21-pair display for four capacity-selected images."""
from pathlib import Path
import argparse,json,hashlib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

IMAGES=['pa4otMbVnkk-06','pa4otMbVnkk-42','pa4otMbVnkk-44','pa4otMbVnkk-11']

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--results',required=True);ap.add_argument('--out',required=True)
    args=ap.parse_args();src=Path(args.results);out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    teams=pd.read_csv(src/'PRESELECTED_8_17_10_TEAMS.csv.gz');pairs=pd.read_csv(src/'PRESELECTED_8_17_10_CONTRASTS.csv.gz')
    assert len(teams)==28 and len(pairs)==84
    allq=pd.to_numeric(pairs.B8L2_CA,errors='coerce').dropna()
    qmax=max(1.,float(allq.abs().max())) if len(allq) else 1.
    qmax=np.ceil(qmax*2)/2
    fig,axes=plt.subplots(4,2,figsize=(14.4,23),layout='constrained')
    for row,im in enumerate(IMAGES):
        t=teams[teams.image.eq(im)].sort_values('n');p=pairs[pairs.image.eq(im)]
        assert len(t)==7 and len(p)==21
        index={key:i for i,key in enumerate(t.team_key)}
        labels=[c.replace('|','+')+'\n(n='+str(int(n))+')' for c,n in zip(t.alliance_classes,t.n)]
        mats=[np.full((7,7),np.nan),np.full((7,7),np.nan)]
        for r in p.to_dict('records'):
            a,c=index[r['input_A_team_key']],index[r['input_C_team_key']]
            i,j=sorted([a,c]);sign=1 if a==i else -1
            mats[0][i,j]=sign*r['B8L2_CA'] if pd.notna(r['B8L2_CA']) else np.nan
            mats[1][i,j]=r['geometry_bev_distance_AC']
        for col,(matrix,title,cmap,lo,hi) in enumerate(zip(mats,
            ['B8L2 change (column team minus row team)','Floor-shape distance (1 - IoU)'],
            ['RdBu','YlOrRd'],[-qmax,0],[qmax,1])):
            ax=axes[row,col];colors=plt.get_cmap(cmap).copy();colors.set_bad('#e9edf1')
            view=np.ma.masked_invalid(matrix);image=ax.imshow(view,cmap=colors,vmin=lo,vmax=hi)
            ax.set_xticks(range(7),labels,fontsize=8);ax.set_yticks(range(7),labels,fontsize=8)
            ax.xaxis.tick_top();ax.tick_params(length=0,pad=6)
            valid=int(np.isfinite(matrix).sum())
            ax.set_title(im+' | '+title+'\n'+str(valid)+'/21 evaluable pairs',fontsize=11,pad=40)
            for i in range(7):
                for j in range(i+1,7):
                    value=matrix[i,j]
                    if np.isfinite(value):
                        label=f'{value:+.1f}' if col==0 else f'{value:.2f}'
                        color='white' if (col==0 and abs(value)>qmax*.62) or (col==1 and value>.58) else '#17212b'
                    else:label='NA';color='#626c76'
                    ax.text(j,i,label,ha='center',va='center',fontsize=8.5,color=color)
            ax.set_xlim(-.5,6.5);ax.set_ylim(6.5,-.5)
            for spine in ax.spines.values():spine.set_visible(False)
            fig.colorbar(image,ax=ax,shrink=.72,pad=.03)
    fig.suptitle('All 7 full-class coalitions and all 21 comparisons per image\n'
       'OPPJOINT K3 | C1:17, C2:10, C3:8 | one building | no unknown-label workers\n'
       'Images selected from frozen capacity before outcomes; changes can include team-size differences.',fontsize=14)
    png=out/'ALL21_Q_AND_FLOOR_SHAPE.png';svg=out/'ALL21_Q_AND_FLOOR_SHAPE.svg'
    fig.savefig(png,dpi=180,bbox_inches='tight');fig.savefig(svg,bbox_inches='tight');plt.close(fig)
    receipt={'all_images':IMAGES,'all_teams':28,'all_pairs':84,'Q_missing_not_imputed':True,
       'direction':'upper triangle only; column minus row for signed Q, symmetric floor geometry distance',
       'Q_color_limits':[-float(qmax),float(qmax)],'floor_distance_color_limits':[0,1],
       'files':[{'path':str(f),'bytes':f.stat().st_size,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()} for f in [png,svg]]}
    (out/'VISUALIZATION_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(receipt,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
