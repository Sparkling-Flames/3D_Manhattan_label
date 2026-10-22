#!/usr/bin/env python3
"""Where observed net quality changes occur; a descriptive partition, not causes.

The three node-count partitions sum to the original mean C-B Q change under
the same hierarchical weights. Equal node count does not prove equal shape or
pure positioning, so it is not mislabeled as a causal localization percentage.
"""
import pandas as pd
from register_structure import HERE, write, save, sha
from analyze_structure import BASE, hierarchy

def main():
    source=HERE/'EVENTS_COMPLETE.csv.gz';E=pd.read_csv(source,low_memory=False)
    D=E[E.study_group.isin(['main_n20','new_only_n20_recorded_time'])].copy()
    q=pd.to_numeric(D.net_B8L2,errors='coerce');ok=q.notna();nodes=pd.to_numeric(D.net_nodes,errors='coerce')
    metrics=[]
    for name,mask in [('node_count_unchanged',nodes.eq(0)),('node_count_increased',nodes.gt(0)),('node_count_decreased',nodes.lt(0))]:
        c=name+'_net_Q_partition';D[c]=(q*mask.astype(int)).where(ok);metrics.append(c)
        c=name+'_event_fraction';D[c]=mask.astype(float).where(ok);metrics.append(c)
        c=name+'_and_Q_gain_event_fraction';D[c]=(mask&q.gt(0)).astype(float).where(ok);metrics.append(c)
    for f in ['ref_node_recall_5','ref_edge_recall_5','ref_node_recall_9','ref_edge_recall_9']:
        v=pd.to_numeric(D['net_'+f],errors='coerce');c=f+'_improved_event_fraction';D[c]=v.gt(0).astype(float).where(v.notna()&ok);metrics.append(c)
    for f in ['S_bottom_deg','dir','Hmean','Hcenter','omission','extension']:
        v=pd.to_numeric(D['net_'+f],errors='coerce');c=f+'_improved_event_fraction';D[c]=v.lt(0).astype(float).where(v.notna()&ok);metrics.append(c)
    metrics.append('net_B8L2')
    P,S,I,B=hierarchy(D,metrics)
    summary=B.groupby(BASE)[metrics].mean().reset_index()
    for _,g in summary.iterrows():
        assert abs(sum(g[n+'_net_Q_partition'] for n in ['node_count_unchanged','node_count_increased','node_count_decreased'])-g.net_B8L2)<1e-8
    outputs=[write(HERE/'analysis/QUALITY_CHANGE_LOCI.csv',summary),write(HERE/'analysis/QUALITY_CHANGE_LOCI_BY_IMAGE.csv.gz',I)]
    save(HERE/'analysis/QUALITY_CHANGE_LOCI_CONTRACT.json',dict(event_sha256=sha(source),outputs=outputs,
        interpretation='Descriptive partition of the signed mean Q effect by observed node-count change. Counts sum under exactly the same support/weights; not a causal attribution. Equal count does not imply equal shape.',
        percentages='All proportions use metric-valid C-B comparisons. Structural reference recall is geometric evidence; necessary semantic detail still requires raw-image inspection.'))

if __name__=='__main__':main()
