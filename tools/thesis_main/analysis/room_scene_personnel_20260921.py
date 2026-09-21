"""固定新版局部测量，区分同房留图、同场景留建筑及历史人员名单外部评价。"""
import collections
import itertools
import json
import numpy as np
import pandas as pd

from .analyze_new_manual_20260921 import ROOT, OUT, read, dump
from .summarize_new_manual_20260921 import local
from .clustering_release.pipeline import rows_at
from .clustering_numeric_research.common import next_uncovered
from .audit_collection_plan_20260921 import blocks


def aggregate(records, predicted='prediction'):
    if not records:return {}
    df=pd.DataFrame(records)
    df['error']=abs(df.value-df[predicted]);df['baseline_error']=abs(df.value-df.baseline)
    by=df.groupby(['building','family'])[['error','baseline_error']].mean().groupby('building').mean()
    gain=(by.baseline_error-by.error).to_numpy()
    boot=np.random.default_rng(20260921).choice(gain,(10000,len(gain)),replace=True).mean(1)
    return dict(images=len(df),room_blocks=df.family.nunique(),buildings=len(by),MAE=by.error.mean(),baseline_MAE=by.baseline_error.mean(),
                gain=gain.mean(),building_interval95=np.quantile(boot,[.025,.975]),per_building=by.to_dict('index'))


def load_views():
    rows={r['canonical_annotation_id']:r for r in rows_at(OUT/'responses.jsonl.gz')}
    views={}
    for r in local('distances.json'):
        if r['condition'] not in ['manual','oos']:continue
        ix=[j for j,cid in enumerate(r['ids']) if not rows[cid]['imputed_point']]
        ids=[r['ids'][j] for j in ix]
        key=r['pool'],r['image_id'];assert key not in views
        workers=[rows[c]['worker_id'] for c in ids];assert len(workers)==len(set(workers))
        views[key]=dict(r,ids=ids,workers=workers,image=np.array(r['image'])[np.ix_(ix,ix)],sphere=np.array(r['sphere'])[np.ix_(ix,ix)])
    return rows,views


