"""v2: image conditions and actual expression changes; reuse existing per-answer geometry."""
import gzip
import json
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image
from shapely.geometry import Polygon

from .scope_difficulty_review_20261011 import floor_features
from .personnel_marking_patterns_20261020 import v, plt

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'research/difficulty/difficulty_mechanisms_v2_20261020'
EVIDENCE=ROOT/'research/statistics/v2_evidence_audit_20261019/records.json.gz'
EXPRESSION=ROOT/'research/workers/personnel_marking_patterns_20261020/record_expression.csv'
TRANSFER=ROOT/'research/same_room/same_room_multiview_20261020/structure_transfer/record_features.csv.gz'


def reference_traits(floor):
    p=np.asarray(floor,float)
    if len(p)<3 or not np.isfinite(p).all() or not Polygon(p).is_valid:
        return dict(ref_geometry_status='unavailable')
    edges=np.roll(p,-1,axis=0)-p;length=np.linalg.norm(edges,axis=1)
    if np.any(length<=1e-8):return dict(ref_geometry_status='zero_length_edge')
    turn=np.degrees(np.arccos(np.clip((edges*np.roll(edges,1,axis=0)).sum(1)/(length*np.roll(length,1)),-1,1)))
    short=(length/length.sum()<.04)&(turn>=15)&(np.roll(turn,-1)>=15)
    az=np.degrees(np.arctan2(p[:,0],p[:,1]));span=np.abs((np.roll(az,-1)-az+180)%360-180)
    geometry=floor_features(p)
    return dict(ref_geometry_status=geometry['geometry_status'],ref_vertices=len(p),
        ref_turn3=int((turn>3).sum()),ref_turn5=int((turn>5).sum()),ref_turn10=int((turn>10).sum()),
        ref_H=geometry['H'],ref_short_edges=int(short.sum()),
        ref_short_min_horizontal_deg=float(span[short].min()) if short.any() else np.nan,
        ref_min_horizontal_deg=float(span.min()),ref_radius_p90_h=float(np.quantile(np.linalg.norm(p,axis=1),.9)))


def paired_conditions(f,left,right,minimum_images=2):
    x=f.groupby(['worker_id','mechanism']).agg(images=('image_code','nunique'),rate=('reduced','mean')).reset_index()
    a=x[x.mechanism.eq(left)&x.images.ge(minimum_images)].drop(columns='mechanism')
    b=x[x.mechanism.eq(right)&x.images.ge(minimum_images)].drop(columns='mechanism')
    p=a.merge(b,on='worker_id',suffixes=('_left','_right'))
    p['left']=left;p['right']=right;p['rate_delta']=p.rate_right-p.rate_left
    return p


