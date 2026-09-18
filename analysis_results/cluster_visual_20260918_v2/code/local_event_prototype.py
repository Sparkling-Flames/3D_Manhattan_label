"""Image-anchored descriptive event signatures on five development images.
ROIs are analyst-defined AFTER reading review comments and viewing images; not independent gold.
No worker identity, old cluster ID, normative accept/reject or quality score enters the rules.
This is not a general semantic detector and does not replace full annotations.
"""
import json,itertools
from pathlib import Path
from collections import Counter
import numpy as np,pandas as pd
import clustering_study as st
import legacy_reproduction as old
R=Path(__file__).resolve().parents[1]
RULES={
'B6ByNegPMKs-11':{'events':['right_closure_band','column_pair_count'],'boxes':[[430,505]],'meaning':'右开口近/远端的坐标带候选，与中部柱体的额外表达分开。宽度145—170为不确定带，不当语义真值。'},
'X7HyMhZNoso-19':{'events':['front_level_pairs','rear_level_pairs'],'boxes':[[440,540]],'meaning':'中央隔断局部；前缘高度带及后接缝高度带的角点对数。不是质量评级。'},
'rPc6DW4iMge-15':{'events':['closet_left_frame','closet_right_frame'],'boxes':[[625,665],[900,950]],'meaning':'同一大致卧室范围内的柜体边框表达机会。'},
'rPc6DW4iMge-20':{'events':['bath_left_frame','bath_right_frame','left_opening_extra','right_corridor_corner'],'boxes':[[365,430],[600,660],[60,125],[785,850]],'meaning':'浴室框、左侧开口和右走廊角分别记录；相同总点数不能替代此联合签名。'},
'wc2JMjhGNzB-67':{'events':['bath_right_frame','right_room_corner'],'boxes':[[315,370],[865,950]],'meaning':'浴室门框额外表达与右侧主墙角缺失同时保留。'}
}

def signature(code,e,pad=0):
    if code not in RULES:return None
    x=e[:,0];spec=RULES[code]
    def count(lo,hi):return int(((x>=lo-pad)&(x<=hi+pad)).sum())
    if code=='B6ByNegPMKs-11':
        q=e[(x>=620-pad)&(x<=910+pad)]
        width=float(np.ptp(q[:,0]))if len(q)==2 else None
        band='uncertain' if width is None else ('near' if width>170+pad else('far'if width<145-pad else'uncertain'))
        return (band,count(430,505))
    if code=='X7HyMhZNoso-19':
        q=e[(x>=440-pad)&(x<=540+pad)]
        front=(q[:,1]<160+pad)&(q[:,2]>400-pad)
        rear=(q[:,1]>=170-pad)&(q[:,2]<395+pad)
        if ((front&rear)|(~front&~rear)).any():return ('uncertain','uncertain')
        return(int(front.sum()),int(rear.sum()))
    return tuple(count(lo,hi)for lo,hi in spec['boxes'])