def main():
    rows,views=load_views()
    from scipy.spatial.distance import jensenshannon
    bycode={v['code']:v for (p,i),v in views.items() if p=='strict'}
    count_controls=[]
    for r in local('same_people_control.json'):
        if r['pool']!='strict':continue
        arrays=[]
        for code in [r['a'],r['b']]:
            v=bycode[code];counts={w:rows[c]['effective_point_count'] for w,c in zip(v['workers'],v['ids'])}
            arrays.append([counts[w] for w in r['workers']])
        aa,bb=arrays;support=sorted(set(aa+bb));ac=collections.Counter(aa);bc=collections.Counter(bb)
        count_controls.append(dict(r,same_person_same_count=np.mean([a==b for a,b in zip(aa,bb)]),
            point_count_js_distance=jensenshannon([ac[n] for n in support],[bc[n] for n in support],base=2)))
    dump('same_room_point_count_control.json',count_controls)
    registry=read('analysis_results/scene_image_exploration_20260910_v1/same_room_selection_registry_v2_20260912.json')
    candidates=[c for c in registry['candidates'] if c['physical_same_supported']]
    family=blocks(candidates);adj=collections.defaultdict(set);comparable=collections.defaultdict(set)
    for c in candidates:
        for a,b in itertools.combinations(c['image_ids'],2):
            adj[a].add(b);adj[b].add(a)
            if c['comparable_for_prediction']:
                comparable[a].add(b);comparable[b].add(a)
    # 已人工整理的粗类继承层，保留原始场景文字；不从目标分歧重分场景。
    scene_source='analysis_results/spatial_dimensions_review_20260913_v2/空间描述与历轮人工记录.json'
    image_meta={i['image_id']:i for i in read(scene_source)['images']}
    # 明确保留未填写粗类，避免groupby丢掉缺失标签的图片。
    scene={i:(r['current_coarse_review']['value'] if r['current_coarse_review']['value'] else '主空间待定') for i,r in image_meta.items()}
    scene_known={'卧室','卫浴','厨房与用餐','工作与学习','起居与休闲','通行与连接','储藏与家务辅助','特殊用途'}
    description=[];predictions=[];summaries=[];room_rows=[]
    for pool in ['historical','strict','conditional']:
        pool_views={i:v for (p,i),v in views.items() if p==pool}
        for iid,v in pool_views.items():
            counts=collections.Counter(rows[c]['effective_point_count'] for c in v['ids']);n=len(v['ids'])
            if not n:continue
            d=v['image'];tri=np.triu_indices(n,1)
            description.append(dict(pool=pool,image_id=iid,code=v['code'],scene=scene[iid],building=v['building'],
                family=family.get(iid,'unconfirmed:'+iid),room_confirmed=iid in family,N=n,
                pair_near=np.mean(d[tri]<=25.6) if n>1 else None,point_count_distribution=dict(counts),
                point_count_entropy=-sum((x/n)*np.log2(x/n) for x in counts.values()),
                next_uncovered5=next_uncovered(d,5,25.6) if n>=10 else None,next_uncovered8=next_uncovered(d,8,25.6) if n>=13 else None))
        for metric,threshold in [('image',25.6),('sphere',9)]:
            for k in [5,8]:
                values={i:next_uncovered(v[metric],k,threshold) for i,v in pool_views.items() if len(v['ids'])>=k+5}
                for iid,value in values.items():
                    building=iid.split('_')[0]
                    outside=[i for i in values if i.split('_')[0]!=building]
                    same_scene=[i for i in outside if scene[i]==scene[iid] and scene[i] in scene_known]
                    base=dict(pool=pool,metric=metric,k=k,image_id=iid,code=pool_views[iid]['code'],scene=scene[iid],building=building,
                        family=family.get(iid,'unconfirmed:'+iid),room_confirmed=iid in family,value=value)
                    if same_scene and outside:
                        # 源图先按房间块、再按建筑等权；未知房间只作未确认图块，不冒充房间。
                        def source_mean(ids):
                            x=pd.DataFrame([dict(building=i.split('_')[0],family=family.get(i,'unconfirmed:'+i),value=values[i]) for i in ids])
                            return x.groupby(['building','family']).value.mean().groupby('building').mean().mean()
                        predictions.append(dict(base,kind='same_scene_other_building',prediction=source_mean(same_scene),baseline=source_mean(outside),
                            source_images=sorted(same_scene),source_buildings=len({i.split('_')[0] for i in same_scene})))
                    same=[i for i in adj[iid] if i in values]
                    if same and outside:
                        others=[i for i in values if i.split('_')[0]==building and family.get(i)!=family.get(iid)]
                        room_rows.append(dict(base,kind='same_room',prediction=np.mean([values[i] for i in same]),baseline=np.mean([values[i] for i in outside]),
                            same_building_other_room=np.mean([values[i] for i in others]) if others else None,source_images=sorted(same),
                            comparable_sources=[i for i in same if i in comparable[iid]]))
    for kind,data in [('scene',predictions),('room',room_rows)]:
        frame=pd.DataFrame(data)
        for (pool,metric,k),part in frame.groupby(['pool','metric','k']):
            scopes=[('all',part)]+[(s,g) for s,g in part.groupby('scene')]
            for scope,g in scopes:summaries.append(dict(kind=kind,pool=pool,metric=metric,k=int(k),scope=scope,**aggregate(g.to_dict('records'))))
    dump('scene_image_statistics.json',description);dump('scene_predictions.json',predictions);dump('room_predictions_extended.json',room_rows);dump('room_scene_summary.json',summaries)

    # 使用已经复算的留建筑旧名单，目标新作答不参与分类。这里只评价有限池覆盖，不再搜索分类。
    roster_path=ROOT/'analysis_results/clustering_numeric_received_20260920/results/personnel/refitted_lobo_rosters.csv'
    rosters=pd.read_csv(roster_path);subtypes=[]
    for pool in ['strict','conditional']:
        for (p,iid),v in views.items():
            if p!=pool:continue
            b=v['building'];available=rosters[rosters.heldout_building==b]
            for config,roster in available.groupby('config'):
                roster=roster.set_index('worker');allix=[j for j,w in enumerate(v['workers']) if w in roster.index]
                if len(allix)<5:continue
                for subtype,g in roster.groupby('subtype'):
                    ix=[j for j in allix if v['workers'][j] in g.index]
                    for k in [3,5,8]:
                        if len(ix)<k+2:continue
                        own=v['image'][np.ix_(ix,ix)];allmat=v['image'][np.ix_(allix,allix)]
                        subtypes.append(dict(pool=pool,config=config,subtype=int(subtype),k=k,image_id=iid,code=v['code'],building=b,
                            family=family.get(iid,'unconfirmed:'+iid),N=len(ix),available_population=len(allix),workers=[v['workers'][j] for j in ix],
                            within_subtype=next_uncovered(own,k,25.6),random_population=next_uncovered(allmat,k,25.6),
                            new_affected=any(rows[v['ids'][j]]['stage']=='scene_stability_stage1' for j in allix)))
    dump('old_roster_new_geometry_subtypes.json',subtypes)
    summary=[];df=pd.DataFrame(subtypes)
    for key,g in df.groupby(['pool','config','subtype','k']):
        for scope,z in [('all',g),('new_affected',g[g.new_affected])]:
            if not len(z):continue
            means=z.groupby(['building','family'])[['within_subtype','random_population']].mean().groupby('building').mean()
            summary.append(dict(pool=key[0],config=key[1],subtype=int(key[2]),k=int(key[3]),scope=scope,images=len(z),buildings=len(means),
                within_subtype=means.within_subtype.mean(),random_population=means.random_population.mean(),
                gap=means.within_subtype.mean()-means.random_population.mean(),minimum_subtype_n=int(z.N.min()),maximum_subtype_n=int(z.N.max())))
    dump('old_roster_subtype_summary.json',summary)
    dump('EXTENDED_ANALYSIS_MANIFEST.json',dict(scene_source=scene_source,roster_source=str(roster_path.relative_to(ROOT)),
        distance_source='distances.json',excluded_from_prediction='借他人信息补点；无唯一上下绑定；重复票；严格池另不计父关联待核查',
        scene_split='整建筑留出；粗类不是物理房间；未确认同房图片不计成已确认房间',
        subtype_scope='留建筑旧名单，当前局部距离评价；k后至少2位同类剩余者。不同子类目标集不同，禁止跨行直接排名；随机对照对未来全体而同类对照对未来同类，不是质量或干预优势。',
        time_status='沿用既有冻结时间分类，新时间未冻结；本轮不重估时间轴',
        source_checks={n:__import__('hashlib').sha256((OUT/n).read_bytes()).hexdigest() for n in ['SUMMARY.json','distances.json','responses.jsonl.gz']}))
    report(description,summaries,room_rows,summary)
    print(json.dumps(dict(scene_predictions=len(predictions),subtype_checks=len(subtypes),report='详细汇报.md'),ensure_ascii=False))


