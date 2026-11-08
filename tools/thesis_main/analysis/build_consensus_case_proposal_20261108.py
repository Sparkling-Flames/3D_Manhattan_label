"""Extract a saved complete-layout case and render a proposal outside the manuscript."""
from pathlib import Path
import gzip
import json

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from PIL import Image
from scipy.optimize import linear_sum_assignment
from shapely.geometry import mapping

from tools.thesis_main.analysis.audit_population_precision_geometry_20261025 import stream_array
from tools.thesis_main.analysis.consensus_delivery_20261008 import fuse
from tools.thesis_main.analysis.fusion_common_panel_20261024 import medoid
from tools.thesis_main.analysis.lee_tile_stage1_20261002 import tile_consensus
from tools.thesis_main.analysis.research_round_20260929 import reconstruct

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / 'research/workers/personnel_population_curves_v2_20261023'
OUT = ROOT / 'docs/thesis_main/论文写作工作资料/共识案例与正文改进待审_20261108'
TEAM = 'uNb9QFRL6hY-45__manual__5dc82190fe__91de328c92b39bc0d8b2'
WORKERS = 'W012 W015 W030 W032 W100 W101 W102 W123 W129 W134'.split()
BLUE, RED, GREEN, GRAY = '#16799b', '#b74736', '#377c55', '#555555'


def extract():
    with gzip.open(SOURCE / 'inputs/INPUT_SNAPSHOT.json.gz', 'rt', encoding='utf-8') as f:
        pool = next(p for p in json.load(f)['images'] if p['pool_id'] == TEAM.rsplit('__', 1)[0])
    records = [r for r in pool['records'] if r['worker_id'] in WORKERS]
    assert len(records) == len(set(WORKERS)) == 10
    selected_ids = {r['object_id'] for r in records}
    saved = next(g for g in stream_array(SOURCE / 'results/ENDPOINT_GEOMETRY.json.gz') if g['team_key'] == TEAM)
    rebuilt = fuse(records, gap=7.5)['automatic']
    automatic = rebuilt['candidate']
    assert np.allclose(automatic['points'], saved['geometry']['points'], atol=1e-9, rtol=0)
    assert len(automatic['points']) == len(pool['reference']['points_1024x512']) == 12
    def rays(points):
        p=np.asarray(points);u=p[:,0]*2*np.pi/1024;v=(p[:,1]/512-.5)*np.pi
        return np.column_stack((np.cos(v)*np.sin(u),np.sin(v),np.cos(v)*np.cos(u)))
    a=rays(automatic['points']);b=rays(pool['reference']['points_1024x512'])
    bottom=np.degrees(np.arccos(np.clip(a[1::2]@b[1::2].T,-1,1)))
    top=np.degrees(np.arccos(np.clip(a[::2]@b[::2].T,-1,1)))
    ri,rj=linear_sum_assignment(bottom+top)
    assert len(ri)==6 and max(bottom[ri,rj].max(),top[ri,rj].max())<1
    steps=(np.roll(rj,-1)-rj)%6
    assert np.all(steps==1) or np.all(steps==5)
    representative, rep_polygon, exclusions, _ = medoid(records)
    assert representative['object_id'] == '88b2b69f04caf44309bc' and len(representative['points']) == 8
    assert not exclusions
    sources = []
    for r in records:
        floor = reconstruct(r, coordinate_convention='continuous')['floor']
        sources.append(dict(id=r['object_id'], worker=r['worker_id'], footprint=np.asarray(floor).tolist()))
    region = tile_consensus(sources)['regions']['mv50']
    groups = []
    for group in rebuilt['identity_groups']:
        if not group['selected']:
            continue
        members = group['members']
        assert len({m['worker'] for m in members}) == group['support']
        assert {m['id'] for m in members} <= selected_ids
        groups.append(dict(feature_id=group['feature_id'], support=group['support'],
                           in_medoid=any(m['id'] == representative['id'] for m in members), members=members))
    missing = [g for g in groups if not g['in_medoid']]
    assert len(missing) == 2 and all(g['support'] == 7 for g in missing)
    assert all(g['support'] > len(records)/2 for g in groups)
    result = dict(team_key=TEAM, source='frozen_v2_saved_endpoint', meta=pool['meta'],
                  workers=WORKERS, records=records, reference=pool['reference'],
                  consensus=saved['geometry'], selected_groups=groups,
                  reference_alignment=dict(reference_indices=rj.tolist(),bottom_angles_deg=bottom[ri,rj].tolist(),
                                           top_angles_deg=top[ri,rj].tolist(),same_cyclic_order=True),
                  medoid=dict(worker=representative['worker_id'], object_id=representative['object_id'],
                              points=representative['points'], footprint=list(rep_polygon.exterior.coords)),
                  bev_region=mapping(region), sources=sources,
                  baseline_note='Medoid and BEV computed for the same saved team with the existing implementations.',
                  check='Saved consensus reproduced; ten exact members; two missing medoid identities each supported by seven people.')
    return result, region


