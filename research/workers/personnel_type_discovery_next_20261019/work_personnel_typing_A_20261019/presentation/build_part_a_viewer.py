"""Self-contained Part A viewer: frozen whole pools, learned labels, exact cases.

No classification, fusion or case selection is performed here. Geometric canvas
projection functions are reused from the archived Pro viewer.
"""
from pathlib import Path
import argparse,base64,csv,gzip,hashlib,io,json,math,re,time
import numpy as np
import pandas as pd
from PIL import Image

HERE=Path(__file__).resolve().parent
WORK=HERE.parent
OLD=WORK/'recovered/work_v2_20261019'
REPO=WORK/'recovered/repo_main_20261019'

def load(p):
    with (gzip.open(p,'rt',encoding='utf-8') if str(p).endswith('.gz') else open(p,encoding='utf-8')) as f:return json.load(f)
def clean(x):
    if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [clean(v) for v in x]
    if isinstance(x,np.generic):return clean(x.item())
    if isinstance(x,float) and not math.isfinite(x):return None
    return x
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dumps(x):return json.dumps(clean(x),ensure_ascii=False,separators=(',',':'),allow_nan=False)

def projection_code():
    src=(OLD/'presentation/viewer_template.html').read_text()
    part=src[src.index('function geometry('):src.index('function pathPlot(')]
    original_hash=hashlib.sha256(part.encode()).hexdigest()
    a=part.index('function imageFor(');b=part.index('async function drawERP(',a)
    part=part[:a]+"function imageFor(id){let record=D.images[id];if(!record?.data)return Promise.resolve(null);if(!imageCache.has(id)){let im=new Image(),p=new Promise(resolve=>{im.onload=()=>resolve(im);im.onerror=()=>resolve(null)});im.src=record.data;imageCache.set(id,p)}return imageCache.get(id)}\n"+part[b:]
    old="if(im)ctx.drawImage(im,0,0,1024,512);for(let l of layers)"
    new="if(im)ctx.drawImage(im,0,0,1024,512);else{ctx.strokeStyle='#31515c';ctx.lineWidth=.5;ctx.beginPath();for(let x=0;x<=1024;x+=128){ctx.moveTo(x,0);ctx.lineTo(x,512)}for(let y=0;y<=512;y+=64){ctx.moveTo(0,y);ctx.lineTo(1024,y)}ctx.stroke();ctx.font='14px PartACJK,sans-serif';ctx.fillStyle='#b3ccd3';ctx.fillText('本页未嵌入该图原图 · 仅显示冻结几何投影',16,25)}for(let l of layers)"
    assert old in part;part=part.replace(old,new).replace('"Noto Sans CJK SC","Microsoft YaHei",sans-serif','PartACJK,"Microsoft YaHei",sans-serif')
    return part,original_hash

def read_case_selection(p):
    if not p.exists():return []
    x=load(p)
    return x.get('cases',[]) if isinstance(x,dict) else x

def collect_cases(selection):
    wanted={c['event_id'] for c in selection}
    if not wanted:return [],[],{}
    source=WORK/'events/common_events.csv.gz'
    pieces=[chunk[chunk.event_id.isin(wanted)].copy() for chunk in pd.read_csv(source,low_memory=False,chunksize=40000)]
    chosen=pd.concat(pieces,ignore_index=True)
    byid=chosen.set_index('event_id')
    assert wanted<=set(byid.index),'case event missing'
    chains=set(chosen.chain_id.dropna())
    chains.discard('')
    if chains:
        pieces=[chunk[chunk.chain_id.isin(chains)].copy() for chunk in pd.read_csv(source,low_memory=False,chunksize=40000)]
        chosen=pd.concat([chosen,*pieces],ignore_index=True).drop_duplicates('event_id')
    requested={}
    for _,r in chosen.iterrows():requested.setdefault(r.pool_id,set()).update([r.request_a,r.request_b])
    poolteams={}
    for pid,rids in requested.items():
        folder=WORK/'events/native_runs/pools'/pid
        rows=[r for r in load(folder/'request_results.json.gz')['results'] if r['request_id'] in rids]
        teamids={r['team_id'] for r in rows};states={}
        for raw in load(folder/'states.json.gz')['states']:
            if raw['team_id'] not in teamids:continue
            state=raw['automatic']
            if state is None:
                states[raw['team_id']]=dict(points=None,floor=None,status='native_fusion_exception',nodes=[],reason='native_fusion_exception',minimum_support=None)
                continue
            cand=state.get('candidate') or {};nodes=state.get('node_consensus',{}).get('nodes',[])
            states[raw['team_id']]=dict(points=cand.get('points'),floor=cand.get('footprint'),status=cand.get('status'),ring_confirmed=cand.get('ring_confirmed'),
               reason=cand.get('reason'),order_status=cand.get('order_status'),minimum_support=state.get('minimum_support'),
               nodes=[dict(id=n.get('feature_id'),support=n.get('support'),selected=n.get('feature_id') in (cand.get('feature_ids') or []),points=n.get('points'),
                           members=[dict(worker=m.get('worker'),pair_index=m.get('pair_index')) for m in n.get('members',[])]) for n in nodes])
        assert len(states)==len(teamids)
        poolteams[pid]=dict(requests=rows,states=states)
    cases=[]
    for c in selection:
        r=byid.loc[c['event_id']].to_dict()
        cases.append(dict(c,pool_id=r['pool_id'],image_id=r['image_id'],image=r['image'],worker_a=r['worker_a'],worker_b=r['worker_b'],
                          request_a=r['request_a'],request_b=r['request_b'],chain_id=r.get('chain_id'),k=int(r['k'])))
    return cases,chosen.to_dict('records'),poolteams

