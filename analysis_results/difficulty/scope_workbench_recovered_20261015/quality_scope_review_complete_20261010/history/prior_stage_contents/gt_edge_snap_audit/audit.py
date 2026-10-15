#!/usr/bin/env python3
"""Read-only, offline GT-edge audit. Python 3.9+ standard library only.

Default source: fixtures/audit_input.json beside this script.
Default output: this script's directory. --source also accepts the full original
workbench data.json with the same five confirmed records.
"""
import argparse, json, math, hashlib, pathlib
BASE = pathlib.Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source', type=pathlib.Path, default=BASE/'fixtures/audit_input.json', help='Frozen fixture or original workbench data.json')
parser.add_argument('--out', type=pathlib.Path, default=BASE, help='Output directory for audit.json and validation.json')
args = parser.parse_args()
SOURCE = args.source.resolve()
OUT = args.out.resolve()
OUT.mkdir(parents=True, exist_ok=True)
raw = SOURCE.read_bytes()
data = json.loads(raw)
frozen = json.loads((BASE/'fixtures/audit_input.json').read_text())
provenance = data.get('provenance', frozen['provenance'])
expected = {x['image_code']:x['confirmed_review'] for x in frozen['images'] if x.get('confirmed_review')}
actual = {x['image_code']:x['confirmed_review'] for x in data['images'] if x.get('confirmed_review')}
if actual != expected:
    raise SystemExit('This frozen audit requires the original five confirmed_review snapshots; supplied source differs. No result was rewritten.')
source_by_code = {x['image_code']:x for x in data['images']}
gt_keys = ['image_id','reference_object_id','reference_version','reference_points_1024x512']
if any(row['image_code'] not in source_by_code or any(row[k] != source_by_code[row['image_code']][k] for k in gt_keys) for row in frozen['images']):
    raise SystemExit('This frozen audit requires the original selected GT snapshots; supplied source differs. No result was rewritten.')
source_candidates = {x['image_code'] for x in data['images'] if len(x.get('reference_points_1024x512',[])) == 16}
frozen_candidates = {x['image_code'] for x in frozen['images'] if len(x['reference_points_1024x512']) == 16}
if source_candidates != frozen_candidates:
    raise SystemExit('This frozen audit requires the original 35 eight-vertex screenshot candidates. No result was rewritten.')
sha256 = lambda value: hashlib.sha256(value).hexdigest()
canonical_hash = lambda value: sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode())

def floor(points):
    ans=[]
    for x,y in points[1::2]:
        u=(x/1024-.5)*2*math.pi;v=(y/512-.5)*math.pi;r=1/math.tan(v)
        ans.append([r*math.sin(u),-r*math.cos(u)])
    return ans

def seg_metrics(a,b,c,d,scale):
    u=[b[k]-a[k] for k in range(2)];v=[d[k]-c[k] for k in range(2)]
    lm=math.hypot(*u);lg=math.hypot(*v)
    dot=sum(u[k]*v[k] for k in range(2))/(lm*lg)
    angle=math.degrees(math.acos(min(1,abs(dot))))
    t=[v[k]/lg for k in range(2)];n=[-t[1],t[0]]
    m0=sum((a[k]-c[k])*t[k] for k in range(2));m1=sum((b[k]-c[k])*t[k] for k in range(2))
    off0=sum((a[k]-c[k])*n[k] for k in range(2));off1=sum((b[k]-c[k])*n[k] for k in range(2))
    low=max(0,min(m0,m1));high=min(lg,max(m0,m1));overlap=max(0,high-low)
    overlap_offsets=[]
    if overlap>1e-12 and abs(m1-m0)>1e-12:
        overlap_offsets=[off0+(off1-off0)*(z-m0)/(m1-m0) for z in [low,high]]
    return dict(angle_difference_deg=angle,manual_edge_length_h=lm,gt_edge_length_h=lg,
        manual_endpoint_signed_offsets_to_gt_support_h=[off0,off1],
        max_abs_support_offset_h=max(abs(off0),abs(off1)),
        max_abs_support_offset_fit_svg_px=max(abs(off0),abs(off1))/scale,
        finite_segment_projection_overlap_h=overlap,overlap_fraction_of_manual_projection=overlap/max(abs(m1-m0),1e-15),
        overlap_signed_offset_range_h=sorted(overlap_offsets) if overlap_offsets else None)

