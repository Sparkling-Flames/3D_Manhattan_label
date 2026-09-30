"""Independent ray reconstruction. +Y up; camera origin; relative height 1.

Raw top endpoints use their own ray and their paired floor's horizontal range.
That range is a proxy, not observed ceiling depth. No coordinate writeback.
"""
from __future__ import annotations
import json
import math
from pathlib import Path
import numpy as np
from scipy.linalg import null_space
from scipy.optimize import minimize, minimize_scalar
from shapely.geometry import Point, Polygon

SCHEMA = "panorama_studio_v1"
HORIZON_DEG = 0.5  # Numerical guard, not an annotation-quality threshold.


def pixel_ray(x, y, width, height, *, coordinate_convention="continuous"):
    if coordinate_convention not in {"continuous", "pixel_center"}:
        raise ValueError("unknown_coordinate_convention")
    if coordinate_convention == "pixel_center": x,y=x+.5,y+.5
    u, v = 2*math.pi*(x/width-.5), math.pi*(.5-y/height)
    return np.array([math.cos(v)*math.sin(u), math.sin(v), -math.cos(v)*math.cos(u)])


def project_pixel(point, width, height, *, coordinate_convention="continuous"):
    if coordinate_convention not in {"continuous", "pixel_center"}:
        raise ValueError("unknown_coordinate_convention")
    offset=.5 if coordinate_convention=="pixel_center" else 0
    x,y,z = point
    return [((math.atan2(x,-z)/(2*math.pi)+.5)*width % width)-offset,
            (.5-math.atan2(y,math.hypot(x,z))/math.pi)*height-offset]


