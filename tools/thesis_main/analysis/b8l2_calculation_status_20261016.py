"""只核原标注的冻结引擎可计算性；与参考缺口、采用资格及是否运行分轴。"""
import numpy as np

from .difficulty_coarse_closeout_20261014 import floor


def inspect_geometry(obj, engine):
    """不修改/补齐原点；旧geometry状态与未确认环只作来源信息。"""
    result=dict(object_id=obj.get('object_id'),input_geometry_status='points_missing',
        full_input_available=False,floor_input_available=False,floor_xz_h=None,reasons=[],warnings=[],
        source_geometry_status=obj.get('geometry',{}).get('status'),ring_confirmed=obj.get('ring_confirmed'),
        geometry_inspected=True,annotation_modified=False,measurement_attempted=False)
    points=obj.get('points_1024x512')
    if points is None or len(points)==0:
        result['reasons']=['final_paired_points_missing']
        return result
    try:
        values=np.asarray(points,dtype=float)
    except (ValueError,TypeError):
        result.update(input_geometry_status='invalid_point_array',reasons=['point_array_not_numeric'])
        return result
    if values.ndim!=2 or values.shape[1]!=2:
        result.update(input_geometry_status='invalid_point_array',reasons=['point_array_shape_invalid'])
        return result
    if len(values)%2:
        result.update(input_geometry_status='unpaired_points',reasons=['odd_point_count_no_pair_repair'])
        return result
    if len(values)<6:
        result.update(input_geometry_status='insufficient_paired_points',reasons=['fewer_than_three_declared_pairs'])
        return result
    # 顶点无效时仍检查已有底点；不为调用完整引擎而补任何顶点。
    bottom=values[1::2]
    if np.isfinite(bottom).all() and ((bottom[:,1]>256)&(bottom[:,1]<512)).all():
        original_floor=floor(values)
        footprint=engine.valid.validate_footprint(original_floor,role='annotation')
        result['floor_input_available']=bool(footprint['available'])
        result['floor_xz_h']=original_floor.tolist() if footprint['available'] else None
        result['floor_reason_codes']=list(dict.fromkeys(e['code'] for e in footprint['errors']))
    else:
        result['floor_reason_codes']=['bottom_nonfinite_or_not_below_horizon']
    try:
        geometry=engine.geometry(points)
    except (ValueError,TypeError,ArithmeticError) as exc:
        result.update(input_geometry_status='floor_only_available' if result['floor_input_available'] else 'geometry_reconstruction_unavailable',
                      reasons=['frozen_geometry:'+str(exc)]+result['floor_reason_codes'])
        return result
    validation=engine.valid.validate_record(geometry,role='annotation')
    reasons=list(validation['reason_codes'])
    # 引擎ERP适配器以底点XZ构造顶点；错配经度不能被这种构造静默“修好”。
    difference=(values[::2,0]-values[1::2,0]+512)%1024-512
    roundoff=engine.valid.ROUNDOFF_MULTIPLIER*engine.valid.EPS64*1024
    if np.any(abs(difference)>roundoff):
        reasons.append('top_bottom_longitude_mismatch_not_repaired')
    result['full_input_available']=bool(validation['available'] and not reasons)
    result['input_geometry_status']=('full_geometry_available' if result['full_input_available'] else
        'floor_only_available' if result['floor_input_available'] else 'invalid_floor_or_ring_geometry')
    result['reasons']=reasons
    result['warnings']=[warning['code'] for warning in validation['warnings']]
    result['validator_version']=validation['validator_version']
    return result


def measure_status(task,engine,*,run=False):
    """可选实际测量检查；未运行/输入不可用/参考缺失均不伪装成运行失败。"""
    result=dict(measurement_status='not_run',measurement_attempted=False,calculation_failed=False,
                input_status='not_checked',reference_status='not_checked',reasons=[])
    if not run:
        return result
    if task.get('reference_points') is None or not task.get('reference_full_available',True):
        result.update(measurement_status='not_run_reference_unavailable',reference_status='missing_full_reference',
                      reasons=['reference_full_points_missing'])
        return result
    geometries=[]
    for role,key in [('input','annotation_points'),('reference','reference_points')]:
        inspection=inspect_geometry(dict(points_1024x512=task[key]),engine)
        result[role+'_status']=inspection['input_geometry_status']
        if not inspection['full_input_available']:
            result.update(measurement_status='not_run_'+role+'_unavailable',reasons=[role+':'+reason for reason in inspection['reasons']])
            return result
        geometries.append(engine.geometry(task[key]))
    result['measurement_attempted']=True
    try:
        measured=engine.measure(*geometries)
    except (ValueError,TypeError,ArithmeticError) as exc:
        result.update(measurement_status='measurement_failed',calculation_failed=True,reasons=['frozen_measurement:'+str(exc)])
        return result
    result.update(measurement_status=measured['status'],reasons=measured.get('reasons',[]))
    return result
