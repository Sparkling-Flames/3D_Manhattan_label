"""Added exploratory sparse feedback baselines after the broad run.
Keeps the primary65 registry runs; additional hypotheses are versioned here.
No outer target selects feature membership or replaces a failed baseline.
"""
import json
import numpy as np
from tools.thesis_main.analysis.image_portrait.pro_core import OUT,write_json

def register():
    root=OUT/'features';reg=json.loads((root/'registry.json').read_text());r=reg['B_feedback'];z=np.load(root/r['file']);cols=r['columns'];X=z['X'];names={
    'BX_counts_only':[c for c in cols if c.endswith('point_count_mean')],
    'BX_rotation_only':[c for c in cols if c.endswith('rotation_dmask')],
    'BX_disagreement_only':[c for c in cols if c.startswith('three_architecture_disagreement')],
    'BX_Bi_policy_only':['bi_heads_boundary_difference','bi_heads_point_count_disagreement','bi_raw_head_height_difference']}
    for name,cs in names.items():
        np.savez_compressed(root/(name+'.npz'),image_ids=z['image_ids'],X=X[:,[cols.index(c)for c in cs]])
        reg[name]=dict(file=name+'.npz',dimensions=len(cs),family='B_late_exploratory_sparse',model='',layer='',pool='',prespecified=False,columns=cs,exact_duplicate_of=None,reason='Separate structural complexity, rotation instability, cross-model discrepancy and policy response; added after initial65 fits')
    write_json(root/'registry.json',reg)
if __name__=='__main__':register()