def run():
    d=json.loads((R/'inputs/key39/data.json').read_text());ns,rec,cov=st.prep(d);rows=[];sens=[];summary=[]
    for c in d['cases']:
        if c['code']not in RULES:continue
        for g in c['groups']:
            sigs=[]
            for cid in g['canonical_ids']:
                r=rec[cid];s=signature(c['code'],r['events']);sigs.append(s)
                ss=[signature(c['code'],r['events'],p)for p in [-8,0,8]]
                sens.append(dict(code=c['code'],condition=g['condition'],id=cid,worker=r['worker_id'],signature=json.dumps(s),changed_under_ROI_pad8=any(s2!=s for s2 in ss),contracted=json.dumps(ss[0]),expanded=json.dumps(ss[2])))
                rows.append(dict(code=c['code'],condition=g['condition'],id=cid,worker=r['worker_id'],signature=json.dumps(s),**{name:val for name,val in zip(RULES[c['code']]['events'],s)}))
            co=Counter(sigs)
            for s,n in co.items():summary.append(dict(code=c['code'],condition=g['condition'],signature=json.dumps(s),n=n,workers=';'.join(rec[cid]['worker_id']for cid,ss in zip(g['canonical_ids'],sigs)if ss==s)))
    pd.DataFrame(rows).to_csv(R/'results/local_event_records.csv',index=False)
    pd.DataFrame(summary).to_csv(R/'results/local_event_patterns.csv',index=False)
    pd.DataFrame(sens).to_csv(R/'results/local_event_ROI_sensitivity.csv',index=False)
    old.save_json(R/'results/local_event_rules.json',RULES)
    print(pd.DataFrame(summary).to_string(index=False));print('sensitivity',len(sens),sum(x['changed_under_ROI_pad8']for x in sens))
    # Named development relations: descriptions, not semantic truth labels or accuracy evaluation.
    rel=[
      ('jtcxE69GiFV-05','manual','W015','W012','same_range_expression_localization_diff','墙角对应相近；首个及左侧底点差异，不是两个房间'),
      ('B6ByNegPMKs-11','manual','W002','W006','different_right_closure','近端门框和门内较远位置'),
      ('B6ByNegPMKs-11','manual','W002','W034','same_right_closure_extra_column','范围相近，但W034额外表达柱体'),
      ('B6ByNegPMKs-21','semi','W001','W032','same_range_extra_center_pair','W001中央门状区域多一对；未评论不等于没差异'),
      ('X7HyMhZNoso-19','manual','W033','W034','full_vs_omitted_partition','隔断前缘及连接均表达，对比全部省略'),
      ('X7HyMhZNoso-19','manual','W033','W037','full_vs_partial_partition','有后连接高度，缺前缘高度'),
      ('X7HyMhZNoso-19','manual','W034','W037','omitted_vs_partial_partition','零局部对和两局部对'),
      ('X7HyMhZNoso-19','manual','W011','W015','same_expressed_partition_localization_diff','均有前缘及后缘；W015有后缘横坐标偏移'),
      ('e9zR4mvMWw7-10','semi','W035','W006','same_range_expression_localization_diff','没有新增房间证据，主要顶点高度'),
      ('e9zR4mvMWw7-32','semi','W031','W002','same_range_expression_localization_diff','同样四个位置机会，顶底坐标不同'),
      ('e9zR4mvMWw7-16','semi','W032','W006','different_local_floor_boundary','W032第三底点明显降到楼梯下方，不能因同点数隐藏'),
      ('q9vSo1VnCiC-32','manual','W014','W027','large_local_misplacement','第二、三对横坐标偏離相应墙角；粗范围相近'),
      ('q9vSo1VnCiC-32','manual','W006','W027','different_seam_range_and_expression','W006进入接缝小空间并有额外表达'),
      ('rPc6DW4iMge-15','manual','W002','W011','same_range_expression_localization_diff','同样四对，大致范围相同'),
      ('rPc6DW4iMge-15','manual','W002','W037','same_range_extra_closet_frame','额外柜框位置，非另一卧室'),
      ('rPc6DW4iMge-20','manual','W034','W037','same_count_different_local_event_set','均六对，但左开口/右走廊角不同，同时有框'),
      ('rPc6DW4iMge-20','manual','W006','W037','same_range_extra_bath_frame','四个基础角对比加浴室框'),
      ('uNb9QFRL6hY-40','manual','W006','W032','different_seam_expression','接缝拥挤墙角的表达数量不同'),
      ('uNb9QFRL6hY-45','manual','W006','W011','different_right_turn_expression','右侧转折表达有区别'),
      ('uNb9QFRL6hY-63','manual','W011','W035','different_left_closure','近端开口与开口后较远端'),
      ('uNb9QFRL6hY-63','manual','W011','W032','different_right_top_boundary_mixed','W032顶点更低、底点接近；不自动称完整向后范围'),
      ('uNb9QFRL6hY-70','manual','W031','W035','extra_visible_extension','W035增加右侧门后局部对'),
      ('wc2JMjhGNzB-30','manual','W002','W034','full_vs_omitted_right_returns','右侧多次转折表达与省略'),
      ('wc2JMjhGNzB-59','manual','W030','W027','same_range_expression_localization_diff','相同四对；边界位置不同'),
      ('wc2JMjhGNzB-59','manual','W027','W032','extra_through_glass_pair','W032在开口内新增一对'),
      ('wc2JMjhGNzB-60','manual','W001','W027','local_position_and_boundary_site_change','W001角点落到柜前缘附近；混合局部偏移，非已证明另一空间'),
      ('wc2JMjhGNzB-67','manual','W002','W034','missing_right_corner','W034少右侧主角，不应用未确认修复'),
      ('wc2JMjhGNzB-67','manual','W002','W037','extra_bath_frame','W037增加门框右侧一对'),
      ('yqstnuAEVhm-34','manual','W006','W012','different_local_closure_boundary','右侧近端与略远边界；不是已证实整个别的房间')]
    mem=pd.read_csv(R/'results/memberships.csv');sm=pd.read_csv(R/'results/spherical_memberships.csv');er=pd.DataFrame(rows);checks=[]
    for code,cond,a,b,relation,note in rel:
        item=dict(code=code,condition=cond,worker_a=a,worker_b=b,relation=relation,visual_note=note,review_status='analyst_development_relation_not_blind_gold')
        m=mem[(mem.code==code)&(mem.condition==cond)]
        for method in st.METHODS:
            s=m[m.method==method];aa=s[s.worker==a];bb=s[s.worker==b]
            item[method]=bool(aa.iloc[0].cluster==bb.iloc[0].cluster)if len(aa)==len(bb)==1 else None
        for method in ['spherical','solid']:
            s=sm[(sm.code==code)&(sm.condition==cond)&(sm.method==method)&(sm.cut==.1)];aa=s[s.worker==a];bb=s[s.worker==b]
            item[method]=bool(aa.iloc[0].cluster==bb.iloc[0].cluster)if len(aa)==len(bb)==1 else None
        s=er[(er.code==code)&(er.condition==cond)];aa=s[s.worker==a];bb=s[s.worker==b]
        item['event_signature_equal']=bool(aa.iloc[0].signature==bb.iloc[0].signature)if len(aa)==len(bb)==1 else None
        checks.append(item)
    pd.DataFrame(checks).to_csv(R/'results/named_visual_relation_checks.csv',index=False)
    print(pd.DataFrame(checks).to_string(index=False))
if __name__=='__main__':run()
