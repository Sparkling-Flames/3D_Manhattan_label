"""Join a few saved v2 personnel contrasts to frozen quality evidence; no refit or rescore."""
import argparse
from collections import defaultdict
import csv
import gzip
import json
from pathlib import Path
from shutil import copyfile

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

from tools.thesis_main.analysis.personnel_corner_panel_20261020 import compare, project

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
AUDIT = ROOT / 'research/statistics/v2_evidence_audit_20261019/records.json.gz'
PROFILE_PAIRS = {
    'b8c07_speed_neutral': ('v2:new:102020', 'v2:new:102023'),
    'yq29_slow_detail': ('v2:new:106435', 'v2:new:106438'),
    'jh404_slow_position_loss': ('v2:new:102546', 'v2:new:102548'),
    'wc230_W122_low_tail': ('v2:new:105759', 'v2:new:105763'),
    'pa405_W126_reverse_tail': ('v2:new:103603', 'v2:new:103606'),
}
SPEED_PAIRS = {
    'zsNo09_near_score_corner_gain': ('zsNo4HB9uLZ-09', '2'),
    'x8F03_near_score_corner_loss': ('x8F5xyUWy9e-03', '2'),
    'yq05_near_score_position_loss': ('yqstnuAEVhm-05', '2'),
}
MECHANISM_CASES = ('manual_jtc26_speed_complement', 'manual_Uw22_local_dilution',
                   'manual_e9z19_lowQ_complement', 'semi_Z610_extra_node_pruning')
CASE_FIELDS = ('case_id', 'row_kind', 'condition', 'layer', 'origin', 'image', 'identity', 'label',
               'reference_id', 'reference_version', 'B8L2', 'D10', 'IoU3D100', 'iou_2d',
               'S_bottom_deg', 'dir', 'Hmean', 'Hcenter', 'nodes', 'diag_corner_recall_05',
               'diag_wall_coverage_05', 'diag_unmatched_candidate_corners', 'ref_node_recall_9',
               'ref_edge_recall_9', 'measurement_status')
PAIR_FIELDS = ('case_id', 'pair_kind', 'condition', 'origin', 'image', 'base_id', 'candidate_id',
               'base_B8L2', 'candidate_B8L2', 'delta_B8L2', 'delta_D10', 'base_nodes',
               'candidate_nodes', 'base_corner_recall_05', 'candidate_corner_recall_05',
               'delta_wall_coverage_05', 'corner_distance_status', 'bev_corner_mean_h',
               'bev_corner_max_h', 'top_corner_mean_h', 'top_corner_max_h', 'note')


def read_json(path):
    with gzip.open(path, 'rt', encoding='utf-8') if path.suffix == '.gz' else path.open(encoding='utf-8') as f:
        return json.load(f)


def read_csv(path):
    with gzip.open(path, 'rt', encoding='utf-8') if path.suffix == '.gz' else path.open(encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def write_csv(path, fields, rows):
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)


def individual_row(case_id, r):
    m = r['measurements']['same_reference_measurements']
    return dict(case_id=case_id, row_kind='individual_audit', condition=r['condition'],
                layer=r['quality_use'], origin=r['origin'], image=r['image_code'],
                identity=r['object_id'], label=r['worker_id'], reference_id=r['reference_id'],
                reference_version=r['reference_version'], B8L2=r['B8L2'], D10=r['D10'],
                IoU3D100=r['IoU3D100'], nodes=r['point_count']//2,
                measurement_status='full_audit', **{k:m[k] for k in ('iou_2d','S_bottom_deg','dir','Hmean','Hcenter')})


def team_row(case_id, p):
    s = p['score']
    row = dict(case_id=case_id, row_kind='saved_fusion_geometry', condition=s['condition'],
                layer=s['layer'], origin='mixed' if s['new_member_n'] and s['old_member_n'] else
                'new' if s['new_member_n'] else 'old', image=s['image'], identity=s['team_key'],
                label=p['label'], reference_id=s['reference_id'], reference_version=s['reference_version'],
                measurement_status=s['score_status'])
    row.update({k:s.get(k) for k in ('B8L2','D10','IoU3D100','iou_2d','S_bottom_deg','dir',
                                    'Hmean','Hcenter','nodes','diag_corner_recall_05',
                                    'diag_wall_coverage_05','diag_unmatched_candidate_corners',
                                    'ref_node_recall_9','ref_edge_recall_9')})
    return row