def draw(data, region):
    plt.rcParams.update({'font.family':'DejaVu Sans', 'font.size':10, 'axes.titlesize':11})
    fig = plt.figure(figsize=(14,8.3), layout='constrained')
    gs = fig.add_gridspec(2,3, height_ratios=[1,1.15])
    ax = fig.add_subplot(gs[0,:2])
    photo = Image.open(ROOT / 'data/mp3d_layout/test/img' / (data['meta']['image_id']+'.png'))
    ax.imshow(photo, extent=(0,1024,512,0))
    ref = np.array(data['reference']['points_1024x512'])
    pts = np.array(data['consensus']['points'])
    features = data['consensus']['feature_ids']
    groups = {g['feature_id']:g for g in data['selected_groups']}
    labels = {fid:chr(65+i) for i,fid in enumerate(features)}
    for i,fid in enumerate(features):
        pair = pts[2*i:2*i+2]
        ax.plot(*pair.T, color=BLUE, lw=1)
        ax.scatter(*pair.T, s=24, color=BLUE, edgecolors='white', linewidths=.5)
        if not groups[fid]['in_medoid']:
            offset=(-55,35) if labels[fid]=='E' else (8,-35)
            ax.annotate(f"{labels[fid]}: 7/10", pair[0], xytext=offset, textcoords='offset points',
                        color='white', weight='bold', arrowprops=dict(arrowstyle='-',color='white'),
                        bbox=dict(fc=BLUE, ec='none', alpha=.9))
        else:
            ax.annotate(labels[fid],pair[0],xytext=(5,-6),textcoords='offset points',color='white',weight='bold',
                        bbox=dict(fc=BLUE,ec='none',alpha=.85,pad=2))
    detail=ax.inset_axes([.02,.03,.18,.38])
    local=np.vstack([pts[2*i:2*i+2] for i,fid in enumerate(features) if not groups[fid]['in_medoid']])
    detail.imshow(photo,extent=(0,1024,512,0));detail.scatter(*local.T,s=24,color=BLUE,edgecolors='white',linewidths=.7)
    top_local=local[::2]
    detail.set(xlim=(local[:,0].min()-13,local[:,0].max()+13),
               ylim=(top_local[:,1].max()+38,top_local[:,1].min()-12),xticks=[],yticks=[])
    detail.set_title('E / F detail',fontsize=9,color=BLUE,pad=2)
    ax.set(xlim=(0,1024), ylim=(512,0)); ax.axis('off')
    ax.set_title('(a) Panorama and retained corner pairs', loc='left')
    ledger=fig.add_subplot(gs[0,2]); ledger.axis('off')
    rows=[[labels[fid], f"{groups[fid]['support']}/10", 'Yes' if groups[fid]['in_medoid'] else 'No'] for fid in features]
    table=ledger.table(cellText=rows,colLabels=['Corner','Support','In medoid'],loc='center',cellLoc='center')
    table.scale(1,1.7); table.auto_set_font_size(False);table.set_fontsize(11)
    for i,fid in enumerate(features,1):
        if not groups[fid]['in_medoid']:
            for j in range(3):table[i,j].set_facecolor('#e4f0f4')
    ledger.set_title('(b) Support from the same ten people',loc='left')
    rf=np.array(data['reference']['floor_xz_h']); cf=np.array(data['consensus']['footprint'])
    arrays=[rf,cf,np.array(data['medoid']['footprint'])]
    parts=list(region.geoms) if region.geom_type=='MultiPolygon' else [region]
    arrays += [np.array(p.exterior.coords) for p in parts]
    allpts=np.vstack(arrays); lo=allpts.min(axis=0)-.18;hi=allpts.max(axis=0)+.18
    for col,title,color in [(0,'(c) Medoid: four corners',RED),(1,'(d) Structural consensus: six corners',BLUE),(2,'(e) BEV majority voting',GREEN)]:
        a=fig.add_subplot(gs[1,col])
        rclosed=np.vstack([rf,rf[0]])
        a.plot(*rclosed.T,'--',color=GRAY,lw=1.5,label='Adopted reference')
        if col<2:
            p=arrays[col+2] if col==0 else cf
            p=np.vstack([p,p[0]])
            a.plot(*p.T,color=color,lw=2,label='Method output'); a.scatter(*p[:-1].T,color=color,s=22,zorder=5)
        else:
            for j,p in enumerate(parts):
                a.plot(*p.exterior.xy,color=color,lw=2,label='Method output' if j==0 else None)
                for hole in p.interiors:a.plot(*hole.xy,color=color,lw=1)
        for i,fid in enumerate(features):
            a.annotate(labels[fid], cf[i], xytext=(7,6),textcoords='offset points',color=BLUE,weight='bold')
        a.set(xlim=(lo[0],hi[0]),ylim=(lo[1],hi[1]),xlabel='x / camera height',ylabel='z / camera height')
        a.set_aspect('equal',adjustable='box');a.grid(alpha=.15);a.set_title(title,loc='left')
        if col==0:a.legend(loc='upper left',fontsize=8)
    fig.suptitle('uNb9QFRL6hY-45 | One saved ten-person team | Two shared turns absent from the medoid',fontsize=14)
    fig.savefig(OUT/'共识保留完整结构_uNb45_10人.png',dpi=180)
    plt.close(fig)


