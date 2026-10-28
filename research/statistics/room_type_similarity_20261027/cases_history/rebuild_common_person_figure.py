#!/usr/bin/env python3
"""Re-export the small common-person chart from saved CSV only; no analysis rerun."""
from pathlib import Path
import os,hashlib,json
os.environ.setdefault('MPLCONFIGDIR','/tmp/room_type_case_mpl')
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image

def main():
    out=Path(__file__).resolve().parent
    src=out/'CASE_COMMON_PERSON_COMPARISONS.csv';p=pd.read_csv(src)
    fig,axs=plt.subplots(1,2,figsize=(12,5))
    for ax,(pid,g) in zip(axs,p.groupby('pair_id',sort=False)):
        v=g.groupby(['annotation_turn5_left','annotation_turn5_right']).size().reset_index(name='people')
        ax.scatter(v.annotation_turn5_left,v.annotation_turn5_right,s=[max(100,int(n)*35) for n in v.people],c='#23577c',alpha=.75)
        for _,r in v.iterrows():
            ax.annotate(str(int(r.people)),(r.annotation_turn5_left,r.annotation_turn5_right),ha='center',va='center',color='white',fontsize=11)
        ax.plot([3.7,6.3],[3.7,6.3],ls='--',c='gray')
        ax.set(xlim=(3.7,6.3),ylim=(3.7,6.3),xticks=[4,5,6],yticks=[4,5,6],xlabel=g.image_code_left.iloc[0]+' turns',ylabel=g.image_code_right.iloc[0]+' turns',title=f'Common people: {len(g)}; fewer turns on right: {(g.turn_change<0).sum()}')
        ax.grid(alpha=.2)
    fig.suptitle('Same-person expression: common-person panels, not independent pair samples',fontsize=13);fig.tight_layout()
    target=out/'C02_COMMON_PERSON_TURNS.png';temporary=out/'C02_COMMON_PERSON_TURNS.tmp.png'
    fig.savefig(temporary,dpi=150);plt.close(fig)
    with Image.open(temporary) as im:im.load();size=im.size
    assert temporary.stat().st_size>10000;temporary.replace(target)
    r={'operation':'Re-export saved common-person CSV; no new scores, fusion, classification, or comparisons','source':src.name,'source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'records':len(p),'images':3,'pairs':2,'output':target.name,'bytes':target.stat().st_size,'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'decoded_pixels':list(size),'actual_decode_success':True}
    (out/'C02_EXPORT_RECEIPT.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print(json.dumps(r))
if __name__=='__main__':main()