def labels():
    p=WORK/'assessment/ALL_SELECTED_AND_BASELINE_LABELS.csv.gz'
    if p.exists():
        x=pd.read_csv(p,low_memory=False)
        x['heldout_building']=x.heldout_building.fillna('FULL')
        return x.to_dict('records'),dict(source=str(p.relative_to(WORK)),sha256=sha(p),new_labels_loaded=True)
    # Skeleton preview only: clearly marked until root publishes frozen labels.
    x=pd.concat([pd.read_csv(OLD/'profiles/full_profiles.csv'),pd.read_csv(OLD/'profiles/fold_profiles.csv')])
    x['heldout_building']=x.heldout_building.fillna('FULL')
    rows=[]
    for method,col in [('Q3','Q3_B8L2'),('old_QT','QT_B8L2'),('old_QTD_archive','fine_dtype_B8L2')]:
        a=x[['heldout_building','worker_id',col,'Q_images','Q_buildings']].rename(columns={col:'class_id','Q_images':'n_images','Q_buildings':'n_buildings'})
        a['method_id']=method;a['difficulty']='global';a['source_candidate_id']='archive_'+col
        rows.extend(a.to_dict('records'))
    return rows,dict(source='archive baseline skeleton only; Part A new labels pending',new_labels_loaded=False)

def subset_font(text):
    from fontTools import subset
    from fontTools.ttLib import TTFont
    src=OLD/'presentation/fonts/NotoSansCJKsc-Regular.otf'
    out=HERE/'fonts/PartA-CJK-subset.woff';out.parent.mkdir(parents=True,exist_ok=True)
    font=TTFont(src)
    options=subset.Options();options.flavor='woff';options.recalc_timestamp=False
    sub=subset.Subsetter(options=options);sub.populate(text=text);sub.subset(font)
    for record in list(font['name'].names):
        if record.nameID in (1,4,6,16):
            font['name'].setName('PartA-CJK-Subset' if record.nameID==6 else 'PartA CJK Subset',record.nameID,record.platformID,record.platEncID,record.langID)
    font.flavor='woff';font.save(out)
    license_text=(OLD/'presentation/fonts/OFL_LICENSE.txt').read_text()
    (out.parent/'OFL_LICENSE.txt').write_text(license_text)
    return base64.b64encode(out.read_bytes()).decode(),dict(source_sha256=sha(src),subset_sha256=sha(out),bytes=out.stat().st_size,license='SIL Open Font License 1.1; same license retained')

