"""Describe every complete-event column and freeze independently savable batch 2."""
from __future__ import annotations
import csv
import json
import shutil
from pathlib import Path
from repair_events import HERE, read_rows, reader, atomic_csv, atomic_json, validate_csv, sha

METRICS = {
 'B8L2':('冻结主质量分','分，0–100'), 'D10':('冻结敏感性质量分','分，0–100'),
 'IoU3D100':('冻结角点均高三维代理IoU×100','百分数，0–100'),
 'iou_2d':('候选底面与冻结参考底面IoU','比例，0–1'),
 'S_bottom_deg':('底面边界的球面双向距离','度'),
 'dir':('候选相对自身最佳正交轴的方向残差','度'),
 'Hmean':('沿周长平均高度比的绝对残差','无量纲'),
 'Hcenter':('中心化局部高度残差','无量纲'),
 'omission':('冻结参考底面的遗漏比例','比例，0–1'),
 'extension':('候选相对冻结参考的扩展比例','比例，0–1'),
 'height_mean_ratio':('冻结引擎平均高度比；区别于角点推导总高height_mean_h','无量纲'),
 'nodes':('融合输出的角点／上下点对数','个'),
 'reference_nodes':('冻结参考的角点／上下点对数','个'),
 'geometry_area_h2':('推导底面面积','相机高度²'),
 'centroid_x_h':('底面质心x坐标','相机高度'), 'centroid_z_h':('底面质心z坐标','相机高度'),
 'bounds_min_x_h':('底面x最小界','相机高度'), 'bounds_max_x_h':('底面x最大界','相机高度'),
 'bounds_min_z_h':('底面z最小界','相机高度'), 'bounds_max_z_h':('底面z最大界','相机高度'),
 'height_mean_h':('由上下射线推导的地面至顶面总高均值','相机高度'),
 'height_min_h':('由上下射线推导的总高最小值','相机高度'),
 'height_max_h':('由上下射线推导的总高最大值','相机高度'),
 'top_y_mean_px':('ERP顶点平均纵坐标','像素，1024×512坐标系'),
 'bottom_y_mean_px':('ERP底点平均纵坐标','像素，1024×512坐标系'),
 'source_time_total_seconds':('全部成员来源标注时间之和；缺任一成员则未知','秒'),
 'target_time_total_seconds':('全部成员目标图匹配时间之和；缺任一成员则未知','秒'),
 'source_time_known_sum_seconds':('来源时间已知成员的时间之和；不能冒充全队总时间','秒'),
 'target_time_known_sum_seconds':('目标图时间已知成员的时间之和','秒'),
 'source_parallel_active_seconds':('全部来源时间已知时的最大成员时间；非实测墙钟时间','秒'),
 'target_parallel_active_seconds':('全部目标图时间已知时的最大成员时间','秒'),
 'fusion_seconds':('实际本地融合计算耗时','秒'), 'score_seconds':('实际本地评分计算耗时','秒'),
 'floor_jaccard_difference':('两终点底面的1−IoU','比例，0–1'),
 'floor_symdiff_h2':('两终点底面面积对称差','相机高度²'),
 'mean_height_prism_pair_iou':('两终点以平均高度比构成的棱柱IoU代理','比例，0–1'),
 'mean_height_prism_pair_difference':('1−两终点均高棱柱IoU代理','比例，0–1'),
 'height_ratio_pair_abs_logdiff':('两终点平均高度比之比的绝对对数','无量纲'),
 'floor_area_abs_log_ratio':('两终点底面面积比的绝对对数','无量纲'),
 'centroid_distance_h':('两终点底面质心距离','相机高度'),
 'structure_bound_cyclic_deg':('同点数环序平移匹配后的最小最大上下边界角差','度'),
 'bound_cyclic_shift':('上述环序平移量','角点索引偏移'),
 'structure_reason':('结构边界比较不可用原因','类别'),
 'geometry_comparison_error':('几何交并运算异常；空字符串表示无记录异常','文本'),
 'shared_workers':('两终点实际共同成员数','人'),
 'turnover':('单边移出／移入的实际人数','人'),
 'symmetric_member_difference':('成员集合对称差大小，通常等于2×实际换人数','人'),
 'same_members':('两个实际成员集合完全相同','布尔'),
 'complete_a':('比较左终点完整可评价','布尔'), 'complete_b':('比较右终点完整可评价','布尔'),
 'both_complete':('比较两终点均完整可评价','布尔'),
 'quality_comparable':('比较两终点B8L2均已知','布尔'),
 'time_comparable':('两终点来源总时间正且来源种类相同','布尔'),
 'joint_cost_quality_comparable':('质量及来源时间均可比较','布尔'),
 'joint_save20_loss_le2':('时间至少节省20%、Q下降不超过2且两终点完整','0/1；不可比较为空'),
 'source_log_time_ratio':('比较右终点总时间/左终点总时间的自然对数','无量纲'),
 'loss_gt5':('比较右终点Q相对左终点下降超过5分','0/1；缺分为空'),
 'loss_gt10':('比较右终点Q相对左终点下降超过10分','0/1；缺分为空'),
 'node_count_change':('比较右终点−左终点角点数','个'),
 'node_count_difference':('两终点角点数绝对差','个'),
 'new_n_change':('比较右终点−左终点新来源人数','人'),
 'minimum_support':('原融合MV50人数票数门槛','票'),
 'node_supports':('入选节点支持票数，按冻结顺序以竖线分隔','票列表'),
 'selected_support_min':('入选节点的最小支持人数/团队人数','比例，0–1'),
 'identity_groups_n':('对应关系形成的原观察组数','个'),
 'unselected_groups_n':('未达到选择条件的观察组数','个'),
 'minority_observations_n':('未入选观察组中的支持票数之和','票'),
 'half_vote_nodes':('冻结融合的半票节点统计','个'),
 'source_time_known_n':('来源时间已知成员数','人'),
 'target_time_known_n':('目标图时间已知成员数','人'),
 'target_individual_B8L2_known_n':('目标图个人Q已知成员数','人'),
 'target_individual_B8L2_mean':('目标图个人Q均值，须全队均已知','分'),
 'target_individual_B8L2_min':('目标图个人Q最小值，须全队均已知','分'),
}
CONTEXT = {
 'event_id':'唯一事件ID', 'pool_id':'任务池ID（图片/条件/参考资格）',
 'image':'短图名', 'image_id':'原始完整图片ID', 'building':'建筑ID',
 'condition':'manual/semi条件', 'layer':'普通Manual/普通Semi/门洞等资格层',
 'difficulty':'冻结难度层', 'difficulty_aligned':'难度标签已对齐标志',
 'reference_id':'冻结参考绑定ID', 'reference_version':'冻结参考版本',
 'method_id':'人员分类方法ID', 'tier':'粗类/细类/单层',
 'labelled_pool_n':'该方法在该池有合法冻结标签的人数', 'formal_pool_n':'正式资格池人数',
 'class_capacities':'每类实际可用人数', 'event_mode':'跨构成或同粗类内换细类块',
 'registration_stage':'构造登记阶段', 'ABC_sampling':'事件采样/构造合同',
 'n':'ABC共同团队人数', 'k':'实际团队人数', 'pool_n':'正式资格池总人数',
 'm_AB':'A→B实际替换人数', 'm_AC':'A→C实际替换人数', 'm_BC':'B→C实际净替换人数',
 'overlap_AB':'A/B重叠成员数', 'overlap_AC':'A/C重叠成员数', 'overlap_BC':'B/C重叠成员数',
 'new_block_YZ_overlap':'Y/Z新块重叠成员数',
 'composition_turnover_AC':'A→C类别人数向量需要迁移的最小人数',
 'team_A':'A终点唯一团队键', 'team_B':'B终点唯一团队键', 'team_C':'C终点唯一团队键',
 'team_key':'实际成员集合对应的终点唯一键',
 'composition_A':'A完整类别人数向量', 'composition_B':'B完整类别人数向量',
 'composition_C':'C完整类别人数向量', 'composition_delta':'C−A类别人数向量',
 'common_background':'共同背景S的实际成员', 'outgoing_block_X':'A中的移出块X',
 'same_count_block_Y':'B中的同构成替代块Y', 'changed_count_block_Z':'C中的改构成替代块Z',
 'member_workers':'实际人员ID列表，竖线分隔', 'member_object_ids':'实际作答记录ID列表，竖线分隔',
 'computed_all_arms':'ABC三个请求均已取得终点', 'all_scored':'ABC三个B8L2均已知',
 'all_complete':'ABC三个终点均完整可评价',
 'time_population':'三终点实际成员来源组合', 'same_source_counts':'ABC新旧来源人数均相同',
 'direction':'登记类别构成变化方向', 'focal_class_count_change':'关注类的C−A人数变化',
 'score_status':'冻结评分状态，失败保持原原因',
 'geometry_status':'冻结几何状态', 'geometry_reason':'冻结几何状态原因',
 'complete_evaluable':'完整终点可评价标志', 'complete_floor_evaluable':'完整底面可评价标志',
 'floor_evaluable':'底面可评价标志', 'connection_available':'连接结果可用标志',
 'below_four':'少于四角标志', 'location_unresolved':'定位未决标志',
 'order_status':'环序状态', 'order_tied':'环序候选并列标志', 'parity':'团队人数奇偶，k mod 2',
 'diag_status':'局部结构诊断状态',
 'endpoint_origin':'新计算/历史恢复/本轮基准复用的来源身份',
 'historical_583261_set_overlap':'是否命中恢复的583261个历史集合索引',
 'historical_complete_geometry_cache':'是否有历史完整几何缓存',
 'historical_scalar_cache':'是否有历史标量缓存',
 'new_n':'该实际团队新来源人数', 'old_n':'该实际团队历史来源人数',
 'new_member_n':'输入任务池的新来源人数（不是实际团队new_n）',
 'old_member_n':'输入任务池的历史来源人数（不是实际团队old_n）',
 'source_inventory_n':'输入任务池的来源库存人数',
 'room_id':'既有房间元数据，缺失不猜测', 'scene':'既有场景元数据',
 'time_source_kinds':'时间来源种类', 'time_source_table':'时间来源表路径',
 'failure':'终点不满足complete_evaluable标志',
 'source_time_seconds':'全队来源标注时间之和；缺成员则未知',
}
CORNER = {
 'corner_metric_schema':'对应角点诊断版本', 'complete':'两终点完整', 'same_count':'两终点角点数相同',
 'corners':'匹配角点数', 'ring_reversed':'对应候选环向反转标志；仅诊断不改原环序',
 'shift':'候选环序位移', 'legacy_angle_deg':'未考虑环向反转的原环序最小最大角差',
 'angle_deg':'考虑环向后候选匹配的最小最大角差',
 'second_angle_deg':'第二好候选的最大角差', 'match_gap_deg':'次优−最优角差',
 'matched_reflex_disagreement_n':'对应候选中凹凸角色不一致数',
 'high_angle_correspondence_warning':'候选角差大于12度警告（不是改变融合参数）',
 'status':'对应角点诊断状态，不同点数/缺几何/并列候选等保留',
 'pair_area_scale_h':'两终点平均底面面积的平方根',
 'near_horizon_bottom_min_deg':'最靠近地平线底点相对地平线的角距离',
}