def read_layout(path, width=1024, height=512):
    path = Path(path)
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(payload,dict):
            raise ValueError("JSON needs explicit width, height, coordinate_mode, ordered_pairs")
        return payload
    points = np.loadtxt(path,ndmin=2)
    if points.shape[1] != 2 or len(points)%2 or len(points)<6:
        raise ValueError("TXT needs an even number of ceiling/floor XY rows, at least six")
    return {"width":width,"height":height,"coordinate_mode":"pixels",
            "ordered_pairs":[{"source_pair_id":str(i//2+1),
                "top":dict(zip(("x","y"),points[i].tolist())),
                "bottom":dict(zip(("x","y"),points[i+1].tolist()))} for i in range(0,len(points),2)]}


def normalize(payload, *, coordinate_convention="continuous"):
    w,h = float(payload["width"]),float(payload["height"])
    if not all(math.isfinite(v) and v>0 for v in [w,h]):
        raise ValueError("width and height must be finite and positive")
    mode = payload["coordinate_mode"]
    if mode not in {"pixels","vis_pixels","ls_percent"}:
        raise ValueError("coordinate_mode must be explicit pixels or ls_percent")
    pairs = []
    for i,item in enumerate(payload["ordered_pairs"]):
        pair = {"source_pair_id":str(item.get("source_pair_id",i+1)),"display_index":i+1}
        for endpoint in ["top","bottom"]:
            x,y = float(item[endpoint]["x"]),float(item[endpoint]["y"])
            if mode=="ls_percent": x,y=x*w/100,y*h/100
            if not all(math.isfinite(v) for v in [x,y]): raise ValueError("coordinates must be finite")
            offset=.5 if coordinate_convention=="pixel_center" else 0
            if not (0<=x+offset<=w and 0<=y+offset<=h): raise ValueError("coordinates outside declared image bounds")
            pair[endpoint]=[x,y]
        pairs.append(pair)
    if len(pairs)<3: raise ValueError("at least three ordered pairs required")
    if len({p["source_pair_id"] for p in pairs})!=len(pairs): raise ValueError("duplicate source pair identity")
    return w,h,pairs


def cross(a,b):
    return a[0]*b[1]-a[1]*b[0]


def triangulate(points):
    """Ear clipping; source indices retained, including collinear wall endpoints."""
    p=np.asarray(points,float)
    poly=Polygon(p)
    if not poly.is_valid or poly.area<1e-10: return []
    ids=list(range(len(p)))
    if sum(cross(p[i],p[(i+1)%len(p)]) for i in ids)<0: ids.reverse()
    triangles=[]
    eps=max(1,np.ptp(p,axis=0).max()**2)*1e-10
    while len(ids)>3:
        found=False
        for k,b in enumerate(ids):
            a,c=ids[k-1],ids[(k+1)%len(ids)]
            turn=cross(p[b]-p[a],p[c]-p[b])
            if abs(turn)<=eps:
                ids.pop(k); found=True; break
            if turn<0: continue
            def inside(j):
                return min(cross(p[b]-p[a],p[j]-p[a]),cross(p[c]-p[b],p[j]-p[b]),
                           cross(p[a]-p[c],p[j]-p[c]))>=-eps
            if any(inside(j) for j in ids if j not in {a,b,c}): continue
            triangles.append([a,b,c]); ids.pop(k); found=True; break
        if not found: return []
    triangles.append(ids)
    return triangles


def footprint_state(points, *, boundary_tolerance=1e-12):
    """几何、相机位置和可见核分别诊断；数值 guard 不作为审核裁决。"""
    p=np.asarray(points,float)
    issues=[]
    if p.ndim!=2 or p.shape[1:]!=(2,) or len(p)<3 or not np.isfinite(p).all():
        return dict(polygon_valid=False,issues=["invalid_footprint"],
                    camera_relation="unavailable",camera_in_visible_kernel=None)
    if np.min(np.linalg.norm(p-np.roll(p,1,axis=0),axis=1))<1e-7:
        issues.append("duplicate_or_zero_edge")
    poly=Polygon(p)
    if not poly.is_valid or poly.area<1e-8:
        return dict(polygon_valid=False,issues=issues+["invalid_footprint"],
                    camera_relation="unavailable",camera_in_visible_kernel=None)
    origin=Point(0,0)
    # 射线往返的舍入误差；只判断数值上的边界，不是人员质量阈值。
    on_boundary=not issues and boundary_tolerance>0 and poly.boundary.distance(origin)<=boundary_tolerance*max(1,np.linalg.norm(p,axis=1).max())
    relation="boundary" if on_boundary else "inside" if poly.contains(origin) else "boundary" if poly.covers(origin) else "outside"
    orientation=1 if sum(cross(p[i],p[(i+1)%len(p)]) for i in range(len(p)))>0 else -1
    kernel=relation=="inside" and all(orientation*cross(p[(i+1)%len(p)]-p[i],-p[i])>=-1e-7
                                     for i in range(len(p)))
    return dict(polygon_valid=not issues,issues=issues,camera_relation=relation,
                camera_in_visible_kernel=bool(kernel))


def geometry_issues(points):
    """历史合并诊断，保留原消费者及拟合行为。"""
    state=footprint_state(points,boundary_tolerance=0)  # 历史精确contains判定保持不变。
    issues=list(state['issues'])
    if state['camera_relation']!='unavailable' and not state['camera_in_visible_kernel']:
        issues.append("camera_visibility_unresolved")
    return issues


def heading_frame(points):
    edges=np.roll(points,-1,axis=0)-points
    angles=np.arctan2(edges[:,1],edges[:,0]); lengths=np.linalg.norm(edges,axis=1)
    def objective(theta):
        residual=(angles-theta+math.pi/4)%(math.pi/2)-math.pi/4
        return float(np.average(residual**2,weights=lengths))
    grid=np.linspace(0,math.pi/2,181,endpoint=False)
    best=grid[min(range(len(grid)),key=lambda i:objective(grid[i]))]
    result=minimize_scalar(objective,bounds=(best-math.pi/180,best+math.pi/180),
                           method="bounded",options={"xatol":1e-12})
    return float(result.x%(math.pi/2))


def metrics(floor,ceiling,frame):
    p=np.asarray(floor)[:,[0,2]]
    edges=np.roll(p,-1,axis=0)-p
    angles=np.arctan2(edges[:,1],edges[:,0])
    residual=np.abs((angles-frame+math.pi/4)%(math.pi/2)-math.pi/4)
    height=np.asarray(ceiling)[:,1]+1
    return {"heading_frame_deg":math.degrees(frame),"heading_mean_deg":float(np.degrees(residual).mean()),
            "heading_max_deg":float(np.degrees(residual).max()),
            "height_relative_spread":float(np.ptp(height)/max(np.median(height),1e-8))}


def angular_errors(points,rays):
    unit=points/np.linalg.norm(points,axis=1)[:,None]
    return np.arctan2(np.linalg.norm(np.cross(unit,rays),axis=1),np.sum(unit*rays,axis=1))


def fit_manhattan(floor,ceiling,pairs,w,h,frame, *, coordinate_convention="continuous"):
    p=np.asarray(floor)[:,[0,2]]; n=len(p)
    basis=np.array([[math.cos(frame),math.sin(frame)],[-math.sin(frame),math.cos(frame)]])
    local=p@basis.T; edges=np.roll(local,-1,axis=0)-local
    direction=np.argmax(abs(edges),axis=1)
    residual=np.degrees(np.arctan2(np.min(abs(edges),axis=1),np.max(abs(edges),axis=1)))
    if np.any(residual>=40): return {"status":"blocked","reasons":["ambiguous_axis_assignment"]}
    constraints=np.zeros((n,2*n))
    for i,axis in enumerate(direction):
        constraints[i,2*i+1-axis]=1
        constraints[i,2*((i+1)%n)+1-axis]=-1
    # Exact equalities in a null-space basis avoid redundant constraints at collinear corners.
    kernel=null_space(constraints)
    start=np.r_[kernel.T@local.ravel(),max(.05,float(np.median(np.array(ceiling)[:,1])))]
    top_rays=np.array([pixel_ray(*pair["top"],w,h,coordinate_convention=coordinate_convention) for pair in pairs])
    bottom_rays=np.array([pixel_ray(*pair["bottom"],w,h,coordinate_convention=coordinate_convention) for pair in pairs])
    signs=np.sign(edges[np.arange(n),direction])
    def decode(v):
        coords=(kernel@v[:-1]).reshape(n,2); world=coords@basis
        return coords,np.c_[world[:,0],np.full(n,-1.),world[:,1]],np.c_[world[:,0],np.full(n,v[-1]),world[:,1]]
    def errors(v):
        _,f,c=decode(v)
        return np.r_[angular_errors(c,top_rays),angular_errors(f,bottom_rays)]
    def ordered_edges(v):
        coords,_,_=decode(v)
        return (np.roll(coords,-1,axis=0)-coords)[np.arange(n),direction]*signs-1e-6
    result=minimize(lambda v:float(np.mean(errors(v)**2)),start,method="SLSQP",
                    bounds=[(None,None)]*(len(start)-1)+[(1e-5,None)],
                    constraints=[{"type":"ineq","fun":ordered_edges}],options={"ftol":1e-12,"maxiter":500})
    _,f,c=decode(result.x)
    issues=geometry_issues(f[:,[0,2]])
    if not result.success or issues or np.min(ordered_edges(result.x)) < -1e-7:
        return {"status":"blocked","reasons":issues or ["optimizer_failed"],"solver_message":str(result.message)}
    dev=np.degrees(errors(result.x))
    return {"status":"ok","floor":f.tolist(),"ceiling":c.tolist(),
            "floor_triangles":triangulate(f[:,[0,2]]),"ceiling_triangles":triangulate(c[:,[0,2]]),
            "reprojected_pairs":[{"source_pair_id":pair["source_pair_id"],"top":project_pixel(c[i],w,h,coordinate_convention=coordinate_convention),
                                  "bottom":project_pixel(f[i],w,h,coordinate_convention=coordinate_convention)} for i,pair in enumerate(pairs)],
            "residual_mean_deg":float(dev.mean()),"residual_max_deg":float(dev.max()),
            "per_pair_residual_deg":[{"top":float(dev[i]),"bottom":float(dev[i+n])} for i in range(n)],
            "metrics":metrics(f,c,frame),"solver_message":str(result.message),
            "axis_assignment":direction.tolist(),"iterations":int(result.nit)}


def analyze(payload, *, compute_fit=True, coordinate_convention="continuous"):
    if coordinate_convention not in {"continuous", "pixel_center"}:
        raise ValueError("unknown_coordinate_convention")
    w,h,pairs=normalize(payload,coordinate_convention=coordinate_convention)
    floor,ceiling,issues=[],[],[]
    declared_floor,bottom_issues=[],[]
    bottom_margins,top_margins=[],[]
    for pair in pairs:
        top,bottom=pair["top"],pair["bottom"]
        rt,rf=[pixel_ray(*p,w,h,coordinate_convention=coordinate_convention) for p in (top,bottom)]
        bm,tm=abs(math.asin(rf[1])),abs(math.asin(rt[1]))
        bottom_margins.append(math.degrees(bm));top_margins.append(math.degrees(tm))
        # 独立底点重建：墙顶不可用不使已声明足迹同时丢失。
        bottom_reason="wrong_hemisphere" if rf[1]>=0 else "near_horizon" if bm<math.radians(HORIZON_DEG) else None
        declared_floor.append(None if bottom_reason else (-rf/rf[1]).tolist())
        if bottom_reason: bottom_issues.append(bottom_reason)
        if abs((top[0]-bottom[0]+w/2)%w-w/2)>1e-6: issues.append("vertical_pair_mismatch")
        if rf[1]>=0 or rt[1]<=0:
            issues.append("wrong_hemisphere"); floor.append(None); ceiling.append(None); continue
        if min(abs(math.asin(rf[1])),abs(math.asin(rt[1])))<math.radians(HORIZON_DEG):
            issues.append("near_horizon"); floor.append(None); ceiling.append(None); continue
        f=-rf/rf[1]; horizontal=np.linalg.norm(rt[[0,2]])
        if horizontal<1e-8:
            issues.append("pole_ray"); floor.append(f.tolist()); ceiling.append(None); continue
        c=rt*(np.linalg.norm(f[[0,2]])/horizontal)
        floor.append(f.tolist()); ceiling.append(c.tolist())
    raw={"floor":floor,"ceiling":ceiling,"floor_triangles":[],"ceiling_triangles":[]}
    if all(p is not None for p in floor+ceiling):
        footprint=np.array(floor)[:,[0,2]]; issues.extend(geometry_issues(footprint))
        raw["floor_triangles"]=triangulate(footprint)
        raw["ceiling_triangles"]=triangulate(np.array(ceiling)[:,[0,2]])
        frame=heading_frame(footprint) if not any(i in issues for i in ["invalid_footprint","duplicate_or_zero_edge"]) else None
        raw["metrics"]=metrics(floor,ceiling,frame) if frame is not None else None
    else:
        frame=None; raw["metrics"]=None
    raw["issues"]=list(dict.fromkeys(issues))
    blockers=[i for i in raw["issues"] if i!="vertical_pair_mismatch"]
    raw["surface_valid"]=not any(i!="camera_visibility_unresolved" for i in blockers)
    state=footprint_state(np.array(declared_floor)[:,[0,2]]) if not bottom_issues else dict(
        polygon_valid=None,issues=list(dict.fromkeys(bottom_issues)),
        camera_relation="unavailable",camera_in_visible_kernel=None)
    footprint_reason=';'.join(state['issues']) or None
    wall_reason=footprint_reason or ';'.join(i for i in raw['issues'] if i!='camera_visibility_unresolved') or None
    if not wall_reason and state['camera_relation']!='inside': wall_reason='camera_not_strictly_inside'
    raw.update(declared_floor=declared_floor,**{k:v for k,v in state.items() if k!='issues'},
        bottom_horizon_margin_deg=min(bottom_margins),top_horizon_margin_deg=min(top_margins),
        representations={
            'declared_footprint':dict(status='unavailable' if footprint_reason else 'ok',reason=footprint_reason),
            'declared_column_wall_band':dict(status='unavailable' if wall_reason else 'ok',reason=wall_reason)})
    fit=({"status":"not_requested"} if not compute_fit else
         {"status":"blocked","reasons":blockers} if blockers else fit_manhattan(floor,ceiling,pairs,w,h,frame,coordinate_convention=coordinate_convention))
    return {"schema_version":SCHEMA,"width":w,"height":h,"pairs":pairs,"raw":raw,"fit":fit,
            "camera_height":1,"scale_unit":"relative","coordinate_convention":coordinate_convention,
            "assumptions":["horizontal_floor","ceiling_range_from_paired_floor","no_annotation_writeback"],
            "numerical_guards":{"horizon_degrees":HORIZON_DEG,"axis_ambiguity_degrees":40}}