def build(selection_path,allow_pending=False):
    started=time.monotonic();HERE.mkdir(parents=True,exist_ok=True)
    snap=load(OLD/'fusion/INPUT_SNAPSHOT.json.gz')
    cluster_api={p['meta']['pool_id']:p for p in load(OLD/'clusters/CLUSTER_API.json.gz')['pools']}
    selection=read_case_selection(selection_path)
    raw_selection=load(selection_path) if selection_path.exists() else {}
    case_catalog=raw_selection.get('catalog',{}) if isinstance(raw_selection,dict) else {}
    cases,events,poolteams=collect_cases(selection)
    labelrows,labelsource=labels()
    if not allow_pending:assert labelsource['new_labels_loaded'],'new frozen Part A labels required for final build'
    featpath=WORK/'forward/fold_features.csv.gz'
    features=pd.read_csv(featpath,low_memory=False)
    if 'inner_group' in features:features=features[features.inner_group.isna()]
    features['heldout_building']=features.heldout_building.fillna('FULL')
    assert not features.duplicated(['heldout_building','worker_id']).any()
    pools={}
    for pool in snap['images']:
        if pool['meta']['layer']!='ordinary_manual':continue
        pid=pool['pool_id'];parts={}
        for part in cluster_api[pid]['partitions']:
            for method in ('affinity','complete'):parts[str(int(part['threshold_deg']))+'_'+method]=part[method]
        rfields=['object_id','worker_id','origin','points','B8L2','D10','source_time_seconds','target_time_seconds','time_source_kind','ring_confirmed','order_status']
        pools[pid]=dict(meta=pool['meta'],reference=pool['reference'],records=[{k:r.get(k) for k in rfields} for r in pool['records']],clusters=parts,
                        requests=poolteams.get(pid,{}).get('requests',[]),states=poolteams.get(pid,{}).get('states',{}))
    audit={x['image_id']:x for x in load(OLD/'original_images/ORIGINAL_IMAGE_AUDIT.json')['images']}
    acquired=load(HERE/'CASE_IMAGE_RECEIPT.json') if (HERE/'CASE_IMAGE_RECEIPT.json').exists() else dict(images=[])
    imap={x['image_id']:x for x in acquired['images']};images={}
    for p in pools.values():
        iid=p['meta']['image_id'];meta=audit[iid]
        im=dict(status='原图本页未嵌入；几何可浏览',original_available=meta['status']=='original_release_bytes_verified',data=None)
        if iid in imap and imap[iid].get('local_path'):
            path=HERE/imap[iid]['local_path']
            assert sha(path)==imap[iid]['sha256']
            src=Image.open(path).convert('RGB');src.thumbnail((1536,768),Image.Resampling.LANCZOS)
            buf=io.BytesIO();src.save(buf,format='JPEG',quality=87,optimize=True)
            im.update(data='data:image/jpeg;base64,'+base64.b64encode(buf.getvalue()).decode(),status='案例原图：Release 档案和逐图摘要已核对；显示为JPEG预览',source_sha256=imap[iid]['sha256'])
        elif not im['original_available']:
            preview=REPO/meta['preview_path']
            if preview.exists():
                im.update(data='data:image/jpeg;base64,'+base64.b64encode(preview.read_bytes()).decode(),status='仅仓库预览；当前Release没有原图，未声称原图视觉核验',source_sha256=sha(preview))
        images[iid]=im
    preferred=['forward_selected','reverse_selected','old_QT','old_QTD_archive']
    present={r['method_id'] for r in labelrows}
    methods=[m for m in preferred if m in present]+sorted(present-set(preferred))
    data=dict(schema='personnel_type_discovery_PartA_offline_v1',pools=pools,images=images,labels=labelrows,methods=methods,
              features=features.to_dict('records'),cases=cases,events=events,case_catalog=case_catalog,
              notes=dict(data_release='v2',main_commit='dafa73ac7d8ada9a7f5c0e483d695adcbd916550',frozen_geometry_commit=snap['git_commit'],
                         quality_inventory=7302,quality_images=196,main_records=5719,main_images=177,personnel_ids=60,
                         event_attempts=286666,old_exact_events=270370,new_nested_events=16296,new_fusions=58679,
                         labels_pending=not labelsource['new_labels_loaded'],scope='Part A types and display; retrospective building holdout, not new external blind test'))
    template=(HERE/'part_a_template.html').read_text()
    renderer,renderer_hash=projection_code()
    raw=dumps(data).encode();packed=gzip.compress(raw,compresslevel=6,mtime=0)
    font,fontmeta=subset_font(template+renderer+raw.decode())
    html=template.replace('__REUSED_PROJECTION__',renderer).replace('__DATA__',base64.b64encode(packed).decode()).replace('__FONT__',font)
    out=HERE/('personnel_types_part_a_preview.html' if allow_pending else 'personnel_types_part_a.html')
    out.write_text(html)
    receipt=dict(status='preview_pending_new_labels' if not labelsource['new_labels_loaded'] else 'built_from_frozen_class_outputs',
                 html=out.name,html_bytes=out.stat().st_size,html_sha256=sha(out),pools=len(pools),records=sum(len(p['records']) for p in pools.values()),
                 workers=features.worker_id.nunique(),class_rows=len(labelrows),methods=methods,case_count=len(cases),case_event_count=len(events),
                 embedded_original_images=sum(x.get('data') is not None and x['original_available'] for x in images.values()),
                 embedded_repository_previews=sum(x.get('data') is not None and not x['original_available'] for x in images.values()),
                 unembedded_but_original_available=sum(x.get('data') is None and x['original_available'] for x in images.values()),
                 label_source=labelsource,feature_source_sha256=sha(featpath),
                 whole_pool_geometries='all 5719 frozen ordinary Manual answers; same points, declared ring and bound reference',
                 projection_reuse=dict(original_renderer_block_sha256=renderer_hash,source='archived Pro viewer_template.html geometry through draw3D',
                     display_only_changes=['null-image grid and explicit missing-display label','font family set to embedded subset']),
                 view_binding_changes=['frozen Part A label and event input adapters','draw frozen reference last to remain visible in dense member overlays'],
                 subset_font=fontmeta,raw_data_bytes=len(raw),packed_data_bytes=len(packed),build_seconds=time.monotonic()-started,
                 network_dependencies=[],no_new_fusion=True,no_class_fitting=True,no_case_selection_here=True,
                 original_visual_review='Only actually opened case canvases may be called visually inspected; image retrieval alone is not inspection')
    (HERE/'VIEWER_BUILD_RECEIPT.json').write_text(json.dumps(clean(receipt),ensure_ascii=False,indent=2)+'\n')
    (HERE/'VIEWER_INPUT_CASE_MANIFEST.json').write_text(json.dumps(clean(cases),ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(clean(receipt),ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--cases',type=Path,default=HERE/'CASE_SELECTION.json')
    ap.add_argument('--allow-pending-labels',action='store_true')
    args=ap.parse_args();build(args.cases,args.allow_pending_labels)
