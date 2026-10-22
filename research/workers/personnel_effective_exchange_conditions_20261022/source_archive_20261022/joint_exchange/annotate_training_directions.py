"""Separate class-center direction from the actual members' training history.

Registration and selected teams remain immutable. In the cached registration,
training_QT_direction was the actual Y/Z members' history difference. This
auxiliary annotation supplies the class-center meaning used in all final
center-direction summaries, and explicitly preserves both quantities.
"""
from __future__ import annotations
from joint_design import *

def annotations(frame):
    labs=pd.read_csv(TAX/'JOINT_LABELS_LOBO.csv.gz');cross=HERE.parent/'cross_condition_taxonomy/CROSS_LABELS_LOBO.csv.gz'
    extra=pd.read_csv(cross) if cross.exists() else pd.DataFrame()
    rows=[];lookup={}
    for (method,cond,building),g in frame.groupby(['method_id','condition','building']):
        if method=='V3_JOINT_QT':fold=labs[labs.condition.eq(cond)&labs.heldout_building.eq(building)&labs.known].copy()
        else:
            fold=extra[extra.method.eq(method)&extra.condition.eq(cond)&extra.heldout_building.eq(building)&extra.known].copy();prefix='m_' if cond=='manual' else 's_'
            for f in FEATURES:fold[f]=fold[prefix+f]
        fi=fold.set_index('worker_id');lm=fi.coarse_label.to_dict();means=fold.groupby('coarse_label')[FEATURES].mean();member_q=fi.q_history.to_dict();member_t=fi.t_history.to_dict()
        for r in g.itertuples():
            y=r.same_count_block_Y.split('|');z=r.changed_count_block_Z.split('|');a=dict(event_id=r.event_id)
            dq=float(np.mean([member_q[w] for w in z])-np.mean([member_q[w] for w in y]));dt=float(np.mean([member_t[w] for w in z])-np.mean([member_t[w] for w in y]))
            a['training_member_QT_direction']=('q_up' if dq>0 else 'q_down')+'__'+('faster' if dt<0 else 'slower');a['annotated_member_history_delta_q_history']=dq;a['annotated_member_history_delta_t_history']=dt
            for f in FEATURES:a['annotated_class_center_delta_'+f]=float(np.mean([means.loc[lm[w],f] for w in z])-np.mean([means.loc[lm[w],f] for w in y]))
            a['training_class_center_QT_direction']=('q_up' if a['annotated_class_center_delta_q_history']>0 else 'q_down')+'__'+('faster' if a['annotated_class_center_delta_t_history']<0 else 'slower');rows.append(a)
    return pd.DataFrame(rows)

def attach(d,kind,condition):
    path=HERE/f'{kind.upper()}_{condition.upper()}_TRAINING_DIRECTIONS.csv.gz'
    if path.exists():a=pd.read_csv(path);assert set(a.event_id)==set(d.event_id)
    else:a=annotations(d);write(path,a)
    out=d.merge(a,on='event_id',validate='one_to_one');out['original_registered_training_QT_direction']=out.training_QT_direction;out['training_QT_direction']=out.training_class_center_QT_direction
    return out

if __name__=='__main__':
    import argparse
    ap=argparse.ArgumentParser();ap.add_argument('kind',choices=['native','cached','cross']);ap.add_argument('condition',choices=['manual','semi']);a=ap.parse_args();d=pd.read_csv(HERE/f'{a.kind.upper()}_{a.condition.upper()}_EVENTS_COMPLETE.csv.gz',low_memory=False);attach(d,a.kind,a.condition)
