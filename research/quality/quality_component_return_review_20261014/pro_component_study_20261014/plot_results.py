#!/usr/bin/env python3
"""Recreate the four separate study figures. Does not choose a plotting style or colors."""
from pathlib import Path
import argparse
import pandas as pd
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parent

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--results',type=Path,default=ROOT/'results')
    parser.add_argument('--output',type=Path,default=ROOT/'figures_replay')
    args=parser.parse_args()
    if args.output.exists() and any(args.output.iterdir()):
        raise SystemExit('Refusing to overwrite a nonempty figures directory')
    args.output.mkdir(parents=True,exist_ok=True)
    labels={'WQ_LS08':'WQ-LS08','arithmetic_candidate':'Arithmetic A',
            'range_anchored_A':'Range-anchored RA','raw_3d_iou':'Original 3D IoU'}
    def save(fig,name):
        fig.tight_layout();fig.savefig(args.output/name,dpi=180);plt.close(fig)
    geo=pd.read_csv(args.results/'geometry_probes.csv')
    g=geo[geo['case'].str.startswith('rhombus_')].copy()
    g['angle']=g['case'].str.split('_').str[-1].astype(float)
    fig,ax=plt.subplots(figsize=(9,5.4))
    for m,label in labels.items():ax.plot(g.angle,g[m],marker='o',label=label)
    ax.set(xlim=(92,-1),ylim=(0,105),xlabel='Acute interior angle (degrees): 90 = reference square',
           ylabel='Score / 100',title='Near-degenerate walls: an arithmetic score can rebound')
    ax.legend();ax.grid(alpha=.25);save(fig,'rhombus_response.png')
    h=pd.read_csv(args.results/'height_probes.csv')
    h=h[h.kind.eq('uniform_total_height_ratio')&h.amplitude.le(4)]
    fig,ax=plt.subplots(figsize=(9,5.4))
    for m,label in labels.items():ax.plot(h.amplitude,h[m],marker='o',label=label)
    ax.set(xlim=(.95,4.05),ylim=(0,105),xlabel='Candidate total room height / reference height',
           ylabel='Score / 100',title='A small height budget also caps the penalty for very large errors')
    ax.legend();ax.grid(alpha=.25);save(fig,'global_height_response.png')
    d=pd.read_csv(args.results/'per_case.csv');g=d[d.execution_status.eq('scored')&d.source_layer.eq('ordinary')]
    fig,ax=plt.subplots(figsize=(7,6))
    ax.scatter(g.WQ_LS08,g.arithmetic_candidate,alpha=.65,label='Arithmetic A')
    ax.scatter(g.WQ_LS08,g.range_anchored_A,marker='x',alpha=.65,label='Range-anchored RA')
    ax.plot([0,100],[0,100],linestyle='--',label='Unchanged')
    ax.set(xlim=(0,103),ylim=(0,103),xlabel='WQ-LS08',ylabel='Alternative score',
           title=f'{len(g)} recovered ordinary-layer records\nNumerical comparison; mode metadata incomplete')
    ax.legend();ax.grid(alpha=.25);save(fig,'ordinary_score_comparison.png')
    g=d[d.execution_status.eq('scored')&d.source_layer.eq('severe')].sort_values('WQ_LS08')
    fig,ax=plt.subplots(figsize=(10,5.4))
    for m,label in labels.items():ax.plot(g.record_id,g[m],marker='o',label=label)
    ax.set(ylim=(0,65),xlabel='Existing severe-exception record',ylabel='Score / 100',
           title='Nine severe-exception records: not a worker-training sample')
    ax.tick_params(axis='x',rotation=35);ax.legend();ax.grid(alpha=.25);save(fig,'severe_records.png')

if __name__=='__main__':main()