def base_description(field):
    if field in METRICS:return METRICS[field]
    if field in CONTEXT:
        unit='标识/类别/文本'
        if field in {'n','k','pool_n','formal_pool_n','labelled_pool_n','m_AB','m_AC','m_BC','overlap_AB','overlap_AC','overlap_BC','new_block_YZ_overlap','new_n','old_n','new_member_n','old_member_n','source_inventory_n','composition_turnover_AC','focal_class_count_change'}:unit='人'
        if field=='source_time_seconds':unit='秒'
        return CONTEXT[field],unit
    if field.startswith('ref_'):
        t=field.rsplit('_',1)[-1]
        if '_recall_' in field:return ('冻结参考'+('角点' if 'node' in field else '边邻接')+f'召回，{t}度诊断门槛','比例，0–1')
        if '_matched_' in field:return (f'{t}度门槛下匹配的参考索引集合','索引列表')
        if '_set_jaccard_difference_' in field:return (f'{t}度门槛下参考匹配集合的1−Jaccard','比例，0–1')
    if field.startswith('diag_wall_coverage_'):return ('参考墙边覆盖诊断，后缀为固定相机高度距离容差','比例，0–1')
    if field.startswith('diag_corner_recall_'):return ('参考角点召回诊断，后缀为固定相机高度距离容差','比例，0–1')
    if field.startswith('corner_'):
        name=field[len('corner_'):]
        if name in CORNER:
            unit='度' if name.endswith('_deg') else ('相机高度' if name.endswith('_h') else '状态/计数')
            return CORNER[name],unit
        if name.startswith(('bev_','top_')):
            p='底点' if name.startswith('bev_') else '顶点'
            desc=p+'对应距离'+name.split('_',1)[1]
            if name.endswith('_h'):unit='相机高度'
            elif name.endswith('_pct_diagonal'):unit='相对左终点底面对角线的百分数'
            elif name.endswith('_local_radius_fraction'):unit='相对成对局部半径的比例'
            else:unit='相对成对面积尺度的比例'
            return desc,unit
    if field.startswith('joint_stable_'):
        return ('质量/角点数/底面/边界联合稳定；strict/main/wide门槛分别为1/.02/2°、2/.05/3°、5/.10/5°；失败为False','布尔')
    if field in {'B8L2_a','B8L2_b'}:return ('比较'+('左' if field.endswith('_a') else '右')+'终点B8L2','分，0–100')
    if field.startswith('abs_'):
        b,u=base_description(field[4:].removesuffix('_change'));return '绝对变化：'+b,u
    if field.endswith('_change'):
        b,u=base_description(field.removesuffix('_change'));return '右−左变化：'+b,u
    return ('冻结原字段 '+field+'；见source_code列定位的实现','保持源定义')


