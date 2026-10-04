"""Apply exact arc consensus to an explicitly selected current roster, no GT.
Input: {image, condition, evidence_kind, records}. Do not include references.
No eligibility selection, reordering, imputation or source mutation occurs here.
"""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT/'src'))
from arc_consensus import fuse
from simplify import compress

def main():
    p=argparse.ArgumentParser(__doc__);p.add_argument('--input',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--epsilon',type=float,default=None);a=p.parse_args()
    if a.out.exists():raise ValueError('use_new_output_file')
    d=json.loads(a.input.read_text());rs=d['records']
    for r in rs:
        for key in ('image','condition','evidence_kind'):
            if key not in r:r[key]=d[key]
            elif key in d and r[key]!=d[key]:raise ValueError('panel_record_metadata_conflict:'+key)
    o=fuse(rs)
    if a.epsilon is not None and o['status']=='ok_conditional_representation':
        o['compression']=compress(o['methods'][o['bev_mv50_complete_method']],a.epsilon)
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(o,ensure_ascii=False,indent=2,allow_nan=False))
if __name__=='__main__':main()
