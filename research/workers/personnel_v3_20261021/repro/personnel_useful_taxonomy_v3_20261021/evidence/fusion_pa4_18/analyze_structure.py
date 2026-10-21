#!/usr/bin/env python3
"""Explain stored vote states, with no fusion or quality-score call.

Reference node/edge assignment is the existing diagnostic, retained separately
from the fusion correspondence contract. Local group IDs are linked only through
immutable (record id, pair index) observations.
"""
import collections, importlib.util, itertools, json
import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment
import export_cases as e

HERE = e.HERE
FOCUS = {
 'V3_pa4_18_positive_n12_m4': {
  'A': [('left_jog_inner','node_011'),('return_split_low_x','node_003'),('return_split_reference_side','node_010'),('tv_side_extra','node_005')],
  'B': [('left_jog_inner','node_010'),('return_merged','node_003'),('tv_side_extra','node_005')],
  'C': [('left_jog_inner','node_010'),('return_merged','node_003'),('tv_side_extra','node_005')]},
 'V3_pa4_18_counterexample_n20_m5': {
  'A': [('left_jog_inner','node_010'),('return_split_low_x','node_003'),('return_split_reference_side','node_011'),('tv_side_extra','node_005')],
  'B': [('left_jog_inner','node_010'),('return_merged','node_003'),('tv_side_extra','node_005')],
  'C': [('left_jog_inner','node_010'),('return_merged','node_003'),('tv_side_extra','node_005')]}}

def obs(g): return {(m['id'],int(m['pair_index'])) for m in g['members']}