def description(field):
    source='analysis/ABC_ALL_COMPONENT_EVENTS.csv.gz'
    source_code='analysis/analyze_global.py'
    original=field
    op='原事件字段'
    if field.startswith('endpoint_'):
        arm,field=field.split('__',1);op=arm[-1]+'终点绝对值'
        source='composition/TEAMS_SCALARS.csv.gz';source_code='composition/run_endpoints.py；原fusion_runner.py'
    elif field in {'A_member_workers','B_member_workers','C_member_workers'}:
        source='composition/TEAMS_SCALARS.csv.gz';source_code='成员块集合重建，且逐臂与原终点member_workers精确核对'
    elif field.endswith('_geometry'):
        field=field.removesuffix('_geometry');op='几何联表保留的同名字段副本';source_code='composition/geometry_events.py'
    if field in {'abs_Q_change_advantage','stable_advantage','common_quality_within_abs','common_quality_cross_abs','net_failure_difference'}:
        special={
          'abs_Q_change_advantage':('A/C绝对Q变化−A/B绝对Q变化','分'),
          'stable_advantage':('A/B联合稳定指示−A/C联合稳定指示','−1/0/+1'),
          'common_quality_within_abs':('仅ABC三臂Q均已知时的A/B绝对Q变化','分'),
          'common_quality_cross_abs':('仅ABC三臂Q均已知时的A/C绝对Q变化','分'),
          'net_failure_difference':('C失败指示−B失败指示','−1/0/+1')}
        desc,unit=special[field]
    elif field.startswith('source_and_historyQ'):
        desc='来源人数相同且X→Y、X→Z两个楼外块均Q变化均不超过字段中阈值';unit='布尔'
    elif '_history_' in field:
        desc='目标建筑外成员历史块特征：'+field+'；same=Y−X，cross=Z−X，net=Z−Y';unit='Q为分；T为对数时间；困难效应为分'
    elif field.startswith('cross_minus_within_'):
        desc,unit=base_description(field[len('cross_minus_within_'):]);desc='A/C减A/B：'+desc
    else:
        if field.startswith(('A_','B_','C_')):
            op=field[0]+'终点绝对值';field=field[2:]
        elif field.startswith(('same_','within_','cross_','net_')) and field not in CONTEXT:
            prefix,field=field.split('_',1)
            op={'same':'B−A或A/B比较','within':'A/B几何比较','cross':'C−A或A/C比较','net':'C−B或B/C比较'}[prefix]
            if prefix=='within' or 'corner_' in field:source_code='composition/geometry_events.py；原summarize_grid.py/corner_distance.py'
        desc,unit=base_description(field)
    source_field=original
    if original.startswith('endpoint_'):source_field=original.split('__',1)[1]
    elif original in {'A_member_workers','B_member_workers','C_member_workers'}:source_field='member_workers'
    return {'field':original,'meaning_zh':desc,'operation':op,'unit':unit,'source_table':source,
            'source_field':source_field,'source_code':source_code,
            'missing_semantics':'空值保持未知/不适用；结合对应score_status、geometry_status和comparison原因；绝不补0。空文本状态按字段解释。'}