def pair_row(case_id, kind, a, b, distance=None, note=''):
    d = distance or {}
    return dict(case_id=case_id, pair_kind=kind, condition=a['condition'], origin=a.get('origin', ''),
                image=a['image'], base_id=a['identity'], candidate_id=b['identity'],
                base_B8L2=a['B8L2'], candidate_B8L2=b['B8L2'],
                delta_B8L2=b['B8L2']-a['B8L2'], delta_D10=b['D10']-a['D10'],
                base_nodes=a['nodes'], candidate_nodes=b['nodes'],
                base_corner_recall_05=a.get('diag_corner_recall_05'),
                candidate_corner_recall_05=b.get('diag_corner_recall_05'),
                delta_wall_coverage_05=(b['diag_wall_coverage_05']-a['diag_wall_coverage_05'])
                    if a.get('diag_wall_coverage_05') is not None and b.get('diag_wall_coverage_05') is not None else None,
                corner_distance_status=d.get('status', 'not_calculated'),
                bev_corner_mean_h=d.get('bev_mean_h'), bev_corner_max_h=d.get('bev_max_h'),
                top_corner_mean_h=d.get('top_mean_h'), top_corner_max_h=d.get('top_max_h'), note=note)


def geometry_distance(a, b):
    ga = {'geometry':{'points':a['points_1024x512']}, 'complete_evaluable':True}
    gb = {'geometry':{'points':b['points_1024x512']}, 'complete_evaluable':True}
    return compare(ga, gb)


def photo(image_id):
    for split in ('test', 'valid', 'valid_no_occ'):
        path = ROOT / 'data/mp3d_layout' / split / 'img' / (image_id+'.png')
        if path.exists(): return path
    raise FileNotFoundError(image_id)


def draw_erp(ax, row, color, label):
    points = np.asarray(row['points_1024x512'], dtype=float).reshape(-1,2,2)
    for surface, style in ((0,'-'), (1,'--')):
        pts = points[:,surface]
        for i in range(len(pts)):
            x,y = pts[i],pts[(i+1)%len(pts)]
            if abs(x[0]-y[0])<512: ax.plot([x[0],y[0]],[x[1],y[1]],style,color=color,lw=1.3,alpha=.8)
    ax.scatter(points[:,1,0],points[:,1,1],s=17,color=color,label=label)


def plot_low_tail(by_id):
    chosen = ('wc230_W122_low_tail', 'pa405_W126_reverse_tail')
    fig = plt.figure(figsize=(15,9))
    grid = fig.add_gridspec(2,3,width_ratios=(2.25,.65,1))
    for row_idx,case_id in enumerate(chosen):
        a,b = (by_id[x] for x in PROFILE_PAIRS[case_id]); ref = a['reference_evidence']
        ax,zoom,bev = [fig.add_subplot(grid[row_idx,j]) for j in range(3)]
        with Image.open(photo(a['image_id'])) as im:
            image = im.resize((1024,512))
            for axis in (ax,zoom):axis.imshow(image,extent=(0,1024,512,0))
        for source,label,color in ((ref,'GT','#333333'),(a,'W122','#0878b9'),(b,'W126','#db6428')):
            for axis in (ax,zoom):draw_erp(axis,source,color,label)
            bottom,_ = project(np.asarray(source['points_1024x512'],float))
            xy = bottom[:,[0,2]];xy = np.vstack((xy,xy[0]))
            bev.plot(xy[:,0],xy[:,1],'-o',lw=1.3,ms=2.5,color=color,label=label)
        _,matched = geometry_distance(a,b)
        worst = max(matched,key=lambda p:p['bev_h'])
        ai,bi = worst['corner_A_index'],worst['corner_other_index']
        xa,xb = a['points_1024x512'][2*ai+1][0],b['points_1024x512'][2*bi+1][0]
        lo=max(0,min(xa,xb)-45);hi=min(1024,max(xa,xb)+45)
        zoom.set(xlim=(lo,hi),ylim=(480,45),title='Largest corresponding-corner gap')
        ax.set(xlim=(0,1024),ylim=(512,0),title=f"{a['image_code']}  W122 {a['B8L2']:.1f} / W126 {b['B8L2']:.1f}")
        bev.plot(0,0,'k*',ms=8,label='camera');bev.set(aspect='equal',title='BEV / camera height',xlabel='x',ylabel='z')
        if row_idx==0:ax.legend(loc='lower right',ncol=3,fontsize=8)
        bev.grid(alpha=.2)
    fig.tight_layout();fig.savefig(OUT/'low_tail_pair_overlays.png',dpi=150);plt.close(fig)


