"""Trace missing full references to containment checks; do not change formal inputs."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from shapely.geometry import Polygon
from tools.label_studio.panorama_studio.geometry import project_pixel
from .scope_reference_reconstruction_20261016 import geometry, floor

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'research/data/scope_quality_rescore_20261016/vertical_cut_audit_20261028'


def main():
    OUT.mkdir(exist_ok=True)
    refs=json.loads((ROOT/'research/quality/quality_workers_v2_20261019/reference_catalog.json').read_text(encoding='utf-8'))
    lookup={r['target_id']:r for r in refs}
    scope=pd.read_csv(ROOT/'research/statistics/external_review_response_20261028/MULTISPACE_41_COVERAGE.csv')
    missing=scope[scope.target_full_status.eq('unavailable')]
    assert len(missing)==29
    rows=[];polygons=[];candidates=[]
    for r in missing.itertuples():
        ref=lookup[r.target_id];p=Polygon(ref['floor_xz_h'])
        attempts=ref['evidence']['constructions'];assert len(attempts)==1
        a=attempts[0];source=lookup[a['source_reference_id']];s=Polygon(source['floor_xz_h'])
        outside=p.difference(s).area
        assert p.is_valid and s.is_valid
        np.testing.assert_allclose(outside,a['result']['outside_source_area_h2'],atol=1e-8)
        plane=a['source_plane'];assert plane is not None
        raw=plane['source_json_geometry'];points=raw['layoutPoints']['points']
        rad=np.linalg.norm(np.array([x['xyz'] for x in points])[:,[0,2]],axis=1)/raw['cameraHeight']
        az=(np.array([x['coords'][0] for x in points])-.5)*2*np.pi
        unrounded=Polygon(np.column_stack([rad*np.sin(az),-rad*np.cos(az)]))
        assert unrounded.is_valid
        ratio=outside/p.area
        # 候选保留用户底面；是否可把原顶平面延续到旧GT之外，另作空间语义确认。
        bottom=np.asarray(ref['floor_xz_h'],float)
        aa,bb,cc=plane['plane']
        heights=aa*bottom[:,0]+bb*bottom[:,1]+cc
        assert np.isfinite(heights).all() and (heights>0).all()
        pixels=[]
        for (x,z),height in zip(bottom,heights):
            pixels.extend([project_pixel([x,height,z],1024,512),project_pixel([x,-1,z],1024,512)])
        np.testing.assert_allclose(floor(pixels),bottom,atol=1e-8)
        np.testing.assert_allclose(np.asarray(geometry(pixels)['top3d'])[:,1],heights,atol=1e-8)
        candidates.append(dict(image=r.image,target_id=r.target_id,
            status='candidate_only_not_formal',construction='confirmed_floor_with_inherited_source_ceiling_plane',
            source_reference_id=a['source_reference_id'],source_plane=plane,
            floor_xz_h=bottom.tolist(),points_1024x512=pixels,geometry=geometry(pixels),
            outside_source_percent=ratio*100,physical_wall_asserted=False))
        rows.append(dict(image=r.image,target_id=r.target_id,source_reference_id=a['source_reference_id'],
            target_area_h2=p.area,outside_area_h2=outside,outside_percent=ratio*100,
            outside_unrounded_source_percent=p.difference(unrounded).area/p.area*100,
            max_distance_to_intersection_h=p.hausdorff_distance(p.intersection(s)),
            explicit_ceiling_plane=True,plane_height_h=plane['plane'][2],
            diagnostic_band='below_0.01_percent' if ratio<1e-4 else 'above_0.01_percent',
            old_reason=ref['minimal_gap']))
        polygons.append((r.image,p,s,ratio*100))
    df=pd.DataFrame(rows);df.to_csv(OUT/'MISSING29_GEOMETRY_DIAGNOSIS.csv',index=False,encoding='utf-8-sig')
    (OUT/'CANDIDATE_REFERENCES.json').write_text(json.dumps(candidates,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams['font.sans-serif']=['Microsoft YaHei','SimHei','DejaVu Sans']
    plt.rcParams['axes.unicode_minus']=False
    fig,axes=plt.subplots(6,5,figsize=(15,17),layout='constrained')
    for ax,(name,p,s,ratio) in zip(axes.flat,polygons):
        ax.fill(*s.exterior.xy,color='#dce6ee',alpha=.65)
        ax.plot(*s.exterior.xy,color='#526b83',lw=1.4)
        ax.plot(*p.exterior.xy,color='#d47113',lw=1.6,ls='--')
        ax.scatter([0],[0],c='#222222',s=8)
        ax.set_title(f'{name}\n越界 {ratio:.5f}%',fontsize=9)
        ax.set_aspect('equal');ax.tick_params(labelsize=7)
    axes.flat[-1].axis('off')
    fig.suptitle('29图底面范围核对：灰蓝为完整源参考，橙虚线为已确认新范围\n黑点为相机拍摄点位；越界比例仅用于诊断，未修改参考或资格',fontsize=14)
    fig.savefig(OUT/'29图范围对照.png',dpi=160);plt.close(fig)
    receipt=dict(images=len(df),explicit_plane=int(df.explicit_ceiling_plane.sum()),diagnostic_bands=df.diagnostic_band.value_counts().to_dict(),candidate_references=len(candidates),candidate_floor_and_height_roundtrip=True,formal_reference_changes=0,new_scores=0)
    (OUT/'CHECKS.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(receipt,ensure_ascii=False));print(df.groupby('diagnostic_band').outside_percent.agg(['min','max']).to_string())


if __name__=='__main__':main()