images=[]
for im in data['images']:
    conf=im.get('confirmed_review')
    if not conf: continue
    gt=floor(im['reference_points_1024x512']);poly=conf['polygon'];ps=gt+poly
    scale=max((max(p[0] for p in ps)-min(p[0] for p in ps))/460,(max(p[1] for p in ps)-min(p[1] for p in ps))/390,.0001)
    edge_rows=[]
    for i,a in enumerate(poly):
        b=poly[(i+1)%len(poly)];pairs=[]
        for j,c in enumerate(gt):
            m=seg_metrics(a,b,c,gt[(j+1)%len(gt)],scale)
            if m['angle_difference_deg']<=1:
                m.update(gt_edge_1based=[j+1,(j+1)%len(gt)+1]);pairs.append(m)
        pairs.sort(key=lambda q:q['max_abs_support_offset_h'])
        nearest=pairs[0] if pairs else None
        rel='no_near_parallel_gt_edge'
        if nearest:
            if nearest['max_abs_support_offset_h']<1e-9 and nearest['overlap_fraction_of_manual_projection']>.99999:rel='exact_inherited_gt_edge_or_subsegment'
            elif nearest['max_abs_support_offset_h']<1e-9:rel='gt_support_extension_scope_cut'
            elif nearest['max_abs_support_offset_h']<.0005:rel='very_small_axis_or_corner_difference_not_material_snap_candidate'
            elif nearest['finite_segment_projection_overlap_h']>1e-5 and nearest['max_abs_support_offset_fit_svg_px']<=20:rel='nearby_finite_gt_edge_review_candidate'
            elif nearest['max_abs_support_offset_fit_svg_px']<=20:rel='nearby_support_only_scope_cut_position_uncertain'
            else:rel='scope_change_not_a_small_snap_offset'
        edge_rows.append(dict(manual_edge_1based=[i+1,(i+1)%len(poly)+1],endpoints_xz_h=[a,b],classification=rel,nearest_parallel_gt_support=nearest,all_parallel_gt_pairs=pairs))
    images.append(dict(image_code=im['image_code'],image_id=im['image_id'],reference_object_id=im['reference_object_id'],reference_version=im['reference_version'],
        confirmed_at=conf['confirmed_at'],confirmed_record_sha256=hashlib.sha256(json.dumps(conf,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
        selected_gt_floor_xz_h=gt,confirmed_polygon_xz_h=poly,operations=conf['operations'],
        fit_world_units_per_svg_pixel=scale,fit_svg_pixels_per_h=1/scale,edges=edge_rows))

screen=data.get('screenshot_observed_gt_vertices_px',frozen['screenshot_observed_gt_vertices_px'])
fits=[]
qmean=[sum(q[k] for q in screen)/len(screen) for k in range(2)]
qc=[[q[k]-qmean[k] for k in range(2)] for q in screen]
for im in data['images']:
    if len(im.get('reference_points_1024x512',[]))!=16:continue
    p=[[x,-z] for x,z in floor(im['reference_points_1024x512'])]
    pmean=[sum(q[k] for q in p)/len(p) for k in range(2)]
    pc=[[q[k]-pmean[k] for k in range(2)] for q in p]
    scale=sum(pc[i][k]*qc[i][k] for i in range(8) for k in range(2))/sum(v*v for row in pc for v in row)
    translation=[qmean[k]-scale*pmean[k] for k in range(2)]
    rmse=math.sqrt(sum((scale*pc[i][k]-qc[i][k])**2 for i in range(8) for k in range(2))/16)
    fits.append(dict(image_code=im['image_code'],image_id=im['image_id'],coordinate_rmse_screenshot_px=rmse,
        screenshot_pixels_per_h=scale,translation_px=translation,is_in_imported_confirmed_five=bool(im.get('confirmed_review'))))
fits.sort(key=lambda x:x['coordinate_rmse_screenshot_px'])

conclusions={
'b8cTxDM8gDG-18':'旧 cut 的新截断边沿 GT 5→6 所在直线延伸，原有保留 GT 边精确继承；未发现明显误对齐。',
'e9zR4mvMWw7-09':'矩形上边是从 GT 点9向右延伸的范围截断，右边仅部分跟随 GT 1→2；其他区域差异属于范围选择。轴对齐造成的最近 GT 支持线偏差小于0.000251h，初始适配小于0.014px，不是明显漏吸附证据。',
'e9zR4mvMWw7-17':'cut 直接连接 GT 点4与7，其他保留边继承 GT；靠近此切线的既有左墙段不能误当成应吸附的新墙边。未发现明显误对齐。',
'pRbA3pwrgk9-02':'唯一较明确的小偏移候选：下边 z=-0.3376472493 相对 GT 6→7 向外约0.00414h；有70.0%横向重叠。右边 x=0.3547333585 离 GT 3→4 延长线约0.09154–0.09158h，但实际线段零重叠，应单列为范围截断位置待用户判断，不能自动改。',
'q9vSo1VnCiC-29':'矩形上边从 GT 6→7 延长，用于截去门外区域；其余最近 GT 支持线误差至多约0.0000247h，初始适配约0.00262px，未发现明显误对齐。'}
for im in images:
    im['conclusion_zh']=conclusions[im['image_code']]
    for edge in im['edges']:
        edge['classification_is_geometric_heuristic_not_semantic_judgment']=True
        edge['interpretation_zh']='几何邻近关系；不能据此判断用户有意范围或批准吸附。'
    if im['image_code']=='b8cTxDM8gDG-18':
        im['edges'][4]['interpretation_zh']='操作记录明确为cut新增截断边，沿GT 5→6支持线延伸；不是误移现有墙边。'
    if im['image_code']=='e9zR4mvMWw7-09':
        im['edges'][0]['interpretation_zh']='矩形上边从GT点9向右延伸；与GT 8→9有限线段没有实质重叠，是范围截断边。'
        im['edges'][1]['interpretation_zh']='矩形右边仅46.7%的投影与GT 1→2重叠，其余属于范围重构。'
    if im['image_code']=='e9zR4mvMWw7-17':
        im['edges'][3]['interpretation_zh']='操作记录明确为cut，精确连接GT点4与7；与附近GT 3→4实际线段没有实质重叠，不能按最近支持线强行改写。'
    if im['image_code']=='pRbA3pwrgk9-02':
        im['edges'][1]['interpretation_zh']='相邻GT竖边3→4的延长线邻近，但实际线段零重叠；右侧范围截断位置仍取决于用户意图，不能宣称错误。'
        im['edges'][2]['interpretation_zh']='下边在重叠区向GT外侧偏移0.004138277–0.004141407h；约70%的底边投影覆盖GT 6→7，属于较明确可复核小偏移候选，尚不能确定为误操作。'
    if im['image_code']=='q9vSo1VnCiC-29':
        im['edges'][2]['interpretation_zh']='矩形上边25.6%的投影覆盖GT 6→7，其余向右延伸，是范围截断边，不是应拉回整段GT的证据。'

report=dict(audit_id='gt_edge_snap_audit_20261010',scope='Read-only audit of five imported confirmed floor regions; no confirmed geometry changed',
    source=dict(filename=SOURCE.name,sha256=sha256(raw),source_commit=data['source_commit'],editor_data_revision=data['editor_data_revision'],original_source_provenance=provenance,geometry_js_sha256=sha256((BASE/'fixtures/geometry_frozen.js').read_bytes())),
    units='camera_height_normalized_xz; h is camera height, not metres',
    method=dict(gt_conversion='Same ERP floor formula as geometry.js: odd-numbered 0-based entries; camera-height-normalized x,z',
        angle_parallel_threshold_deg=1,very_small_support_offset_threshold_h=0.0005,near_support_screen_threshold_fit_svg_px=20,thresholds_are_heuristics_not_semantic_judgments=True,screen_estimate='SVG viewBox pixels at initial fit and zoom=1; actual CSS/screenshot pixels and later zoom may differ',
        fit_scale_formula='max(x_extent/460, z_extent/390, 0.0001) over selected GT and confirmed polygon',
        distance='Signed perpendicular distances to exact selected GT supporting line; overlap is projection intersection with the finite GT segment',
        limitations=['Only five confirmed_review snapshots frozen from the original data.json, not newer browser-only drafts or confirmations.',
                    'Nearness cannot establish user intent; no proposed snap is approved.',
                    'Small deviations in axis-aligned rectangles are compatible with projecting slightly non-axis-aligned ERP-rounded GT into angle=0 rectangles; no attribution beyond geometry.',
                    'Supporting-line-only matches are separated from actual finite wall-segment overlap.',
                    'Top boundaries and formal reference eligibility are outside this audit.']),
    images=images,screenshot=dict(filename='fixtures/screenshot_q9vSo1VnCiC-12.png',sha256=provenance['screenshot_sha256'],observed_gt_vertices_px=screen,compared_candidate_count=len(fits),all_candidate_fits=fits,
        matching_method='Isotropic scale+translation fit to eight manually read labelled GT vertices; no draft coordinates reconstructed',top_matches=fits[:3],
        conclusion_zh='截图GT对应q9vSo1VnCiC-12；不是旧5份确认之一。截图本身不能给出用户当前草稿的精确坐标，也不能证明已确认。'),
    summary=dict(clearer_small_offset_candidates=[dict(image_code='pRbA3pwrgk9-02',manual_edge_1based=[3,4],gt_edge_1based=[6,7],status='requires_user_review_not_a_proven_error')],
        ambiguous_scope_cut_candidates=[dict(image_code='pRbA3pwrgk9-02',manual_edge_1based=[2,3],gt_edge_1based=[3,4],reason='near supporting line only; no finite segment overlap')],
        confirmed_geometry_modified=False))
(OUT/'audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
# Replay is independent of edge-offset calculations. This mirrors the frozen
# geometry.js cut/rectangle operations used by these five records.
def cross(a,b,p):
    return (b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0])

def clip(poly,a,b,side):
    out=[]
    for i,p in enumerate(poly):
        q=poly[(i+1)%len(poly)];fp=side*cross(a,b,p);fq=side*cross(a,b,q)
        ip=fp>=-1e-8;iq=fq>=-1e-8
        if ip:out.append(p[:])
        if ip!=iq:
            t=fp/(fp-fq);out.append([p[k]+t*(q[k]-p[k]) for k in range(2)])
    cleaned=[]
    for p in out:
        if not cleaned or math.dist(p,cleaned[-1])>1e-8:cleaned.append(p)
    if len(cleaned)>1 and math.dist(cleaned[-1],cleaned[0])<=1e-8:cleaned.pop()
    return cleaned

def replay(poly,operations):
    for op in operations:
        if op['type']=='cut':poly=clip(poly,op['a'],op['b'],op['side'])
        elif op['type']=='rectangle':
            rad=math.radians(op['angle']);u=[math.cos(rad),math.sin(rad)];v=[-u[1],u[0]]
            local=lambda p:[sum(p[k]*axis[k] for k in range(2)) for axis in [u,v]]
            x,y=local(op['a']),local(op['b'])
            poly=[[q[0]*u[k]+q[1]*v[k] for k in range(2)] for q in [[x[0],x[1]],[y[0],x[1]],[y[0],y[1]],[x[0],y[1]]]]
        else:raise ValueError('Unsupported frozen operation: '+op['type'])
    return poly

validation_rows=[]
for im in images:
    rep=replay(im['selected_gt_floor_xz_h'],im['operations']);p=im['confirmed_polygon_xz_h']
    if len(rep)!=len(p):raise AssertionError('Replay length mismatch: '+im['image_code'])
    err=max(math.dist(a,b) for a,b in zip(rep,p))
    if err>1e-9:raise AssertionError('Replay coordinate mismatch: '+im['image_code'])
    validation_rows.append(dict(image_code=im['image_code'],operations_replay_matches=True,max_vertex_error_h=err,confirmed_record_sha256=im['confirmed_record_sha256']))
assert SOURCE.read_bytes()==raw, 'Read-only source changed during audit'
assert sha256((BASE/'fixtures/geometry_frozen.js').read_bytes())==provenance['frozen_geometry_sha256']
assert sha256((BASE/'fixtures/screenshot_q9vSo1VnCiC-12.png').read_bytes())==provenance['screenshot_sha256']
validation=dict(confirmed_count=len(images),all_replays_match=True,read_only_audit=True,source_unchanged=True,
    fixture_confirmed_snapshots_match=True,screenshot_candidate_count=len(fits),
    all_original_eight_vertex_candidates_present=len(fits)==provenance['original_screenshot_candidate_count'],
    source_filename=SOURCE.name,source_sha256=sha256(raw),audit_json_sha256=sha256((OUT/'audit.json').read_bytes()),
    dependency='Python 3.9+ standard library only',results=validation_rows)
(OUT/'validation.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2)+'\n')
print('Audit complete: 5 unchanged confirmed snapshots; replay matches; '+str(len(fits))+' screenshot candidates. Output: '+str(OUT))