def main(bundle):
    records = read_json(AUDIT)['records']; by_id = {r['object_id']:r for r in records}
    speed = read_csv(bundle/'claims/speed_n5_comparisons.csv.gz')
    claims = {r['team_key']:r for r in read_json(bundle/'claims/claim_teams.json.gz')}
    rows,pairs = [],[]
    for case_id,ids in PROFILE_PAIRS.items():
        a,b = (by_id[x] for x in ids)
        assert a['condition']==b['condition']=='manual' and a['reference_id']==b['reference_id']
        ra,rb = individual_row(case_id,a),individual_row(case_id,b)
        rows.extend((ra,rb))
        distance,_ = geometry_distance(a,b)
        pairs.append(pair_row(case_id,'same_image_individual',ra,rb,distance,
                              'same accepted reference; point count alone is not structure truth'))

    for name in MECHANISM_CASES:
        d = read_json(bundle/'mechanisms/cases'/f'{name}.json')
        panel_rows = [team_row(name,p) for p in d['panels']]
        rows.extend(panel_rows)
        for j in range(len(d['panels'])-1):
            sa,sb = d['panels'][j]['score'],d['panels'][j+1]['score']
            distance,_ = compare(sa,sb)
            pairs.append(pair_row(f'{name}_{j}_{j+1}','saved_fusion_path',panel_rows[j],panel_rows[j+1],distance,
                                  'matched distances only for unique cyclic same-count correspondence'))

    selected=[]
    for case_id,(image,replicate) in SPEED_PAIRS.items():
        found=[r for r in speed if r['image']==image and r['replicate']==replicate
               and r['layer']=='ordinary_manual' and r['origin']=='new' and r['domain']=='allQ'
               and r['member_stage']=='member_check' and r['n_fast']=='4' and r['contrast']=='versus_slow']
        assert len(found)==1 and found[0]['both_scored']=='True'
        s=found[0];selected.append(s)
        side=[]
        for key,label in ((s['base_team_key'],'5 slow'),(s['candidate_team_key'],'4 fast + 1 slow')):
            t=claims[key]
            side.append(dict(case_id=case_id,row_kind='saved_claim_scalar',condition=t['condition'],layer=t['layer'],
                             origin='new',image=t['image'],identity=key,label=label,reference_id=t['reference_id'],
                             reference_version=t['reference_version'],B8L2=t['B8L2'],D10=t['D10'],nodes=t['nodes'],
                             diag_corner_recall_05=t['diag_corner_recall_05'],
                             diag_wall_coverage_05=t['diag_wall_coverage_05'],
                             measurement_status='saved_scalar_no_3d_or_components'))
        rows.extend(side)
        pairs.append(pair_row(case_id,'speed_member_check',side[0],side[1],dict(status=s['corner_distance_status'],
            bev_mean_h=float(s['bev_corner_mean_h']) if s['bev_corner_mean_h'] else None,
            bev_max_h=float(s['bev_corner_max_h']) if s['bev_corner_max_h'] else None,
            top_mean_h=float(s['top_corner_mean_h']) if s['top_corner_mean_h'] else None),
            'historical Q-matched fast/slow; candidate versus five-slow on same target'))
        assert abs(float(s['quality_difference'])-pairs[-1]['delta_B8L2'])<1e-9

    shared=defaultdict(dict)
    for r in records:
        if (r['worker_id'] in ('W122','W126') and r['condition']=='manual' and not r['is_oos']
                and not r['is_doorway'] and r['quality_use']=='ordinary_primary'):
            shared[(r['image_id'],r['reference_id'])][r['worker_id']]=r
    common=[(v['W122'],v['W126']) for v in shared.values() if len(v)==2]
    assert len(common)==106
    low_tail={w:dict(mean=float(np.mean([x[i]['B8L2'] for x in common])),
                     q10=float(np.percentile([x[i]['B8L2'] for x in common],10)),
                     below_50=sum(x[i]['B8L2']<50 for x in common))
              for i,w in enumerate(('W122','W126'))}
    panel=[r for r in speed if r['layer']=='ordinary_manual' and r['origin']=='new' and r['domain']=='allQ'
           and r['n_fast']=='4' and r['contrast']=='versus_slow' and r['member_stage']=='member_check'
           and r['both_scored']=='True']
    near=[r for r in panel if abs(float(r['quality_difference']))<2]
    structural=[r for r in near if r['base_nodes']!=r['candidate_nodes']
        or (r['corner_recall_difference'] and abs(float(r['corner_recall_difference']))>=.2)
        or (r['wall_coverage_difference'] and abs(float(r['wall_coverage_difference']))>=.1)
        or (r['bev_corner_max_h'] and float(r['bev_corner_max_h'])>=.2)]
    assert len(panel)==279 and len(near)==88 and len(structural)==20
    summary=dict(source_bundle='HOHONET_personnel_research_20261020',source_audit='v2_evidence_audit_20261019',
                 low_tail_shared_images=len(common),low_tail=low_tail,
                 speed_member_check=dict(scored_pairs=len(panel),near_B8L2_2_points=len(near),
                   near_score_geometry_screen=len(structural),screen_images=len({r['image'] for r in structural}),
                   screen_buildings=len({r['building'] for r in structural}),
                   screen_gain=sum(float(r['quality_difference'])>0 for r in structural),
                   screen_loss=sum(float(r['quality_difference'])<0 for r in structural),
                   screen_definition='|delta B8L2|<2 and (vertex count changes or |delta corner recall|>=.2 or |delta wall coverage|>=.1 or maximum corresponding BEV corner distance>=.2h); exploratory diagnostic, not failure rate'),
                 selected_speed_pair_ids=[(r['base_team_key'],r['candidate_team_key']) for r in selected])
    (OUT/'SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    write_csv(OUT/'CASE_ROWS.csv',CASE_FIELDS,rows)
    write_csv(OUT/'PAIR_DIAGNOSTICS.csv',PAIR_FIELDS,pairs)

    fig,ax=plt.subplots(figsize=(7,5))
    ax.scatter([float(r['quality_difference']) for r in panel],
               [float(r['corner_recall_difference']) for r in panel],s=11,alpha=.35,color='#627d91')
    ax.axvspan(-2,2,color='#eee5cb',alpha=.55);ax.axhline(0,color='#777',lw=.7);ax.axvline(0,color='#777',lw=.7)
    for s in selected:
        ax.scatter(float(s['quality_difference']),float(s['corner_recall_difference']),s=55,color='#c34e36')
        ax.annotate(s['image'],(float(s['quality_difference']),float(s['corner_recall_difference'])),
                    xytext=(7,7),textcoords='offset points',fontsize=7)
    ax.set(xlabel='4 fast + 1 slow minus 5 slow: B8L2',ylabel='Reference corner recall difference',
           title='Ordinary new Manual, member check: 279 scored pairs')
    ax.grid(alpha=.2);fig.tight_layout();fig.savefig(OUT/'near_score_corner_changes.png',dpi=170);plt.close(fig)
    plot_low_tail(by_id)
    copyfile(bundle/'mechanisms/figures/profile_W109_W112.png',OUT/'profile_W109_W112_reused.png')


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--bundle',type=Path,required=True)
    main(parser.parse_args().bundle)