def semi_case():
    """Check the model file, deployed payload and raw submissions without assigning new error labels."""
    evidence=pd.read_csv(ROOT/'research/workers/worker_v1_pro_integration_20261017/initialization_evidence.csv').set_index('object_id')
    review=pd.read_csv(ROOT/'research/workers/worker_v1_pro_integration_20261017/semi_correction_evidence.csv').set_index('object_id')
    proposals=pd.read_csv(ROOT/'analysis_results/uncertainty_cloud_inputs_20260906_v1/facts/proposal_response.csv.gz').set_index('canonical_annotation_id')
    ids=['1d9605edabc41fe8','f2652a9524294607','31d3caf93d1b2b79']
    image_id='e9zR4mvMWw7_f7ab5b3ece274b48be57eb65bb6d4814'
    model_path=ROOT/'output/mp3d_layout/HOHO_layout_aug_efficienthc_Transen1_resnet34'/f'{image_id}.txt'
    model=np.loadtxt(model_path)
    submissions=[]
    for oid in ids:
        ev=evidence.loc[oid];p=proposals.loc[oid];r=review.loc[oid]
        assert ev.runtime_initialization_kind=='natural_trap' and ev.initialization_source_verified
        assert np.array_equal(model,np.array(json.loads(p.initial_points_json)))
        assert np.array_equal(model,np.array(json.loads(p.final_points_json)))
        runtime=json.loads((ROOT/ev.runtime_source).read_text(encoding='utf-8-sig'))
        task=next(t for t in runtime if t['id']==int(ev.runtime_task))
        answer=next(a for a in task['annotations'] if a['id']==int(ev.runtime_annotation))
        raw=np.array([[v['value']['x']*10.24,v['value']['y']*5.12] for v in answer['result'] if v.get('type')=='keypointlabels'])
        assert np.allclose(raw,model,rtol=0,atol=1e-9)
        found=0
        for path in json.loads(ev.import_paths):
            for task in json.loads((ROOT/path).read_text(encoding='utf-8-sig')):
                if task.get('data',{}).get('base_task_id')!=image_id:continue
                assert task['data']['source_type']=='trap_natural'
                assert task['data']['proposal_source_kind']=='model_output_txt'
                for prediction in task.get('predictions',[]):
                    pts=np.array([[v['value']['x']*10.24,v['value']['y']*5.12] for v in prediction['result'] if v.get('type')=='keypointlabels'])
                    assert np.allclose(pts,model,rtol=0,atol=1e-9);found+=1
        assert found
        submissions.append(dict(object_id=oid,worker=ev.worker_id,task=int(ev.runtime_task),annotation=int(ev.runtime_annotation),
                                runtime_source=ev.runtime_source,import_paths=json.loads(ev.import_paths),
                                annotation_comments=json.loads(r.source_comments_verified),unchanged=True))
    data=dict(image='e9zR4mvMWw7-39',image_id=image_id,initialization_kind='natural_model_output_selected_as_trap',
              model_file=str(model_path.relative_to(ROOT)),points=model.tolist(),submissions=submissions,
              evidence='Exact model, deployment and raw-submission equality; archived annotation comments identify model errors.',
              boundary='A selected case, separate from the 156 expert-confirmed synthetic-error opportunities; no new expert defect labels.')
    (OUT/'Semi自然模型初始化_e9z39_来源.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    fig=plt.figure(figsize=(13,6.5),layout='constrained');gs=fig.add_gridspec(2,3,height_ratios=[1,.8])
    photo=Image.open(ROOT/'data/mp3d_layout/test/img'/f'{image_id}.png')
    a=fig.add_subplot(gs[0,:2]);a.imshow(photo,extent=(0,1024,512,0))
    for pair in model.reshape(-1,2,2):a.plot(*pair.T,color=RED,lw=.8)
    a.scatter(*model.T,s=15,c=RED,edgecolors='white',linewidths=.5)
    a.axis('off');a.set_title('(a) Deployed model initialization and unchanged submissions',loc='left')
    t=fig.add_subplot(gs[0,2]);t.axis('off')
    table=t.table(cellText=[[r['worker'],'8','Unchanged'] for r in submissions],
                  colLabels=['Annotator','Pairs','Submission'],cellLoc='center',loc='center')
    table.scale(1,1.7);table.auto_set_font_size(False);table.set_fontsize(10)
    t.set_title('(b) Three source-verified responses',loc='left')
    for col,(xlim,ylim,title) in enumerate([((530,605),(70,180),'(c) Upper endpoint detail'),((750,820),(0,180),'(d) Upper endpoint detail'),((750,820),(410,512),'(e) Lower endpoint detail')]):
        a=fig.add_subplot(gs[1,col]);a.imshow(photo,extent=(0,1024,512,0));a.scatter(*model.T,s=35,c=RED,edgecolors='white',linewidths=.8)
        a.set(xlim=xlim,ylim=ylim[::-1],xlabel='Panorama u (px)',ylabel='Panorama v (px)');a.set_title(title,loc='left')
    fig.suptitle('e9zR4mvMWw7-39 | Natural model output selected for review | Initial geometry retained at submission',fontsize=13)
    fig.savefig(OUT/'Semi自然模型初始化保留_e9z39.png',dpi=180);plt.close(fig)
    print('Semi model / deployed / raw submission checks passed for three records')


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    data, region=extract()
    (OUT/'uNb45_10人_来源与几何.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    draw(data,region)
    semi_case()
    print(json.dumps({'case':TEAM,'checks':'passed','figure':str(OUT/'共识保留完整结构_uNb45_10人.png')},ensure_ascii=False))


if __name__=='__main__':
    main()
