"""Copy completed artifacts into the repository's single canonical research folder.

This changes presentation paths only; it never changes numerical results.
"""
from pathlib import Path
import hashlib, json, shutil

ROOT=Path('/workspace/scratch/fe955c3c772c')
WORK=ROOT/'population_work'
OUT=ROOT/'HOHONET_population_latest/research/workers/personnel_population_curves_v2_20261023'

def allowed(p):
    return p.is_file() and not any(s.startswith('.') or s=='__pycache__' for s in p.parts) and not p.name.endswith(('.tmp','.pyc','.log'))

def copy(src,dst):
    dst.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(src,dst)

for p in (WORK/'results').iterdir():
    if allowed(p):copy(p,OUT/'results'/p.name)
for p in (WORK/'coverage').iterdir():
    if allowed(p):copy(p,OUT/'coverage'/p.name)
copy(WORK/'inventory/SOURCE_COMMIT_ANCESTRY.json',OUT/'SOURCE_COMMIT_ANCESTRY.json')

skipnat={'NATURAL_ADJACENT_TRANSITIONS.csv.gz','NATURAL_PAIRED_PATH_INTERVALS.csv.gz','SECTION6_NATURAL_FINDINGS.md'}
for p in (WORK/'difficulty/final24').iterdir():
    if allowed(p) and p.name not in skipnat:copy(p,OUT/'natural'/p.name)
copy(WORK/'difficulty/NATURAL_TABLE_GUIDE.md',OUT/'natural/NATURAL_TABLE_GUIDE.md')

skippolicy={'POLICY_PAIRED_PREFIX_EVENTS.csv.gz','POLICY_DIRECT_PAIRED_PREFIX_EVENTS.csv.gz','POLICY_FINDINGS.md'}
for p in (WORK/'composition/final').iterdir():
    if allowed(p) and p.name not in skippolicy:copy(p,OUT/'policies'/p.name)
copy(WORK/'composition/POLICY_FIELDS.md',OUT/'policies/POLICY_FIELDS.md')
for p in (WORK/'composition').iterdir():
    if allowed(p) and p.suffix in ('.csv','.gz','.json','.md') and not p.name.startswith(('AGGREGATE_','COMPONENT_','FOCAL_','POLICY_FIELDS')):
        copy(p,OUT/'design'/p.name)
for p in (WORK/'compact_events').iterdir():
    if allowed(p):copy(p,OUT/'events'/p.name)
for p in (WORK/'cases').rglob('*'):
    if allowed(p):copy(p,OUT/'cases'/p.relative_to(WORK/'cases'))
for d in ['code','composition','difficulty']:
    for p in (WORK/d).glob('*.py'):
        copy(p,OUT/'code'/p.name)
for p in (WORK/'difficulty').iterdir():
    if allowed(p) and p.suffix in ('.csv','.gz','.json','.md') and not p.name.startswith(('PRELIMINARY_','NATURAL_TABLE_GUIDE')):
        copy(p,OUT/'inputs'/p.name)
for n in ['REUSE_INVENTORY.json','HISTORICAL_GEOMETRY_RECEIPT.json','HISTORICAL_GEOMETRY_SOURCE_INDEX.csv','OLD_NATURAL_SUPPORT.csv','LATER_CACHE_OVERLAPS.csv','ENGINE_EXACT_REUSE_CHECK.json','SAME_ROOM_GEOMETRY_RESTORATION.json']:
    copy(WORK/'inventory'/n,OUT/'inputs'/n)

# Source files are already preserved with their exact original hashes. Update
# only canonical explanatory documents and relational path columns.
for p in [OUT/'events/README.md',OUT/'events/EVENT_RELATION_MAP.csv',OUT/'natural/NATURAL_TABLE_GUIDE.md',OUT/'policies/POLICY_FIELDS.md']:
    s=p.read_text(encoding='utf-8-sig')
    s=s.replace('../composition/','../design/').replace('`composition/','`design/')
    if p.name=='NATURAL_TABLE_GUIDE.md':
        s=s.replace('NATURAL_ADJACENT_TRANSITIONS.csv.gz','../events/NATURAL_ADJACENT_TRANSITIONS_LINKED.csv.gz')
        s=s.replace('NATURAL_PAIRED_PATH_INTERVALS.csv.gz','../events/NATURAL_PAIRED_PATH_INTERVALS_LINKED.csv.gz')
    if p.name=='POLICY_FIELDS.md':
        s=s.replace('POLICY_PAIRED_PREFIX_EVENTS.csv.gz','../events/POLICY_PAIRED_PREFIX_EVENTS_LINKED.csv.gz')
        s=s.replace('POLICY_DIRECT_PAIRED_PREFIX_EVENTS.csv.gz','../events/POLICY_DIRECT_PAIRED_PREFIX_EVENTS_LINKED.csv.gz')
    p.write_text(s,encoding='utf-8-sig' if p.suffix=='.csv' else 'utf-8')

# Correct only the generic role name. The five cases' actual regular classes
# remain called regular when their fold-specific definition supports it.
p=OUT/'cases/final_context/CASE_CURVE_BACKGROUND.md'
s=p.read_text().replace('四种政策为较多转折类优先、历史常规结构类优先、联合较高历史Q类优先、联合较快类优先。',
    '四种政策为较多转折类优先、历史人数最多结构类优先、联合较高历史Q类优先、联合较快类优先。表中五案该最多结构类的逐折语义均为常规，因此案例表仍按实际角色称常规。')
p.write_text(s)

history=OUT/'stage01_natural_baseline'
if history.exists():
    shutil.rmtree(history)
history.mkdir()
(history/'README.md').write_text('# 阶段01原4顺序检查点\n\n完整原阶段已单独保存为 `HOHONET_v2自然人数曲线_阶段01_完整前缀与分项结果_20261023.zip`，另有同阶段中文说明。最终目录不重复打包这批派生表。当前主结论读 `../natural/` 的最终24顺序结果；旧阶段数值保留探索身份，不覆盖新结果。\n')

stats={}
for folder in ['results','natural','policies','events','design','inputs','coverage','cases','code']:
    files=[p for p in (OUT/folder).rglob('*') if allowed(p)]
    stats[folder]={'files':len(files),'bytes':sum(p.stat().st_size for p in files)}
(WORK/'canonical_copy_receipt.json').write_text(json.dumps(stats,indent=2))
print(json.dumps(stats,indent=2))
