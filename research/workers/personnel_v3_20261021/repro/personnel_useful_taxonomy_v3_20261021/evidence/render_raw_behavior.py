"""Actual raw markings, outside-building labels, frozen coordinates and Release photos.
These are selected descriptive opportunities, not an independent frequency estimate.
"""
from pathlib import Path
import os,sys,json,hashlib,importlib.util
os.environ.setdefault('MPLCONFIGDIR','/tmp/hohonet_v3_mpl')
import pandas as pd
HERE=Path(__file__).resolve().parent;NEW=HERE.parent
OLD=NEW.parent/'personnel_global_composition_20261021';ROOT=NEW.parents[2]
sys.path.insert(0,str(OLD/'composition'))
import global_study as gs

SPECS=[
 dict(case_id='V3_RAW_wc2_56_SEMI',image='wc2JMjhGNzB-56',condition='semi',
      title='Semi同图三种表达：四转折、共线分段、额外短转折',
      groups=[('S1.1','常规四转折：W002 / W008',['W002','W008']),
              ('S1.2','同一粗类内：5点对仍是4个有效转折',['W010','W014']),
              ('S2.1','较多转折：8点对含3条短边',['W006','W011','W021'])],
      note='第二组两人在该图均从精确初稿删去3点对后保留1个近共线点。第三组与参考的差别涉及开口附近表达，不能单凭多点判错。'),
 dict(case_id='V3_RAW_pa4_18_MANUAL',image='pa4otMbVnkk-18',condition='manual',
      title='Manual同图结构机会：四转折简化与六转折短边',
      groups=[('M2.1','常规表达组中的简化作答',['W103','W110']),
              ('M3.1','较多转折组：六转折与一条短边',['W109','W112','W122'])],
      note='成员按这一具体可见机会事后选择。类别是历史倾向；这幅图不估计全组保留概率，第三名成员同时展示定位差异。'),
 dict(case_id='V3_RAW_jtc_28_MANUAL',image='jtcxE69GiFV-28',condition='manual',
      title='同一楼外类别内仍有保留与简化：jtc-28',
      groups=[('M2.1','较少转折作答：4—5个转折',['W103','W113']),
              ('M4.1','较多转折组：8个转折、3条短边',['W109','W126','W130']),
              ('M4.1','同类反例：W115本图仅4个转折',['W115'])],
      note='该目标楼外选型为四组，不能把M4编号与全数据三组编号直接比较。W115在历史上属于较多转折侧，但本图遗漏了同类他人表达的转折。')]

def main():
    pools=gs.pool_lookup();labs=pd.read_csv(NEW/'taxonomy/LABELS_LOBO.csv.gz',keep_default_na=False)
    behavior=pd.read_csv(NEW/'taxonomy/BEHAVIOR_RECORDS.csv.gz')
    spec=importlib.util.spec_from_file_location('existing_raw_renderer',OLD/'evidence/render_evidence.py');adapter=importlib.util.module_from_spec(spec);spec.loader.exec_module(adapter)
    spec=importlib.util.spec_from_file_location('frozen_visuals',adapter.RENDERER);v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
    font=adapter.DEFAULT_FONT
    if not font.is_file():font=Path('/tmp/HOHONET_NotoSansCJKsc-VF.ttf')
    v._configure_font(font);allrows=[];receipts=[]
    for s in SPECS:
        pool=[p for p in pools.values() if p['meta']['image']==s['image'] and p['meta']['condition']==s['condition']]
        assert len(pool)==1,(s['image'],len(pool));pool=pool[0];meta=pool['meta'];building=meta['building']
        ll=labs[labs.condition.eq(s['condition'])&labs.heldout_building.eq(building)].set_index('worker_id')
        ids=list(dict.fromkeys(w for _,_,ws in s['groups'] for w in ws));records={r['worker_id']:r for r in pool['records']}
        assert set(ids)<=records.keys()
        members=[];groups=[]
        for label,title,ws in s['groups']:
            assert all(ll.loc[w,'fine_label']==label for w in ws),(s,label,ws)
            groups.append(dict(class_id=label,label=title,workers=ws))
        for w in ids:
            r=dict(records[w]);r['class_id']=ll.loc[w,'fine_label'];members.append(r)
            bx=behavior[(behavior.worker_id==w)&(behavior.condition==s['condition'])&(behavior.image_code==s['image'])]
            assert len(bx)==1
            r0=bx.iloc[0]
            allrows.append(dict(case_id=s['case_id'],method='V3_BEHAVIOR',condition=s['condition'],image=s['image'],building=building,
                worker_id=w,object_id=r['object_id'],coarse_label=ll.loc[w,'coarse_label'],fine_label=ll.loc[w,'fine_label'],selected_family=ll.loc[w,'selected_family'],
                turn_n=r0.turn_n,short_turn_edges=r0.short_turn_edges,near_straight_nodes_5deg=r0.near_straight_nodes_5deg,
                B8L2=r.get('B8L2'),D10=r.get('D10'),history_turn=ll.loc[w,'turn_history'],history_redundancy=ll.loc[w,'redundancy_history'],
                history_images=ll.loc[w,'n_images'],history_buildings=ll.loc[w,'n_buildings'],note=s['note']))
        case=dict(s,pool_id=pool['pool_id'],image_id=meta['image_id'],reference=pool['reference'],members=members,raw_overlay_groups=groups,
            raw_overlay_title=s['title'],class_colors={g['class_id']:color for g,color in zip(groups,['#237cad','#c17d18','#347f59'])},
            selected_family=ll.loc[ids[0],'selected_family'],label_file_sha256=hashlib.sha256((NEW/'taxonomy/LABELS_LOBO.csv.gz').read_bytes()).hexdigest(),
            selection='post_result_visible_marking_opportunities_with_explicit_same_class_counterexample_not_prevalence_estimation')
        photo=HERE/'originals'/f'{meta["image_id"]}.png';assert photo.is_file()
        case['photo_sha256']=hashlib.sha256(photo.read_bytes()).hexdigest()
        out=HERE/'figures'/s['case_id'];out.mkdir(parents=True,exist_ok=True)
        gs.save(HERE/'cases'/f'{s["case_id"]}.json.gz',case)
        receipt=adapter.raw_three_views(v,case,photo,out);receipt.update(case_id=s['case_id'],actual_release_photo_sha256=case['photo_sha256'])
        receipts.append(receipt)
    pd.DataFrame(allrows).to_csv(HERE/'RAW_CASE_MEMBER_EVIDENCE.csv',index=False,encoding='utf-8-sig')
    (HERE/'RAW_FIGURE_RECEIPT.json').write_text(json.dumps(receipts,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'cases':len(receipts),'member_rows':len(allrows),'no_fusion_calls':True},ensure_ascii=False))

if __name__=='__main__':main()