def report(description,summaries,rooms,subtypes):
    d=pd.DataFrame(description);s=pd.DataFrame(summaries);g=pd.DataFrame(subtypes)
    lines=['# 同房间、同场景与人员子类：全历史及新增数据详细汇报','',
        '2026-09-21。审核入口：[新增数据审核](审核/index.html)。本轮复用原局部距离、人员留建筑名单及图库基础；不是新建分类体系或更改Paper A正式合同。原始点、既有人工修复、45条父关联待核查和全部新时间未冻结的口径见[接入报告](复算报告.md)。','',
        '## 结论','',
        '- 同房间有可迁移线索，但仅6栋楼提供k=8的配对评价，明显反例仍在；不能宣布相同房间必有相同收敛人数。',
        '- 相同用途粗类不足以预测相似的分歧/覆盖过程。跨建筑检验当前甚至略差于总体基线；不是否定所有图像特征或场景条件的价值。',
        '- 人员连续差异有证据；尚未找到可以最终定稿的固定人员分类。近期主候选采用易解释的Manual参考偏差粗类，时间保留辅助连续轴、质量＋时间作对照；Semi行为细类另外验证，不强行四类。','',
        '## 1. 相似性究竟指什么','',
        '本次比较标注分布的表现：有效点数分布、同图作答成对相近比例，以及观察k名独立人员后，下一位剩余池人员没有容差内近邻的概率U(k)。U越低表示当前测量下覆盖越充分，不等于正确率。跨视角没有直接比较全景像素坐标：相机位置改变时，点坐标不能直接作为同一物理角点的差值。','',
        '所有几何沿用同有效点数硬约束、上下绑定后固定起点顺序、逐端点最大误差；图上25.6像素与球面9°均保留。本报告的几何相似性受尚未裁决的对应及容差影响，没有IoU权重。对预测移除借他人信息补点记录；这些记录仍保留描述性研究价值。','',
        '| 数据口径 | 无辅助图片 | 人图记录 | 建筑 |','|---|---:|---:|---:|']
    for pool,z in d.groupby('pool'):lines.append(f'| {pool} | {len(z)} | {z.N.sum()} | {z.building.nunique()} |')
    lines += ['', 'historical为旧冻结历史；strict为新增后暂不纳入父记录独立性待核查者；conditional额外计入这些记录。上表是可绑定、可作独立预测的Manual/OOS视图；不是全部原始条数，也没有把Semi混进Manual。strict覆盖240图、2393份、22栋楼；全条件描述性绑定池是2925份。不是每张图都足以估计U(8)。','',
        '## 2. 同一房间','',
        '使用人工台账支持的物理同房关系，源图与目标图分离；重叠子集只用于防泄漏分块，不传递生成未确认配对。先按目标图、房间块、建筑等权汇总误差。k=5/8分别要求目标与源图至少10/13份，留5位池内后续作答。','',
        '| 口径 | k | 目标图 | 建筑 | 同房MAE | 楼外总体基线MAE | 改善 |','|---|---:|---:|---:|---:|---:|---:|']
    for r in s[(s.kind=='room')&(s.metric=='image')&(s.scope=='all')].to_dict('records'):
        lines.append(f"| {r['pool']} | {r['k']} | {r['images']} | {r['buildings']} | {r['MAE']:.4f} | {r['baseline_MAE']:.4f} | {r['gain']:+.4f} |")
    primary=[r for r in rooms if r['pool']=='strict' and r['metric']=='image' and r['k']==8]
    matched=[dict(r,baseline=r['same_building_other_room']) for r in primary if r['same_building_other_room'] is not None]
    control=aggregate(matched);dump('same_building_control.json',control)
    lines += ['',f"严格k=8：41目标、9个同房关系块、6栋建筑；5栋方向为正，改善区间[-0.1528, 0.1688]跨0。与同楼其他房间基线比较，在相同{control['images']}目标上基线MAE为{control['baseline_MAE']:.4f}，同房仍为{control['MAE']:.4f}，但建筑区间同样跨0。不能把41张图当41个独立房间。",'',
        '**范围可比性另有未决：**按旧台账更严格的`comparable_for_prediction`字段，当前41个目标中仅2个有合格源图。其余包含范围/主空间或子集状态未完全确认，不能把“物理同房支持”写成“相同可标范围均已确认”。这些差异本身可研究，故本轮保留广义同房分析；严格可比子集太少，不能单独支撑普遍预测结论。','',
        '只用旧历史源图预测本次新增影响的目标：23目标、3组、全在uNb。MAE改善0.06835；含父关联敏感性为0.05178。这是楼内线索，目标可能同时含新旧作答，不是纯新人员或新建筑前瞻测试。','',
        '同人员控制：严格池120个图对，6栋楼，每对至少10名共同人员。q9-02/q9-13在同一批人员、k=5下U差约0.91；k=8两图分别接近0和0.867。这个反例是旧高人数图，不能归咎新增人员。图对共享图片/房间，不作为120个独立样本。','',
        '点数分布也单独检查：在上述120对中，同一人员在两个视角给出相同有效点数的比例，图对等权平均44.4%；两个点数分布的JS距离均值0.458（0完全相同、1无重叠）。这是由uNb大量相关图对主导的描述值，不是房间等权准确率。按建筑的同点数比例约12.5%—45.7%。同房不等于相同点数；视角、遮挡、细节/范围选择可能不同。即使点数分布不同，分歧程度仍可能相似，例如7y图对的U(5)差约0.003。逐图对和共同人员见same_room_point_count_control.json。','',
        '| 建筑 | 同房关系块 | k=8目标数 | 同房MAE |','|---|---|---:|---:|']
    rr=pd.DataFrame(primary);rr['error']=abs(rr.value-rr.prediction)
    for (b,f),z in rr.groupby(['building','family']):
        codes='、'.join(x.rsplit('-',1)[1] for x in z.code)
        lines.append(f'| {b} | 图{codes} | {len(z)} | {z.error.mean():.4f} |')
    lines += ['', '## 3. 同场景：跨房间、跨建筑的用途粗类','',
        '分类读取最新空间维度台账的`current_coarse_review`，保留待定及历史开放复合标签为未知，不把“未分类”当一个相似场景。同类源图完全排除目标建筑；源图先房间块再建筑等权。全局基线使用完全相同的楼外信息与汇总。未知房间仅作未确认图块，不计成确认房间。','',
        '| 场景 | 当前无辅助图 | 人图记录 | 建筑 | ≥13人的图 | U(8)均值／范围 |','|---|---:|---:|---:|---:|---|']
    for scene,z in d[d.pool=='strict'].groupby('scene'):
        q=z[z.N>=13].next_uncovered8
        text=f'{q.mean():.3f} / {q.min():.3f}—{q.max():.3f}' if len(q) else '不足'
        lines.append(f'| {scene} | {len(z)} | {z.N.sum()} | {z.building.nunique()} | {len(q)} | {text} |')
    lines += ['', '上述均值是描述性图片等权，下面误差是建筑等权，不能混为同一统计。用途相同的图片内部跨度很大。', '',
        '| 跨建筑场景预测 | k | 目标图／建筑 | 同类MAE | 总体基线MAE | 改善 |','|---|---:|---|---:|---:|---:|']
    for r in s[(s.kind=='scene')&(s.scope=='all')&(s.metric=='image')].to_dict('records'):
        lines.append(f"| {r['pool']} | {r['k']} | {r['images']}/{r['buildings']} | {r['MAE']:.4f} | {r['baseline_MAE']:.4f} | {r['gain']:+.4f} |")
    lines += ['', '严格k=8覆盖71图、14栋建筑，MAE 0.2425，高于总体基线0.2090；改善为−0.0335，条件性建筑重采样区间[−0.0588, −0.0123]。球面9°同样不占优（0.2285对0.2020）；纳入父关联后方向不变。此区间仅对当前固定预测结果重采样，不是重新拟合全部处理流程的确认性检验。','',
        '| 场景 | k=8目标／建筑 | 同类MAE | 总体基线MAE | 改善 |','|---|---|---:|---:|---:|']
    for r in s[(s.kind=='scene')&(s.scope!='all')&(s.pool=='strict')&(s.metric=='image')&(s.k==8)].to_dict('records'):
        lines.append(f"| {r['scope']} | {r['images']}/{r['buildings']} | {r['MAE']:.4f} | {r['baseline_MAE']:.4f} | {r['gain']:+.4f} |")
    lines += ['', '起居与休闲有小幅正向，但仅3栋建筑；厨房/储藏各2张目标，不能排出稳定优劣。工作学习虽有9张图，但仅1张达到13人，缺跨楼同类源；特殊用途和待定场景也未形成可评价预测。数据不足不记成失败。', '',
        '这只否定当前“用途粗类均值”足以解释分歧的简单方案，不等于图像相似性无效。既有模型角点数留建筑基线在旧45图/14楼上MAE约0.174，总体均值约0.263；加入更多模型差异特征反而约0.191。这是旧固定数据的另一面板，不能与本表直接排名，但支持优先验证简单结构特征（角点复杂度、局部遮挡/遗漏、交界），暂不开发复杂尺度算法。','',
        '## 4. 人员分类与导师的子类收敛','',
        '导师原文：“7/8/7这个比例，有点不理想，如果能确认一个具体人群子类能收敛才最理想。”另明确ABCD/AABC是人员类型组合，按人独立采集，后处理复用；没有要求固定四类或人为均分。[原始交流](../full_corpus_research_received_20260918/sources/mentor_conversation_6.txt)。','',
        '需要连过三关：①在训练楼上能解释这种行为；②换楼后能重复识别这个子类；③在未参与分类的目标图上，同类真实人数增加时，分布/覆盖逐步稳定。低参考偏差、少簇和类内收敛分别检验；不能在目标图上把离群者摘走后称类内收敛。','',
        '### 已有研究到底支持什么','',
        '- 历史15种Q/T/S/B信息组合、不同组数，共303套配置保留。最新数值包复现六套候选Q2/Q3、QT2/QT3、QTSB3、Semi TRI3的2992条留建筑归属；不是已经确认六种天然人群。',
        '- 连续画像的留建筑MSE相对基线改善：历史参考偏差4.78%（区间包含无改善）、Manual冻结时间48.51%、Semi编辑31.50%、净改善13.01%、scope两轴13.25%/20.81%。这些是不同任务的预测收益，不能加成一个能力总分。',
        '- 历史Semi完整同面板：三指标二分对修改/时间/参考偏差改善21.16%/13.74%/6.03%，连续三轴27.71%/52.47%/13.37%。硬分型未稳定优于保留连续值；旧后续20人分半ARI约0.107，换参考距离/初始化后明显改变。',
        '- 旧时间较快子类在39张共同目标中，18张达到当时的稳定判据，随机8张；但参考偏差4.06对3.81，稳定更多不等于更准确。这是旧0.95方法结果，不能直接搬成当前局部距离下已验证的收敛。',
        '- 仅把当前完整链接换成代表半径，单人组画像的两类名单平均迁移4.68/24人。因此不采用“单人簇多＝低能力或捣乱”作主分类规则。成对分歧比单人组更少依赖分区，但仍不是独立质量依据。','',
        '### 本轮已把旧留建筑名单接到新增后的几何','',
        '不重挑类型，不用新目标作答改名单。以下k=5，每个子类在目标图至少7人，保留2位同类后续作答。随机对照来自同图有分类资料的全体人员，精确期望等于相同人数随机子池的平均；同类未来与全体未来是不同分布，差值不能解释成干预效应。','',
        '| 候选 | 子类号 | 目标／建筑 | 同类U(5) | 同人数随机总体U(5) | 差（低更好） |','|---|---:|---|---:|---:|---:|']
    selected={('Q_2',1),('QT_2',1),('QT_3',1),('QTSB_3',1),('QTSB_3',2),('TRI_3',2),('TRI_3',3)}
    for r in g[(g.pool=='strict')&(g.k==5)&(g.scope=='all')].to_dict('records'):
        if (r['config'],r['subtype']) in selected:lines.append(f"| {r['config']} | {r['subtype']} | {r['images']}/{r['buildings']} | {r['within_subtype']:.4f} | {r['random_population']:.4f} | {r['gap']:+.4f} |")
    lines += ['', 'Q为历史参考偏差，T为合格冻结时间，S为scope两方向代理，B为Semi修改与净改善；TRI为Semi编辑/时间/最终参考偏差。子类号只在同一方案内有意义，每个留建筑折名单可能改变。上表各行目标集合不同，禁止用最低U排名“最佳分类”。所有4542项检查、人员名单与新增影响子集单列在old_roster_new_geometry_subtypes.json。','',
        'Q2低参考偏差候选在k=5可评价17图/5楼，有约9.05个百分点覆盖改善；但新增影响图中尚无该子类足够人数的k=5面板。QT2第一子类58图/15楼改善约6.32个百分点，新增影响仅3图/2楼。新数据主要补到了其他子类，尚不足以宣称新批次独立证实了最有希望的子类。Semi低编辑组W006/W011/W021只有3人，不能研究第5或第8人后的同类收敛。','',
        '### 近期选择','',
        '主候选：在范围/参考明确的Manual校准图上，用参考偏差构成易解释粗类，结合人工确认的边界、细节执行记录解释；目前参考偏差不能冒称全部规则执行。质量＋时间作为对照，时间先保留连续值，待新日志冻结再更新。难以稳定归类者保持未定，不为了人数把剩余人员归为同质类。',
        '保留一条独立行为路线：Semi明确有偏初始化上的保留/修正倾向；只称行为候选，不迁移成Manual能力或认真程度。连续画像始终作基线。最终选型要求在相同目标图、相同人数、相同几何方法下比较，并查看名单稳定性、覆盖和参考质量；不以曲线更平选择规则。',
        '具体子类内部形成稳定多簇也可以是研究结果；少数表达和单人表达保留。全体的表达覆盖另报，不能用易收敛子类替代总体分布。现有185703个真实四人团队的研究没有一致支持AABC普遍优于其他组成，也不证明AABC无研究价值。','',
        '## 5. 审核与下一步','',
        '本轮39项审核不是旧39图：前8项为uNb-40两对对应、两份奇数点、W034重复版本及四份上下绑定；随后31图汇总45条父关联。下拉及文字留空，可暂缓。来源核查不是必须靠逐图看才能判断；若有平台操作记录，应以其说明父关联如何产生。审核导出不会自动改原点或分簇。','',
        '先完成例外核查并冻结一个工作测量版本，再沿同一入口重算。人员主候选在独立校准资料中确定，目标图和新人的验证结果不参与选规则。扩大图像/建筑覆盖比在同一栋楼继续增加大量高度相关视角更能补足泛化证据；具体采集量另按现有计划处理，本报告不派发新任务。','',
        '原始导出及正式协议不变。最新时间未冻结，因此当前不能回答新批次active time是否也同房/同场景相似。对已有冻结时间的人员连续差异证据与本次几何结果分表，不混成同一分母。','',
        '复算：`python -X utf8 -B -m tools.thesis_main.analysis.room_scene_personnel_20260921`；审核生成：`python -X utf8 -B -m tools.thesis_main.analysis.build_new_manual_review_20260921`。输入与字段边界见EXTENDED_ANALYSIS_MANIFEST.json。']
    (OUT/'详细汇报.md').write_text('\n'.join(lines)+'\n',encoding='utf8')


if __name__=='__main__':main()
