#!/usr/bin/env python3
"""独立复核旧图内顺序、分组选择与线性证书；不导入交付代码，不写输入。"""
from pathlib import Path
from decimal import Decimal
import argparse, csv, hashlib, itertools, json, platform
import numpy as np
import pandas as pd
import scipy
from scipy.optimize import linprog

ROOT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--package',type=Path,default=ROOT/'extracted/quality_calibration_repro_20261008')
parser.add_argument('--original-source',type=Path,default=ROOT.parent/'oct8-pro-quality-handoff')
parser.add_argument('--reproduced',type=Path,default=ROOT/'reproduced')
parser.add_argument('--output',type=Path,default=ROOT/'independent_results')
args=parser.parse_args()
PKG = args.package.resolve()
SOURCE = PKG / 'source/oct8-pro-quality-handoff'
ORIGINAL = args.original_source.resolve()
OUT = args.output.resolve()
assert OUT != SOURCE and SOURCE not in OUT.parents
assert OUT != ORIGINAL and ORIGINAL not in OUT.parents
OUT.mkdir(exist_ok=True)
EPS = 1e-12

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def save(name, obj):
    (OUT/name).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')

manifest = json.loads((PKG/'PACKAGE_HASHES.json').read_text())
assert all(sha(PKG/k) == v for k,v in manifest.items())
source_files = [p for p in SOURCE.rglob('*') if p.is_file()]
assert len(source_files) == 60
assert all(p.read_bytes() == (ORIGINAL/p.relative_to(SOURCE)).read_bytes() for p in source_files)
source_sha = {str(p.relative_to(SOURCE)): sha(p) for p in source_files}

df = pd.read_csv(SOURCE/'data/unified36_existing_metrics.csv').set_index('review_id')
sc = json.loads((SOURCE/'data/formulas.json').read_text())['scales']
f = pd.DataFrame(index=df.index)
f['IoU_loss'] = 1 - df.iou
f['C_scaled'] = df.C / 2
f['T_scaled'] = df['T'] * sc['L'] / sc['T']
f['F_scaled'] = df['F'] * sc['L'] / sc['T']
f['Dir_scaled'] = df.dir * sc['L'] / sc['dir']
f['Flat_scaled'] = df.flat * sc['L'] / sc['flat']
lc = f.IoU_loss + f.C_scaled
g = (f.Dir_scaled + f.Flat_scaled) / 2
X = np.column_stack([lc, f.T_scaled, g])
ix = {q:i for i,q in enumerate(df.index)}
images = list(df.image_code.unique())
pairs = []
ties = []
for image in images:
    ids = list(df.index[df.image_code == image])
    for x,y in itertools.combinations(ids, 2):
        sx,sy = df.loc[x,'human_score_original'], df.loc[y,'human_score_original']
        if sx == sy:
            ties.append((x,y)); continue
        better,worse = (x,y) if sx > sy else (y,x)
        pairs.append((image, better, worse))
assert (len(pairs),len(ties)) == (61,29)

grid = [(a/4,b/4,(4-a-b)/4) for a in range(5) for b in range(5-a)]
names = [f'grid_{int(a*4)}{int(b*4)}{int(c*4)}' for a,b,c in grid]
loss = X @ np.asarray(grid).T
rate = np.empty((len(images),len(grid)))
margin_by_image = {}
for im,image in enumerate(images):
    pp = [(b,w) for img,b,w in pairs if img==image]
    margins = np.array([loss[ix[w]]-loss[ix[b]] for b,w in pp])
    margin_by_image[image] = margins
    rate[im] = np.mean(np.where(margins > EPS, 1, np.where(margins < -EPS, 0, .5)),axis=0)

def tie_key(k):
    a,b,c = grid[k]
    return (sum(v > 0 for v in grid[k]), int(b > 0)+int(c > 0), b+c, c,b,names[k])

def select(scores, held, restricted=False):
    eligible = [k for k,w in enumerate(grid) if not restricted or w[0] > 0]
    train = scores[np.arange(len(images)) != held].mean(axis=0)
    best = max(train[k] for k in eligible)
    tied = [k for k in eligible if abs(train[k]-best) <= EPS]
    return min(tied,key=tie_key), tied, float(best)

