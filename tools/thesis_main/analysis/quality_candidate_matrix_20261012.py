"""汇总既有候选的审核约束与控制代价；不搜索参数、不生成新评级。"""
from pathlib import Path
import argparse

if __package__:
    from .quality_joint_response_20261012 import terms,read_json,save_json
else:
    from quality_joint_response_20261012 import terms,read_json,save_json


def build(study):
    previous=read_json(study/'results.json')
    audit=read_json(study.parent/'quality_review_constraints_20261012/audit.json')
    evidence=read_json(study.parent/'quality_review_constraints_20261012/evidence.json')
    joint=read_json(study/'joint_response.json')
    real=read_json(study/'decision_check.json')
    configs={c['name']:dict(kind='response',config=c) for c in read_json(study/'protocol.json')['candidates']}
    for c in evidence['configs']+audit['probe_definitions']['configs']:
        if c['name'] in ('Q_dbounded1_max_height','Q_dbounded1_max_top') or c['name'].startswith('probe_'):
            configs[c['name']]=dict(kind='legacy',config=c)
    rows=[]
    for name,c in configs.items():
        pairs={}
        for panel in previous['overall_pairs']:
            if c['kind']=='response':
                pair=panel['scores'][name];a,b=pair['a'],pair['b']
            else:
                panel_old=next(p for p in audit['overall_pairs'] if p['panel']==panel['panel'])
                pair=next(p for p in panel_old['scores'] if p['candidate']==name);a,b=pair['score_a'],pair['score_b']
            pairs[panel['panel']]=dict(a=a,b=b,difference=a-b,
                direction_agrees=a>b if panel['panel'] in ('P01','C03') else None,numeric_tolerance=None)
        if c['kind']=='response':
            a,b=[previous['reviewed_terms'][rid][name]['top_only_penalty'] for rid in ('R00397','R00418')]
        else:
            p=next(p for p in audit['P04'] if p['candidate']==name)
            a,b=p['T20']['top_only_penalty'],p['S034']['top_only_penalty']
        controls=[]
        for ratio,local in ((.8,0),(.5,0),(2,0),(1,.1)):
            control=next(x for x in joint['controls'] if x['ratio']==ratio and x['local']==local and x['scale']==2)
            assert control['status']=='available'
            controls.append(dict(id=control['id'],ratio=ratio,local=local,score=terms(control['metrics'],c)['score'],human_grade=None))
        mono=joint['monotonicity'].get(name)
        rows.append(dict(name=name,config=c,pairs=pairs,
            P04=dict(T20_penalty=a,S034_penalty=b,direction_agrees=b>a,scope='top_only_not_overall'),
            fixed_controls=controls,
            grid_control={k:mono[k] for k in ('compared','increases','unchanged','decreases')} if mono else None,
            real_reference_control=real['summary'].get(name)))
    coverage={}
    for name,subset in [('all',previous['development']),('confirmed',[r for r in previous['development'] if r['applicability_confirmed']])]:
        differences=[r['scores']['relative4']-r['scores']['relative2_mean1'] for r in subset]
        coverage[name]=dict(records=len(subset),quartic_lower_score_than_mean1=sum(x < -1e-8 for x in differences),
                            minimum_score_difference=min(differences),maximum_score_difference=max(differences))
    p01=[]
    for rid in ('R02015','R00637'):
        m=next(r['metrics'] for r in evidence['tables']['real39'] if r['id']==rid)
        p01.append(dict(id=rid,original=terms(m,configs['relative2'])['score'],
                        direction_zero=terms(dict(m,dir=0),configs['relative2'])['score']))
    return dict(schema='quality_candidate_matrix_v1',candidates=rows,quartic_vs_mean1=coverage,P01_direction_ablation=p01,
        sources=['results.json','../quality_review_constraints_20261012/audit.json','joint_response.json','decision_check.json','human_review_feedback.json'],
        human_review=read_json(study/'human_review_feedback.json'),formal_score_changed=False,
        scope='13既有候选，四条已有域内控制；未调参，未重算几何。方向相符不等于效度，未知不能计通过，原始输入质量不能由本表认证。')


def render(result):
    lines=['# 既有候选的约束与代价表','',
        '由已保存结果直接汇总，未增加参数搜索或人工标签。当前推进解释见[收敛建议](CANDIDATE_DIRECTION.md)。',
        'P04列为T20 / S034顶部单独处罚百分比；P01、C01—C04列为A减B的总分。P01、C03有方向，其余只显示分差，不设通过线。',
        '控制沿用相同底面、参考墙高2.4、水平尺度2：均高比0.8、0.5、2及均高正确/局部RMS10%；均在相机域内。控制分数不附人工严重等级。',
        '', '|候选|P01差|C01差|C02差|C03差|C04差|P04处罚%|P04方向|均高0.8|均高0.5|均高2|局部10%|真实参考增分/30|',
        '|---|---:|---:|---:|---:|---:|---|---|---:|---:|---:|---:|---|']
    for r in result['candidates']:
        p=r['P04'];ref=r['real_reference_control']
        cells=[r['name']]+[f"{r['pairs'][x]['difference']:.2f}" for x in ('P01','C01','C02','C03','C04')]
        cells += [f"{100*p['T20_penalty']:.2f} / {100*p['S034_penalty']:.2f}",'相符' if p['direction_agrees'] else '相反']
        cells += [f"{x['score']:.2f}" for x in r['fixed_controls']]+[str(ref['increases']) if ref else '未测']
        lines.append('|'+ '|'.join(cells)+'|')
    lines+=['','真实参考控制只有30/64条域内可比，不是人员误排率；两个局部加强探针未进入该实验，不能把未测写成0。',
        'V01/V02人工原话与分层解释见[回执](human_review_feedback.json)：V02底面B、二维顶部A；三维高度未评。不转成上述总分的训练标签。',
        '复算：`python -B tools/thesis_main/analysis/quality_candidate_matrix_20261012.py`。数值机器表见[candidate_matrix.json](candidate_matrix.json)。']
    return '\n'.join(lines)+'\n'


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--study',type=Path,default=Path('research/quality_top_height_response_20261012'))
    study=p.parse_args().study
    result=build(study)
    save_json(study/'candidate_matrix.json',result)
    (study/'CANDIDATE_MATRIX.md').write_text(render(result),encoding='utf-8')
    print('13 existing candidates; no parameter search or geometry recomputation')