def main():
    fe, fr, _, _ = e.gs.setup_engine()
    mod = importlib.util.spec_from_file_location('frozen_viewer', e.ROOT/'research/workers/personnel_interchangeability_20261020/analysis/composition/case_visuals.py')
    v = importlib.util.module_from_spec(mod); mod.loader.exec_module(v)
    tables = collections.defaultdict(list); cases = []
    for path in sorted((HERE/'cases').glob('*.json.gz')):
        c = e.gs.read(path); cases.append(c); members = {m['worker_id']:m for m in c['members']}
        base = dict(case_id=c['case_id'],image=c['pool_meta']['image'])
        ref = np.asarray(c['reference']['points_1024x512'])
        for m in c['members']:
            p = np.asarray(m['points']); costs = np.maximum(fe.angular(p[::2],ref[::2]),fe.angular(p[1::2],ref[1::2]))
            rr, cc = linear_sum_assignment(costs)
            match = {int(i):int(j) for i,j in zip(rr,cc) if costs[i,j] <= 9}
            tables['RAW_REFERENCE_OPPORTUNITIES'].append(dict(base,worker_id=m['worker_id'],class_id=m['class_id'],
                raw_pair_count=len(p)//2,target_B8L2=m.get('B8L2'),
                matched_reference_nodes_9='|'.join(str(x) for x in sorted(match.values())),
                left_jog_inner_r4_matched=4 in match.values(),left_jog_return_r5_matched=5 in match.values(),
                individual_inner_min_bound_deg=float(costs[:,4].min()),individual_return_min_bound_deg=float(costs[:,5].min()),
                note='frozen paired-angle assignment diagnostic; not a semantic adjudication'))
        for t in c['teams']:
            refcheck = fr.reference_structure(t['geometry']['points'],ref)
            assert all(refcheck[k] == t[k] for k in refcheck), (c['case_id'],t['label'],'native reference diagnostic mismatch')
            glookup = {g['feature_id']:g for g in t['full_state']['identity_groups']}
            feature_index = {f:i for i,f in enumerate(t['geometry']['feature_ids'])}
            geom = v.viewer_geometry(t['geometry']['points'],t['geometry']['footprint'])
            p = np.asarray(t['geometry']['points'])
            costs = np.maximum(fe.angular(p[::2],ref[::2]),fe.angular(p[1::2],ref[1::2]))
            rr,cc = linear_sum_assignment(costs); matched = {int(i):(int(j),float(costs[i,j])) for i,j in zip(rr,cc)}
            for f,i in feature_index.items():
                j,angle = matched.get(i,(-1,np.nan))
                tables['SELECTED_CORNER_GEOMETRY'].append(dict(base,arm=t['label'],feature_id=f,n=t['k'],
                    support=glookup[f]['support'],threshold=t['minimum_support'],reference_assignment_index=j,
                    reference_assignment_bound_deg=angle,reference_assignment_within9=angle<=9,
                    top_x=p[2*i,0],top_y=p[2*i,1],bottom_x=p[2*i+1,0],bottom_y=p[2*i+1,1],
                    floor_x_h=geom['floor'][i,0],floor_z_h=geom['floor'][i,1],
                    derived_height_h=geom['ceiling_xyz'][i,1]+1))
            for g in t['full_state']['identity_groups']:
                for m in g['members']:
                    tables['GROUP_MEMBERS'].append(dict(base,arm=t['label'],feature_id=g['feature_id'],selected=g['selected'],
                        support=g['support'],threshold=t['minimum_support'],worker_id=m['worker'],class_id=members[m['worker']]['class_id'],
                        object_id=m['id'],pair_index=m['pair_index'],source_pair_index=m['source_pair_index'],
                        top_x=m['points'][0][0],top_y=m['points'][0][1],bottom_x=m['points'][1][0],bottom_y=m['points'][1][1]))
                for coordinate, ix in [('x',(0,0)),('top_y',(0,1)),('bottom_y',(1,1))]:
                    mm = sorted(g['members'],key=lambda m:(m['points'][ix[0]][ix[1]],m['worker']))
                    median = float(np.median([m['points'][ix[0]][ix[1]] for m in mm]))
                    assert abs(median-g['center'][ix[0]][ix[1]]) < 1e-8
                    central = {(len(mm)-1)//2,len(mm)//2}
                    for rank,m in enumerate(mm):
                        tables['MEDIAN_ORDER_STATISTICS'].append(dict(base,arm=t['label'],feature_id=g['feature_id'],
                            coordinate=coordinate,support=len(mm),selected=g['selected'],rank_1_based=rank+1,worker_id=m['worker'],
                            class_id=members[m['worker']]['class_id'],value=m['points'][ix[0]][ix[1]],median_value=median,
                            central_rank=rank in central,median_weight=1/len(central) if rank in central else 0))
            for role,f in FOCUS[c['case_id']][t['label']]:
                g = glookup[f]; background = set(c['event']['common_background'].split('|'))
                counts = collections.Counter(members[m['worker']]['coarse_class'] for m in g['members'])
                tables['FOCUS_GROUPS'].append(dict(base,arm=t['label'],role=role,feature_id=f,n=t['k'],support=g['support'],
                    threshold=t['minimum_support'],selected=g['selected'],M1_votes=counts['M1'],M2_votes=counts['M2'],M3_votes=counts['M3'],
                    top_x=g['center'][0][0],top_y=g['center'][0][1],bottom_y=g['center'][1][1],
                    background_votes=sum(m['worker'] in background for m in g['members']),
                    variable_block_votes=sum(m['worker'] not in background for m in g['members']),
                    background_workers='|'.join(sorted(m['worker'] for m in g['members'] if m['worker'] in background)),
                    variable_block_workers='|'.join(sorted(m['worker'] for m in g['members'] if m['worker'] not in background))))
            for edge in t['full_state']['ring_diagnostics']['edges']:
                tables['SELECTED_RING_EDGE_VOTES'].append(dict(base,arm=t['label'],node_pair='|'.join(edge['feature_ids']),
                    direct_support=edge['direct_support'],projected_support=edge['projected_support'],
                    direct_workers='|'.join(edge['direct_workers']),projected_workers='|'.join(edge['projected_workers'])))
        for a,b in itertools.combinations(c['teams'],2):
            am = {ob:g for g in a['full_state']['identity_groups'] for ob in obs(g)}
            bm = {ob:g for g in b['full_state']['identity_groups'] for ob in obs(g)}
            common = set(am)&set(bm)
            for ob in sorted(set(am)|set(bm)):
                ag,bg = am.get(ob),bm.get(ob)
                source = next(m for m in (ag or bg)['members'] if (m['id'],m['pair_index']) == ob)
                tables['OBSERVATION_ASSIGNMENT_TRANSMISSION'].append(dict(base,arm_A=a['label'],arm_B=b['label'],
                    object_id=ob[0],pair_index=ob[1],worker_id=source['worker'],
                    status='common' if ob in common else ('removed' if ag else 'incoming'),
                    A_feature_id=ag['feature_id'] if ag else '',B_feature_id=bg['feature_id'] if bg else '',
                    A_selected=ag['selected'] if ag else None,B_selected=bg['selected'] if bg else None,
                    common_groupmates_changed=(obs(ag)&common != obs(bg)&common) if ob in common else None,
                    A_common_groupmate_count=len(obs(ag)&common) if ag else 0,B_common_groupmate_count=len(obs(bg)&common) if bg else 0))
    exp = pd.read_csv(e.ROOT/'research/workers/personnel_marking_patterns_20261020/record_expression.csv')
    ids = {m['object_id'] for c in cases for m in c['members']}
    exp = exp[exp.object_id.isin(ids)]
    e.savecsv('RAW_EXPRESSION_INPUT_ROWS.csv',exp)
    for name,rows in tables.items(): e.savecsv(name+'.csv',pd.DataFrame(rows))
    v._configure_font(e.ROOT/'research/workers/personnel_composition_study_20261019/analysis/fonts/NotoSansSC-Regular.ttf')
    fg = pd.DataFrame(tables['FOCUS_GROUPS']); fig,axes = v.plt.subplots(2,3,figsize=(14.5,8))
    cases.sort(key=lambda c:'counterexample' in c['case_id'])
    for row,c in enumerate(cases):
        df = fg[fg.case_id==c['case_id']]
        for col,role in enumerate(['left_jog_inner','return','tv_side_extra']):
            ax = axes[row,col]
            z = df[df.role.str.startswith(role)]
            order = [('A','return_split_low_x'),('A','return_split_reference_side'),('B','return_merged'),('C','return_merged')] if role=='return' else [(a,role) for a in 'ABC']
            z = pd.DataFrame([z[(z.arm==arm)&(z.role==r)].iloc[0] for arm,r in order])
            xx = np.arange(len(z)); bottoms = np.zeros(len(z))
            for cl,color in [('M2','#2276a0'),('M3','#3c9265')]:
                ax.bar(xx,z[cl+'_votes'],bottom=bottoms,color=color,width=.6,label=cl)
                bottoms += z[cl+'_votes'].to_numpy()
            ax.axhline(c['teams'][0]['minimum_support'],color='#b84c3f',ls='--',lw=1.3)
            for j,r in enumerate(z.itertuples()):
                ax.text(j,r.support+.35,f'{r.support}票 / '+('保留' if r.selected else '未保留'),ha='center',fontsize=9)
            ax.set_xticks(xx, ['A组1','A组2','B','C'] if role=='return' else ['A','B','C'])
            ax.set_ylim(0,15 if row else 12);ax.grid(axis='y',alpha=.18);ax.set_axisbelow(True)
            title = ['左后墙短转折（参考角4）','返角附近：A两组在B/C合并','电视侧参考外位置（ERP x约603）'][col]
            ax.set_title(title,fontsize=11)
            if col==0: ax.set_ylabel(f'{"正例" if row==0 else "反例"} n={c["n"]}\n实际人员票数')
    fig.suptitle('同样的类别人数，并不固定每个局部位置的有效票数',x=.055,ha='left',fontsize=16)
    handles,labels=axes[0,0].get_legend_handles_labels();fig.legend(handles,labels,loc='lower center',ncol=2,bbox_to_anchor=(.5,.035),frameon=False)
    fig.text(.055,.016,'蓝为楼外M2，绿为楼外M3；红虚线为实际门槛。A的两个返角附近组须扣除离队观察后再与B/C对应，不能直接相加。',fontsize=9,color='#4f5f70')
    fig.tight_layout(rect=(.02,.085,.99,.93));(HERE/'figures').mkdir(exist_ok=True)
    fig.savefig(HERE/'figures/VOTE_TRANSMISSION.png',dpi=170,facecolor='white');v.plt.close(fig)
    e.gs.save(HERE/'STRUCTURE_ANALYSIS_CONTRACT.json',dict(no_fusion_calls=True,no_quality_score_calls=True,
        reference_diagnostics='existing fusion_runner.reference_structure output checked exactly against native 5/9 degree diagnostics; no new score',
        group_correspondence='immutable record id and pair index; numeric group labels local to each team',
        median_check='all existing group x/top_y/bottom_y checked against coordinate medians to 1e-8; no seam-crossing group',
        original_expression_rows=len(exp),focus_group_definitions=FOCUS,
        heights='frozen viewer; camera height=1, inferred from paired floor ray, not measured absolute room height'))
    print('Saved actual group votes, immutable observation changes, medians and reference diagnostics; no scoring.',flush=True)

if __name__ == '__main__': main()