folds, wrong, restricted_wrong, invariance = [],[],[],[]
for h,image in enumerate(images):
    k,tied,best = select(rate,h)
    kr,_,_ = select(rate,h,True)
    pp = [(b,w) for img,b,w in pairs if img==image]
    mm = margin_by_image[image][:,k]
    mr = margin_by_image[image][:,kr]
    wrong += [(b,w) for (b,w),m in zip(pp,mm) if m < -EPS]
    restricted_wrong += [(b,w) for (b,w),m in zip(pp,mr) if m < -EPS]
    # 对留出图的所有候选评价施加极端替换；训练选择应完全不变。
    # 这是纯内存合成回归测试，不是新人工分，也不写任何评分/GT。
    selected_ids = []
    for replacement in [np.zeros(len(grid)),np.ones(len(grid)),np.arange(len(grid))*100.0,-np.arange(len(grid))*100.0]:
        modified = rate.copy(); modified[h] = replacement
        selected_ids.append(names[select(modified,h)[0]])
    assert selected_ids == [names[k]]*4
    invariance.append({'留出图':image,'原选择':names[k],'四种留出结果替换后选择':selected_ids,'通过':True})
    folds.append({'image':image,'selected':names[k],'weights':grid[k],
                  'tied':[names[t] for t in tied], 'train_macro':best,
                  'correct':int(np.sum(mm>EPS)),'numerical_ties':int(np.sum(abs(mm)<=EPS)),
                  'total':len(pp),'rate':float(rate[h,k]),
                  'restricted_selected':names[kr],'restricted_correct':int(np.sum(mr>EPS))})

published = pd.read_csv(PKG/'results/statistics/outer_fold_weight_selection.csv').set_index('held_out_image')
assert all(r['selected']==published.loc[r['image'],'selected_candidate'] for r in folds)
assert sum(r['correct'] for r in folds)==55
assert sum(r['restricted_correct'] for r in folds)==55
assert all(r['numerical_ties']==0 for r in folds)
macro = float(np.mean([r['rate'] for r in folds]))
assert abs(macro-12/13)<1e-12

a = (f.loc['Q26']-f.loc['Q28']).to_numpy()
b = (f.loc['Q25']-f.loc['Q30']).to_numpy()
A = np.vstack([a,b])
certificate = a+10*b
assert (certificate < 0).all()
# 不依赖 LP 求解器的十进制直接证书（冻结 CSV 字符串与尺度值）。
raw = {r['review_id']:r for r in csv.DictReader((SOURCE/'data/unified36_existing_metrics.csv').open(encoding='utf-8-sig'))}
def exact_features(q):
    r=raw[q]; L=Decimal(str(sc['L']))
    return [1-Decimal(r['iou']),Decimal(r['C'])/2,
            Decimal(r['T'])*L/Decimal(str(sc['T'])),Decimal(r['F'])*L/Decimal(str(sc['T'])),
            Decimal(r['dir'])*L/Decimal(str(sc['dir'])),Decimal(r['flat'])*L/Decimal(str(sc['flat']))]
qa,qb,qc,qd = map(exact_features,['Q26','Q28','Q25','Q30'])
exact_cert = [x-y+10*(z-t) for x,y,z,t in zip(qa,qb,qc,qd)]
assert all(x < 0 for x in exact_cert)

lp_cases = []
for title, margin, normalized in [
    ('严格序：两条margin>=1，无归一',1,False),
    ('弱序：两条margin>=0，非零权重用sum(w)=1排除全零',0,True),
    ('弱序：两条margin>=0，允许全零',0,False),
]:
    result=linprog(np.ones(6),A_ub=-A,b_ub=-np.ones(2)*margin,
                   A_eq=np.ones((1,6)) if normalized else None,
                   b_eq=[1] if normalized else None,bounds=[(0,None)]*6,method='highs')
    lp_cases.append({'测试':title,'可行':bool(result.success),'状态':int(result.status),
                     '见证权重':result.x.tolist() if result.success else None})
assert [r['可行'] for r in lp_cases]==[False,False,True]
maxmin = linprog([0]*6+[-1],A_ub=np.column_stack([-A,np.ones(2)]),b_ub=np.zeros(2),
                 A_eq=[[1]*6+[0]],b_eq=[1],bounds=[(0,None)]*6+[(None,None)],method='highs')
