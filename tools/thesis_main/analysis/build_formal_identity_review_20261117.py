"""Simple fresh review of current groups; no historical review labels or exclusions."""
from pathlib import Path
import csv, gzip, io, json, random, shutil, zipfile
ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'research/fusion/formal_identity_review_20261117'
PACKAGE = 'fresh_group_review_20261117_v2'
ZIP = Path('C:/Users/ASUS/Downloads/gap75_evidence_20261117.zip')
def dump(path, value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def main():
    dest=OUT/'reviewer';(dest/'images').mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(ZIP) as z:
        def table(name):return list(csv.DictReader(io.StringIO(z.read('gap75_audit/'+name).decode('utf-8-sig'))))
        primary={r['pool_id'] for r in table('formal_validation_srs60.csv')}
        diagnostic={r['pool_id'] for r in table('formal_validation_diagnostic12.csv')}
        pools=json.loads(gzip.decompress(z.read('gap75_audit/inputs/INPUT_SNAPSHOT.json.gz')))['images']
        ordinary=sorted([p for p in pools if p['meta']['layer']=='ordinary_manual'],key=lambda p:p['pool_id'])
        assert primary == set(random.Random(20261117).sample([p['pool_id'] for p in ordinary],60))
        chosen=[p for p in ordinary if p['pool_id'] in primary|diagnostic]
        assert len(chosen)==72 and not primary&diagnostic
        scenes=[];manifest=[]
        for i,p in enumerate(chosen,1):
            sid=f'I{i:03d}';iid=p['meta']['image_id']
            image=None
            for folder in [ROOT.parent/'original_images',ROOT/'data/mp3d_layout/valid/img',ROOT/'data/mp3d_layout/train/img',ROOT/'data/mp3d_layout/test/img']:
                f=folder/(iid+'.png')
                if f.exists():image=f;break
            if image is None:
                image=next((ROOT/'data').rglob(iid+'.png'))
            shutil.copyfile(image,dest/'images'/(sid+'.png'))
            s=json.loads(gzip.decompress(z.read('gap75_audit/states/'+p['pool_id']+'.json.gz')))
            groups=[dict(id=f'G{k+1}',members=g,selected=k in s['states']['7.5']['selected_group_indices']) for k,g in enumerate(s['states']['7.5']['groups'])]
            scenes.append(dict(id=sid,code=p['meta']['image'],image='images/'+sid+'.png',n=len(p['records']),observations=s['nodes'],groups=groups))
            manifest.append(dict(id=sid,pool_id=p['pool_id'],image=p['meta']['image'],cohort='random60' if p['pool_id'] in primary else 'diagnostic12',difficulty=p['meta']['difficulty']))
    data=dict(package=PACKAGE,gap=7.5,scenes=scenes)
    (dest/'data.js').write_text('const REVIEW_DATA = '+json.dumps(data,ensure_ascii=False,separators=(',',':'))+';\n',encoding='utf-8')
    for name in ['index.html','app.js']:
        shutil.copyfile(Path(__file__).with_name('formal_identity_review_'+name),dest/name)
    dump(OUT/'COORDINATOR_MANIFEST.json',dict(package=PACKAGE,seed=20261117,validation_population=206,excluded_old_images=0,legacy_answers_used=False,random_sample=60,diagnostic_sample=12,scenes=manifest))
    count=dict(scenes=len(scenes),records=sum(s['n'] for s in scenes),observations=sum(len(s['observations']) for s in scenes),population=206,excluded=0)
    dump(OUT/'BUILD_CHECK.json',count);print(json.dumps(count))
if __name__=='__main__':main()