def main():
    full=HERE/'ABC_EVENT_RESULTS_COMPLETE.csv.gz'
    with reader(full) as f:
        rd=csv.DictReader(f);fields=rd.fieldnames
        nonmissing={k:0 for k in fields};examples={}
        for row in rd:
            for k,v in row.items():
                if v!='':
                    nonmissing[k]+=1
                    if k not in examples:examples[k]=v
    dictionary=[]
    for k in fields:
        r=description(k);r.update(available_rows=nonmissing[k],missing_rows=12953-nonmissing[k],example=examples.get(k,''))
        dictionary.append(r)
    dfields=list(dictionary[0])
    dresult=atomic_csv(HERE/'EVENT_FIELD_DICTIONARY.csv',dfields,dictionary,fields,key='field')
    # Split the large ordinary-Manual CSV without recomputing any endpoint.
    with reader(full) as handle:
        rd=csv.DictReader(handle);f=rd.fieldnames
        rows=[r for r in rd if r['layer']=='ordinary_manual']
    manual=[]
    for i in range(0,len(rows),4000):
        r=rows[i:i+4000]
        manual.append(atomic_csv(HERE/f'ABC_EVENTS_MANUAL_ORDINARY_PART{i//4000+1:02d}_COMPLETE.csv',f,r,[x['event_id'] for x in r]))
    old=json.loads((HERE/'FULL_REPAIR_RECEIPT.json').read_text())
    initial=json.loads((HERE/'ORIGINAL_INCOMPLETE_EXPORT_DIAGNOSIS.json').read_text())
    for key in ['old_published_rows','old_published_columns','missing_rows_restored','restored_by_layer','original_export_evidence','initial_diagnosis_is_immutable']:
        old[key]=initial[key]
    old['sources']=initial['sources']+[x for x in old['sources'] if x['path']=='composition/TEAMS_SCALARS.csv.gz']
    old['outputs']=[x for x in old['outputs'] if not x['path'].startswith('ABC_EVENTS_MANUAL_ORDINARY') and x['path']!='EVENT_FIELD_DICTIONARY.csv']+manual+[dresult]
    old['shard_rows_total']=sum(x['rows'] for x in old['outputs'] if x['path'].startswith('ABC_EVENTS_'))
    assert old['shard_rows_total']==12953
    old['diagnosis_reference']='ORIGINAL_INCOMPLETE_EXPORT_DIAGNOSIS.json'
    old['dictionary_unexpanded_fields']=[r['field'] for r in dictionary if '冻结原字段' in r['meaning_zh']]
    atomic_json(HERE/'FULL_REPAIR_RECEIPT.json',old)
    # Ready batches are immutable after hand-off. Never reuse a live generator
    # output as the pending upload source.
    ready=HERE/'ready_batch02';ready.mkdir(exist_ok=True)
    names=[x['path'] for x in old['outputs'] if x['path']!='ABC_EVENT_RESULTS_KEY_REPAIRED.csv']
    names+=['FULL_REPAIR_RECEIPT.json','repair_events.py','build_dictionary_and_freeze.py']
    manifest=[]
    for name in names:
        src=HERE/name;target=ready/name
        if target.exists():assert sha(src)==sha(target),('ready batch is immutable',name)
        else:shutil.copyfile(src,target)
        manifest.append({'filename':name,'bytes':target.stat().st_size,'sha256':sha(target)})
    atomic_json(ready/'BATCH02_MANIFEST.json',manifest)
    print(json.dumps({'ready_directory':str(ready),'files':manifest,'unexpanded_fields':old['dictionary_unexpanded_fields']},ensure_ascii=False))


if __name__=='__main__':main()