assert maxmin.success and maxmin.x[-1] < -0.02

# 求使 a+lambda*b 全分量严格负的开区间，证明 lambda=10 不是临界取值。
lower=max(-aa/bb for aa,bb in zip(a,b) if bb<0)
upper=min(-aa/bb for aa,bb in zip(a,b) if bb>0)
assert lower < 10 < upper
pd.DataFrame({'分量':f.columns,'a':a,'b':b,'a+10b':certificate,
              '十进制独立复算':[str(x) for x in exact_cert]}).to_csv(OUT/'六分量证书独立复算.csv',index=False,encoding='utf-8-sig')
pd.DataFrame(folds).to_csv(OUT/'按建筑留出独立复算.csv',index=False,encoding='utf-8-sig')
save('留出信息隔离测试.json',invariance)
save('严格序和弱序检验.json',{'tests':lp_cases,'max_min_normalized_margin':float(maxmin.x[-1]),
    'lambda_strictly_negative_interval':[float(lower),float(upper)],
    'certificate_largest_component':float(certificate.max()),
    'interpretation':'弱序在非零非负线性模型下也不可行；允许全零只能得到所有答案完全同值的退化解。间隔数值不是人感知质量间隔。'})

# 比较复跑表与交付表，区分环境/路径元数据与数值差异。
comparison=[]
for sub in ['statistics','geometry']:
    for expected in sorted((PKG/'results'/sub).glob('*.csv')):
        actual=args.reproduced/sub/'results'/expected.name
        assert actual.is_file(),actual
        left,right=pd.read_csv(expected),pd.read_csv(actual)
        assert list(left.columns)==list(right.columns) and left.shape==right.shape
        mismatches=0; maxdiff=0.0
        for col in left:
            if pd.api.types.is_numeric_dtype(left[col]) and pd.api.types.is_numeric_dtype(right[col]):
                x,y=left[col].to_numpy(dtype=float),right[col].to_numpy(dtype=float)
                ok=np.isclose(x,y,rtol=1e-10,atol=1e-10,equal_nan=True)
                mismatches+=int(np.sum(~ok))
                if np.any(np.isfinite(x)&np.isfinite(y)):
                    maxdiff=max(maxdiff,float(np.max(abs(x[np.isfinite(x)&np.isfinite(y)]-y[np.isfinite(x)&np.isfinite(y)]))))
            else:
                mismatches+=int(np.sum(left[col].fillna('').astype(str)!=right[col].fillna('').astype(str)))
        assert mismatches==0,(expected,mismatches)
        comparison.append({'section':sub,'file':expected.name,'rows':len(left),'mismatches':mismatches,'max_numeric_difference':maxdiff})
pd.DataFrame(comparison).to_csv(OUT/'交付表与重跑表比较.csv',index=False,encoding='utf-8-sig')
assert {str(p.relative_to(SOURCE)):sha(p) for p in source_files}==source_sha
summary={'状态':'通过','包哈希核对文件数':len(manifest),'原包逐字节一致文件数':len(source_files),
    '原文件未变':True,'旧异分序对':len(pairs),'旧同档描述对':len(ties),
    '正确序对':sum(r['correct'] for r in folds),'配对比例':55/61,'六图等权':macro,
    '原网格错误':[list(p) for p in wrong],'LC正权重网格错误':[list(p) for p in restricted_wrong],
    '交付CSV数值一致表数':len(comparison),'最大数值差':max(r['max_numeric_difference'] for r in comparison),
    '最大最小归一间隔':float(maxmin.x[-1]),'非零弱序同样不可行':True,
    '无泄漏结论':'代码审阅未见留出图旧分进入该折选权；六折内存干预测试通过。未排除历史选例、特征和网格设计中的研究选择影响。',
    '绝对质量已校准':False,'人工新标签数':0,
    '运行环境':{'python':platform.python_version(),'numpy':np.__version__,'pandas':pd.__version__,'scipy':scipy.__version__}}
save('独立审查摘要.json',summary)
print(json.dumps(summary,ensure_ascii=False,indent=2))