def save(name,data):
    if isinstance(data,pd.DataFrame):data.to_csv(OUT/name,index=False,encoding='utf-8-sig')
    else:(OUT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    records=json.load(gzip.open(EVIDENCE,'rt',encoding='utf-8'))['records']
    selected=[r for r in records if r['is_oos'] is False]
    assert len({r['object_id'] for r in records})==len(records)
    by_id={r['object_id']:r for r in selected}
    d=pd.read_csv(EXPRESSION,low_memory=False)
    assert set(d.object_id)==set(by_id)
    # Reuse per-answer expression and 9/12-degree correspondence, no refit/re-score.
    transfer=pd.read_csv(TRANSFER,low_memory=False)
    extra=['object_id','corner_delta','unmatched_ref_9','unmatched_ref_12','bottom_bias_9','omission','extension','log_area_ratio']
    d=d.merge(transfer[extra],on='object_id',how='left',validate='one_to_one')
    refs={};ref_rows=[];current={}
    for r in selected:
        current[r['object_id']]=(r['image_evidence'].get('difficulty_record') or {}).get('target_version')
        ref=r['reference_evidence'] or {};tid=r['reference_id']
        if tid and tid not in refs:
            refs[tid]=ref
            if ref.get('floor_xz_h') is not None:
                ref_rows.append(dict(reference_id=tid,**reference_traits(ref['floor_xz_h'])))
    rf=pd.DataFrame(ref_rows);save('reference_conditions.csv',rf)
    d=d.merge(rf,on='reference_id',how='left',validate='many_to_one')
    d['current_target']=d.object_id.map(current)
    d['same_difficulty_target']=d.reference_id.eq(d.current_target)
    d['annotation_turn5']=d.pair_n-d.near_straight_nodes_5deg
    d['reduced']=d.annotation_turn5.lt(d.ref_turn5).astype('boolean').mask(d.ref_turn5.isna()|d.annotation_turn5.isna())
    d['mechanism']=np.where(d.ref_H.isna(),'geometry_unknown',
        np.where(d.ref_H.gt(0),'geometric_self_occlusion',np.where(d.ref_short_edges.gt(0),'short_edge_H0','plain_H0')))
    d['personal_sample']=d.personal_comparison & d.independent_vote_eligible & d.peer_n.ge(3)
    # Correctness statements require existing formal reference eligibility; GT-free expressions do not.
    d['reference_sample']=d.personal_sample & d.quality_usable & d.same_difficulty_target & d.ref_turn5.notna()
    save('record_conditions.csv.gz',d)
    image=[]
    use=d[d.reference_sample & d.condition.eq('manual') & d.layer.eq('ordinary')]
    for (im,tid),f in use.groupby(['image_code','reference_id']):
        a=f.iloc[0]
        image.append(dict(image_code=im,image_id=a.image_id,reference_id=tid,building_id=a.building_id,
            difficulty=a.difficulty,n=len(f),people=f.worker_id.nunique(),mechanism=a.mechanism,
            ref_turn5=a.ref_turn5,ref_H=a.ref_H,short_edges=a.ref_short_edges,
            short_span_deg=a.ref_short_min_horizontal_deg,far_p90_h=a.ref_radius_p90_h,
            reduction_rate=f.reduced.mean(),unmatched9=f.unmatched_ref_9.mean(),
            matched_bottom_bias=f.bottom_bias_9.mean(),peer_delta=f.pair_n_peer_delta.mean()))
    images=pd.DataFrame(image);save('image_mechanisms.csv',images)
    six=use[use.ref_turn5.eq(6)].copy()
    group=[]
    for (n,mechanism),f in images.groupby(['ref_turn5','mechanism']):
        bybuilding=f.groupby('building_id').reduction_rate.mean()
        group.append(dict(ref_turn5=n,mechanism=mechanism,images=len(f),buildings=f.building_id.nunique(),
            reduction_rate_image_equal=f.reduction_rate.mean(),reduction_rate_building_equal=bybuilding.mean()))
    save('fixed_complexity_summary.csv',pd.DataFrame(group))
    pairs=pd.concat([paired_conditions(six,'plain_H0','short_edge_H0'),
                     paired_conditions(six,'plain_H0','geometric_self_occlusion')],ignore_index=True)
    save('person_fixed6_conditions.csv',pairs)
    class_rows=[]
    for (im,tid),f in six.groupby(['image_code','reference_id']):
        if min(f.R5.sum(),(~f.R5).sum())<2:continue
        class_rows.append(dict(image_code=im,reference_id=tid,mechanism=f.mechanism.iloc[0],
            R5_n=int(f.R5.sum()),others_n=int((~f.R5).sum()),R5_reduction=f.loc[f.R5,'reduced'].mean(),
            other_reduction=f.loc[~f.R5,'reduced'].mean()))
    save('same_image_fixed6_R5.csv',pd.DataFrame(class_rows))
    sensitivity=[]
    for angle in [3,5,10]:
        for mechanism,f in six.groupby('mechanism'):
            f=f.copy();f['reduced_angle']=(f.pair_n-f[f'near_straight_nodes_{angle}deg'])<f[f'ref_turn{angle}']
            rates=f.groupby('image_code').reduced_angle.mean()
            sensitivity.append(dict(angle_deg=angle,mechanism=mechanism,images=len(rates),reduction_image_mean=rates.mean()))
    save('turn_threshold_sensitivity.csv',pd.DataFrame(sensitivity))
    # GT-free spread includes different accepted ranges, but exactly one independent person per image.
    area=d[d.personal_comparison & d.independent_vote_eligible & d.condition.eq('manual')].copy()
    assert not area.duplicated(['worker_id','image_id']).any()
    area['image_people']=area.groupby('image_id').object_id.transform('count')
    area=area[area.image_people.ge(3)]
    area['area_peer_absolute_log_deviation']=(area.log_area-area.groupby('image_id').log_area.transform('median')).abs()
    area_images=area.groupby(['image_code','building_id','layer']).agg(
        people=('worker_id','nunique'),median_abs_deviation=('area_peer_absolute_log_deviation','median'),
        log_area_iqr=('log_area',lambda s:s.quantile(.75)-s.quantile(.25))).reset_index()
    save('doorway_area_image_spread.csv',area_images)
    save('area_peer_records.csv.gz',area[['object_id','worker_id','image_id','image_code','building_id','layer','reference_id','quality_usable','log_area','area_peer_absolute_log_deviation']])
    aw=area.groupby(['worker_id','layer']).agg(images=('image_id','nunique'),deviation=('area_peer_absolute_log_deviation','mean')).reset_index()
    ap=aw[aw.layer.eq('ordinary')&aw.images.ge(2)].merge(aw[aw.layer.eq('doorway')&aw.images.ge(2)],on='worker_id',suffixes=('_ordinary','_doorway'))
    ap['doorway_delta']=ap.deviation_doorway-ap.deviation_ordinary
    save('person_doorway_area_spread.csv',ap)
    hard=use[use.difficulty.eq('困难')].copy()
    hard['expression_relation']=np.where(hard.annotation_turn5.lt(hard.ref_turn5),'fewer_turns',
        np.where(hard.annotation_turn5.gt(hard.ref_turn5),'more_turns','same_turn_count'))
    save('hard_expression_records.csv',hard)
    hard_summary=hard.groupby(['image_code','mechanism','expression_relation']).agg(
        n=('object_id','size'),unmatched9=('unmatched_ref_9','mean'),bias=('bottom_bias_9','mean')).reset_index()
    save('hard_expression_images.csv',hard_summary)
    # A two-image within-person condition contrast, selected from existing visual notes, never scores.
    selected_cases=['b8cTxDM8gDG-07','jtcxE69GiFV-13','jh4fc5c5qoQ-13']
    case_rows=d[d.personal_sample & d.condition.eq('manual') & d.image_code.isin(selected_cases)].copy()
    save('case_person_rows.csv',case_rows)
    a=case_rows[case_rows.image_code.eq(selected_cases[0])]
    b=case_rows[case_rows.image_code.eq(selected_cases[1])]
    p=a[['worker_id','object_id','reference_id','annotation_turn5']].merge(
        b[['worker_id','object_id','reference_id','annotation_turn5']],on='worker_id',suffixes=('_clear','_curtain'),validate='one_to_one')
    p['turn_delta']=p.annotation_turn5_curtain-p.annotation_turn5_clear
    save('same_people_clear_curtain.csv',p)

    v._configure_font(Path('C:/Windows/Fonts/msyh.ttc'))
    six_images=images[images.ref_turn5.eq(6)]
    names=['plain_H0','short_edge_H0','geometric_self_occlusion']
    fig,ax=plt.subplots(figsize=(8,4.6))
    for j,name in enumerate(names):
        f=six_images[six_images.mechanism.eq(name)].sort_values('image_code')
        jitter=np.linspace(-.13,.13,len(f))
        ax.scatter(j+jitter,f.reduction_rate*100,s=30,alpha=.8)
        ax.plot([j-.2,j+.2],[f.reduction_rate.mean()*100]*2,color='black',linewidth=2)
        ax.text(j,103,f'{len(f)}图',ha='center')
    ax.set_xticks(range(3),['H=0，无短边','H=0，有短转折边','几何H>0'])
    ax.set_ylim(-3,112);ax.set_ylabel('同图少于参考有效转折数的人员比例（%）')
    ax.set_title('固定6转折：表达简化仍随条件变化，点代表图片')
    fig.tight_layout();fig.savefig(OUT/'fixed6_conditions.png',dpi=160);plt.close(fig)

    fig,axes=plt.subplots(2,2,figsize=(13,9))
    details=[]
    for i,code in enumerate(selected_cases[:2]):
        pool=case_rows[case_rows.image_code.eq(code)]
        r=by_id[pool.iloc[0].object_id];ref=r['reference_evidence'];pf=np.asarray(ref['floor_xz_h'])
        edge=np.roll(pf,-1,axis=0)-pf;l=np.linalg.norm(edge,axis=1)
        endpoint=int(np.argmin(l));px=np.asarray(ref['points_1024x512'])[::2,0]
        # The two focus edges do not cross the ERP seam; preserve original pixel coordinates.
        low,high=sorted([px[endpoint],px[(endpoint+1)%len(px)]]);assert high-low<512
        zoom=(max(0,low-70),min(1024,high+70),0,512)
        photo_path=ROOT/'data/mp3d_layout/img_v'/(r['image_id']+'.jpg')
        photo=np.asarray(Image.open(photo_path).convert('RGB'))
        ids=[]
        for j in range(2):
            v._erp_background(axes[i,j],photo,None if j==0 else zoom)
            v._erp_edges(axes[i,j],ref['points_1024x512'],'#ffd43b',reference=True)
            for worker,color in [('W107','#ff56c8'),('W112','#00d5ff')]:
                rr=pool[pool.worker_id.eq(worker)];assert len(rr)==1
                obj=by_id[rr.iloc[0].object_id];v._erp_edges(axes[i,j],obj['points_1024x512'],color,markers=True)
                if j==0:ids.append(dict(worker_id=worker,object_id=obj['object_id'],turns=rr.iloc[0].annotation_turn5))
            axes[i,j].set_title(code+(' 全景' if j==0 else ' 短边附近局部放大'))
        details.append(dict(image_code=code,reference_id=ref['target_id'],photo=photo_path.relative_to(ROOT).as_posix(),
            workers=ids,zoom_1024x512=zoom,short_edge_1based=endpoint+1))
    fig.suptitle('同一人员跨图：W107品红、W112青色、原参考黄色；线条为既定处理后点位',fontsize=12)
    fig.tight_layout();fig.savefig(OUT/'same_people_conditions_overlay.png',dpi=150);plt.close(fig)
    save('overlay_evidence.json',details)
    fig,axes=plt.subplots(1,2,figsize=(11,4.5))
    for j,layer in enumerate(['ordinary','doorway']):
        f=area_images[area_images.layer.eq(layer)].sort_values('image_code')
        axes[0].scatter(j+np.linspace(-.15,.15,len(f)),f.log_area_iqr,s=14,alpha=.65)
        axes[0].plot([j-.2,j+.2],[f.log_area_iqr.median()]*2,color='black',lw=2)
    axes[0].set_xticks([0,1],['普通（216图）','门洞（17图）']);axes[0].set_ylabel('同图作答 log 面积四分位距')
    axes[1].scatter(range(len(ap)),ap.sort_values('doorway_delta').doorway_delta,s=18)
    axes[1].axhline(0,color='gray',lw=1);axes[1].set_xlabel('两条件各至少2图的51名人员，按差值排序')
    axes[1].set_ylabel('本人偏离同图面积中位数程度：门洞−普通')
    fig.suptitle('范围/尺度分散线索，不直接判定空间选择对错');fig.tight_layout()
    fig.savefig(OUT/'doorway_area_spread.png',dpi=150);plt.close(fig)
    # Far/near is exploratory: the dataset is not a calibrated metric room survey.
    probe=six_images[six_images.ref_H.eq(0)]
    save('feature_associations.json',dict(fixed6_H0_images=len(probe),
        far_radius_reduction_spearman=probe.far_p90_h.corr(probe.reduction_rate,method='spearman'),
        short_span_images=int(probe.short_span_deg.notna().sum()),
        short_span_reduction_spearman=probe.short_span_deg.corr(probe.reduction_rate,method='spearman')))
    save('COVERAGE.json',dict(data_release='v2',inventory=len(records),non_oos_records=len(selected),
        non_oos_images=len({r['image_id'] for r in selected}),doorway_images=len({r['image_id'] for r in selected if r['is_doorway']}),
        geometry_available=int(d.feature_status.eq('valid_floor').sum()),personal_expression_records=int(d.personal_sample.sum()),
        nonformal_expression_records=int((d.personal_sample & ~d.quality_usable).sum()),
        known_GT_issue_expression_records=int(sum(bool(by_id[o]['exclusion_attribution']['context_factors']['gt_substantive_error'] or by_id[o]['exclusion_attribution']['context_factors']['gt_detail_omission']) for o in d.loc[d.personal_sample,'object_id'])),
        formal_current_target_manual_records=len(use),formal_current_target_manual_images=use.image_id.nunique(),
        fixed6_records=len(six),fixed6_images=six.image_id.nunique(),same_people_example=len(p),
        no_labels_changed=True,no_score_recomputed=True))
    save('SOURCES.json',dict(data_release='v2',analysis_revision='difficulty_mechanisms_v2_20261020_r1',
        primary=str(EVIDENCE.relative_to(ROOT)),reused_expression=str(EXPRESSION.relative_to(ROOT)),
        reused_correspondence=str(TRANSFER.relative_to(ROOT)),
        same_room_mechanisms='research/same_room/same_room_multiview_20261020/structure_transfer/README.md',
        points='effective processed points from evidence; no original reimport or reordering',
        class_labels='frozen exploratory R5/H2/Rnew2; labels not independently validated here'))
    print((OUT/'COVERAGE.json').read_text(encoding='utf-8'))


if __name__=='__main__':main()

